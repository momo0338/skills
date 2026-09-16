#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""wx_stats.py —— 微信公众号「数据统计 / 数据分析」全能力 CLI

覆盖官方 datacube 全部 21 个接口（用户 2 / 图文 10 / 消息 7 / 接口 2），
并保留广告分析（Ad_Analysis）的入口指引。

  用户数据
    getusersummary          用户增减数据           跨度 ≤7 天
    getusercumulate         累计用户数据           跨度 ≤7 天
  图文数据（★=官方已停止维护，建议迁移到右侧新接口）
    ★getarticlesummary     图文群发每日数据       1 天
    ★getuserread           图文阅读概况数据       1 天
    ★getuserreadhour       图文阅读分时数据       1 天
    ★getusershare          图文转发概况数据       1 天
    ★getusersharehour      图文转发分时数据       1 天
    ★getarticletotal       图文群发总数据         1 天（统计发表后最多 7 天）
    getarticleread          发表内容每日阅读       1 天
    getarticleshare         发表内容每日分享       1 天
    getbizsummary           发表内容概况总数据     ≤30 天
    getarticletotaldetail   发表内容发表详细数据   1 天（每篇统计发表后 30 天）
  消息数据
    getupstreammsg          消息发送概况           <7 天
    getupstreammsgweek      消息发送周数据         必须同一天
    getupstreammsgmonth     消息发送月数据         必须同一天
    getupstreammsghour      消息发送分时           1 天
    getupstreammsgdist      消息发送分布           ≤15 天
    getupstreammsgdistweek  消息发送分布周数据     ≤15 天
    getupstreammsgdistmonth 消息发送分布月数据     ≤15 天
  接口数据
    getinterfacesummary     被动回复概要           ≤30 天
    getinterfacesummaryhour 被动回复分布           1 天

关键使用注意（来自官方文档）：
  1) 数据只存 2014-12-01 之后；每天 8 点后查询前一天数据才准确
  2) 阅读量总和（中间页阅读+原文页阅读+分享+收藏）< 3 的图文不会被统计
  3) 「发表内容」新接口族（getarticleread/getarticleshare/getbizsummary/
     getarticletotaldetail）数据起始 2025-11-01，更早日期查不到
  4) 数据可能延迟，返回体 is_delay=false 表示已是最新
  5) 用户分析属「用户管理」权限、图文分析属「群发与通知」权限、
     消息分析属「消息管理」权限、接口分析属对应权限集
     —— 未开通「认证」的个人订阅号调用会返回 48001

用法示例：
  python3 wx_stats.py list                            # 列出全部接口与跨度
  python3 wx_stats.py fetch getusersummary --days 7   # 拉最近 7 天用户增减
  python3 wx_stats.py fetch getbizsummary --begin 2026-09-01 --end 2026-09-15
  python3 wx_stats.py fetch getuserread --date 2026-09-15 --csv /tmp/read.csv
  python3 wx_stats.py users --days 30                 # 用户增减+累计（自动分段）
  python3 wx_stats.py daily                           # 昨日核心指标一览
  python3 wx_stats.py selftest                        # 逐接口权限自检
  python3 wx_stats.py webplan                         # 接口无权限时走后台网页
