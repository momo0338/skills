"""dy-doudian CLI：凭据检查、token 管理、快速数据查询。"""

from __future__ import annotations

import argparse
import json
import sys

from dy_doudian.client import DoudianClient
from dy_doudian.config import TOKENS_PATH, ConfigError, ensure_config
from dy_doudian.token_manager import TokenManager


def cmd_status() -> int:
    try:
        cfg = ensure_config()
    except ConfigError as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 1
    print(f"app_key:   {cfg.app_key[:6]}...{cfg.app_key[-4:]}")
    print(f"shop_id:   {cfg.shop_id}")
    print(f"access_token: {'已配置' if cfg.access_token else '未配置'}")
    print(f"refresh_token: {'已配置' if cfg.refresh_token else '未配置（无法自动续期）'}")
    print(f"token 持久化: {TOKENS_PATH if TOKENS_PATH.exists() else '无（首次授权后生成）'}")
    return 0


def cmd_token_info() -> int:
    try:
        cfg = ensure_config()
    except ConfigError as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 1
    tm = TokenManager(cfg)
    try:
        token = tm.get_token()
        print(f"当前 access_token: {token[:12]}...{token[-6:]}")
    except Exception as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 1
    return 0


def cmd_query(args: argparse.Namespace) -> int:
    try:
        cfg = ensure_config()
        client = DoudianClient(cfg)
    except ConfigError as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 1
    try:
        if args.kind == "orders":
            data = client.get_order_list(page=args.page, page_size=args.page_size)
        elif args.kind == "products":
            data = client.get_product_list(page=args.page, page_size=args.page_size)
        elif args.kind == "reviews":
            data = client.get_review_list(page=args.page, page_size=args.page_size)
        elif args.kind == "refunds":
            data = client.get_refund_list(page=args.page, page_size=args.page_size)
        elif args.kind == "bills":
            data = client.get_bill_list(page=args.page, page_size=args.page_size)
        elif args.kind == "shop":
            data = client.get_shop_info()
        elif args.kind == "live-rooms":
            data = client.list_live_rooms(page=args.page, page_size=args.page_size)
        else:
            print(f"未知查询类型: {args.kind}", file=sys.stderr)
            return 1
        print(json.dumps(data, ensure_ascii=False, indent=2)[:args.limit])
    except Exception as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 1
    finally:
        client.close()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="dy-doudian 抖音小店本地化工具")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("status", help="查看凭据配置状态")
    sub.add_parser("token", help="查看/刷新 access_token")

    q = sub.add_parser("query", help="查询经营数据")
    q.add_argument(
        "kind",
        choices=["orders", "products", "reviews", "refunds", "bills", "shop", "live-rooms"],
        help="查询类型",
    )
    q.add_argument("--page", type=int, default=0)
    q.add_argument("--page-size", type=int, default=10)
    q.add_argument("--limit", type=int, default=4000, help="输出字符上限")

    from dy_doudian.browser.cli import build_parser as build_browser_parser

    build_browser_parser(sub)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "status":
        return cmd_status()
    if args.command == "token":
        return cmd_token_info()
    if args.command == "query":
        return cmd_query(args)
    if args.command == "browser":
        from dy_doudian.browser.cli import dispatch

        return dispatch(args)
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
