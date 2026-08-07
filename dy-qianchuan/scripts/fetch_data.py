#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
千川数据拉取脚本
支持三种模式:
  1. 真实API: 从千川开放平台拉取账户/素材报表数据
  2. --mock:   使用内置示例数据演示全流程
  3. --manual: 手动输入数据（无API权限时）
"""
import argparse
import json
import os
import sys
import datetime
import yaml

try:
    import requests
except ImportError:
    requests = None

BASE_URL = "https://api.oceanengine.com/open_api"

# 千川账户报表接口: 获取投放账户数据
ADVERTISER_REPORT_ENDPOINT = "/v1.0/qianchuan/report/advertiser/get/"
# 千川素材报表接口: 获取投放素材数据
MATERIAL_REPORT_ENDPOINT = "/v1.0/qianchuan/report/material/get/"
# 获取Access Token
TOKEN_ENDPOINT = "/v1.0/oauth2/access_token/"

SYS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(SYS_DIR, "config", "api_config.yaml")
DATA_DIR = os.path.join(SYS_DIR, "data", "daily")


def load_api_config():
    if not os.path.exists(CONFIG_PATH):
        return {}
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def refresh_access_token(cfg):
    """使用 app_id/app_secret 刷新 access_token"""
    api = cfg.get("api", {})
    app_id = api.get("app_id", "")
    secret = api.get("app_secret", "")
    if not app_id or not secret or requests is None:
        return api.get("access_token", "")
    try:
        resp = requests.post(
            BASE_URL + TOKEN_ENDPOINT,
            json={"app_id": int(app_id), "secret": secret, "grant_type": "auth_code", "auth_code": ""},
            timeout=15,
        )
        data = resp.json()
        token = data.get("data", {}).get("access_token", "")
        if token:
            api["access_token"] = token
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                yaml.safe_dump(cfg, f, allow_unicode=True)
        return token
    except Exception as e:
        print(f"[warn] token 刷新失败: {e}", file=sys.stderr)
        return api.get("access_token", "")


def fetch_advertiser_report(cfg, days=1):
    """拉取账户维度的消耗/ROI/成交数据"""
    api = cfg.get("api", {})
    token = api.get("access_token", "")
    advertiser_id = api.get("advertiser_id", 0)
    if not token or not advertiser_id or requests is None:
        raise RuntimeError("未配置 access_token/advertiser_id，请使用 --mock 或 --manual")

    today = datetime.date.today()
    start = today - datetime.timedelta(days=days - 1)
    end = today
    fields = [
        "stat_cost",            # 消耗
        "pay_order_amount",     # 成交金额(GMV)
        "pay_order_count",      # 成交订单数
        "pay_roi",              # ROI
        "ctr",                  # 点击率
        "cvr",                  # 转化率
        "click_cnt",            # 点击数
        "show_cnt",             # 展示数
        "convert_cnt",          # 转化数
    ]
    params = {
        "advertiser_id": advertiser_id,
        "start_date": start.strftime("%Y-%m-%d"),
        "end_date": end.strftime("%Y-%m-%d"),
        "fields": fields,
        "time_granularity": cfg.get("fetch", {}).get("time_granularity", "TIME_GRANULARITY_DAILY"),
    }
    headers = {"Access-Token": token}
    resp = requests.get(BASE_URL + ADVERTISER_REPORT_ENDPOINT, params=params, headers=headers, timeout=30)
    data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(f"账户报表API错误: {data}")
    return data.get("data", {}).get("list", [])


def fetch_material_report(cfg, days=1):
    """拉取素材维度的数据（逐条素材的消耗/CTR/ROI/转化）"""
    api = cfg.get("api", {})
    token = api.get("access_token", "")
    advertiser_id = api.get("advertiser_id", 0)
    if not token or not advertiser_id or requests is None:
        raise RuntimeError("未配置 access_token/advertiser_id，请使用 --mock 或 --manual")

    today = datetime.date.today()
    start = today - datetime.timedelta(days=days - 1)
    end = today
    fields = [
        "stat_cost",        # 消耗
        "pay_order_amount", # 成交金额
        "pay_roi",          # ROI
        "ctr",              # 点击率
        "cvr",              # 转化率
        "click_cnt",
        "show_cnt",
        "convert_cnt",
    ]
    params = {
        "advertiser_id": advertiser_id,
        "start_date": start.strftime("%Y-%m-%d"),
        "end_date": end.strftime("%Y-%m-%d"),
        "fields": fields,
        "material_type": "video",
        "page": 1,
        "page_size": 100,
    }
    headers = {"Access-Token": token}
    resp = requests.get(BASE_URL + MATERIAL_REPORT_ENDPOINT, params=params, headers=headers, timeout=30)
    data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(f"素材报表API错误: {data}")
    return data.get("data", {}).get("list", [])


def build_mock_data():
    """内置示例数据：模拟一个美妆账号的账户+素材数据（含健康/关注/衰退各状态）"""
    today = datetime.date.today()
    account = {
        "date": today.strftime("%Y-%m-%d"),
        "stat_cost": 8200,
        "pay_order_amount": 118000,
        "pay_order_count": 2360,
        "pay_roi": 14.39,
        "ctr": 3.8,
        "cvr": 4.2,
        "click_cnt": 56000,
        "show_cnt": 1473684,
        "convert_cnt": 2352,
    }
    # 素材列表: name, days_on(上线天数), stat_cost, pay_amount, ctr, cvr, roi
    raw_materials = [
        {"name": "主播展示A-美妆教程", "days_on": 12, "stat_cost": 2200, "pay_amount": 39600, "ctr": 4.5, "cvr": 5.1, "roi": 18.0},
        {"name": "主播展示B-成分解析", "days_on": 9, "stat_cost": 1800, "pay_amount": 30600, "ctr": 4.1, "cvr": 4.8, "roi": 17.0},
        {"name": "场景实拍C-日常vlog", "days_on": 6, "stat_cost": 900, "pay_amount": 7200, "ctr": 2.6, "cvr": 3.2, "roi": 8.0},
        {"name": "混剪D-爆款合集", "days_on": 5, "stat_cost": 1300, "pay_amount": 16900, "ctr": 3.4, "cvr": 4.0, "roi": 13.0},
        {"name": "教程E-新手教学", "days_on": 7, "stat_cost": 700, "pay_amount": 8400, "ctr": 3.0, "cvr": 3.6, "roi": 12.0},
        {"name": "主播展示F-测评对比", "days_on": 15, "stat_cost": 600, "pay_amount": 3600, "ctr": 1.8, "cvr": 2.1, "roi": 6.0},
        {"name": "场景实拍G-开箱", "days_on": 3, "stat_cost": 400, "pay_amount": 2800, "ctr": 2.9, "cvr": 3.4, "roi": 7.0},
        {"name": "素材H-测试中", "days_on": 1, "stat_cost": 200, "pay_amount": 3200, "ctr": 4.8, "cvr": 5.5, "roi": 16.0},
        {"name": "素材I-测试中", "days_on": 1, "stat_cost": 100, "pay_amount": 800, "ctr": 2.2, "cvr": 2.6, "roi": 8.0},
    ]
    materials = []
    for m in raw_materials:
        m["date"] = today.strftime("%Y-%m-%d")
        materials.append(m)
    return {"account": account, "materials": materials}


def manual_input():
    """手动输入模式"""
    print("=== 千川数据手动录入 ===")
    account = {
        "date": datetime.date.today().strftime("%Y-%m-%d"),
        "stat_cost": float(input("今日消耗(元): ")),
        "pay_order_amount": float(input("今日GMV/成交金额(元): ")),
        "pay_roi": float(input("今日ROI: ")),
        "ctr": float(input("今日CTR(%,如3.8): ")),
        "cvr": float(input("今日CVR(%,如4.2): ")),
    }
    materials = []
    while True:
        name = input("\n素材名称(直接回车结束): ")
        if not name:
            break
        m = {
            "name": name,
            "days_on": int(input("  上线天数: ")),
            "stat_cost": float(input("  消耗(元): ")),
            "pay_amount": float(input("  成交金额(元): ")),
            "ctr": float(input("  CTR(%,如4.5): ")),
            "cvr": float(input("  CVR(%,如5.1): ")),
            "roi": float(input("  ROI: ")),
        }
        m["date"] = account["date"]
        materials.append(m)
    return {"account": account, "materials": materials}


def save_daily(data):
    """保存每日数据快照"""
    os.makedirs(DATA_DIR, exist_ok=True)
    date_str = data["account"]["date"]
    path = os.path.join(DATA_DIR, f"raw_{date_str}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return path


def main():
    parser = argparse.ArgumentParser(description="千川数据拉取")
    parser.add_argument("--mock", action="store_true", help="使用内置示例数据")
    parser.add_argument("--manual", action="store_true", help="手动输入数据")
    parser.add_argument("--days", type=int, default=None, help="拉取最近N天（默认取配置）")
    args = parser.parse_args()

    cfg = load_api_config()
    days = args.days or cfg.get("fetch", {}).get("days", 1)

    if args.mock:
        data = build_mock_data()
        print("[mock] 使用内置示例数据")
    elif args.manual:
        data = manual_input()
        print("[manual] 手动录入完成")
    else:
        token = refresh_access_token(cfg)
        if not token or not cfg.get("api", {}).get("advertiser_id"):
            print("[warn] 未配置API凭证，回退到 --mock 模式演示", file=sys.stderr)
            data = build_mock_data()
            print("[mock] 使用内置示例数据")
        else:
            print("[api] 拉取千川开放平台数据...")
            acct = fetch_advertiser_report(cfg, days)
            mats = fetch_material_report(cfg, days)
            if not acct:
                raise RuntimeError("账户报表无数据")
            a = acct[0]
            data = {
                "account": {
                    "date": datetime.date.today().strftime("%Y-%m-%d"),
                    "stat_cost": a.get("stat_cost", 0),
                    "pay_order_amount": a.get("pay_order_amount", 0),
                    "pay_order_count": a.get("pay_order_count", 0),
                    "pay_roi": a.get("pay_roi", 0),
                    "ctr": a.get("ctr", 0),
                    "cvr": a.get("cvr", 0),
                },
                "materials": [
                    {
                        "name": f"素材{m.get('material_id', i)}",
                        "days_on": 1,
                        "stat_cost": m.get("stat_cost", 0),
                        "pay_amount": m.get("pay_order_amount", 0),
                        "ctr": m.get("ctr", 0),
                        "cvr": m.get("cvr", 0),
                        "roi": m.get("pay_roi", 0),
                    }
                    for i, m in enumerate(mats)
                ],
            }

    path = save_daily(data)
    print(f"数据已保存: {path}")
    print(f"账户: 消耗={data['account']['stat_cost']} GMV={data['account']['pay_order_amount']} "
          f"ROI={data['account']['pay_roi']} CTR={data['account']['ctr']}%")
    print(f"素材数: {len(data['materials'])}")


if __name__ == "__main__":
    main()
