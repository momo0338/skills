"""audio/service.py — P3 音频：原音切段 + 2 秒闸 + timing（WP3）。

忠实复刻原项目 cut_audio.py 的算法与铁律，仅做冻结期要求的改造：

业务铁律（07-22 实翻车固化，WP1 DESIGN §12 裁决，必须保留）：
- 即梦 mm 音频上传下限 **2 秒**——所有切片一律 apad 到 `max(2.0, span)`，
  **只垫到 2 秒上传下限，绝不垫到规划段时长**（垫满会触发 gen 的「配音超长」
  误加时，每段白烧 1 秒，用户抓的账）。
- 原音切段是确定性 IO；timing 轴是从 shotlist 的 dialogue 反推镜级字幕轴。

确定性函数（pad_for_upload / segment_cut_args / build_timing）与 ffmpeg IO
（cut_original_audio）解耦，便于离线单测；ffmpeg 调用仅在真实装配时发生。
"""

from __future__ import annotations

import json
import os
import subprocess
from typing import Any

# 即梦音频上传下限（秒）。WP1 冻结，禁止改成规划时长。
UPLOAD_FLOOR = 2.0

# 切音频统一参数（采样率 24k 单声道，与即梦口型对齐）
_CUT_SR = 24000


def pad_for_upload(span: float) -> float:
    """2 秒闸：上传音频最短 2s，仅垫到下限，不垫满规划时长。

    ``span = end - start``（实际镜跨度）。返回 ``max(UPLOAD_FLOOR, span)``。
    这是 P3 最关键的业务规则，必须有测试（WP2 parity 同源纪律）。
    """
    return max(UPLOAD_FLOOR, float(span))


def segment_cut_args(seg: dict, video: str, dst: str) -> list[str]:
    """构造「从原片切一段配音」的 ffmpeg 命令（确定性）。

    - ``-ss/-to`` 用段的 start/end（真实镜边界，非规划时长）；
    - ``-vn -ac 1 -ar 24000`` 抽单声道配音轨；
    - ``apad=whole_dur={pad}`` 只垫到 2s 下限。
    """
    span = float(seg["end"]) - float(seg["start"])
    pad = pad_for_upload(span)
    return [
        "ffmpeg", "-y", "-v", "error",
        "-ss", str(seg["start"]), "-to", str(seg["end"]),
        "-i", video, "-vn", "-ac", "1", "-ar", str(_CUT_SR),
        "-af", f"apad=whole_dur={pad}", dst,
    ]


def shot_in_segment(shot: dict, seg_start: float, seg_end: float, tol: float = 0.01) -> bool:
    """该镜的 dialogue 是否整体落在段边界内（含 0.01s 容差）。"""
    return shot["start"] >= seg_start - tol and shot["end"] <= seg_end + tol


def build_timing(segs: list[dict], shots: list[dict], tol: float = 0.01) -> dict:
    """从 segments + shotlist 反推镜级字幕轴 timing.json（确定性）。

    每段存一个列表，元素 ``{text, start, dur}``：
    - text = 镜 dialogue（正字，不含读音修正）；
    - start = 镜相对段起点的偏移（秒）；
    - dur = 镜跨度（秒）。
    只收真实人声 dialogue，静音/无台词镜跳过。
    """
    timing: dict[str, list[dict]] = {}
    for s in segs:
        items = []
        for sh in shots:
            dlg = (sh.get("dialogue") or "").strip()
            if not dlg:
                continue
            if shot_in_segment(sh, s["start"], s["end"], tol):
                items.append({
                    "text": dlg,
                    "start": round(float(sh["start"]) - float(s["start"]), 2),
                    "dur": round(float(sh["end"]) - float(sh["start"]), 2),
                })
        timing[s["seg"]] = items
    return timing


def _load_segs(plan: str) -> list[dict]:
    d: Any = json.load(open(plan, encoding="utf-8"))
    return d.get("segments", d) if isinstance(d, dict) else d


def _load_shots(shotlist: str) -> list[dict]:
    d: Any = json.load(open(shotlist, encoding="utf-8"))
    return d.get("shots", d)


def cut_original_audio(
    plan: str, video: str, shotlist: str | None, out_dir: str, cfg=None
) -> dict:
    """原音切段主入口（编排层，含 ffmpeg IO）。

    每段产出一个 ``{seg}.wav``（垫到 2s 下限），并写 ``timing.json``。
    返回 timing 字典。无 ffmpeg/源视频时不调用（调用方负责存在性）。
    """
    segs = _load_segs(plan)
    shots = _load_shots(shotlist) if shotlist else []
    os.makedirs(out_dir, exist_ok=True)

    for s in segs:
        dst = os.path.join(out_dir, f"{s['seg']}.wav")
        subprocess.run(segment_cut_args(s, video, dst), check=True)

    timing = build_timing(segs, shots)
    with open(os.path.join(out_dir, "timing.json"), "w", encoding="utf-8") as f:
        json.dump(timing, f, ensure_ascii=False, indent=1)
    n = sum(len(v) for v in timing.values())
    print(
        f"[cut_audio] {len(segs)}段切片(含>=2s闸) + timing.json {n}句 → {out_dir}",
        flush=True,
    )
    return timing
