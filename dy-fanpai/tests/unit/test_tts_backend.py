"""audio/tts_backend.py 离线确定性单测（不碰 VoxCPM/Voicebox 真实环境）。

只测纯函数与编排的可测部分:
- 注册表:register / list_backends / get_backend / backend_available(未知后端)
- _seg_dialogue: 去说话人标签 / 空台词
- _seg_plan_duration: duration / end-start 取时长
- voxcpm_client._build_payload: FileData 带 meta(关键修复) / fn_index / 参数顺序
- voxcpm_client._extract_audio_url: 从 process_completed 提 URL
- voicebox_client 确定性函数: _strip_sse / _parse_status / _build_generate_payload
- synthesize 未知后端 / 不可用后端 抛错(用不可用后端的 available 短路)
"""

import json

import pytest

from dy_fanpai.audio import tts_backend as TB
from dy_fanpai.audio import voicebox_client as VB
from dy_fanpai.audio import voxcpm_client as VC
from dy_fanpai.config import Config


# ---------------------------------------------------------------------------
# 注册表
# ---------------------------------------------------------------------------
def test_list_backends_has_builtin():
    names = TB.list_backends()
    for n in ("voxcpm", "voicebox"):
        assert n in names, f"内置后端 {n} 应在注册表"


def test_get_backend_known_unknown():
    assert TB.get_backend("voicebox") is not None
    assert TB.get_backend("nope") is None


def test_backend_available_unknown():
    ok, msg = TB.backend_available("nope", Config())
    assert not ok
    assert "未知" in msg


def test_register_custom_extension_point():
    """预留扩展点：@register 注册新后端即出现在列表。"""
    @TB.register("ext_test")
    class _Ext:
        name = "ext_test"

        @staticmethod
        def available(cfg):  # pragma: no cover
            return True, "ok"

    try:
        assert "ext_test" in TB.list_backends()
        assert TB.get_backend("ext_test") is _Ext
    finally:
        # 清理注册表，避免污染其他用例
        TB._REGISTRY.pop("ext_test", None)
        if "ext_test" in TB._ORDER:
            TB._ORDER.remove("ext_test")


# ---------------------------------------------------------------------------
# 段台词 / 时长
# ---------------------------------------------------------------------------
def test_seg_dialogue_strips_speaker_labels():
    assert TB._seg_dialogue({"dialogue": "A：你好，B：再见"}) == "你好，再见"
    assert TB._seg_dialogue({"dialogue": " 甲：试试这款冰丝内裤"}) == "试试这款冰丝内裤"
    assert TB._seg_dialogue({"dialogue": "没有标签的一句"}) == "没有标签的一句"


def test_seg_dialogue_empty():
    assert TB._seg_dialogue({"dialogue": ""}) == ""
    assert TB._seg_dialogue({"dialogue": "   "}) == ""


def test_seg_plan_duration_priority():
    assert TB._seg_plan_duration({"duration": 6, "start": 0, "end": 4}) == 6.0
    assert TB._seg_plan_duration({"start": 2.5, "end": 5.0}) == 2.5
    assert TB._seg_plan_duration({"end": 3.0}) == 3.0
    assert TB._seg_plan_duration({}) == 0.0


# ---------------------------------------------------------------------------
# voxcpm_client 确定性函数
# ---------------------------------------------------------------------------
def test_voxcpm_build_payload_has_meta():
    """关键修复：FileData 必须带 meta，否则 Gradio pydantic 校验失败。"""
    p = VC._build_payload("台词", "/tmp/ref.wav", "参考文本")
    assert p["fn_index"] == 2
    assert p["data"][2]["meta"] == {"_type": "gradio.FileData"}
    assert p["data"][2]["path"] == "/tmp/ref.wav"
    assert p["data"][0] == "台词"
    assert p["data"][3] is True  # use_prompt_text
    assert p["data"][4] == "参考文本"  # prompt_text_input
    assert p["data"][5] == 2.0  # cfg
    assert p["session_hash"].startswith("sess_")


def test_voxcpm_extract_audio_url():
    frame = {
        "msg": "process_completed",
        "output": {"data": [{"url": "https://x/gradio_api/file=/tmp/a.mp3",
                             "path": "/tmp/a.mp3"}]},
    }
    assert VC._extract_audio_url(frame) == "https://x/gradio_api/file=/tmp/a.mp3"


def test_voxcpm_extract_audio_url_empty():
    assert VC._extract_audio_url({"output": {"data": []}}) is None
    assert VC._extract_audio_url({"output": {"data": [None]}}) is None
    assert VC._extract_audio_url({"output": {}}) is None


def test_voxcpm_space_url_default_and_custom():
    assert VC._space_url(Config()) == "https://openbmb-voxcpm-demo.hf.space"
    cfg = Config(voxcpm_space_url="https://example.hf.space/")
    assert VC._space_url(cfg) == "https://example.hf.space"


# ---------------------------------------------------------------------------
# synthesize 编排（后端不可用/未知短路，不真调网络）
# ---------------------------------------------------------------------------
def test_synthesize_unknown_backend_raises(tmp_path):
    plan = tmp_path / "segments.json"
    plan.write_text(json.dumps(
        [{"seg": "S1", "dialogue": "你好", "duration": 4}]), encoding="utf-8")
    with pytest.raises(RuntimeError, match="未知 TTS 后端"):
        TB.synthesize(str(plan), str(tmp_path / "out"), "nope", Config())


