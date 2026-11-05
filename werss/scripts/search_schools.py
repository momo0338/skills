#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Double First-Class / 985 / 211 University Employment Office MP Search & Auto-Subscriber
Zero-dependency script to search, match, and subscribe university employment official accounts via WeRSS.
"""

import argparse
import base64
import csv
import datetime
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

# Complete list of 147 Double First-Class universities in China (inclusive of all 39 '985' and 116 '211')
SCHOOLS_DATA = [
    # 北京
    ("北京大学", "985/211", "北京", "北大"),
    ("清华大学", "985/211", "北京", "清华"),
    ("中国人民大学", "985/211", "北京", "人大"),
    ("北京航空航天大学", "985/211", "北京", "北航"),
    ("北京理工大学", "985/211", "北京", "北理工"),
    ("中国农业大学", "985/211", "北京", "中农大"),
    ("北京师范大学", "985/211", "北京", "北师大"),
    ("中央民族大学", "985/211", "北京", "中央民大"),
    ("北京交通大学", "211", "北京", "北京交大"),
    ("北京工业大学", "211", "北京", "北工大"),
    ("北京科技大学", "211", "北京", "北科大"),
    ("北京化工大学", "211", "北京", "北化工"),
    ("北京邮电大学", "211", "北京", "北邮"),
    ("北京林业大学", "211", "北京", "北林"),
    ("北京中医药大学", "211", "北京", "北中医"),
    ("北京外国语大学", "211", "北京", "北外"),
    ("中国传媒大学", "211", "北京", "中传"),
    ("对外经济贸易大学", "211", "北京", "对外经贸"),
    ("中央音乐学院", "211", "北京", "央音"),
    ("中国政法大学", "211", "北京", "法大"),
    ("华北电力大学", "211", "北京", "华电"),
    ("中国地质大学(北京)", "211", "北京", "地大北京"),
    ("中国矿业大学(北京)", "211", "北京", "矿大北京"),
    ("中国石油大学(北京)", "211", "北京", "中石油北京"),
    ("中央财经大学", "211", "北京", "中财"),
    ("北京体育大学", "211", "北京", "北体"),
    ("中国科学院大学", "双一流", "北京", "国科大"),
    ("外交学院", "双一流", "北京", "外交学院"),
    ("北京协和医学院", "双一流", "北京", "协和医学院"),
    ("中央戏剧学院", "双一流", "北京", "中戏"),
    ("中央美术学院", "双一流", "北京", "央美"),
    ("中国音乐学院", "双一流", "北京", "国音"),
    ("首都师范大学", "双一流", "北京", "首师大"),
    # 天津
    ("南开大学", "985/211", "天津", "南开"),
    ("天津大学", "985/211", "天津", "天大"),
    ("天津医科大学", "211", "天津", "天医大"),
    ("天津工业大学", "双一流", "天津", "天工大"),
    ("天津中医药大学", "双一流", "天津", "天中医"),
    # 河北
    ("河北工业大学", "211", "河北", "河工大"),
    # 山西
    ("太原理工大学", "211", "山西", "太原理工"),
    ("山西大学", "双一流", "山西", "山大"),
    # 内蒙古
    ("内蒙古大学", "211", "内蒙古", "内大"),
    # 辽宁
    ("大连理工大学", "985/211", "辽宁", "大工"),
    ("东北大学", "985/211", "辽宁", "东大"),
    ("辽宁大学", "211", "辽宁", "辽大"),
    ("大连海事大学", "211", "辽宁", "海大"),
    # 吉林
    ("吉林大学", "985/211", "吉林", "吉大"),
    ("东北师范大学", "211", "吉林", "东北师大"),
    ("延边大学", "211", "吉林", "延大"),
    # 黑龙江
    ("哈尔滨工业大学", "985/211", "黑龙江", "哈工大"),
    ("哈尔滨工程大学", "211", "黑龙江", "哈工程"),
    ("东北林业大学", "211", "黑龙江", "东林"),
    ("东北农业大学", "211", "黑龙江", "东农"),
    # 上海
    ("复旦大学", "985/211", "上海", "复旦"),
    ("同济大学", "985/211", "上海", "同济"),
    ("上海交通大学", "985/211", "上海", "上海交大"),
    ("华东师范大学", "985/211", "上海", "华东师大"),
    ("华东理工大学", "211", "上海", "华理"),
    ("东华大学", "211", "上海", "东华"),
    ("上海外国语大学", "211", "上海", "上外"),
    ("上海大学", "211", "上海", "上大"),
    ("上海财经大学", "211", "上海", "上财"),
    ("海军军医大学", "211", "上海", "二军医大"),
    ("上海科技大学", "双一流", "上海", "上科大"),
    ("上海音乐学院", "双一流", "上海", "上音"),
    ("上海戏剧学院", "双一流", "上海", "上戏"),
    ("上海体育大学", "双一流", "上海", "上体"),
    ("上海中医药大学", "双一流", "上海", "上海中医药"),
    ("上海海洋大学", "双一流", "上海", "上海海洋"),
    # 江苏
    ("南京大学", "985/211", "江苏", "南大"),
    ("东南大学", "985/211", "江苏", "东大"),
    ("苏州大学", "211", "江苏", "苏大"),
    ("南京航空航天大学", "211", "江苏", "南航"),
    ("南京理工大学", "211", "江苏", "南理工"),
    ("中国矿业大学", "211", "江苏", "矿大"),
    ("河海大学", "211", "江苏", "河海"),
    ("江南大学", "211", "江苏", "江南大"),
    ("南京农业大学", "211", "江苏", "南农"),
    ("中国药科大学", "211", "江苏", "药大"),
    ("南京师范大学", "211", "江苏", "南师大"),
    ("南京邮电大学", "双一流", "江苏", "南邮"),
    ("南京信息工程大学", "双一流", "江苏", "南信大"),
    ("南京林业大学", "双一流", "江苏", "南林"),
    ("南京中医药大学", "双一流", "江苏", "南中医"),
    ("南京医科大学", "双一流", "江苏", "南医大"),
    # 浙江
    ("浙江大学", "985/211", "浙江", "浙大"),
    ("宁波大学", "双一流", "浙江", "宁大"),
    ("中国美术学院", "双一流", "浙江", "国美"),
    # 安徽
    ("中国科学技术大学", "985/211", "安徽", "中科大"),
    ("合肥工业大学", "211", "安徽", "合工大"),
    ("安徽大学", "211", "安徽", "安大"),
    # 福建
    ("厦门大学", "985/211", "福建", "厦大"),
    ("福州大学", "211", "福建", "福大"),
    # 江西
    ("南昌大学", "211", "江西", "南大"),
    # 山东
    ("山东大学", "985/211", "山东", "山大"),
    ("中国海洋大学", "985/211", "山东", "海大"),
    ("中国石油大学(华东)", "211", "山东", "石大"),
    # 河南
    ("郑州大学", "211", "河南", "郑大"),
    ("河南大学", "双一流", "河南", "河大"),
    # 湖北
    ("武汉大学", "985/211", "湖北", "武大"),
    ("华中科技大学", "985/211", "湖北", "华科"),
    ("中国地质大学(武汉)", "211", "湖北", "地大武汉"),
    ("武汉理工大学", "211", "湖北", "武汉理工"),
    ("华中农业大学", "211", "湖北", "华农"),
    ("华中师范大学", "211", "湖北", "华师"),
    ("中南财经政法大学", "211", "湖北", "中南财大"),
    # 湖南
    ("中南大学", "985/211", "湖南", "中南"),
    ("湖南大学", "985/211", "湖南", "湖大"),
    ("国防科技大学", "985/211", "湖南", "国防科大"),
    ("湖南师范大学", "211", "湖南", "湖南师大"),
    ("湘潭大学", "双一流", "湖南", "湘大"),
    # 广东
    ("中山大学", "985/211", "广东", "中大"),
    ("华南理工大学", "985/211", "广东", "华工"),
    ("暨南大学", "211", "广东", "暨大"),
    ("华南师范大学", "211", "广东", "华师"),
    ("南方科技大学", "双一流", "广东", "南科大"),
    ("华南农业大学", "双一流", "广东", "华农"),
    ("广州医科大学", "双一流", "广东", "广医"),
    ("广州中医药大学", "双一流", "广东", "广中医"),
    # 广西
    ("广西大学", "211", "广西", "西大"),
    # 海南
    ("海南大学", "211", "海南", "海大"),
    # 重庆
    ("重庆大学", "985/211", "重庆", "重大"),
    ("西南大学", "211", "重庆", "西大"),
    # 四川
    ("四川大学", "985/211", "四川", "川大"),
    ("电子科技大学", "985/211", "四川", "成电"),
    ("西南交通大学", "211", "四川", "西南交大"),
    ("四川农业大学", "211", "四川", "川农"),
    ("西南财经大学", "211", "四川", "西财"),
    ("成都理工大学", "双一流", "四川", "成理"),
    ("成都中医药大学", "双一流", "四川", "成中医"),
    ("西南石油大学", "双一流", "四川", "西南石大"),
    # 贵州
    ("贵州大学", "211", "贵州", "贵大"),
    # 云南
    ("云南大学", "211", "云南", "云大"),
    # 西藏
    ("西藏大学", "211", "西藏", "藏大"),
    # 陕西
    ("西安交通大学", "985/211", "陕西", "西安交大"),
    ("西北工业大学", "985/211", "陕西", "西工大"),
    ("西北农林科技大学", "985/211", "陕西", "西农"),
    ("西北大学", "211", "陕西", "西大"),
    ("西安电子科技大学", "211", "陕西", "西电"),
    ("陕西师范大学", "211", "陕西", "陕师大"),
    ("长安大学", "211", "陕西", "长大"),
    ("空军军医大学", "211", "陕西", "四军医大"),
    # 甘肃
    ("兰州大学", "985/211", "甘肃", "兰大"),
    # 青海
    ("青海大学", "211", "青海", "青大"),
    # 宁夏
    ("宁夏大学", "211", "宁夏", "宁大"),
    # 新疆
    ("新疆大学", "211", "新疆", "新大"),
    ("石河子大学", "211", "新疆", "石大"),
]


def load_credentials():
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
    from werss.client import load_config
    return load_config()


def search_school_mp(school_name, short_names, base_url, ak, sk):
    """Search WeChat official account for a school's career/employment center."""
    query = f"{school_name} 就业"
    kw = urllib.parse.quote(query)
    url = f"{base_url}/api/v1/wx/mps/search/{kw}?limit=5&offset=0"

    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"AK-SK {ak}:{sk}",
            "User-Agent": "WeRSS-SchoolSearch/1.0"
        }
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            items = data.get("data", {}).get("list", [])
            if not items:
                # Try fallback query with first short name
                aliases = short_names if isinstance(short_names, list) else [short_names]
                if aliases and aliases[0] and aliases[0] != school_name:
                    fb_kw = urllib.parse.quote(f"{aliases[0]} 就业")
                    fb_req = urllib.request.Request(
                        f"{base_url}/api/v1/wx/mps/search/{fb_kw}?limit=5&offset=0",
                        headers={"Authorization": f"AK-SK {ak}:{sk}"}
                    )
                    with urllib.request.urlopen(fb_req, timeout=15) as fb_resp:
                        fb_data = json.loads(fb_resp.read().decode("utf-8"))
                        items = fb_data.get("data", {}).get("list", [])

            return score_and_select_best(school_name, short_names, items)
    except Exception as e:
        return None, f"Search failed: {e}"


