"""media/audio 对当前算法 golden 的 parity 测试（WP3，验收门 4 统一 golden）。

docs/PARITY.md 待办 1/2：为 WP3（切段 timing / 装配 args）建「当前算法 golden」，
用 assert 级结构化断言固化行为，防回归。golden 由**当前**代码生成并冻结
（见 tests/parity/fixtures/wp3_*.golden.json），测试同时做两类断言：
- 逐字段等于 golden（确定性复现）；
- 业务铁律断言（2 秒闸、归一化参数、解码体检标记等），防止未来改动
  只满足 golden 却违背业务规则。
"""

import json
import os

from dy_fanpai.audio import service as audio
from dy_fanpai.media import ffmpeg as ff

FIX = os.path.join(os.path.dirname(__file__), "fixtures")
SEGS = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "fixtures", "scenarios", "A", "segments.golden.json"))
SHOTS = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "fixtures", "scenarios", "A", "shotlist.json"))
ARGS_GOLDEN = os.path.join(FIX, "wp3_ffmpeg_args.golden.json")
TIMING_GOLDEN = os.path.join(FIX, "wp3_timing.golden.json")


def _load(p):
    return json.load(open(p, encoding="utf-8"))


def test_ffmpeg_args_parity():
    """装配 ffmpeg 参数与 golden 逐字段一致（防参数漂移）。"""
    golden = _load(ARGS_GOLDEN)
    assert ff.normalize_args("clip.mp4", "out.mp4") == golden["normalize_args"]
    assert ff.pad_audio_args("voice.wav", 10.0, "out.wav") == golden["pad_audio_args"]
    assert ff.silence_args(6.5, "silence.wav") == golden["silence_args"]
    assert ff.concat_args("list.txt", "out.mp4", vcopy=True) == golden["concat_args_copy"]
    assert ff.concat_args("list.txt", "out.mp4", vcopy=False) == golden["concat_args_reenc"]
    assert ff.mux_args("video_only.mp4", "voiceover.wav", "FULL.mp4") == golden["mux_args"]


def test_normalize_business_rules():
    """归一化铁律：720x1280、setsar=1、yuv420p、libx264 crf20、-an。"""
    cmd = ff.normalize_args("clip.mp4", "out.mp4")
    joined = " ".join(cmd)
    assert "scale=720:1280" in joined, "目标分辨率 720x1280"
    assert "setsar=1" in joined, "统一 SAR"
    assert "yuv420p" in joined, "像素格式"
    assert "-crf" in joined and "20" in joined, "crf20"
    assert "libx264" in joined, "编码器"
    assert "-an" in joined, "视频归一化不携带音轨"


def test_2s_upload_floor():
    """即梦音频 2 秒下限铁律：只垫到 2s，绝不垫满规划时长。"""
    assert audio.pad_for_upload(1.0) == 2.0, "短音频垫到 2s"
    assert audio.pad_for_upload(2.0) == 2.0, "恰好 2s 不追加"
    assert audio.pad_for_upload(3.0) == 3.0, "超过 2s 保持原长"
    assert audio.pad_for_upload(0.5) == 2.0, "极短音频也垫到 2s"


def test_segment_cut_args_business_rules():
    """切段命令铁律：-ss/-to 用镜边界、单声道 24k、apad 只到 2s 下限。"""
    cmd = audio.segment_cut_args({"seg": "S1", "start": 0.0, "end": 9.09}, "src.mp4", "S1.wav")
    joined = " ".join(cmd)
    assert "-ss" in joined and "0.0" in joined, "起点用镜 start"
    assert "-to" in joined and "9.09" in joined, "终点用镜 end"
    assert "-ac" in joined and "1" in joined, "单声道"
    assert "-ar" in joined and "24000" in joined, "24k 采样率"
    assert "apad=whole_dur=9.09" in joined, "垫到 max(2s, span)"


def test_timing_parity():
    """timing 输出与 golden 逐字段一致（确定性复现）。"""
    segs = _load(SEGS)
    shots = _load(SHOTS)["shots"]
    got = audio.build_timing(segs, shots)
    assert got == _load(TIMING_GOLDEN), "build_timing 输出与 golden 不一致"


def test_timing_shape():
    """timing 结构：每段列表、元素含 text/start/dur、无静音空台词。"""
    segs = _load(SEGS)
    shots = _load(SHOTS)["shots"]
    timing = audio.build_timing(segs, shots)
    for seg_key, items in timing.items():
        assert isinstance(items, list), f"{seg_key} 应为列表"
        for it in items:
            assert set(it) == {"text", "start", "dur"}, f"{seg_key} 元素字段缺失"
            assert it["text"].strip(), f"{seg_key} 出现空台词"
            assert it["dur"] >= 0, f"{seg_key} dur 为负"


def test_timing_offsets_relative_to_segment_start():
    """timing.start 是镜相对段起点的偏移；落在段边界内的台词才收录。"""
    segs = _load(SEGS)
    shots = _load(SHOTS)["shots"]
    timing = audio.build_timing(segs, shots)
    by_seg = {s["seg"]: s for s in segs}
    for seg_key, items in timing.items():
        seg = by_seg[seg_key]
        for it in items:
            # start 是相对偏移，须落在 [0, 段跨度] 内
            assert 0 <= it["start"] <= (seg["end"] - seg["start"]) + 0.02, (
                f"{seg_key} 偏移 {it['start']} 超出段跨度"
            )
