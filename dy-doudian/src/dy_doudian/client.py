"""抖店开放平台 API 客户端：MD5 签名 + 请求 + TokenManager 集成。

签名算法与 mcp-cn-commerce 保持一致（经官方验证）：
1. 过滤空值业务参数
2. 按 key 排序序列化为紧凑 JSON
3. ``MD5(app_key + param_json + app_secret)``
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from typing import Any

import httpx

from dy_doudian.config import DoudianConfig
from dy_doudian.token_manager import TokenManager

logger = logging.getLogger(__name__)

BASE_URL = "https://openapi-fxg.jinritemai.com/"
SUCCESS_CODE = 10000


class DoudianAPIError(RuntimeError):
    """API 返回非成功码。"""

    def __init__(self, code: int, msg: str, sub_code: str = "", sub_msg: str = ""):
        super().__init__(f"抖店 API 错误 {code}: {msg} (sub: {sub_code} {sub_msg})".strip())
        self.code = code
        self.msg = msg
        self.sub_code = sub_code
        self.sub_msg = sub_msg


def canonicalize_sign_value(value: Any) -> str:
    """确定性序列化，保证签名可复现（与 mcp-cn-commerce 一致）。"""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return str(value)


def build_sign(app_key: str, app_secret: str, params: dict[str, Any]) -> str:
    """计算抖店 MD5 签名。"""
    clean = {
        k: canonicalize_sign_value(v)
        for k, v in params.items()
        if v is not None and v != ""
    }
    sorted_params = dict(sorted(clean.items()))
    param_json = json.dumps(sorted_params, separators=(",", ":"), ensure_ascii=False)
    sign_str = f"{app_key}{param_json}{app_secret}"
    return hashlib.md5(sign_str.encode()).hexdigest()


class DoudianClient:
    """抖店开放平台客户端。"""

    def __init__(self, cfg: DoudianConfig, token_manager: TokenManager | None = None):
        self.cfg = cfg
        self.token_manager = token_manager or TokenManager(cfg)
        self._client = httpx.Client(timeout=30)

    def close(self) -> None:
        self._client.close()

    def _request(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """发起签名请求。access_token 经 TokenManager 自动续期。"""
        params = params or {}
        token = self.token_manager.get_token()

        url = f"{BASE_URL.rstrip('/')}/{method.lstrip('/')}"
        common = {
            "app_key": self.cfg.app_key,
            "timestamp": str(int(time.time())),
            "v": "2",
            "sign_method": "md5",
            "access_token": token,
            "sign": build_sign(self.cfg.app_key, self.cfg.app_secret, params),
        }

        resp = self._client.post(url, params=common, json=params)
        resp.raise_for_status()
        try:
            result = resp.json()
        except json.JSONDecodeError:
            raise DoudianAPIError(
                -1, f"无效 JSON 响应 (HTTP {resp.status_code}): {resp.text[:300]}"
            )

        code = result.get("code", SUCCESS_CODE)
        if code != SUCCESS_CODE:
            raise DoudianAPIError(
                code=code,
                msg=result.get("msg", "unknown error"),
                sub_code=str(result.get("sub_code", "")),
                sub_msg=str(result.get("sub_msg", "")),
            )
        return result.get("data", result)

    # ── 订单 ─────────────────────────────────────────────

    def get_order_list(
        self,
        start_time: str = "",
        end_time: str = "",
        order_status: str = "",
        page: int = 0,
        page_size: int = 10,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"page": str(page), "size": str(page_size)}
        if start_time:
            params["start_time"] = start_time
        if end_time:
            params["end_time"] = end_time
        if order_status:
            params["order_status"] = str(order_status)
        data = self._request("order/list", params)
        raw = data.get("list", data.get("data", []))
        return raw if isinstance(raw, list) else []

    def get_order_detail(self, order_id: str) -> dict[str, Any]:
        data = self._request("order/detail", {"order_id": str(order_id)})
        return data.get("order", data)

    # ── 商品 ─────────────────────────────────────────────

    def get_product_list(self, page: int = 0, page_size: int = 10) -> list[dict[str, Any]]:
        data = self._request("product/list", {"page": str(page), "size": str(page_size)})
        raw = data.get("list", data.get("data", []))
        return raw if isinstance(raw, list) else []

    def get_product_detail(self, product_id: str) -> dict[str, Any]:
        data = self._request("product/detail", {"product_id": str(product_id)})
        return data.get("data", data)

    # ── 评价 ─────────────────────────────────────────────

    def get_review_list(
        self, page: int = 0, page_size: int = 10, product_id: str = ""
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"page": str(page), "size": str(page_size)}
        if product_id:
            params["product_id"] = str(product_id)
        data = self._request("comment/list", params)
        raw = data.get("list", data.get("data", []))
        return raw if isinstance(raw, list) else []

    # ── 直播 ─────────────────────────────────────────────

    def get_live_data(
        self, room_id: str = "", start_time: str = "", end_time: str = ""
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"room_id": str(room_id)}
        if start_time:
            params["start_time"] = start_time
        if end_time:
            params["end_time"] = end_time
        return self._request("live/getLiveRoomData", params)

    def list_live_rooms(self, page: int = 0, page_size: int = 10) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"page": str(page), "size": str(page_size)}
        data = self._request("live/getLiveRoomList", params)
        raw = data.get("list", data.get("data", []))
        return raw if isinstance(raw, list) else []

    # ── 账单 ─────────────────────────────────────────────

    def get_bill_list(
        self, start_date: str = "", end_date: str = "", page: int = 0, page_size: int = 20
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"page": str(page), "size": str(page_size)}
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        data = self._request("finance/getBillList", params)
        raw = data.get("list", data.get("data", []))
        return raw if isinstance(raw, list) else []

    # ── 售后 / 退款 ──────────────────────────────────────

    def get_refund_list(
        self,
        start_time: str = "",
        end_time: str = "",
        refund_type: str = "",
        page: int = 0,
        page_size: int = 10,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"page": str(page), "size": str(page_size)}
        if start_time:
            params["start_time"] = start_time
        if end_time:
            params["end_time"] = end_time
        if refund_type:
            params["type"] = refund_type
        data = self._request("refund/listSearch", params)
        raw = data.get("list", data.get("data", []))
        return raw if isinstance(raw, list) else []

    # ── 店铺 ─────────────────────────────────────────────

    def get_shop_info(self) -> dict[str, Any]:
        data = self._request("shop/basicInfo", {})
        return data.get("shop", data.get("shop_info", data))

    def get_shop_score(self) -> dict[str, Any]:
        data = self._request("shop/getShopScore", {})
        return data.get("data", data)

    # ── 物流 ─────────────────────────────────────────────

    def get_logistics_tracking(self, order_id: str) -> dict[str, Any]:
        data = self._request("order/logisticsTrace", {"order_id": str(order_id)})
        return data.get("data", data)

    def list_logistics_companies(self) -> list[dict[str, Any]]:
        data = self._request("order/getLogisticsCompanyList", {})
        raw = data.get("list", data.get("data", []))
        return raw if isinstance(raw, list) else []

    # ── 飞鸽客服 ─────────────────────────────────────────

    def get_feige_messages(
        self, user_id: str, start_time: str = "", end_time: str = ""
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"user_id": str(user_id)}
        if start_time:
            params["start_time"] = start_time
        if end_time:
            params["end_time"] = end_time
        data = self._request("im/getMessageList", params)
        raw = data.get("list", data.get("data", []))
        return raw if isinstance(raw, list) else []

    # ── 流量 / 短视频数据 ────────────────────────────────

    def get_traffic_data(
        self, start_date: str = "", end_date: str = ""
    ) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        return self._request("shop/getTrafficData", params)

    def get_short_video_data(
        self, video_id: str = "", start_date: str = "", end_date: str = ""
    ) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if video_id:
            params["video_id"] = str(video_id)
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        return self._request("video/getVideoData", params)

    # ── 营销 / 优惠券 ────────────────────────────────────

    def list_promotions(self, status: str = "", page: int = 0, page_size: int = 10) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"page": str(page), "size": str(page_size)}
        if status:
            params["status"] = str(status)
        data = self._request("promotion/list", params)
        raw = data.get("list", data.get("data", []))
        return raw if isinstance(raw, list) else []

    def list_coupons(self, status: str = "", page: int = 0, page_size: int = 10) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"page": str(page), "size": str(page_size)}
        if status:
            params["status"] = str(status)
        data = self._request("coupon/list", params)
        raw = data.get("list", data.get("data", []))
        return raw if isinstance(raw, list) else []

    # ── 类目 / 品牌 ──────────────────────────────────────

    def list_categories(self, parent_id: str = "") -> list[dict[str, Any]]:
        params: dict[str, Any] = {}
        if parent_id:
            params["parent_id"] = str(parent_id)
        data = self._request("product/getCategoryList", params)
        raw = data.get("list", data.get("data", []))
        return raw if isinstance(raw, list) else []

    def list_brands(self, category_id: str = "") -> list[dict[str, Any]]:
        params: dict[str, Any] = {}
        if category_id:
            params["category_id"] = str(category_id)
        data = self._request("product/getBrandList", params)
        raw = data.get("list", data.get("data", []))
        return raw if isinstance(raw, list) else []
