#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WeRSS CLI - WeChat Official Accounts RSS & Subscription Assistant
Zero-dependency CLI tool for managing WeRSS instances via AK/SK auth.
"""

import argparse
import datetime
import json
import os
import sys
import urllib.parse
from pathlib import Path

try:
    from werss.client import load_config as _load_config_file, api_request as _client_request
except ImportError:  # pragma: no cover - fallback for direct script execution
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from werss.client import load_config as _load_config_file, api_request as _client_request


def load_config(args):
    """Load configuration: CLI flags > Env vars > config.json > ~/.werss/config.json"""
    return _load_config_file(
        base_url=args.base_url,
        ak=args.ak,
        sk=args.sk,
    )


def api_request(base_url, ak, sk, method, endpoint, params=None, data=None):
    """Backward-compatible wrapper delegating to werss.client.api_request."""
    return _client_request(base_url, ak, sk, method, endpoint, params=params, data=data)


def cmd_subscribe(args, base_url, ak, sk):
    """Add a subscription by WeChat article link or MP name."""
    if args.url:
        print(f"[*] Parsing WeChat article: {args.url}")
        res = api_request(
            base_url, ak, sk,
            method="POST",
            endpoint="/api/v1/wx/mps/by_article",
            params={"url": args.url}
        )
        if isinstance(res, dict) and res.get("code") == 0:
            data = res.get("data", {})
            mp_id = data.get("mp_id") or data.get("id")
            mp_info = data.get("mp_info") or {}
            mp_name = mp_info.get("mp_name") or data.get("mp_name", "未知")
            logo = mp_info.get("logo") or data.get("logo") or data.get("mp_cover", "")
            biz = mp_info.get("biz") or data.get("biz") or data.get("faker_id", "")
            intro = data.get("mp_intro") or ""
            article_title = data.get("title", "")

            print("\n[✓] 订阅成功！")
            print("=" * 50)
            print(f"  公众号名称: {mp_name}")
            print(f"  内部识别码: {mp_id}")
            if article_title:
                print(f"  解析来源文: {article_title}")
            if biz:
                print(f"  微信 Biz ID: {biz}")
            if intro:
                print(f"  简介信息: {intro}")
            if logo:
                print(f"  头像链接: {logo}")
            print("-" * 50)
            print("  RSS 订阅源:")
            print(f"  • RSS 2.0:  {base_url}/feed/{mp_id}.xml")
            print(f"  • Atom:     {base_url}/feed/{mp_id}.atom")
            print(f"  • JSON:     {base_url}/feed/{mp_id}.json")
            print("=" * 50)
            return 0
        else:
            print(f"[✗] 订阅失败: {res}")
            return 1
    elif args.name:
        print(f"[*] Adding MP by name: {args.name}")
        body = {"mp_name": args.name}
        if args.mp_id:
            body["mp_id"] = args.mp_id
        if args.cover:
            body["mp_cover"] = args.cover
        if args.intro:
            body["mp_intro"] = args.intro

        res = api_request(
            base_url, ak, sk,
            method="POST",
            endpoint="/api/v1/wx/mps",
            data=body
        )
        if isinstance(res, dict) and res.get("code") == 0:
            print(f"[✓] 添加成功: {res.get('data')}")
            return 0
        else:
            print(f"[✗] 添加失败: {res}")
            return 1
    else:
        print("[!] 请提供 --url <文章链接> 或 --name <公众号名称>")
        return 1


def cmd_list(args, base_url, ak, sk):
    """List subscribed official accounts."""
    params = {
        "page": args.page,
        "size": args.size,
    }
    if args.keyword:
        params["keyword"] = args.keyword

    res = api_request(base_url, ak, sk, "GET", "/api/v1/wx/mps", params=params)
    if not isinstance(res, dict) or res.get("code") != 0:
        print(f"[✗] 获取公众号列表失败: {res}")
        return 1

    data = res.get("data", {})
    mps = data.get("list", [])
    total = data.get("total", len(mps))

    if args.json:
        print(json.dumps(res, indent=2, ensure_ascii=False))
        return 0

    print(f"\n[*] 已订阅公众号 (共 {total} 个, 当前第 {args.page} 页 / 每页 {args.size} 条):")
    print("=" * 80)
    print(f"{'公众号名称':<16} | {'ID':<22} | {'状态':<6} | {'Feed XML'}")
    print("-" * 80)
    for m in mps:
        mp_id = m.get("id") or m.get("mp_id", "-")
        name = m.get("mp_name", "未知")
        status = "启用" if m.get("status", 1) == 1 else "暂停"
        feed_url = f"{base_url}/feed/{mp_id}.xml"
        # Format padding for Chinese characters
        name_display = name[:14]
        print(f"{name_display:<14} | {mp_id:<22} | {status:<6} | {feed_url}")
    print("=" * 80)
    print(f"提示: 全量聚合 Feed 链接: {base_url}/feed/all.xml\n")
    return 0


def cmd_search(args, base_url, ak, sk):
    """Search official accounts online via WeChat search."""
    kw = urllib.parse.quote(args.keyword)
    res = api_request(base_url, ak, sk, "GET", f"/api/v1/wx/mps/search/{kw}", params={"limit": args.limit, "offset": args.offset})
    if not isinstance(res, dict) or res.get("code") != 0:
        print(f"[✗] 搜索失败: {res}")
        return 1

    data = res.get("data", {})
    items = data.get("list", [])
    print(f"\n[*] 微信在线搜索: '{args.keyword}' (找到 {len(items)} 个候选结果):")
    print("=" * 80)
    for i, it in enumerate(items, 1):
        nick = it.get("nickname", "")
        alias = it.get("alias", "")
        sign = it.get("signature", "").replace("\n", " ")
        fakeid = it.get("fakeid", "")
        qr_url = f"https://open.weixin.qq.com/qr/code?username={alias}" if alias else "（未公开微信号，暂无直接二维码）"
        print(f"[{i}] {nick} (微信号: {alias or '无'})")
        print(f"    二维码: {qr_url}")
        print(f"    签名: {sign}")
        print(f"    FakeID (biz): {fakeid}")
        print()
    print("=" * 80)
    return 0


def cmd_articles(args, base_url, ak, sk):
    """Fetch articles from WeRSS."""
    params = {
        "page": args.page,
        "size": args.limit,
    }
    if args.mp_id:
        params["mp_id"] = args.mp_id
    if args.keyword:
        params["keyword"] = args.keyword

    res = api_request(base_url, ak, sk, "GET", "/api/v1/wx/articles", params=params)
    if not isinstance(res, dict) or res.get("code") != 0:
        print(f"[✗] 获取文章列表失败: {res}")
        return 1

    data = res.get("data", {})
    articles = data.get("list", [])
    total = data.get("total", len(articles))

    if args.json:
        print(json.dumps(res, indent=2, ensure_ascii=False))
        return 0

    print(f"\n[*] 文章列表 (共 {total} 篇, 展示前 {len(articles)} 条):")
    print("=" * 80)
    for a in articles:
        art_id = a.get("id", "")
        title = a.get("title", "无标题")
        pub_time = a.get("publish_time") or a.get("create_time")
        if pub_time:
            time_str = datetime.datetime.fromtimestamp(pub_time).strftime("%Y-%m-%d %H:%M")
        else:
            time_str = a.get("created_at", "-")[:16]
        url = a.get("url") or a.get("link", "")
        print(f"• [{time_str}] {title}")
        print(f"  ID: {art_id}  |  链接: {url}")
    print("=" * 80)
    return 0


def cmd_sync(args, base_url, ak, sk):
    """Trigger update/sync for a specific MP."""
    mp_id = args.id
    print(f"[*] 正在触发公众号 {mp_id} 的文章抓取与同步...")
    res = api_request(
        base_url, ak, sk,
        "GET",
        f"/api/v1/wx/mps/update/{mp_id}",
        params={"start_page": 0, "end_page": args.pages}
    )
    if isinstance(res, dict) and res.get("code") == 0:
        data = res.get("data", {})
        total = data.get("total", 0)
        mps_info = data.get("mps", {})
        name = mps_info.get("mp_name", mp_id)
        print(f"[✓] 同步完成: 公众号【{name}】，抓取到 {total} 篇新文章。")
        return 0
    else:
        print(f"[✗] 同步失败: {res}")
        return 1


def cmd_export_opml(args, base_url, ak, sk):
    """Export OPML subscriptions file."""
    print("[*] 正在导出 OPML 订阅源列表...")
    res = api_request(base_url, ak, sk, "GET", "/api/v1/wx/export/mps/opml")
    if isinstance(res, str) and ("<opml" in res or "<?xml" in res):
        out_file = args.output or "werss_subscriptions.opml"
        with open(out_file, "w", encoding="utf-8") as f:
            f.write(res)
        print(f"[✓] OPML 已导出并保存至: {out_file}")
        return 0
    elif isinstance(res, dict) and res.get("code") == 0:
        opml_text = res.get("data", "")
        out_file = args.output or "werss_subscriptions.opml"
        with open(out_file, "w", encoding="utf-8") as f:
            f.write(opml_text)
        print(f"[✓] OPML 已导出并保存至: {out_file}")
        return 0
    else:
        print(f"[✗] 导出失败: {res}")
        return 1


def cmd_feed(args, base_url, ak, sk):
    """Show feed URLs."""
    if args.id:
        print(f"\n[*] 公众号 [{args.id}] Feed 链接:")
        print(f"  • RSS 2.0:  {base_url}/feed/{args.id}.xml")
        print(f"  • Atom:     {base_url}/feed/{args.id}.atom")
        print(f"  • JSON:     {base_url}/feed/{args.id}.json")
    else:
        print(f"\n[*] 全局聚合 Feed 链接:")
        print(f"  • 全量汇总 RSS: {base_url}/feed/all.xml")
    return 0


def cmd_tags(args, base_url, ak, sk):
    """Manage tags in WeRSS."""
    action = args.action or "list"

    if action == "list":
        res = api_request(base_url, ak, sk, "GET", "/api/v1/wx/tags", params={"limit": 100})
        if not isinstance(res, dict) or res.get("code") != 0:
            print(f"[✗] 获取标签列表失败: {res}")
            return 1
        tags = res.get("data", {}).get("list", [])
        if args.json:
            print(json.dumps(tags, indent=2, ensure_ascii=False))
            return 0
        print(f"\n[*] 标签列表 (共 {len(tags)} 个):")
        print("=" * 80)
        print(f"{'标签名称':<20} | {'公众号数':<8} | {'标签 ID':<38}")
        print("-" * 80)
        for t in tags:
            raw_mps = json.loads(t.get("mps_id") or "[]")
            mp_count = len(raw_mps)
            print(f"{t.get('name', '-'):<20} | {mp_count:<8} | {t.get('id', '-'):<38}")
            print(f"  • Web 详情:  {base_url}/views/tag/{t.get('id')}")
            print(f"  • Feed XML:  {base_url}/feed/tag/{t.get('id')}.xml")
            print(f"  • Feed Atom: {base_url}/feed/tag/{t.get('id')}.atom")
        print("=" * 80)
        return 0

    elif action == "create":
        if not args.name:
            print("[✗] 请指定标签名称 (--name)")
            return 1
        payload = {
            "name": args.name,
            "cover": "",
            "intro": args.intro or "",
            "mps_id": "[]",
            "status": 1
        }
        res = api_request(base_url, ak, sk, "POST", "/api/v1/wx/tags", data=payload)
        if isinstance(res, dict) and res.get("code") == 0:
            tag_data = res.get("data", {})
            print(f"[✓] 成功创建标签【{args.name}】(ID: {tag_data.get('id')})")
            return 0
        else:
            print(f"[✗] 创建标签失败: {res}")
            return 1

    elif action == "add":
        if not args.tag or not args.mp_ids:
            print("[✗] 请指定目标标签 (--tag) 和公众号 ID (--mp-ids)")
            return 1
        # Resolve tag ID
        res = api_request(base_url, ak, sk, "GET", "/api/v1/wx/tags", params={"limit": 100})
        tags = res.get("data", {}).get("list", [])
        target = None
        for t in tags:
            if t.get("id") == args.tag or t.get("name") == args.tag:
                target = t
                break
        if not target:
            print(f"[✗] 未找到标签: {args.tag}")
            return 1

        raw_mps = json.loads(target.get("mps_id") or "[]")
        # Extract existing IDs whether stored as dicts or strings
        existing_ids = set()
        mps_items = []
        for item in raw_mps:
            mid = item.get("id") if isinstance(item, dict) else str(item)
            if mid and mid not in existing_ids:
                existing_ids.add(mid)
                mps_items.append({"id": mid, "name": item.get("name", "") if isinstance(item, dict) else ""})

        added = 0
        for mid in args.mp_ids:
            if mid not in existing_ids:
                existing_ids.add(mid)
                mps_items.append({"id": mid, "name": ""})
                added += 1

        payload = {
            "name": target.get("name"),
            "cover": target.get("cover") or "",
            "intro": target.get("intro") or "",
            "mps_id": json.dumps(mps_items, ensure_ascii=False),
            "status": target.get("status", 1)
        }
        update_res = api_request(base_url, ak, sk, "PUT", f"/api/v1/wx/tags/{target['id']}", data=payload)
        if isinstance(update_res, dict) and update_res.get("code") == 0:
            print(f"[✓] 成功为标签【{target.get('name')}】追加 {added} 个公众号，当前共 {len(mps_items)} 个！")
            return 0
        else:
            print(f"[✗] 更新标签失败: {update_res}")
            return 1

    return 0


def cmd_delete(args, base_url, ak, sk):
    """Delete a subscription."""
    mp_id = args.id
    print(f"[*] 正在删除订阅: {mp_id}")
    res = api_request(base_url, ak, sk, "DELETE", f"/api/v1/wx/mps/{mp_id}")
    if isinstance(res, dict) and res.get("code") == 0:
        print(f"[✓] 已成功删除公众号 {mp_id}")
        return 0
    else:
        print(f"[✗] 删除失败: {res}")
        return 1


def main():
    parser = argparse.ArgumentParser(description="WeRSS CLI - 微信公众号 RSS 订阅与管理客户端")
    parser.add_argument("--base-url", help="WeRSS API Base URL (default: https://rss.mmdai.top)")
    parser.add_argument("--ak", help="Access Key (AK)")
    parser.add_argument("--sk", help="Secret Key (SK)")

    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # subscribe
    p_sub = subparsers.add_parser("subscribe", help="添加公众号订阅（支持文章链接自动解析或直接指定名称）")
    p_sub.add_argument("--url", "-u", help="微信公众号文章链接 (如 https://mp.weixin.qq.com/s/xxx)")
    p_sub.add_argument("--name", "-n", help="公众号名称")
    p_sub.add_argument("--mp-id", help="公众号唯一 ID（可选）")
    p_sub.add_argument("--cover", help="公众号头像链接（可选）")
    p_sub.add_argument("--intro", help="公众号简介（可选）")

    # list
    p_list = subparsers.add_parser("list", help="列出已订阅的公众号")
    p_list.add_argument("--keyword", "-k", help="按公众号名称关键词过滤")
    p_list.add_argument("--page", type=int, default=1, help="页码 (默认 1)")
    p_list.add_argument("--size", type=int, default=20, help="每页条数 (默认 20)")
    p_list.add_argument("--json", action="store_true", help="以 JSON 格式输出")

    # search
    p_search = subparsers.add_parser("search", help="微信在线搜索公众号")
    p_search.add_argument("keyword", help="搜索关键词")
    p_search.add_argument("--limit", type=int, default=5, help="返回条数 (默认 5)")
    p_search.add_argument("--offset", type=int, default=0, help="偏移量 (默认 0)")

    # articles
    p_art = subparsers.add_parser("articles", help="查询文章列表")
    p_art.add_argument("--mp-id", help="指定公众号 ID")
    p_art.add_argument("--keyword", "-k", help="文章标题关键词")
    p_art.add_argument("--limit", type=int, default=10, help="条数限制 (默认 10)")
    p_art.add_argument("--page", type=int, default=1, help="页码 (默认 1)")
    p_art.add_argument("--json", action="store_true", help="以 JSON 格式输出")

    # sync
    p_sync = subparsers.add_parser("sync", help="即时触发公众号更新同步")
    p_sync.add_argument("id", help="公众号 ID (如 MP_WXS_2390216734)")
    p_sync.add_argument("--pages", type=int, default=1, help="更新页数范围 (默认 1)")

    # feed
    p_feed = subparsers.add_parser("feed", help="查看 RSS / Atom 订阅链接")
    p_feed.add_argument("--id", help="指定公众号 ID (缺省时展示全量汇总 Feed)")

    # export-opml
    p_opml = subparsers.add_parser("export-opml", help="导出 OPML 订阅源文件")
    p_opml.add_argument("-o", "--output", help="保存的文件路径 (默认 werss_subscriptions.opml)")

    # tags
    p_tag = subparsers.add_parser("tags", help="管理订阅标签与标签 Feed")
    p_tag.add_argument("action", nargs="?", default="list", choices=["list", "create", "add"], help="操作: list(默认)/create/add")
    p_tag.add_argument("--name", help="标签名称")
    p_tag.add_argument("--intro", help="标签介绍")
    p_tag.add_argument("--tag", help="目标标签名称或 ID")
    p_tag.add_argument("--mp-ids", nargs="+", help="公众号 ID 列表")
    p_tag.add_argument("--json", action="store_true", help="以 JSON 格式输出")

    # delete
    p_del = subparsers.add_parser("delete", help="删除公众号订阅")
    p_del.add_argument("id", help="公众号 ID")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(0)

    base_url, ak, sk = load_config(args)

    commands = {
        "subscribe": cmd_subscribe,
        "list": cmd_list,
        "search": cmd_search,
        "articles": cmd_articles,
        "sync": cmd_sync,
        "feed": cmd_feed,
        "export-opml": cmd_export_opml,
        "tags": cmd_tags,
        "delete": cmd_delete,
    }

    handler = commands.get(args.command)
    if handler:
        sys.exit(handler(args, base_url, ak, sk))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
