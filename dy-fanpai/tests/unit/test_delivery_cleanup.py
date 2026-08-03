"""WP5 清理 dry-run 单元测试（delivery/cleanup.py）。"""

from __future__ import annotations

from pathlib import Path

from dy_fanpai.delivery import cleanup as C


def _seed(run: Path) -> None:
    (run / "inputs").mkdir(parents=True)
    (run / "inputs" / "src.mp4").write_bytes(b"source")  # 受保护
    (run / "output").mkdir()
    (run / "output" / "FULL.mp4").write_bytes(b"final")  # 受保护
    (run / "output" / "FULL.partial").write_bytes(b"tmp")  # 临时
    (run / "generation" / "clips").mkdir(parents=True)
    (run / "generation" / "clips" / "raw.tmp").write_bytes(b"tmp")  # 临时
    (run / "generation" / "tasks").mkdir()
    (run / "generation" / "tasks" / "S1.json").write_text("{}")  # 受保护
    (run / "run.json").write_text("{}")  # 受保护


def test_dry_run_reports_only_temp(tmp_path):
    _seed(tmp_path)
    cands = C.plan_cleanup(str(tmp_path), dry_run=True)
    assert str(tmp_path / "output" / "FULL.partial") in cands
    assert str(tmp_path / "generation" / "clips" / "raw.tmp") in cands
    # 受保护项不在候选
    assert str(tmp_path / "inputs" / "src.mp4") not in cands
    assert str(tmp_path / "output" / "FULL.mp4") not in cands
    assert str(tmp_path / "run.json") not in cands
    assert str(tmp_path / "generation" / "tasks" / "S1.json") not in cands


def test_dry_run_does_not_delete(tmp_path):
    _seed(tmp_path)
    C.plan_cleanup(str(tmp_path), dry_run=True)
    assert (tmp_path / "output" / "FULL.partial").exists()


def test_real_delete_removes_temp_only(tmp_path):
    _seed(tmp_path)
    cands = C.plan_cleanup(str(tmp_path), dry_run=False)
    assert len(cands) == 2
    assert not (tmp_path / "output" / "FULL.partial").exists()
    assert not (tmp_path / "generation" / "clips" / "raw.tmp").exists()
    # 受保护项仍在
    assert (tmp_path / "inputs" / "src.mp4").exists()
    assert (tmp_path / "output" / "FULL.mp4").exists()
    assert (tmp_path / "run.json").exists()


def test_extra_protected_prefix(tmp_path):
    (tmp_path / "secret").mkdir()
    (tmp_path / "secret" / "x.tmp").write_bytes(b"tmp")  # 临时但额外受保护
    cands = C.plan_cleanup(str(tmp_path), dry_run=True, protected=["secret/"])
    assert not any("secret" in c for c in cands)
