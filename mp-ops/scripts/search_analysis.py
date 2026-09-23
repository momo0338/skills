#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
公众号「搜一搜 / 搜索长尾」分析（无后台数据也能跑）

背景：个人订阅号拿不到 datacube 接口权限（48001），后台「搜一搜」真实数据只能靠网页抓取
      （见 scripts/search_fetch.py）。在拿到真实数据之前，本脚本用**发表记录本身**评估
      每篇内容的搜索长尾价值，并做交叉验证。

⚠️ 诚实声明：本脚本产出的是**推算值**，不是后台实测的搜一搜阅读量。
   唯一能做半实证的部分是【D】：发布超过 N 天的老稿，群发流量早已结束，
   其累计阅读近似等于长尾流量（搜一搜 + 历史消息 + 收藏回看），
   用它可以检验"搜索友好度"这个打分是否真的和长尾表现相关。

用法：
    export GZH_WORK_DIR="/path/to/账号目录"
    python3 search_analysis.py [--csv 路径] [--old-days 90] [--json 输出.json]
"""
import csv, os, re, json, sys, statistics as st
from collections import Counter, defaultdict
from datetime import datetime, date

def mean(x): x=list(x); return st.mean(x) if x else 0.0
def med(x):  x=list(x); return st.median(x) if x else 0.0

BASE = os.environ.get("GZH_WORK_DIR") or os.getcwd()
OLD_DAYS = 90

csv_path = None
for i, a in enumerate(sys.argv[1:]):
    if a == "--csv": csv_path = sys.argv[i + 2]
    if a == "--old-days": OLD_DAYS = int(sys.argv[i + 2])
if not csv_path:
    hits = sorted(f for f in os.listdir(BASE) if f.startswith("发表记录") and f.endswith(".csv"))
    if not hits:
        sys.exit(f"未找到发表记录 CSV，请用 --csv 指定（当前目录 {BASE}）")
    csv_path = os.path.join(BASE, hits[-1])

rows = []
with open(csv_path, encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        t = (r.get("title") or "").strip()
        if not t: continue
        n = lambda k: int(r[k]) if (r.get(k) or "").strip().isdigit() else 0
        rows.append({"date": r["date"], "title": t, "read": n("read"), "share": n("share"),
                     "haokan": n("haokan"), "sent": n("sent_succ"),
                     "deleted": r.get("deleted") == "True",
                     "album": (r.get("album") or "").strip(),
                     "digest": (r.get("digest") or "").strip()})
rows.sort(key=lambda x: x["date"])
live = [r for r in rows if not r["deleted"]]
SNAP = datetime.strptime(max(r["date"] for r in rows), "%Y-%m-%d").date()
for r in rows:
    r["age"] = (SNAP - datetime.strptime(r["date"], "%Y-%m-%d").date()).days

# ---------------- 词库 ----------------
PLACE = r"南京|江宁|建邺|玄武|鼓楼|秦淮|栖霞|雨花台|浦口|六合|溧水|高淳|扬州|镇江|泰州|淮安|苏州|无锡|常州|南通|盐城|徐州|连云港|宿迁|江苏|汤山|仙林|河西|城东|城南|江北"
VENUE = r"博物馆|博物院|公园|图书馆|美术馆|科技馆|纪念馆|陵园|景区|景点|古镇|大学|学院|学校|地铁|高铁|山|湖|寺|塔|园|馆|故居|遗址|城墙|码头|书院"
INTENT = r"攻略|怎么|如何|预约|门票|免费|开放|时间|地址|交通|停车|清单|大全|盘点|推荐|排名|值得|必去|指南|路线|全攻略|汇总|合集|一览|表|入口|流程|条件|政策|补贴|疫苗|开学|放假|秋假|寒假|暑假|报名|办理|指南"
CROWD = r"遛娃|亲子|带娃|儿童|小孩|小学生|幼儿园|娃|家长|孩子|宝宝|一家"
TIME_SENSITIVE = r"本周|本周六|本周末|今日|今天|明天|限时|截止|最后|倒计时|抓紧|速看|速|即将|新开|刚开|今年|今年|20\d\d年|[0-9]{1,2}月[0-9]{1,2}日|开放日|一天两场|一年一次"
EVERGREEN_HINT = r"攻略|清单|大全|盘点|汇总|一览|指南|怎么|如何|值得|推荐|排名"

def score(r):
    t = r["title"]; d = r["digest"]
    s, hits = 0.0, []
    if re.search(PLACE, t):   s += 2.0; hits.append("地点")
    if re.search(VENUE, t):   s += 2.0; hits.append("场所")
    m = re.findall(INTENT, t)
    if m: s += min(1.5 * len(set(m)), 3.0); hits.append("意图词x%d" % len(set(m)))
    if re.search(CROWD, t):   s += 1.0; hits.append("人群")
    sens = re.findall(TIME_SENSITIVE, t)
    if sens: s -= 2.0; hits.append("时效词x%d" % len(set(sens)))
    if re.search(EVERGREEN_HINT, t) and not sens: s += 2.0; hits.append("常青式")
    if not r["album"]:        s -= 0.5; hits.append("无合集")
    r["sscore"] = round(s, 1); r["hits"] = hits
    r["evergreen"] = (not sens)
    return r
for r in live: score(r)

print("=" * 84)
print(f"搜一搜 / 搜索长尾分析　数据源：{os.path.basename(csv_path)}")
print(f"在库 {len(live)} 篇｜跨度 {rows[0]['date']} ~ {rows[-1]['date']}｜快照 {SNAP}")
print("⚠️ 打分是推算值；【D】段用老稿累计阅读做半实证交叉验证")
print("=" * 84)

# ---------- A 搜索意图词覆盖 ----------
print("\n【A】标题里的搜索意图词覆盖（读者会怎么搜，你的标题接得住吗）")
words = Counter()
for r in live:
    for w in re.findall(INTENT, r["title"]): words[w] += 1
print("  TOP20 意图词：" + "、".join(f"{w}({c})" for w, c in words.most_common(20)))
covered = set(words)
gap = [w for w in ["攻略", "预约", "门票", "免费", "开放", "时间", "地址", "交通", "停车",
                   "清单", "推荐", "值得", "怎么", "流程", "条件"] if w not in covered]
print(f"  未覆盖的高频意图词（{len(gap)}）：{'、'.join(gap) if gap else '无'}")

# ---------- B 打分分布 ----------
print("\n【B】搜索友好度打分分布（地点2 + 场所2 + 意图词≤3 + 人群1 + 常青2 - 时效2 - 无合集0.5）")
bands = [("高 ≥5", 5, 99), ("中 2~5", 2, 5), ("低 0~2", 0, 2), ("负 <0", -99, 0)]
for nm, lo, hi in bands:
    sel = [r for r in live if lo <= r["sscore"] < hi]
    if sel:
        print(f"  {nm:<8}{len(sel):>4} 篇｜篇均阅读 {mean([x['read'] for x in sel]):>8,.0f}"
              f"｜中位 {med([x['read'] for x in sel]):>7,.0f}｜分享 {mean([x['share'] for x in sel]):>5.1f}")

# ---------- C 常青 vs 时效 ----------
print("\n【C】常青 vs 时效（时效稿长尾价值会衰减，这是搜一搜的天花板）")
for nm, f in [("常青稿（无时效词）", lambda r: r["evergreen"]), ("时效稿", lambda r: not r["evergreen"])]:
    sel = [r for r in live if f(r)]
    if sel:
        print(f"  {nm:<16}{len(sel):>4} 篇（{len(sel)/len(live)*100:>4.1f}%）"
              f"｜篇均阅读 {mean([x['read'] for x in sel]):>8,.0f}"
              f"｜中位 {med([x['read'] for x in sel]):>7,.0f}"
              f"｜搜索分 {mean([x['sscore'] for x in sel]):>5.2f}")

# ---------- D 半实证：老稿长尾 ----------
old = [r for r in live if r["age"] >= OLD_DAYS]
print(f"\n【D】★半实证：发布 ≥{OLD_DAYS} 天的老稿（{len(old)} 篇）——群发流量已结束，累计阅读≈长尾流量")
if len(old) >= 10:
    print(f"{'搜索分档':<10}{'篇数':>4}{'中位阅读':>9}{'均值阅读':>9}{'中位分享':>8}  说明")
    for nm, lo, hi in [("高 ≥5", 5, 99), ("中 2~5", 2, 5), ("低 <2", -99, 2)]:
        sel = [r for r in old if lo <= r["sscore"] < hi]
        if len(sel) >= 3:
            print(f"  {nm:<8}{len(sel):>4}{med([x['read'] for x in sel]):>9,.0f}"
                  f"{mean([x['read'] for x in sel]):>9,.0f}{med([x['share'] for x in sel]):>8.0f}")
    hi_ = [r for r in old if r["sscore"] >= 5]
    lo_ = [r for r in old if r["sscore"] < 2]
    if hi_ and lo_:
        print(f"\n  高档中位 {med([x['read'] for x in hi_]):,.0f} vs 低档中位 {med([x['read'] for x in lo_]):,.0f}"
              f"　→ 倍数 {med([x['read'] for x in hi_])/max(med([x['read'] for x in lo_]),1):.2f}x")
        try:
            c = st.correlation([r["sscore"] for r in old], [r["read"] for r in old])
            print(f"  搜索分 vs 老稿累计阅读 相关系数 r = {c:+.3f}（正相关=打分有效，接近0=打分没用）")
        except Exception: pass
    print("\n  ▼ 老稿里搜索分最高 TOP10（该维护/更新的长尾资产）")
    for r in sorted(old, key=lambda x: -x["sscore"])[:10]:
        print(f"    {r['sscore']:>5.1f}分｜{r['read']:>6,}读｜{r['age']:>4}天｜{r['date']}｜{r['title'][:36]}")

# ---------- E 合集维度 ----------
print("\n【E】合集维度的搜索资产价值（合集=搜索入口的候选）")
alb = defaultdict(list)
for r in live: alb[r["album"] or "(无合集)"].append(r)
print(f"{'合集':<18}{'篇数':>4}{'搜索分':>7}{'常青率':>7}{'中位阅读':>9}{'老稿中位':>9}")
for k, v in sorted(alb.items(), key=lambda kv: -mean([x["sscore"] for x in kv[1]])):
    ov = [x for x in v if x["age"] >= OLD_DAYS]
    print(f"{k[:16]:<18}{len(v):>4}{mean([x['sscore'] for x in v]):>7.2f}"
          f"{sum(1 for x in v if x['evergreen'])/len(v)*100:>6.0f}%"
          f"{med([x['read'] for x in v]):>9,.0f}"
          f"{(med([x['read'] for x in ov]) if ov else 0):>9,.0f}")

# ---------- G 真实长尾结构（剔除爆款）----------
print("\n【G】★真实长尾水位：老稿阅读的大头其实是爆款的一次性爆发，不是持续长尾")
if len(old) >= 10:
    tot_old = sum(r["read"] for r in old)
    print(f"  老稿合计阅读 {tot_old:,}，占全库 {tot_old/sum(r['read'] for r in live)*100:.1f}%  → 账号是**存量驱动型**")
    for k in [1, 3, 5, 10, 20]:
        s5 = sorted(old, key=lambda x: -x["read"])[:k]
        print(f"    老稿 TOP{k:<3}占老稿阅读 {sum(x['read'] for x in s5)/tot_old*100:>5.1f}%")
    old2 = sorted(old, key=lambda x: -x["read"])[5:]
    print(f"\n  剔除老稿 TOP5 后（{len(old2)} 篇）——这才是可持续长尾的水位：")
    print(f"    中位 {med([x['read'] for x in old2]):,.0f} 读｜均值 {mean([x['read'] for x in old2]):,.0f} 读"
          f"｜最高 {max(x['read'] for x in old2):,}｜最低 {min(x['read'] for x in old2):,}")
    print(f"    即：一篇普通稿沉淀 {OLD_DAYS}+ 天，中位数约 {med([x['read'] for x in old2]):,.0f} 读，"
          f"而发布首日群发约 {med([r['read'] for r in live if r['age']<7]) or 0:,.0f} 读量级")
    print("\n  ▼ 真正的慢长尾赢家（老稿、剔 TOP5、按阅读排序）——共同点值得抄")
    for r in sorted(old2, key=lambda x: -x["read"])[:10]:
        print(f"    {r['read']:>6,}读 分享{r['share']:>4}｜{r['age']:>4}天｜{r['title'][:38]}")
    print("\n  → 结论：撑起慢长尾的是「独家/稀缺/难预约的现场体验」，不是标题里的搜索词堆砌。")

# ---------- F 行动 ----------
print("\n【F】行动清单")
old_ts = [r for r in old if not r["evergreen"] and r["sscore"] >= 3]
print(f"  1. 该更新的过期常青稿：{len(old_ts)} 篇（老 + 含时效词 + 搜索价值不低）")
for r in sorted(old_ts, key=lambda x: -x["sscore"])[:8]:
    print(f"     {r['sscore']:>5.1f}分｜{r['read']:>6,}读｜{r['date']}｜{r['title'][:36]}")
    print(f"        → 建议：去掉标题里的时效词，正文改成年度版，让它重新具备长尾价值")
no_place = [r for r in live if not re.search(PLACE, r["title"])]
print(f"  2. 标题缺地点名的 {len(no_place)} 篇（{len(no_place)/len(live)*100:.0f}%）"
      f"——『南京XX怎么预约』是典型搜索句式，缺地名会丢搜索流量")
for r in sorted(no_place, key=lambda x: -x["read"])[:6]:
    print(f"     {r['read']:>6,}读｜{r['title'][:40]}")
no_album = [r for r in live if not r["album"]]
if no_album:
    print(f"  3. 无合集 {len(no_album)} 篇，合集是搜索结果的聚合入口，建议补齐")

# ---------- H 真实搜一搜数据（后台抓取后回填）----------
if "--channels" in sys.argv:
    cp = sys.argv[sys.argv.index("--channels") + 1]
    with open(cp, encoding="utf-8") as f: ch = json.load(f)
    valid = [x for x in ch.get("items", []) if x.get("ok") and x.get("channels")]
    print("\n" + "=" * 84)
    print(f"【H】★真实搜一搜数据（后台 appmsganalysis 渠道构成，{ch.get('fetched_at','')}）")
    print(f"    有效样本 {len(valid)} 篇｜来源：{ch.get('source','')}")
    print("=" * 84)
    if valid:
        print("\n  全样本平均渠道构成：")
        for k in ch.get("channels_order", ["搜一搜","聊天会话","其它","公众号消息","公众号主页","推荐","朋友圈"]):
            print(f"    {k:<8}{mean([x['channels'].get(k, 0) for x in valid]):>6.1f}%")
        ss = [(x, x["channels"].get("搜一搜", 0)) for x in valid]
        print(f"\n  ▼ 搜一搜占比 TOP10")
        for x, v in sorted(ss, key=lambda t: -t[1])[:10]:
            print(f"    {v:>5.1f}%｜{x.get('read',0):>6,}读｜{x['date']}｜{x['title'][:34]}")
        print(f"\n  ▼ 搜一搜占比 BOTTOM8")
        for x, v in sorted(ss, key=lambda t: t[1])[:8]:
            print(f"    {v:>5.1f}%｜{x.get('read',0):>6,}读｜{x['date']}｜{x['title'][:34]}")
        # 关键验证：打分是否预测真实搜一搜占比
        for r in live: score(r)
        pairs = []
        for x in valid:
            m = [r for r in live if r["title"].startswith(x["title"][:12])]
            if m: pairs.append((max(m, key=lambda r: r["sscore"])["sscore"], x["channels"].get("搜一搜", 0)))
        if len(pairs) >= 5:
            c = st.correlation([p[0] for p in pairs], [p[1] for p in pairs])
            print(f"\n  ★验证：搜索友好度打分 vs 真实搜一搜占比  r = {c:+.3f}（{len(pairs)} 篇匹配）")
            print("    r 接近 0 或为负 → 【B】~【D】的推算结论成立：标题堆搜索词换不来搜一搜流量")
            print("    r 明显为正    → 推翻推算：该按搜索友好度改标题")

if "--json" in sys.argv:
    p = sys.argv[sys.argv.index("--json") + 1]
    with open(p, "w", encoding="utf-8") as f:
        json.dump([{k: v for k, v in r.items() if k != "hits"} for r in live], f, ensure_ascii=False, indent=1)
    print(f"\n[已导出] {p}")
