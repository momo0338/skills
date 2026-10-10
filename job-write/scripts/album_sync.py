#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""album_sync.py — 文章公开页 → articles.albums 合集回填（2026-10-09）

背景：发表记录接口（appmsgpublish）不回传合集字段，但**已发布文章的公开页面**
会渲染 `albuminfo`（合集 id/title/link/content_size），无需登录即可抓。

策略（保守）：
  - albums 为空的行 → 抓公开页解析，有合集则写入（JSON 数组格式，与既有数据一致）
  - albums 已有的行 → 抓来**只比对不覆盖**，差异打印让人工核（人工标签优先）
  - published_url 为空的行 → 跳过（wx-import 行 102 篇都有 published_url）

用法：
    python3 album_sync.py                 # dry-run（只统计与抽样）
    python3 album_sync.py --apply         # 真写
    python3 album_sync.py --all --apply   # 全量重抓比对（默认只抓空行）
"""
import argparse
import json
import re
import sqlite3
import sys
import time
import urllib.request
from datetime import datetime

DB = '/Users/zhugx/codeup/obsidian/03-工作记录/码上职业/工具/内容流水线.db'
UA = 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)'
NOW = lambda: datetime.now().isoformat(timespec='seconds')


def fetch_album(url):
    """抓文章公开页 → (合集名列表, 原始 albuminfo 片段是否存在)。"""
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    html = urllib.request.urlopen(req, timeout=15).read().decode('utf-8', errors='ignore')
    # albuminfo 块内 title: 'xxx'（容忍 " * 1" 尾巴）
    names = re.findall(r"albuminfo:\s*\{[^}]*?title:\s*'([^']+)'", html)
    if not names:  # 多合集形态：album_list / 多个块兜底
        names = re.findall(r"title:\s*'([^']{1,40})'[^}]*?album_id", html)
    return [n.strip() for n in dict.fromkeys(names) if n.strip()], bool(names)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--all', action='store_true', help='全量重抓比对（默认只抓 albums 空的）')
    ap.add_argument('--limit', type=int, default=0)
    a = ap.parse_args()

    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    where = '' if a.all else "AND (albums IS NULL OR albums='' OR albums='[]')"
    rows = con.execute(f"SELECT id, published_title, albums, published_url FROM articles "
                       f"WHERE status='published' AND published_url IS NOT NULL AND published_url != '' {where} "
                       f"ORDER BY id").fetchall()
    if a.limit:
        rows = rows[:a.limit]
    print(f'待处理 {len(rows)} 篇（{"全量比对" if a.all else "仅空行回填"}，mode={"APPLY" if a.apply else "DRY-RUN"}）')

    filled = mismatch = noblank = fail = 0
    for i, r in enumerate(rows, 1):
        t = r['published_title'][:26]
        try:
            names, _ = fetch_album(r['published_url'])
        except Exception as e:
            fail += 1
            print(f'  ⚠️ #{r["id"]} {t}: 抓取失败 {e}')
            names = None
        if names is None:
            continue
        cur = r['albums']
        cur_list = json.loads(cur) if cur and cur.startswith('[') else ([cur] if cur else [])
        new_json = json.dumps(names, ensure_ascii=False)
        if not names:
            noblank += 1
            print(f'  · #{r["id"]} {t}: 平台页无合集（{"保持" if not cur_list else f"人工值{cur_list}保留"}）')
        elif not cur_list:
            # 空 → 回填
            if a.apply:
                con.execute('BEGIN')
                con.execute('UPDATE articles SET albums=?, updated_at=? WHERE id=?', (new_json, NOW(), r['id']))
                con.execute("INSERT INTO audit_log (table_name, row_key, action, snapshot, at, actor) "
                            "VALUES ('articles', ?, 'album_fill', ?, ?, 'album_sync')",
                            (str(r['id']), json.dumps({'title': t, 'albums': names}, ensure_ascii=False), NOW()))
                con.commit()
            filled += 1
            print(f'  {"🗑️" if a.apply else "[dry]"} #{r["id"]} {t}: 回填 {names}')
        elif set(names) != set(cur_list):
            mismatch += 1
            print(f'  ⚠️ #{r["id"]} {t}: 人工值={cur_list} 平台值={names} —— 不覆盖，请人工核')
        else:
            print(f'  ✓ #{r["id"]} {t}: 一致')
        time.sleep(0.8)

    remain = con.execute("SELECT COUNT(*) FROM articles WHERE (albums IS NULL OR albums='' OR albums='[]') "
                         "AND published_url IS NOT NULL AND published_url != ''").fetchone()[0]
    print(f'\n[ok] 回填 {filled}｜差异待核 {mismatch}｜平台无合集 {noblank}｜失败 {fail}｜库内剩余空 {remain}（{"已写库" if a.apply else "dry-run 未写"}）')
    con.close()


if __name__ == '__main__':
    main()
