#!/usr/bin/env python3
"""抽帧 + tesseract OCR，从视频画面字幕提取带时间窗的逐句字幕流。

用法:
  python3 ocr_subtitles.py <视频.mp4> <输出目录> [--fps 1] [--region bottom|full]

输出:
  <输出目录>/subtitles.txt   — 逐句字幕流（[MM:SS-MM:SS] 文本）
  <输出目录>/frames/         — 抽帧缓存（重复运行可复用）

依赖: ffmpeg, tesseract (chi_sim)
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


def run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def extract_frames(video: Path, out_dir: Path, fps: float, region: str) -> list[Path]:
    frames_dir = out_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    # 清掉旧帧，避免上一轮残留混入
    for old in frames_dir.glob("*.jpg"):
        old.unlink()

    vf = f"fps={fps}"
    if region == "bottom":
        # 字幕通常位于画面下部约 1/4 区域，裁剪掉上部干扰
        vf += ",crop=iw:ih*0.28:0:ih*0.72"
    r = run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(video), "-vf", vf,
             "-q:v", "2", str(frames_dir / "frame_%04d.jpg")])
    if r.returncode != 0:
        print(f"ffmpeg 抽帧失败: {r.stderr[:300]}", file=sys.stderr)
        sys.exit(1)
    return sorted(frames_dir.glob("*.jpg"))


def ocr_frame(frame: Path) -> str:
    r = run(["tesseract", str(frame), "-", "-l", "chi_sim", "--psm", "6"])
    if r.returncode != 0:
        return ""
    return r.stdout


def clean_line(line: str) -> str:
    """去空白、去纯噪声行。"""
    t = re.sub(r"\s+", "", line)
    # 常见 OCR 噪声：全英文/数字/符号混排、单字符、无中文字符的行
    if len(t) < 2:
        return ""
    if not re.search(r"[\u4e00-\u9fff]", t):
        return ""
    # 中文字符占比过低视为噪声
    zh = len(re.findall(r"[\u4e00-\u9fff]", t))
    if zh / max(len(t), 1) < 0.5:
        return ""
    return t


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("video", type=Path)
    ap.add_argument("out_dir", type=Path)
    ap.add_argument("--fps", type=float, default=1.0)
    ap.add_argument("--region", choices=["bottom", "full"], default="bottom")
    args = ap.parse_args()

    for tool in ("ffmpeg", "tesseract"):
        if shutil.which(tool) is None:
            print(f"缺少依赖: {tool}", file=sys.stderr)
            sys.exit(1)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    frames = extract_frames(args.video, args.out_dir, args.fps, args.region)
    if not frames:
        print("未抽到任何帧", file=sys.stderr)
        sys.exit(1)

    # 逐帧 OCR，记录时间戳
    lines: list[tuple[float, str]] = []
    for i, frame in enumerate(frames):
        ts = i / args.fps
        for raw in ocr_frame(frame).splitlines():
            text = clean_line(raw)
            if text:
                lines.append((ts, text))

    # 相邻去重：同一句字幕连续多帧出现只保留一条（时间窗取首尾）
    merged: list[tuple[float, float, str]] = []
    for ts, text in lines:
        if merged and merged[-1][2] == text:
            merged[-1] = (merged[-1][0], ts, text)
        else:
            merged.append((ts, ts, text))

    out = args.out_dir / "subtitles.txt"
    with out.open("w", encoding="utf-8") as f:
        for start, end, text in merged:
            f.write(f"[{start:05.1f}-{end:05.1f}] {text}\n")
    print(f"OCR 完成: {len(frames)} 帧 -> {len(merged)} 条字幕")
    print(f"输出: {out}")


if __name__ == "__main__":
    main()
