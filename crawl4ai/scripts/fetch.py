#!/usr/bin/env python3
"""crawl4ai-fetcher: 基于 Crawl4AI 的一键网页提取脚本。

用法:
  python3 fetch.py <url> [--query 主题] [--selector css] [--json] [--max-chars N]

输出: 渲染后网页的 Markdown 正文（--query 时输出 Fit Markdown；--json 时输出结构化 JSON）。
"""

import argparse
import asyncio
import json
import sys


def parse_args():
    p = argparse.ArgumentParser(description="Crawl4AI 网页提取脚本")
    p.add_argument("url", help="目标网页 URL")
    p.add_argument("--query", default="", help="BM25 主题过滤词，输出 Fit Markdown")
    p.add_argument("--selector", default="", help="CSS 选择器，定向提取指定区域")
    p.add_argument("--json", action="store_true", help="输出 JSON 结构化结果")
    p.add_argument("--max-chars", type=int, default=0, help="限制输出字符数 (0=不限制)")
    return p.parse_args()


def clip(text, n):
    return text if n <= 0 or len(text) <= n else text[:n] + "\n…[已截断]"


async def run(args):
    from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig

    browser = BrowserConfig(headless=True)
    config = CrawlerRunConfig(css_selector=args.selector or None)

    if args.query:
        from crawl4ai.content_filter_strategy import BM25ContentFilter
        config.content_filter = BM25ContentFilter(user_query=args.query, threshold=1.0)

    async with AsyncWebCrawler(config=browser) as crawler:
        result = await crawler.arun(url=args.url, config=config)

    if result.success is False:
        print(f"抓取失败: {result.error_message}", file=sys.stderr)
        sys.exit(1)

    markdown = result.fit_markdown if (args.query and result.fit_markdown) else result.markdown
    markdown = markdown or ""

    if args.json:
        out = {
            "url": args.url,
            "title": getattr(result, "metadata", {}).get("title", "") if getattr(result, "metadata", None) else "",
            "markdown": clip(markdown, args.max_chars),
            "links_count": len(getattr(result, "links", {}).get("internal", [])) + len(getattr(result, "links", {}).get("external", [])) if getattr(result, "links", None) else 0,
        }
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        print(clip(markdown, args.max_chars))


if __name__ == "__main__":
    asyncio.run(run(parse_args()))
