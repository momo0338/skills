#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""draft_reconcile.py — 微信草稿箱 ⇋ 内容流水线.db drafts 表 定时全量对账（2026-10-09 方案B）

定位
----
方案 B（对账兜底）：定时把草稿箱全量拉下来，经 draft_sync.py upsert 进 drafts 表，
兜住 hook②（draft_ctl，方案A）覆盖不到的漏网——手动后台推送、老稿原位更新、
改标题重推等。与方案 A 的关系：hook② 保证「秒级回写」，本脚本保证「日级对账」。

流程
----
1. wx_draft.py list 分页拉全量（count=20，no_content=1 不带正文）
2. 合并多页为 draft_sync 兼容的 {"total_count": T, "item": [...]}
3. 差集预检：在箱 vs 库内 media_id 集合
4. 调 draft_sync.py --apply upsert（单位解析/审计全部复用其逻辑）
5. 消失报告：在库不在箱的行**只报告不改状态**（群发/删除均会使草稿从箱消失，
   自动判定易误判；处置归看板人工 mark 或方案 C）

用法
----
    python3 draft_reconcile.py --profile mashang             # dry-run
    python3 draft_reconcile.py --profile mashang --apply     # 真写（automation 用）
"""
import argparse
import glob
import json
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from draft_sync import DEFAULT_DB, NOW  # noqa: E402

VENV_PY = '/Users/zhugx/.workbuddy/binaries/python/envs/default/bin/python3'
WX_DRAFT = os.path.expanduser('~/src/skills/mp-publish/scripts/wx_draft.py')
DRAFT_SYNC = os.path.expanduser('~/src/skills/job-write/scripts/draft_sync.py')
PUBLISH_RECORDS_GLOB = os.path.expanduser('~/.cache/weixin/publish_records/*发表记录*.json')
PAGE_SIZE = 20  # draft/batchget count 上限（实测）


def _lcs(a, b):
    """最长公共子串长度（消失稿↔发布标题指纹）。"""
    if not a or not b:
        return 0
    last = [0] * (len(b) + 1)
    best = 0
    for ca in a:
        cur = [0] * (len(b) + 1)
        for j, cb in enumerate(b, 1):
            if ca == cb:
                cur[j] = last[j - 1] + 1
                best = max(best, cur[j])
        last = cur
    return best


def fetch_all(profile):
    """分页拉全量草稿 → (merged dict, per_page raw)。"""
    merged = {'total_count': None, 'item': []}
    offset, pages = 0, 0
    tmpdir = tempfile.mkdtemp(prefix='draft_reconcile_')
    while True:
        out = os.path.join(tmpdir, f'page_{offset}.json')
        r = subprocess.run(
            [VENV_PY, WX_DRAFT, '--profile', profile, 'list',
             '--offset', str(offset), '--count', str(PAGE_SIZE), '--json', out],
            capture_output=True, text=True, timeout=60)
        if r.returncode != 0:
            raise RuntimeError(f'wx_draft list offset={offset} 失败: '
                               f'{(r.stderr or r.stdout).strip()[:200]}')
        data = json.load(open(out, encoding='utf-8'))
        total = data.get('total_count')
        if merged['total_count'] is None:
            merged['total_count'] = total
        items = data.get('item') or []
        merged['item'].extend(items)
        pages += 1
        offset += len(items)
        if not items or offset >= (total or 0):
            break
        if pages > 30:  # 保险丝：600 篇封顶，防 total 异常死循环
            raise RuntimeError('分页超过 30 页，total_count 异常，中止')
    return merged, tmpdir


def db_media_ids(db):
    con = sqlite3.connect(f'file:{db}?mode=ro', uri=True)
    rows = con.execute('SELECT media_id, title, status FROM drafts').fetchall()
    con.close()
    return {r[0]: (r[1], r[2]) for r in rows}


def load_published_titles():
    """最新发表记录 json → 发布标题列表；无文件返回 None。"""
    files = glob.glob(PUBLISH_RECORDS_GLOB)
    if not files:
        return None
    f = max(files, key=os.path.getmtime)
    d = json.load(open(f, encoding='utf-8'))
    titles = []
    for item in d.get('publish_list', []):
        try:
            info = json.loads(item['publish_info'])
        except Exception:
            continue
        for am in info.get('appmsg_info', []):
            t = (am.get('title') or '').strip()
            if t:
                titles.append(t)
    return titles


def match_published(draft_title, db_ids, mid, published_titles):
    """消失稿是否命中发表记录：单位核心名进发布标题 ＋ LCS≥8。

    ⛔ unit_name_resolved 为空的行指纹不足，一律不判（保留）——防误删。
    返回命中的发布标题（用于审计），未命中返回 None。
    """
    unit = db_unit_of(DEFAULT_DB, mid) if db_ids else None
    unit = unit or ''
    core = re.sub(r'国网|有限责任公司|有限公司|股份|责任公司|公司|人民政府', '', unit)
    if len(core) < 4:
        return None
    for ptitle in published_titles:
        if core[:6] in ptitle and _lcs(draft_title, ptitle) >= 8:
            return ptitle
    return None


def main():
    ap = argparse.ArgumentParser(description='草稿箱⇋drafts表 定时全量对账（方案B）')
    ap.add_argument('--profile', default='mashang', help='公众号 profile（默认 mashang）')
    ap.add_argument('--db', default=DEFAULT_DB)
    ap.add_argument('--apply', action='store_true', help='真写（调 draft_sync --apply）；缺省 dry-run')
    a = ap.parse_args()

    print(f'== 草稿箱全量对账（profile={a.profile}，{"APPLY" if a.apply else "DRY-RUN"}）==')
    merged, tmpdir = fetch_all(a.profile)
    total, items = merged['total_count'], merged['item']
    print(f'平台在箱 {total} 篇，实拉 {len(items)} 条（{len({i["media_id"] for i in items})} 个唯一 media_id）')

    # 合并落盘（draft_sync 输入格式）
    merged_path = os.path.join(tmpdir, 'draft_merged.json')
    json.dump(merged, open(merged_path, 'w', encoding='utf-8'), ensure_ascii=False)

    # 差集预检
    in_box = {i['media_id'] for i in items}
    db_ids = db_media_ids(a.db)
    to_add = in_box - set(db_ids)
    missing = set(db_ids) - in_box
    print(f'差集：在箱不在库 {len(to_add)} 条（将 INSERT）｜在库不在箱 {len(missing)} 条（见下方消失报告）')

    # 调 draft_sync（单一真源：upsert+单位解析+audit 全在它那边）
    cmd = [VENV_PY, DRAFT_SYNC, '--json', merged_path, '--db', a.db]
    if a.apply:
        cmd.append('--apply')
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    out = (r.stdout or '') + (r.stderr or '')
    # 只透出关键行，避免刷屏
    for line in out.splitlines():
        if any(k in line for k in ['草稿 ', '单位可解析', 'APPLY', '提交完成', '回滚', '❌', 'dry-run']):
            print('  ' + line)
    if r.returncode != 0:
        print(f'❌ draft_sync 退出码 {r.returncode}，对账中止')
        sys.exit(1)

    # 消失处置（朱总 2026-10-09 裁定：确认已发布的直接删）
    if missing:
        print(f'\n[消失处置] 在库不在箱 {len(missing)} 条：')
        published_titles = load_published_titles()
        if published_titles is None:
            print('  ⛔ 无发表记录 json，无法判定已发布 —— 全部保留，请先跑 mp-ops refresh_publish_records.py')
            published_titles = []
        else:
            age_h = (time.time() - os.path.getmtime(max(glob.glob(PUBLISH_RECORDS_GLOB), key=os.path.getmtime))) / 3600
            print(f'  发表记录基线：{os.path.basename(max(glob.glob(PUBLISH_RECORDS_GLOB), key=os.path.getmtime))}'
                  f'（滞后 {age_h:.1f} 小时）{"⚠️ 滞后>24h，今日消失稿可能判定不到，建议先刷新" if age_h > 24 else ""}')
        purged, kept = 0, 0
        for mid in sorted(missing):
            t, st = db_ids[mid]
            hit_title = match_published(t, db_ids, mid, published_titles)
            if hit_title and a.apply:
                con = sqlite3.connect(a.db)
                con.execute('PRAGMA busy_timeout=5000')
                con.execute('BEGIN')
                con.execute("INSERT INTO audit_log (table_name, row_key, action, snapshot, at, actor) "
                            "VALUES ('drafts', ?, 'purge_published', ?, ?, 'draft_reconcile')",
                            (mid, json.dumps({'title': t[:60], 'matched_published_title': hit_title[:60]},
                                             ensure_ascii=False), NOW()))
                con.execute('DELETE FROM drafts WHERE media_id=?', (mid,))
                con.commit()
                con.close()
                purged += 1
                print(f'  🗑️ 已发布确认→删除  {t[:34]}（发布标题: {hit_title[:30]}）')
            elif hit_title:
                purged += 1
                print(f'  🗑️ [dry-run]将删（已发布确认）  {t[:34]}（发布标题: {hit_title[:30]}）')
            else:
                kept += 1
                print(f'  · 保留（未见发布记录：定时发布中待到点 / 手动删除）  status={st}  {t[:36]}')
        if purged or kept:
            print(f'  小计：删除 {purged} ／ 保留 {kept}')

    # 对账动作留痕（一批一条）
    if a.apply:
        con = sqlite3.connect(a.db)
        con.execute('PRAGMA busy_timeout=5000')
        con.execute(
            "INSERT INTO audit_log (table_name, row_key, action, snapshot, at, actor) "
            "VALUES ('drafts', ?, 'reconcile', ?, ?, 'draft_reconcile')",
            (f'batch:{datetime.now().strftime("%Y-%m-%d")}',
             json.dumps({'total_in_box': total, 'fetched': len(items),
                         'to_add': len(to_add), 'missing': len(missing)},
                        ensure_ascii=False), NOW()))
        con.commit()
        con.close()
        print(f'\n[ok] 对账完成（audit_log 已记 reconcile 批次）')
    else:
        print('\n[dry-run] 未写库。加 --apply 执行。')


if __name__ == '__main__':
    main()
