#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Inspect all MPs in WeRSS, find any with empty/missing mp_cover,
search WeChat API to fetch their official logo (round_head_img),
and update them in WeRSS via PUT /api/v1/wx/mps/{mp_id}.
"""

import json
import time
import urllib.parse
import urllib.request

CONFIG_FILE = "/Users/zhugx/src/skills/werss/config.json"
with open(CONFIG_FILE, "r") as f:
    cfg = json.load(f)

BASE_URL = cfg["base_url"].rstrip("/")
AK = cfg["access_key"]
SK = cfg["secret_key"]
AUTH_HEADER = {"Authorization": f"AK-SK {AK}:{SK}"}

def get_all_mps():
    all_mps = []
    offset = 0
    limit = 50
    while True:
        url = f"{BASE_URL}/api/v1/wx/mps?limit={limit}&offset={offset}"
        req = urllib.request.Request(url, headers=AUTH_HEADER)
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode())
            items = data.get("data", {}).get("list", [])
            total = data.get("data", {}).get("total", 0)
            all_mps.extend(items)
            offset += len(items)
            if offset >= total or not items:
                break
    return all_mps

def search_logo(name):
    kw = urllib.parse.quote(name)
    url = f"{BASE_URL}/api/v1/wx/mps/search/{kw}?limit=5&offset=0"
    req = urllib.request.Request(url, headers=AUTH_HEADER)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
            items = data.get("data", {}).get("list", [])
            for it in items:
                # exact or close match
                if it.get("nickname") == name or name in it.get("nickname", ""):
                    head_img = it.get("round_head_img")
                    if head_img:
                        return head_img
            if items and items[0].get("round_head_img"):
                return items[0].get("round_head_img")
    except Exception as e:
        print(f"  [!] 搜索 logo 出错: {name} -> {e}")
    return None

def update_mp_cover(mp_id, mp_name, cover_url, intro):
    url = f"{BASE_URL}/api/v1/wx/mps/{mp_id}"
    payload = {
        "mp_name": mp_name,
        "mp_cover": cover_url,
        "mp_intro": intro or ""
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **AUTH_HEADER},
        method="PUT"
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
            return data.get("code") == 0
    except Exception as e:
        print(f"  [!] 更新失败 {mp_id}: {e}")
        return False

def main():
    mps = get_all_mps()
    print(f"[*] WeRSS 实例中共有 {len(mps)} 个公众号")
    
    missing = [m for m in mps if not m.get("mp_cover") or not m.get("mp_cover").strip()]
    print(f"[*] 其中缺少 logo / 头像的公众号共: {len(missing)} 个\n")
    
    fixed_count = 0
    for idx, m in enumerate(missing, 1):
        mid = m["id"]
        name = m.get("mp_name", "")
        intro = m.get("mp_intro", "")
        print(f"[{idx:02d}/{len(missing)}] 正在为【{name}】({mid}) 获取官方 Logo...")
        time.sleep(0.3)
        cover = search_logo(name)
        if cover:
            ok = update_mp_cover(mid, name, cover, intro)
            if ok:
                print(f"   ✓ 成功更新 Logo: {cover[:40]}...")
                fixed_count += 1
            else:
                print(f"   ✗ 更新接口返回失败")
        else:
            print(f"   ✗ 未能搜索到对应头像")
            
    print(f"\n[✓] 修复完成！成功为 {fixed_count}/{len(missing)} 个公众号补齐了官方 Logo 头像。")

if __name__ == "__main__":
    main()
