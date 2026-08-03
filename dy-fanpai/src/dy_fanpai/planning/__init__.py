"""planning/ — P2 规划与审核阶段（WP2 实现）。

- planner     : 镜头归并 / 路由 / 即梦提示词 / 完备性关卡 → segments.json + segments.md
- localization: B 模式本地化(apply_edits 离线可测;rewrite 需 Ark key)
"""

from . import localization, planner
from .localization import apply_edits, apply_edits_dict, rewrite
from .planner import (
    build_hero_prompt,
    build_kou_prompt,
    build_package_prompt,
    completeness_check,
    group_shots,
    merged_form_map,
    pick_product_anchors,
    plan,
    seg_role,
    split_long_shots,
)

__all__ = [
    "planner",
    "localization",
    "plan",
    "split_long_shots",
    "group_shots",
    "seg_role",
    "merged_form_map",
    "pick_product_anchors",
    "build_kou_prompt",
    "build_hero_prompt",
    "build_package_prompt",
    "completeness_check",
    "apply_edits",
    "apply_edits_dict",
    "rewrite",
]