def test_synthesize_only_filters_segments_before_backend(tmp_path):
    """only 过滤在 available 检查之前对段列表生效（用必然不可用后端验证不报段错误）。"""
    plan = tmp_path / "segments.json"
    plan.write_text(json.dumps([
        {"seg": "S1", "dialogue": "你好", "duration": 4},
        {"seg": "S2", "dialogue": "再见", "duration": 4},
    ]), encoding="utf-8")
    cfg = Config()  # voicebox 无 profile_id/参考音频 → 必然不可用
    # 后端不可用 → 仍抛 RuntimeError（只验证 only 不改变该行为，且不崩在段过滤）
    with pytest.raises(RuntimeError, match="不可用"):
        TB.synthesize(str(plan), str(tmp_path / "out"), "voicebox", cfg, only={"S1"})


def test_synthesize_unavailable_backend_raises(tmp_path):
    """voicebox 无 profile_id/参考音频时应报不可用(不真调网络)。"""
    plan = tmp_path / "segments.json"
    plan.write_text(json.dumps(
        [{"seg": "S1", "dialogue": "你好", "duration": 4}]), encoding="utf-8")
    cfg = Config()
    with pytest.raises(RuntimeError, match="不可用"):
        TB.synthesize(str(plan), str(tmp_path / "out"), "voicebox", cfg)


# ---------------------------------------------------------------------------
# 对齐工具（_align_duration 用真实 ffmpeg 小样本,仅当 ffmpeg 存在才跑）
# ---------------------------------------------------------------------------
def _have_ffmpeg() -> bool:
    import shutil

    return (shutil.which("ffmpeg") is not None
            or shutil.which("/opt/homebrew/bin/ffmpeg") is not None)


@pytest.mark.skipif(not _have_ffmpeg(), reason="需要 ffmpeg")
def test_align_duration_pad_and_compress(tmp_path):
    cfg = Config(ffmpeg_bin="/opt/homebrew/bin/ffmpeg")
    src = str(tmp_path / "src.wav")
    import subprocess

    # 生成 2s 静音作为源
    subprocess.run([cfg.ffmpeg_bin, "-y", "-v", "error", "-f", "lavfi",
                    "-i", "anullsrc=r=24000:cl=mono", "-t", "2", src], check=True)
    # 不足段长 → pad 到 5s
    out = str(tmp_path / "pad.wav")
    dur = TB._align_duration(src, out, 5.0, cfg)
    assert abs(dur - 5.0) < 0.1
    got = TB._probe_duration(out, cfg)
    assert abs(got - 5.0) < 0.1
    # 超长(2s) → 压缩到 1s (超过容差才动)
    out2 = str(tmp_path / "cmp.wav")
    dur2 = TB._align_duration(src, out2, 1.0, cfg)
    assert abs(dur2 - 1.0) < 0.1
    got2 = TB._probe_duration(out2, cfg)
    assert abs(got2 - 1.0) < 0.1


# ---------------------------------------------------------------------------
# voicebox_client 确定性函数
# ---------------------------------------------------------------------------
def test_voicebox_strip_sse():
    assert VB._strip_sse('data: {"status":"completed"}') == '{"status":"completed"}'
    assert VB._strip_sse('data: {"status":"generating"}\n\n') == '{"status":"generating"}'
    assert VB._strip_sse('plain json') == 'plain json'


def test_voicebox_parse_status():
    st = VB._parse_status('data: {"status":"completed","duration":3.5,"error":null}')
    assert st["status"] == "completed"
    assert st["duration"] == 3.5
    st2 = VB._parse_status('data: {"status":"failed","error":"boom"}')
    assert st2["status"] == "failed"
    assert st2["error"] == "boom"
    st3 = VB._parse_status("not json")
    assert st3["status"] == "unknown"


def test_voicebox_build_generate_payload():
    cfg = Config(voicebox_language="zh", voicebox_model_size="1.7B", voicebox_instruct="")
    p = VB._build_generate_payload("你好", "prof-123", cfg)
    assert p["profile_id"] == "prof-123"
    assert p["text"] == "你好"
    assert p["language"] == "zh"
    assert p["model_size"] == "1.7B"
    assert p["normalize"] is True
    assert p["instruct"] is None  # 空 instruct → None

    cfg2 = Config(voicebox_instruct="用温柔的语气")
    p2 = VB._build_generate_payload("你好", "prof", cfg2)
    assert p2["instruct"] == "用温柔的语气"


def test_voicebox_generation_to_status():
    st = VB._generation_to_status({"id": "g1", "status": "generating"})
    assert st["status"] == "generating"
    st2 = VB._generation_to_status(
        {"id": "g2", "status": "completed", "duration": 2.0})
    assert st2["duration"] == 2.0


def test_voicebox_backend_available_requires_config():
    # 无 profile_id 且无参考音频 → 不可用
    ok, msg = TB.backend_available("voicebox", Config())
    assert not ok
    assert "voicebox_profile_id" in msg
    # 有参考音频 → 可用(实际就绪以 /health 为准)
    ok2, _ = TB.backend_available("voicebox", Config(voicebox_reference_audio="/tmp/x.wav"))
    assert ok2
