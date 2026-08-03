"""quality 单元（WP5）：qc.py + judge.py 的纯/确定性测试。

probe/qc_video/judge_pair 含 ffprobe/ffmpeg IO，本测试以 monkeypatch 替换
subprocess.check_output 与 media.ffmpeg.dur/decode_ok，保证离线、确定性、可复跑。
mouth_evidence/qc_report/judge_summary 为纯函数，直接断言。

IO 切割依据（EXECUTION_PLAN §3 / §11）：技术 QC 与 subprocess 分离，
确定性函数可零依赖单测；真实 ffprobe/ffmpeg 由 tests/integration/test_delivery_t3.py 覆盖。
"""

from __future__ import annotations

import json
import subprocess

from dy_fanpai.media import ffmpeg as F
from dy_fanpai.quality import judge, qc

# ---- IO 替身 ----

def _probe_check_output(has_video: bool = True, has_audio: bool = True,
                        w: int = 720, h: int = 1280):
    """伪造 ffprobe 的 json 输出（bytes，和真实 check_output 一致可被 .decode）。"""
    streams = []
    if has_video:
        streams.append({"codec_type": "video", "width": w, "height": h})
    if has_audio:
        streams.append({"codec_type": "audio", "width": 0, "height": 0})
    payload = json.dumps({"streams": streams})

    def fake(cmd, *a, **k):  # noqa: ANN001, ANN002, ANN003
        return payload.encode()

    return fake


# ---- qc.py ----

def test_probe_parses_streams(monkeypatch):
    monkeypatch.setattr(subprocess, "check_output",
                        _probe_check_output(w=720, h=1280))
    monkeypatch.setattr(F, "dur", lambda p: 5.0)
    monkeypatch.setattr(F, "decode_ok", lambda p: True)
    info = qc.probe("x.mp4")
    assert info["has_video"] and info["has_audio"]
    assert info["width"] == 720 and info["height"] == 1280
    assert info["duration"] == 5.0


def test_qc_video_ok(monkeypatch):
    monkeypatch.setattr(subprocess, "check_output",
                        _probe_check_output(w=720, h=1280))
    monkeypatch.setattr(F, "dur", lambda p: 5.0)
    monkeypatch.setattr(F, "decode_ok", lambda p: True)
    r = qc.qc_video("x.mp4", target_w=720, target_h=1280)
    assert r["ok"] is True
    assert r["resolution_ok"] is True
    assert r["decode_ok"] is True
    assert r["issues"] == []


def test_qc_video_bad_resolution(monkeypatch):
    monkeypatch.setattr(subprocess, "check_output",
                        _probe_check_output(w=1080, h=1920))
    monkeypatch.setattr(F, "dur", lambda p: 5.0)
    monkeypatch.setattr(F, "decode_ok", lambda p: True)
    r = qc.qc_video("x.mp4", target_w=720, target_h=1280)
    assert r["ok"] is False
    assert any("分辨率" in i for i in r["issues"])


def test_qc_video_no_audio(monkeypatch):
    monkeypatch.setattr(subprocess, "check_output",
                        _probe_check_output(has_audio=False))
    monkeypatch.setattr(F, "dur", lambda p: 5.0)
    monkeypatch.setattr(F, "decode_ok", lambda p: True)
    r = qc.qc_video("x.mp4", target_w=720, target_h=1280)
    assert r["ok"] is False
    assert any("无音频流" in i for i in r["issues"])


def test_qc_video_probe_failure(monkeypatch):
    def boom(cmd, *a, **k):  # noqa: ANN001, ANN002, ANN003
        raise RuntimeError("ffprobe 挂了")
    monkeypatch.setattr(subprocess, "check_output", boom)
    r = qc.qc_video("x.mp4", target_w=720, target_h=1280)
    assert r["ok"] is False
    assert any("probe 失败" in i for i in r["issues"])


def test_mouth_evidence():
    assert qc.mouth_evidence(5.0, 5.0) is True
    assert qc.mouth_evidence(5.0, 4.9) is True    # 容差内
    assert qc.mouth_evidence(5.05, 5.0) is True   # 略长 ok
    assert qc.mouth_evidence(4.9, 5.0) is False   # 差 > 0.05 容差


def test_qc_report():
    checks = [{"ok": True, "path": "a"}, {"ok": False, "path": "b"}]
    rep = qc.qc_report(checks)
    assert rep["total"] == 2 and rep["passed"] == 1 and rep["failed"] == 1
    assert rep["all_passed"] is False
    assert qc.qc_report([{"ok": True}])["all_passed"] is True
    assert qc.qc_report([])["all_passed"] is False


# ---- judge.py ----

def _patch_probe(monkeypatch, orig_dur=10.0, gen_dur=9.5, w=720, h=1280):
    def fake_probe(p):
        dur = orig_dur if "orig" in p else gen_dur
        return {"duration": dur, "width": w, "height": h,
                "has_video": True, "has_audio": True}
    # judge.py 以 `from .qc import probe` 绑定了引用，必须替换 judge 命名空间里的 probe
    monkeypatch.setattr(judge, "probe", fake_probe)
    monkeypatch.setattr(F, "decode_ok", lambda p: True)


def test_judge_pair_pass(monkeypatch):
    _patch_probe(monkeypatch, orig_dur=10.0, gen_dur=9.5)
    r = judge.judge_pair("orig.mp4", "gen.mp4", target_w=720, target_h=1280)
    assert r["structural_pass"] is True
    assert 0.5 <= r["duration_ratio"] <= 2.0
    assert r["both_decode_ok"] is True
    assert r["resolution_match"] is True


def test_judge_pair_bad_ratio(monkeypatch):
    _patch_probe(monkeypatch, orig_dur=1.0, gen_dur=100.0)
    r = judge.judge_pair("orig.mp4", "gen.mp4", target_w=720, target_h=1280)
    assert r["structural_pass"] is False
    assert r["duration_ratio"] > 2.0


def test_judge_pair_decode_fail(monkeypatch):
    _patch_probe(monkeypatch, orig_dur=10.0, gen_dur=9.5)
    monkeypatch.setattr(F, "decode_ok", lambda p: False)
    r = judge.judge_pair("orig.mp4", "gen.mp4", target_w=720, target_h=1280)
    assert r["structural_pass"] is False
    assert r["both_decode_ok"] is False


def test_judge_pair_resolution_mismatch(monkeypatch):
    _patch_probe(monkeypatch, orig_dur=10.0, gen_dur=9.5, w=1080, h=1920)
    r = judge.judge_pair("orig.mp4", "gen.mp4", target_w=720, target_h=1280)
    assert r["structural_pass"] is False
    assert r["resolution_match"] is False


def test_judge_summary():
    pairs = [{"structural_pass": True}, {"structural_pass": False}]
    s = judge.judge_summary(pairs)
    assert s["total"] == 2 and s["passed"] == 1 and s["failed"] == 1
    assert s["all_passed"] is False
    assert judge.judge_summary([{"structural_pass": True}])["all_passed"] is True
