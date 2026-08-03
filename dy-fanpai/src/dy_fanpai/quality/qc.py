"""quality/qc.py — 技术 QC（WP5）。

离线可跑的技术质检：ffprobe 探活、解码体检（复用 media.ffmpeg.decode_ok）、
分辨率/时长/流检测，以及口型证据（生成段时长是否覆盖配音时长）。

确定性函数与 ffmpeg/ffprobe IO 分离：probe/qc_video 含 IO；mouth_evidence/qc_report 纯函数。
"""

from __future__ import annotations

import json
import subprocess
from typing import Any

from ..media import ffmpeg as F


def probe(path: str) -> dict[str, Any]:
    """ffprobe 探活：时长、是否有视频/音频流、分辨率（确定性 IO）。"""
    out = subprocess.check_output([
        "ffprobe", "-v", "quiet",
        "-show_entries", "stream=codec_type,width,height",
        "-of", "json", path,
    ]).decode()
    streams = json.loads(out).get("streams", [])
    has_video = any(s.get("codec_type") == "video" for s in streams)
    has_audio = any(s.get("codec_type") == "audio" for s in streams)
    v = next((s for s in streams if s.get("codec_type") == "video"), {})
    w = int(v.get("width", 0)) if v else 0
    h = int(v.get("height", 0)) if v else 0
    return {
        "duration": F.dur(path),
        "has_video": has_video,
        "has_audio": has_audio,
        "width": w,
        "height": h,
    }


def qc_video(path: str, *, target_w: int, target_h: int) -> dict[str, Any]:
    """单文件技术 QC（确定性 IO）。

    检查：视频/音频流存在、分辨率命中目标、解码无坏流、时长 > 0。
    返回含 ``ok`` 与 ``issues`` 的报告 dict。
    """
    try:
        info = probe(path)
    except Exception as e:  # noqa: BLE001 - 探活失败也作为质检问题上报
        return {"path": path, "ok": False, "issues": [f"probe 失败: {e}"]}

    issues: list[str] = []
    if not info["has_video"]:
        issues.append("无视频流")
    if not info["has_audio"]:
        issues.append("无音频流")
    if info["width"] != target_w or info["height"] != target_h:
        issues.append(
            f"分辨率 {info['width']}x{info['height']} != 目标 {target_w}x{target_h}"
        )
    if not F.decode_ok(path):
        issues.append("解码发现坏流(Invalid NAL / Invalid data)")
    if info["duration"] <= 0:
        issues.append("时长 <= 0")

    return {
        "path": path,
        "ok": not issues,
        "duration": info["duration"],
        "has_video": info["has_video"],
        "has_audio": info["has_audio"],
        "resolution": (info["width"], info["height"]),
        "resolution_ok": info["width"] == target_w and info["height"] == target_h,
        "decode_ok": F.decode_ok(path),
        "issues": issues,
    }


def mouth_evidence(video_dur: float, audio_dur: float, *, tol: float = 0.05) -> bool:
    """口型证据：生成段时长是否覆盖配音时长（视频够长，口型才对得上）。

    允许极小负差（生成段略短于配音的容差），避免浮点抖动误报。
    """
    return video_dur >= audio_dur - tol


def qc_report(checks: list[dict[str, Any]]) -> dict[str, Any]:
    """聚合多文件 QC 报告（纯函数）。"""
    passed = [c for c in checks if c.get("ok")]
    return {
        "total": len(checks),
        "passed": len(passed),
        "failed": len(checks) - len(passed),
        "all_passed": len(passed) == len(checks) and len(checks) > 0,
        "details": checks,
    }
