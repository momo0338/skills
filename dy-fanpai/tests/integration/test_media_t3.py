"""T3 媒体集成（WP3）：合成小视频离线跑通 ffmpeg 编排。

验收准则（EXECUTION_PLAN §11 WP3）："合成媒体离线全通过"。

本测试真实调用 ffmpeg/ffprobe（无网络、无付费 API），覆盖：
- ffprobe 时长读取 ``dur()``；
- 解码体检 ``decode_ok()``（只认坏流标记）；
- 归一化 ``normalize_args`` 真实产物（720x1280）；
- 装配 ``assemble()`` 真实成片（pad 配音 / 静音段 / concat / mux）；
- 原音切段 ``cut_original_audio()`` 真实产物 + 2 秒闸 + ``timing.json``。

需要系统安装 ffmpeg/ffprobe；缺失则整模块 skip。
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess

import pytest

from dy_fanpai.audio import service as A
from dy_fanpai.media import ffmpeg as F

FFMPEG = shutil.which("ffmpeg")
FFPROBE = shutil.which("ffprobe")
pytestmark = pytest.mark.skipif(
    not (FFMPEG and FFPROBE),
    reason="需要系统 ffmpeg/ffprobe 才能跑 T3 媒体集成",
)


def _make_clip(path: str, seconds: float = 3.0) -> None:
    """合成一段竖屏 720x1280 + 440Hz 正弦音频的小视频。"""
    cmd = [
        "ffmpeg", "-y", "-v", "error",
        "-f", "lavfi", "-i", f"color=c=blue:s=720x1280:r=25:d={seconds}",
        "-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest",
        path,
    ]
    subprocess.run(cmd, check=True, capture_output=True, text=True)


def _make_wav(path: str, seconds: float = 2.0) -> None:
    cmd = [
        "ffmpeg", "-y", "-v", "error",
        "-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}",
        "-ar", "44100", "-ac", "2", path,
    ]
    subprocess.run(cmd, check=True, capture_output=True, text=True)


def _resolution(path: str) -> tuple[int, int]:
    out = subprocess.check_output([
        "ffprobe", "-v", "quiet", "-show_entries",
        "stream=width,height", "-of", "csv=p=0", path,
    ]).decode().strip()
    for line in out.splitlines():
        parts = line.split(",")
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            return int(parts[0]), int(parts[1])
    raise AssertionError(f"无法解析分辨率: {out!r}")


def test_dur_and_decode_ok(tmp_path):
    clip = tmp_path / "clip.mp4"
    _make_clip(str(clip), seconds=3.0)
    assert abs(F.dur(str(clip)) - 3.0) < 0.3
    assert F.decode_ok(str(clip)) is True


def test_normalize_real(tmp_path):
    clip = tmp_path / "clip.mp4"
    _make_clip(str(clip), seconds=3.0)
    nv = tmp_path / "norm.mp4"
    subprocess.run(
        F.normalize_args(str(clip), str(nv)),
        check=True, capture_output=True, text=True,
    )
    assert nv.exists()
    assert F.decode_ok(str(nv)) is True
    assert _resolution(str(nv)) == (720, 1280)


def test_assemble_real(tmp_path):
    clips_dir = tmp_path / "clips"
    audio_dir = tmp_path / "audio"
    clips_dir.mkdir()
    audio_dir.mkdir()
    # 两段：S1 有配音，S2 无配音（走静音分支）
    c1 = clips_dir / "S1.mp4"
    c2 = clips_dir / "S2.mp4"
    _make_clip(str(c1), seconds=2.0)
    _make_clip(str(c2), seconds=1.5)
    # S2 故意不提供 wav → assemble 应填静音而不崩溃
    _make_wav(str(audio_dir / "S1.wav"), seconds=2.0)

    plan = tmp_path / "plan.json"
    plan.write_text(json.dumps([{"seg": "S1"}, {"seg": "S2"}]), encoding="utf-8")

    out = tmp_path / "FULL.mp4"
    F.assemble(str(plan), str(clips_dir), str(audio_dir), str(out))
    assert out.exists()
    assert F.decode_ok(str(out)) is True
    assert _resolution(str(out)) == (720, 1280)
    assert abs(F.dur(str(out)) - 3.5) < 0.5


def test_cut_original_audio_real(tmp_path):
    clip = tmp_path / "src.mp4"
    _make_clip(str(clip), seconds=3.0)

    plan = tmp_path / "plan.json"
    plan.write_text(json.dumps({"segments": [
        {"seg": "S1", "start": 0.0, "end": 1.0},
    ]}), encoding="utf-8")

    shotlist = tmp_path / "shotlist.json"
    shotlist.write_text(json.dumps({"shots": [
        {"start": 0.2, "end": 0.8, "dialogue": "大家好"},
    ]}), encoding="utf-8")

    out_dir = tmp_path / "audio_out"
    timing = A.cut_original_audio(
        str(plan), str(clip), str(shotlist), str(out_dir),
    )

    wav = out_dir / "S1.wav"
    assert wav.exists()
    # 2 秒闸：实际跨度 1.0s，但垫到 2.0s 上传下限
    assert F.dur(str(wav)) >= 1.99, "2 秒闸未生效"
    assert os.path.exists(out_dir / "timing.json")
    items = timing["S1"]
    assert items and items[0]["text"] == "大家好"
    assert abs(items[0]["start"] - 0.2) < 0.01
    assert abs(items[0]["dur"] - 0.6) < 0.01
