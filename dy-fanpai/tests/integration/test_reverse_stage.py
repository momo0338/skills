"""pipeline reverse 阶段接入测试：反推腿选择 + 产物落盘 + plan 自动带入。

验证 WP6「完整 CLI」的 reverse 阶段在 live 模式能驱动反推腿（seed/kimi/qwen），
并让后续 plan 阶段自动消费 reverse/shotlist.json。网络调用全部 monkeypatch，
不真实调用 API（T4 纪律）。
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
    return ws, src


def _enable_live(ws):
    """把 run.json 的 live 打开(费用审批后 reverse 才能跑)。"""
    p = ws / "run.json"
    d = json.loads(p.read_text(encoding="utf-8"))
    d["live"] = True
    p.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")


def test_run_reverse_qwen_live(monkeypatch, tmp_path):
    """live + --leg qwen: 真调 qwen.reverse(被 mock),产物写 reverse/shotlist.json。"""
    ws, src = _new_ws(tmp_path)
    _enable_live(ws)

    from dy_fanpai.reverse import qwen

    called = {}

    def fake_qwen_reverse(video, out=None, **kw):
        called["video"] = video
        d = {
            "overall": {"product": "测试产品", "style": "s", "narrative_arc": "n",
                        "why_viral": "w", "full_transcript": ""},
            "shots": [{"shot_id": 1, "start": 0.0, "end": 3.0, "dialogue": "你好。世界。",
                       "person": "主播", "action": "展示", "subject": "产品",
                       "product_role": "package_text", "host_on_camera": True,
                       "onscreen_text": "", "key_colors": ""}],
        }
        if out:
            json.dump(d, open(out, "w"), ensure_ascii=False, indent=2)
        return d

    monkeypatch.setattr(qwen, "reverse", fake_qwen_reverse)

    assert main(["approve", str(ws), "rights"]) == 0
    assert main(["run", str(ws), "--stage", "reverse", "--leg", "qwen"]) == 0
    rev = ws / "reverse" / "shotlist.json"
    assert rev.exists(), "reverse/shotlist.json 应产出"
    data = json.loads(rev.read_text(encoding="utf-8"))
    assert data["shots"][0]["dialogue"] == "你好。世界。"
    run = RunManifest.model_validate(json.loads((ws / "run.json").read_text(encoding="utf-8")))
    assert run.stage_results["reverse"]["leg"] == "qwen"


def test_run_reverse_offline_skips(tmp_path):
    """离线(live=false)时 reverse 正确跳过,不产出 shotlist,不虚报完成。"""
    ws, _ = _new_ws(tmp_path)
    assert main(["approve", str(ws), "rights"]) == 0
    rc = main(["run", str(ws), "--stage", "reverse"])
    assert rc == 0  # 离线跳过不报错
    assert not (ws / "reverse" / "shotlist.json").exists(), "离线不应产出反推结果"


def test_run_reverse_bad_leg(tmp_path):
    """非法反推腿 → argparse choices 约束在 CLI 层拒绝(SystemExit)。"""
    ws, _ = _new_ws(tmp_path)
    _enable_live(ws)
    assert main(["approve", str(ws), "rights"]) == 0
    import pytest

    with pytest.raises(SystemExit):
        main(["run", str(ws), "--stage", "reverse", "--leg", "nope"])
    assert not (ws / "reverse" / "shotlist.json").exists(), "非法腿不应产出"


def test_plan_consumes_reverse_shotlist(monkeypatch, tmp_path):
    """plan 阶段自动消费 reverse/shotlist.json(无需手动复制到 planning/)。"""
    ws, src = _new_ws(tmp_path)
    _enable_live(ws)
    # 直接写 reverse/shotlist.json,模拟已反推
    rev = ws / "reverse" / "shotlist.json"
    rev.parent.mkdir(exist_ok=True)
    rev.write_text(json.dumps({
        "overall": {"product": "p", "style": "s", "narrative_arc": "n",
                    "why_viral": "w", "full_transcript": ""},
        "shots": [{"shot_id": 1, "start": 0.0, "end": 3.0, "dialogue": "你好。世界。",
                   "person": "主播", "action": "展示", "subject": "产品",
                   "product_role": "package_text", "host_on_camera": True,
                   "onscreen_text": "", "key_colors": ""}],
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


def test_run_audio_source_live(monkeypatch, tmp_path):
    """live + plan 已批: 原音切段(被 mock)产出 wav 并登记,离线正确跳过。"""
    ws, _ = _new_ws(tmp_path)
    _enable_live(ws)
    (ws / "planning" / "segments.json").write_text(json.dumps(
        [{"seg": "S1", "start": 0.0, "end": 3.0, "dialogue": "你好。世界。"}]), encoding="utf-8")
    (ws / "planning" / "shotlist.json").write_text(json.dumps(
        {"shots": [{"shot_id": 1, "start": 0.0, "end": 3.0,
                    "dialogue": "你好。世界。"}]}), encoding="utf-8")

    from dy_fanpai.audio import service as audio_mod

    def fake_cut(plan, video, shotlist, out_dir, cfg=None):
        import os

        os.makedirs(out_dir, exist_ok=True)
        open(os.path.join(out_dir, "S1.wav"), "wb").write(b"RIFF")
        t = {"S1": [{"text": "你好。世界。", "start": 0.0, "dur": 3.0}]}
        json.dump(t, open(os.path.join(out_dir, "timing.json"), "w"), ensure_ascii=False)
        return t

    monkeypatch.setattr(audio_mod, "cut_original_audio", fake_cut)

    assert main(["approve", str(ws), "rights"]) == 0
    assert main(["approve", str(ws), "plan"]) == 0
    assert main(["run", str(ws), "--stage", "audio"]) == 0
    assert (ws / "audio" / "segments" / "S1.wav").exists()
    assert (ws / "audio" / "timing.json").exists(), "timing.json 应复制到规范位置"
    run = RunManifest.model_validate(json.loads((ws / "run.json").read_text(encoding="utf-8")))
    assert run.stage_results["audio"]["mode"] == "source"


def test_run_audio_offline_skips(tmp_path):
    """离线(live=false)时 audio 正确跳过,不产出。"""
    ws, _ = _new_ws(tmp_path)
    assert main(["approve", str(ws), "rights"]) == 0
    assert main(["approve", str(ws), "plan"]) == 0
    rc = main(["run", str(ws), "--stage", "audio"])
    assert rc == 0
    segs_dir = ws / "audio" / "segments"
    assert not segs_dir.exists() or not list(segs_dir.glob("*.wav"))
