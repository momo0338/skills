#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, sys, argparse, httpx

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
os.makedirs(DATA_DIR, exist_ok=True)

PROVINCE_CODES = {
    '北京': '110000', '北京市': '110000',
    '天津': '120000', '天津市': '120000',
    '河北': '130000', '河北省': '130000',
    '山西': '140000', '山西省': '140000',
    '内蒙古': '150000', '内蒙古自治区': '150000',
    '辽宁': '210000', '辽宁省': '210000',
    '吉林': '220000', '吉林省': '220000',
    '黑龙江': '230000', '黑龙江省': '230000',
    '上海': '310000', '上海市': '310000',
    '江苏': '320000', '江苏省': '320000',
    '浙江': '330000', '浙江省': '330000',
    '安徽': '340000', '安徽省': '340000',
    '福建': '350000', '福建省': '350000',
    '江西': '360000', '江西省': '360000',
    '山东': '370000', '山东省': '370000',
    '河南': '410000', '河南省': '410000',
    '湖北': '420000', '湖北省': '420000',
    '湖南': '430000', '湖南省': '430000',
    '广东': '440000', '广东省': '440000',
    '广西': '450000', '广西壮族自治区': '450000',
    '海南': '460000', '海南省': '460000',
    '重庆': '500000', '重庆市': '500000',
    '四川': '510000', '四川省': '510000',
    '贵州': '520000', '贵州省': '520000',
    '云南': '530000', '云南省': '530000',
    '西藏': '540000', '西藏自治区': '540000',
    '陕西': '610000', '陕西省': '610000',
    '甘肃': '620000', '甘肃省': '620000',
    '青海': '630000', '青海省': '630000',
    '宁夏': '640000', '宁夏回族自治区': '640000',
    '新疆': '650000', '新疆维吾尔自治区': '650000',
    '台湾': '710000', '台湾省': '710000',
    '香港': '810000', '香港特别行政区': '810000',
    '澳门': '820000', '澳门特别行政区': '820000',
    '全国': '100000', '中国': '100000'
}

def resolve_adcode(name_or_code: str) -> str:
    name_or_code = name_or_code.strip()
    if name_or_code.isdigit(): return name_or_code
    return PROVINCE_CODES.get(name_or_code, '')

def get_geojson(name_or_code: str, force: bool = False) -> str:
    adcode = resolve_adcode(name_or_code)
    if not adcode:
        raise ValueError(f'未识别的省份名称或行政区划代码：{name_or_code}')
    filename = f'{adcode}_full.json'
    cache_path = os.path.join(DATA_DIR, filename)
    if os.path.exists(cache_path) and not force:
        return cache_path
    url = f'https://geo.datav.aliyun.com/areas_v3/bound/{adcode}_full.json'
    resp = httpx.get(url, timeout=20, follow_redirects=True)
    if resp.status_code != 200:
        raise RuntimeError(f'下载失败：HTTP {resp.status_code} ({url})')
    with open(cache_path, 'wb') as f:
        f.write(resp.content)
    return cache_path

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='获取并缓存中国省份 GeoJSON 数据')
    parser.add_argument('province', help='省份名称或代码')
    parser.add_argument('--force', action='store_true', help='强制刷新')
    args = parser.parse_args()
    try:
        p = get_geojson(args.province, force=args.force)
        print(f'OK: {p}')
    except Exception as e:
        print(f'Error: {e}', file=sys.stderr)
        sys.exit(1)
