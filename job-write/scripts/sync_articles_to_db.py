#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""sync_articles_to_db.py —— 已迁出本技能（2026-09-25）

⛔ 本文件是**迁移留痕薄壳**，不再是可执行的对账实现，也不再持有任何数据库写能力。
原实现直接 `sqlite3.connect(jobs.db)` 并 `commit()`，绕过了 ijob 的
备份 / SHA-256 校验 / 单事务 / 写后终验门禁，与「ijob 是独立项目」的解耦目标冲突。

新位置（唯一实现）：
    /Users/zhugx/src/ijob/scripts/reconcile_articles.py

新用法：
    python3 /Users/zhugx/src/ijob/scripts/reconcile_articles.py           # dry-run（默认只读）
    python3 /Users/zhugx/src/ijob/scripts/reconcile_articles.py --apply   # 写库

新旧差异（迁移时同时修掉的两个真缺陷，别回退）：
  1. **占位行闸门**（新增）：原实现会把 `batch_type` 为 `台账#%` / `入口×%` 的
     旧台账占位行当真实批次回填。实测「中国电建三公司…江苏台账#15」这类占位行
     会被误判为可写目标。库内共 107 条此类未成稿占位行，是潜在污染池。
  2. **`--dry-run` 默认反转**（新增）：原实现默认**直接写库**，只有显式传
     `--dry-run` 才不写。新实现默认 dry-run，必须显式 `--apply` 才写。

本技能侧的正确读路径：只用 `ijob` 技能的只读契约（`ijob brief` / `ijob status`），
内容状态一律看 `content_state` 业务语义，不要在本技能内自行推库或写库。
"""

from __future__ import annotations

import sys

RELOCATION = "/Users/zhugx/src/ijob/scripts/reconcile_articles.py"

MESSAGE = f"""⛔ sync_articles_to_db.py 已于 2026-09-25 从 job-write 迁出，本文件不再是实现。

原因：原实现直连 ijob 的 SQLite 并 commit()，绕过 ijob 的备份 / SHA-256 /
单事务 / 写后终验门禁；且默认即写库。对账属于 ijob 内部写操作，不应由内容侧技能持有。

新位置（唯一实现）：
    {RELOCATION}

新用法：
    python3 {RELOCATION}            # dry-run（默认只读，用 mode=ro + query_only）
    python3 {RELOCATION} --apply    # 写库（强制备份 + SHA-256 校验 + 单事务 + 写后终验）

本技能侧读路径：只用 `ijob` 技能只读契约（ijob brief / ijob status），
稿件状态看 content_state（unwritten / written / published），不要在本技能内推库或写库。
"""


def main() -> int:
    print(MESSAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
