#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Search, match, auto-subscribe, tag, and export Key Specialized & High-Level Non-Double-First-Class Universities
"""

import base64
import csv
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from werss.client import load_config, get_data_dir

BASE_URL, AK, SK = load_config()
DATA_DIR = get_data_dir()
TAG_ID = "a2c22e73-d5c6-4536-8bc2-484a217ee85a"
AUTH_HEADER = {"Authorization": f"AK-SK {AK}:{SK}"}

KEY_SCHOOLS = [
    # 电力
    ("东北电力大学", "行业特色/电力", "吉林", ["东电", "东北电大"]),
    ("上海电力大学", "行业特色/电力", "上海", ["上电", "上海电大"]),
    ("长沙理工大学", "行业特色/电力", "湖南", ["长沙理工", "长理"]),
    ("三峡大学", "行业特色/电力水利", "湖北", ["三大", "三峡大"]),
    ("沈阳工程学院", "行业特色/电力", "辽宁", ["沈阳工程"]),
    # IT/电子
    ("杭州电子科技大学", "行业特色/IT电子", "浙江", ["杭电"]),
    ("重庆邮电大学", "行业特色/IT电子", "重庆", ["重邮"]),
    ("西安邮电大学", "行业特色/IT电子", "陕西", ["西邮"]),
    ("桂林电子科技大学", "行业特色/IT电子", "广西", ["桂电"]),
    # 政法
    ("华东政法大学", "行业特色/政法", "上海", ["华政"]),
    ("西南政法大学", "行业特色/政法", "重庆", ["西政"]),
    ("西北政法大学", "行业特色/政法", "陕西", ["西法大", "西北政法"]),
    # 铁路交通
    ("石家庄铁道大学", "行业特色/铁道交通", "河北", ["石铁大", "石家庄铁道"]),
    ("华东交通大学", "行业特色/铁道交通", "江西", ["华东交大"]),
    ("大连交通大学", "行业特色/铁道交通", "辽宁", ["大连交大"]),
    ("兰州交通大学", "行业特色/铁道交通", "甘肃", ["兰州交大", "兰交大"]),
    # 军工兵工
    ("中北大学", "行业特色/军工国防", "山西", ["中北"]),
    ("长春理工大学", "行业特色/军工国防", "吉林", ["长春理工", "长理"]),
    ("西安工业大学", "行业特色/军工国防", "陕西", ["西安工大", "西工院"]),
    ("沈阳理工大学", "行业特色/军工国防", "辽宁", ["沈理工", "沈阳理工"]),
    # 民航航运
    ("中国民航大学", "行业特色/民航", "天津", ["中航大", "民航大学"]),
    ("中国民用航空飞行学院", "行业特色/民航", "四川", ["中飞院"]),
    ("上海海事大学", "行业特色/航运", "上海", ["上海海事", "海事大"]),
    ("集美大学", "行业特色/航运水产", "福建", ["集美", "集大"]),
    # 石油化工
    ("东北石油大学", "行业特色/石油化工", "黑龙江", ["东油", "东北石油"]),
    ("西安石油大学", "行业特色/石油化工", "陕西", ["西石大", "西安石油"]),
    ("长江大学", "行业特色/石油地质", "湖北", ["长大", "长江大"]),
    ("常州大学", "行业特色/石油化工", "江苏", ["常大", "常州大"]),
    # 财经
    ("东北财经大学", "行业特色/财经", "辽宁", ["东财", "东北财大"]),
    ("江西财经大学", "行业特色/财经", "江西", ["江财", "江西财大"]),
    ("山西财经大学", "行业特色/财经", "山西", ["山财", "山西财大"]),
    ("首都经济贸易大学", "行业特色/财经", "北京", ["首经贸"]),
    ("浙江工商大学", "行业特色/财经", "浙江", ["浙商大", "浙江工商"]),
    # 省属高水平综合/工科
    ("深圳大学", "省属重点/综合", "广东", ["深大"]),
    ("广东工业大学", "省属重点/工科", "广东", ["广工", "广工大"]),
    ("浙江工业大学", "省属重点/工科", "浙江", ["浙工大"]),
    ("江苏大学", "省属重点/工科", "江苏", ["江大", "江苏大"]),
    ("扬州大学", "省属重点/综合", "江苏", ["扬大", "扬州大"]),
    ("南京工业大学", "省属重点/工科", "江苏", ["南工大"]),
    ("燕山大学", "省属重点/重工", "河北", ["燕大", "燕山大"]),
    ("青岛大学", "省属重点/综合", "山东", ["青大", "青岛大"]),
    ("齐鲁工业大学", "省属重点/工科", "山东", ["齐鲁工大"]),
    ("黑龙江大学", "省属重点/综合", "黑龙江", ["黑大", "黑龙江大"]),
    ("武汉科技大学", "省属重点/冶金工科", "湖北", ["武科大"]),
    ("西安建筑科技大学", "省属重点/建筑土木", "陕西", ["西建大", "西建"]),
    ("西安科技大学", "省属重点/矿业安全", "陕西", ["西科大", "西科"]),
    ("江西师范大学", "省属重点/师范", "江西", ["江西师大", "江师大"]),
    ("山东师范大学", "省属重点/师范", "山东", ["山师大", "山东师大"]),
    ("河南师范大学", "省属重点/师范", "河南", ["河南师大", "河师大"]),
    # 医科
    ("首都医科大学", "行业特色/医药卫生", "北京", ["首医", "首医大"]),
    ("中国医科大学", "行业特色/医药卫生", "辽宁", ["中国医大", "红医"]),
    ("哈尔滨医科大学", "行业特色/医药卫生", "黑龙江", ["哈医大"]),
    ("温州医科大学", "行业特色/医药卫生", "浙江", ["温医大", "温医"]),
    ("南方医科大学", "行业特色/医药卫生", "广东", ["南医大", "南方医大"]),
    ("重庆医科大学", "行业特色/医药卫生", "重庆", ["重医", "重医大"])
]


def score_and_select(school_name, aliases, items):
    if not items:
        return None
    best_item = None
    best_score = -999

    for it in items:
        score = 0
        nick = it.get("nickname", "")
        sign = it.get("signature", "")
        verify = it.get("verify_status", 0)

        negatives = ["考研", "考公", "培训", "教研", "兼职群", "互助", "备考", "辅导", "校友会", "研招网", "公考", "中公", "华图"]
        if any(w in nick for w in negatives):
            score -= 40

        branch_words = ["分校", "校区", "独立学院", "科技学院", "职业学院", "继续教育", "自考"]
        if any(b in nick for b in branch_words) and not any(b in school_name for b in branch_words):
            score -= 30

        career_words = ["就业", "创业", "职业发展", "招就", "生涯", "毕业生", "招聘", "选聘"]
        if any(w in nick for w in career_words):
            score += 30
        elif any(w in sign for w in career_words):
            score += 12

        if school_name in nick:
            score += 40
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

        if verify == 2:
            score += 15

        if "官方" in sign or "指导中心" in sign or "处" in sign or "办公室" in sign:
            score += 10

        if score > best_score:
            best_score = score
            best_item = it

    if best_item and best_score >= 15:
        return best_item
    elif items:
        return items[0]
    return None


def search_school(school, aliases):
    kw = urllib.parse.quote(f"{school} 就业")
    url = f"{BASE_URL}/api/v1/wx/mps/search/{kw}?limit=5&offset=0"
    req = urllib.request.Request(url, headers=AUTH_HEADER)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
            items = data.get("data", {}).get("list", [])
            if not items and aliases:
                fallback_kw = urllib.parse.quote(f"{aliases[0]} 就业")
                f_req = urllib.request.Request(f"{BASE_URL}/api/v1/wx/mps/search/{fallback_kw}?limit=5&offset=0", headers=AUTH_HEADER)
                with urllib.request.urlopen(f_req, timeout=15) as f_resp:
                    f_data = json.loads(f_resp.read().decode())
                    items = f_data.get("data", {}).get("list", [])
            return score_and_select(school, aliases, items)
    except Exception as e:
        print(f"  [!] 搜索错误 {school}: {e}")
        return None


def fakeid_to_mp_id(fakeid):
    try:
        num = base64.b64decode(fakeid).decode("utf-8", errors="ignore").strip()
        return f"MP_WXS_{num}"
    except Exception:
        return f"MP_WXS_{fakeid}"


def main():
    print(f"[*] 开始检索 {len(KEY_SCHOOLS)} 所重点本科/行业特色高校的就业招聘官方公众号...")
    matched = []
    
    for idx, (school, tier, province, aliases) in enumerate(KEY_SCHOOLS, 1):
        time.sleep(0.4)
        item = search_school(school, aliases)
        if not item:
            print(f"[{idx:02d}/{len(KEY_SCHOOLS)}] [✗] {school}: 未找到匹配公众号")
            continue

        nick = item.get("nickname", "")
        alias = item.get("alias", "")
        fakeid = item.get("fakeid", "")
        mp_id = fakeid_to_mp_id(fakeid)
        sign = item.get("signature", "").replace("\n", " ").strip()
        qr_url = f"https://open.weixin.qq.com/qr/code?username={alias}" if alias else ""
        feed_xml = f"{BASE_URL}/feed/{mp_id}.xml"

        matched.append({
            "school": school,
            "tier": tier,
            "province": province,
            "mp_name": nick,
            "alias": alias,
            "mp_id": mp_id,
            "fakeid": fakeid,
            "feed_xml": feed_xml,
            "qr_code_url": qr_url,
            "signature": sign
        })
        print(f"[{idx:02d}/{len(KEY_SCHOOLS)}] [✓] {school} -> {nick} ({alias or '无微信号'}) [{mp_id}]")

    print(f"\n[*] 检索完成：成功匹配 {len(matched)} / {len(KEY_SCHOOLS)} 所高校。")

    # 1. 批量保存为 key_university_employment_mps.csv
    key_csv_path = str(DATA_DIR / "key_university_employment_mps.csv")
    headers = ["school", "tier", "province", "mp_name", "alias", "mp_id", "fakeid", "feed_xml", "qr_code_url", "signature"]
    with open(key_csv_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(matched)
    print(f"[✓] 已保存重点本科清单至: {key_csv_path}")

    # 2. 调用 WeRSS 批量导入订阅接口
    print("\n[*] 正在批量将这些高校就业公众号导入 WeRSS 订阅库...")
    import_csv_buf = []
    import_csv_buf.append("id,公众号名称,封面图,简介,状态,创建时间,faker_id")
    now_iso = time.strftime("%Y-%m-%dT%H:%M:%S")
    for m in matched:
        # WeRSS import format: id, mp_name, mp_cover, mp_intro, status, created_at, faker_id
        import_csv_buf.append(f'{m["mp_id"]},{m["mp_name"]},,{m["signature"]},1,{now_iso},{m["fakeid"]}')
    csv_bytes = "\n".join(import_csv_buf).encode("utf-8")

    boundary = "----WebKitFormBoundary" + uuid_str()
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="key_mps.csv"\r\n'
        f"Content-Type: text/csv\r\n\r\n"
    ).encode("utf-8") + csv_bytes + f"\r\n--{boundary}--\r\n".encode("utf-8")

    import_req = urllib.request.Request(
        f"{BASE_URL}/api/v1/wx/export/mps/import",
        data=body,
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            **AUTH_HEADER
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(import_req, timeout=30) as res:
            res_data = json.loads(res.read().decode())
            print(f"[✓] WeRSS 批量导入响应: {res_data.get('message', 'ok')}")
    except Exception as e:
        print(f"[!] 批量导入 API 异常: {e}")

    # 3. 追加到 “大学就业中心” 标签 (tag)
    print(f"\n[*] 正在将新公众号追加到【大学就业中心】标签...")
    tag_req = urllib.request.Request(f"{BASE_URL}/api/v1/wx/tags/{TAG_ID}", headers=AUTH_HEADER)
    with urllib.request.urlopen(tag_req) as res:
        tag_json = json.loads(res.read().decode())["data"]

    existing_mps = json.loads(tag_json.get("mps_id") or "[]")
    existing_id_set = set()
    all_tag_items = []
    for it in existing_mps:
        mid = it.get("id") if isinstance(it, dict) else str(it)
        if mid and mid not in existing_id_set:
            existing_id_set.add(mid)
            all_tag_items.append({"id": mid, "name": it.get("name", "") if isinstance(it, dict) else ""})

    added_count = 0
    for m in matched:
        mid = m["mp_id"]
        if mid not in existing_id_set:
            existing_id_set.add(mid)
            all_tag_items.append({"id": mid, "name": m["mp_name"]})
            added_count += 1

    put_body = {
        "name": tag_json.get("name", "大学就业中心"),
        "cover": tag_json.get("cover", ""),
        "intro": tag_json.get("intro", "全国双一流/985/211及重点行业特色高校就业指导中心官方公众号"),
        "mps_id": json.dumps(all_tag_items, ensure_ascii=False),
        "status": 1
    }
    put_req = urllib.request.Request(
        f"{BASE_URL}/api/v1/wx/tags/{TAG_ID}",
        data=json.dumps(put_body).encode("utf-8"),
        headers={"Content-Type": "application/json", **AUTH_HEADER},
        method="PUT"
    )
    with urllib.request.urlopen(put_req) as res:
        put_resp = json.loads(res.read().decode())
        print(f"[✓] 成功为标签【大学就业中心】新增 {added_count} 个公众号，标签内目前共有 {len(all_tag_items)} 个公众号！")

    # 4. 生成双一流 + 重点本科两批高校的合并大表
    combined_csv_path = str(DATA_DIR / "university_employment_mps_all_combined.csv")
    combined_rows = []
    seen_ids = set()

    # 读原双一流表
    old_csv_path = str(DATA_DIR / "university_employment_mps_all.csv")
    if os.path.exists(old_csv_path):
        with open(old_csv_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for r in reader:
                mid = r.get("mp_id", "").strip()
                if mid and mid not in seen_ids:
                    seen_ids.add(mid)
                    combined_rows.append(r)

    # 追加新重点院校
    for m in matched:
        mid = m["mp_id"]
        if mid not in seen_ids:
            seen_ids.add(mid)
            combined_rows.append(m)

    headers = ["school", "tier", "province", "mp_name", "alias", "mp_id", "fakeid", "feed_xml", "qr_code_url", "signature", "match_note"]
    with open(combined_csv_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(combined_rows)

    print(f"\n[✓] 已生成合并总表: {combined_csv_path} (共包含全国 {len(combined_rows)} 所高校就业公众号)")


def uuid_str():
    import uuid
    return str(uuid.uuid4()).replace("-", "")


if __name__ == "__main__":
    main()
