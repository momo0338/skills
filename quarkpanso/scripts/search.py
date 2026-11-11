#!/usr/bin/env python3
"""夸克盘搜搜索：走公开只读接口，默认返回 3 条。

用法：
    python3 search.py "武林外传"                  # 默认 3 条
    python3 search.py "武林外传" --limit 5
    python3 search.py "三体" --share-time month
    python3 search.py "武林外传" --raw             # 打印接口原始返回，排查用

接口返回不可用时输出 ENDPOINT_UNAVAILABLE，由调用方改走浏览器。
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

DEFAULT_ENDPOINT = os.environ.get("QUARKPANSO_API", "https://amcmm.com/api/pan-search-v3.php")


def call_endpoint(endpoint, params, timeout=15):
    url = endpoint + ("&" if "?" in endpoint else "?") + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")
    except urllib.error.URLError as exc:
        return 0, json.dumps({"ok": False, "error": "NETWORK", "msg": str(exc.reason)}, ensure_ascii=False)


def main():
    parser = argparse.ArgumentParser(description="夸克盘搜搜索（仅夸克网盘）")
    parser.add_argument("keyword", help="搜索关键词")
    parser.add_argument("--limit", type=int, default=3, help="返回条数，默认 3，服务端最多 5")
    parser.add_argument("--share-time", dest="share_time", default="", help="week / month / half_year / year")
    parser.add_argument("--page", type=int, default=1, help="页码")
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT, help="接口地址")
    parser.add_argument("--raw", action="store_true", help="打印接口原始返回")
    args = parser.parse_args()

    params = {
        "q": args.keyword,
        "limit": max(1, args.limit),
        "share_time": args.share_time,
        "page": max(1, args.page),
    }
    code, raw = call_endpoint(args.endpoint, params)

    if args.raw:
        print("HTTP %s" % code)
        print(raw[:4000])
        return 0

    try:
        body = json.loads(raw)
    except ValueError:
        print(json.dumps({
            "ok": False,
            "error": "ENDPOINT_UNAVAILABLE",
            "http": code,
            "hint": "接口返回非 JSON，请改用浏览器模式",
            "preview": raw[:160],
        }, ensure_ascii=False, indent=2))
        return 2

    if not isinstance(body, dict) or not body.get("ok"):
        message = body.get("msg") if isinstance(body, dict) else "unknown"
        print(json.dumps({
            "ok": False,
            "error": "ENDPOINT_UNAVAILABLE",
            "http": code,
            "upstream_error": body.get("error") if isinstance(body, dict) else None,
            "msg": message,
            "hint": "接口不可用，改用浏览器模式",
        }, ensure_ascii=False, indent=2))
        return 2

    body["channel"] = "endpoint"
    print(json.dumps(body, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