"""
import argparse
import datetime as dt
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wx_common import (  # noqa: E402
    WxApiError, api_call, die, dump_json, human, load_wx_creds, write_csv,
    set_profile,
)

DATA_EPOCH = dt.date(2014, 12, 1)       # 官方数据起始
NEW_FAMILY_EPOCH = dt.date(2025, 11, 1)  # 「发表内容」新接口族数据起始

# 值 → 中文解码表
# 注意：user_source 这一类字段在不同接口语义不同，必须按接口区分：
#   - getusersummary     的 user_source = 关注渠道
#   - getuserread/hour   的 user_source = 阅读来源
USER_SOURCE = {
    0: "其他合计", 1: "公众号搜索", 17: "名片分享", 30: "扫描二维码",
    57: "文章内账号名称", 100: "微信广告", 161: "他人转载",
    149: "小程序关注", 200: "视频号", 201: "直播",
}
READ_SOURCE = {
    99999999: "全部", 0: "会话", 1: "好友", 2: "朋友圈",
    4: "历史消息页", 5: "其他", 6: "看一看", 7: "搜一搜",
}
DECODERS = {
    "msg_type": {1: "文字", 2: "图片", 3: "语音", 4: "视频", 6: "第三方应用消息"},
    "share_scene": {1: "好友转发", 2: "朋友圈", 255: "其他"},
    "count_interval": {0: "0 次", 1: "1-5 次", 2: "6-10 次", 3: "10 次以上"},
    "publish_type": {0: "已通知", 1: "未开启通知"},
}

# 接口注册表：span=0 表示「begin_date 必须等于 end_date」
APIS = {
    # ---------------- 用户数据 ----------------
    "getusersummary": dict(
        path="/datacube/getusersummary", group="用户数据", desc="获取用户增减数据",
        span=7, fields=[("ref_date", "日期"), ("user_source", "关注渠道"),
                        ("new_user", "新增关注"), ("cancel_user", "取消关注")]),
    "getusercumulate": dict(
        path="/datacube/getusercumulate", group="用户数据", desc="获取累计用户数据",
        span=7, fields=[("ref_date", "日期"), ("cumulate_user", "累计总用户")]),

    # ---------------- 图文数据 ----------------
    "getarticlesummary": dict(
        path="/datacube/getarticlesummary", group="图文数据", desc="获取图文群发每日数据",
        span=1, deprecated="getarticleread / getarticleshare / getbizsummary / getarticletotaldetail",
        fields=[("ref_date", "日期"), ("msgid", "消息ID"), ("title", "标题"),
                ("int_page_read_user", "图文页阅读人数"), ("int_page_read_count", "图文页阅读次数"),
                ("ori_page_read_user", "原文页阅读人数"), ("ori_page_read_count", "原文页阅读次数"),
                ("share_user", "分享人数"), ("share_count", "分享次数"),
                ("add_to_fav_user", "收藏人数"), ("add_to_fav_count", "收藏次数")]),
    "getuserread": dict(
        path="/datacube/getuserread", group="图文数据", desc="获取图文阅读概况数据",
        span=1, deprecated="getarticleread",
        fields=[("ref_date", "日期"), ("user_source", "阅读来源"),
                ("int_page_read_user", "图文页阅读人数"), ("int_page_read_count", "图文页阅读次数"),
                ("ori_page_read_user", "原文页阅读人数"), ("ori_page_read_count", "原文页阅读次数"),
                ("share_user", "分享人数"), ("share_count", "分享次数"),
                ("add_to_fav_user", "收藏人数"), ("add_to_fav_count", "收藏次数")]),
    "getuserreadhour": dict(
        path="/datacube/getuserreadhour", group="图文数据", desc="获取图文阅读分时数据",
        span=1, deprecated="getarticleread",
        fields=[("ref_date", "日期"), ("ref_hour", "小时"), ("user_source", "阅读来源"),
                ("int_page_read_user", "图文页阅读人数"), ("int_page_read_count", "图文页阅读次数"),
                ("share_user", "分享人数"), ("share_count", "分享次数")]),
    "getusershare": dict(
        path="/datacube/getusershare", group="图文数据", desc="获取图文转发概况数据",
        span=1, deprecated="getarticleshare",
        fields=[("ref_date", "日期"), ("share_scene", "分享场景"),
                ("share_user", "分享人数"), ("share_count", "分享次数")]),
    "getusersharehour": dict(
        path="/datacube/getusersharehour", group="图文数据", desc="获取图文转发分时数据",
        span=1, deprecated="getarticleshare",
        fields=[("ref_date", "日期"), ("ref_hour", "小时"), ("share_scene", "分享场景"),
                ("share_user", "分享人数"), ("share_count", "分享次数")]),
    "getarticletotal": dict(
        path="/datacube/getarticletotal", group="图文数据", desc="获取图文群发总数据",
        span=1, deprecated="getarticletotaldetail",
        fields=[("ref_date", "群发日期"), ("msgid", "消息ID"), ("title", "标题")]),
    "getarticleread": dict(
        path="/datacube/getarticleread", group="图文数据", desc="获取发表内容每日阅读数据",
        span=1, new=True,
        fields=[("ref_date", "日期"), ("msgid", "消息ID"), ("read_user", "阅读人数")]),
    "getarticleshare": dict(
        path="/datacube/getarticleshare", group="图文数据", desc="获取发表内容每日分享数据",
        span=1, new=True,
        fields=[("ref_date", "日期"), ("msgid", "消息ID"), ("share_user", "分享人数")]),
    "getbizsummary": dict(
        path="/datacube/getbizsummary", group="图文数据", desc="获取发表内容概况总数据",
        span=30, new=True,
        fields=[("ref_date", "日期"), ("read_user", "阅读人数"), ("share_user", "分享人数"),
                ("zaikan_user", "爱心赞人数"), ("like_user", "拇指赞人数"),
                ("comment_count", "留言条数"), ("collection_user", "微信收藏人数"),
                ("redirect_ori_page_user", "跳转原文人数"), ("send_page_count", "发布篇数")]),
    "getarticletotaldetail": dict(
        path="/datacube/getarticletotaldetail", group="图文数据", desc="获取发表内容发表详细数据",
        span=1, new=True,
        fields=[("ref_date", "发表日期"), ("msgid", "消息ID"), ("title", "标题"),
                ("content_url", "文章链接"), ("stat_date", "统计日期"),
                ("read_user", "阅读人数"), ("share_user", "分享人数"),
                ("zaikan_user", "爱心赞"), ("like_user", "拇指赞"),
                ("comment_count", "留言数"), ("collection_user", "收藏人数"),
                ("praise_money", "赞赏金额(分)"), ("read_subscribe_user", "阅读后关注"),
                ("read_delivery_rate", "阅读送达率"), ("read_finish_rate", "阅读完成率"),
                ("read_avg_activetime", "平均阅读时长(min)")]),

    # ---------------- 消息数据 ----------------
    "getupstreammsg": dict(
        path="/datacube/getupstreammsg", group="消息数据", desc="获取消息发送概况数据",
        span=7, fields=[("ref_date", "日期"), ("msg_type", "消息类型"),
                        ("msg_user", "发送用户数"), ("msg_count", "消息总数")]),
    "getupstreammsgweek": dict(
        path="/datacube/getupstreammsgweek", group="消息数据", desc="获取消息发送周数据",
        span=0, fields=[("ref_date", "周起始日"), ("msg_type", "消息类型"),
                        ("msg_user", "发送用户数"), ("msg_count", "消息总数")]),
    "getupstreammsgmonth": dict(
        path="/datacube/getupstreammsgmonth", group="消息数据", desc="获取消息发送月数据",
        span=0, fields=[("ref_date", "月起始日"), ("msg_type", "消息类型"),
                        ("msg_user", "发送用户数"), ("msg_count", "消息总数")]),
    "getupstreammsghour": dict(
        path="/datacube/getupstreammsghour", group="消息数据", desc="获取消息发送分时数据",
        span=1, fields=[("ref_date", "日期"), ("ref_hour", "小时"), ("msg_type", "消息类型"),
                        ("msg_user", "发送用户数"), ("msg_count", "消息总数")]),
    "getupstreammsgdist": dict(
        path="/datacube/getupstreammsgdist", group="消息数据", desc="获取消息发送分布数据",
        span=15, fields=[("ref_date", "日期"), ("count_interval", "发送量区间"),
                         ("msg_user", "发送用户数")]),
    "getupstreammsgdistweek": dict(
        path="/datacube/getupstreammsgdistweek", group="消息数据", desc="获取消息发送分布周数据",
        span=15, fields=[("ref_date", "周起始日"), ("count_interval", "发送量区间"),
                         ("msg_user", "发送用户数")]),
    "getupstreammsgdistmonth": dict(
        path="/datacube/getupstreammsgdistmonth", group="消息数据", desc="获取消息发送分布月数据",
        span=15, fields=[("ref_date", "月起始日"), ("count_interval", "发送量区间"),
                         ("msg_user", "发送用户数")]),

    # ---------------- 接口数据 ----------------
    "getinterfacesummary": dict(
        path="/datacube/getinterfacesummary", group="接口数据", desc="获取被动回复概要数据",
        span=30, fields=[("ref_date", "日期"), ("callback_count", "被动回复次数"),
                         ("fail_count", "失败次数"), ("total_time_cost", "总耗时"),
                         ("max_time_cost", "最大耗时")]),
    "getinterfacesummaryhour": dict(
        path="/datacube/getinterfacesummaryhour", group="接口数据", desc="获取被动回复分布数据",
        span=1, fields=[("ref_date", "日期"), ("ref_hour", "小时"),
                        ("callback_count", "被动回复次数"), ("fail_count", "失败次数"),
                        ("total_time_cost", "总耗时"), ("max_time_cost", "最大耗时")]),
}

GROUP_ORDER = ["用户数据", "图文数据", "消息数据", "接口数据"]


# --------------------------------------------------------------------------- #
# 日期与分段
# --------------------------------------------------------------------------- #
def parse_date(s):
    try:
        return dt.datetime.strptime(s.strip(), "%Y-%m-%d").date()
    except ValueError:
        die(f"[FAIL] 日期需为 YYYY-MM-DD 格式，收到: {s}")


def default_range(args):
    """默认查询「昨天」（官方：每天 8 点后才可查前一天数据）。"""
    if getattr(args, "date", ""):
        d = parse_date(args.date)
        return d, d
    end = parse_date(args.end) if args.end else (dt.date.today() - dt.timedelta(days=1))
    begin = parse_date(args.begin) if args.begin else end
    if getattr(args, "days", 0):
        begin = end - dt.timedelta(days=args.days - 1)
    if begin > end:
        die(f"[FAIL] begin({begin}) 晚于 end({end})")
    return begin, end


def segments(begin, end, span):
    """把 [begin, end] 按接口跨度上限切段；span<=0 表示必须逐日查询。"""
    step = 1 if span <= 0 else span
    cur = begin
    while cur <= end:
        seg_end = min(cur + dt.timedelta(days=step - 1), end)
        yield cur, seg_end
        cur = seg_end + dt.timedelta(days=1)


def fetch_one(api_name, begin, end, span_override=None, quiet=False):
    """按段拉取一个接口，返回 list（已合并）。遇跨度超限自动减半降级重试。"""
    apis = APIS[api_name]
    span = span_override or apis["span"]
    if span <= 0:
        span = 1
    rows, cur_span = [], span
    pending = list(segments(begin, end, cur_span))
    idx = 0
    while idx < len(pending):
        b, e = pending[idx]
        try:
            r = api_call(apis["path"], {"begin_date": str(b), "end_date": str(e)})
        except WxApiError as ex:
            if ex.errcode in (61500, 61501) and cur_span > 1:
                new_span = max(1, cur_span // 2)
                if not quiet:
                    print(f"  [降级] {b}~{e} 报 {ex.errcode}（跨度超限），"
                          f"分段从 {cur_span} 天收窄到 {new_span} 天重试")
                cur_span = new_span
                pending = list(segments(begin, end, cur_span))
                idx = 0
                rows = []
                continue
            raise
        batch = r.get("list") or []
        rows.extend(batch)
        idx += 1
    return rows


# --------------------------------------------------------------------------- #
# 展示
# --------------------------------------------------------------------------- #
def decode(field, val, api=None):
    """把枚举值翻成中文；浮点保留 4 位有效小数。"""
    if field == "user_source":
        tbl = USER_SOURCE if api == "getusersummary" else READ_SOURCE
        try:
            return tbl.get(int(val), val)
        except (TypeError, ValueError):
            return val
    tbl = DECODERS.get(field)
    if tbl:
        try:
            return tbl.get(int(val), val)
        except (TypeError, ValueError):
            return val
    if isinstance(val, float):
        return f"{val:.4f}".rstrip("0").rstrip(".")
    return val


def unnest(row):
    """把接口返回里的嵌套 detail / detail_list 拍平到主行，便于统一按 fields 展示。

    - detail:       dict  → 键值提升到主行（getbizsummary / getarticleread / getarticleshare）
    - detail_list:  list  → 取第一项提升（getarticletotaldetail，接口按"每天一行"返回）
    """
    d = dict(row or {})
    v = d.pop("detail", None)
    if isinstance(v, dict):
        d.update(v)
    elif isinstance(v, list):
        d["detail"] = json.dumps(v, ensure_ascii=False)
    dl = d.pop("detail_list", None)
    if isinstance(dl, list) and dl and isinstance(dl[0], dict):
        d.update(dl[0])
    return d


def print_rows(api_name, rows, limit=200):
    """按注册表里的 fields 逐列对齐输出（自动中文解码 + 嵌套拍平）。"""
    fields = APIS[api_name]["fields"]
    if not rows:
        print("  （无数据：可能该日无统计（阅读量过低/无内容变化），或数据尚未生成）")
        return
    view = [unnest(r) for r in rows]
    cells = [[str(decode(k, r.get(k, ""), api_name)) for k, _ in fields] for r in view[:limit]]
    widths = [max(len(fields[i][1]), *(len(row[i]) for row in cells)) for i in range(len(fields))]
    print("  " + "  ".join(fields[i][1].ljust(widths[i]) for i in range(len(fields))))
    print("  " + "  ".join("-" * w for w in widths))
    for row in cells:
        print("  " + "  ".join(row[i].ljust(widths[i]) for i in range(len(fields))))
    if len(rows) > limit:
        print(f"  ... 共 {len(rows)} 行，仅显示前 {limit} 行（完整数据见 --json/--csv）")


# --------------------------------------------------------------------------- #
# 子命令
# --------------------------------------------------------------------------- #
def cmd_list(args):
    print("=" * 96)
    print("微信公众号数据统计（datacube）接口总览")
    print("=" * 96)
    for g in GROUP_ORDER:
        names = [n for n, v in APIS.items() if v["group"] == g]
        if not names:
            continue
        print(f"\n【{g}】共 {len(names)} 个")
        for n in names:
            v = APIS[n]
            span_txt = "必须同一天" if v["span"] <= 0 else (
                f"跨度≤{v['span']}天" if v["span"] > 1 else "仅支持 1 天")
            tag = ""
            if v.get("new"):
                tag = "  [新接口族·数据起 2025-11-01]"
            if v.get("deprecated"):
                tag = f"  [官方已停止维护 → 建议改用 {v['deprecated']}]"
            print(f"  {n:<24} {v['path']:<38} {span_txt}{tag}")
            print(f"  {'':<24} {v['desc']}")
    print("\n【广告分析】官方独立说明页："
          "https://developers.weixin.qq.com/doc/subscription/guide/product/analysis_data/ad/Ad_Analysis")
    print("=" * 96)
    print("通用注意事项：")
    print("  1) 数据仅存 2014-12-01 之后；每天 8 点后查前一天数据才准")
    print("  2) 阅读量总和 < 3 的图文不入统计（数据可能为空是正常的）")
    print("  3) 本脚本已按各接口跨度上限自动分段，并对 61501/61500 自动降级重试")
    return None


def cmd_fetch(args):
    api_name = args.api
    if api_name not in APIS:
        die(f"[FAIL] 未知接口 {api_name}；可用接口见 `python3 wx_stats.py list`")
    apis = APIS[api_name]
    begin, end = default_range(args)

    if begin < DATA_EPOCH:
        print(f"  [WARN] 起始日期早于官方数据起点 {DATA_EPOCH}，结果可能为空或不可信")
    if apis.get("new") and begin < NEW_FAMILY_EPOCH:
        print(f"  [WARN] {api_name} 数据起始于 {NEW_FAMILY_EPOCH}，更早日期无效")

    print(f"[fetch] {api_name} —— {apis['desc']}")
    print(f"[fetch] 区间 {begin} ~ {end}（{(end - begin).days + 1} 天，"
          f"接口上限 {'同一天' if apis['span'] <= 0 else str(apis['span']) + ' 天'}）")
    if apis.get("deprecated"):
        print(f"  [注意] 官方已停止维护，建议改用：{apis['deprecated']}")

    rows = fetch_one(api_name, begin, end, span_override=args.span)
    print(f"[fetch] 共取回 {len(rows)} 行")
    print_rows(api_name, rows, limit=args.limit)

    if args.json:
        dump_json({"api": api_name, "begin": str(begin), "end": str(end),
                   "count": len(rows), "list": rows}, args.json)
    if args.csv:
        write_csv(rows, args.csv)
    return rows


def cmd_users(args):
    """用户增减 + 累计用户联合拉取（含净增计算）。"""
    end = parse_date(args.end) if args.end else (dt.date.today() - dt.timedelta(days=1))
    begin = end - dt.timedelta(days=args.days - 1)
    print(f"[users] 用户数据 {begin} ~ {end}（{args.days} 天，按 7 天分段）")
    a = fetch_one("getusersummary", begin, end)
    b = fetch_one("getusercumulate", begin, end)

    # 按日聚合净增
    per_day = {}
    for r in a:
        d = r.get("ref_date")
        s = per_day.setdefault(d, {"new": 0, "cancel": 0})
        s["new"] += r.get("new_user") or 0
        s["cancel"] += r.get("cancel_user") or 0
    cum = {r.get("ref_date"): r.get("cumulate_user") for r in b}

    print(f"\n{'日期':<12}{'新增':>8}{'取关':>8}{'净增':>8}{'累计用户':>12}")
    print("-" * 52)
    tn = tc = 0
    for d in sorted(per_day):
        s = per_day[d]
        net = s["new"] - s["cancel"]
        tn += s["new"]
        tc += s["cancel"]
        print(f"{d:<12}{human(s['new']):>8}{human(s['cancel']):>8}{human(net):>8}{human(cum.get(d)):>12}")
    print("-" * 52)
    print(f"{'合计':<12}{human(tn):>8}{human(tc):>8}{human(tn-tc):>8}")
    if not per_day:
        print("  （无数据）")
    if args.csv:
        write_csv([dict(ref_date=d, new_user=v["new"], cancel_user=v["cancel"],
                        net=v["new"] - v["cancel"], cumulate_user=cum.get(d))
                   for d, v in sorted(per_day.items())], args.csv)
    if args.json:
        dump_json({"usersummary": a, "usercumulate": b}, args.json)
    return per_day


def cmd_daily(args):
    """昨日核心指标一览（一次打通「用户 + 发表内容 + 消息」三块）。"""
    d = parse_date(args.date) if args.date else (dt.date.today() - dt.timedelta(days=1))
    ds = str(d)
    print("=" * 72)
    print(f"公众号数据日报  {ds}")
    print("=" * 72)

    def try_fetch(name, **kw):
        try:
            return fetch_one(name, d, d, quiet=True)
        except WxApiError as e:
            print(f"  [跳过] {name}: {e.errcode} {e.errmsg}"
                  + ("（48001 = 本账号无该接口权限）" if e.errcode == 48001 else ""))
            return []

    print("\n【用户】")
    us = try_fetch("getusersummary")
    cu = try_fetch("getusercumulate")
    if us:
        new = sum(r.get("new_user") or 0 for r in us)
        cancel = sum(r.get("cancel_user") or 0 for r in us)
        print(f"  新增关注 {new} / 取消关注 {cancel} / 净增 {new - cancel}")
        for r in sorted(us, key=lambda x: -(x.get("new_user") or 0))[:5]:
            if (r.get("new_user") or 0) or (r.get("cancel_user") or 0):
                print(f"    {decode('user_source', r.get('user_source'), 'getusersummary'):<14}"
                      f" 新增 {r.get('new_user')}，取关 {r.get('cancel_user')}")
    if cu:
        print(f"  累计总用户 {cu[-1].get('cumulate_user')}")

    print("\n【发表内容】")
    bs = try_fetch("getbizsummary")
    for r in bs:
        dt_ = r.get("detail") or {}
        print(f"  阅读 {human(dt_.get('read_user'))} / 分享 {human(dt_.get('share_user'))} / "
              f"爱心赞 {human(dt_.get('zaikan_user'))} / 拇指赞 {human(dt_.get('like_user'))} / "
              f"留言 {human(dt_.get('comment_count'))} / 收藏 {human(dt_.get('collection_user'))}")
    ar = try_fetch("getarticleread")
    if ar:
        print(f"  当日有阅读变化的文章 {len(ar)} 篇")
        for r in ar[:10]:
            det = r.get("detail") or {}
            print(f"    {r.get('msgid'):<18} 阅读人数 {det.get('read_user')}")
    else:
        old = try_fetch("getarticlesummary")
        if old:
            print(f"  （旧接口 getarticlesummary）当日被阅读的群发文章 {len(old)} 篇")

    print("\n【消息】")
    um = try_fetch("getupstreammsg")
    if um:
        tu = sum(r.get("msg_user") or 0 for r in um)
        tc2 = sum(r.get("msg_count") or 0 for r in um)
        print(f"  发送消息用户数 {tu} / 消息总数 {tc2}")
        for r in um:
            print(f"    {decode('msg_type', r.get('msg_type')):<14}"
                  f" 用户 {r.get('msg_user')}，消息 {r.get('msg_count')}")
    print("\n" + "=" * 72)
    print("[提醒] 数据存在延迟，返回体 is_delay=false 才表示已是最新；建议 8 点后查询")
    return None


def cmd_selftest(args):
    print("=" * 88)
    print("数据统计接口权限自检（逐个探测，48001 代表本账号未开通该权限）")
    print("=" * 88)
    load_wx_creds()
    y = dt.date.today() - dt.timedelta(days=1)
    ok, denied, other = [], [], []
    for name, v in APIS.items():
        try:
            r = api_call(v["path"], {"begin_date": str(y), "end_date": str(y)}, check=False)
            ec = r.get("errcode", 0)
            if ec in (0, None):
                n = len(r.get("list") or [])
                ok.append(name)
                print(f"  ✓ {name:<24} 可用（返回 {n} 行）")
            elif ec == 48001:
                denied.append(name)
                print(f"  ✗ {name:<24} 48001 未授权")
            else:
                other.append(name)
                print(f"  ? {name:<24} {ec} {r.get('errmsg')}")
        except WxApiError as e:
            if e.errcode == 48001:
                denied.append(name)
                print(f"  ✗ {name:<24} 48001 未授权")
            else:
                other.append(name)
                print(f"  ? {name:<24} {e.errcode} {e.errmsg}")
        time.sleep(0.2)
    print("-" * 88)
    print(f"结论：可用 {len(ok)} / 未授权 {len(denied)} / 其它 {len(other)}（共 {len(APIS)}）")
    if denied and len(denied) == len(APIS):
        print(">>> 全部未授权：数据统计接口「向所有认证公众号开放」，个人订阅号无法认证，")
        print("    因此接口数据不可用。替代方案：公众号后台「数据 → 内容分析/用户分析」网页，")
        print("    用 ego-browser 携带登录态抓取（见 SKILL.md「已发布内容查询」章节同款姿势）。")
    return None


def cmd_webplan(args):
    """数据接口不可用时的替代路径（后台网页 + ego-browser 携登录态抓取）。"""
    print("=" * 88)
    print("数据接口不可用时的替代路径：公众号后台网页")
    print("=" * 88)
    print("""