def score_and_select_best(school_name, short_names, items):
    """Score candidates to find the authoritative career office account."""
    if not items:
        return None, "No results found"

    aliases = short_names if isinstance(short_names, list) else [short_names]
    best_item = None
    best_score = -999

    for it in items:
        score = 0
        nick = it.get("nickname", "")
        sign = it.get("signature", "")
        verify = it.get("verify_status", 0)

        # Negative checks for commercial test prep / third parties
        negatives = ["考研", "考公", "培训", "教研", "兼职群", "互助", "备考", "辅导", "校友会", "研招网", "公考"]
        if any(w in nick for w in negatives):
            score -= 30

        # Branch/sub-campus/independent college penalties unless target is specifically one
        branch_words = ["分校", "校区", "独立学院", "科德", "知行", "滨海"]
        if any(b in nick for b in branch_words) and not any(b in school_name for b in branch_words):
            score -= 40

        # Positive keywords
        career_words = ["就业", "创业", "职业发展", "招就", "生涯", "毕业生", "招聘"]
        if any(w in nick for w in career_words):
            score += 25
        elif any(w in sign for w in career_words):
            score += 10

        # School identity matching
        if school_name in nick:
            score += 35
        elif school_name in sign:
            score += 15

        for sn in aliases:
            if sn:
                if f"{sn}就业" in nick or f"{sn}学生就业" in nick or f"{sn}招就" in nick:
                    score += 45
                elif sn in nick:
                    score += 25
                elif sn in sign:
                    score += 12

        # Official WeChat verification (verify_status == 2 is official enterprise/org verified)
        if verify == 2:
            score += 15

        # Official keywords in signature
        if "官方" in sign or "指导中心" in sign or "处" in sign or "办公室" in sign:
            score += 10

        if score > best_score:
            best_score = score
            best_item = it

    if best_item and best_score >= 15:
        return best_item, None
    elif items:
        return items[0], "Low confidence match"
    return None, "No suitable candidate"


