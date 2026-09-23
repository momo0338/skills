#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
搜一搜 / 阅读渠道构成 抓取（后台内部接口，需登录态）

接口来源：本文件**不自己发明 URL**，全部照抄 `mp-publish/SKILL.md` §八.2 的实测记录：

  单篇明细  GET /misc/appmsganalysis?action=detailpage&msgid=<MID>&publish_date=<YYYY-MM-DD>
              &type=int&pageVersion=1&token=<t>&lang=zh_CN
      → 返回 HTML，读 document.body.innerText
      → 「阅读渠道构成」7 项百分比，按图例固定顺序：
        搜一搜 → 聊天会话 → 其它 → 公众号消息 → 公众号主页 → 推荐 → 朋友圈
      → 顶部还有：阅读人数 / 平均阅读时长 / 完读率 / 新增关注 / 分享 / 在看 / 收藏 等

  账号底数  GET /misc/useranalysis?token=<t>&lang=zh_CN      # 关注来源含「搜一搜」

为什么不用 datacube：个人订阅号无权限，21 个接口全 48001（`wx_stats.py selftest` 可复验）。

用法（ego 浏览器里需先扫码登录）：
    export GZH_WORK_DIR="/path/to/账号目录"
    python3 search_fetch.py --check                      # 检查登录态 + 取 token
    python3 search_fetch.py --limit 30                   # 抓最近 30 篇的渠道构成
    python3 search_fetch.py --msgid 1000000172 --date 2026-09-16   # 只抓单篇
    python3 search_fetch.py --account-summary            # 账号层面的关注来源

产出：~/.cache/weixin/publish_records/search_channels_<YYYYMMDD_HHMM>.json
      随后用 search_analysis.py --channels <该json> 做分析。

⚠️ 口径警告：detailpage 的「阅读人数」是区间口径且页面可能滞后；
   appmsgpublish 的 read 是累计 live 值。比大小一律用后者，或注明口径。
"""
import os, sys, json, re, subprocess, tempfile, csv
from datetime import datetime

EGO = os.path.expanduser("~/.local/bin/ego-browser")
UID = os.popen("id -u").read().strip() or "501"
CHANNELS = ["搜一搜", "聊天会话", "其它", "公众号消息", "公众号主页", "推荐", "朋友圈"]
LOGIN_BAD = ["扫码", "微信扫一扫", "登录超时", "请重新登录", "loginpage", "系统繁忙"]


def run_ego(js: str, timeout: int = 600) -> str:
    if not os.path.exists(EGO):
        sys.exit(f"未找到 ego-browser：{EGO}")
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
        f.write(js); path = f.name
    try:
        p = subprocess.run(["launchctl", "asuser", UID, EGO, "nodejs"],
                           stdin=open(path), capture_output=True, text=True, timeout=timeout)
        return (p.stdout or "") + (p.stderr or "")
    finally:
        os.unlink(path)


def check_and_token(timeout=90) -> str:
    return run_ego('''
const task = await useOrCreateTaskSpace('搜一搜抓取')
// 必须用首页：/cgi-bin/home 在登录态失效时是"登录超时"死页，不显示二维码
await openOrReuseTab('https://mp.weixin.qq.com/', { wait: true, timeout: 40 })
const href = String(await js('location.href'))
const t = String(await snapshotText())
const m = href.match(/token=(\\d+)/)
cliLog('HREF=' + href)
cliLog('TOKEN=' + (m ? m[1] : 'none'))
// ★强信号优先：URL 带 token 且落在后台页 => 必定已登录。
//   不能只用文本黑名单判定：后台首页有运营文案「推荐带来6.5万阅读量，微信扫码查看
//   你的一周创作总结」，含「扫码」二字，2026-09-22 实测导致把已登录误判成未登录。
const strongIn = /token=\\d+/.test(href) && /cgi-bin\\/(home|appmsg|masssend)/.test(href)
const strongOut = href.includes('loginpage') || /微信扫一扫|登录超时|请重新登录/.test(t)
const ok = strongIn || (!strongOut && /token=\\d+/.test(href))
cliLog('LOGGED_IN=' + (ok ? 'yes' : 'no'))
if (ok) cliLog('REASON=URL 带 token 且位于后台页')
else cliLog('REASON=' + (href.includes('loginpage') ? '跳转到 loginpage' : '未取到 token'))
''', timeout=timeout)


def parse_token(out: str):
    m = re.search(r"TOKEN=(\d+)", out)
    return m.group(1) if m else None


def parse_detail(text: str) -> dict:
    """从 detailpage 的 innerText 抠出渠道百分比与顶部指标。

    ⚠️ 实测结构（2026-09-22，与 mp-publish 文档的"固定图例顺序"描述不一致）：
       "阅读渠道构成 / Chart / Bar chart with 7 bars / ... / 99.3% / 0.2% / ...(7 个值) /
        推荐 / 聊天会话 / ...(7 个名) / 0% / 25% / ...(坐标轴) / End of interactive chart"
       即**数值在前、图例名在后，两者都按数值降序**，必须按位置 zip 配对。
       且图例出现之后的 % 是坐标轴刻度（0/25/50/75/100/125），必须丢弃。
    """
    res = {"channels": {}, "top": {}}
    t = text.replace("\\n", "\n")
    for key in ["阅读人数", "阅读次数", "平均阅读时长", "完读率", "新增关注",
                "分享", "在看", "赞赏", "留言", "收藏", "听全文"]:
        m = re.search(key + r"[^\d]{0,12}([\d,]+(?:\.\d+)?)", t)
        if m:
            res["top"][key] = m.group(1).replace(",", "")
    i = t.find("阅读渠道构成")
    if i >= 0:
        seg = t[i:]
        e = seg.find("End of interactive chart")
        if e > 0: seg = seg[:e]
        nums, names = [], []
        for line in seg.split("\n"):
            line = line.strip()
            if re.fullmatch(r"(\d+(?:\.\d+)?)%", line):
                if not names: nums.append(float(line[:-1]))
            elif line in CHANNELS and line not in names:
                names.append(line)
        if names and len(nums) == len(names):
            res["channels"] = dict(zip(names, nums))
        elif nums:
            res["raw_numbers"] = nums[:7]
    return res


def report_links(token: str) -> list:
    """从内容分析 report 页提取单篇「详情」链接里的真实 msgid。

    CSV 里的 msgid 是**发表批次号**（1000000172），detailpage 接口不认，返回
    「系统错误(200002)」；真实 id 是 **appmsgid_序号**（2247488280_1）。
    """
    url = (f"https://mp.weixin.qq.com/misc/appmsganalysis?action=report&type=daily_v2"
           f"&token={token}&lang=zh_CN")
    js = f"""
