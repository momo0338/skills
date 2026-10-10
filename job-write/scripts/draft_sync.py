#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""draft_sync.py — 微信草稿箱 → 内容流水线.db `drafts` 表同步

定位（2026-10-09 定案）
----------------------
草稿箱数据**不进 articles 表**，独立落 `drafts` 表。理由（实测）：
  1. `articles.source_id` 是 NOT NULL 外键 → 装草稿必须先造 sources 行，
     而草稿的 `content_source_url` 有 1/39 是空的（软文），根本造不出；
  2. `articles` 的 `published_*` 系 6 列（msgid/appmsgid/itemidx/publish_type/
     published_url/published_at）在草稿阶段**结构性为空**，硬塞进去会在 89 条
     published 旁边多出一批半空行，污染"已发布台账"语义；
  3. `UNIQUE(source_id, variant)` 是"同一素材的版本"，草稿是"同一媒体的推送批次"，
     语义不同，易撞唯一约束。
`drafts` 表按草稿语义建模，字段与 `draft/batchget` 返回 1:1 对齐，迁移零损耗。

单位解析
--------
草稿标题 ≠ 单位名（微信为打开率彻底改写标题）。规则优先级：
  1. 显式映射 TITLE_UNIT_MAP（人工确认）；
  2. 人工确认的归一化/歧义映射 AMBIGUOUS；
  3. 最长优先「单位名 ⊂ 标题」匹配（含去括号归一化，解决
     「中国通信建设第三工程局有限公司（中通建三局）」↔ 标题用简称）；
  4. 解析不到 → unit_id 留空 + 写 unit_resolve_note，⛔ 绝不猜、绝不新建单位
     （units 是主数据，改动需人工确认）。

用法
----
    python3 draft_sync.py --json draft_merged.json            # dry-run
    python3 draft_sync.py --json draft_merged.json --apply    # 真写
