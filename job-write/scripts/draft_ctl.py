#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""draft_ctl.py — 单条草稿秒级回写 内容流水线.db `drafts` 表（2026-10-09 方案A）

定位
----
wx_pipeline 推送成功后的 hook②：STEP 4 的 draft/get 回读响应落盘后，
本脚本**零额外 API 调用**，把这一条草稿 upsert 进 drafts 表（含单位解析＋audit_log）。
与 draft_sync.py（批式全量对账）共用同一套字段映射与单位解析——import 复用，单一真源。

接口
----
    # hook 模式（wx_pipeline 自动调用，直写）
    draft_ctl.py --json /tmp/wxrun_mashang/zj_draft_get.json \
                 --media-id <media_id> --apply

    # 手动补写模式（默认 dry-run）
    draft_ctl.py --json <path> --media-id <id>

输入 json 兼容两种形态：
  a) {"media_id": "...", "news_item": [...]}   ← wx_pipeline 落盘（方案A）
  b) {"news_item": [...]}                       ← wx_draft.py get --json（media_id 走 --media-id）

⛔ 只写镜像字段；status / article_id 不碰（local_prefix/verify_pass 列已于 2026-10-10 DROP）
   （status 归看板人工 mark，article_id 挂接归方案 C）。
"""
import argparse
import json
import sys
from datetime import datetime

import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from draft_sync import resolve_unit, guess_line, connect, DEFAULT_DB, NOW  # noqa: E402


def load_item(path, media_id_arg):
    """从落盘 json 提取单条草稿字段（兼容两种顶层形态）。"""
    with open(path, encoding='utf-8') as f:
        d = json.load(f)
    items = d.get('news_item') or []
    if not items:
        raise ValueError('json 中无 news_item')
    mid = (media_id_arg or '').strip() or (d.get('media_id') or '').strip()
    if not mid:
        raise ValueError('media_id 未提供（json 顶层与 --media-id 均为空）')
    ni = items[0]
    return {
        'media_id': mid,
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
    }


def audit(con, media_id, action, payload):
    con.execute(
        "INSERT INTO audit_log (table_name, row_key, action, snapshot, at, actor) "
        "VALUES ('drafts', ?, ?, ?, ?, 'wx_pipeline-hook')",
        (media_id, action, json.dumps(payload, ensure_ascii=False), NOW()))


def main():
    ap = argparse.ArgumentParser(description='单条草稿回写 drafts 表（方案A hook②）')
    ap.add_argument('--json', required=True, help='draft/get 回读落盘 json')
    ap.add_argument('--media-id', default=None, help='media_id（json 顶层无 media_id 时必填）')
    ap.add_argument('--db', default=DEFAULT_DB)
    ap.add_argument('--apply', action='store_true', help='真写；缺省 dry-run')
    a = ap.parse_args()

    d = load_item(a.json, a.media_id)
    con = connect(a.db)
    try:
        con.execute('PRAGMA busy_timeout=5000')
        uid, uname, note = resolve_unit(con, d['title'])
        line = guess_line(d['title'], d['source_url'])

        r = con.execute('SELECT id, title FROM drafts WHERE media_id=?', (d['media_id'],)).fetchone()
        mode = 'UPDATE' if r else 'INSERT'
        print(f'[dry-run] ' if not a.apply else '[apply] ',
              f'{mode} media_id={d["media_id"][:20]}…｜{d["title"][:26]}…｜'
              f'unit={(uname or "—")}｜line={line}｜{note}')

        if not a.apply:
            print('[dry-run] 未写库。加 --apply 执行。')
            return

        con.execute('BEGIN')
        if r:
            con.execute(
                'UPDATE drafts SET title=?,source_url=?,temp_url=? WHERE id=?',
                (d['title'], d['source_url'], d['temp_url'], r['id']))
        else:
            con.execute(
                'INSERT INTO drafts (media_id,title,source_url,temp_url,status) '
                'VALUES (?,?,?,?,\'draft\')',
                (d['media_id'], d['title'], d['source_url'], d['temp_url']))
        audit(con, d['media_id'],
              f'hook_{mode.lower()}',
              {'title': d['title'][:60], 'unit': uname, 'note': note,
               'source_url': d['source_url'], 'line': line})
        con.commit()
        print(f'[ok] drafts {mode} 成功（media_id={d["media_id"][:20]}…，audit_log 已记）')
    except Exception as e:
        con.rollback()
        print(f'❌ 已回滚：{e}')
        sys.exit(1)
    finally:
        con.close()


if __name__ == '__main__':
    main()
