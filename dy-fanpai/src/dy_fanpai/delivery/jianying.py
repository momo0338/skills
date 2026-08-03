"""delivery/jianying.py — 剪映草稿交付（WP5）。

构建 5 轨剪映草稿的确定性【规格】，并提供离线可写的 JSON 引擎；真机 pyJianYingDraft
写入为外部验收项（需 Windows/WSL 机器 + 剪映版本 + 草稿目录），本环境不执行。

业务铁律（EXECUTION_PLAN §11 WP5 / 清单 U4）：
- 禁止默认覆盖剪映草稿（write_draft 默认拒绝覆盖，需显式 force）。
- 真机打开验证属外部验收（本机只生成可被剪映照抄的规格/清单）。
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


def _ts_to_sec(ts: str) -> float:
    """SRT 时间戳 → 秒（fmt_ts 的逆运算）。"""
    h, m, rest = ts.split(":")
    s, ms = rest.split(",")
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0


def parse_srt(path: str) -> list[dict[str, float | str]]:
    """解析 SRT 为字幕条目列表 ``{start, end, text}``（确定性）。"""
    text = Path(path).read_text(encoding="utf-8")
    cues: list[dict[str, float | str]] = []
    for block in [b.strip() for b in text.split("\n\n") if b.strip()]:
        lines = block.split("\n")
        if len(lines) < 3:
            continue
        m = re.match(r"(\d+:\d+:\d+,\d+)\s*-->\s*(\d+:\d+:\d+,\d+)", lines[1].strip())
        if not m:
            continue
        start = _ts_to_sec(m.group(1))
        end = _ts_to_sec(m.group(2))
        cue_text = " ".join(lines[2:]).strip()
        cues.append({"start": start, "end": end, "text": cue_text})
    return cues


def build_draft_spec(
    *,
    video: str,
    srt: str | None = None,
    bgm: str | None = None,
    captions: list[dict[str, Any]] | None = None,
    onscreen: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """构建 5 轨剪映草稿规格（确定性）：

    1. 主视频轨（FULL，无字幕无 BGM）
    2. 原声轨
    3. 字幕/文本轨（来自 SRT 或 captions）
    4. 贴纸轨（来自 onscreen 屏上贴字）
    5. BGM 轨（可选）

    返回可被 JSON 序列化的 dict；pyJianYingDraft 真机写入时（外部）消费此规格。
    """
    tracks: list[dict[str, Any]] = []
    tracks.append({"type": "video", "name": "主视频轨", "clips": [{"src": video}]})
    tracks.append({"type": "audio", "name": "原声轨", "clips": [{"src": video}]})

    if srt and Path(srt).exists():
        tracks.append({"type": "text", "name": "字幕轨", "clips": parse_srt(srt)})
    elif captions:
        tracks.append({"type": "text", "name": "字幕轨", "clips": captions})

    if onscreen:
        tracks.append({"type": "sticker", "name": "贴纸轨", "clips": onscreen})

    if bgm:
        tracks.append({"type": "audio", "name": "BGM轨", "clips": [{"src": bgm}]})

    return {
        "version": 1,
        "draft_name": Path(video).stem,
        "tracks": tracks,
    }


def draft_json(spec: dict[str, Any]) -> str:
    """规格 → JSON 文本（UTF-8 保留中文）。"""
    return json.dumps(spec, ensure_ascii=False, indent=2)


def write_draft(
    spec: dict[str, Any],
    draft_dir: str,
    *,
    engine: str = "json",
    force: bool = False,
) -> str:
    """写剪映草稿。

    - engine="json"：离线写 ``draft_info.json`` 规格（默认，可被剪映流程照抄）。
      默认禁止覆盖已存在的规格；需 ``force=True``。
    - engine="pyjianying"：真机写草稿为外部验收项，本环境不执行，
      缺 pyJianYingDraft 或本机一律抛 RuntimeError 标明外部验收未完成。
    """
    if engine == "pyjianying":
        try:
            import pyJianYingDraft  # type: ignore[reportMissingImports]  # noqa: F401
        except ImportError:
            raise RuntimeError(
                "剪映草稿引擎不可用：需 Windows/WSL 机器 + 已安装 pyJianYingDraft。"
                "本机仅生成 JSON 规格（engine='json'）。"
            )
        # 真机写入依赖剪映版本/草稿目录，属外部验收项，本环境不执行
        raise RuntimeError("pyjianying 真机写草稿为外部验收项，请在指定机器运行")

    if engine != "json":
        raise ValueError(f"未知 engine: {engine}")

    d = Path(draft_dir)
    d.mkdir(parents=True, exist_ok=True)
    p = d / "draft_info.json"
    if p.exists() and not force:
        raise FileExistsError(
            f"剪映草稿已存在，禁止默认覆盖：{p}（用 force=True 覆盖）"
        )
    p.write_text(draft_json(spec), encoding="utf-8")
    return str(p)
