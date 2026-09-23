#!/usr/bin/env python3
"""
sync_articles_to_db.py
文章与数据库状态自动对账与回填工具

作用：
扫描 2027年校园招聘/ 与 事业单位招考/ 下的待发布/已发布 HTML 稿件，
自动对账 jobs.db 中的 campaigns 记录：
若本地已有成稿（size > 5KB）但数据库中 campaigns.has_article = 0，
则自动双写回填 campaign_articles 表并置位 campaigns.has_article = 1。
最后调用 cycle_status.py 刷新巡检源调度状态，彻底消除数据漂移。

用法：
    python3 sync_articles_to_db.py --dry-run     # 只对账不写库（首次务必先跑这个）
    python3 sync_articles_to_db.py               # 实际回填
    python3 sync_articles_to_db.py --db <路径> --project-dir <路径>

安全约定（重要）：
    匹配用的是「标题双向包含」的模糊判断，因此存在两类歧义，脚本**默认遇到就
    跳过并报告**，绝不静默写入：
      A. 一稿命中多批次  → 同一份 HTML 被写进多个 campaign
      B. 多稿命中同批次  → 例如同一稿件在「待发布/」和「已发布/」各有一份副本，
                           会把两份先后写进同一 campaign_id（后者覆盖前者）
    B 类尤其危险：到底该用待发布的新版还是已发布的旧版，属业务判断，
    脚本不做猜测。人工逐条确认后，确需放行再加 --allow-multi-match 重跑。

流程：先全量扫描归集 → 双向冲突检测 → 报告 → 仅对无冲突项执行写入。
"""

import os
import glob
import re
import sqlite3
import subprocess

DB_PATH = '/Users/zhugx/src/ijob/data/jobs.db'
PROJECT_DIR = '/Users/zhugx/codeup/obsidian/03-工作记录/码上职业'
CYCLE_SCRIPT = '/Users/zhugx/src/ijob/patrol/cycle_status.py'
MIN_SIZE = 5000          # 小于此字节数视为占位/空稿


