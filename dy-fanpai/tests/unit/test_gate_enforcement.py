"""WP6 闸口验收（验收门 5）：四个闸口不能被 run 或 --force 绕过。

覆盖：
- ``workflow.require_gate`` 在未批准时抛 GateBlocked；
- CLI ``approve`` 记录闸口；
- CLI ``run --stage deliver`` 在无 qc 闸口时拦截（返回 1），批准后执行；
- 不存在 ``--force`` 之类的绕过 flag（argparse 直接拒绝未知参数）。
"""

from __future__ import annotations

import json

import pytest

from dy_fanpai import workflow
from dy_fanpai.cli import main
from dy_fanpai.models import Approval, Gate, RunManifest, Stage


def _write_ws(root, *, approvals=None, current_stage=Stage.PREPARE, live=False):
    root.mkdir(parents=True, exist_ok=True)
    run = RunManifest(current_stage=current_stage, live=live)
    for g in approvals or []:
        run.approvals[g.value] = Approval(gate=g, approved=True, approved_by="integrator")
    root.joinpath("run.json").write_text(run.model_dump_json(indent=2), encoding="utf-8")
    for d in ("inputs", "reverse", "planning", "audio", "generation", "qc", "output"):
        root.joinpath(d).mkdir(parents=True, exist_ok=True)
    return root


def test_require_gate_blocks_without_approval():
    run = RunManifest()
    with pytest.raises(workflow.GateBlocked):
        workflow.require_gate(run, Gate.QC)


def test_approve_records_and_unblocks():
    run = RunManifest()
    workflow.approve_gate(run, Gate.QC, by="integrator")
    workflow.require_gate(run, Gate.QC)  # 不应抛
    assert run.approvals["qc"].approved is True


def test_approve_cli_records(tmp_path):
    root = _write_ws(tmp_path / "ws")
    assert main(["approve", str(root), "qc"]) == 0
    run = RunManifest.model_validate(json.loads((root / "run.json").read_text(encoding="utf-8")))
    assert run.approvals["qc"].approved is True


def test_run_deliver_blocked_without_qc(tmp_path):
    root = _write_ws(tmp_path / "ws")  # 无 qc 批准
    root.joinpath("output", "FULL.mp4").write_bytes(b"placeholder")
    rc = main(["run", str(root), "--stage", "deliver"])
    assert rc == 1  # 闸口拦截
    assert not (root / "output" / "FINAL.mp4").exists()


def test_run_deliver_executes_with_qc(tmp_path):
    root = _write_ws(tmp_path / "ws", approvals=[Gate.QC])
    root.joinpath("output", "FULL.mp4").write_bytes(b"placeholder")
    rc = main(["run", str(root), "--stage", "deliver"])
    assert rc == 0
    assert (root / "output" / "FINAL.mp4").exists()
    assert (root / "output" / "FULL.srt").exists()
    assert (root / "output" / "草稿" / "draft_info.json").exists()
    run = RunManifest.model_validate(json.loads((root / "run.json").read_text(encoding="utf-8")))
    assert any(a.kind == "final" for a in run.artifacts)


def test_run_full_chain_blocked_without_rights(tmp_path):
    root = _write_ws(tmp_path / "ws")  # 全新，无任一闸口
    rc = main(["run", str(root)])  # 默认跑到 deliver，首阶段 reverse 需 rights
    assert rc == 1


def test_no_force_bypass_flag(tmp_path):
    # 验收门 5：闸口不能被 --force 绕过。本包 CLI 根本没有 --force，
    # 任何绕过尝试都被 argparse 拒绝（SystemExit）。
    root = _write_ws(tmp_path / "ws", approvals=[Gate.QC])
    root.joinpath("output", "FULL.mp4").write_bytes(b"placeholder")
    with pytest.raises(SystemExit):
        main(["run", str(root), "--stage", "deliver", "--force"])
