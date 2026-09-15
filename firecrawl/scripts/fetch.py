#!/usr/bin/env python3
"""Firecrawl CLI 工具: 支持单页 Scrape、全站递归 Crawl、站点地图 Map 与结构化 Extract。

用法:
  # 1. 单页抓取为 Markdown
  python3 fetch.py scrape "https://example.com/article" [--json] [--max-chars N]

  # 2. 发现整站所有 URL (Map)
  python3 fetch.py map "https://example.com" [--query "docs"] [--limit 50]

  # 3. 递归爬取整站 / 批量页面 (Crawl)
  python3 fetch.py crawl "https://example.com" [--limit 10] [--max-depth 2] [--json]

  # 4. 结构化抽取 (Extract)
  python3 fetch.py extract "https://example.com/product" --schema '{"name": "string", "price": "number"}'

环境变量:
  FIRECRAWL_API_KEY   : Firecrawl API Key（官方云端服务必需；私有化部署若未设 auth 可选）
  FIRECRAWL_BASE_URL  : API 基础地址（默认: https://api.firecrawl.dev）
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

DEFAULT_BASE_URL = "https://api.firecrawl.dev"


def get_config():
    # 优先读取当前进程环境变量，若未设置则自动回退读取 ~/.codex/.env
    api_key = os.environ.get("FIRECRAWL_API_KEY", "").strip()
    base_url = os.environ.get("FIRECRAWL_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
    if not api_key:
        env_path = os.path.expanduser("~/.codex/.env")
        if os.path.exists(env_path):
            try:
                with open(env_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("FIRECRAWL_API_KEY="):
                            api_key = line.split("=", 1)[1].strip().strip('"\'')
                        elif line.startswith("FIRECRAWL_BASE_URL="):
                            base_url = line.split("=", 1)[1].strip().strip('"\'').rstrip("/")
            except Exception:
                pass

    if not api_key and base_url == DEFAULT_BASE_URL:
        print("错误: 未配置环境变量 FIRECRAWL_API_KEY。", file=sys.stderr)
        print("请在环境变量中设置 FIRECRAWL_API_KEY（注册获取: https://firecrawl.dev）", file=sys.stderr)
        print("如果是本地/私有化部署，请设置 FIRECRAWL_BASE_URL（如 http://localhost:3002）。", file=sys.stderr)
        sys.exit(1)
    return api_key, base_url


def api_request(endpoint, payload=None, method="POST"):
    api_key, base_url = get_config()
    url = f"{base_url}{endpoint}"
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "MomoSkills-Firecrawl/1.0",
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            res_body = resp.read().decode("utf-8")
            return json.loads(res_body)
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        try:
            err_json = json.loads(err_body)
            msg = err_json.get("error", err_body)
        except Exception:
            msg = err_body
        print(f"Firecrawl API 请求失败 [{e.code}]: {msg}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"网络请求错误: {e}", file=sys.stderr)
        sys.exit(1)


def clip(text, n):
    if not text:
        return ""
    return text if n <= 0 or len(text) <= n else text[:n] + "\n…[已截断]"


def handle_scrape(args):
    payload = {
        "url": args.url,
        "formats": ["markdown"],
    }
    if args.only_main_content:
        payload["onlyMainContent"] = True
    if args.wait_for:
        payload["waitFor"] = args.wait_for

    res = api_request("/v1/scrape", payload=payload)
    data = res.get("data", {})
    markdown = data.get("markdown", "")
    metadata = data.get("metadata", {})

    if args.json:
        out = {
            "success": res.get("success", True),
            "url": args.url,
            "title": metadata.get("title", ""),
            "description": metadata.get("description", ""),
            "markdown": clip(markdown, args.max_chars),
            "metadata": metadata,
        }
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        print(clip(markdown, args.max_chars))


def handle_map(args):
    payload = {"url": args.url}
    if args.query:
        payload["search"] = args.query
    if args.limit:
        payload["limit"] = args.limit

    res = api_request("/v1/map", payload=payload)
    links = res.get("links", [])
    if args.json:
        out = {
            "success": res.get("success", True),
            "url": args.url,
            "total": len(links),
            "links": links,
        }
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        print(f"发现 {len(links)} 个 URL 链接:")
        for idx, link in enumerate(links, start=1):
            print(f"{idx}. {link}")


def handle_crawl(args):
    scrape_opts = {"formats": ["markdown"]}
    payload = {
        "url": args.url,
        "limit": args.limit,
        "scrapeOptions": scrape_opts,
    }
    if args.max_depth:
        payload["maxDepth"] = args.max_depth
    if args.allow_backward_links:
        payload["allowBackwardLinks"] = True

    # 1. 提交异步 Crawl 任务
    init_res = api_request("/v1/crawl", payload=payload)
    crawl_id = init_res.get("id")
    if not crawl_id:
        print(f"未能获取 crawl ID: {init_res}", file=sys.stderr)
        sys.exit(1)

    print(f"已启动全站爬取任务 [ID: {crawl_id}]，正在等待抓取完成...", file=sys.stderr)

    # 2. 轮询状态
    start_time = time.time()
    while True:
        status_res = api_request(f"/v1/crawl/{crawl_id}", method="GET")
        status = status_res.get("status")
        total = status_res.get("total", 0)
        completed = status_res.get("completed", 0)

        if status == "completed":
            data = status_res.get("data", [])
            if args.json:
                print(json.dumps(status_res, ensure_ascii=False, indent=2))
            else:
                print(f"\n===== 爬取完成 (共 {len(data)} 页) =====\n")
                for item in data:
                    meta = item.get("metadata", {})
                    title = meta.get("title", "未命名页面")
                    page_url = meta.get("sourceURL", "")
                    md = item.get("markdown", "")
                    print(f"## {title}\nURL: {page_url}\n")
                    print(clip(md, args.max_chars))
                    print("\n" + "-" * 40 + "\n")
            break
        elif status == "failed":
            print(f"爬取任务失败: {status_res.get('error', '未知错误')}", file=sys.stderr)
            sys.exit(1)
        elif status == "cancelled":
            print("爬取任务已被取消", file=sys.stderr)
            sys.exit(1)
        else:
            print(f"  进度: {completed}/{total} 页 ({status})...", file=sys.stderr)
            if time.time() - start_time > args.timeout:
                print(f"爬取任务超时（>{args.timeout}s），终止等待", file=sys.stderr)
                sys.exit(1)
            time.sleep(3)


def handle_extract(args):
    try:
        schema = json.loads(args.schema)
    except Exception as e:
        print(f"解析 JSON Schema 失败: {e}", file=sys.stderr)
        sys.exit(1)

    payload = {
        "urls": [args.url],
        "schema": schema,
    }
    if args.prompt:
        payload["prompt"] = args.prompt

    res = api_request("/v1/extract", payload=payload)
    print(json.dumps(res, ensure_ascii=False, indent=2))


def main():
    p = argparse.ArgumentParser(description="Firecrawl API 网页提取与全站爬取工具")
    sub = p.add_subparsers(dest="command", help="操作命令")

    # scrape
    p_scrape = sub.add_parser("scrape", help="单页抓取为 Markdown")
    p_scrape.add_argument("url", help="目标 URL")
    p_scrape.add_argument("--json", action="store_true", help="输出完整 JSON 结构")
    p_scrape.add_argument("--only-main-content", action="store_true", default=True, help="仅提取主体内容")
    p_scrape.add_argument("--wait-for", type=int, default=0, help="等待渲染毫秒数")
    p_scrape.add_argument("--max-chars", type=int, default=0, help="限制输出字符数")

    # map
    p_map = sub.add_parser("map", help="发现整站 URL 列表 (Site Map)")
    p_map.add_argument("url", help="站点根 URL")
    p_map.add_argument("--query", default="", help="搜索过滤关键词")
    p_map.add_argument("--limit", type=int, default=100, help="最大返回 URL 数量")
    p_map.add_argument("--json", action="store_true", help="输出 JSON 格式")

    # crawl
    p_crawl = sub.add_parser("crawl", help="全站深度递归爬取")
    p_crawl.add_argument("url", help="站点起始 URL")
    p_crawl.add_argument("--limit", type=int, default=10, help="最大爬取页面数")
    p_crawl.add_argument("--max-depth", type=int, default=2, help="最大爬取深度")
    p_crawl.add_argument("--allow-backward-links", action="store_true", help="允许向上一级路径跳转")
    p_crawl.add_argument("--timeout", type=int, default=300, help="总超时秒数")
    p_crawl.add_argument("--max-chars", type=int, default=4000, help="每页 Markdown 最大截断字符数")
    p_crawl.add_argument("--json", action="store_true", help="输出 JSON 格式")

    # extract
    p_extract = sub.add_parser("extract", help="LLM 结构化抽取")
    p_extract.add_argument("url", help="目标 URL")
    p_extract.add_argument("--schema", required=True, help="JSON Schema 字符串")
    p_extract.add_argument("--prompt", default="", help="提示词说明")

    args = p.parse_args()
    if not args.command:
        p.print_help()
        sys.exit(1)

    if args.command == "scrape":
        handle_scrape(args)
    elif args.command == "map":
        handle_map(args)
    elif args.command == "crawl":
        handle_crawl(args)
    elif args.command == "extract":
        handle_extract(args)


if __name__ == "__main__":
    main()
