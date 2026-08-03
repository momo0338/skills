"""每日巡检：汇总订单/商品/驳回/罗盘数据，生成运营日报。

借鉴 clawshop-douyin-operator 的每日巡检流程：
1. 订单管理 → 今日订单数
2. 商品管理 → 在售商品总数
3. 审核驳回页 → 驳回商品数
4. 可选：电商罗盘经营概览关键指标
"""

from __future__ import annotations

import logging
import time
from datetime import date
from typing import Any

from playwright.sync_api import Page

from dy_doudian.browser.base import FXG_DOMAIN
from dy_doudian.browser.order_client import read_order_count
from dy_doudian.browser.shop_client import count_rejected, read_all_products

logger = logging.getLogger(__name__)

COMPASS_URL = f"{FXG_DOMAIN}/ffa/mcompass/overview"


def _read_compass_overview(page: Page) -> dict[str, Any]:
    """读取电商罗盘经营概览关键指标（尽力而为）。"""
    try:
        page.goto(COMPASS_URL, wait_until="domcontentloaded")
        time.sleep(6)
    except Exception:
        return {}
    data = page.evaluate(
        """() => {
            const text = document.body.innerText;
            const out = {};
            const pairs = [
                ['gmv', /(?:成交|GMV)[金额]*\\s*[¥￥]?\\s*([\\d,.]+[万亿]?)/],
                ['orders', /(?:订单|单量)[^\\n]{0,6}(\\d+)/],
                ['visitors', /(?:访客|uv)[^\\n]{0,6}(\\d+)/],
                ['conversion', /(?:转化率|支付转化率)[^\\n]{0,6}([\\d.]+%)/],
            ];
            pairs.forEach(([key, re]) => {
                const m = text.match(re);
                if (m) out[key] = m[1];
            });
            return out;
        }"""
    )
    return data if isinstance(data, dict) else {}


def run_daily_report(page: Page) -> dict[str, Any]:
    """执行每日巡检并生成日报数据。

    Returns:
        包含巡检日期与各维度数据的字典
    """
    result: dict[str, Any] = {"date": date.today().isoformat()}

    try:
        result["today_orders"] = read_order_count(page)
    except Exception as exc:
        result["today_orders"] = None
        result.setdefault("errors", []).append(f"订单数读取失败: {exc}")

    try:
        products = read_all_products(page, max_pages=5)
        result["on_sale_products"] = len(products)
    except Exception as exc:
        result["on_sale_products"] = None
        result.setdefault("errors", []).append(f"商品数读取失败: {exc}")

    try:
        result["rejected_products"] = count_rejected(page)
    except Exception as exc:
        result["rejected_products"] = None
        result.setdefault("errors", []).append(f"驳回数读取失败: {exc}")

    try:
        result["compass"] = _read_compass_overview(page)
    except Exception as exc:
        result.setdefault("errors", []).append(f"罗盘读取失败: {exc}")

    return result


def format_report(data: dict[str, Any]) -> str:
    """把巡检数据格式化为可读日报文本。"""
    lines = [
        "📊 抖店每日巡检日报",
        f"🗓️ {data['date']}",
        "",
    ]
    orders = data.get("today_orders")
    lines.append(f"今日订单：{orders if orders is not None else '读取失败'}单")
    on_sale = data.get("on_sale_products")
    lines.append(f"在售商品：{on_sale if on_sale is not None else '读取失败'}个")
    rejected = data.get("rejected_products")
    lines.append(f"审核驳回：{rejected if rejected is not None else '读取失败'}个")

    compass = data.get("compass") or {}
    if compass:
        lines.append("")
        lines.append("电商罗盘：")
        for key, value in compass.items():
            lines.append(f"  {key}: {value}")

    errors = data.get("errors") or []
    if errors:
        lines.append("")
        lines.append("⚠️ 巡检告警：")
        for err in errors:
            lines.append(f"  - {err}")

    return "\n".join(lines)
