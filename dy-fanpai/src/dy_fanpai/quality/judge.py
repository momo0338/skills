"""quality/judge.py — 双视频评委（WP5，确定性结构版）。

原项目「双视频评委」依赖模型对原片与生成片做语义/质量比对；本环境实现确定性
【结构评委】：双方都能解码、分辨率一致、时长比在合理区间（0.5~2.0）。

模型级语义评委属外部验收项（需 Ark 等），此处只交付可离线复跑的结构校验，
保证「技术状态与人工状态分离」（EXECUTION_PLAN §11 WP5 验收）。
"""

from __future__ import annotations

from typing import Any

from ..media import ffmpeg as F
from .qc import probe


def judge_pair(
    original_path: str,
    generated_path: str,
    *,
    target_w: int,
    target_h: int,
) -> dict[str, Any]:
    """原片 vs 生成片 结构评委（确定性 IO）。

    通过条件：双方解码无坏流 + 分辨率命中目标 + 时长比 0.5~2.0。
    返回评分 dict；模型级语义评委不在此实现（外部验收）。
    """
    o = probe(original_path)
    g = probe(generated_path)
    dur_ratio = g["duration"] / o["duration"] if o["duration"] else 0.0
    res_match = (g["width"], g["height"]) == (target_w, target_h)
    both_decode = F.decode_ok(original_path) and F.decode_ok(generated_path)
    structural_pass = bool(both_decode and res_match and 0.5 <= dur_ratio <= 2.0)
    return {
        "original": original_path,
        "generated": generated_path,
        "original_duration": o["duration"],
        "generated_duration": g["duration"],
        "duration_ratio": dur_ratio,
        "resolution_match": res_match,
        "both_decode_ok": both_decode,
        "structural_pass": structural_pass,
    }


def judge_summary(pairs: list[dict[str, Any]]) -> dict[str, Any]:
    """聚合多对评委结果（纯函数）。"""
    passed = [p for p in pairs if p.get("structural_pass")]
    return {
        "total": len(pairs),
        "passed": len(passed),
        "failed": len(pairs) - len(passed),
        "all_passed": len(passed) == len(pairs) and len(pairs) > 0,
        "details": pairs,
    }
