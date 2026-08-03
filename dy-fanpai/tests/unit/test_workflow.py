"""T1 单元与契约：闸口、max_submits、费用账本。"""

import pytest

from dy_fanpai.models import Gate, ProviderName, RunManifest
from dy_fanpai.workflow import (
    GateBlocked,
    MaxSubmitsExceeded,
    add_cost,
    approve_gate,
    enforce_max_submits,
    require_gate,
)


def _run() -> RunManifest:
    return RunManifest(project_id="demo", live=True, max_submits=2)


def test_gate_blocks_when_unapproved():
    run = _run()
    with pytest.raises(GateBlocked):
        require_gate(run, Gate.PLAN)


def test_gate_passes_after_approve():
    run = _run()
    approve_gate(run, Gate.PLAN, by="integrator")
    # 不应抛
    require_gate(run, Gate.PLAN)
    assert run.approvals["plan"].approved


def test_max_submits_enforced():
    run = _run()
    enforce_max_submits(run, requested=2)  # 边界允许
    with pytest.raises(MaxSubmitsExceeded):
        enforce_max_submits(run, requested=3)


def test_max_submits_skipped_when_offline():
    run = RunManifest(live=False, max_submits=0)
    # 离线模式不检查上限
    enforce_max_submits(run, requested=999)


def test_cost_ledger_appends():
    run = _run()
    add_cost(run, ProviderName.DREAMINA, 0.42, task_id="abc")
    assert len(run.cost_ledger) == 1
    assert run.cost_ledger[0].amount == 0.42
