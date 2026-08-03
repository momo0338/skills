"""WP6 端到端流水线（离线可跑部分）：new → approve → run 各阶段。

验证 WP6「完整 CLI」在离线环境能串起流程并正确拦截闸口：
- ``new`` 创建干净工作区；
- ``approve rights`` 后 ``run --stage plan`` 离线产出 segments.json（planner 确定性）；
- ``approve qc`` 后 ``run --stage deliver`` 离线产出 FINAL/SRT/剪映草稿 并登记产物；
- 无 qc 时 ``run --stage deliver`` 被闸口拦截（返回 1，不产出任何成品）。
（reverse/generate/assemble 需 Live/网络/生成产物，离线 run 正确跳过，不虚报完成。）
"""

from __future__ import annotations

import json

from dy_fanpai.cli import main
from dy_fanpai.models import RunManifest, Stage


def _new_ws(tmp_path):
    src = tmp_path / "source.mp4"
    src.write_bytes(b"dummy")
    ws = tmp_path / "ws"
    assert main(["new", "--video", str(src), "--workspace", str(ws)]) == 0
    return ws


def test_new_creates_workspace(tmp_path):
    ws = _new_ws(tmp_path)
    run = RunManifest.model_validate(json.loads((ws / "run.json").read_text(encoding="utf-8")))
    assert run.current_stage == Stage.PREPARE


def test_run_plan_offline(tmp_path):
    ws = _new_ws(tmp_path)
    (ws / "planning" / "shotlist.json").write_text(json.dumps({
        "shots": [{
            "shot_id": "1a", "start": 0.0, "end": 3.0,
            "person": "主播", "action": "展示", "subject": "产品",
            "onscreen_text": "", "dialogue": "你好。世界。",
        }]
    }), encoding="utf-8")
    (ws / "planning" / "assets.json").write_text(json.dumps({
        "host_anchor": "", "host_desc": "", "product_desc": "测试产品",
        "products": {}, "product_verbs": [],
    }), encoding="utf-8")

    assert main(["approve", str(ws), "rights"]) == 0
    assert main(["run", str(ws), "--stage", "plan"]) == 0
    segs = json.loads((ws / "planning" / "segments.json").read_text(encoding="utf-8"))
    assert isinstance(segs, list) and len(segs) >= 1
    run = RunManifest.model_validate(json.loads((ws / "run.json").read_text(encoding="utf-8")))
    assert run.current_stage == Stage.PLAN


def test_run_deliver_offline_with_qc(tmp_path):
    ws = _new_ws(tmp_path)
    (ws / "output" / "FULL.mp4").write_bytes(b"placeholder")
    (ws / "planning" / "segments.json").write_text(json.dumps(
        [{"seg": "S1", "dialogue": "你好。世界。", "duration": 2.0}]), encoding="utf-8")

    assert main(["approve", str(ws), "qc"]) == 0
    assert main(["run", str(ws), "--stage", "deliver"]) == 0
    assert (ws / "output" / "FINAL.mp4").exists()
    assert (ws / "output" / "FULL.srt").exists()
    assert (ws / "output" / "草稿" / "draft_info.json").exists()
    run = RunManifest.model_validate(json.loads((ws / "run.json").read_text(encoding="utf-8")))
    assert any(a.kind == "final" for a in run.artifacts)
    assert run.current_stage == Stage.DELIVER


def test_run_deliver_blocked_without_qc(tmp_path):
    ws = _new_ws(tmp_path)
    (ws / "output" / "FULL.mp4").write_bytes(b"placeholder")
    rc = main(["run", str(ws), "--stage", "deliver"])
    assert rc == 1  # 缺 qc 闸口 → 拦截
    assert not (ws / "output" / "FINAL.mp4").exists()