背景：datacube 数据接口「向所有认证公众号开发者开放」。个人订阅号无法完成微信认证，
      因此 21 个接口全部返回 48001（2026-09-16 实测：可用 0 / 未授权 21）。
      此时数据并非拿不到 —— 后台「数据」板块的网页视图与接口同源，只是入口不同。

接口族 ↔ 后台位置对照
┌────────────────────────┬──────────────────────────────────────────────┐
│ datacube 接口族         │ 公众号后台（mp.weixin.qq.com）位置            │
├────────────────────────┼──────────────────────────────────────────────┤
│ 用户数据 getusersummary │ 左侧「数据」→ 用户分析 → 用户增长 / 用户属性   │
│ 用户数据 getusercumulate│ 同上，「用户增长」页含累计关注总人数曲线       │
│ 图文数据 getarticleread │ 左侧「数据」→ 内容分析 → 单篇图文数据          │
│ 图文数据 getbizsummary  │ 左侧「数据」→ 内容分析 → 内容汇总              │
│ 图文数据 getuserread*   │ 内容分析 → 单篇图文 → 阅读来源分布             │
│ 消息数据 getupstreammsg │ 左侧「数据」→ 消息分析（部分账号无此模块）      │
│ 接口数据 getinterface*  │ 左侧「数据」→ 接口分析（需先配置服务器地址）    │
└────────────────────────┴──────────────────────────────────────────────┘
注：后台菜单以账号实际可见项为准；上表是导航语义对照，不保证每个账号都有全部模块。

