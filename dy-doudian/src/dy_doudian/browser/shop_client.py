"""商品管理：全量列表读取 + 批量上/下架。

参考 clawshop-douyin-operator 的实战验证方案：
- 抖店商品列表是虚拟滚动，每页只渲染 ~7 条，必须边滚边采集
- 翻页用页码点击而非 URL
- 批量下架：搜索商品ID → 全选 → 批量下架 → 弹窗确认
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any

from playwright.sync_api import Page

from dy_doudian.browser.base import FXG_DOMAIN

logger = logging.getLogger(__name__)

PRODUCT_LIST_URL = f"{FXG_DOMAIN}/ffa/g/list?sov_draft_status=0&sov_goodsType=0"
PRODUCT_REJECTED_URL = f"{FXG_DOMAIN}/ffa/g/list?sov_draft_status=3"


def read_all_products(page: Page, max_pages: int = 20) -> list[dict[str, Any]]:
    """分页滚动采集全部在售商品。

    Returns:
        [{"product_id": str, "name": str, "list_date": str | None}]
    """
    page.goto(PRODUCT_LIST_URL, wait_until="domcontentloaded")
    time.sleep(8)

    products: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for _ in range(max_pages):
        # 当前页滚动采集
        page.evaluate(
            """() => {
                window._scrollDone = false;
                let i = 0;
                const scrollEl = document.scrollingElement;
                scrollEl.scrollTop = 0;
                const step = () => {
                    scrollEl.scrollTop += 500;
                    i++;
                    if (i < 15) setTimeout(step, 200);
                    else window._scrollDone = true;
                };
                step();
            }"""
        )
        for _ in range(30):
            if page.evaluate("window._scrollDone === true"):
                break
            time.sleep(0.3)

        rows = page.evaluate(
            """() => {
                const out = [];
                document.querySelectorAll('table tbody tr, [class*="goods"] [class*="row"], [class*="list"] [class*="item"]').forEach(r => {
                    const t = r.innerText || '';
                    const id = t.match(/ID[:：]?\\s*(\\d{15,})/);
                    const dt = t.match(/(20\\d{2}\\/\\d{2}\\/\\d{2})/);
                    const name = t.split('\\n')[0]?.slice(0, 60) || '';
                    if (id) out.push({ product_id: id[1], name, list_date: dt ? dt[1] : null });
                });
                return out;
            }"""
        )
        for row in rows:
            if row["product_id"] not in seen_ids:
                seen_ids.add(row["product_id"])
                products.append(row)

        # 翻页
        has_next = page.evaluate(
            """() => {
                const btns = [...document.querySelectorAll('[class*="pagination"] button, [class*="page"] button, .ant-pagination button')];
                const next = btns.find(b => b.textContent.includes('下一页') || b.getAttribute('aria-label')?.includes('next'));
                return next && !next.disabled;
            }"""
        )
        if not has_next:
            break
        clicked = page.evaluate(
            """() => {
                const btns = [...document.querySelectorAll('[class*="pagination"] button, [class*="page"] button, .ant-pagination button')];
                const next = btns.find(b => b.textContent.includes('下一页') || b.getAttribute('aria-label')?.includes('next'));
                if (next) { next.click(); return true; }
                return false;
            }"""
        )
        if not clicked:
            break
        time.sleep(4)

    return products


def batch_take_down(page: Page, product_ids: list[str]) -> dict[str, Any]:
    """批量下架商品。

    流程：打开商品管理 → 搜索框输入商品ID（逗号分隔）→ 查询 → 全选 → 批量下架 → 弹窗确认。

    Args:
        page: 已登录的页面
        product_ids: 商品 ID 列表

    Returns:
        操作结果统计
    """
    page.goto(PRODUCT_LIST_URL, wait_until="domcontentloaded")
    time.sleep(6)

    # 搜索商品 ID
    search_ok = page.evaluate(
        """(ids) => {
            const inputs = [...document.querySelectorAll('input')];
            const target = inputs.find(i => i.placeholder?.includes('搜索') || i.placeholder?.includes('ID'));
            if (!target) return false;
            target.value = ids;
            target.dispatchEvent(new Event('input', { bubbles: true }));
            return true;
        }""",
        ",".join(product_ids),
    )
    if not search_ok:
        return {"ok": False, "error": "未找到商品搜索框"}

    # 点查询
    time.sleep(1)
    page.get_by_role("button", name=re.compile("查询|搜索")).first.click(timeout=5000)
    time.sleep(4)

    # 全选
    page.evaluate(
        """() => {
            const checks = [...document.querySelectorAll('input[type="checkbox"]')];
            checks.forEach(c => { if (!c.checked) c.click(); });
            return checks.length;
        }"""
    )
    time.sleep(1)

    # 批量下架
    down_ok = page.evaluate(
        """() => {
            const btns = [...document.querySelectorAll('button')];
            const target = btns.find(b => b.textContent.trim().includes('批量下架') || b.textContent.trim() === '下架');
            if (target) { target.click(); return true; }
            return false;
        }"""
    )
    if not down_ok:
        return {"ok": False, "error": "未找到下架按钮"}

    # 弹窗确认
    time.sleep(1.5)
    confirm_ok = page.evaluate(
        """() => {
            const btns = [...document.querySelectorAll('button')];
            const target = btns.find(b => b.textContent.trim().includes('仍要下架') || b.textContent.trim() === '确定');
            if (target) { target.click(); return true; }
            return false;
        }"""
    )
    time.sleep(2)

    return {
        "ok": True,
        "requested": len(product_ids),
        "confirmed": confirm_ok,
    }


def count_rejected(page: Page) -> int:
    """统计审核驳回商品数。"""
    page.goto(PRODUCT_REJECTED_URL, wait_until="domcontentloaded")
    time.sleep(6)
    match = page.evaluate(
        """() => {
            const m = document.body.innerText.match(/共\\s*\\d+\\s*件商品|共\\s*(\\d+)\\s*条/);
            return m ? m[0] : null;
        }"""
    )
    if match:
        nums = re.findall(r"\d+", match)
        return int(nums[0]) if nums else 0
    return 0
