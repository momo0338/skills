"""浏览器自动化层测试（mock Page，不启动真实浏览器）。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from dy_doudian.browser.daily_report import format_report
from dy_doudian.browser.order_client import mark_order_shipped, read_order_count


def make_page(inner_text: str = "", rows: list | None = None) -> MagicMock:
    """构造 mock Page，支持 evaluate 按脚本特征返回不同结果。"""
    page = MagicMock()
    page.url = "https://fxg.jinritemai.com/ffa/morder/order/list"

    def evaluate(script, *args):
        if "match(/共" in script or "match(/全部" in script:
            return inner_text
        if "document.querySelectorAll('table tbody tr" in script or "querySelectorAll('table tbody tr" in script:
            return rows or []
        if "placeholder?.includes('订单号')" in script:
            return True
        if "textContent.trim().includes('发货')" in script:
            return True
        if "textContent.trim().includes('确认')" in script:
            return True
        return None

    page.evaluate = evaluate
    return page


class TestOrderCount(unittest.TestCase):
    @patch("dy_doudian.browser.order_client.time.sleep")
    def test_reads_order_count(self, _sleep):
        page = make_page(inner_text="共 123 单")
        self.assertEqual(read_order_count(page), 123)

    @patch("dy_doudian.browser.order_client.time.sleep")
    def test_returns_zero_when_no_match(self, _sleep):
        page = make_page(inner_text="页面加载中...")
        self.assertEqual(read_order_count(page), 0)


class TestMarkShipped(unittest.TestCase):
    @patch("dy_doudian.browser.order_client.time.sleep")
    def test_dry_run_does_not_ship(self, _sleep):
        page = make_page()
        result = mark_order_shipped(page, ["ord-1", "ord-2"], dry_run=True)
        self.assertTrue(result["ok"])
        self.assertTrue(result["dry_run"])
        self.assertNotIn("shipped", result)

    @patch("dy_doudian.browser.order_client.time.sleep")
    def test_execute_ships_after_confirm(self, _sleep):
        page = make_page()
        result = mark_order_shipped(page, ["ord-1"], dry_run=False)
        self.assertTrue(result["ok"])
        self.assertFalse(result["dry_run"])
        self.assertTrue(result["confirmed"])


class TestReportFormat(unittest.TestCase):
    def test_format_report_contains_all_sections(self):
        data = {
            "date": "2026-08-03",
            "today_orders": 42,
            "on_sale_products": 79,
            "rejected_products": 3,
            "compass": {"gmv": "1.2万", "conversion": "3.5%"},
            "errors": ["罗盘读取失败"],
        }
        text = format_report(data)
        self.assertIn("2026-08-03", text)
        self.assertIn("今日订单：42单", text)
        self.assertIn("在售商品：79个", text)
        self.assertIn("审核驳回：3个", text)
        self.assertIn("gmv: 1.2万", text)
        self.assertIn("巡检告警", text)

    def test_format_report_handles_failures(self):
        data = {"date": "2026-08-03", "today_orders": None}
        text = format_report(data)
        self.assertIn("读取失败", text)


if __name__ == "__main__":
    unittest.main()
