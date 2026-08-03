"""WP5 字幕成品单元测试（delivery/final.py 确定性逻辑）。"""

from __future__ import annotations

from dy_fanpai.delivery import final as F


def test_fmt_ts_zero():
    assert F.fmt_ts(0) == "00:00:00,000"


def test_fmt_ts_hms():
    # 1h1m1.5s
    assert F.fmt_ts(3661.5) == "01:01:01,500"


def test_sentences_strip_speaker():
    assert F.sentences("A：大家好。B：谢谢。") == ["大家好。", "谢谢。"]


def test_sentences_no_label():
    assert F.sentences("直接说话。") == ["直接说话。"]


def test_build_srt_entries_clock_and_weights():
    segs = [{"dialogue": "大家好。谢谢。", "duration": 2.0}]
    entries = F.build_srt_entries(segs)
    assert len(entries) == 2
    assert entries[0][2] == "大家好。"
    assert entries[0][0] == 0.0
    assert abs(entries[1][1] - 2.0) < 1e-6


def test_build_srt_entries_multi_segment_clock():
    segs = [
        {"dialogue": "第一段。", "duration": 1.0},
        {"dialogue": "第二段。", "duration": 1.0},
    ]
    entries = F.build_srt_entries(segs)
    # 第二段从 1.0s 起
    assert entries[1][0] == 1.0


def test_render_srt_format(tmp_path):
    segs = [{"dialogue": "大家好。谢谢。", "duration": 2.0}]
    entries = F.build_srt_entries(segs)
    s = F.render_srt(entries)
    assert s.startswith("1\n")
    assert s.count(" --> ") == 2
    assert s.endswith("\n\n")
    assert "大家好。" in s and "谢谢。" in s


def test_export_srt_write_and_roundtrip(tmp_path):
    segs = [{"dialogue": "你好。世界。", "duration": 2.0}]
    srt, n = F.export_srt(segs, str(tmp_path / "OUT"))
    assert n == 2
    from dy_fanpai.delivery import jianying as J

    cues = J.parse_srt(srt)
    assert len(cues) == 2
    assert cues[0]["text"] == "你好。"


def test_export_onscreen_skips_none(tmp_path):
    shots = [
        {"onscreen_text": "限时五折", "start": 1, "end": 3, "shot_id": 5},
        {"onscreen_text": "无", "start": 0, "end": 1},
    ]
    md, n = F.export_onscreen(shots, str(tmp_path / "OUT"))
    assert n == 1
    text = open(md, encoding="utf-8").read()
    assert "限时五折" in text and "#5" in text


def test_export_onscreen_shot_id_fallback(tmp_path):
    shots = [{"onscreen_text": "品牌词", "start": 0, "end": 1}]
    md, n = F.export_onscreen(shots, str(tmp_path / "OUT"))
    assert n == 1
    assert "#1" in open(md, encoding="utf-8").read()


def test_subtitle_filter_style_and_escape():
    f = F.subtitle_filter("/tmp/a:b.srt")
    assert "subtitles='" in f
    assert "force_style='" in f
    assert "FontSize=24" in f
    assert "PrimaryColour=&HFFFFFF&" in f
    assert "Outline=2" in f
    # 路径冒号转义
    assert "\\:" in f
