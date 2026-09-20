#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""recruit_adapters.py —— 平台族适配器（P3，job-write 配套）

当前实现：
  zhaokao   智联招考型子站（附录 A 三步法）：
            cms-menu/list-portal → job-info/selectJobList → 岗位数组
            适用于 jsrg / jsep / jsyhkf 等**招考型**站点；
            企业招聘型站点返回 492「站点已经禁用」，不适用。
            ⚠️ 2026-09-18 实测更正：jssalt2026xz 属**企业型**，返回 492，**不在**适用名单内
            （原 docstring 曾误列为适用）。判断口径＝看子站是「招考报名站」还是「企业招聘站」。

约定：
  scan_<kind>(entry, verbose) -> (items, ok)
  items: [{"title","source","date","url","note"}]
  零依赖（urllib/json），沿用 recruit_scan 的 UA 与放宽 SSL。
"""
import json
import re
import ssl
import time
import urllib.request

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36")
SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE

ZKAPI = "https://zkapi.zhaopin.com/zhaokao/api/zhaokao/h5"


def _get_json(url, referer, timeout=15):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Content-Type": "application/json",
        "Source-Channel": "6",
        "x-zp-device-sn": "recruit-scan-probe",
        "Referer": f"https://{referer}/",
    })
    with urllib.request.urlopen(req, timeout=timeout, context=SSL_CTX) as resp:
        return json.loads(resp.read().decode("utf-8", "ignore"))


def scan_zhaokao(entry, verbose=True):
    """智联招考型子站：直接拉岗位数组（附录 A）。

    entry: {"id","name","url",...}
    返回 (items, ok)；站点非招考型（492）或接口异常 → ([], False)。
    """
    m = re.match(r"https?://([^/]+)", entry["url"])
    if not m:
        return [], False
    host = m.group(1)
    try:
        menu = _get_json(f"{ZKAPI}/cms-menu/list-portal", host)
        if not menu.get("success"):
            if verbose:
                print(f"  ⚠️  [招考·{entry['name']}] {menu.get('msg', '未知错误')}",
                      file=__import__("sys").stderr)
            return [], False
        data = _get_json(f"{ZKAPI}/job-info/selectJobList", host)
        jobs = data.get("data") or []
        if not isinstance(jobs, list):
            jobs = []
    except Exception as e:
        if verbose:
            print(f"  ⚠️  [招考·{entry['name']}] 接口失败：{str(e)[:60]}",
                  file=__import__("sys").stderr)
        return [], False

    items = []
    for j in jobs:
        name = str(j.get("jobName") or "").strip()
        if not name:
            continue
        place = (j.get("jobAddress") or j.get("jobGroupName") or "").strip()
        items.append({
            "title": f"{name}（{entry['name']}）",
            "source": f"招考接口·{entry['name']}",
            "date": "",
            "url": f"https://{host}/zk/#/jobDetail?id={j.get('id', '')}",
            "note": " ｜ ".join(x for x in [
                str(j.get("enrollmentUnit") or "").strip(),
                (f"{j.get('enrollmentPlaces')}人" if j.get("enrollmentPlaces") else ""),
                str(j.get("eduRecord") or "").strip(),
                str(place).strip(),
            ] if x),
        })
        time.sleep(0.1)
    return items, True

def scan_guopin(entry, verbose=True, max_pages=2):
    """国聘网央企/国企/高校事业单位官方招聘平台适配器。
    
    使用免签名的推荐与最新岗位接口拉取结构化在招信息。
    entry: {"id", "name", "url", ...}
    返回 (items, ok)
    """
    api_url = "https://gp-api.iguopin.com/api/jobs/v1/recom-job"
    headers = {
        "User-Agent": UA,
        "Content-Type": "application/json",
        "Device": "pc",
        "Version": "5.2.300",
        "Subsite": "iguopin"
    }
    
    keywords = ["", "计算机", "电气", "机械", "管理"]
    items = []
    seen_ids = set()
    
    try:
        for kw in keywords:
            for page in range(1, max_pages + 1):
                search_body = {"page": page, "page_size": 20}
                if kw:
                    search_body["keyword"] = kw
                payload = {
                    "search": search_body,
                    "recom": {"update_time": True, "company_nature": True, "hot_job": True}
                }
                req = urllib.request.Request(api_url, headers=headers, data=json.dumps(payload).encode("utf-8"))
                with urllib.request.urlopen(req, timeout=12, context=SSL_CTX) as resp:
                    res_json = json.loads(resp.read().decode("utf-8", "ignore"))
                    if res_json.get("code") != 200:
                        continue
                    job_list = res_json.get("data", {}).get("list") or []
                    for it in job_list:
                        jid = it.get("job_id")
                        if not jid or jid in seen_ids:
                            continue
                        seen_ids.add(jid)
                        
                        jname = it.get("job_name", "").strip()
                        cname = it.get("company_name", "").strip()
                        cinfo = it.get("company_info") or {}
                        nature = cinfo.get("nature_cn") or it.get("nature_cn") or "国企"
                        
                        districts = it.get("district_list") or []
                        area_cn = districts[0].get("area_cn") if districts else "全国"
                        edu = it.get("education_cn", "")
                        amount = it.get("amount")
                        amount_str = f"{amount}人" if amount else ""
                        
                        # 组合标准标题与摘要
                        full_title = f"{cname} {jname} 招聘"
                        note_parts = [nature, area_cn, edu, amount_str]
                        note = " ｜ ".join(p for p in note_parts if p)
                        
                        items.append({
                            "title": full_title,
                            "source": "国聘·央企招聘平台",
                            "date": (it.get("refresh_time") or it.get("start_time") or "")[:10],
                            "url": f"https://www.iguopin.com/job/detail?id={jid}",
                            "note": note,
                        })
                time.sleep(0.2)
        return items, True
    except Exception as e:
        if verbose:
            print(f"  ⚠️  [国聘·{entry['name']}] 接口失败：{str(e)[:60]}",
                  file=__import__("sys").stderr)
        return items, len(items) > 0

