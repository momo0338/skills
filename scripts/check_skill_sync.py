#!/usr/bin/env python3
"""Skill-sync drift checker.

验证技能列表的三处"事实来源"保持一致，防止新增/删除技能时文档与注册表漂移：

1. disk     — 仓库根目录下含 SKILL.md 的技能目录（discover_valid_skills）
2. README   — README.md 的「技能目录与概览」表格 + 开头技能数量声明
3. registry — scripts/auto_config_ai.py 中 SKILL_DEPS 的键

规则：
- 磁盘上每个技能目录必须在 README 表格和 SKILL_DEPS 中各出现一次
- README 表格每行必须对应一个真实存在的技能目录（链接路径 == 技能名）
- README 声明的技能数量必须与表格行数一致
- SKILL_DEPS 中不允许出现磁盘上不存在的技能

用法：
  python3 scripts/check_skill_sync.py        # 退出码 0=同步, 1=漂移
  也可作为模块被 test_deps.py 导入复用 run_checks()
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from auto_config_ai import SKILL_DEPS, discover_valid_skills

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
README_PATH = os.path.join(REPO_ROOT, "README.md")

# README 表格行形如: | **[name](./name)** | `name/` | ... |
README_ROW_RE = re.compile(r"\|\s*\*\*\[([^\]]+)\]\(\./([^)]+)\)\s*\*\*")
# README 开头数量声明形如: 包含 **16 个** 通用与专项 AI Agent 技能（个后可不带闭合 **）
README_COUNT_RE = re.compile(r"\*\*(\d+)\s*个")

# 非技能目录（即使含 SKILL.md 也不计入，discover_valid_skills 已排除，这里兜底）
IGNORED = {"scripts", "data", "node_modules"}


def readme_table():
    """解析 README 表格，返回 [(技能名, 链接路径), ...]；链接路径与技能名不符则记录。"""
    rows = []
    with open(README_PATH, encoding="utf-8") as f:
        for line in f:
            m = README_ROW_RE.search(line)
            if m:
                rows.append((m.group(1).strip(), m.group(2).strip()))
    return rows


def readme_count_claim():
    """解析 README 开头的技能数量声明，返回 int 或 None。"""
    with open(README_PATH, encoding="utf-8") as f:
        head = f.read(2000)
    m = README_COUNT_RE.search(head)
    return int(m.group(1)) if m else None


def run_checks(skills_root=REPO_ROOT):
    """执行全部一致性检查，返回 [(ok: bool, name: str, detail: str), ...]。"""
    checks = []

    disk_skills = {name for name, _ in discover_valid_skills(skills_root)}
    table_rows = readme_table()
    readme_skills = {name for name, _ in table_rows}
    registry_skills = set(SKILL_DEPS.keys())

    # 1. 磁盘技能必须在 README 与注册表中出现
    for name in sorted(disk_skills - readme_skills):
        checks.append((False, "disk→README", f"技能 '{name}' 在磁盘上但 README 表格缺失"))
    for name in sorted(disk_skills - registry_skills):
        checks.append((False, "disk→registry", f"技能 '{name}' 在磁盘上但 SKILL_DEPS 缺失"))

    # 2. README 行必须对应真实技能目录，且链接路径 == 技能名
    for name, path in table_rows:
        if name not in disk_skills:
            checks.append((False, "README→disk", f"README 行 '{name}' 无对应技能目录"))
        if path != name:
            checks.append((False, "README path", f"行 '{name}' 链接路径 '{path}' 与技能名不符"))

    # 3. 注册表条目必须对应真实技能目录
    for name in sorted(registry_skills - disk_skills):
        checks.append((False, "registry→disk", f"SKILL_DEPS 条目 '{name}' 无对应技能目录"))

    # 4. README 数量声明必须与表格行数一致
    claimed = readme_count_claim()
    if claimed is None:
        checks.append((False, "README count", "README 开头缺少技能数量声明（包含 **N 个**）"))
    elif claimed != len(table_rows):
        checks.append((False, "README count",
                       f"README 声明 {claimed} 个技能，实际表格 {len(table_rows)} 行"))

    if not checks:
        checks.append((True, "all", f"{len(disk_skills)} 个技能：磁盘/README/注册表三方一致"))
    return checks


def main():
    results = run_checks()
    failed = 0
    for ok, name, detail in results:
        if ok:
            print(f"  OK    {name}: {detail}")
        else:
            failed += 1
            print(f"  FAIL  {name}: {detail}")
    print(f"\nSkill sync: {'OK' if failed == 0 else f'{failed} drift(s) detected'}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
