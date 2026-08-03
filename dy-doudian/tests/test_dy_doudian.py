"""签名正确性 + token 生命周期测试。"""

from __future__ import annotations

import json
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from dy_doudian import client as client_mod
from dy_doudian.client import DoudianClient, build_sign, canonicalize_sign_value
from dy_doudian.config import DoudianConfig
from dy_doudian.token_manager import TokenManager, refresh_access_token


class TestSigning(unittest.TestCase):
    def test_sign_deterministic(self):
        params = {"a": "1", "b": "2", "c": {"x": 1, "y": "z"}}
        s1 = build_sign("key", "secret", params)
        s2 = build_sign("key", "secret", dict(reversed(list(params.items()))))
        self.assertEqual(s1, s2)

    def test_sign_filters_empty(self):
        with_empty = build_sign("key", "secret", {"a": "1", "b": None, "c": ""})
        without = build_sign("key", "secret", {"a": "1"})
        self.assertEqual(with_empty, without)

    def test_sign_matches_reference(self):
        # 与 mcp-cn-commerce 相同的输入应产生相同签名（算法兼容验证）
        params = {"page": "0", "size": "10"}
        our = build_sign("appkey", "appsecret", params)
        # 独立手算参考值（MD5("appkey" + '{"page":"0","size":"10"}' + "appsecret")）
        ref = __import__("hashlib").md5(
            b'appkey{"page":"0","size":"10"}appsecret'
        ).hexdigest()
        self.assertEqual(our, ref)

    def test_canonicalize_value_types(self):
        self.assertEqual(canonicalize_sign_value(True), "true")
        self.assertEqual(canonicalize_sign_value(False), "false")
        self.assertEqual(canonicalize_sign_value({"b": 2, "a": 1}), '{"a":1,"b":2}')
        self.assertEqual(canonicalize_sign_value(None), "")
        self.assertEqual(canonicalize_sign_value("x"), "x")


class TestTokenManager(unittest.TestCase):
    def setUp(self):
        self.cfg = DoudianConfig(
            app_key="key",
            app_secret="secret",
            shop_id="shop",
            access_token="initial-token",
            refresh_token="refresh-token",
        )

    def test_returns_token_when_fresh(self):
        tm = TokenManager(self.cfg)
        future = time.time() + 86400
        tm._expires_at = future
        self.assertEqual(tm.get_token(), "initial-token")

    def test_refreshes_when_expiring(self):
        tm = TokenManager(self.cfg)
        tm._expires_at = time.time() + 60  # 临近过期
        with patch("dy_doudian.token_manager.refresh_access_token",
                   return_value=("new-token", "2099-01-01T00:00:00+00:00")):
            with tempfile.TemporaryDirectory() as td:
                with patch("dy_doudian.token_manager.TOKENS_PATH", Path(td) / "tokens.json"):
                    token = tm.get_token()
        self.assertEqual(token, "new-token")

    def test_raises_when_expiring_without_refresh(self):
        cfg = DoudianConfig(
            app_key="key", app_secret="secret", shop_id="shop",
            access_token="t", refresh_token="",
        )
        tm = TokenManager(cfg)
        tm._expires_at = time.time() + 60
        with self.assertRaises(Exception):
            tm.get_token()

    def test_persist_and_reload(self):
        with tempfile.TemporaryDirectory() as td:
            tokens_path = Path(td) / "tokens.json"
            with patch("dy_doudian.token_manager.TOKENS_PATH", tokens_path):
                tm = TokenManager(self.cfg)
                tm.set_token("saved-token", "2099-01-01T00:00:00+00:00", "new-refresh")
                self.assertTrue(tokens_path.exists())

                # 新实例（内存无 token）应从持久化恢复
                fresh_cfg = DoudianConfig(
                    app_key="key", app_secret="secret", shop_id="shop",
                    access_token="", refresh_token="",
                )
                tm2 = TokenManager(fresh_cfg)
                self.assertEqual(tm2.get_token(), "saved-token")


class TestClient(unittest.TestCase):
    def test_request_builds_signed_post(self):
        cfg = DoudianConfig(
            app_key="key", app_secret="secret", shop_id="shop",
            access_token="tok",
        )
        client = DoudianClient(cfg)
        captured = {}

        class FakeResp:
            status_code = 200
            def raise_for_status(self):
                pass
            def json(self):
                return {"code": 10000, "data": {"list": [{"order_id": "1"}]}}

        class FakeHTTPX:
            def post(self, url, params=None, json=None):
                captured["url"] = url
                captured["params"] = params
                captured["json"] = json
                return FakeResp()
            def close(self):
                pass

        client._client = FakeHTTPX()  # type: ignore
        result = client.get_order_list(page=0, page_size=10)
        self.assertEqual(result, [{"order_id": "1"}])
        self.assertIn("order/list", captured["url"])
        self.assertEqual(captured["params"]["app_key"], "key")
        self.assertIn("sign", captured["params"])
        # 业务参数在 body
        self.assertEqual(captured["json"], {"page": "0", "size": "10"})
        client.close()

    def test_extended_tools_use_correct_endpoints(self):
        """验证补齐的 13 个工具使用与 mcp-cn-commerce 一致的 API 端点。"""
        cfg = DoudianConfig(
            app_key="key", app_secret="secret", shop_id="shop",
            access_token="tok",
        )
        client = DoudianClient(cfg)
        calls = []

        class FakeResp:
            status_code = 200
            def raise_for_status(self):
                pass
            def json(self):
                return {"code": 10000, "data": {"list": [{"id": "1"}], "data": {"ok": 1}}}

        class FakeHTTPX:
            def post(self, url, params=None, json=None):
                calls.append((url, json))
                return FakeResp()
            def close(self):
                pass

        client._client = FakeHTTPX()  # type: ignore

        client.get_refund_list(page=0, page_size=10)
        client.get_shop_info()
        client.get_logistics_tracking("oid-1")
        client.list_logistics_companies()
        client.get_feige_messages("uid-1")
        client.get_traffic_data("2026-01-01", "2026-01-02")
        client.get_short_video_data(video_id="vid-1")
        client.list_promotions(status="1")
        client.list_coupons(status="1")
        client.get_shop_score()
        client.list_categories("0")
        client.list_brands("cat-1")
        client.list_live_rooms()
        client.get_bill_list("2026-01-01", "2026-01-31")

        expected_endpoints = [
            "refund/listSearch",
            "shop/basicInfo",
            "order/logisticsTrace",
            "order/getLogisticsCompanyList",
            "im/getMessageList",
            "shop/getTrafficData",
            "video/getVideoData",
            "promotion/list",
            "coupon/list",
            "shop/getShopScore",
            "product/getCategoryList",
            "product/getBrandList",
            "live/getLiveRoomList",
            "finance/getBillList",
        ]
        actual = [url.split("jinritemai.com/", 1)[-1] for url, _ in calls]
        self.assertEqual(actual, expected_endpoints)
        client.close()


if __name__ == "__main__":
    unittest.main()
