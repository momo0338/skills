"""T3 交付集成（WP5）：真实 ffmpeg 跑通 质检 + 混 BGM + FINAL 母版拷贝/非烧字幕路径。

验收准则（EXECUTION_PLAN §11 WP5）："合成媒体离线全通过"（无网络、无付费 API）。

需要系统 ffmpeg/ffprobe；缺失则整模块 skip。
烧字幕(burn_subtitles) 依赖 libass 的 subtitles filter，本机 macOS 构建缺失，
以 HAS_SUBTITLES 探测；缺失则对应用例 skip（标记为外部验收项，CLI 已做
CalledProcessError 兜底 → 退化为无烧字幕 FINAL）。
"""

from __future__ import annotations

import shutil
import subprocess

import pytest

from dy_fanpai.delivery import final
from dy_fanpai.media import ffmpeg as F
from dy_fanpai.quality import qc

FFMPEG = shutil.which("ffmpeg")
FFPROBE = shutil.which("ffprobe")
pytestmark = pytest.mark.skipif(
    not (FFMPEG and FFPROBE),
    reason="需要系统 ffmpeg/ffprobe 才能跑 T3 交付集成",
)


def _has_subtitles() -> bool:
    if not FFMPEG:
        return False
    out = subprocess.run([FFMPEG, "-hide_banner", "-filters"],
                         capture_output=True, text=True).stdout
    return "subtitles" in out


HAS_SUBTITLES = _has_subtitles()


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


def _make_wav(path: str, seconds: float = 3.0) -> None:
    cmd = [
        "ffmpeg", "-y", "-v", "error",
        "-f", "lavfi", "-i", f"sine=frequency=220:duration={seconds}",
        "-ar", "44100", "-ac", "2", path,
    ]
    subprocess.run(cmd, check=True, capture_output=True, text=True)


def test_qc_video_real_ok(tmp_path):
    clip = tmp_path / "clip.mp4"
    _make_clip(str(clip), seconds=3.0)
    r = qc.qc_video(str(clip), target_w=720, target_h=1280)
    assert r["ok"] is True
    assert r["resolution"] == (720, 1280)
    assert r["decode_ok"] is True


def test_mux_bgm_real(tmp_path):
    clip = tmp_path / "clip.mp4"
    _make_clip(str(clip), seconds=3.0)
    bgm = tmp_path / "bgm.wav"
    _make_wav(str(bgm), seconds=3.0)
    out = tmp_path / "FINAL.mp4"
    final.mux_bgm(str(clip), str(bgm), str(out))
    assert out.exists()
    assert F.decode_ok(str(out)) is True
    assert abs(F.dur(str(out)) - 3.0) < 0.3  # 原声时长保留


def test_build_final_copy(tmp_path):
    full = tmp_path / "FULL.mp4"
    _make_clip(str(full), seconds=3.0)
    size0 = full.stat().st_size
    out = tmp_path / "FINAL.mp4"
    final.build_final(str(full), str(out))  # 无 srt/bgm → 直接拷贝
    assert out.exists()
    assert out.stat().st_size == size0       # FINAL 与 FULL 同字节
    assert full.stat().st_size == size0       # FULL 未被修改（只读铁律）


def test_build_final_with_bgm_no_burn(tmp_path):
    full = tmp_path / "FULL.mp4"
    _make_clip(str(full), seconds=3.0)
    bgm = tmp_path / "bgm.wav"
    _make_wav(str(bgm), seconds=3.0)
    out = tmp_path / "FINAL.mp4"
    final.build_final(str(full), str(out), bgm=str(bgm), burn=False)
    assert out.exists()
    assert F.decode_ok(str(out)) is True


def test_burn_subtitles_requires_libass(tmp_path):
    if not HAS_SUBTITLES:
        pytest.skip("本机构建无 libass subtitles filter，烧字幕为外部验收项")
    full = tmp_path / "FULL.mp4"
    _make_clip(str(full), seconds=3.0)
    srt = tmp_path / "s.srt"
    srt.write_text("1\n00:00:00,000 --> 00:00:03,000\n你好\n\n", encoding="utf-8")
    out = tmp_path / "BURNED.mp4"
    final.burn_subtitles(str(full), str(srt), str(out))
    assert out.exists()
    assert F.decode_ok(str(out)) is True
