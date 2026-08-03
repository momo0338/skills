"""audio/service.py 离线确定性单测(不碰 ffmpeg)。

只测纯函数:pad_for_upload(2秒闸) / segment_cut_args(切音频命令) /
shot_in_segment / build_timing(镜级字幕轴)。
cut_original_audio 编排层含 ffmpeg IO,不在单测范围。
"""

import json

from dy_fanpai.audio import service as AS


def test_pad_for_upload_floor():
    """span<2 → 垫到 2.0;span>=2 → 原样(只垫下限,不垫满规划时长)。"""
    assert AS.pad_for_upload(1.0) == 2.0
    assert AS.pad_for_upload(0.5) == 2.0
    assert AS.pad_for_upload(2.0) == 2.0
    assert AS.pad_for_upload(5.0) == 5.0
    assert AS.pad_for_upload(9.09) == 9.09


def test_segment_cut_args_uses_2s_gate():
    """切音频命令: -ss/-to 用段边界, -ar 24000, apad=whole_dur={pad}(pad=max(2,span))。"""
    seg = {"seg": "S1", "start": 1.0, "end": 2.0}  # span=1 → pad=2
    args = AS.segment_cut_args(seg, "src.mp4", "out.wav")
    assert args[0] == "ffmpeg"
    assert "-ss" in args and args[args.index("-ss") + 1] == "1.0"
    assert "-to" in args and args[args.index("-to") + 1] == "2.0"
    assert "-ar" in args and args[args.index("-ar") + 1] == "24000"
    assert "-vn" in args and "-ac" in args
    apad = [a for a in args if a.startswith("apad=")][0]
    assert apad == "apad=whole_dur=2.0"


def test_segment_cut_args_pad_uses_span_when_long():
    """span>2 → pad=span(不垫满规划时长)。"""
    seg = {"seg": "S2", "start": 0.0, "end": 9.0}
    args = AS.segment_cut_args(seg, "src.mp4", "out.wav")
    apad = [a for a in args if a.startswith("apad=")][0]
    assert apad == "apad=whole_dur=9.0"


def test_shot_in_segment():
    assert AS.shot_in_segment({"start": 1.0, "end": 3.0}, 0.0, 10.0)
    assert not AS.shot_in_segment({"start": 9.5, "end": 11.0}, 0.0, 10.0)


def test_build_timing_picks_dialogue_in_bounds():
    """timing 只收段内真实人声 dialogue,记录相对段起点的 start 与镜跨度 dur。"""
    segs = [{"seg": "S1", "start": 0.0, "end": 10.0},
            {"seg": "S2", "start": 10.0, "end": 20.0}]
    shots = [
        {"start": 1.0, "end": 3.0, "dialogue": "第一句"},
        {"start": 12.0, "end": 15.0, "dialogue": "第二句"},
        {"start": 30.0, "end": 31.0, "dialogue": "段外不收"},
    ]
    t = AS.build_timing(segs, shots)
    assert t["S1"] == [{"text": "第一句", "start": 1.0, "dur": 2.0}]
    assert t["S2"] == [{"text": "第二句", "start": 2.0, "dur": 3.0}]


def test_build_timing_skips_empty_dialogue():
    segs = [{"seg": "S1", "start": 0.0, "end": 10.0}]
    shots = [{"start": 1.0, "end": 3.0, "dialogue": ""}]
    assert AS.build_timing(segs, shots)["S1"] == []


def test_build_timing_roundtrip_json():
    """timing 可序列化(交付端消费)。"""
    segs = [{"seg": "S1", "start": 0.0, "end": 5.0}]
    shots = [{"start": 1.0, "end": 2.0, "dialogue": "x"}]
    t = AS.build_timing(segs, shots)
    assert json.loads(json.dumps(t)) == t
