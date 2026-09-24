#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成「线上已发布流量台账」（码上职业）

数据源：微信后台发表记录 appmsgpublish 原始 JSON（由 mp-ops 的
refresh_publish_records.py 落盘），本脚本**只做解析与排版，不联网**。

══════════════════════════════════════════════════════════════════════
一、字段取法（2026-09-24 实测，踩过坑）
══════════════════════════════════════════════════════════════════════

- `publish_page` 是 **JSON 字符串**，需二次 `json.loads`，不是 dict。
- 发布性质：`publish_list[i].publish_type`
    - **101 = 群发**（占每日 1 次额度，通知粉丝）
    - **1   = 发表·不通知**（不占额度，有永久链接）
- ⛔ **发表·不通知没有 `sent_info`**（会漏掉所有不通知稿的日期）。
  日期统一取 `publish_info.appmsg_info[j].line_info.send_time`（Unix 秒）。
- 一条 `publish_list` 可能含**多篇** `appmsg_info`（多图文），要展开成多行。
- `read_num` / `share_num` 是**当前累计值**，每天取数要**直接覆盖**，
  ⛔ 绝不能自己累加（后台给的就是累计数，累加会越滚越错）。
- `is_deleted=true` 的稿**仍留在列表里**，要标出来而不是当正常数据用。

══════════════════════════════════════════════════════════════════════
二、用法
══════════════════════════════════════════════════════════════════════

  python3 build_traffic_ledger.py                     # 用最新发表记录生成
  python3 build_traffic_ledger.py --src <JSON 路径>    # 指定源文件
  python3 build_traffic_ledger.py --out <MD 路径>     # 指定输出（默认写运营/01-…）
  python3 build_traffic_ledger.py --dry-run           # 只打印统计，不写文件

