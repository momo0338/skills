import urllib.request, urllib.parse, json, time, base64, csv, io, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from werss.client import load_config, get_data_dir

BASE_URL, AK, SK = load_config()
AUTH_HEADER = {'Authorization': f'AK-SK {AK}:{SK}'}
DATA_DIR = get_data_dir()

# 全国 31 个省/直辖市/自治区 + 新疆兵团 + 国务院国资委
PROVINCIAL_TARGETS = [
    {"province": "中央/国务院", "search_kw": "国资小新", "expected_name": "国资小新"},
    {"province": "北京", "search_kw": "国资京京", "expected_name": "国资京京"},
    {"province": "天津", "search_kw": "天津国资", "expected_name": "天津国资"},
    {"province": "河北", "search_kw": "河北国资", "expected_name": "河北国资"},
    {"province": "山西", "search_kw": "山西国资", "expected_name": "山西国资"},
    {"province": "内蒙古", "search_kw": "内蒙古国资", "expected_name": "内蒙古国资"},
    {"province": "辽宁", "search_kw": "辽宁国资", "expected_name": "辽宁国资"},
    {"province": "吉林", "search_kw": "吉林国资", "expected_name": "吉林国资"},
    {"province": "黑龙江", "search_kw": "龙江国资", "expected_name": "龙江国资"},
    {"province": "上海", "search_kw": "上海国资", "expected_name": "上海国资"},
    {"province": "江苏", "search_kw": "江苏国资", "expected_name": "江苏国资"},
    {"province": "浙江", "search_kw": "浙江国资", "expected_name": "浙江国资"},
    {"province": "安徽", "search_kw": "安徽国资", "expected_name": "安徽国资"},
    {"province": "福建", "search_kw": "八闽国资", "expected_name": "八闽国资"},
    {"province": "江西", "search_kw": "江西国资", "expected_name": "江西国资"},
    {"province": "山东", "search_kw": "山东国资资讯", "expected_name": "山东国资资讯"},
    {"province": "河南", "search_kw": "河南国资", "expected_name": "河南国资"},
    {"province": "湖北", "search_kw": "湖北国资", "expected_name": "湖北国资"},
    {"province": "湖南", "search_kw": "湖南国资", "expected_name": "湖南国资"},
    {"province": "广东", "search_kw": "广东国资", "expected_name": "广东国资"},
    {"province": "广西", "search_kw": "广西国资", "expected_name": "广西国资"},
    {"province": "海南", "search_kw": "海南国资", "expected_name": "海南国资"},
    {"province": "重庆", "search_kw": "重庆国资", "expected_name": "重庆国资"},
    {"province": "四川", "search_kw": "四川国资", "expected_name": "四川国资"},
    {"province": "贵州", "search_kw": "贵州国资", "expected_name": "贵州国资"},
    {"province": "云南", "search_kw": "云南国资", "expected_name": "云南国资"},
    {"province": "西藏", "search_kw": "西藏国资委", "expected_name": "西藏国资委"},
    {"province": "陕西", "search_kw": "陕西国资", "expected_name": "陕西国资"},
    {"province": "甘肃", "search_kw": "甘肃国资", "expected_name": "甘肃国资"},
    {"province": "青海", "search_kw": "青海经信委", "expected_name": "青海经信委"},
    {"province": "宁夏", "search_kw": "宁夏国资", "expected_name": "宁夏国资"},
    {"province": "新疆", "search_kw": "新疆国资", "expected_name": "新疆国资"},
    {"province": "新疆兵团", "search_kw": "兵团国资", "expected_name": "兵团国资"}
]

def werss_search(kw):
    url = f"{BASE_URL}/api/v1/wx/mps/search/{urllib.parse.quote(kw)}?limit=5&offset=0"
    req = urllib.request.Request(url, headers=AUTH_HEADER)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            return data.get('data', {}).get('list', [])
    except Exception as e:
        print(f"  [Search Error for {kw}]: {e}")
        return []

matched_accounts = []

print(f"=== 开始通过 WeRSS 内部搜索接口精准检索全国省级国资委公众号 ===")
for target in PROVINCIAL_TARGETS:
    prov = target['province']
    kw = target['search_kw']
    expected = target['expected_name']
    
    hits = werss_search(kw)
    time.sleep(0.5)
    
    selected = None
    if hits:
        # 优先完全匹配名字
        for h in hits:
            if h.get('nickname') == expected:
                selected = h
                break
        if not selected:
            # 次优选包含名字且认证过的
            for h in hits:
                if expected in h.get('nickname', '') and h.get('verify_status') == 2:
                    selected = h
                    break
        if not selected and hits:
            selected = hits[0]
            
    if selected:
        fid = selected.get('fakeid', '')
        # 解码 fakeid 得到纯数字 mp_id
        num_id = ""
        try:
            num_id = base64.b64decode(fid).decode('utf-8')
        except:
            num_id = ""
        mp_id_formatted = f"MP_WXS_{num_id}" if num_id else ""
        
        info = {
            "province": prov,
            "mp_name": selected.get('nickname'),
            "alias": selected.get('alias', ''),
            "fakeid": fid,
            "mp_id": mp_id_formatted,
            "cover": selected.get('round_head_img', ''),
            "signature": selected.get('signature', ''),
            "verify_status": selected.get('verify_status', 0),
            "service_type": selected.get('service_type', 0)
        }
        matched_accounts.append(info)
        print(f"  ✓ [{prov}] 匹配成功: {info['mp_name']} (微信号: {info['alias'] or '无'}, ID: {info['mp_id']}, 认证: {info['verify_status']})")
    else:
        print(f"  ✗ [{prov}] 未能检索到结果 (关键词: {kw})")

print(f"\n检索完成，共成功匹配 {len(matched_accounts)} / {len(PROVINCIAL_TARGETS)} 个省级国资公众号。")

# 保存为临时结果
with open(DATA_DIR / 'sasac_matched.json', 'w', encoding='utf-8') as f:
    json.dump(matched_accounts, f, ensure_ascii=False, indent=2)

