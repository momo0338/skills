import urllib.request, urllib.parse, json, time, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from werss.client import load_config

BASE_URL, AK, SK = load_config()
AUTH_HEADER = {'Authorization': f'AK-SK {AK}:{SK}'}

PROVINCES = [
    {"province": "中央/国务院", "target": "国务院国资委", "queries": ["国资小新", "国务院国资委"], "expected": "国资小新"},
    {"province": "北京", "target": "北京市国资委", "queries": ["北京国资", "北京市国资委", "国资京京"], "expected": "国资京京"},
    {"province": "天津", "target": "天津市国资委", "queries": ["天津国资", "天津市国资委"], "expected": "天津国资"},
    {"province": "河北", "target": "河北省国资委", "queries": ["河北国资", "河北省国资委"], "expected": "河北国资"},
    {"province": "山西", "target": "山西省国资委", "queries": ["山西国资", "山西省国资委"], "expected": "山西国资"},
    {"province": "内蒙古", "target": "内蒙古自治区国资委", "queries": ["内蒙古国资", "内蒙古国资委"], "expected": "内蒙古国资"},
    {"province": "辽宁", "target": "辽宁省国资委", "queries": ["辽宁国资", "辽宁省国资委"], "expected": "辽宁国资"},
    {"province": "吉林", "target": "吉林省国资委", "queries": ["吉林国资", "吉林省国资委", "吉林省人民政府国有资产"], "expected": "吉林国资"},
    {"province": "黑龙江", "target": "黑龙江省国资委", "queries": ["龙江国资", "黑龙江国资", "黑龙江省国资委"], "expected": "龙江国资"},
    {"province": "上海", "target": "上海市国资委", "queries": ["上海国资", "上海市国资委"], "expected": "上海国资"},
    {"province": "江苏", "target": "江苏省国资委", "queries": ["江苏国资", "江苏省国资委"], "expected": "江苏国资"},
    {"province": "浙江", "target": "浙江省国资委", "queries": ["浙江国资", "浙江省国资委"], "expected": "浙江国资"},
    {"province": "安徽", "target": "安徽省国资委", "queries": ["安徽国资", "安徽省国资委"], "expected": "安徽国资"},
    {"province": "福建", "target": "福建省国资委", "queries": ["八闽国资", "福建国资", "福建省国资委"], "expected": "八闽国资"},
    {"province": "江西", "target": "江西省国资委", "queries": ["江西国资", "江西省国资委"], "expected": "江西国资"},
    {"province": "山东", "target": "山东省国资委", "queries": ["山东国资资讯", "山东国资", "山东省国资委"], "expected": "山东国资资讯"},
    {"province": "河南", "target": "河南省国资委", "queries": ["河南国资", "河南省国资委"], "expected": "河南国资"},
    {"province": "湖北", "target": "湖北省国资委", "queries": ["湖北国资", "湖北省国资委"], "expected": "湖北国资"},
    {"province": "湖南", "target": "湖南省国资委", "queries": ["湖南国资", "国资潇湘", "湖南省国资委"], "expected": "湖南国资"},
    {"province": "广东", "target": "广东省国资委", "queries": ["广东国资", "广东省国资委"], "expected": "广东国资"},
    {"province": "广西", "target": "广西壮族自治区国资委", "queries": ["广西国资", "广西国资委"], "expected": "广西国资"},
    {"province": "海南", "target": "海南省国资委", "queries": ["海南国资", "海南省国资委"], "expected": "海南国资"},
    {"province": "重庆", "target": "重庆市国资委", "queries": ["重庆国资", "重庆市国资委"], "expected": "重庆国资"},
    {"province": "四川", "target": "四川省国资委", "queries": ["四川国资", "四川省国资委"], "expected": "四川国资"},
    {"province": "贵州", "target": "贵州省国资委", "queries": ["贵州国资", "贵州省国资委"], "expected": "贵州国资"},
    {"province": "云南", "target": "云南省国资委", "queries": ["云南国资", "云南省国资委"], "expected": "云南国资"},
    {"province": "西藏", "target": "西藏自治区国资委", "queries": ["西藏国资委", "西藏国资"], "expected": "西藏国资委"},
    {"province": "陕西", "target": "陕西省国资委", "queries": ["陕西国资", "陕西省国资委"], "expected": "陕西国资"},
    {"province": "甘肃", "target": "甘肃省国资委", "queries": ["甘肃国资", "甘肃省国资委"], "expected": "甘肃国资"},
    {"province": "青海", "target": "青海省国资委", "queries": ["青海经信委", "青海国资", "青海国投"], "expected": "青海经信委"},
    {"province": "宁夏", "target": "宁夏回族自治区国资委", "queries": ["宁夏国资", "宁夏国资委"], "expected": "宁夏国资"},
    {"province": "新疆", "target": "新疆维吾尔自治区国资委", "queries": ["新疆国资", "新疆国资委"], "expected": "新疆国资"},
    {"province": "新疆兵团", "target": "新疆生产建设兵团国资委", "queries": ["兵团国资", "兵团国资委"], "expected": "兵团国资"}
]