⚠️ 本脚本**只读缓存、只写 vault 台账**，不碰 `jobs.db`、不改任何硬信息。
"""
import os
import sys
import json
import glob
import argparse
from datetime import datetime, timezone, timedelta

CST = timezone(timedelta(hours=8))
DEFAULT_OUT = os.path.expanduser(
    "~/codeup/obsidian/03-工作记录/码上职业/运营/01-线上已发布台账.md")
CACHE = os.path.expanduser("~/.cache/weixin/publish_records")


def pick_source(explicit=""):
    """取最新的 mashang 发表记录 JSON。"""
    if explicit:
        if not os.path.exists(explicit):
            sys.exit(f"源文件不存在：{explicit}")
        return explicit
    pats = [os.path.join(CACHE, "mashang_发表记录_*.json")]
    hits = []
    for p in pats:
        hits.extend(glob.glob(p))
    if not hits:
        sys.exit(f"没找到发表记录 JSON（{CACHE}/mashang_发表记录_*.json）。\n"
                 f"请先跑 mp-ops/scripts/refresh_publish_records.py 抓取。")
    return max(hits, key=os.path.getmtime)


def parse(src: str) -> list:
    """解析发表记录 → 行列表（每篇文章一行）。"""
    with open(src, encoding="utf-8") as f:
        raw = json.load(f)
    page = raw.get("publish_page")
    if isinstance(page, str):
        page = json.loads(page)          # ⛔ 二次解析，字符串不是 dict
    if not page:
        sys.exit("publish_page 为空，源文件可能不是有效响应。")

    rows = []
    for item in page.get("publish_list", []):
        ptype = item.get("publish_type")
        nature = "群发" if ptype == 101 else ("发表·不通知" if ptype == 1 else f"未知({ptype})")
        pinfo = item.get("publish_info")
        if isinstance(pinfo, str):
            pinfo = json.loads(pinfo)
        pinfo = pinfo or {}
        # ⛔ 不通知稿没有 sent_info，日期只能从 line_info.send_time 取
        sent = pinfo.get("sent_info") or {}
        batch_ts = sent.get("send_time")
        for art in pinfo.get("appmsg_info", []) or []:
            li = art.get("line_info") or {}
            ts = li.get("send_time") or batch_ts
            dt = datetime.fromtimestamp(ts, CST).strftime("%Y-%m-%d") if ts else "—"
            rows.append({
                "date": dt,
                "title": (art.get("title") or "").strip(),
                "nature": nature,
                "read": art.get("read_num", 0) or 0,
                "share": art.get("share_num", 0) or 0,
                "like": art.get("like_num", 0) or 0,
                "url": art.get("content_url") or "",
                "deleted": bool(art.get("is_deleted")),
            })
    rows.sort(key=lambda r: (r["date"], r["title"]), reverse=True)
    return rows


def render(rows: list, src: str) -> str:
    live = [r for r in rows if not r["deleted"]]
    dead = [r for r in rows if r["deleted"]]
    total_read = sum(r["read"] for r in live)
    total_share = sum(r["share"] for r in live)
    mass = sum(1 for r in live if r["nature"] == "群发")
    quiet = sum(1 for r in live if r["nature"] == "发表·不通知")
    top = sorted(live, key=lambda r: r["read"], reverse=True)[:10]

    L = []
    L.append("# 01 · 线上已发布台账（码上职业）\n")
    L.append(f"> 数据源：`{os.path.basename(src)}`｜生成时间：{datetime.now(CST):%Y-%m-%d %H:%M}")
    L.append(f"> 取数口径：微信后台**发表记录**（`appmsgpublish`）。"
             f"⛔ 草稿箱不可靠（群发后草稿仍留存），判断「发了没」只看这里。\n")
    L.append("## 概览\n")
    L.append("| 项 | 值 |")
    L.append("|---|---|")
    L.append(f"| 在册文章 | **{len(live)}** 篇 |")
    L.append(f"| 群发 / 发表·不通知 | {mass} / {quiet} |")
    L.append(f"| 累计阅读（合计） | **{total_read:,}** |")
    L.append(f"| 累计分享（合计） | **{total_share:,}** |")
    if dead:
        L.append(f"| ⛔ 已删除（不计入合计） | {len(dead)} 篇 |")
    L.append("")
    L.append("> 📌 `read_num`/`share_num` 是后台给的**当前累计值**，每天取数**直接覆盖**，⛔ 不要累加。\n")

    L.append("## 阅读 TOP10\n")
    L.append("| # | 日期 | 文章 | 性质 | 阅读 | 分享 |")
    L.append("|---|---|---|---|---|---|")
    for i, r in enumerate(top, 1):
        t = r["title"][:38] + ("…" if len(r["title"]) > 38 else "")
        L.append(f"| {i} | {r['date']} | {t} | {r['nature']} | {r['read']:,} | {r['share']:,} |")
    L.append("")

    L.append("## 全量明细（按日期倒序）\n")
    L.append("| 日期 | 文章 | 性质 | 阅读 | 分享 | 在看 | 链接 |")
    L.append("|---|---|---|---|---|---|---|")
    for r in rows:
        t = r["title"][:40] + ("…" if len(r["title"]) > 40 else "")
        flag = " ⛔已删" if r["deleted"] else ""
        link = f"[原文]({r['url']})" if r["url"] else "—"
        L.append(f"| {r['date']}{flag} | {t} | {r['nature']} | {r['read']:,} | "
                 f"{r['share']:,} | {r['like']:,} | {link} |")
    L.append("")
    L.append("---")
    L.append("")
    L.append("## 红线\n")
    L.append("1. ⛔ **累计值覆盖更新，不是累加**（后台给的就是累计数）。")
    L.append("2. ⛔ **判断「发了没」只看后台发表记录**，草稿箱会骗人。")
    L.append("3. ⛔ **同一份数字不抄进别处**（同主题只留一个入口）。专题文件只引结论。")
    L.append("4. ⛔ **不改 `jobs.db` 硬信息**；本台账只管流量，不管人数/截止日/岗位。")
    L.append("5. ⛔ 本号固定 `mashang`（码上职业），⛔ 别把 `manba`（满爸爱生活）数据混进来。")
    L.append("")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description="生成码上职业线上已发布流量台账")
    ap.add_argument("--src", default="", help="发表记录 JSON（默认取缓存里最新的）")
    ap.add_argument("--out", default=DEFAULT_OUT, help="输出 md 路径")
    ap.add_argument("--dry-run", action="store_true", help="只统计不写文件")
    args = ap.parse_args()

    src = pick_source(args.src)
    rows = parse(src)
    if not rows:
        sys.exit("解析出 0 行，源文件可能异常。")
    live = [r for r in rows if not r["deleted"]]
    print(f"源文件：{src}")
    print(f"解析：{len(rows)} 行（在册 {len(live)}，已删 {len(rows)-len(live)}）")
    print(f"群发 {sum(1 for r in live if r['nature']=='群发')} / "
          f"不通知 {sum(1 for r in live if r['nature']=='发表·不通知')}")
    print(f"累计阅读 {sum(r['read'] for r in live):,} / 累计分享 {sum(r['share'] for r in live):,}")
    if args.dry_run:
        print("\n--dry-run，未写文件")
        return
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(render(rows, src))
    print(f"\n✅ 已写入：{args.out}")


if __name__ == "__main__":
    main()
