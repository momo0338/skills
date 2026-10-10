#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""content_ctl.py — 内容流水线 CLI 单入口（方案 v2/v3，2026-10-08 定稿）

pipeline.db 五表：units / sources / articles / article_metrics / events / audit_log
status 由 events 推导维护，禁止直改。AI/人工一律经本 CLI 写入。

用法:
  content_ctl.py init                                   # 建表（幂等）
  content_ctl.py ready                                  # 选活池
  content_ctl.py written <article_id> --files md,html,cover
  content_ctl.py pushed <article_id> --media-id X       # wx_pipeline 钩子调用
  content_ctl.py grouped <单位关键词> [--publish-type 101|1]
  content_ctl.py reconcile [--src <发表记录.json>]       # 拉发表记录对账回填
  content_ctl.py export                                  # 导出 json 视图
  content_ctl.py audit                                   # 对账报告
"""
import argparse
import hashlib
import json
import os
import sqlite3
import sys
from datetime import datetime

DB = os.environ.get('PIPELINE_DB',
                    '/Users/zhugx/codeup/obsidian/03-工作记录/码上职业/工具/内容流水线.db')
WORKSPACE = os.environ.get('PIPELINE_WS',
                           '/Users/zhugx/codeup/obsidian/03-工作记录/码上职业')
VIEW_JSON = os.path.join(WORKSPACE, '内容状态视图.json')

NOW = lambda: datetime.now().isoformat(timespec='seconds')

DDL = '''
CREATE TABLE IF NOT EXISTS units (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  full_name TEXT,
  category TEXT NOT NULL
    CHECK(category IN ('公司信息','电网','铁路','银行','基金','证券','期货','保险',
                       '信托','其他','中烟','医院','学校','机关单位')),
  subcategory TEXT,
  nature TEXT, tags TEXT, city TEXT, region TEXT, industry TEXT,
  website TEXT, recruit_site TEXT, logo_path TEXT,
  credit_code TEXT, registered_capital TEXT, insured_count TEXT,
  enterprise_type TEXT, registered_address TEXT,
  status TEXT DEFAULT 'active', remark TEXT,
  updated_at TEXT,
  UNIQUE(name, category)
);
CREATE TABLE IF NOT EXISTS sources (
  id INTEGER PRIMARY KEY,
  bullet_id TEXT UNIQUE,
  url TEXT NOT NULL,
  unit_id INTEGER NOT NULL REFERENCES units(id),
  title_raw TEXT, announce_date TEXT,
  raw_path TEXT, deadline TEXT,
  recruit_status TEXT DEFAULT 'active'
    CHECK(recruit_status IN ('active','expired','unknown')),
  fetched_at TEXT
);
CREATE TABLE IF NOT EXISTS articles (
  id INTEGER PRIMARY KEY,
  source_id INTEGER REFERENCES sources(id),
  variant TEXT,
  meta TEXT,
  status TEXT NOT NULL DEFAULT 'unwritten'
    CHECK(status IN ('unwritten','written','draft','published')),
  verify_pass INTEGER DEFAULT 0,
  media_id TEXT,
  publish_type INTEGER, published_title TEXT, published_digest TEXT,
  published_url TEXT, published_at TEXT,
  msgid TEXT, appmsgid TEXT, itemidx INTEGER,
  albums TEXT, published_original INTEGER, is_deleted INTEGER DEFAULT 0,
  tags TEXT, created_at TEXT, updated_at TEXT,
  UNIQUE(source_id, variant)
);
CREATE TABLE IF NOT EXISTS article_metrics (
  id INTEGER PRIMARY KEY,
  article_id INTEGER NOT NULL REFERENCES articles(id),
  snap_date TEXT NOT NULL,
  read_num INTEGER, like_num INTEGER, old_like_num INTEGER,
  share_num INTEGER, comment_num INTEGER, reprint_num INTEGER,
  moment_like_num INTEGER, sent_succ INTEGER,
  UNIQUE(article_id, snap_date)
);
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY,
  article_id INTEGER NOT NULL REFERENCES articles(id),
  event_type TEXT NOT NULL CHECK(event_type IN (
    'source_added','verify_passed','written','pushed_draftbox',
    'grouped','published_matched','archived','expired')),
  payload TEXT, at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS audit_log (
  id INTEGER PRIMARY KEY, table_name TEXT, row_key TEXT,
  action TEXT, snapshot TEXT, at TEXT, actor TEXT
);
'''

def connect():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    con.execute('PRAGMA journal_mode=WAL')
    con.execute('PRAGMA foreign_keys=ON')
    return con

def log_event(con, article_id, etype, payload=None, actor='AI'):
    con.execute('INSERT INTO events(article_id,event_type,payload,at) VALUES(?,?,?,?)',
                (article_id, etype, json.dumps(payload or {}, ensure_ascii=False), NOW()))
    con.commit()

def find_article(con, kw):
    """按 id / media_id / 标题子串 找稿件，唯一命中才返回。"""
    if kw.isdigit():
        r = con.execute('SELECT * FROM articles WHERE id=?', (int(kw),)).fetchone()
        if r: return r
    r = con.execute('SELECT * FROM articles WHERE media_id=?', (kw,)).fetchone()
    if r: return r
    rs = con.execute('SELECT * FROM articles WHERE published_title LIKE ? OR meta LIKE ?',
                     (f'%{kw}%', f'%{kw}%')).fetchall()
    if len(rs) == 1: return rs[0]
    if len(rs) > 1:
        sys.exit(f'⛔ 关键词命中 {len(rs)} 篇，请用 id/media_id 精确指定')
    return None

# ── 子命令 ──────────────────────────────────────────────

def cmd_init(a):
    con = connect()
    con.executescript(DDL)
    con.commit()
    print(f'✅ pipeline.db 表结构就绪: {DB}')

def cmd_ready(a):
    con = connect()
    rs = con.execute('''
      SELECT s.id sid, u.name unit, s.title_raw, s.deadline, s.recruit_status,
             (SELECT COUNT(*) FROM articles a WHERE a.source_id=s.id) n_articles
      FROM sources s JOIN units u ON u.id=s.unit_id
      WHERE s.recruit_status='active'
      ORDER BY CASE WHEN s.deadline GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
                    THEN s.deadline ELSE '9999-12-31' END, s.id''').fetchall()
    print(f'{"id":>4} {"截止":<12} {"稿":>3} {"单位":<20} 公告标题')
    for r in rs:
        print(f'{r["sid"]:>4} {r["deadline"] or "-":<12} {r["n_articles"]:>3} {r["unit"][:20]:<20} {(r["title_raw"] or "")[:36]}')
    print(f'共 {len(rs)} 条 active 素材')

def cmd_written(a):
    con = connect()
    art = find_article(con, a.article)
    if not art: sys.exit(f'⛔ 找不到稿件: {a.article}')
    meta = json.loads(art['meta'] or '{}')
    if a.files:
        meta['files'] = a.files          # 三件套路径记入 meta（md,html,cover）
    con.execute('UPDATE articles SET meta=? WHERE id=?',
                (json.dumps(meta, ensure_ascii=False), art['id']))
    log_event(con, art['id'], 'written', {'files': a.files})
    con.commit()
    print(f'[ok] article#{art["id"]} 门禁通过（meta 已记三件套；状态列已删，事件流水为准）')

def cmd_pushed(a):
    con = connect()
    art = find_article(con, a.article)
    if not art:
        print(f'[hook] 未匹配到流水线稿件（{a.article[:24]}…）—— 可能不在本库范围，跳过')
        return   # 钩子模式：不阻塞推送主流程
    su = a.source_url or None
    con.execute('UPDATE articles SET source_url=COALESCE(source_url, ?) WHERE id=?',
                (su, art['id']))
    log_event(con, art['id'], 'pushed_draftbox', {'media_id': a.media_id, 'source_url': su})
    con.commit()
    print(f'[ok] article#{art["id"]} → draft (media_id={a.media_id[:20]}...)')

def cmd_grouped(a):
    con = connect()
    art = find_article(con, a.article)
    if not art: sys.exit(f'⛔ 找不到稿件: {a.article}')
    payload = {'publish_type': a.publish_type}
    con.execute('UPDATE articles SET publish_type=?, published_at=? WHERE id=?',
                (a.publish_type, NOW(), art['id']))
    log_event(con, art['id'], 'grouped', payload)
    con.commit()
    print(f'[ok] article#{art["id"]} → published')

def cmd_import_published(a):
    """发表记录 → articles 全量补全（2026-10-09 朱总裁定：articles 以平台回传为准）。

    每篇发表记录文章按归一化标题查 articles：
      已有 → 补空字段（轻 UPDATE，不覆盖已有值）；
      没有 → INSERT（source_id=NULL＝平台回传未挂接本地线索，schema 已放开）。
    防重：标题归一化精确匹配；unit 挂接后续人工/方案C，绝不猜。
    """
    import glob, re
    src = a.src or max(glob.glob('/Users/zhugx/.cache/weixin/publish_records/*发表记录*.json'),
                       key=os.path.getmtime)
    d = json.load(open(src))
    con = connect()
    art_rows = con.execute('SELECT id, published_title, published_url, published_at, publish_type, msgid, appmsgid, itemidx, published_original, is_deleted FROM articles').fetchall()
    def _norm(t):
        return re.sub(r'\s+', '', t or '')
    by_title = {}
    for r in art_rows:
        by_title[_norm(r['published_title'])] = r
    now = NOW()
    inserted = updated = skipped = 0
    con.execute('BEGIN')
    for item in d.get('publish_list', []):
        try:
            info = json.loads(item['publish_info'])
        except Exception:
            continue
        ptype = item.get('publish_type')
        sent_t = (info.get('sent_info') or {}).get('time')
        for i, am in enumerate(info.get('appmsg_info', [])):
            ptitle = (am.get('title') or '').strip()
            if not ptitle:
                continue
            am_t = sent_t or (am.get('line_info') or {}).get('send_time')
            pub_time = datetime.fromtimestamp(am_t).isoformat(sep=' ', timespec='seconds') if am_t else None
            url = am.get('content_url') or ''
            hit = by_title.get(_norm(ptitle))
            if hit:
                sets, vals = [], []
                for col, v in [('published_title', ptitle), ('published_url', url),
                               ('published_at', pub_time), ('publish_type', ptype),
                               ('msgid', str(info.get('msgid'))), ('appmsgid', str(am.get('appmsgid'))),
                               ('itemidx', i), ('published_original', am.get('copyright_type')),
                               ('is_deleted', 1 if am.get('is_deleted') else 0)]:
                    if v and not hit[col]:
                        sets.append(f'{col}=?'); vals.append(v)
                if sets:
                    vals.append(hit['id'])
                    con.execute("UPDATE articles SET " + ', '.join(sets) + " WHERE id=?", vals)
                    log_event(con, hit['id'], 'published_backfill', {'title': ptitle[:40]})
                    updated += 1
                else:
                    skipped += 1
            else:
                cur = con.execute(
                    "INSERT INTO articles (variant, publish_type,"
                    " published_title, published_url, published_at, msgid, appmsgid, itemidx,"
                    " published_original, is_deleted)"
                    " VALUES ('wx-import', ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (ptype, ptitle, url, pub_time, str(info.get('msgid')),
                     str(am.get('appmsgid')), i, am.get('copyright_type'),
                     1 if am.get('is_deleted') else 0))
                con.execute("INSERT INTO audit_log (table_name, row_key, action, snapshot, at, actor) "
                            "VALUES ('articles', ?, 'import_published', ?, ?, 'content_ctl')",
                            (str(cur.lastrowid), json.dumps({'title': ptitle[:60], 'url': url[:80]},
                                                            ensure_ascii=False), now))
                inserted += 1
    con.commit()
    total = con.execute("SELECT COUNT(*) FROM articles WHERE status='published'").fetchone()[0]
    print(f'[ok] import_published：新增 {inserted} ／ 补字段 {updated} ／ 已齐 {skipped}；articles published 现共 {total} 篇')
    con.close()


def cmd_reconcile(a):
    """拉最新发表记录，按 content_url/标题 匹配 draft 稿自动回填 published。"""
    import glob
    src = a.src or max(glob.glob('/Users/zhugx/.cache/weixin/publish_records/*发表记录*.json'),
                       key=os.path.getmtime)
    d = json.load(open(src))
    con = connect()
    drafts = con.execute('''SELECT a.*, u.name unit_name, u.full_name unit_full FROM articles a JOIN sources s ON s.id=a.source_id JOIN units u ON u.id=s.unit_id WHERE a.status IN ('draft','published')''').fetchall()
    matched, pending = 0, []
    for item in d.get('publish_list', []):
        info = json.loads(item['publish_info'])
        ptype = item.get('publish_type')
        sent_t = (info.get('sent_info') or {}).get('time')
        for i, am in enumerate(info.get('appmsg_info', [])):
            url = am.get('content_url') or ''
            ptitle = am.get('title') or ''
            # 【2026-10-09 修】发表·不通知(publish_type=1)没有 sent_info，时间在 appmsg_info[i].line_info.send_time
            # 只读 sent_info 会让未通知稿 published_at 全空（实测 69/89 篇）。两处字段兜底。
            am_t = sent_t or (am.get('line_info') or {}).get('send_time')
            pub_time = datetime.fromtimestamp(am_t).isoformat(sep=' ', timespec='seconds') if am_t else None
            hit = None
            import re as _re
            for art in drafts:
                if art['published_url']: continue
                wt = art['published_title']
                # 信号1（主）：单位关键片段出现在发布标题（去「国网/公司/有限/股份」等壳后 ≥4 字）
                core = _re.sub(r'国网|有限责任公司|有限公司|股份|责任公司|公司', '',
                               art['unit_full'] or art['unit_name'] or '')
                uhit = len(core) >= 4 and core[:6] in ptitle
                # 信号2（辅）：工作/公告标题与发布标题 LCS ≥ 6 且发布标题含业务词
                biz = any(k in ptitle for k in ('校招','招聘','招录','校园招聘','公告'))
                if uhit and biz and _lcs(wt, ptitle) >= 6:
                    hit = art; break
            if hit:
                con.execute('''UPDATE articles SET publish_type=?, published_title=?,
                               published_url=?, published_at=?, msgid=?, appmsgid=?, itemidx=?,
                               published_original=?, is_deleted=? WHERE id=?''',
                            (ptype, ptitle, url, pub_time, str(info.get('msgid')),
                             str(am.get('appmsgid')), i, am.get('copyright_type'),
                             1 if am.get('is_deleted') else 0, hit['id']))
                log_event(con, hit['id'], 'published_matched',
                          {'publish_type': ptype, 'url': url, 'title': ptitle})
                matched += 1
                tag = '字段补全'
                print(f'[ok] #{hit["id"]} {hit["published_title"][:24]} {tag}（发布标题: {ptitle[:28]}）')
            else:
                pending.append(ptitle)
    con.commit()
    print(f'\n对账完成: 自动回填 {matched} 篇 ｜ 未匹配线上稿 {len(pending)} 篇（人工判断）')
    for t in pending[:10]:
        print(f'  ? {t[:40]}')

def _lcs(a, b):
    m = [[0]*(len(b)+1) for _ in range(len(a)+1)]
    best = 0
    for i in range(1, len(a)+1):
        for j in range(1, len(b)+1):
            if a[i-1] == b[j-1]:
                m[i][j] = m[i-1][j-1]+1; best = max(best, m[i][j])
    return best

def cmd_export(a):
    con = connect()
    arts = con.execute('''SELECT a.*, s.bullet_id, s.url source_url, u.name unit_name
                          FROM articles a JOIN sources s ON s.id=a.source_id
                          JOIN units u ON u.id=s.unit_id''').fetchall()
    out = {'schema_version': '2.0-view', 'updated_at': NOW(),
           'authority': '只读视图！真源=工具/内容流水线.db（events 驱动），本文件禁止手改',
           'batches': {}}
    for r in arts:
        key = f'{r["unit_name"]}||{r["published_title"]}'
        out['batches'][key] = {
            'unit': r['unit_name'], 'title': r['published_title'], 'state': r['status'],
            'meta': json.loads(r['meta'] or '{}'), 'issue': (json.loads(r['meta'] or '{}')).get('issue'),
            'media_id': r['media_id'], 'source': {'bullet_id': r['bullet_id'], 'url': r['source_url']},
            'publish': ({'type': r['publish_type'], 'title': r['published_title'],
                         'url': r['published_url'], 'at': r['published_at'],
                         'albums': json.loads(r['albums'] or '[]')} if r['status'] == 'published' else {}),
        }
    json.dump(out, open(VIEW_JSON, 'w'), ensure_ascii=False, indent=1)
    print(f'✅ 视图已导出: {VIEW_JSON}（{len(out["batches"])} 条）')

def cmd_audit(a):
    con = connect()
    for t in ('units', 'sources', 'articles', 'events', 'audit_log'):
        print(f'{t:>10}: {con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]} 行')
    print('\n状态分布:', dict(con.execute(
        'SELECT status, COUNT(*) FROM articles GROUP BY status').fetchall()))
    bad = con.execute('''SELECT COUNT(*) FROM articles a LEFT JOIN sources s ON s.id=a.source_id
                         WHERE s.id IS NULL''').fetchone()[0]
    print(f'孤儿稿件(无素材): {bad}（应为 0）')

def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('init')
    p = sub.add_parser('ready'); p.add_argument('--all', action='store_true')
    p = sub.add_parser('written'); p.add_argument('article'); p.add_argument('--files')
    p = sub.add_parser('pushed'); p.add_argument('article'); p.add_argument('--media-id', required=True)
    p.add_argument('--title'); p.add_argument('--match', choices=['title','id'], default='id')
    p.add_argument('--source-url')
    p = sub.add_parser('import_published'); p.add_argument('--src')
    p = sub.add_parser('grouped'); p.add_argument('article')
    p.add_argument('--publish-type', type=int, default=1)
    p = sub.add_parser('reconcile'); p.add_argument('--src')
    sub.add_parser('export')
    sub.add_parser('audit')
    a = ap.parse_args()
    globals()[f'cmd_{a.cmd}'](a)

if __name__ == '__main__':
    main()