const task = await useOrCreateTaskSpace('搜一搜抓取')
await openOrReuseTab({json.dumps(url)}, {{ wait: true, timeout: 45 }})
await new Promise(r => setTimeout(r, 2500))
cliLog('@@@LINKS@@@')
cliLog(String(await js(String.raw`JSON.stringify([...document.querySelectorAll('a')]
  .map(a => a.getAttribute('href') || '').filter(h => h.includes('msgid=')))`)))
cliLog('@@@TEXT@@@')
cliLog(String(await js('document.body.innerText')).slice(0, 8000))
"""
    out = run_ego(js, timeout=150)
    seg = out.split("@@@LINKS@@@")[-1]
    part, _, body = seg.partition("@@@TEXT@@@")
    try:
        arr = json.loads(part.strip()[part.strip().find("["):part.strip().rfind("]") + 1])
    except Exception:
        return []
    # 页面正文里标题与发表时间成对出现，顺序与「详情」链接一致
    # 标题与「发表时间」之间常有空行，故用 \\n+ 而非 \\n
    pairs = re.findall(r"([^\\n]+)\\n+发表时间：(\\d{4})/(\\d{2})/(\\d{2})", body.replace("\\\\n", "\\n"))
    res, seen = [], set()
    for idx, h in enumerate(arr):
        m = re.search(r"msgid=([\d_]+)&publish_date=([\d-]+)", h)
        if not m or m.group(1) in seen:
            continue
        seen.add(m.group(1))
        title = pairs[idx][0].strip() if idx < len(pairs) else "(未知标题)"
        res.append({"msgid": m.group(1), "date": m.group(2), "title": title[:40], "read": 0})
    return res


def load_rows(work_dir: str, limit: int):
    hits = sorted(f for f in os.listdir(work_dir) if f.startswith("发表记录") and f.endswith(".csv"))
    if not hits:
        sys.exit(f"未找到发表记录 CSV（{work_dir}）")
    rows = []
    with open(os.path.join(work_dir, hits[-1]), encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            if not (r.get("title") or "").strip() or r.get("deleted") == "True":
                continue
            n = lambda k: int(r[k]) if (r.get(k) or "").strip().isdigit() else 0
            rows.append({"msgid": r.get("msgid", ""), "date": r["date"],
                         "title": r["title"][:40], "read": n("read")})
    rows.sort(key=lambda x: x["date"], reverse=True)
    return rows[:limit]


def fetch_details(token: str, rows: list, out_path: str):
    items = []
    for i, r in enumerate(rows, 1):
        url = (f"https://mp.weixin.qq.com/misc/appmsganalysis?action=detailpage"
               f"&msgid={r['msgid']}&publish_date={r['date']}&type=int&pageVersion=1"
               f"&token={token}&lang=zh_CN")
        js = f'''
const task = await useOrCreateTaskSpace('搜一搜抓取')
await openOrReuseTab({json.dumps(url)}, {{ wait: true, timeout: 35 }})
await new Promise(r => setTimeout(r, 1200))
cliLog('@@@TXT@@@')
cliLog(String(await js('document.body.innerText')).slice(0, 6000))
'''
        body = run_ego(js, timeout=120).split("@@@TXT@@@")[-1]
        if "阅读渠道构成" not in body and "阅读人数" not in body:
            print(f"  [{i}/{len(rows)}] x 无数据（页面滞后或 msgid 不匹配）| {r['title'][:24]}")
            items.append({**r, "ok": False})
            continue
        d = parse_detail(body)
        items.append({**r, "ok": True, **d})
        tc = max(d["channels"].items(), key=lambda kv: kv[1]) if d["channels"] else ("-", 0)
        print(f"  [{i}/{len(rows)}] ok 搜一搜 {d['channels'].get('搜一搜', 0):.1f}%"
              f" | 最高渠道 {tc[0]} {tc[1]:.1f}% | {r['title'][:24]}")
    payload = {"fetched_at": datetime.now().isoformat(timespec="seconds"),
               "source": "mp.weixin.qq.com /misc/appmsganalysis?action=detailpage",
               "channels_order": CHANNELS, "items": items}
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    print(f"\n[已落盘] {out_path}（{sum(1 for x in items if x['ok'])}/{len(items)} 篇有效）")


def account_summary(token: str):
    url = f"https://mp.weixin.qq.com/misc/useranalysis?token={token}&lang=zh_CN"
    out = run_ego(f'''
const task = await useOrCreateTaskSpace('搜一搜抓取')
await openOrReuseTab({json.dumps(url)}, {{ wait: true, timeout: 40 }})
await new Promise(r => setTimeout(r, 1500))
cliLog('@@@TXT@@@')
cliLog(String(await js('document.body.innerText')).slice(0, 4000))
''', timeout=120)
    print(out.split("@@@TXT@@@")[-1][:3000])


if __name__ == "__main__":
    # 有副作用的脚本：--help 只打印用法，绝不发起抓取
    if "-h" in sys.argv or "--help" in sys.argv:
        print(__doc__); sys.exit(0)
    a = sys.argv[1:]
    work = os.environ.get("GZH_WORK_DIR") or os.getcwd()
    if "--check" in a:
        out = check_and_token()
        tk = parse_token(out)
        print(out)
        print(f"\n登录态：{'有效' if 'LOGGED_IN=yes' in out else '失效，需扫码'}｜token：{tk or '未取到'}")
    elif "--account-summary" in a:
        tk = parse_token(check_and_token())
        if not tk: sys.exit("取不到 token，请先扫码登录")
        account_summary(tk)
    elif "--msgid" in a and "--date" in a:
        tk = parse_token(check_and_token())
        if not tk: sys.exit("取不到 token，请先扫码登录")
        fetch_details(tk, [{"msgid": a[a.index("--msgid") + 1], "date": a[a.index("--date") + 1],
                            "title": "(手动指定)", "read": 0}],
                      os.path.expanduser("~/.cache/weixin/publish_records/search_channels_single.json"))
    else:
        limit = int(a[a.index("--limit") + 1]) if "--limit" in a else 30
        tk = parse_token(check_and_token())
        if not tk:
            sys.exit("未登录或 token 取不到：请在 ego 浏览器里扫码登录 mp.weixin.qq.com 后重试。\n"
                     "（datacube 接口对个人号无权限，必须走后台网页。）")
        links = report_links(tk)
        if not links:
            sys.exit("未能从内容分析页取到 msgid 列表（页面结构可能变了）")
        if limit: links = links[:limit]
        rows = links
        print(f"内容分析页取到 {len(links)} 篇真实 msgid（appmsgid_序号）")
        fetch_details(tk, rows, os.path.expanduser(
            f"~/.cache/weixin/publish_records/search_channels_{datetime.now():%Y%m%d_%H%M}.json"))