抓取姿势（沿用 SKILL.md「已发布内容查询」章节的 ego-browser 套路）
  1. 打开 https://mp.weixin.qq.com/ 并完成扫码登录（登录态可复用）
  2. 进入「数据」板块，选择日期区间，等页面渲染完成
  3. 同源 fetch 后台自身的 JSON 接口，或直接读取 DOM 表格
  4. 落盘为 JSON/CSV，本地做趋势与环比分析

自检命令
  python3 wx_stats.py selftest     # 逐个探测 21 个接口的授权状态
  python3 wx_stats.py list         # 查看接口、跨度上限、维护状态
""")
    return None


# --------------------------------------------------------------------------- #
def build_parser():

    # --json/--csv 用 parents 让每个子命令都能就近书写（例如 list --count 3 --json out.json）
    # default=SUPPRESS 保证「只写在顶层」或「只写在子命令」两种写法都不会被对方的默认值覆盖。
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", default=argparse.SUPPRESS,
                        help="把原始返回写入该 JSON 文件；用 - 打印到标准输出")
    # 多账号：--profile <alias> 优先于环境变量 WX_PROFILE 与 profiles.json 的 default。
    # default=SUPPRESS 同样避免子命令层级互相覆盖。
    common.add_argument("--profile", default=argparse.SUPPRESS,
                        help="指定公众号账号别名（见 wx_account.py list）；缺省走 WX_PROFILE 或默认账号")
    common.add_argument("--csv", default=argparse.SUPPRESS,
                        help="把数据写成 CSV（自动扁平化嵌套字段）")

    p = argparse.ArgumentParser(
        prog="wx_stats.py",
        description="微信公众号数据统计（数据分析）全能力 CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        parents=[common],
        epilog=__doc__.split("用法示例：")[-1],
    )
    sub = p.add_subparsers(dest="cmd")

    s = sub.add_parser("list", help="列出全部接口、跨度上限与维护状态", parents=[common])
    s.set_defaults(func=cmd_list)

    s = sub.add_parser("fetch", help="调用任意一个 datacube 接口", parents=[common])
    s.add_argument("api", help="接口名，如 getusersummary（见 `list`）")
    s.add_argument("--begin", default="", help="起始日期 YYYY-MM-DD（默认同 end）")
    s.add_argument("--end", default="", help="结束日期（默认昨天）")
    s.add_argument("--date", default="", help="单日快捷方式，等价 begin=end=该日")
    s.add_argument("--days", type=int, default=0, help="最近 N 天（覆盖 --begin）")
    s.add_argument("--span", type=int, default=0, help="手动指定分段跨度（0=用接口默认）")
    s.add_argument("--limit", type=int, default=200, help="控制台最多显示行数")
    s.set_defaults(func=cmd_fetch)

    s = sub.add_parser("users", help="用户增减 + 累计用户联合报表", parents=[common])
    s.add_argument("--days", type=int, default=7)
    s.add_argument("--end", default="")
    s.set_defaults(func=cmd_users)

    s = sub.add_parser("daily", help="指定日期（默认昨天）核心指标一览", parents=[common])
    s.add_argument("--date", default="")
    s.set_defaults(func=cmd_daily)

    s = sub.add_parser("selftest", help="逐接口权限自检", parents=[common])
    s.set_defaults(func=cmd_selftest)

    s = sub.add_parser("webplan", help="接口无权限时的后台网页替代路径", parents=[common])
    s.set_defaults(func=cmd_webplan)
    return p


def main():
    p = build_parser()
    args = p.parse_args()
    # parents 里用了 SUPPRESS，未指定时属性不存在，这里统一补默认值
    for _k, _dv in (("json", ""), ("csv", ""), ("profile", "")):
        if not hasattr(args, _k):
            setattr(args, _k, _dv)
    # 账号选择必须在任何凭据/token 读取之前生效（并写回环境变量，子进程继承）。
    # ⚠️ 只有显式传了 --profile 才覆盖；未传时保留环境变量 WX_PROFILE 的语义，
    #    否则 set_profile("") 会把 WX_PROFILE 清掉，导致 shell 层切换失效。
    _profile_arg = getattr(args, "profile", "") or ""
    if _profile_arg:
        set_profile(_profile_arg)
    if not getattr(args, "cmd", None):
        p.print_help()
        return
    try:
        args.func(args)
    except WxApiError as e:
        print(f"[FAIL] 接口报错 {e.errcode}: {e.errmsg}  ({e.path})")
        if e.hint():
            print("    " + e.hint())
        if e.errcode == 48001:
            print("    >>> 该接口要求账号已「认证」；个人订阅号不可认证，故无法调用。")
            print("        替代：公众号后台「数据」板块网页，或用 ego-browser 携登录态抓取。")
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == "__main__":
    main()
