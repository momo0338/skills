# -*- coding: utf-8 -*-
import os
import requests
import re
import json
import time
import argparse

DEFAULT_AK = os.environ.get("BAIDU_MAP_AK", "")  # 凭据不入库，用环境变量注入
import sys as _sys
if not DEFAULT_AK:
    _sys.exit("请先注入百度地图 AK：export BAIDU_MAP_AK=<你的AK>，或显式传 --ak <AK>")

def meter2Degree(x, y, ak):
    url = "http://api.map.baidu.com/geoconv/v1/?coords=" + x + "," + y + "&from=6&to=5&output=json&ak=" + ak
    header = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    response = requests.get(url, headers=header, timeout=10)
    answer = response.json()
    result = answer.get("result", [])
    if not result:
        return None, None
    return result[0]["x"], result[0]["y"]

def coordinateToPoints(coordinates, ak):
    points = ""
    if not coordinates or "-" not in coordinates:
        return points
    parts = coordinates.split("-")
    if len(parts) < 2:
        return points
    temp_coordinates = parts[1].replace(";", "").split(",")
    temp_points = []
    for i in range(0, len(temp_coordinates) - 1, 2):
        try:
            x = temp_coordinates[i].strip()
            y = temp_coordinates[i + 1].strip()
            temp_points.append({"x": x, "y": y})
        except (ValueError, IndexError):
            continue

    for point in temp_points:
        lng, lat = meter2Degree(point["x"], point["y"], ak)
        if lng is not None and lat is not None:
            points += str(lng) + "," + str(lat) + ";"

    return points

def searchPlace(name, ak, region="全国"):
    url = "http://api.map.baidu.com/place/v2/search"
    params = {
        "query": name,
        "region": region,
        "output": "json",
        "ak": ak
    }
    header = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    try:
        response = requests.get(url, params=params, headers=header, timeout=10)
        result = response.json()
        results = result.get("results", [])
        if results:
            return results[0]
    except Exception as e:
        print(f"搜索失败: {e}")
    return None

def getBorder(uid, ak):
    url = "http://map.baidu.com/?pcevaname=pc4.1&qt=ext&ext_ver=new&l=12&uid=" + uid
    header = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    try:
        response = requests.get(url, headers=header, timeout=10)
        answer = response.json()
        content = answer.get("content", {})
        if not content:
            return ""
        geo = content.get("geo", "")
        if geo:
            return coordinateToPoints(geo, ak)
    except Exception as e:
        print(f"  获取边界失败 uid={uid}: {e}")
    return ""

def read_input_text(filepath):
    names = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = re.split(r'[，,\s、;；]+', line)
            for p in parts:
                p = p.strip()
                if p:
                    names.append(p)
    return names

def save_geojson(results, output_file):
    features = []
    for row in results:
        border_points = row.get("border_points", "").strip()
        if not border_points:
            continue

        points_list = border_points.rstrip(";").split(";")
        coords = []
        for p in points_list:
            p = p.strip()
            if "," in p:
                try:
                    lng, lat = p.split(",")
                    coords.append([float(lng), float(lat)])
                except ValueError:
                    continue

        if len(coords) < 3:
            continue

        if coords[0] != coords[-1]:
            coords.append(coords[0])

        center_lng = sum(c[0] for c in coords) / len(coords)
        center_lat = sum(c[1] for c in coords) / len(coords)

        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [coords]
            },
            "properties": {
                "name": row.get("name", "").strip(),
                "uid": row.get("uid", "").strip(),
                "center": [center_lng, center_lat]
            }
        }
        features.append(feature)

    geojson = {
        "type": "FeatureCollection",
        "features": features
    }

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(geojson, f, ensure_ascii=False)

    print(f"成功转换 {len(features)} 个多边形到: {output_file}")

def main():
    parser = argparse.ArgumentParser(description="百度地图小区边界获取工具")
    parser.add_argument("-a", "--ak", default=DEFAULT_AK, help="百度地图 AK（默认内置）")
    parser.add_argument("-i", "--input", default="", help="输入文本文件（每行一个或多个地名，支持空格、逗号、顿号分隔）")
    parser.add_argument("-o", "--output", default="", help="输出文件名（默认自动命名）")
    parser.add_argument("-d", "--delay", type=float, default=1.0, help="请求间隔秒数")
    parser.add_argument("--no-geojson", action="store_true", help="不输出 GeoJSON 文件")
    parser.add_argument("-s", "--search", help="搜索单个地点名称并获取边界")
    parser.add_argument("-r", "--region", default="全国", help="搜索区域（默认全国）")
    args = parser.parse_args()

    if not args.search and not args.input:
        print("错误: 需要提供 -s/--search 或 -i/--input 参数")
        return

    if args.search:
        print(f"正在搜索: {args.search} (区域: {args.region})")
        result = searchPlace(args.search, args.ak, args.region)
        if result:
            uid = result.get("uid", "")
            name = result.get("name", "")
            print(f"找到: {name} (uid={uid})")
            if uid:
                points = getBorder(uid, args.ak)
                if points:
                    base_name = name.replace("/", "_").replace(" ", "_")
                    geojson_output = base_name + "_border.geojson"

                    if not args.no_geojson:
                        save_geojson([{"name": name, "uid": uid, "border_points": points}], geojson_output)

                    print("\n完成！")
                else:
                    print("未获取到边界信息")
            else:
                print("未找到 uid")
        else:
            print("未找到搜索结果")
        return

    names = read_input_text(args.input)
    if not names:
        print("输入文件为空或格式不正确")
        return

    if not args.output:
        base_name = args.input.rsplit(".", 1)[0]
        geojson_output = base_name + "_border.geojson"
    else:
        geojson_output = args.output.replace(".csv", ".geojson").replace(".txt", ".geojson")

    print(f"读取到 {len(names)} 个地名，开始获取边界...")

    results = []

    for i, name in enumerate(names, 1):
        print(f"[{i}/{len(names)}] {name}")
        result = searchPlace(name, args.ak, args.region)
        if result:
            uid = result.get("uid", "")
            actual_name = result.get("name", name)
            print(f"  找到: {actual_name} (uid={uid[:8]}...)")
            if uid:
                points = getBorder(uid, args.ak)
                if points:
                    results.append({"name": actual_name, "uid": uid, "border_points": points})
                else:
                    print(f"  未获取到边界信息")
            time.sleep(args.delay)
        else:
            print(f"  未找到搜索结果")
            time.sleep(args.delay)

    if not args.no_geojson:
        save_geojson(results, geojson_output)

    print("\n完成！")

if __name__ == "__main__":
    main()