def decode_fakeid_to_mp_id(fakeid):
    """Decode base64 fakeid to numeric ID and construct MP_WXS_{num}."""
    try:
        decoded = base64.b64decode(fakeid).decode("utf-8", errors="ignore").strip()
        if decoded:
            return f"MP_WXS_{decoded}"
    except Exception:
        pass
    # Fallback to sanitized fakeid
    safe_fakeid = fakeid.replace("=", "").replace("/", "_").replace("+", "-")
    return f"MP_WXS_{safe_fakeid}"


def batch_subscribe_mps(matched_mps, base_url, ak, sk):
    """Import and subscribe all matched MPs in one batch via CSV multipart upload."""
    if not matched_mps:
        print("[!] 没有匹配到任何有效公众号可订阅。")
        return False

    lines = ["id,公众号名称,封面图,简介,状态,创建时间,faker_id"]
    now_str = datetime.datetime.now().isoformat()

    for item in matched_mps:
        fakeid = item.get("fakeid", "")
        mp_id = decode_fakeid_to_mp_id(fakeid)
        name = item.get("nickname", "未知")
        cover = item.get("round_head_img", "")
        intro = item.get("signature", "").replace("\r", " ").replace("\n", " ").replace(",", "，")
        lines.append(f"{mp_id},{name},{cover},{intro},1,{now_str},{fakeid}")

    csv_content = "\r\n".join(lines) + "\r\n"

    boundary = uuid.uuid4().hex
    body = (
        f"--{boundary}\r\n"
        f"Content-Disposition: form-data; name=\"file\"; filename=\"mps_school.csv\"\r\n"
        f"Content-Type: text/csv; charset=utf-8\r\n\r\n"
        f"{csv_content}\r\n"
        f"--{boundary}--\r\n"
    ).encode("utf-8")

    req = urllib.request.Request(
        f"{base_url}/api/v1/wx/export/mps/import",
        data=body,
        headers={
            "Authorization": f"AK-SK {ak}:{sk}",
            "Content-Type": f"multipart/form-data; boundary={boundary}"
        }
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            res = json.loads(resp.read().decode("utf-8"))
            if res.get("code") == 0:
                stats = res.get("data", {}).get("stats", {})
                print(f"\n[✓] 批量导入与订阅完成！")
                print(f"    • 总共提交: {stats.get('total', len(matched_mps))} 个")
                print(f"    • 成功导入: {stats.get('imported', 0)} 个新公众号")
                print(f"    • 覆盖更新: {stats.get('updated', 0)} 个")
                print(f"    • 跳过存在: {stats.get('skipped', 0)} 个")
                return True
            else:
                print(f"[✗] 导入失败: {res}")
                return False
    except Exception as e:
        print(f"[✗] 导入请求异常: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="高校就业创业指导中心公众号批量检索与订阅助手")
    parser.add_argument("--tier", choices=["985", "211", "all"], default="all", help="筛选高校层级 (985, 211, 或 all全部147所)")
    parser.add_argument("--province", "-p", help="按省份筛选高校 (如: 北京, 上海, 江苏, 湖北)")
    parser.add_argument("--subscribe", "-s", action="store_true", default=True, help="搜索到后直接批量自动订阅进 WeRSS (默认开启)")
    parser.add_argument("--no-subscribe", dest="subscribe", action="store_false", help="仅搜索并导出结果，不加入订阅")
    parser.add_argument("--output", "-o", help="输出保存的 CSV 文件路径")
    parser.add_argument("--delay", type=float, default=0.5, help="请求间隔秒数 (默认 0.5s，防微信频控)")

    args = parser.parse_args()
    base_url, ak, sk = load_credentials()

    if not ak or not sk:
        print("[!] 错误: 未找到有效的 AK/SK 凭证，请检查 config.json 或环境变量。")
        sys.exit(1)

    # Filter target schools
    targets = []
    for school, tier, prov, short_name in SCHOOLS_DATA:
        if args.province and args.province not in prov:
            continue
        if args.tier == "985" and "985" not in tier:
            continue
        if args.tier == "211" and "211" not in tier:
            continue
        targets.append((school, tier, prov, short_name))

    print(f"\n[*] 目标高校范围: 共 {len(targets)} 所 (层级: {args.tier}, 省份: {args.province or '全国'})")
    print(f"[*] WeRSS 实例地址: {base_url}")
    print(f"[*] 自动订阅模式: {'已开启 (自动导入入库)' if args.subscribe else '仅检索，不订阅'}\n")

    matched_records = []
    mps_to_import = []

    for idx, (school, tier, prov, short_name) in enumerate(targets, 1):
        print(f"[{idx}/{len(targets)}] 正在检索: {school} ({prov}·{tier})...", end=" ", flush=True)
        item, note = search_school_mp(school, short_name, base_url, ak, sk)

        if item:
            nick = item.get("nickname", "")
            alias = item.get("alias", "")
            fakeid = item.get("fakeid", "")
            mp_id = decode_fakeid_to_mp_id(fakeid)
            sign = item.get("signature", "").replace("\n", " ").replace("\r", " ")
            print(f"-> 命中: 【{nick}】 ({alias or '无微信号'})")

            record = {
                "school": school,
                "tier": tier,
                "province": prov,
                "mp_name": nick,
                "alias": alias,
                "mp_id": mp_id,
                "fakeid": fakeid,
                "feed_xml": f"{base_url}/feed/{mp_id}.xml",
                "signature": sign,
                "match_note": note or "精确匹配"
            }
            matched_records.append(record)
            mps_to_import.append(item)
        else:
            print(f"-> [!] 未命中 ({note})")
            matched_records.append({
                "school": school,
                "tier": tier,
                "province": prov,
                "mp_name": "未找到",
                "alias": "-",
                "mp_id": "-",
                "fakeid": "-",
                "feed_xml": "-",
                "signature": "-",
                "match_note": note
            })

        if idx < len(targets):
            time.sleep(args.delay)

    # Save to CSV if requested or default
    out_file = args.output or f"university_employment_mps_{args.tier}.csv"
    with open(out_file, "w", encoding="utf-8-sig", newline="") as f:
        fieldnames = ["school", "tier", "province", "mp_name", "alias", "mp_id", "fakeid", "feed_xml", "signature", "match_note"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(matched_records)
    print(f"\n[✓] 检索汇总结果已保存至: {out_file}")

    # Auto subscribe into WeRSS
    if args.subscribe and mps_to_import:
        print(f"[*] 准备批量订阅 {len(mps_to_import)} 个匹配到的官方公众号到 WeRSS...")
        batch_subscribe_mps(mps_to_import, base_url, ak, sk)
        print(f"\n[✓] 全量聚合 Feed 链接: {base_url}/feed/all.xml")
        print("[✓] 可使用 CLI 查看最新状态: python3 werss/werss_cli.py list")


if __name__ == "__main__":
    main()
