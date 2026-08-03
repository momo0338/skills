"""订单管理：订单查询 + 发货操作（发货中心）。

抖店发货中心路径：/ffa/morder/logistics/ewaybill-delivery
只读查询可直接执行；发货为写操作，默认 dry_run 模式。
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any

from playwright.sync_api import Page

from dy_doudian.browser.base import FXG_DOMAIN

logger = logging.getLogger(__name__)

ORDER_LIST_URL = f"{FXG_DOMAIN}/ffa/morder/order/list"
DELIVERY_URL = f"{FXG_DOMAIN}/ffa/morder/logistics/ewaybill-delivery"


def read_order_count(page: Page) -> int:
    """读取订单列表页订单总数。"""
    page.goto(ORDER_LIST_URL, wait_until="domcontentloaded")
    time.sleep(6)
    match = page.evaluate(
        """() => {
            const m = document.body.innerText.match(/共\\s*\\d+\\s*单|共\\s*(\\d+)\\s*笔|全部\\s*(\\d+)\\s*单/);
            return m ? m[0] : null;
        }"""
    )
    if match:
        nums = re.findall(r"\d+", match)
        return int(nums[0]) if nums else 0
    return 0


def list_today_orders(page: Page, limit: int = 20) -> list[dict[str, Any]]:
    """读取今日订单列表（订单号 + 状态 + 金额，尽量截取）。"""
    page.goto(ORDER_LIST_URL, wait_until="domcontentloaded")
    time.sleep(6)
    rows = page.evaluate(
        """() => {
            const out = [];
            document.querySelectorAll('table tbody tr, [class*="order"] [class*="row"]').forEach(r => {
                const t = r.innerText || '';
                const id = t.match(/(\\d{15,})/);
                const money = t.match(/[¥￥]\\s*([\\d,.]+)/);
                if (id) out.push({
                    order_id: id[1],
                    money: money ? money[1] : null,
                    preview: t.slice(0, 80),
                });
            });
            return out;
        }"""
    )
    return rows[:limit]


def mark_order_shipped(page: Page, order_ids: list[str], dry_run: bool = True) -> dict[str, Any]:
    """对订单执行发货（发货中心）。

    Args:
        page: 已登录页面
        order_ids: 待发货订单号
        dry_run: True 时只做导航+定位验证，不实际提交（默认安全模式）

    Returns:
        操作结果
    """
    page.goto(DELIVERY_URL, wait_until="domcontentloaded")
    time.sleep(6)

    # 定位待发货订单搜索
    search_ok = page.evaluate(
        """(ids) => {
            const inputs = [...document.querySelectorAll('input')];
            const target = inputs.find(i => i.placeholder?.includes('订单号') || i.placeholder?.includes('搜索'));
            if (!target) return false;
            target.value = ids.join(',');
            target.dispatchEvent(new Event('input', { bubbles: true }));
            return true;
        }""",
        order_ids,
    )
    if not search_ok:
        return {"ok": False, "error": "未找到订单搜索框", "dry_run": dry_run}

    time.sleep(1)
    page.get_by_role("button", name=re.compile("查询|搜索")).first.click(timeout=5000)
    time.sleep(4)

    if dry_run:
        return {
            "ok": True,
            "dry_run": True,
            "message": f"已定位 {len(order_ids)} 个待发货订单（dry_run，未实际发货）",
        }

    # 实际发货：全选 → 批量发货 → 确认
    page.evaluate(
        """() => {
            const checks = [...document.querySelectorAll('input[type="checkbox"]')];
            checks.forEach(c => { if (!c.checked) c.click(); });
            return checks.length;
        }"""
    )
    time.sleep(1)
    ship_ok = page.evaluate(
        """() => {
            const btns = [...document.querySelectorAll('button')];
            const target = btns.find(b => b.textContent.trim().includes('发货'));
            if (target) { target.click(); return true; }
            return false;
        }"""
    )
    time.sleep(1.5)
    confirm_ok = page.evaluate(
        """() => {
            const btns = [...document.querySelectorAll('button')];
            const target = btns.find(b => b.textContent.trim().includes('确认') || b.textContent.trim().includes('确定'));
            if (target) { target.click(); return true; }
            return false;
        }"""
    )
    return {
        "ok": ship_ok,
        "requested": len(order_ids),
        "shipped": ship_ok,
        "confirmed": confirm_ok,
        "dry_run": False,
    }