def search_kw(kw):
    url = f'{BASE_URL}/api/v1/wx/mps/search/{urllib.parse.quote(kw)}?limit=6&offset=0'
    req = urllib.request.Request(url, headers=AUTH_HEADER)
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read().decode())
            return data.get('data', {}).get('list', [])
    except Exception as e:
        return []

def score_item(item, prov_info):
    name = item.get('nickname', '')
    sign = item.get('signature', '')
    alias = item.get('alias', '')
    verify = item.get('verify_status', 0)
    expected = prov_info.get('expected', '')
    prov = prov_info['province']
    
    score = 0
    # 命中期望名字
    if name == expected:
        score += 150
    elif expected in name:
        score += 80
        
    # 官方认证
    if verify == 2:
        score += 50
    elif verify == 0:
        score -= 40
        
    # 关键词加分
    combined = (name + ' ' + sign).lower()
    if '国资委' in combined or '国有资产监督管理' in combined:
        score += 40
    if '省国资委' in combined or '自治区国资委' in combined or '市国资委' in combined:
        score += 30
    if '官方' in combined or '权威' in combined or '订阅号' in combined:
        score += 15
        
    # 扣分项：地级市/区县（当不是直辖市时）
    city_penalties = ['朝阳', '温州', '苏州', '广州', '珠海', '成都', '武汉', '哈尔滨', '长春', '南宁', '青岛', '大连', '宁波', '厦门', '深圳', '无锡', '常州', '佛山', '东莞', '烟台', '唐山', '徐州', '赣州', '九江', '洛阳', '宜昌', '襄阳', '绵阳', '芜湖', '泉州', '漳州', '柳州', '桂林', '包头']
    if prov not in ['北京', '上海', '天津', '重庆']:
        for cp in city_penalties:
            if cp in name:
                score -= 60
                
    # 扣分项：第三方培训机构/招聘中介
    if '非官方' in sign or '公益性分享' in sign or '事业单位招聘' in name or '考试' in sign or '网校' in sign or '教育' in sign:
        score -= 100
        
    # 扣分项：纯企业而非监管部门（除非特定兜底）
    if '有限公司' in name or '股份公司' in name or '集团有限公司' in name:
        score -= 30
        
    return score

results = []
for p in PROVINCES:
    candidates = {}
    for q in p['queries']:
        items = search_kw(q)
        time.sleep(0.3)
        for it in items:
            fid = it.get('fakeid')
            if fid and fid not in candidates:
                candidates[fid] = it
    scored = []
    for it in candidates.values():
        s = score_item(it, p)
        scored.append((s, it))
    scored.sort(key=lambda x: x[0], reverse=True)
    best = scored[0] if scored else (0, None)
    results.append({
        'province': p['province'],
        'target': p['target'],
        'best': best[1],
        'score': best[0]
    })

print(f"{'省份':<8} | {'最佳匹配':<16} | {'微信号':<15} | {'得分':<5} | {'简介'}")
print("-" * 80)
for r in results:
    b = r['best']
    if b:
        print(f"{r['province']:<8} | {b.get('nickname'):<16} | {b.get('alias') or 'None':<15} | {r['score']:<5} | {b.get('signature')[:30]}")
    else:
        print(f"{r['province']:<8} | {'未找到':<16} | {'':<15} | {0:<5} |")

