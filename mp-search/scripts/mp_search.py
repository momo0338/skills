#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
mp_search.py: 微信文章与官方标准短链检索采集统一工具

功能：
1. album   - 抓取公众号合集（Album）整卷文章列表与 Markdown 索引（公开 API，免登录）
2. account - 获取指定公众号全量/近期历史图文与永久短链（公众平台超链接接口）
3. format  - 将搜一搜采集到的文章元数据与真实互动指标格式化为 Markdown 对比表格
"""

import argparse
import json
import os
import re
import subprocess
import sys

# 保证同目录模块可直接引入
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def handle_album(args):
    """处理合集抓取"""
    from album_fetcher import AlbumFetcher

    fetcher = AlbumFetcher(output_dir=args.output, batch_size=args.batch_size)
    result = fetcher.fetch(args.url)

    if result.get("success"):
        print("\n" + "=" * 60)
        print("✅ 合集抓取成功！")
        print("=" * 60)
        print("合集名称:", result.get("album_title", "-"))
        print("公众号:", result.get("account_name", "-"))
        print("文章总数:", result.get("total_count", 0))
        if result.get("index_file"):
            print("Markdown 索引文件:", result["index_file"])
        if result.get("json_file"):
            print("JSON 数据文件:", result["json_file"])
    else:
        print("\n❌ 合集抓取失败:", result.get("error", "未知错误"), file=sys.stderr)
        sys.exit(1)


def handle_account(args):
    """处理号内历史文章获取"""
    from wechat_mp_login import mp_login_and_get_articles

    print("📝 目标公众号:", args.nickname)
    print("📊 最大获取条数:", args.max_count)
    print("🌐 模式:", "无头模式 (Headless)" if args.headless else "可视化浏览器")
    if args.output:
        print("💾 输出文件:", args.output)
    print()

    try:
        result = mp_login_and_get_articles(
            nickname=args.nickname,
            max_count=args.max_count,
            headless=args.headless,
            output_file=args.output,
        )

        if result.get("success"):
            print("\n" + "=" * 60)
            print("✅ 账号推文获取成功！")
            print("=" * 60)
            print("公众号:", args.nickname)
            print("文章总数:", result.get("total", 0))
            print("本次获取:", len(result.get("articles", [])))
        else:
            print("\n❌ 获取失败:", result.get("message", "未知错误"), file=sys.stderr)
            sys.exit(1)
    except Exception as e:
        print("\n❌ 发生异常:", e, file=sys.stderr)
        sys.exit(1)


def handle_format(args):
    """处理搜一搜数据表格格式化"""
    from mp_search_formatter import format_markdown_table

    with open(args.input_file, "r", encoding="utf-8") as f:
        payload = json.load(f)

    keyword = payload.get("keyword", "微信搜一搜")
    rank_type = payload.get("rank_type", "最热")
    items = payload.get("items", [])

    md_content = format_markdown_table(keyword, rank_type, items)

    if args.output:
        os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(md_content)
        print("✅ 表格已输出至:", args.output)
    else:
        print(md_content)

def handle_search(args):
    """处理公众号文章关键词检索（支持最热/最新）"""
    from mp_search_formatter import format_markdown_table

    keyword = args.keyword.strip()
    sort_mode = args.sort  # "hot" or "new"
    rank_type = "最新" if sort_mode == "new" else "最热"
    limit = args.limit

    print(f"🔍 正在检索微信公众号文章: 关键词「{keyword}」 | 排序: {rank_type} | 数量: {limit}篇 ...", file=sys.stderr)

    cmd = ["opencli", "weixin", "search", keyword, "--limit", str(limit), "-f", "json"]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        raw = res.stdout
        idx = raw.find("[")
        if idx == -1:
            print(f"⚠️ 未检索到结果或输出格式异常: {res.stderr}", file=sys.stderr)
            items = []
        else:
            raw_data = json.loads(raw[idx:])
            items = []
            for d in raw_data:
                account_name = d.get("author") or d.get("account") or "-"
                pub_time = d.get("publish_time") or "-"
                item = {
                    "title": d.get("title", "").strip(),
                    "account": account_name,
                    "publish_date": pub_time,
                    "read_count": "-",
                    "like_count": 0,
                    "share_count": 0,
                    "collect_count": 0,
                    "comment_count": 0,
                    "mp_url": d.get("url", "").strip(),
                    "summary": d.get("summary", "").strip()
                }
                items.append(item)
    except FileNotFoundError:
        print("❌ 未找到 opencli 命令，请确认系统已安装 opencli: npm install -g @jackwener/opencli", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"❌ 检索失败: {e}", file=sys.stderr)
        sys.exit(1)

    payload = {
        "keyword": keyword,
        "rank_type": rank_type,
        "items": items
    }

    if args.output:
        os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        print(f"✅ 检索 JSON 数据已保存至: {args.output}", file=sys.stderr)

    md_content = format_markdown_table(keyword, rank_type, items)
    if args.format_md:
        os.makedirs(os.path.dirname(os.path.abspath(args.format_md)), exist_ok=True)
        with open(args.format_md, "w", encoding="utf-8") as f:
            f.write(md_content)
        print(f"✅ 对比表格 Markdown 已保存至: {args.format_md}", file=sys.stderr)

    if not args.output and not args.format_md:
        print(md_content)


def main():
    parser = argparse.ArgumentParser(
        description="MP-Search: 微信文章与官方标准短链检索采集工具"
    )
    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # 0. search 子命令
    search_parser = subparsers.add_parser("search", help="按关键词检索微信文章列表（支持最热/最新）")
    search_parser.add_argument("keyword", help="搜索关键词")
    search_parser.add_argument("-s", "--sort", choices=["hot", "new"], default="hot", help="排序方式：hot(最热/综合), new(最新时效)")
    search_parser.add_argument("-n", "--limit", type=int, default=10, help="返回条数 (默认 10)")
    search_parser.add_argument("-o", "--output", help="输出 JSON 数据文件路径 (供 gh-write 消费)")
    search_parser.add_argument("--format-md", help="同步输出 Markdown 对比表格文件路径")

    # 1. album 子命令
    album_parser = subparsers.add_parser("album", help="抓取公众号合集（Album）整卷文章列表")
    album_parser.add_argument("url", help="微信合集页面 URL")
    album_parser.add_argument("-o", "--output", default="./weixin-albums", help="输出目录 (默认 ./weixin-albums)")
    album_parser.add_argument("-b", "--batch-size", type=int, default=20, help="每页获取文章数 (默认 20，最大 20)")

    # 2. account 子命令
    account_parser = subparsers.add_parser("account", help="获取指定公众号历史推文列表与官方短链")
    account_parser.add_argument("nickname", help="目标公众号名称")
    account_parser.add_argument("-n", "--max-count", type=int, default=20, help="最大获取数量 (默认 20)")
    account_parser.add_argument("--headless", action="store_true", default=True, help="无头模式 (默认开启)")
    account_parser.add_argument("--no-headless", dest="headless", action="store_false", help="显示浏览器窗口 (用于扫码登录)")
    account_parser.add_argument("-o", "--output", help="输出 JSON 文件路径")

    # 3. format 子命令
    format_parser = subparsers.add_parser("format", help="将搜一搜采集数据格式化为 Markdown 互动对比表")
    format_parser.add_argument("input_file", help="搜一搜采集数据 JSON 文件路径")
    format_parser.add_argument("-o", "--output", help="输出 Markdown 文件路径 (默认标准输出)")

    args = parser.parse_args()

    if args.command == "search":
        handle_search(args)
    elif args.command == "album":
        handle_album(args)
    elif args.command == "account":
        handle_account(args)
    elif args.command == "format":
        handle_format(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
