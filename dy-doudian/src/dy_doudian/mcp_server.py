"""dy-doudian MCP Server：把抖店经营数据暴露为 MCP 只读工具。

运行方式：`uvx dy-doudian-mcp`（或 `python -m dy_doudian.mcp_server`）
配置：环境变量或 ~/.dy-doudian/.env（见 config.py）
"""

from __future__ import annotations

import asyncio
import sys
from typing import Any

from mcp.server.fastmcp import FastMCP

from dy_doudian.client import DoudianClient
from dy_doudian.config import ConfigError, ensure_config

server = FastMCP("dy-doudian")

_client: DoudianClient | None = None


def _get_client() -> DoudianClient:
    global _client
    if _client is None:
        try:
            cfg = ensure_config()
        except ConfigError as exc:
            raise ConfigError(
                f"抖店凭据未配置: {exc}。请设置 DOUDIAN_APP_KEY/APP_SECRET/SHOP_ID/ACCESS_TOKEN"
                " 或填写 ~/.dy-doudian/.env"
            ) from exc
        _client = DoudianClient(cfg)
    return _client


@server.tool()
async def get_order_list(
    start_time: str = "",
    end_time: str = "",
    order_status: str = "",
    page: int = 0,
    page_size: int = 10,
) -> dict[str, Any]:
    """获取抖店订单列表。start_time/end_time 格式 'YYYY-MM-DD HH:MM:SS'；
    order_status: 1待确认,2备货中,3已发货,4已收货,5已完成,101已取消。"""
    client = _get_client()
    orders = client.get_order_list(start_time, end_time, order_status, page, page_size)
    return {"count": len(orders), "orders": orders}


@server.tool()
async def get_order_detail(order_id: str) -> dict[str, Any]:
    """获取单个订单详情。"""
    client = _get_client()
    return client.get_order_detail(order_id)


@server.tool()
async def get_product_list(page: int = 0, page_size: int = 10) -> dict[str, Any]:
    """获取店铺商品列表。"""
    client = _get_client()
    products = client.get_product_list(page, page_size)
    return {"count": len(products), "products": products}


@server.tool()
async def get_review_list(page: int = 0, page_size: int = 10, product_id: str = "") -> dict[str, Any]:
    """获取商品评价列表（只读）。"""
    client = _get_client()
    reviews = client.get_review_list(page, page_size, product_id)
    return {"count": len(reviews), "reviews": reviews}


@server.tool()
async def get_live_data(room_id: str = "", start_time: str = "", end_time: str = "") -> dict[str, Any]:
    """获取直播间数据。room_id 必填；start_time/end_time 格式 'YYYY-MM-DD HH:MM:SS'。"""
    client = _get_client()
    return client.get_live_data(room_id, start_time, end_time)


@server.tool()
async def list_live_rooms(page: int = 0, page_size: int = 10) -> dict[str, Any]:
    """获取直播间列表。"""
    client = _get_client()
    rooms = client.list_live_rooms(page, page_size)
    return {"count": len(rooms), "rooms": rooms}


@server.tool()
async def get_bill_list(start_date: str = "", end_date: str = "", page: int = 0) -> dict[str, Any]:
    """获取账单明细。start_date/end_date 格式 'YYYY-MM-DD'。"""
    client = _get_client()
    bills = client.get_bill_list(start_date, end_date, page)
    return {"count": len(bills), "bills": bills}


@server.tool()
async def get_refund_list(
    start_time: str = "", end_time: str = "", refund_type: str = "", page: int = 0, page_size: int = 10
) -> dict[str, Any]:
    """获取售后/退款单列表。refund_type: 0仅退款,1退货退款,2换货,3维修。"""
    client = _get_client()
    refunds = client.get_refund_list(start_time, end_time, refund_type, page, page_size)
    return {"count": len(refunds), "refunds": refunds}


@server.tool()
async def get_shop_info() -> dict[str, Any]:
    """获取店铺基本信息（名称/Logo/评分/状态）。"""
    client = _get_client()
    return client.get_shop_info()


@server.tool()
async def get_shop_score() -> dict[str, Any]:
    """获取店铺评分。"""
    client = _get_client()
    return client.get_shop_score()


@server.tool()
async def get_logistics_tracking(order_id: str) -> dict[str, Any]:
    """获取订单物流轨迹。"""
    client = _get_client()
    return client.get_logistics_tracking(order_id)


@server.tool()
async def list_logistics_companies() -> dict[str, Any]:
    """获取物流公司列表。"""
    client = _get_client()
    companies = client.list_logistics_companies()
    return {"count": len(companies), "companies": companies}


@server.tool()
async def get_feige_messages(user_id: str, start_time: str = "", end_time: str = "") -> dict[str, Any]:
    """获取飞鸽客服会话消息。user_id 必填。"""
    client = _get_client()
    messages = client.get_feige_messages(user_id, start_time, end_time)
    return {"count": len(messages), "messages": messages}


@server.tool()
async def get_traffic_data(start_date: str = "", end_date: str = "") -> dict[str, Any]:
    """获取店铺流量数据。日期格式 'YYYY-MM-DD'。"""
    client = _get_client()
    return client.get_traffic_data(start_date, end_date)


@server.tool()
async def get_short_video_data(video_id: str = "", start_date: str = "", end_date: str = "") -> dict[str, Any]:
    """获取短视频数据。"""
    client = _get_client()
    return client.get_short_video_data(video_id, start_date, end_date)


@server.tool()
async def list_promotions(status: str = "", page: int = 0, page_size: int = 10) -> dict[str, Any]:
    """获取营销活动列表。"""
    client = _get_client()
    promotions = client.list_promotions(status, page, page_size)
    return {"count": len(promotions), "promotions": promotions}


@server.tool()
async def list_coupons(status: str = "", page: int = 0, page_size: int = 10) -> dict[str, Any]:
    """获取优惠券列表。"""
    client = _get_client()
    coupons = client.list_coupons(status, page, page_size)
    return {"count": len(coupons), "coupons": coupons}


@server.tool()
async def list_categories(parent_id: str = "") -> dict[str, Any]:
    """获取商品类目列表。"""
    client = _get_client()
    categories = client.list_categories(parent_id)
    return {"count": len(categories), "categories": categories}


@server.tool()
async def list_brands(category_id: str = "") -> dict[str, Any]:
    """获取商品品牌列表。"""
    client = _get_client()
    brands = client.list_brands(category_id)
    return {"count": len(brands), "brands": brands}


def main() -> None:
    """MCP server 入口（stdio）。"""
    server.run()


if __name__ == "__main__":
    main()
