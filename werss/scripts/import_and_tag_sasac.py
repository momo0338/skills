import urllib.request, urllib.parse, json, time, base64, csv, io, datetime, uuid, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from werss.client import load_config, get_data_dir

BASE_URL, AK, SK = load_config()
AUTH_HEADER = {'Authorization': f'AK-SK {AK}:{SK}'}
DATA_DIR = get_data_dir()

with open(DATA_DIR / 'sasac_matched.json', 'r', encoding='utf-8') as f:
    accounts = json.load(f)

# 添加湖南的融媒体官方平台“国资潇湘”作为高权重补充
accounts.append({
    "province": "湖南(融媒体)",
    "mp_name": "国资潇湘",
    "alias": "HUNAN-SASAC",
    "fakeid": "MzI1MDc0NDYwMw==",
    "mp_id": "MP_WXS_3250744603",
    "cover": "http://mmbiz.qpic.cn/mmbiz_png/MUqzc3wqSv3UCCQeSTQcjIGXf9Edle9PZjHPcLW3yEO0NL6Kbqr3MjBC73FZN0iaGvYHgiaHMicLSKgMxSaqHxm5Q/0?wx_fmt=png",
    "signature": "始于国资，扎根潇湘。湖南经济发展的记录者和观察者。本平台内容是在湖南省国资委指导下，由中央广播电视总台湖南总站监督制作。",
    "verify_status": 2,
    "service_type": 1
})

print(f"Total SASAC accounts to import: {len(accounts)}")

# 1. 构建与 WeRSS export/mps/import 完全兼容的 CSV
lines = ["id,公众号名称,封面图,简介,状态,创建时间,faker_id"]
now_str = datetime.datetime.now().isoformat()

for a in accounts:
    mp_id = a['mp_id']
    name = a['mp_name']
    cover = a.get('cover', '')
    intro = a.get('signature', '').replace('\r', ' ').replace('\n', ' ').replace(',', '，')
    fid = a['fakeid']
    lines.append(f"{mp_id},{name},{cover},{intro},1,{now_str},{fid}")

csv_content = "\r\n".join(lines) + "\r\n"

boundary = uuid.uuid4().hex
body = (
    f"--{boundary}\r\n"
    f"Content-Disposition: form-data; name=\"file\"; filename=\"sasac_mps.csv\"\r\n"
    f"Content-Type: text/csv; charset=utf-8\r\n\r\n"
    f"{csv_content}\r\n"
    f"--{boundary}--\r\n"
).encode("utf-8")

headers = {
    'Authorization': f'AK-SK {AK}:{SK}',
    'Content-Type': f'multipart/form-data; boundary={boundary}',
    'Content-Length': str(len(body))
}

print("正在通过 WeRSS 批量导入接口导入全国省级国资委公众号...")
req = urllib.request.Request(f"{BASE_URL}/api/v1/wx/export/mps/import", data=body, headers=headers, method='POST')
with urllib.request.urlopen(req) as resp:
    res = json.loads(resp.read().decode())
    print("导入响应:", res)

# 2. 检查并创建标签“全国省级国资委”
tag_id = None
req_tags = urllib.request.Request(f"{BASE_URL}/api/v1/wx/tags", headers=AUTH_HEADER)
with urllib.request.urlopen(req_tags) as resp:
    tags_data = json.loads(resp.read().decode()).get('data', {}).get('list', [])
    for t in tags_data:
        if t.get('name') in ['全国省级国资委', '省级国资委', '国资委']:
            tag_id = t.get('id')
            print(f"找到已有标签: {t.get('name')} (ID: {tag_id})")
            break

all_sasac_mp_ids = list(set([a['mp_id'] for a in accounts if a.get('mp_id')]))
print(f"准备向标签写入 {len(all_sasac_mp_ids)} 个公众号...")

tag_payload = json.dumps({
    "name": "全国省级国资委",
    "intro": "全国31个省/直辖市/自治区国资委、兵团国资委及国务院国资委官方公众号（含国企招聘专栏合集）",
    "mps_id": json.dumps(all_sasac_mp_ids),
    "status": 1
}).encode('utf-8')

if not tag_id:
    print("创建新标签: 全国省级国资委...")
    req_new_tag = urllib.request.Request(
        f"{BASE_URL}/api/v1/wx/tags",
        data=tag_payload,
        headers={**AUTH_HEADER, 'Content-Type': 'application/json'},
        method='POST'
    )
    with urllib.request.urlopen(req_new_tag) as resp:
        t_res = json.loads(resp.read().decode())
        tag_id = t_res.get('data', {}).get('id')
        print(f"标签创建成功: {tag_id}")
else:
    print(f"更新已有标签 {tag_id}...")
    req_put_tag = urllib.request.Request(
        f"{BASE_URL}/api/v1/wx/tags/{tag_id}",
        data=tag_payload,
        headers={**AUTH_HEADER, 'Content-Type': 'application/json'},
        method='PUT'
    )
    with urllib.request.urlopen(req_put_tag) as resp:
        put_res = json.loads(resp.read().decode())
        print("标签更新响应:", put_res)

# 3. 生成规范的 CSV 交付文件
csv_file_path = str(DATA_DIR / 'provincial_sasac_mps.csv')
with open(csv_file_path, 'w', encoding='utf-8-sig', newline='') as f:
    out_writer = csv.writer(f)
    out_writer.writerow([
        '省份/行政区',
        '机构定位',
        '官方公众号名称',
        '微信号(ID)',
        'WeRSS内部ID',
        '微信Base64_FakeID',
        '官方头像Logo直链',
        '官方关注二维码直链',
        '独立RSS源链接',
        '官方认证状态',
        '官方简介与特色'
    ])
    for a in accounts:
        feed_url = f"{BASE_URL}/feed/{a['mp_id']}.xml" if a.get('mp_id') else ""
        qr_code = f"https://open.weixin.qq.com/qr/code?username={a['alias']}" if a.get('alias') else ""
        org_title = f"{a['province']}国资监管机构" if not a['province'].startswith('中央') else "国务院直属特设机构"
        out_writer.writerow([
            a['province'],
            org_title,
            a['mp_name'],
            a['alias'] or '暂未设置微信号',
            a['mp_id'],
            a['fakeid'],
            a['cover'],
            qr_code,
            feed_url,
            "官方机构认证(政务/事业单位)" if a.get('verify_status') == 2 else "企业认证",
            a.get('signature', '')
        ])

print(f"交付文件已生成: {csv_file_path}")
