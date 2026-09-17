#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""recruit_adapters.py —— 平台族适配器（P3，job-write 配套）

当前实现：
  zhaokao   智联招考型子站（附录 A 三步法）：
            cms-menu/list-portal → job-info/selectJobList → 岗位数组
            适用于 jsrg / jsep / jsyhkf / jssalt2026xz 等招考型站点；
            企业招聘型站点返回 492「站点已经禁用」，不适用。

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
