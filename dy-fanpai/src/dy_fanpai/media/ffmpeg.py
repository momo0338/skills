"""media/ffmpeg.py — P5 装配基础：ffprobe 时长、归一化、拼接、解码体检（WP3）。

忠实复刻原项目 assemble.py 的 ffmpeg 编排与踩坑经验，仅做冻结期改造：
1. 音频/路径逻辑集中此处（不再散落）；
2. 确定性函数（dur / normalize_args / pad_audio_args / silence_args / concat_args /
   mux_args / decode_ok）与 subprocess（assemble）解耦，便于离线单测；
   assemble 自身用合成小视频做 T3 集成测试。

业务铁律（assemble 踩坑固化，必须保留）：
- 每段配音 pad 到该段【视频时长】→ 口播段口型对齐（段音频对齐到段起点）；
- 视频先逐段归一化(scale+pad 720x1280+setsar)再 concat → 避免异源 NAL 错；
- 配音轨与画面等长 mux；缺配音的段填静音(纯画面段)；
- 解码体检只认 ``Invalid NAL`` / ``Invalid data`` 字样（07-25 大鹅4 S2 实翻车：
  大小正常但字节流损坏会花屏卡死且骗过大小校验）。
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile

# 装配目标分辨率（竖屏 9:16）
TARGET_W, TARGET_H = 720, 1280
# 坏流判定关键字（字节流损坏但大小正常）
_BAD_MARKERS = ("Invalid NAL", "Invalid data")


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True)


def dur(path: str) -> float:
    """ffprobe → 时长(秒)。"""
    return float(subprocess.check_output(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "csv=p=0", path]).strip())


def normalize_args(clip: str, dst: str) -> list[str]:
    """逐段视频归一化（确定性）：720x1280 + setsar=1 + yuv420p + libx264 crf20。"""
    return [
        "ffmpeg", "-y", "-i", clip, "-an",
        "-c:v", "libx264", "-crf", "20", "-preset", "medium", "-pix_fmt", "yuv420p",
        "-vf", f"scale={TARGET_W}:{TARGET_H}:force_original_aspect_ratio=decrease,"
               f"pad={TARGET_W}:{TARGET_H}:(ow-iw)/2:(oh-ih)/2,setsar=1",
        dst, "-loglevel", "error",
    ]


def pad_audio_args(wav: str, video_dur: float, dst: str) -> list[str]:
    """段配音 pad 到视频时长（确定性），44.1k 立体声。"""
    return [
        "ffmpeg", "-y", "-i", wav, "-af", "apad", "-t", f"{video_dur}",
        "-ar", "44100", "-ac", "2", dst, "-loglevel", "error",
    ]


def silence_args(video_dur: float, dst: str) -> list[str]:
    """无配音段填静音（确定性），44.1k 立体声。"""
    return [
        "ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
        "-t", f"{video_dur}", dst, "-loglevel", "error",
    ]


def concat_args(filelist: str, dst: str, vcopy: bool = True) -> list[str]:
    """concat 合并（确定性）。vcopy=True 用 -c copy（视频/音频流拷贝）。"""
    cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", filelist]
    if vcopy:
        cmd += ["-c", "copy"]
    else:
        cmd += ["-c:v", "libx264", "-crf", "20"]
    cmd += [dst, "-loglevel", "error"]
    return cmd


def mux_args(video_only: str, voiceover: str, out: str) -> list[str]:
    """mux 画面 + 配音轨（确定性）：视频流拷贝，音频 aac 192k。"""
    return [
        "ffmpeg", "-y", "-i", video_only, "-i", voiceover,
        "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac",
        "-b:a", "192k", out, "-loglevel", "error",
    ]


def decode_ok(path: str, probe_secs: int = 2) -> bool:
    """解码体检：大小正常但字节流损坏(NAL错)会花屏卡死。仅认坏标记字样。

    返回 True 表示解码未发现 ``Invalid NAL`` / ``Invalid data``。
    """
    r = _run([
        "ffmpeg", "-v", "error", "-i", path, "-t", str(probe_secs), "-f", "null", "-",
    ])
    return not any(m in r.stderr for m in _BAD_MARKERS)


def assemble(plan_path, clips_dir: str, audio_dir: str | None, out: str) -> None:
    """装配主入口（编排层，含 ffmpeg IO）。

    吃 segments + clips/<seg>.mp4 + audio/<seg>.wav → 完整成片 FULL.mp4。
    缺片跳过（成片会短）；无可用片段直接返回。
    """
    segs = json.load(open(plan_path, encoding="utf-8"))
    work = tempfile.mkdtemp(prefix="assemble_")
    norm_list, audio_list, missing = [], [], []
    for s in segs:
        name = s["seg"]
        clip = os.path.join(clips_dir, f"{name}.mp4")
        if not os.path.exists(clip):
            missing.append(name)
            continue
        vd = dur(clip)
        # 1) 视频归一化
        nv = os.path.join(work, f"{name}.mp4")
        _run(normalize_args(clip, nv))
        norm_list.append(nv)
        # 2) 段配音 pad 到视频时长(无配音则纯静音)
        na = os.path.join(work, f"{name}.wav")
        wav = os.path.join(audio_dir, f"{name}.wav") if audio_dir else ""
        if wav and os.path.exists(wav):
            _run(pad_audio_args(wav, vd, na))
        else:
            _run(silence_args(vd, na))
        audio_list.append(na)

    if missing:
        print(f"[assemble][缺片] {missing} — 跳过,成片会短")
    if not norm_list:
        print("[assemble] 无可用片段")
        return

    # concat 视频
    vlist = os.path.join(work, "v.txt")
    open(vlist, "w").write("\n".join(f"file '{p}'" for p in norm_list))
    video_only = os.path.join(work, "video_only.mp4")
    _run(concat_args(vlist, video_only, vcopy=True))
    # concat 配音轨
    alist = os.path.join(work, "a.txt")
    open(alist, "w").write("\n".join(f"file '{p}'" for p in audio_list))
    voiceover = os.path.join(work, "voiceover.wav")
    _run(concat_args(alist, voiceover, vcopy=True))
    # mux
    _run(mux_args(video_only, voiceover, out))
    print(f"[assemble] 成片 → {out}  {dur(out):.1f}s  {os.path.getsize(out)//1048576}MB")
