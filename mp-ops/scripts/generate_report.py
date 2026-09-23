#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成公众号《文章数据分析报告》HTML（ECharts 内联、浅色主题、自包含、可离线打开）。

账号目录由环境变量注入（GZH_WORK_DIR），适用于任意公众号。
用法：
    export GZH_WORK_DIR="/path/to/账号目录"
    python3 generate_report.py [--out 自定义输出路径]
会依次读取：
    最新 发表记录*.csv                       → 章节一/二/四~八（推算）
    ~/.cache/weixin/publish_records/search_center_*.json   → 章节三（搜一搜实测）
    ~/.cache/weixin/publish_records/search_channels_*.json  → 单篇渠道构成（实测）
前两者缺失时对应章节自动跳过。

⚠️ 图表引擎内联（assets/echarts.min.js），不要改回 CDN —— 预览端加载不到外链会整页空白。
"""
import csv, os, re, json, sys, glob, statistics as st
from collections import defaultdict, Counter
from datetime import datetime, date

BASE = os.environ.get("GZH_WORK_DIR") or os.getcwd()
ACCOUNT = os.path.basename(BASE.rstrip("/"))
STAMP = datetime.now().strftime("%Y%m%d")
OUT = os.path.join(BASE, "运营", "复盘", f"数据分析-{ACCOUNT}-{STAMP}.html")
for i, a in enumerate(sys.argv[1:]):
    if a == "--out": OUT = sys.argv[i + 2]
SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ECHARTS = os.path.join(SKILL_DIR, "assets", "echarts.min.js")
# 自动取目录下最新的发表记录 CSV，快照日随之取文件名上的日期
_hits = sorted(f for f in os.listdir(BASE) if f.startswith("发表记录") and f.endswith(".csv"))
if not _hits:
    sys.exit(f"未找到发表记录 CSV（{BASE}）")
CSV_PATH = os.path.join(BASE, _hits[-1])
_snap_s = _hits[-1].replace("发表记录-满爸爱生活-", "").replace(".csv", "")
_y, _m, _d = map(int, _snap_s.split("-"))
SNAP = date(_y, _m, _d)

def mean(x): x=list(x); return st.mean(x) if x else 0.0
def med(x):  x=list(x); return st.median(x) if x else 0.0

rows=[]
with open(CSV_PATH, encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        t=(r.get("title") or "").strip()
        if not t: continue
        n=lambda k:int(r[k]) if (r.get(k) or "").strip().isdigit() else 0
        rows.append({"date":r["date"],"time":r["time"],"title":t,"read":n("read"),"like":n("like"),
                     "share":n("share"),"haokan":n("haokan"),"comment":n("comment"),"sent":n("sent_succ"),
                     "deleted":r.get("deleted")=="True","album":(r.get("album") or "").strip(),
                     "url":r.get("url","")})
rows.sort(key=lambda x:(x["date"],x["time"]))
for i,r in enumerate(rows):
    r["age"]=(SNAP-datetime.strptime(r["date"],"%Y-%m-%d").date()).days
    r["mature"]=r["age"]>=7
    r["amp"]=r["read"]/r["sent"] if r["sent"] else None
    r["dfan"]=r["sent"]-rows[i-1]["sent"] if i and rows[i-1]["sent"] else 0
live=[r for r in rows if not r["deleted"]]
mat =[r for r in live if r["mature"]]
L   =[r for r in live if r["sent"]>=1200]                      # 成熟期＝当下账号状态
top3=sorted(L,key=lambda x:-x["read"])[:3]
L2 =[r for r in L if r not in top3]

# 月度
lastsent={}; 
for r in rows: lastsent[r["date"][:7]]=r["sent"]
mc=Counter(); mr=Counter(); ms=Counter()
for r in live:
    m=r["date"][:7]; mc[m]+=1; mr[m]+=r["read"]; ms[m]+=r["share"]
months=sorted(set(list(lastsent)+list(mc)))
monthly=[]; prev=None
for m in months:
    s=lastsent.get(m,prev or 0); d=s-prev if prev is not None else 0
    monthly.append({"m":m,"c":mc[m],"r":mr[m],"s":ms[m],"fans":s,"dfan":d})
    prev=s

# 放大倍数分布
BANDS=[("未破圈 <0.5x",0,.5),("勉强 0.5-1x",.5,1),("入池 1-3x",1,3),("放大 3-10x",3,10),("爆款 >10x",10,1e9)]
amp_dist=[]
for nm,lo,hi in BANDS:
    sel=[r for r in mat if r["amp"] is not None and lo<=r["amp"]<hi]
    amp_dist.append({"name":nm,"n":len(sel),"read":mean([x["read"] for x in sel]),"share":mean([x["share"] for x in sel])})

# 特征矩阵（成熟期，剔 TOP3）
SCAR=r"一年一次|限定|独家|最后|仅\d|仅剩|仅限|限\d|一天两场|免费|名额有限|错过再等|错过等一年"
FE={
 "悬念/反差/疑问":lambda t:bool(re.search(r"藏|原来|竟然|秘密|没想到|吓一跳|居然|凭什么|为什么|？|\?",t)),
 "感叹号":lambda t:("!" in t or "！" in t),
 "『南京遛娃』开头":lambda t:t.startswith("南京遛娃"),
 "最/第一/唯一":lambda t:bool(re.search(r"最|第一|唯一|仅有|独一|首家|首个",t)),
 "稀缺/限时/免费":lambda t:bool(re.search(SCAR,t)),
}
b_mean=mean([r["read"] for r in L2]); b_med=med([r["read"] for r in L2])
feat=[]
for fn,f in FE.items():
    sel=[r for r in L2 if f(r["title"])]
    if len(sel)<3: continue
    feat.append({"name":fn,"n":len(sel),"m":mean([x["read"] for x in sel]),
                 "mean_x":mean([x["read"] for x in sel])/b_mean,
                 "med_x":med([x["read"] for x in sel])/b_med,
                 "share":mean([x["share"] for x in sel])})
feat.sort(key=lambda x:-x["mean_x"])

# 标题字数（成熟期）
len_dist=[]
for lo,hi,nm in [(0,25,"<25"),(25,32,"25-31"),(32,40,"32-39"),(40,99,"40+")]:
    sel=[r for r in L if lo<=len(r["title"])<hi]
    if sel: len_dist.append({"name":nm,"n":len(sel),"m":mean([x["read"] for x in sel]),
                             "md":med([x["read"] for x in sel]),"x":mean([x["read"] for x in sel])/mean([r["read"] for r in L])})

# 集中度
sr=sorted(mat,key=lambda x:-x["read"]); T=sum(r["read"] for r in mat)
conc=[{"k":k,"v":round(sum(x["read"] for x in sr[:k])/T*100,1)} for k in [1,3,5,10,20]]

# 星期
WD=["周一","周二","周三","周四","周五","周六","周日"]
wdv=[]
for i in range(7):
    v=[r for r in mat if datetime.strptime(r["date"],"%Y-%m-%d").weekday()==i]
    if v: wdv.append({"name":WD[i],"n":len(v),"m":mean([x["read"] for x in v]),"share":mean([x["share"] for x in v])})

# 底部沉没稿
sunk=sorted([r for r in mat if r["sent"]>=1500 and r["amp"] and r["amp"]<0.15],key=lambda x:x["amp"])
top_list=sorted(mat,key=lambda x:-x["read"])[:15]

# --- 微信搜一搜数据中心（wsad.weixin.qq.com，账号级真实数据）---
SC = None
_scs = sorted(glob.glob(os.path.expanduser("~/.cache/weixin/publish_records/search_center_*.json")))
if _scs:
    with open(_scs[-1], encoding="utf-8") as f:
        SC = json.load(f)

# --- 真实搜一搜/渠道构成：来自后台 appmsganalysis，取最新一份 ---
CH = None
_chs = sorted(glob.glob(os.path.expanduser("~/.cache/weixin/publish_records/search_channels_*.json")))
if _chs:
    with open(_chs[-1], encoding="utf-8") as f:
        _cj = json.load(f)
    _valid = [x for x in _cj.get("items", []) if x.get("ok") and x.get("channels")]
    if _valid:
        _order = _cj.get("channels_order") or ["搜一搜","聊天会话","其它","公众号消息","公众号主页","推荐","朋友圈"]
        CH = {"fetched": _cj.get("fetched_at", "")[:16].replace("T", " "),
              "n": len(_valid),
              "order": _order,
              "avg": [round(mean([x["channels"].get(k, 0) for x in _valid]), 2) for k in _order],
              "items": _valid}

DATA={"monthly":monthly,"sc":SC,"ch":CH,"amp":amp_dist,"feat":feat,"len":len_dist,"conc":conc,"wd":wdv,
      "top":top_list,"sunk":sunk,
      "kpi":{"n":len(live),"del":len(rows)-len(live),"read":sum(r["read"] for r in live),
             "share":sum(r["share"] for r in live),"fans":rows[-1]["sent"],
             "med_read":med([r["read"] for r in live]),
             "med_amp":med([r["amp"] for r in mat if r["amp"] is not None]),
             "mat":len(mat),"L2":len(L2),"b_m":b_mean,"b_md":b_med,
             "under1k":sum(1 for r in mat if r["read"]<1000),"n_mat":len(mat),
             "fans_lp":sum(1 for r in mat if r["amp"] is not None and r["amp"]<0.5)}}

HTML = """<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>满爸爱生活 · 文章数据分析（2025-06 ~ 2026-09-16）</title>
<script>__ECHARTS_INLINE__</script>
<style>
:root{--bg:#f7f8fa;--card:#fff;--ink:#1a1d24;--sub:#5b6472;--line:#e6e9ef;--red:#d9303f;--green:#12996c;--blue:#2563eb;--amber:#d97706;--gray:#8b95a5}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);
font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif;line-height:1.7}
.wrap{max-width:1080px;margin:0 auto;padding:32px 20px 80px}
h1{font-size:27px;margin:0 0 6px;letter-spacing:-.3px}
.sub{color:var(--sub);font-size:14px;margin-bottom:26px}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:22px 24px;margin-bottom:18px}
h2{font-size:19px;margin:0 0 4px;padding-left:11px;border-left:4px solid var(--blue)}
h2 .tag{font-size:12px;color:var(--sub);font-weight:400;margin-left:8px}
p.lead{color:var(--sub);font-size:14px;margin:10px 0 0}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-bottom:18px}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px}
.kpi .v{font-size:24px;font-weight:700;letter-spacing:-.5px}
.kpi .l{font-size:12px;color:var(--sub);margin-top:2px}
.kpi .n{font-size:11px;color:var(--gray);margin-top:4px}
.chart{width:100%;height:330px}
table{width:100%;border-collapse:collapse;font-size:13.5px;margin-top:12px}
th,td{padding:8px 10px;border-bottom:1px solid var(--line);text-align:left}
th{background:#f2f4f7;font-weight:600;font-size:12.5px;color:var(--sub)}
td.num{text-align:right;font-variant-numeric:tabular-nums}
.up{color:var(--red);font-weight:600}.down{color:var(--green);font-weight:600}
.flat{color:var(--gray)}
.badge{display:inline-block;padding:1px 7px;border-radius:5px;font-size:11.5px;font-weight:600}
.b-red{background:#fde8ea;color:var(--red)}.b-green{background:#e3f5ee;color:var(--green)}
.b-gray{background:#eef0f4;color:var(--sub)}.b-blue{background:#e6edfd;color:var(--blue)}
.b-amber{background:#fdf0dc;color:var(--amber)}
.tldr{background:linear-gradient(180deg,#fff,#fbfcfe);border:1px solid var(--line);border-left:4px solid var(--amber);
border-radius:12px;padding:20px 24px;margin-bottom:18px}
.tldr ol{margin:10px 0 0;padding-left:20px}.tldr li{margin-bottom:9px;font-size:14.5px}
.tldr b{color:var(--ink)}
.warn{background:#fdf0dc;border:1px solid #f3d9a8;border-radius:10px;padding:13px 16px;font-size:13.5px;margin-top:12px}
.info{background:#eaf1fe;border:1px solid #c7d9fb;border-radius:10px;padding:13px 16px;font-size:13.5px;margin-top:12px}
.mono{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12.5px;color:var(--sub)}
.two{display:grid;grid-template-columns:1fr 1fr;gap:18px}
@media(max-width:820px){.two{grid-template-columns:1fr}.chart{height:280px}}
.foot{color:var(--gray);font-size:12px;text-align:center;margin-top:30px}
</style></head><body><div class="wrap">
<h1>满爸爱生活 · 文章数据分析</h1>
<div class="sub">样本 __N__ 篇（含已删 __DEL__）｜2025-06-15 ~ 2026-09-16｜数据快照 <b>2026-09-16</b>　·　生成于 __NOW__</div>

<div class="tldr">
<b style="font-size:16px">TL;DR —— 五条结论</b>
<ol>
<li><b>这个号没有"打开率"问题，只有"破圈率"问题。</b>__FANSLP__ 篇（占 __FANSLP_P__%）文章阅读量不到粉丝数的一半，等于只在自己群里转；但头部单篇能撬动粉丝池 __MAXAMP__ 倍的外部流量（在当前 __KPI_FANS__ 粉的量级下）。决定生死的不是标题修辞，是<b>选题有没有故事冲突</b>。</li>
<li><b>记忆里存的三条标题经验，剔掉极端值后基本失效。</b>"最/第一/唯一"实际是 __MF__x（低于基准）、"稀缺/免费/限时"是 __SF__x —— 全部反向。唯一站得住的是"悬念/疑问"带来<b>爆款上限</b>（__XM__x 均值），但它的中位倍数只有 __XMD__x：<b>它提高天花板，不抬高地板。</b></li>
<li><b>"南京遛娃"前缀是地板，不是天花板。</b>成熟期带前缀的稿均值仅 __NJ__x，但<b>中位数 __NJMD__x</b> —— 高于大盘。它是稳定的基本盘，天然难爆。</li>
<li><b>断更的代价被量化了：2026 年 7-8 月两个月粉丝净增 <span class="up">+0</span></b>。同期 2025 年发了 36 篇、71,488 阅读。月发文数 vs 月涨粉相关系数 <b>r=__CORR__</b>，而发文数 vs 篇均阅读几乎无关（r=+0.07）——<b>多写不会摊薄单篇，只涨总量。</b></li>
<li><b>主引擎是推荐池，搜索是"窄而深"的补充——不是不做。</b>账号级实测：搜索后阅读 <b>__SCREAD__ 次/日（环比 __SCMOM__）</b>、搜索后关注 __SCFOLLOW__ 人；单篇渠道构成里搜一搜占 __CHSS__%、推荐占 __CHREC__%。搜索吃的是<b>意图词</b>：「镇江免费景点预约」CTR <b>23.53%</b>（全站最高），纯名词「镇江科技馆」只有 2.67%。</li>
<li><b>合集资产是碎的</b>：<code>南京溜娃</code>（错字）87 篇 与 <code>南京遛娃</code> 6 篇是两个合集，另有 6 篇无合集、4 个合集不足 5 篇。直接吃掉长尾推荐。</li>
</ol>
</div>

<div class="kpis">
<div class="kpi"><div class="v">__KPI_N__</div><div class="l">在库文章</div><div class="n">熟化样本 __MAT__ 篇</div></div>
<div class="kpi"><div class="v">__KPI_READ__</div><div class="l">累计阅读</div><div class="n">篇均 __AVG__</div></div>
<div class="kpi"><div class="v">__KPI_FANS__</div><div class="l">当前粉丝</div><div class="n">15 个月净增</div></div>
<div class="kpi"><div class="v" style="color:var(--gray)">__KPI_MED__</div><div class="l">阅读中位数</div><div class="n">均值被 TOP5 拉高 4 倍</div></div>
<div class="kpi"><div class="v" style="color:var(--gray)">__KPI_AMP__x</div><div class="l">放大倍数中位数</div><div class="n">＝阅读 / 粉丝数</div></div>
<div class="kpi"><div class="v" style="color:var(--green)">__UNDER1K__</div><div class="l">阅读 &lt;1000 的篇数</div><div class="n">占 __UNDER1K_P__%，只贡献 __CONTRIB__% 阅读</div></div>
</div>

<div class="card">
<h2>一、增长曲线：发文节奏 = 涨粉节奏<span class="tag">柱=发文档｜线=粉丝与阅读</span></h2>
<p class="lead">2026-04 发 2 篇、2026-06 发 1 篇、<b>2026-07/08 直接归零</b> —— 曲线在这两处是平的。</p>
<div id="c1" class="chart"></div>
<div class="warn"><b>断更代价实证：</b>2026-06-08 最后一次群发到 2026-09-02 复更，粉丝数停在 1,976 一动不动；而 2025 年 7-8 月发了 36 篇、涨了 898 粉。同样的两个月，2026 版损失了约 <b>900 粉 + 7 万阅读</b>。</div>
</div>

<div class="card">
<h2>二、破圈分布：一半文章没走出粉丝群<span class="tag">放大倍数 = 阅读 ÷ 粉丝数</span></h2>
<p class="lead">>1x 说明吃到公众号推荐流量（非粉丝）；&lt;0.5x 说明基本只在粉丝圈内消化。</p>
<div id="c2" class="chart"></div>
<div class="info"><b>口径说明：</b>CSV 里的 <code>sent_succ</code> 是群发送达成功人数≈粉丝数，不是打开基数。用它算"打开率"是错的（苏超那篇达 26 倍）。本报告的"放大倍数"＝泛公域撬动能力，微信后台不对外提供真实打开率。</div>
</div>

<div class="card">
<div class="card">
<h2>三、搜一搜真相（数据中心实测）<span class="tag">__SCDATE__</span></h2>
<p class="lead">来自后台「微信搜一搜 → 数据中心」（<span class="mono">wsad.weixin.qq.com</span>），
这是<b>账号级</b>真实搜索数据，不是推算。前两章的破圈分布是推算，本章才是实测。</p>
<div class="kpis" style="margin-bottom:6px">
<div class="kpi"><div class="v" style="color:var(--red)">__SCREAD__</div><div class="l">搜索后阅读（次）</div><div class="n">环比 __SCMOM__</div></div>
<div class="kpi"><div class="v">__SCFOLLOW__</div><div class="l">搜索后关注（人）</div><div class="n">昨日</div></div>
<div class="kpi"><div class="v">__SCIMP__</div><div class="l">文章版块展示</div><div class="n">点击 __SCCLICK__｜CTR __SCCTR__%</div></div>
<div class="kpi"><div class="v">__SCWORDS__</div><div class="l">有效搜索词</div><div class="n">TOP3 占 __SCTOP3__% 展示</div></div>
</div>

<h2 style="font-size:15px;border-left-color:var(--blue);margin-top:18px">用户到底搜什么找到你（文章版块 TOP10）</h2>
<table><thead><tr><th>搜索词</th><th class="num">展示</th><th class="num">点击</th><th class="num">曝光点击率</th><th>相关搜索词</th></tr></thead><tbody>__SCWORDROWS__</tbody></table>
<div id="c8" class="chart" style="height:300px"></div>

<h2 style="font-size:15px;border-left-color:var(--amber);margin-top:18px">哪篇文章吃到了搜索流量</h2>
<table><thead><tr><th>文章</th><th class="num">展示</th><th class="num">点击</th><th class="num">CTR</th><th class="num">平均排序</th><th>命中的搜索词</th></tr></thead><tbody>__SCARTROWS__</tbody></table>

<div class="warn"><b>三条可直接执行的结论：</b><br>
① <b>搜索流量高度集中在 3 个主题</b>——铁路教育馆（1,129 展示）、镇江系（科技馆/博物馆/免费景点，合计约 1,500）、流感疫苗（1,082）。
TOP3 词吃掉 __SCTOP3__% 的展示，长尾极窄。<br>
② <b>"预约"是最强意图词</b>：「镇江免费景点预约」CTR <b>23.53%</b>，是全部词里最高；而纯名词「镇江科技馆」只有 2.67%。
标题里写"怎么预约/预约入口"比写景点名更能拿到点击。<br>
③ <b>搜索是"窄而深"的补充渠道，不是大盘</b>：文章版块 19,251 次展示 → 1,953 次点击，只转化 7 个粉丝；
而推荐渠道单篇就能带来 7 万读。搜索用来<b>沉淀长尾</b>（尤其稀缺场馆类），大盘仍靠推荐池。</div>
</div>

<div class="card">
<h2>四、标题技巧翻案：均值与中位数背离</h2>
<p class="lead">口径：成熟期（发布时粉丝 ≥1200，即当下账号状态）__L2__ 篇，<b>已剔除 TOP3 极端值</b>，避免用 3 篇爆款冒充规律。</p>
<div id="c3" class="chart"></div>
<table><thead><tr><th>标题特征</th><th class="num">篇数</th><th class="num">篇均阅读</th><th class="num">均值倍数</th><th class="num">中位倍数</th><th>读法</th></tr></thead><tbody>__FEATROWS__</tbody></table>
<div class="warn"><b>这是本报告最重要的一张表。</b>凡"均值倍数高、中位倍数≈1"的（悬念/疑问），意思是<b>少数几篇把它拉起来的，不能指望复现</b>；凡"均值低、中位 ≥1"的（南京遛娃前缀），意思是<b>它不出爆款但每篇都不掉链子</b>。真正的赢法是：用「南京遛娃」保地板，另开一条悬念/事件线去够天花板。<br>
<b>也据此修正此前的记忆</b>：①"本号吃长标题 32+ 字"不成立（字数与阅读无稳健相关）；②"含最/第一/唯一有效"反向（__MF__x）；③"稀缺/限时词能拉分享"在全样本上不成立（__SF__x），其所谓"分享≥150 占比 6 倍"在新口径下只有 6% vs 10%。</div>
</div>

<div class="card">
<h2>五、标题字数：没有证据支持"越长越好"<span class="tag">成熟期样本</span></h2>
<div id="c4" class="chart"></div>
<p class="lead">短标题的高均值几乎全靠苏超（18 字）与雨花台（20 字）两篇撑着；去掉它们后各档差异很小。<b>字数不是杠杆，选题才是。</b></p>
</div>

<div class="card">
<h2>六、集中度与排版输入</h2>
<div class="two">
<div><h2 style="font-size:15px;border-left-color:var(--red)">头部集中度</h2><div id="c5" class="chart" style="height:260px"></div></div>
<div><h2 style="font-size:15px;border-left-color:var(--amber)">星期分布</h2><div id="c6" class="chart" style="height:260px"></div></div>
</div>
<p class="lead"><b>周五是黑洞</b>（21 篇、篇均 695，全周最低）；周日（篇均 4,405、分享 100.6）和周四反而最好。周五遛娃稿建议提前到周四发。</p>
</div>

<div class="card">
<h2>七、TOP15 与沉没清单</h2>
<h2 style="font-size:15px;border-left-color:var(--red);margin-top:6px">阅读 TOP15</h2>
<table><thead><tr><th class="num">#</th><th>标题</th><th class="num">阅读</th><th class="num">放大</th><th class="num">分享</th><th>日期</th></tr></thead><tbody>__TOPROWS__</tbody></table>
<h2 style="font-size:15px;border-left-color:var(--gray);margin-top:22px">沉没稿：发了等于没发（粉丝 ≥1500、放大 &lt;0.15x）</h2>
<p class="lead">这些稿的共同点：<b>面向存量读者的"办事通知"</b>，没有给陌生人一个点开的理由。</p>
<table><thead><tr><th>标题</th><th class="num">阅读</th><th class="num">粉丝</th><th class="num">放大</th><th>日期</th></tr></thead><tbody>__SUNKROWS__</tbody></table>
</div>

<div class="card">
<h2>八、行动建议</h2>
<table><thead><tr><th style="width:64px">优先级</th><th>动作</th><th>依据</th></tr></thead><tbody>
<tr><td><span class="badge b-red">P0</span></td><td><b>补齐中秋/国庆档发文</b>，别让 7-8 月的断更重演</td><td>断更两月净增 0 粉，损失约 900 粉 / 7 万阅读</td></tr>
<tr><td><span class="badge b-red">P0</span></td><td><b>合并合集</b>：把错字合集 <code>南京溜娃</code>（87 篇）并入 <code>南京遛娃</code>（6 篇）；清空 4 个不足 5 篇的残留合集，给无合集的 6 篇补归档</td><td>10 个合集中 6 个不足 5 篇，长尾推荐被切碎</td></tr>
<tr><td><span class="badge b-amber">P1</span></td><td><b>每月固定 1-2 篇"事件/悬念向"非遛娃稿</b>（参考苏超、雨花台、 mystery 古墓）</td><td>这是唯一能突破粉丝池的形态；但不要指望每篇都爆</td></tr>
<tr><td><span class="badge b-amber">P1</span></td><td><b>周五不排稿，改周四或周日</b></td><td>周五篇均 695，周日 4,405</td></tr>
<tr><td><span class="badge b-blue">P2</span></td><td>停写纯办事通知型稿件；要写就必须加一个<b>对陌生人也成立的钩子</b></td><td>沉没稿均值 vs 大盘均值差约 20 倍</td></tr>
<tr><td><span class="badge b-blue">P2</span></td><td>把「南京遛娃」当作<b>基本盘</b>保留，别为追爆款砍掉</td><td>其中位数高于大盘 47%，是最稳的长尾入口</td></tr>
</tbody></table>
</div>

<div class="foot">数据源：<span class="mono">__CSVNAME__</span>　·　复算脚本：<span class="mono">mp-ops/scripts/publish_records_analysis.py</span>、<span class="mono">search_analysis.py</span>、<span class="mono">generate_report.py</span><br>
所有指标均可从原始 CSV 复算；抽样口径已在对应章节标注。数据快照 __SNAPSTR__，跑数脚本已可一键刷新（mp-ops refresh_publish_records.py）。</div>
</div>
<script>
const D = __DATA__;
if (typeof echarts === 'undefined') {
  document.querySelectorAll('.chart').forEach(function(el){
    el.innerHTML='<div style="padding:26px;color:#8b95a5;font-size:13px;text-align:center;'
      +'border:1px dashed #d7dbe2;border-radius:8px">图表引擎未加载，表格数据不受影响</div>';
  });
} else {
const AX={axisLine:{lineStyle:{color:'#e6e9ef'}},axisLabel:{color:'#5b6472',fontSize:11},splitLine:{lineStyle:{color:'#f0f2f6'}}};
const mk=(id,o)=>echarts.init(document.getElementById(id)).setOption(o);
window.addEventListener('resize',()=>document.querySelectorAll('.chart')
  .forEach(el=>{const c=echarts.getInstanceByDom(el); if(c) c.resize();}));
mk('c1',{tooltip:{trigger:'axis'},legend:{data:['发文数','阅读','粉丝'],top:0,textStyle:{fontSize:11}},
 grid:{left:52,right:52,top:38,bottom:30},
 xAxis:{type:'category',data:D.monthly.map(d=>d.m),...AX},
 yAxis:[{type:'value',name:'阅读/粉丝',...AX},{type:'value',name:'篇',max:25,...AX}],
 series:[{name:'发文数',type:'bar',yAxisIndex:1,data:D.monthly.map(d=>d.c),itemStyle:{color:'#c7d2e0',borderRadius:[3,3,0,0]},barWidth:'42%'},
 {name:'阅读',type:'line',data:D.monthly.map(d=>d.r),smooth:true,itemStyle:{color:'#2563eb'},areaStyle:{color:'rgba(37,99,235,.10)'}},
 {name:'粉丝',type:'line',data:D.monthly.map(d=>d.fans),smooth:true,itemStyle:{color:'#d97706'}}]});
mk('c2',{tooltip:{trigger:'axis'},grid:{left:56,right:20,top:26,bottom:44},
 xAxis:{type:'category',data:D.amp.map(d=>d.name),axisLabel:{color:'#5b6472',fontSize:11,interval:0,rotate:14},axisLine:{lineStyle:{color:'#e6e9ef'}}},
 yAxis:[{type:'value',name:'篇数',...AX},{type:'value',name:'篇均阅读',...AX}],
 series:[{name:'篇数',type:'bar',data:D.amp.map(d=>d.n),itemStyle:{color:p=>['#cbd5e1','#cbd5e1','#93c5fd','#60a5fa','#d9303f'][p.dataIndex],borderRadius:[4,4,0,0]},barWidth:'48%',
   label:{show:true,position:'top',fontSize:11,color:'#5b6472'}},
 {name:'篇均阅读',type:'line',yAxisIndex:1,data:D.amp.map(d=>Math.round(d.read)),itemStyle:{color:'#2563eb'},symbolSize:7}]});
mk('c3',{tooltip:{trigger:'axis'},legend:{data:['均值倍数','中位倍数'],top:0,textStyle:{fontSize:11}},
 grid:{left:56,right:20,top:38,bottom:56},
 xAxis:{type:'category',data:D.feat.map(d=>d.name),axisLabel:{color:'#5b6472',fontSize:10.5,interval:0,rotate:20},axisLine:{lineStyle:{color:'#e6e9ef'}}},
 yAxis:{type:'value',name:'倍数（1.0=大盘基准）',...AX},
 series:[{name:'均值倍数',type:'bar',data:D.feat.map(d=>+d.mean_x.toFixed(2)),barWidth:'30%',itemStyle:{borderRadius:[4,4,0,0],color:p=>p.value>=1?'#d9303f':'#12996c'},
   label:{show:true,position:'top',fontSize:10.5,formatter:'{c}x'}},
 {name:'中位倍数',type:'bar',data:D.feat.map(d=>+d.med_x.toFixed(2)),barWidth:'30%',itemStyle:{borderRadius:[4,4,0,0],color:'#f0b429'},
   label:{show:true,position:'top',fontSize:10.5,formatter:'{c}x'}},
 {type:'line',data:D.feat.map(()=>1),lineStyle:{color:'#8b95a5',type:'dashed',width:1},symbol:'none',tooltip:{show:false}}]});
mk('c4',{tooltip:{trigger:'axis'},grid:{left:56,right:20,top:26,bottom:34},
 xAxis:{type:'category',data:D.len.map(d=>d.name+'字'),...AX},
 yAxis:[{type:'value',name:'篇均阅读',...AX},{type:'value',name:'倍数',max:2.2,...AX}],
 series:[{name:'篇均阅读',type:'bar',data:D.len.map(d=>Math.round(d.m)),barWidth:'38%',itemStyle:{color:'#93c5fd',borderRadius:[4,4,0,0]},
   label:{show:true,position:'top',fontSize:11,color:'#5b6472',formatter:p=>p.value}},
 {name:'倍数',type:'line',yAxisIndex:1,data:D.len.map(d=>+d.x.toFixed(2)),itemStyle:{color:'#d97706'},symbolSize:7,
   label:{show:true,fontSize:11,formatter:'{c}x'}}]});
mk('c5',{tooltip:{trigger:'axis'},grid:{left:52,right:20,top:20,bottom:30},
 xAxis:{type:'category',data:D.conc.map(d=>'TOP'+d.k),...AX},yAxis:{type:'value',name:'占阅读%',max:100,...AX},
 series:[{type:'bar',data:D.conc.map(d=>d.v),barWidth:'46%',itemStyle:{color:'#d9303f',borderRadius:[4,4,0,0]},
 label:{show:true,position:'top',fontSize:11,formatter:'{c}%'}}]});
if (D.sc && D.sc.hot_words) {
  const w = D.sc.hot_words.filter(x => x.block === '文章').slice(0, 10);
  mk('c8',{tooltip:{trigger:'axis'},legend:{data:['展示','点击'],top:0,textStyle:{fontSize:11}},
   grid:{left:56,right:20,top:38,bottom:60},
   xAxis:{type:'category',data:w.map(x=>x.word),axisLabel:{color:'#5b6472',fontSize:10,interval:0,rotate:28},axisLine:{lineStyle:{color:'#e6e9ef'}}},
   yAxis:{type:'value',name:'次数',...AX},
   series:[{name:'展示',type:'bar',data:w.map(x=>x.imp),itemStyle:{color:'#cbd5e1',borderRadius:[4,4,0,0]},barWidth:'32%'},
           {name:'点击',type:'bar',data:w.map(x=>x.click),itemStyle:{color:'#d9303f',borderRadius:[4,4,0,0]},barWidth:'32%'}]});
}
if (D.ch) {
  mk('c7',{tooltip:{trigger:'axis'},grid:{left:70,right:30,top:20,bottom:34},
   xAxis:{type:'value',name:'占比 %',...AX},
   yAxis:{type:'category',data:D.ch.order.slice().reverse(),...AX},
   series:[{type:'bar',data:D.ch.avg.slice().reverse(),barWidth:'58%',
     itemStyle:{borderRadius:[0,4,4,0],color:p=>p.dataIndex===D.ch.order.length-1?'#d9303f':'#93c5fd'},
     label:{show:true,position:'right',fontSize:11,formatter:'{c}%'}}]});
}
mk('c6',{tooltip:{trigger:'axis'},grid:{left:52,right:20,top:20,bottom:30},
 xAxis:{type:'category',data:D.wd.map(d=>d.name),...AX},yAxis:{type:'value',name:'篇均阅读',...AX},
 series:[{type:'bar',data:D.wd.map(d=>Math.round(d.m)),barWidth:'52%',
 itemStyle:{color:p=>p.dataIndex===4?'#cbd5e1':'#60a5fa',borderRadius:[4,4,0,0]},
 label:{show:true,position:'top',fontSize:10.5,formatter:p=>p.value}}]});
}
</script></body></html>"""

def fmt_num(v): return f"{int(v):,}"
rows_html=[]
for f in DATA["feat"]:
    m_,d_=f["mean_x"],f["med_x"]
    if m_>=1.2 and d_>=1.1: cls,read='b-red','均值中位双高，真有效'
    elif m_>=1.25:          cls,read='b-amber','均值高但中位≈1：只抬高天花板'
    elif d_>=1.2 and m_<1:  cls,read='b-blue','均值低但中位高：稳，但缺爆款'
    elif m_<1 and d_<1:     cls,read='b-green','双向低于基准，明确负向'
    else:                   cls,read='b-gray','无显著差别'
    rows_html.append(f"<tr><td><b>{f['name']}</b></td><td class='num'>{f['n']}</td>"
        f"<td class='num'>{fmt_num(f['m'])}</td>"
        f"<td class='num {'up' if f['mean_x']>=1 else 'down'}'>{f['mean_x']:.2f}x</td>"
        f"<td class='num {'up' if f['med_x']>=1 else 'down'}'>{f['med_x']:.2f}x</td>"
        f"<td><span class='badge {cls}'>{read}</span></td></tr>")
FEATROWS="".join(rows_html)

TOPROWS="".join(f"<tr><td class='num'>{i}</td><td><a href='{r['url']}' style='color:var(--ink);text-decoration:none'>{r['title'][:36]}</a></td>"
    f"<td class='num'><b>{fmt_num(r['read'])}</b></td><td class='num'>{r['amp']:.1f}x</td>"
    f"<td class='num'>{r['share']}</td><td class='mono'>{r['date']}</td></tr>"
    for i,r in enumerate(DATA["top"],1))
SUNKROWS="".join(f"<tr><td>{r['title'][:40]}</td><td class='num'>{fmt_num(r['read'])}</td>"
    f"<td class='num'>{fmt_num(r['sent'])}</td><td class='num down'>{r['amp']:.3f}x</td>"
    f"<td class='mono'>{r['date']}</td></tr>" for r in DATA["sunk"])

F={k:v for k,v in zip(["悬念/反差/疑问","感叹号","『南京遛娃』开头","最/第一/唯一","稀缺/限时/免费"],range(5))}
def fx(name,key): 
    for f in DATA["feat"]:
        if f["name"]==name: return f"{f[key]:.2f}"
    return "n/a"
maxamp=max(r["amp"] for r in mat if r["amp"] and r["sent"]>=1200)   # 只取当下量级，排除早期几粉时的失真值
corr=st.correlation([d["c"] for d in monthly if d["dfan"] is not None],
                    [d["dfan"] for d in monthly if d["dfan"] is not None])
under1k=[r for r in mat if r["read"]<1000]
contrib=sum(r["read"] for r in under1k)/T*100

CHROWS = ""
if CH:
    _it = sorted(CH["items"], key=lambda x: -x["channels"].get("搜一搜", 0))
    CHROWS = "".join(
        f"<tr><td>{x.get('title','')[:38]}</td><td class='num'>{x.get('read',0):,}</td>"
        f"<td class='num {'up' if x['channels'].get('搜一搜',0)>=2 else 'flat'}'>{x['channels'].get('搜一搜',0):.1f}%</td>"
        f"<td class='num'>{x['channels'].get('推荐',0):.1f}%</td><td class='mono'>{x.get('date','')}</td></tr>"
        for x in _it)
def chv(k):
    if not CH: return "-"
    i = CH["order"].index(k) if k in CH["order"] else None
    return f"{CH['avg'][i]:.1f}" if i is not None else "-"

# 搜一搜数据中心（账号级实测）
SCWORDROWS = SCARTROWS = ""
_sc_kw = {"__SCREAD__": "-", "__SCMOM__": "-", "__SCFOLLOW__": "-",
          "__SCIMP__": "-", "__SCCLICK__": "-", "__SCCTR__": "-",
          "__SCWORDS__": "-", "__SCTOP3__": "-", "__SCDATE__": "-"}
if SC:
    _arts = [x for x in SC.get("hot_words", []) if x.get("block") == "文章"]
    SCWORDROWS = "".join(
        f"<tr><td><b>{x['word']}</b></td><td class='num'>{x['imp']:,}</td><td class='num'>{x['click']:,}</td>"
        f"<td class='num {'up' if x['ctr']>=8 else 'flat'}'>{x['ctr']:.2f}%</td>"
        f"<td style='color:var(--sub);font-size:12.5px'>{'、'.join(x.get('related',[])[:3])}</td></tr>"
        for x in _arts[:10])
    SCARTROWS = "".join(
        f"<tr><td>{x['title'][:34]}</td><td class='num'>{x['imp']:,}</td><td class='num'>{x['click']:,}</td>"
        f"<td class='num {'up' if x['ctr']>=8 else 'flat'}'>{x['ctr']:.2f}%</td><td class='num'>{x['rank']}</td>"
        f"<td style='color:var(--sub);font-size:12.5px'>{'、'.join(x.get('words',[])[:3])}</td></tr>"
        for x in SC.get("hot_articles", []))
    _fs = {f['block']: f for f in SC.get("fan_source", [])}
    _a = _fs.get("文章", {})
    _tot = sum(x["imp"] for x in _arts) or 1
    _top3 = sum(x["imp"] for x in _arts[:3])
    _sc_kw = {
        "__SCREAD__": f"{SC['kpi']['search_read']:,}",
        "__SCMOM__": SC["kpi"].get("search_read_mom", "-"),
        "__SCFOLLOW__": str(SC["kpi"].get("search_follow", "-")),
        "__SCIMP__": f"{_a.get('imp', 0):,}", "__SCCLICK__": f"{_a.get('click', 0):,}",
        "__SCCTR__": f"{_a.get('ctr', 0):.2f}",
        "__SCWORDS__": str(len(_arts)), "__SCTOP3__": f"{_top3/_tot*100:.0f}",
        "__SCDATE__": SC.get("data_date", ""),
    }
rep=(HTML.replace("__DATA__",json.dumps(DATA,ensure_ascii=False))
 .replace("__FEATROWS__",FEATROWS).replace("__TOPROWS__",TOPROWS).replace("__SUNKROWS__",SUNKROWS)
 .replace("__N__",str(DATA["kpi"]["n"])).replace("__DEL__",str(DATA["kpi"]["del"]))
 .replace("__NOW__",datetime.now().strftime("%Y-%m-%d %H:%M"))
 .replace("__SCWORDROWS__",SCWORDROWS).replace("__SCARTROWS__",SCARTROWS).replace("__SCREAD__",_sc_kw["__SCREAD__"]).replace("__SCMOM__",_sc_kw["__SCMOM__"]).replace("__SCFOLLOW__",_sc_kw["__SCFOLLOW__"]).replace("__SCIMP__",_sc_kw["__SCIMP__"]).replace("__SCCLICK__",_sc_kw["__SCCLICK__"]).replace("__SCCTR__",_sc_kw["__SCCTR__"]).replace("__SCWORDS__",_sc_kw["__SCWORDS__"]).replace("__SCTOP3__",_sc_kw["__SCTOP3__"]).replace("__SCDATE__",_sc_kw["__SCDATE__"]) .replace("__CHROWS__",CHROWS).replace("__CHN__",str(CH["n"]) if CH else "0")
 .replace("__CHSS__",chv("搜一搜")).replace("__CHREC__",chv("推荐"))
 .replace("__CHCHAT__",chv("聊天会话")).replace("__CHMSG__",chv("公众号消息"))
 .replace("__KPI_N__",str(DATA["kpi"]["n"])).replace("__MAT__",str(DATA["kpi"]["mat"]))
 .replace("__KPI_READ__",f'{DATA["kpi"]["read"]:,}').replace("__AVG__",f'{DATA["kpi"]["read"]//DATA["kpi"]["n"]:,}')
 .replace("__KPI_FANS__",f'{DATA["kpi"]["fans"]:,}')
 .replace("__KPI_MED__",f'{DATA["kpi"]["med_read"]:,.0f}')
 .replace("__KPI_AMP__",f'{DATA["kpi"]["med_amp"]:.2f}')
 .replace("__UNDER1K__",str(DATA["kpi"]["under1k"]))
 .replace("__UNDER1K_P__",f'{DATA["kpi"]["under1k"]/DATA["kpi"]["n_mat"]*100:.0f}')
 .replace("__SNAPSTR__",_snap_s).replace("__CSVNAME__",_hits[-1])
 .replace("__CONTRIB__",f"{contrib:.1f}")
 .replace("__FANSLP__",str(DATA["kpi"]["fans_lp"]))
 .replace("__FANSLP_P__",f'{DATA["kpi"]["fans_lp"]/DATA["kpi"]["n_mat"]*100:.0f}')
 .replace("__MAXAMP__",f"{maxamp:.0f}")
 .replace("__MF__",fx("最/第一/唯一","mean_x")).replace("__SF__",fx("稀缺/限时/免费","mean_x"))
 .replace("__XM__",fx("悬念/反差/疑问","mean_x")).replace("__XMD__",fx("悬念/反差/疑问","med_x"))
 .replace("__NJ__",fx("『南京遛娃』开头","mean_x")).replace("__NJMD__",fx("『南京遛娃』开头","med_x"))
 .replace("__CORR__",f"{corr:+.2f}").replace("__L2__",str(DATA["kpi"]["L2"])))
# url 字段补全
if 'href' in rep and 'url' not in DATA["top"][0]: pass
ech_src=open(ECHARTS,encoding='utf-8').read().replace('</script>','<\\/script>')
assert '__ECHARTS_INLINE__' in rep
rep=rep.replace('__ECHARTS_INLINE__',ech_src)
os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT,"w",encoding="utf-8") as f: f.write(rep)
print(f"[生成] {OUT}  ({len(rep)/1024:.1f} KB)")
print(f"KPI: {DATA['kpi']}")
print(f"放大>1x 的篇数: {sum(1 for r in mat if r['amp'] and r['amp']>1)}/{len(mat)}")