"""
import argparse
import json
import re
import sqlite3
import sys
from datetime import datetime

DEFAULT_DB = '/Users/zhugx/codeup/obsidian/03-工作记录/码上职业/工具/内容流水线.db'
NOW = lambda: datetime.now().strftime('%Y-%m-%dT%H:%M:%S')

# ── 人工确认的单位映射（草稿标题片段 → units.name 精确值）──────────────
TITLE_UNIT_MAP = {
    '中国人民大学苏州校区': None,          # 人大苏州研究院是办学主体，units 无此行
    '苏州市吴江区教育系统': '苏州市吴江区人民政府',  # 稿内为区教育局统招
    '盐城大丰区教育系统': '盐城市大丰区人民政府',   # 标题缺「市」字，最长匹配会误中「盐城」（2026-10-09 实测）
}
# 归一化后仍需人工确认的（简称歧义 / 全称带括号后缀）
AMBIGUOUS = {
    '中通建三局': '中国通信建设第三工程局有限公司（中通建三局）',
    '东方电气': '中国东方电气',
    '中国融通': '中国融通资产管理',
    '国药集团': '国药控股江苏',
    '小米集团': '小米集团（小米华东总部）',
    '烽火通信': '烽火通信/中国信科（南京）',
    '华为南研所': '华为技术有限公司（南京研究所）',
    '江苏省沿海开发集团': '省沿海开发集团',
    '莱斯信息': '南京莱斯信息技术股份有限公司',
    '中国邮政江苏': '中国邮政江苏省分公司',
    '中国电信江苏': '中国电信江苏',
    '中国移动江苏': '中国移动江苏公司',
    '中国联通江苏': '中国联通江苏省分公司',
    '阿里': None,            # units 只有「阿里」，与阿里巴巴集团不等价 → 留空待人工
}


def norm(s):
    """归一化：去括号内容（含全角）、去空白。"""
    s = re.sub(r'[（(][^）)]*[）)]', '', s or '')
    return re.sub(r'\s+', '', s)


def connect(db):
    con = sqlite3.connect(db)
    con.row_factory = sqlite3.Row
    con.execute('PRAGMA foreign_keys=ON')
    return con


def load_drafts(path):
    with open(path, encoding='utf-8') as f:
        d = json.load(f)
    items = d['item'] if isinstance(d, dict) else d
    out = []
    for it in items:
        ni = it['content']['news_item'][0]
        out.append({
            'media_id': it['media_id'],
            'title': ni.get('title', ''),
            'author': ni.get('author', ''),
            'digest': ni.get('digest', ''),
            'source_url': (ni.get('content_source_url') or '').strip() or None,
            'thumb_media_id': ni.get('thumb_media_id', ''),
            'thumb_url': ni.get('thumb_url', ''),
            'temp_url': ni.get('url', ''),
            'need_open_comment': ni.get('need_open_comment'),
            'only_fans_can_comment': ni.get('only_fans_can_comment'),
            'article_type': ni.get('article_type', ''),
            'create_time': it['content'].get('create_time') or it.get('update_time'),
            'update_time': it.get('update_time'),
        })
    return out, (d.get('total_count') if isinstance(d, dict) else len(out))


def iso(ts):
    return datetime.fromtimestamp(ts).strftime('%Y-%m-%dT%H:%M:%S') if ts else None


def guess_line(title, url):
    if any(k in title for k in ['学院', '大学', '学校', '教育系统', '教师', '高校']):
        return '教育'
    if '医院' in title or '卫健' in (url or ''):
        return '医疗'
    if '校招' in title or '秋招' in title or '2027' in title:
        return '校招'
    return '其他'


def resolve_unit(con, title):
    """→ (unit_id|None, unit_name|None, note)"""
    for kw, target in TITLE_UNIT_MAP.items():
        if kw in title:
            if target is None:
                return None, None, f'人工确认：units 无「{kw}」，留空待补主数据'
            r = con.execute('SELECT id,name FROM units WHERE name=?', (target,)).fetchone()
            return (r['id'], r['name'], f'显式映射 {kw}→{target}') if r else \
                   (None, None, f'映射目标 {target} 不在 units')
    for kw, target in AMBIGUOUS.items():
        if kw in title:
            if target is None:
                return None, None, f'人工标记歧义：{kw}，留空待核对'
            r = con.execute('SELECT id,name FROM units WHERE name=?', (target,)).fetchone()
            return (r['id'], r['name'], f'歧义映射 {kw}→{target}') if r else \
                   (None, None, f'映射目标 {target} 不在 units')
    # ⚠️ 不过滤 units.status：北京信托 status='written'（已写过）也是合法归属单位，
    # status 语义是"写过没"而非"是否有效"。单位状态不该影响草稿归属判定。
    rows = con.execute("SELECT id,name,category,status FROM units").fetchall()
    t_n = norm(title)
    cands = [r for r in rows if r['name'] and
             (r['name'] in title or (len(norm(r['name'])) >= 4 and norm(r['name']) in t_n))]
    if not cands:
        return None, None, '标题未匹配到任何 units.name'
    # 优先 active，其次名称最长
    best = max(cands, key=lambda r: (r['status'] == 'active', len(r['name'])))
    return best['id'], best['name'], f'名称匹配→{best["name"]}（{best["category"]}）'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--json', required=True)
    ap.add_argument('--db', default=DEFAULT_DB)
    ap.add_argument('--apply', action='store_true')
    a = ap.parse_args()

    drafts, total = load_drafts(a.json)
    con = connect(a.db)
    print(f'草稿 {len(drafts)} 条（平台 total_count={total}）')
    print(f'目标表 drafts｜模式：{"APPLY 真写" if a.apply else "DRY-RUN"}\n' + '=' * 76)

    rows, unresolved = [], []
    for d in drafts:
        uid, uname, note = resolve_unit(con, d['title'])
        if uid is None:
            unresolved.append((d['title'], note))
        rows.append((d, uid, uname, note))
        print(f'  {"✅" if uid else "⚠️ "} {d["title"][:28]:30} unit={(uname or "—"):22} {note[:32]}')

    n_unit = sum(1 for _, u, _, _ in rows if u)
    print('=' * 76)
    print(f'单位可解析 {n_unit}/{len(rows)}｜待人工 {len(unresolved)}')
    for t, why in unresolved:
        print(f'  · {t[:34]} —— {why}')

    if not a.apply:
        print('\n[dry-run] 未写库。加 --apply 执行。')
        con.close()
        return

    print('\n' + '=' * 76 + '\n[APPLY] 写入 drafts 表\n')
    ins = upd = 0
    con.execute('BEGIN')
    try:
        for d, uid, uname, note in rows:
            # 2026-10-10 二次收缩：drafts=最小镜像（media_id/title/source_url/temp_url/status），
            # 解析结果(unit/note/line)只进 audit_log 快照，不再落列。
            r = con.execute('SELECT id FROM drafts WHERE media_id=?', (d['media_id'],)).fetchone()
            _audit = lambda act: con.execute(
                "INSERT INTO audit_log (table_name, row_key, action, snapshot, at, actor) "
                "VALUES ('drafts', ?, ?, ?, ?, 'draft_sync')",
                (d['media_id'], act,
                 json.dumps({'title': d['title'][:60], 'unit': uname, 'note': note, 'line': guess_line(d['title'], d['source_url'])},
                            ensure_ascii=False), NOW()))
            if r:
                con.execute(
                    'UPDATE drafts SET title=?,source_url=?,temp_url=? WHERE id=?',
                    (d['title'], d['source_url'], d['temp_url'], r['id']))
                _audit('sync_update')
                upd += 1
            else:
                con.execute(
                    'INSERT INTO drafts (media_id,title,source_url,temp_url,status) '
                    'VALUES (?,?,?,?,\'draft\')',
                    (d['media_id'], d['title'], d['source_url'], d['temp_url']))
                _audit('sync_insert')
                ins += 1
        con.commit()
        print(f'[APPLY] 提交完成：新增 {ins} ／ 更新 {upd}')
    except Exception as e:
        con.rollback()
        print(f'❌ 已回滚：{e}')
        sys.exit(1)
    con.close()


if __name__ == '__main__':
    main()
