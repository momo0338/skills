"""delivery/final.py — 字幕成品 + FINAL 母版（WP5）。

忠实复刻原项目 export_subs.py 的字幕逻辑（fmt_ts / sentences / export），并补齐
WP5 交付链路：SRT 导出、屏上贴字清单、烧字幕 filter、BGM 混音、FULL→FINAL 母版。

业务铁律（WP1 DESIGN / EXECUTION_PLAN §11 WP5）：
- FULL.mp4 始终保持无字幕、无 BGM（line 208）；FINAL 才叠加字幕/BGM。
- 字幕一律后期加（即梦生成阶段已被要求"保持无字幕"），SRT 用 segments 的【正字台词】。

确定性函数（fmt_ts / sentences / build_srt_entries / subtitle_filter）与 ffmpeg IO
（burn_subtitles / mux_bgm / build_final）解耦，便于离线单测；ffmpeg 调用仅真实交付时发生。
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

# 默认字幕样式（ffmpeg force_style），仅供 subtitle_filter 使用
SUBTITLE_FONT_SIZE = 24
SUBTITLE_FONT_COLOR = "&HFFFFFF&"  # 白字（ASS 颜色 BGR 顺序）
SUBTITLE_OUTLINE = 2


def fmt_ts(sec: float) -> str:
    """SRT 时间戳 ``HH:MM:SS,mmm``（与原 export_subs.fmt_ts 逐字节一致）。"""
    ms = int(round(sec * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


SPK = re.compile(r"^[A-Z甲乙丙][：:]")


def sentences(text: str) -> list[str]:
    """切句（保留标点），剥掉 A：/B： 说话人标签（字幕不显示标签）。

    与原 export_subs.sentences 语义一致。
    """
    parts = [x for x in re.split(r"(?<=[。！？!?；;，,])", text) if x.strip()]
    return [SPK.sub("", x).strip() for x in parts if SPK.sub("", x).strip()]


def build_srt_entries(segments: list[dict[str, Any]]) -> list[tuple[float, float, str]]:
    """从 segments 构造 SRT 条目（段内按字数占比粗摊句时长，段间按 start 归零累加）。

    每条 ``(start, end, text)``；与原 export_subs.export 的 SRT 累加时钟一致。
    """
    entries: list[tuple[float, float, str]] = []
    clock = 0.0
    for s in segments:
        d = (s.get("dialogue") or "").strip()
        dur = float(s.get("duration", 0)) or (float(s["end"]) - float(s["start"]))
        if d:
            sents = sentences(d)
            total = sum(len(x) for x in sents) or 1
            t0 = clock
            for x in sents:
                t1 = t0 + dur * len(x) / total
                entries.append((t0, min(t1, clock + dur), x))
                t0 = t1
        clock += dur
    return entries


def render_srt(entries: list[tuple[float, float, str]]) -> str:
    """渲染 SRT 文本（与原 export_subs 的块格式 ``i\\nts --> ts\\ntext\\n\\n`` 一致）。"""
    blocks = [
        f"{i}\n{fmt_ts(a)} --> {fmt_ts(b)}\n{x}\n\n"
        for i, (a, b, x) in enumerate(entries, 1)
    ]
    return "".join(blocks)


def write_srt(entries: list[tuple[float, float, str]], path: str) -> int:
    """写 SRT 文件，返回条目数。"""
    Path(path).write_text(render_srt(entries), encoding="utf-8")
    return len(entries)


def export_srt(segments: list[dict[str, Any]], out_base: str) -> tuple[str, int]:
    """导出 ``<out_base>.srt``，返回 (路径, 条目数)。"""
    srt = f"{out_base}.srt"
    n = write_srt(build_srt_entries(segments), srt)
    return srt, n


def export_onscreen(shots: list[dict[str, Any]], out_base: str) -> tuple[str, int]:
    """导出原片屏上贴字清单 ``<out_base>_贴字清单.md``，返回 (路径, 条数)。

    与原 export_subs 一致：跳过空 / "无" / "none" 的 onscreen_text；shot_id 缺失时回退序号。
    """
    rows: list[tuple[Any, Any, Any, str]] = []
    for i, sh in enumerate(shots, 1):
        ot = (sh.get("onscreen_text") or "").strip()
        if ot and ot not in ("无", "none"):
            sid = sh.get("shot_id", i)
            rows.append((sh.get("start", 0), sh.get("end", 0), sid, ot))

    md = f"{out_base}_贴字清单.md"
    lines = [
        "# 原片屏上贴字清单(照着做同款贴字;品牌/价格换成你的)\n",
        "",
        "| 时间 | 镜 | 原片贴字 |",
        "|---|---|---|",
    ]
    for a, b, sid, ot in rows:
        lines.append(f"| {a}–{b}s | #{sid} | {ot.replace(chr(10), '<br>')} |")
    Path(md).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return md, len(rows)


def subtitle_filter(
    srt_path: str,
    *,
    font_size: int = SUBTITLE_FONT_SIZE,
    font_color: str = SUBTITLE_FONT_COLOR,
    outline: int = SUBTITLE_OUTLINE,
) -> str:
    """构造 ffmpeg subtitles 烧字幕 filter（确定性）。

    路径中的 ``:`` 需转义为 ``\\:`` 避免 filter 解析错误。
    """
    esc = str(srt_path).replace(":", "\\:")
    style = f"FontSize={font_size},PrimaryColour={font_color},Outline={outline}"
    return f"subtitles='{esc}':force_style='{style}'"


def burn_subtitles(
    video: str, srt: str, out: str, *, vf: str | None = None, ffmpeg_bin: str | None = None
) -> str:
    """烧字幕（ffmpeg subtitles filter，需 libass 支持的构建）。

    依赖 libass；在无 subtitles filter 的 ffmpeg 构建上会抛 CalledProcessError，
    调用方应捕获并标记外部验收未完成。
    ffmpeg_bin 缺省时自动探测（brew ffmpeg-full 优先,见 config._find_ffmpeg_full）。
    """
    if ffmpeg_bin is None:
        from ..config import Config

        ffmpeg_bin = Config.load().ffmpeg_bin
    filt = vf or subtitle_filter(srt)
    cmd = [
        ffmpeg_bin, "-y", "-v", "error", "-i", video,
        "-vf", filt, "-c:v", "libx264", "-crf", "20", "-pix_fmt", "yuv420p",
        "-c:a", "copy", out,
    ]
    subprocess.run(cmd, check=True, capture_output=True, text=True)
    return out


def mux_bgm(video: str, bgm: str, out: str, *, bgm_volume: float = 0.3) -> str:
    """混音 BGM 到原声之下（原声保留，BGM 压低），写 FINAL。"""
    cmd = [
        "ffmpeg", "-y", "-v", "error", "-i", video, "-i", bgm,
        "-filter_complex",
        f"[1:a]volume={bgm_volume}[bg];[0:a][bg]amix=inputs=2:duration=first",
        "-map", "0:v", "-map", "0:a", "-c:v", "copy", "-c:a", "aac",
        "-b:a", "192k", out,
    ]
    subprocess.run(cmd, check=True, capture_output=True, text=True)
    return out


def build_final(
    full: str,
    out: str,
    *,
    srt: str | None = None,
    bgm: str | None = None,
    burn: bool = True,
) -> str:
    """由 FULL 母版产出 FINAL（可烧字幕 + 混 BGM）。

    铁律：FULL 始终不修改（只读），所有变换写入 ``out``。无 srt/bgm 时直接拷贝 FULL。
    """
    cur = full
    if srt and burn:
        burned = os.path.join(os.path.dirname(out) or ".", "_burned_tmp.mp4")
        burn_subtitles(cur, srt, burned)
        cur = burned
    if bgm:
        mux_bgm(cur, bgm, out)
    else:
        if cur != full:
            shutil.move(cur, out)
        else:
            shutil.copy(full, out)
    return out
