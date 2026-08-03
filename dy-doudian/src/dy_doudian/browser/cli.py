"""dy-doudian browser 子命令：浏览器自动化运营操作。

安全边界：
- 只读操作（商品列表/订单数/巡检）可直接执行
- 写操作（上下架/发货）默认 dry_run，需显式 --execute
"""

from __future__ import annotations

import argparse
import sys

from dy_doudian.browser.base import DoudianBrowser, DoudianBrowserError
from dy_doudian.browser.daily_report import format_report, run_daily_report
from dy_doudian.browser.order_client import list_today_orders, mark_order_shipped, read_order_count
from dy_doudian.browser.shop_client import batch_take_down, read_all_products


def _require_login(browser: DoudianBrowser, page) -> bool:
    if not browser.is_logged_in(page):
        print(
            "未检测到抖店登录态。请先在浏览器中登录 https://fxg.jinritemai.com\n"
            "登录后重新运行本命令（登录态会自动保存复用）。",
            file=sys.stderr,
        )
        return False
    return True


def cmd_login() -> int:
    """打开浏览器让用户手动登录并保存登录态。"""
    with DoudianBrowser() as browser:
        page = browser.new_page()
        page.goto("https://fxg.jinritemai.com", wait_until="domcontentloaded")
        print("请在打开的浏览器中完成登录，登录成功后按回车继续...")
        input()
        browser.save_state()
        print("登录态已保存到 ~/.dy-doudian/browser-state.json")
    return 0


def cmd_products(args: argparse.Namespace) -> int:
    with DoudianBrowser() as browser:
        page = browser.new_page()
        if not _require_login(browser, page):
            return 1
        try:
            products = read_all_products(page, max_pages=args.max_pages)
            print(f"在售商品总数: {len(products)}")
            for p in products[: args.limit]:
                print(f"  {p['product_id']} | {p['name'][:40]} | {p['list_date'] or '日期未知'}")
            return 0
        except DoudianBrowserError as exc:
            print(f"错误: {exc}", file=sys.stderr)
            return 1


def cmd_take_down(args: argparse.Namespace) -> int:
    if not args.ids:
        print("请用 --ids 指定商品 ID（逗号分隔）", file=sys.stderr)
        return 1
    with DoudianBrowser() as browser:
        page = browser.new_page()
        if not _require_login(browser, page):
            return 1
        ids = [i.strip() for i in args.ids.split(",") if i.strip()]
        result = batch_take_down(page, ids)
        print(result)
        return 0 if result.get("ok") else 1


def cmd_orders(args: argparse.Namespace) -> int:
    with DoudianBrowser() as browser:
        page = browser.new_page()
        if not _require_login(browser, page):
            return 1
        if args.action == "count":
            print(f"订单总数: {read_order_count(page)}")
            return 0
        if args.action == "today":
            orders = list_today_orders(page, limit=args.limit)
            print(f"今日订单数: {len(orders)}")
            for o in orders:
                print(f"  {o['order_id']} | ¥{o['money'] or '?'} | {o['preview'][:40]}")
            return 0
        if args.action == "ship":
            if not args.ids:
                print("发货请用 --ids 指定订单号", file=sys.stderr)
                return 1
            result = mark_order_shipped(page, [i.strip() for i in args.ids.split(",")], dry_run=not args.execute)
            print(result)
            return 0 if result.get("ok") else 1
    return 1


def cmd_report() -> int:
    with DoudianBrowser() as browser:
        page = browser.new_page()
        if not _require_login(browser, page):
            return 1
        try:
            data = run_daily_report(page)
        except DoudianBrowserError as exc:
            print(f"错误: {exc}", file=sys.stderr)
            return 1
        print(format_report(data))
    return 0


def build_parser(subparsers) -> None:
    p = subparsers.add_parser("browser", help="浏览器自动化运营（抖店网页版）")
    sub = p.add_subparsers(dest="browser_action")

    sub.add_parser("login", help="打开浏览器登录抖店并保存登录态")

    prod = sub.add_parser("products", help="读取在售商品列表")
    prod.add_argument("--max-pages", type=int, default=20)
    prod.add_argument("--limit", type=int, default=20)

    td = sub.add_parser("takedown", help="批量下架商品")
    td.add_argument("--ids", required=True, help="商品 ID 逗号分隔")
    td.add_argument("--execute", action="store_true", help="实际执行（默认仅定位验证）")

    orders = sub.add_parser("orders", help="订单操作")
    orders.add_argument("action", choices=["count", "today", "ship"])
    orders.add_argument("--ids", help="发货用：订单号逗号分隔")
    orders.add_argument("--limit", type=int, default=20)
    orders.add_argument("--execute", action="store_true", help="实际发货（默认 dry-run）")

    sub.add_parser("report", help="每日巡检生成日报")


def dispatch(args: argparse.Namespace) -> int:
    """根据 browser 子命令分发到对应实现。"""
    action = getattr(args, "browser_action", None)
    if action == "login":
        return cmd_login()
    if action == "products":
        return cmd_products(args)
    if action == "takedown":
        return cmd_take_down(args)
    if action == "orders":
        return cmd_orders(args)
    if action == "report":
        return cmd_report()
    print("请指定 browser 子命令: login / products / takedown / orders / report", file=sys.stderr)
    return 1
