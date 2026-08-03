"""dy_fanpai 工作流（WP1 冻结）。

集中状态机、四闸口检查、费用账本与 max_submits 硬上限。任何状态变更必须经此，
禁止在业务模块里各自维护状态（EXECUTION_PLAN §12.2）。
"""

from __future__ import annotations

from datetime import UTC

from .models import (
    Approval,
    CostEntry,
    Gate,
    ProviderName,
    RunManifest,
    RunStatus,
    Stage,
)

# 阶段 → 进入该阶段后期望的状态
_STAGE_STATUS: dict[Stage, RunStatus] = {
    Stage.PREPARE: RunStatus.READY,
    Stage.REVERSE: RunStatus.REVERSED,
    Stage.PLAN: RunStatus.PLANNED,
    Stage.AUDIO: RunStatus.AUDIO_READY,
    Stage.GENERATE: RunStatus.GENERATING,
    Stage.ASSEMBLE: RunStatus.ASSEMBLED,
    Stage.DELIVER: RunStatus.DELIVERED,
}


class GateBlocked(RuntimeError):
    """闸口未通过，run 必须立即停止。"""


class MaxSubmitsExceeded(RuntimeError):
    """超过 max_submits 硬上限。"""


def set_stage(run: RunManifest, stage: Stage) -> None:
    run.current_stage = stage


def set_status(run: RunManifest, status: RunStatus) -> None:
    run.status = status


def mark_stage_done(run: RunManifest, stage: Stage) -> None:
    """进入下一阶段前，把当前阶段标记为对应完成状态。"""
    if stage in _STAGE_STATUS:
        run.status = _STAGE_STATUS[stage]


# ---------------------------------------------------------------------------
# 闸口
# ---------------------------------------------------------------------------
def require_gate(run: RunManifest, gate: Gate) -> None:
    """闸口未批准则抛 GateBlocked（CLI 捕获后停止）。"""
    ap = run.approvals.get(gate.value)
    if ap is None or not ap.approved:
        raise GateBlocked(f"闸口未通过：{gate.value}（G{gate_int(gate)}）")


def approve_gate(run: RunManifest, gate: Gate, by: str, note: str = "") -> None:
    from datetime import datetime

    run.approvals[gate.value] = Approval(
        gate=gate,
        approved=True,
        approved_at=datetime.now(UTC).isoformat(),
        approved_by=by,
        note=note,
    )


def gate_int(gate: Gate) -> int:
    return {"rights": 1, "plan": 2, "cost": 3, "qc": 4}[gate.value]


# ---------------------------------------------------------------------------
# 费用与提交上限
# ---------------------------------------------------------------------------
def enforce_max_submits(run: RunManifest, requested: int) -> None:
    """代码硬执行 max_submits（EXECUTION_PLAN §5 P4）。"""
    if not run.live:
        return
    used = sum(1 for c in run.cost_ledger if c.task_id)
    if used + requested > run.max_submits:
        raise MaxSubmitsExceeded(f"提交数 {used + requested} 超过 max_submits={run.max_submits}")


def add_cost(
    run: RunManifest,
    provider: ProviderName,
    amount: float,
    task_id: str | None = None,
    note: str = "",
) -> None:
    run.cost_ledger.append(CostEntry(provider=provider, amount=amount, task_id=task_id, note=note))
