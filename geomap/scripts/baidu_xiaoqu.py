# -*- coding: utf-8 -*-

import os
import csv
import numpy as np
import requests
import time, math
import argparse

DEFAULT_AK = os.environ.get("BAIDU_MAP_AK", "")  # 凭据不入库，用环境变量注入
import sys as _sys
if not DEFAULT_AK:
    _sys.exit("请先注入百度地图 AK：export BAIDU_MAP_AK=<你的AK>，或显式传 --ak <AK>")

parser = argparse.ArgumentParser(description="百度地图小区批量抓取工具")
parser.add_argument("-a", "--ak", default=DEFAULT_AK, help="百度地图 AK")
parser.add_argument("-o", "--output", default="community.csv", help="输出文件名")
parser.add_argument("-u", "--unit", type=int, default=60, help="栅格数量")
parser.add_argument("--lat-min", type=float, default=32.006867)
parser.add_argument("--lat-max", type=float, default=32.014927)
parser.add_argument("--lng-min", type=float, default=118.717349)
parser.add_argument("--lng-max", type=float, default=118.728725)
parser.add_argument("--i-start", type=int, default=0)
parser.add_argument("--i-end", type=int, default=59)
parser.add_argument("--j-start", type=int, default=0)
parser.add_argument("--j-end", type=int, default=59)
args = parser.parse_args()

ak = args.ak
output_file = args.output

lat_partion = [round(x, 6) for x in list(np.linspace(args.lat_min, args.lat_max, args.unit))]
lng_partion = [round(y, 6) for y in list(np.linspace(args.lng_min, args.lng_max, args.unit))]

fieldnames = ["province", "city", "area", "community", "address", "lat", "lng", "uid", "detail"]

with open(output_file, "w", newline="", encoding="utf-8-sig") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()

    print(f"开始抓取小区数据，结果保存到 {output_file}\n")

    def get_community():
        for i in range(args.i_start, args.i_end):
            for j in range(args.j_start, args.j_end):
                not_max_page = True
                page_num = 0

                while not_max_page:
                    url = f"http://api.map.baidu.com/place/v2/search?query=小区&page_size=20&page_num={page_num}&bounds={lat_partion[i]},{lng_partion[j]},{lat_partion[i+1]},{lng_partion[j+1]}&output=json&ak={ak}"
                    header = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/70.0.3538.77 Safari/537.36'}
                    response = requests.get(url, headers = header)
                    time.sleep(1)

                    answer = response.json()
                    total = answer.get("total", 0)
                    max_page = math.ceil(total / 20)

                    if answer.get('status') == 0 and 'results' in answer:
                        print("\n# Rectangle (%d,%d)  Page %s" % (i, j, page_num))
                        print("# Amount: %s" % len(answer['results']))
                        print("# Total: %s" % total)

                        page_num += 1
                        if page_num > max_page:
                            break

                        for k in range(len(answer['results'])):
                            province = answer['results'][k]['province']
                            if province == "澳门特别行政区":
                                break
                            city = answer['results'][k]['city']
                            area = answer['results'][k]['area']
                            community = answer['results'][k]['name']
                            address = answer['results'][k]['address']
                            lat = answer['results'][k]['location']['lat']
                            lng = answer['results'][k]['location']['lng']
                            uid = answer['results'][k]['uid']
                            detail = answer['results'][k]['detail']
                            row = {"province": province, "city": city, "area": area, "community": community, "address": address, "lat": lat, "lng": lng, "uid": uid, "detail": detail}
                            print(row)
                            writer.writerow(row)
                            f.flush()
                    else:
                        print("* The rectangle (%d,%d) contains no community"%(i, j))
                        break

    if __name__=='__main__':
        get_community()
        print(f"\n完成，数据已保存到 {output_file}")

