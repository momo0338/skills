"""WP5 剪映草稿单元测试（delivery/jianying.py 确定性逻辑）。"""

from __future__ import annotations

import json

import pytest

from dy_fanpai.delivery import jianying as J


def test_parse_srt_roundtrip(tmp_path):
    from dy_fanpai.delivery import final as F

    segs = [{"dialogue": "你好。世界。", "duration": 2.0}]
    srt, _ = F.export_srt(segs, str(tmp_path / "OUT"))
    cues = J.parse_srt(srt)
    assert len(cues) == 2
    assert cues[0]["text"] == "你好。"
    assert cues[0]["start"] == 0.0


def test_build_draft_spec_track_count(tmp_path):
    srt = tmp_path / "FULL.srt"
    srt.write_text("1\n00:00:00,000 --> 00:00:02,000\n你好\n\n", encoding="utf-8")
    spec = J.build_draft_spec(
        video="/x/FULL.mp4",
        srt=str(srt),
        bgm="/x/bgm.mp3",
        onscreen=[{"text": "品牌"}],
    )
    # 视频 + 原声 + 字幕 + 贴纸 + BGM = 5 轨
    assert len(spec["tracks"]) == 5
    types = [t["type"] for t in spec["tracks"]]
    assert types == ["video", "audio", "text", "sticker", "audio"]


def test_build_draft_spec_minimal_two_tracks():
    spec = J.build_draft_spec(video="/x/FULL.mp4")
    assert [t["type"] for t in spec["tracks"]] == ["video", "audio"]


def test_draft_json_valid():
    spec = J.build_draft_spec(video="/x/FULL.mp4")
    text = J.draft_json(spec)
    assert json.loads(text)["draft_name"] == "FULL"


def test_write_draft_json_engine(tmp_path):
    spec = J.build_draft_spec(video="/x/FULL.mp4")
    J.write_draft(spec, str(tmp_path / "draft"))
    assert (tmp_path / "draft" / "draft_info.json").exists()


def test_write_draft_refuses_overwrite_without_force(tmp_path):
    spec = J.build_draft_spec(video="/x/FULL.mp4")
    J.write_draft(spec, str(tmp_path / "draft"))
    with pytest.raises(FileExistsError):
        J.write_draft(spec, str(tmp_path / "draft"))


def test_write_draft_force_overwrites(tmp_path):
    spec = J.build_draft_spec(video="/x/FULL.mp4")
    J.write_draft(spec, str(tmp_path / "draft"))
    p = J.write_draft(spec, str(tmp_path / "draft"), force=True)
    assert p.endswith("draft_info.json")


def test_write_draft_pyjianying_external():
    spec = J.build_draft_spec(video="/x/FULL.mp4")
    with pytest.raises(RuntimeError):
        J.write_draft(spec, "/x/draft", engine="pyjianying")