def run_sync(dry_run=False, db_path=DB_PATH, project_dir=PROJECT_DIR,
             allow_multi_match=False, run_cycle=True, min_size=MIN_SIZE):
    if not os.path.exists(db_path):
        print(f"❌ 找不到数据库: {db_path}")
        return

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # ── 收集全部排版 HTML ──
    search_patterns = [
        os.path.join(project_dir, '2027年校园招聘/**/*.html'),
        os.path.join(project_dir, '事业单位招考/**/*.html'),
    ]
    html_files = []
    for pat in search_patterns:
        html_files.extend(glob.glob(pat, recursive=True))

    print(f"🔍 共扫描到 {len(html_files)} 个本地排版 HTML 文件"
          + ("（dry-run：只对账，不写库）" if dry_run else ""))

    c.execute("SELECT id, title, has_article FROM campaigns")
    all_camps = c.fetchall()

    # ── 阶段 1：扫描 + 匹配，先归集、不写入 ──
    plan = {}            # campaign_id -> [(html_path, camp, size)]
    file_to_camps = {}   # html_path -> [camp]
    unparsed = 0

    for h in html_files:
        basename = os.path.basename(h)
        size = os.path.getsize(h)
        if size < min_size:
            continue

        # 提取单位关键词
        # 模式1: <专场号2位>-单位名-排版.html            如 01-江苏省铁路集团-排版.html
        # 模式2: <专场号2位>-<序号2位>-单位名-排版.html   如 02-01-华电江苏-排版.html
        # 模式3: YYYY-MM-DD-单位名-排版.html             日期前缀
        # ⚠️ 原正则把专场号写死成 `03-`，导致 01/02/04… 等专场整批被跳过
        #    （实测 96 个 HTML 里 46 个因此未参与对账，2026-09-23 修）
        m = re.search(r'^(?:\d{4}-\d{2}-\d{2}|\d{2}(?:-\d{2})?)-(.*?)(?:-\d+人)?-排版\.html$',
                      basename)
        if not m:
            unparsed += 1
            continue
        cname = m.group(1).strip()
        cname_clean = re.sub(r'202\d校招|202\d招聘', '', cname).strip()
        if not cname_clean:
            unparsed += 1
            continue

        matched = [camp for camp in all_camps
                   if camp['has_article'] == 0
                   and (cname_clean in camp['title'] or camp['title'] in cname_clean)]
        if not matched:
            continue

        file_to_camps[h] = matched
        for camp in matched:
            plan.setdefault(camp['id'], []).append((h, camp, size))

    # ── 阶段 2：双向冲突检测 ──
    multi_file = {h: cs for h, cs in file_to_camps.items() if len(cs) > 1}   # A: 一稿→多批次
    multi_batch = {cid: v for cid, v in plan.items() if len(v) > 1}          # B: 多稿→同批次

    conflicted_files, conflicted_cids = set(), set()
    if not allow_multi_match:
        for h, cs in multi_file.items():
            conflicted_files.add(h)
            conflicted_cids.update(x['id'] for x in cs)
        for cid, items in multi_batch.items():
            conflicted_cids.add(cid)
            conflicted_files.update(h for h, _, _ in items)

    # ── 阶段 3：冲突项报告（不写入）──
    if multi_file and not allow_multi_match:
        print(f"\n⏭️  A 类冲突：{len(multi_file)} 个稿件命中【多个批次】，已跳过：")
        for h, cs in list(multi_file.items())[:10]:
            print(f"   {os.path.basename(h)}")
            print(f"      → 命中批次 {[(x['id'], x['title'][:24]) for x in cs]}")
        if len(multi_file) > 10:
            print(f"   ... 另有 {len(multi_file) - 10} 个")

    if multi_batch and not allow_multi_match:
        print(f"\n⏭️  B 类冲突：{len(multi_batch)} 个批次被【多份稿件】命中，已跳过：")
        for cid, items in list(multi_batch.items())[:10]:
            print(f"   批次 [ID={cid}] {items[0][1]['title'][:36]}")
            for h, _, size in items:
                print(f"      ← {os.path.relpath(h, project_dir)}  ({size} B)")
        print("   到底该用哪一份（如「待发布」的新版 vs 「已发布」的旧版）属业务判断，")
        print("   请人工确认后手工处理，或确认可覆盖时加 --allow-multi-match 重跑。")

    if conflicted_cids:
        print(f"\n⚠️  本次因冲突共跳过 {len(conflicted_cids)} 个批次、{len(conflicted_files)} 个稿件。")

    # ── 阶段 4：执行（仅无冲突项）──
    plan_count = fixed_count = 0
    for cid, items in plan.items():
        if cid in conflicted_cids:
            continue
        for h, camp, size in items:
            if h in conflicted_files:
                continue
            print(f"⚠️ 发现未同步批次 [ID={camp['id']}]: {camp['title'][:40]}")
            print(f"   匹配到本地成稿: {os.path.basename(h)} ({size} 字节)")
            plan_count += 1
            if not dry_run:
                with open(h, 'r', encoding='utf-8') as f:
                    html_content = f.read()
                c.execute('''
                    INSERT INTO campaign_articles (campaign_id, rendered_html, official_html, updated_at)
                    VALUES (?, ?, '', datetime('now', 'localtime'))
                    ON CONFLICT(campaign_id) DO UPDATE SET
                        rendered_html = excluded.rendered_html,
                        updated_at = excluded.updated_at
                ''', (camp['id'], html_content))
                c.execute('UPDATE campaigns SET has_article = 1 WHERE id = ?', (camp['id'],))
                fixed_count += 1

    if unparsed:
        print(f"ℹ️  {unparsed} 个 HTML 文件名不符合命名规范，已跳过。")

    if dry_run:
        print(f"\n🧪 dry-run 结束：预计可回填 {plan_count} 个批次（未写库）。")
    elif fixed_count > 0:
        conn.commit()
        c.execute('PRAGMA integrity_check')
        print(f"✅ 成功双写回填 {fixed_count} 个批次！integrity_check = {c.fetchone()[0]}")
        # 刷新巡检源调度
        if run_cycle and os.path.exists(CYCLE_SCRIPT):
            subprocess.run(['python3', CYCLE_SCRIPT], capture_output=True)
            print("🔄 已同步刷新 patrol_sources.cycle_status 调度状态")
    else:
        print("🎉 全部本地成稿与数据库状态 100% 对齐，零漂移！")

    conn.close()


if __name__ == '__main__':
    import argparse

    ap = argparse.ArgumentParser(description='文章与数据库状态自动对账与回填')
    ap.add_argument('--dry-run', action='store_true',
                    help='只对账、不写库（首次务必先跑这个）')
    ap.add_argument('--db', default=DB_PATH, help=f'jobs.db 路径（默认 {DB_PATH}）')
    ap.add_argument('--project-dir', default=PROJECT_DIR,
                    help=f'稿件根目录（默认 {PROJECT_DIR}）')
    ap.add_argument('--allow-multi-match', action='store_true',
                    help='放行多对多匹配（默认遇到 A/B 类冲突就跳过，防污染）')
    ap.add_argument('--no-cycle', action='store_true',
                    help='回填后不刷新巡检源调度状态')
    a = ap.parse_args()

    run_sync(dry_run=a.dry_run, db_path=a.db, project_dir=a.project_dir,
             allow_multi_match=a.allow_multi_match, run_cycle=not a.no_cycle)
