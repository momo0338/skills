# -*- coding: utf-8 -*-
import requests
import csv
import os
import sys
import argparse
import time

DEFAULT_AK = os.environ.get("BAIDU_MAP_AK", "")  # 凭据不入库，用环境变量注入
import sys as _sys
if not DEFAULT_AK:
    _sys.exit("请先注入百度地图 AK：export BAIDU_MAP_AK=<你的AK>，或显式传 --ak <AK>")

def get_poi_data(ak, query, region, page_size=20, page_num=0):
    url = "https://api.map.baidu.com/place/v2/search"
    params = {
        "query": query,
        "region": region,
        "output": "json",
        "ak": ak,
        "page_size": page_size,
        "page_num": page_num
    }
    response = requests.get(url, params=params)
    return response.json()

def fetch_all_pages(ak, query, region, delay=1):
    all_results = []
    page_num = 0
    page_size = 20

    while True:
        data = get_poi_data(ak, query, region, page_size, page_num)

        if data.get("status") != 0:
            print(f"  API 返回错误: {data.get('message')}")
            break

        total = data.get("total", 0)
        results = data.get("results", [])
        all_results.extend(results)

        print(f"  第 {page_num + 1} 页，{len(results)} 条，累计 {len(all_results)}/{total} 条")

        if len(all_results) >= total:
            break

        page_num += 1
        time.sleep(delay)

    return all_results

def read_queries_from_file(filepath):
    queries = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                queries.append(line)
    return queries

def save_results_to_csv(all_results, output_file):
    if not all_results:
        print("  无结果")
        return

    fieldnames = ["query", "name", "lat", "lng", "address", "province", "city", "area", "telephone", "detail", "uid", "street_id"]

    with open(output_file, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for query_text, item in all_results:
            row = {
                "query": query_text,
                "name": item.get("name", ""),
                "lat": item.get("location", {}).get("lat", ""),
                "lng": item.get("location", {}).get("lng", ""),
                "address": item.get("address", ""),
                "province": item.get("province", ""),
                "city": item.get("city", ""),
                "area": item.get("area", ""),
                "telephone": item.get("telephone", ""),
                "detail": item.get("detail", ""),
                "uid": item.get("uid", ""),
                "street_id": item.get("street_id", "")
            }
            writer.writerow(row)

    print(f"\n成功保存 {len(all_results)} 条记录到: {output_file}")

def main():
    parser = argparse.ArgumentParser(description="百度地图 POI 查询工具")
    parser.add_argument("-a", "--ak", default=DEFAULT_AK, help="百度地图 AK（默认内置）")
    parser.add_argument("-r", "--region", required=True, help="查询城市，如 南京市")
    parser.add_argument("-q", "--query", default="", help="查询关键词，如 小区")
    parser.add_argument("-f", "--file", default="", help="查询词文件，每行一个地名")
    parser.add_argument("-o", "--output", default="", help="输出文件名")
    parser.add_argument("-d", "--delay", type=float, default=0.5, help="请求间隔秒数")
    args = parser.parse_args()

    queries = []
    if args.file:
        queries = read_queries_from_file(args.file)
        print(f"从文件 {args.file} 读取到 {len(queries)} 个查询词")
    elif args.query:
        queries = [args.query]
        print(f"查询关键词: {args.query}")
    else:
        print("请指定 --query 或 --file")
        return

    if not args.output:
        args.output = f"poi_results_{args.region}.csv"

    all_results = []
    total_count = 0

    for i, q in enumerate(queries, 1):
        print(f"\n[{i}/{len(queries)}] 查询: {q}")
        results = fetch_all_pages(args.ak, q, args.region, args.delay)
        for item in results:
            all_results.append((q, item))
        total_count += len(results)

    print(f"\n全部完成，共获取 {total_count} 条记录")
    save_results_to_csv(all_results, args.output)

if __name__ == "__main__":
    main()

