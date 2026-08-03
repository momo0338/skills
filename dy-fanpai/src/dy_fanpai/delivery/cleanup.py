"""delivery/cleanup.py — 工作区临时文件清理（dry-run 优先，WP5）。

WP5 负责「清理 dry-run」。设计原则（EXECUTION_PLAN 清单 U4 / §11）：
- 默认 dry-run：只报告候选，不删除。
- 受保护集合永不被清理：源视频(inputs)、最终成品(FULL/FINAL)、任务 ID
  (generation/tasks)、费用与验收记录(run.json 及根目录 *.json/*.md)。
- 仅清理明确临时的文件（*.tmp / *.partial / assemble_* / __pycache__），
  即使误匹配保护项也会被保护网拦下。

真删除需显式 dry_run=False（CLI 用 --yes 触发）。
"""

from __future__ import annotations

import shutil
from pathlib import Path

# 受保护前缀（相对工作区根）：源视频 / 任务 ID / QC 记录
PROTECTED_PREFIXES: tuple[str, ...] = ("inputs/", "generation/tasks/", "qc/")
# 受保护文件名：最终成品 / 主清单
PROTECTED_NAMES: tuple[str, ...] = ("run.json", "FULL.mp4", "FINAL.mp4")
# 根目录记录文件后缀：费用/验收记录
PROTECTED_ROOT_SUFFIXES: tuple[str, ...] = (".json", ".md")

# 临时文件判定（清理的唯一主门）
TEMP_SUFFIXES: tuple[str, ...] = (".tmp", ".partial")
TEMP_DIR_NAMES: tuple[str, ...] = ("__pycache__",)
TEMP_NAME_PREFIXES: tuple[str, ...] = ("assemble_",)


def _is_protected(rel: Path, extra: tuple[str, ...]) -> bool:
    s = str(rel)
    for p in PROTECTED_PREFIXES + extra:
        if s.startswith(p):
            return True
    if rel.name in PROTECTED_NAMES:
        return True
    # 根目录的 *.json/*.md 视为记录文件受保护；子目录的草稿规格等不在列
    if len(rel.parts) == 1 and rel.suffix in PROTECTED_ROOT_SUFFIXES:
        return True
    return False


def _is_temp(p: Path) -> bool:
    if p.is_dir():
        return p.name in TEMP_DIR_NAMES or p.name.startswith(TEMP_NAME_PREFIXES)
    if p.suffix in TEMP_SUFFIXES:
        return True
    if p.name.startswith(TEMP_NAME_PREFIXES):
        return True
    return False


def plan_cleanup(
    run_dir: str,
    *,
    dry_run: bool = True,
    protected: list[str] | None = None,
) -> list[str]:
    """扫描工作区临时文件。

    dry_run=True（默认）：只返回候选路径，不删除。
    dry_run=False：删除候选（受保护项已排除）。
    返回候选路径列表（相对/绝对取决于传入 run_dir）。
    """
    root = Path(run_dir)
    extra = tuple(protected or ())
    candidates: list[str] = []
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root)
        if _is_protected(rel, extra):
            continue
        if _is_temp(p):
            candidates.append(str(p))
    if not dry_run:
        for c in candidates:
            pp = Path(c)
            if pp.is_dir():
                shutil.rmtree(pp)
            else:
                pp.unlink()
    return candidates
