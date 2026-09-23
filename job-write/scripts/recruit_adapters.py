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
  guopin   国聘网央企/国企官方招聘平台（gp-api.iguopin.com 推荐/最新岗位接口）。
  beisen   北森招聘门户（zhiye.com 新门户 ux-recruitment-portal 2022+）：
            POST /api/Jobad/GetJobAdPageList 拉职位数组。
            2026-09-23 实测（foresealife.zhiye.com）：接口免鉴权、JSON 返回；
            职位详情 URL = https://<host>/<campus|social>/detail?jobAdId=<Id>。
            ⚠️ 北森**老版模板**（CMS / tms-recruit，如 cssc.zhiye.com）无此接口
            （302→404，非 JSON）——调用方需将其降级为哨兵（见 recruit_scan 数据分型）。

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


def scan_beisen(entry, verbose=True, max_pages=3, only_campus=True):
    """北森招聘门户（zhiye.com 新门户 ux-recruitment-portal 2022+）职位列表适配器。

    POST /api/Jobad/GetJobAdPageList（免鉴权 JSON 接口），返回在招职位数组。
    entry: {"id","name","url",...}
    only_campus=True（默认）：只保留校招/校园/实习/管培类岗位进收件箱——
    北森在招岗位以社招为主（实测 80 站单轮 9479 条，社招占绝大多数），
    全量入库会淹没公告线索；公众号选题（A 线校招）也只需要校招类。
    社招岗位如需监控，传 only_campus=False 取全量。
    返回 (items, ok)；老版模板（CMS/tms-recruit）接口 302/非 JSON → ([], False)，
    调用方应将该源降级为哨兵（改 kind=self_spa），避免持续误报健康失败。
    """
    m = re.match(r"https?://([^/]+)", entry["url"])
    if not m:
        return [], False
    host = m.group(1)
    api = f"https://{host}/api/Jobad/GetJobAdPageList"
    headers = {
        "User-Agent": UA,
        "Content-Type": "application/json",
        "Accept": "application/json, text/plain, */*",
        "Origin": f"https://{host}",
        "Referer": f"https://{host}/",
    }
    body = {
        "PageIndex": 0, "PageSize": 100, "KeyWords": "", "SpecialType": 0,
        "PortalId": "",
        "DisplayFields": ["Category", "Kind", "LocId", "PostDate",
                          "ClassificationTwo", "WorkWeChatQrCode"],
    }

    items = []
    try:
        for page in range(max_pages):
            body["PageIndex"] = page
            req = urllib.request.Request(
                api, headers=headers,
                data=json.dumps(body).encode("utf-8"))
            with urllib.request.urlopen(req, timeout=15, context=SSL_CTX) as resp:
                raw = resp.read()
                try:
                    data = json.loads(raw.decode("utf-8", "ignore"))
                except Exception:
                    # 老版模板 / 非 JSON：明确回报不支持
                    if verbose:
                        print(f"  ⚠️  [北森·{entry['name']}] 接口非 JSON"
                              f"（老版模板不支持），建议降级哨兵", file=__import__("sys").stderr)
                    return [], False
            jobs = data.get("Data") or []
            if not isinstance(jobs, list) or not jobs:
                break
            total = data.get("Total") or 0
            for j in jobs:
                jid = j.get("Id") or j.get("JobAdId")
                jname = str(j.get("JobAdName") or "").strip()
                if not jid or not jname:
                    continue
                category = str(j.get("Category") or "").strip()
                kind_str = str(j.get("Kind") or "").strip()
                # only_campus：只保留校招/校园/实习/管培类岗位
                if only_campus and not (
                        "校招" in category or "校园" in category
                        or "实习" in category or "intern" in kind_str.lower()
                        or "管培" in jname):
                    continue
                locs = j.get("LocNames") or []
                place = "、".join(str(x) for x in locs if x) if locs else ""
                hc = j.get("HeadCount")
                hc_str = f"{hc}人" if isinstance(hc, (int, float)) and hc else ""
                note_parts = [category, place, hc_str,
                              str(j.get("Degree") or "").strip()]
                note = " ｜ ".join(p for p in note_parts if p)
                # 详情页路由：校招/校园类走 campus，其余走 social
                detail_path = "campus" if ("校招" in category or "校园" in category
                                           or "intern" in str(j.get("Kind") or "").lower()
                                           or "实习" in str(j.get("Kind") or "")) else "social"
                items.append({
                    "title": f"{jname}（{entry['name']}）",
                    "source": f"北森招聘·{entry['name']}",
                    "date": str(j.get("PostDate") or "")[:10],
                    "url": f"https://{host}/{detail_path}/detail?jobAdId={jid}",
                    "note": note,
                })
            if len(jobs) < (body["PageSize"] or 100) or (total and page * (body["PageSize"] or 100) + len(jobs) >= total):
                break
            time.sleep(0.15)
    except Exception as e:
        if verbose:
            print(f"  ⚠️  [北森·{entry['name']}] 接口失败：{str(e)[:60]}",
                  file=__import__("sys").stderr)
        return items, len(items) > 0

    return items, True

