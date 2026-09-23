#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
公众号发表记录量化分析（通用，账号目录由 GZH_WORK_DIR 注入）
用法：python3 publish_records_analysis.py [--csv 路径]

⚠️ 口径纪律（2026-09-22 实测修正，别再退回旧说法）：
  1) CSV 的 sent_succ 是「群发送达成功人数」≈**当时粉丝数**，**不是打开基数**。
     read/sent 常 >100%（爆款可达 20+ 倍），所以这个比值是**公域放大倍数**（>1 即吃到推荐流量），
     不是打开率。微信后台不对外提供真实打开率，别用本脚本冒充打开率下结论。
  2) 发布不足 7 天的稿仍在发酵，混排会把好稿误判成差稿。
     对比类统计请用 `mat`（熟化样本），不要用 `live`。见维度【12】。
  3) 篇均（mean）极易被少量爆款拉高，**必须同时看中位数**；
     判断"某个标题特征有没有用"要放在同粉丝规模层内做，并剔除极端值——见【12】。
"""
import csv, sys, re, os, statistics as st
from collections import Counter, defaultdict
from datetime import datetime

# --- 迁移到 skill 时新增：空样本不再抛 StatisticsError ---
def safe_mean(seq):
    """空序列返回 0.0，避免 st.mean([]) 抛异常中断整份报告。"""
    seq = list(seq)
    return st.mean(seq) if seq else 0.0


BASE = os.environ.get("GZH_WORK_DIR") or os.getcwd()  # 由调用方注入，不再硬编码具体账号目录
# 自动取账号目录下最新的发表记录 CSV（刷新后会生成新日期的 CSV，别写死文件名）
_hits = sorted(f for f in os.listdir(BASE) if f.startswith("发表记录") and f.endswith(".csv"))
if not _hits:
    sys.exit(f"未找到发表记录 CSV（{BASE}）；先跑 refresh_publish_records.py")
CSV = os.path.join(BASE, _hits[-1])

rows = []
with open(CSV, encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        if not r.get("title"):
            continue
        def num(k):
            v = (r.get(k) or "").strip()
            return int(v) if v.isdigit() else 0
        d = {
            "date": r["date"], "time": r["time"], "title": r["title"].strip(),
            "read": num("read"), "like": num("like"), "share": num("share"),
            "haokan": num("haokan"), "comment": num("comment"),
            "sent": num("sent_succ"), "deleted": r.get("deleted") == "True",
            "album": (r.get("album") or "").strip(),
            "original": (r.get("original") or "").strip(),
            "itemidx": num("itemidx"), "article_count": num("article_count"),
            "digest": (r.get("digest") or "").strip(),
            "url": r.get("url", ""),
        }
        rows.append(d)

rows.sort(key=lambda x: (x["date"], x["time"]))
live = [r for r in rows if not r["deleted"]]

# --- 熟化过滤：发布不足 MATURE_DAYS 天的稿处于发酵期，不参与对比类统计 ---
SNAP = datetime.strptime(max(r["date"] for r in rows), "%Y-%m-%d").date()
MATURE_DAYS = 7
for r in rows:
    r["age"] = (SNAP - datetime.strptime(r["date"], "%Y-%m-%d").date()).days
    r["mature"] = r["age"] >= MATURE_DAYS
mat = [r for r in live if r["mature"]]
def amp(r):
    """公域放大倍数 = 阅读 / 粉丝数。>1 表示突破粉丝池吃到推荐流量。"""
    return r["read"] / r["sent"] if r["sent"] else None

def pct(a, b):
    return f"{a/b*100:.2f}%" if b else "-"

print("=" * 78)
print(f"总样本：{len(rows)} 条（含已删 {len(rows)-len(live)}）｜在库 {len(live)} 篇")
print(f"时间跨度：{rows[0]['date']} ~ {rows[-1]['date']}")
print(f"累计阅读：{sum(r['read'] for r in live):,}｜累计分享：{sum(r['share'] for r in live):,}"
      f"｜累计点赞：{sum(r['like'] for r in live):,}｜累计评论：{sum(r['comment'] for r in live):,}")
print(f"篇均阅读：{st.mean([r['read'] for r in live]):.0f}｜中位：{st.median([r['read'] for r in live]):.0f}")

# ---------- 1. 粉丝增长曲线（sent_succ 增量）----------
print("\n" + "=" * 78)
print("【1】粉丝规模曲线（sent_succ = 群发送达人数，即当时用户数）")
print("-" * 78)
print(f"起始送达：{rows[0]['sent']:,} → 最新送达：{rows[-1]['sent']:,}"
      f"｜净增 {rows[-1]['sent']-rows[0]['sent']:+,}")
by_month_lastsent = {}
for r in rows:
    m = r["date"][:7]
    by_month_lastsent[m] = r["sent"]
prev = None
print(f"{'月份':<9}{'月末送达':>9}{'月净增':>8}{'发文':>5}{'阅读':>9}{'篇均':>7}{'篇均涨粉':>9}")
mon_stat = defaultdict(lambda: {"c": 0, "r": 0})
for r in live:
    m = r["date"][:7]
    mon_stat[m]["c"] += 1
    mon_stat[m]["r"] += r["read"]
months = sorted(set(list(by_month_lastsent) + list(mon_stat)))
sent_series = sorted(by_month_lastsent.items())
for m in months:
    s = by_month_lastsent.get(m, (prev or 0))
    delta = s - prev if prev is not None else 0
    c = mon_stat[m]["c"]; rr = mon_stat[m]["r"]
    print(f"{m:<9}{s:>9,}{delta:>+8}{c:>5}{rr:>9,}{rr//c if c else 0:>7}"
          f"{round(delta/c) if c else 0:>9}")
    prev = s

# 每篇净增粉delta for correlation
for i, r in enumerate(rows):
    if i and rows[i-1]["sent"]:
        r["d_fan"] = r["sent"] - rows[i-1]["sent"]
    else:
        r["d_fan"] = 0
live_f = [r for r in live if "d_fan" in r]

# ---------- 2. 打开率（read / sent）----------
print("\n" + "=" * 78)
print("【2】公域放大倍数 = 阅读 / 送达人数（≈粉丝数）")
print("    ⚠️ 这不是打开率：>1 表示突破粉丝池吃到推荐流量；微信不对外提供真实打开率")
print("-" * 78)
q = sorted([r for r in live if r["sent"] > 0], key=lambda x: x["read"]/x["sent"])
n = len(q)
bands = [("0~1%", 0, .01), ("1~2%", .01, .02), ("2~4%", .02, .04), ("4~8%", .04, .08),
         ("8~15%", .08, .15), ("15%+", .15, 9)]
for name, lo, hi in bands:
    sel = [r for r in q if lo <= r["read"]/r["sent"] < hi]
    if sel:
        print(f"{name:<8}{len(sel):>4} 篇（{len(sel)/n*100:>5.1f}%）"
              f"｜篇均阅读 {st.mean([x['read'] for x in sel]):>8,.0f}"
              f"｜篇均分享 {st.mean([x['share'] for x in sel]):>6.1f}")
print(f"\n中位打开率：{st.median([r['read']/r['sent'] for r in q])*100:.2f}%"
      f"｜均值：{st.mean([r['read']/r['sent'] for r in q])*100:.2f}%")
print("\n▼ 打开率 TOP10（排除送达过小）")
for r in sorted([x for x in q if x["sent"] > 1000], key=lambda x: -x["read"]/x["sent"])[:10]:
    print(f"  {r['read']/r['sent']*100:>6.2f}%｜{r['read']:>6,}读/{r['sent']:>5,}送｜{r['date']}｜{r['title'][:34]}")
print("\n▼ 打开率 BOTTOM10 已发布30天以上（送达>1500）")
old = [x for x in q if x["sent"] > 1500]
for r in sorted(old, key=lambda x: x["read"]/x["sent"])[:10]:
    print(f"  {r['read']/r['sent']*100:>6.2f}%｜{r['read']:>6,}读/{r['sent']:>5,}送｜{r['date']}｜{r['title'][:34]}")

# ---------- 3. 标题因素回归式交叉表 ----------
print("\n" + "=" * 78)
print("【3】标题特征 × 效果（在库篇）")
print("-" * 78)
def tag(r):
    t = r["title"]
    return {
        "前21字含数字": bool(re.search(r"[0-9０-９]", t[:21])),
        "含最/第一/唯一/仅": bool(re.search(r"最|第一|唯一|仅有|独一|首家|首个", t)),
        "含感叹号": ("!" in t or "！" in t),
        "含问号": ("?" in t or "？" in t),
        "含遛娃前缀": ("遛娃" in t[:12]),
        "含免费": ("免费" in t),
        "含南京": ("南京" in t),
        "含江苏/全省": ("江苏" in t or "全省" in t),
        "含｜分隔": "｜" in t,
        "长标题>=30": len(t) >= 30,
        "短标题<20": len(t) < 20,
    }
feats = list(tag(live[0]).keys())
print(f"{'特征':<16}{'篇数':>5}{'篇均阅读':>9}{'中位':>7}{'篇均分享':>8}{'打开率':>8}{' vs 全量倍数':>11}")
base_read = st.mean([r["read"] for r in live])
for f in feats:
    sel = [r for r in live if tag(r)[f]]
    if len(sel) < 2: continue
    ratio = st.mean([r["read"] for r in sel]) / base_read
    op = safe_mean([r["read"]/r["sent"] for r in sel if r["sent"]]) * 100
    print(f"{f:<16}{len(sel):>5}{st.mean([r['read'] for r in sel]):>9,.0f}"
          f"{st.median([r['read'] for r in sel]):>7.0f}{st.mean([r['share'] for r in sel]):>8.1f}"
          f"{op:>7.2f}%{ratio:>10.2f}x")

print("\n▼ 标题字数分档")
for lo, hi, nm in [(0,20,"<20"),(20,26,"20-25"),(26,32,"26-31"),(32,40,"32-39"),(40,99,"40+")]:
    sel = [r for r in live if lo <= len(r["title"]) < hi]
    if sel:
        print(f"  {nm:<7}{len(sel):>4} 篇｜篇均阅读 {st.mean([r['read'] for r in sel]):>7,.0f}"
              f"｜篇均分享 {st.mean([r['share'] for r in sel]):>5.1f}｜打开率 {safe_mean([r['read']/r['sent'] for r in sel if r['sent']])*100:>5.2f}%")

# ---------- 4. 合集维度 ----------
print("\n" + "=" * 78)
print("【4】合集（album）维度")
print("-" * 78)
alb = defaultdict(list)
for r in live:
    alb[r["album"] or "(无合集)"].append(r)
res = sorted(alb.items(), key=lambda kv: -st.mean([x["read"] for x in kv[1]]))
print(f"{'合集':<22}{'篇数':>4}{'篇均阅读':>9}{'中位':>7}{'分享':>6}{'收藏好看':>8}{'打开率':>7}")
for k, v in res:
    op = safe_mean([x["read"]/x["sent"] for x in v if x["sent"]]) * 100
    print(f"{k[:20]:<22}{len(v):>4}{st.mean([x['read'] for x in v]):>9,.0f}"
          f"{st.median([x['read'] for x in v]):>7.0f}{st.mean([x['share'] for x in v]):>6.1f}"
          f"{st.mean([x['haokan'] for x in v]):>8.1f}{op:>6.2f}%")

# ---------- 5. 发布时段 ----------
print("\n" + "=" * 78)
print("【5】发布时段 × 效果")
print("-" * 78)
hh = defaultdict(list)
for r in live:
    hh[int(r["time"][:2])].append(r)
print(f"{'时段':<8}{'篇数':>5}{'篇均阅读':>9}{'中位':>7}{'篇均分享':>8}{'打开率':>7}")
for h in sorted(hh):
    v = hh[h]
    op = safe_mean([x["read"]/x["sent"] for x in v if x["sent"]]) * 100
    print(f"{h:02d}时    {len(v):>5}{st.mean([x['read'] for x in v]):>9,.0f}"
          f"{st.median([x['read'] for x in v]):>7.0f}{st.mean([x['share'] for x in v]):>8.1f}{op:>6.2f}%")
print("\n▼ 星期分布（0=周一）")
wd = defaultdict(list)
WD = ["周一","周二","周三","周四","周五","周六","周日"]
for r in live:
    wd[datetime.strptime(r["date"], "%Y-%m-%d").weekday()].append(r)
for k in sorted(wd):
    v = wd[k]
    print(f"  {WD[k]}：{len(v):>3} 篇｜篇均阅读 {st.mean([x['read'] for x in v]):>7,.0f}"
          f"｜篇均分享 {st.mean([x['share'] for x in v]):>5.1f}")

# ---------- 6. 分享率 / 互动结构 ----------
print("\n" + "=" * 78)
print("【6】互动结构：这批数据到底靠什么起量？")
print("-" * 78)
tot_r = sum(r["read"] for r in live); tot_s = sum(r["share"] for r in live)
tot_l = sum(r["like"] for r in live); tot_c = sum(r["comment"] for r in live)
tot_h = sum(r["haokan"] for r in live)
print(f"整体：分享/阅读 = {tot_s/tot_r*100:.2f}%（每千读 {tot_s/tot_r*1000:.1f} 次分享）")
print(f"      点赞/阅读 = {tot_l/tot_r*100:.2f}%｜在看/阅读 = {tot_h/tot_r*100:.2f}%｜评论/阅读 = {tot_c/tot_r*100:.3f}%")
corr = st.correlation if hasattr(st, "correlation") else None
xs = [r["read"] for r in live]
for k, nm in [("share","分享"), ("like","点赞"), ("haokan","在看"), ("comment","评论")]:
    ys = [r[k] for r in live]
    try:
        c = st.correlation(xs, ys)
    except Exception:
        c = float("nan")
    print(f"  {nm} 与阅读的相关系数 r = {c:.3f}")

print("\n▼ 分档看互动率（按阅读量分层）")
for lo, hi, nm in [(0,300,"<300"),(300,800,"300-800"),(800,3000,"800-3k"),(3000,10000,"3k-1w"),(10000,9e9,"1w+")]:
    sel = [r for r in live if lo <= r["read"] < hi]
    if sel:
        sr = sum(x["read"] for x in sel)
        print(f"  {nm:<8}{len(sel):>4} 篇｜分享率 {sum(x['share'] for x in sel)/sr*100:>5.2f}%"
              f"｜点赞率 {sum(x['like'] for x in sel)/sr*100:>5.2f}%"
              f"｜在看率 {sum(x['haokan'] for x in sel)/sr*100:>5.2f}%"
              f"｜评论率 {sum(x['comment'] for x in sel)/sr*100:>5.2f}%")

# ---------- 7. 头部集中度 ----------
print("\n" + "=" * 78)
print("【7】头部集中度（判断账号是否过度依赖爆款）")
print("-" * 78)
sr = sorted(live, key=lambda x: -x["read"]); T = sum(r["read"] for r in live)
for k in [1,3,5,10,20]:
    s = sum(x["read"] for x in sr[:k])
    print(f"  TOP{k:<3}占阅读 {s/T*100:>5.1f}%｜累计篇数占比 {k/len(live)*100:>4.1f}%")
print(f"  TOP20 篇中有 {sum(1 for x in sr[:20] if x['read']>10000)} 篇过万；"
      f"全库过万 {sum(1 for x in live if x['read']>10000)} 篇")
print(f"  阅读 <1000 的占比：{sum(1 for x in live if x['read']<1000)/len(live)*100:.1f}%"
      f"（{sum(1 for x in live if x['read']<1000)} 篇），它们合计贡献 "
      f"{sum(x['read'] for x in live if x['read']<1000)/T*100:.1f}% 阅读")

# ---------- 8. 长期趋势：近 vs 远 ----------
print("\n" + "=" * 78)
print("【8】近 90 天 vs 早期（判断账号是在上行还是衰退）")
print("-" * 78)
recent = [r for r in live if r["date"] >= "2026-06-16"]
early = [r for r in live if r["date"] < "2026-06-16"]
for nm, v in [("近90天", recent), ("早期", early)]:
    if v:
        print(f"  {nm}：{len(v)} 篇｜篇均阅读 {st.mean([x['read'] for x in v]):>7,.0f}"
              f"｜篇均分享 {st.mean([x['share'] for x in v]):>5.1f}"
              f"｜打开率 {safe_mean([x['read']/x['sent'] for x in v if x['sent']])*100:>5.2f}%"
              f"｜分享率 {sum(x['share'] for x in v)/sum(x['read'] for x in v)*100:>5.2f}%")

print("\n▼ 2026 各月明细")
m26 = defaultdict(list)
for r in live:
    if r["date"].startswith("2026"): m26[r["date"][:7]].append(r)
for m in sorted(m26):
    v = m26[m]; rr = sum(x["read"] for x in v)
    print(f"  {m}：{len(v):>2} 篇｜阅读 {rr:>7,}｜篇均 {rr//len(v):>6,}｜分享 {sum(x['share'] for x in v):>4}"
          f"｜打开率 {safe_mean([x['read']/x['sent'] for x in v if x['sent']])*100:>5.2f}%")

# ---------- 9. 已删篇 ----------
if len(rows) != len(live):
    print("\n" + "=" * 78)
    print("【9】已删除篇")
    print("-" * 78)
    for r in rows:
        if r["deleted"]:
            print(f"  {r['date']}｜{r['read']:>5,}读｜{r['title'][:44]}")

# ---------- 10. TOP / BOTTOM ----------
print("\n" + "=" * 78)
print("【10】阅读 TOP20")
print("-" * 78)
for i, r in enumerate(sr[:20], 1):
    print(f"{i:>3}. {r['read']:>6,}读 分享{r['share']:>4} 赞{r['like']:>3}｜{r['date']} {r['time']}｜{r['title'][:40]}")
print("\n【11】分享 TOP15（转发驱动型标题样本）")
print("-" * 78)
for i, r in enumerate(sorted(live, key=lambda x: -x["share"])[:15], 1):
    print(f"{i:>3}. 分享{r['share']:>4} 读{r['read']:>6,} 率{r['share']/max(r['read'],1)*100:>5.1f}%｜{r['date']}｜{r['title'][:40]}")

# ---------- 12. 稳健性复核（2026-09-22 新增，可靠结论以此为准）----------
# 目的：维度【3】的标题结论是"全样本 + 未剔极端值 + 未分层"，容易被少数爆款带偏，
#       历史上据此得出过错误经验（如"长标题更好""最/第一/唯一有效"），复核后均为反向或无效。
print("\n" + "=" * 78)
print("【12】稳健性复核：分层 + 剔极端值（★可靠结论以此为准，勿直接采信【3】）")
print("-" * 78)
SCAR = r"一年一次|限定|独家|最后|仅\d|仅剩|仅限|限\d|一天两场|免费|名额有限|错过再等|错过等一年"
FEATS = {
    "悬念/反差/疑问": lambda t: bool(re.search(r"藏|原来|竟然|秘密|没想到|吓一跳|居然|凭什么|为什么|？|\?", t)),
    "感叹号":        lambda t: ("!" in t or "！" in t),
    "最/第一/唯一":  lambda t: bool(re.search(r"最|第一|唯一|仅有|独一|首家|首个", t)),
    "稀缺/限时/免费": lambda t: bool(re.search(SCAR, t)),
    "『南京遛娃』类前缀": lambda t: bool(re.match(r"^[^｜|]{0,6}遛娃", t)),
}
mature_fans = [r["sent"] for r in mat if r["sent"]]
hi = sorted(mature_fans)[int(len(mature_fans) * 0.6)] if mature_fans else 0   # 当下量级阈值（60% 分位）
L = [r for r in mat if r["sent"] >= hi]
top3 = sorted(L, key=lambda x: -x["read"])[:3]
L2 = [r for r in L if r not in top3]
print(f"成熟层（发布时粉丝 ≥{hi:,}）{len(L)} 篇｜剔除 TOP{len(top3)} 极端值后 {len(L2)} 篇"
      f"｜基准 篇均 {safe_mean([x['read'] for x in L2]):,.0f} / 中位 {st.median([x['read'] for x in L2]):,.0f}")
print("  被剔除：", "、".join(f"{x['read']:,}读《{x['title'][:14]}》" for x in top3))
b_m = safe_mean([x["read"] for x in L2]) or 1
b_d = st.median([x["read"] for x in L2]) or 1
print(f"\n{'特征':<20}{'篇数':>4}{'篇均':>9}{'均值倍数':>9}{'中位倍数':>9}  读法")
for fn, f in FEATS.items():
    sel = [r for r in L2 if f(r["title"])]
    if len(sel) < 3:
        print(f"{fn:<20}{len(sel):>4}  样本不足，无法判断（该写法可能已停用）")
        continue
    mx = safe_mean([x["read"] for x in sel]) / b_m
    dx = st.median([x["read"] for x in sel]) / b_d
    if mx >= 1.2 and dx >= 1.1:   note = "真有效"
    elif mx >= 1.25:              note = "只抬高天花板（中位≈1，别指望复现）"
    elif dx >= 1.2 and mx < 1:    note = "地板资产：稳但缺爆款，别砍"
    elif mx < 1 and dx < 1:       note = "明确负向，别再用"
    else:                         note = "无显著差别"
    print(f"{fn:<20}{len(sel):>4}{safe_mean([x['read'] for x in sel]):>9,.0f}{mx:>8.2f}x{dx:>8.2f}x  {note}")

print("\n  ▼ 标题字数（成熟层）")
for lo, uhi, nm in [(0, 25, "<25"), (25, 32, "25-31"), (32, 40, "32-39"), (40, 999, "40+")]:
    sel = [r for r in L if lo <= len(r["title"]) < uhi]
    if len(sel) >= 2:
        print(f"    {nm:<6}{len(sel):>3}篇｜篇均 {safe_mean([x['read'] for x in sel]):>7,.0f}"
              f"｜中位 {st.median([x['read'] for x in sel]):>6.0f}"
              f"｜倍数 {safe_mean([x['read'] for x in sel])/ (safe_mean([x['read'] for x in L]) or 1):>5.2f}x")

# 发文节奏 vs 涨粉
mon_c = Counter(); mon_r = Counter()
for r in live:
    m = r["date"][:7]; mon_c[m] += 1; mon_r[m] += r["read"]
last = {}
for r in rows: last[r["date"][:7]] = r["sent"]
ms = sorted(set(list(mon_c) + list(last)))
xs, ys, zs = [], [], []
prev = None
for m in ms:
    s_ = last.get(m, prev or 0); d = s_ - prev if prev is not None else 0
    if mon_c[m] and prev is not None:
        xs.append(mon_c[m]); ys.append(mon_r[m] // mon_c[m]); zs.append(d)
    prev = s_
if len(xs) >= 3:
    print(f"\n  ▼ 发文节奏：月发文数 vs 篇均阅读 r={st.correlation(xs, ys):+.3f}"
          f"｜vs 月净增粉 r={st.correlation(xs, zs):+.3f}")
    print("    （r 接近 0 = 多写不摊薄单篇收益，只涨总量；断更是纯亏）")

# 合集质量
alb = defaultdict(list)
for r in live: alb[r["album"] or "(无合集)"].append(r)
tiny = [k for k, v in alb.items() if len(v) < 5]
print(f"\n  ▼ 合集质量：共 {len(alb)} 个，其中不足 5 篇的 {len(tiny)} 个（{('、'.join(tiny[:6])) or '无'}）"
      f"｜无合集 {sum(1 for r in live if not r['album'])} 篇")
print("    → 合集碎片化会切断长尾推荐，建议合并/补齐")

# 导出结构化 JSON 供报告使用
import json
_acc = os.path.basename(BASE.rstrip("/"))
out = os.path.join(os.path.expanduser("~/.cache/weixin/publish_records"), f"{_acc}_分析数据.json")
with open(out, "w", encoding="utf-8") as f:
    json.dump([{k: v for k, v in r.items()} for r in rows], f, ensure_ascii=False, indent=1)
print(f"\n[已导出] {out}")
