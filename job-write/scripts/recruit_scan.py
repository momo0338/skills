#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""招聘 / 招考信息源每日巡检（job-write 配套脚本）

双通道巡检，输出"今天新增了哪些招聘信息"：

  通道 1 · wx   微信公众号侧（免登录）
      调 `opencli weixin search "<关键词>" -f json`（走搜狗微信开放检索），
      按关键词组批量检索，拿到 标题 / 摘要 / 发布时间 / 链接。

  通道 2 · web  官方站点侧（免登录）
      轮询政府人社网、招聘平台的列表页，正则提取"招聘·招考·公告"类条目标题与链接。

两条通道的命中结果都会与状态文件里的"已见过标题集合"做 diff，
因此**新增判定与运行频率无关**，每天跑、隔天跑都不会重复刷屏。

设计取舍（为什么不用第三方库）：
  - 只用标准库（urllib / re / json），零依赖 → automation、cron 都能直接拉起来跑。
  - 官网解析用"贪心抓 <a> 标题 + 关键词过滤 + 噪音词排除"，不做站点专属爬虫；
    宁可漏抓，也不引入一堆易碎的 CSS 选择器。

用法：
    python3 recruit_scan.py                          # 双通道巡检，打印报告
    python3 recruit_scan.py --mode wx                # 只巡检公众号
    python3 recruit_scan.py --mode web               # 只巡检官网
    python3 recruit_scan.py --state s.json --out r.md
    python3 recruit_scan.py --all                    # 忽略状态，输出全部命中（首次建库）
    python3 recruit_scan.py --mode web --line B      # P2：只扫 B 线（sources.yaml）
    python3 recruit_scan.py --no-sources             # P2：强制用内置 WEB_SOURCES

P2（2026-09-17）配置驱动与健康检查：
  - 官网源默认读 sources.yaml（probe_sources.py 生成），按 enabled/kind 分流：
    gov_list|gov_bm|self_list|hotjob → 列表扫描；self_spa → 哨兵（hash 变更告警）；
    beisen/zhaopin/moka/job51/chinahr → P3 适配器，暂跳过。
  - 健康状态写 <state目录>/sources-health.json（last_ok_at / consecutive_fail / last_code）；
    连续失败 ≥3 在报告顶部列「源告警」，防"源静默失效"。

实测结论（2026-09-16）：
  - `opencli` 必须用**全路径** `/usr/local/bin/opencli`（沙箱 PATH 里没有）；
    超时要用环境变量 `OPENCLI_BROWSER_COMMAND_TIMEOUT`，命令行 `--timeout` 不存在。
  - 首次调用较慢，重复调用约 3 秒；返回体前面混有 node 警告，需从第一个 `[` 截起。
"""

import argparse
import json
import os
import re
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.request
from html import unescape

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

OPENCLI = "/usr/local/bin/opencli"

# ⚠️ 沙箱 / 代理环境（本机走 fake-IP 网关）下，urllib 对政府网 HTTPS 会报
#    `SSL: CERTIFICATE_VERIFY_FAILED`，而 curl 正常。巡检是只读公开页面，
#    故默认放宽校验；需要严格校验时加 --verify-ssl。
SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE

# ── 命中 / 噪音 关键词 ────────────────────────────────────────────────
HIT = re.compile(r"招聘|校招|招考|选聘|选调|遴选|事业单位|编内|岗位表|人才引进|资格审查|见习|实习")
NOISE = re.compile(r"退休|工伤|送达|催告|催缴|补贴.*名单|职称评审|考试成绩|面试成绩|体检.*公示|"
                   r"拟聘.*公示|招聘.{0,8}公示|"          # 录用公示＝招聘已结束的环节，不是招聘公告
                   r"取消.*公告|年审|备案|注销|遗失|作废|统计公报|满意度|"
                   # 制度/附件类（是规则文件，不是招聘公告）
                   r"表格|附件|考试大纲|人员办法|工作意见|处理规定|实施意见|意见$|详见|"
                   # 栏目导航页
                   r"专栏|导航|首页|更多")

# ── 公众号巡检关键词组（通道 1）─────────────────────────────────────
# ⚠️ opencli 每次调用要拉起浏览器（首次 ~60s，后续 ~3s），查询越多越慢。
#    建议 3–5 个关键词；需要更细的分组时，用 --wx-query 临时追加。
WX_QUERIES = [
    "南京 招聘 公告",
    "南京 校招",
    "江苏 事业单位 招聘 公告",
    "江苏 国企 招聘 2027",
    "江苏 银行 2027 校园招聘 公告",  # 银行批次集中、文本型，09-16 银行专题补充
]

# ── 官网源（通道 2）──────────────────────────────────────────────────
# P2 起支持外部 sources.yaml（probe_sources.py 生成，配置驱动）：
#   --sources 路径 缺省取 DEFAULT_SOURCES_YAML；文件缺失时回退到内置 WEB_SOURCES。
# yaml 字段：id/name/group/line/tier/kind/url/enabled/probe
# kind 分流：gov_list|gov_bm|self_list|hotjob → 正常列表扫描；
#            self_spa → 哨兵（title-hash 变更告警）；
#            beisen|zhaopin_*|moka|job51|chinahr → P3 适配器，暂不扫。
DEFAULT_SOURCES_YAML = ("/Users/zhugx/codeup/obsidian/03-工作记录/"
                        "码上职业/工具/sources.yaml")

# url  列表页地址；base 用于把相对链接补成绝对
# 选源原则：优先"招聘专栏列表页"，不要放网站首页（首页 90% 是无关政务新闻）
WEB_SOURCES = [
    {
        "name": "江苏省属事业单位公开招聘专栏",
        "url": "http://jshrss.jiangsu.gov.cn/col/col93339/index.html",
        "base": "http://jshrss.jiangsu.gov.cn/",
    },
    {
        "name": "江苏全省公办技工院校公开招聘",
        "url": "http://jshrss.jiangsu.gov.cn/col/col93485/index.html",
        "base": "http://jshrss.jiangsu.gov.cn/",
    },
    {
        "name": "江苏人事人才公共服务网",
        "url": "http://jshrss.jiangsu.gov.cn/col/col57142/index.html",
        "base": "http://jshrss.jiangsu.gov.cn/",
    },
    {
        "name": "南京市人力资源和社会保障局",
        "url": "http://rsj.nanjing.gov.cn/",
        "base": "http://rsj.nanjing.gov.cn/",
    },
    {
        "name": "泰州市人力资源和社会保障局",
        "url": "https://rsj.taizhou.gov.cn/",
        "base": "https://rsj.taizhou.gov.cn/",
    },
    {
        "name": "国家能源集团招聘",
        "url": "https://zhaopin.chnenergy.com.cn/",
        "base": "https://zhaopin.chnenergy.com.cn/",
    },
    {
        "name": "国聘（央企统一招聘平台）",
        "url": "https://www.iguopin.com/",
        "base": "https://www.iguopin.com/",
    },
]


# ══════════════════════════════════════════════════════════════════
#  工具
# ══════════════════════════════════════════════════════════════════
def _curl_fetch(url: str, timeout: int = 20) -> str:
    """urllib 被 TLS 指纹/legacy renegotiation 拒时，用 /usr/bin/curl（LibreSSL）兜底。"""
    curl = "/usr/bin/curl" if os.path.exists("/usr/bin/curl") else "curl"
    p = subprocess.run(
        [curl, "-sk", "-L", "--compressed", "-A", UA, "-m", str(timeout),
         "-o", "-", url],
        capture_output=True, timeout=timeout + 5)
    return p.stdout.decode("utf-8", "ignore")


def fetch(url: str, timeout: int = 20, verify_ssl: bool = False) -> str:
    """取回网页文本，自动处理 gzip 与 charset；urllib 失败自动 curl 兜底。"""
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,*/*",
            "Accept-Encoding": "gzip, deflate",
        })
        ctx = None if verify_ssl else SSL_CTX
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            raw = resp.read()
            if "gzip" in resp.headers.get("Content-Encoding", ""):
                import gzip
                try:
                    raw = gzip.decompress(raw)
                except Exception:
                    pass
            ctype = resp.headers.get("Content-Type", "")
            m = re.search(r"charset=([\w\-]+)", ctype, re.I)
            for enc in ([m.group(1)] if m else []) + ["utf-8", "gbk", "gb18030"]:
                try:
                    return raw.decode(enc)
                except Exception:
                    continue
            return raw.decode("utf-8", "ignore")
    except Exception:
        return _curl_fetch(url, timeout)


def clean_title(s: str) -> str:
    s = re.sub(r"<[^>]+>", "", s)
    s = unescape(s)
    s = re.sub(r"[\s\u3000]+", " ", s)
    return s.strip(" \u3000-—|·\t\r\n")


def is_hit(title: str) -> bool:
    if not (8 <= len(title) <= 90):
        return False
    if NOISE.search(title):
        return False
    return bool(HIT.search(title))


def abspath(href: str, base: str) -> str:
    if href.startswith("http"):
        return href
    if href.startswith("//"):
        return "https:" + href
    if href.startswith("/"):
        m = re.match(r"https?://[^/]+", base)
        return (m.group(0) if m else base.rstrip("/")) + href
    return base.rstrip("/") + "/" + href.lstrip("./")


# ══════════════════════════════════════════════════════════════════
#  通道 1：公众号（搜狗微信检索）
# ══════════════════════════════════════════════════════════════════
SOGOU_URL = "https://weixin.sogou.com/weixin?type=2&ie=utf8&query={q}"


def parse_sogou(html_text: str):
    """解析搜狗微信搜索结果页。

    实测结构（2026-09-16，两种模板都要兼容）：
      <div class="txt-box">
        <h3><a href="/link?url=...">标题（可含 <!--red_beg--> 高亮注释）</a></h3>
        <p class="txt-info" ...>摘要</p>
        <div class="s-p">
          <span class="all-time-y2">公众号名</span>          ← 模板 A
          <span class="s2"><script>document.write(timeConvert('1789520496'))</script></span>
        </div>
      </div>
    模板 B 的号名在 <a class="account">，时间在 <div class="s-p" t="...">。
    ⚠️ 结果链接是 sogou 跳转链（有反爬、会过期），只用来"发现"，
       真实原文链接需另行溯源（见 job-write §3.1 的官方公告网址口径）。
    """
    out = []
    for blk in html_text.split('<div class="txt-box">')[1:]:
        m = re.search(r"<h3>.*?<a[^>]*>(.*?)</a>", blk, re.S)
        if not m:
            continue
        title = clean_title(m.group(1))
        if not title:
            continue
        info = re.search(r'<p class="txt-info"[^>]*>(.*?)</p>', blk, re.S)
        acc = (re.search(r'class="all-time-y2"[^>]*>(.*?)</span>', blk, re.S)
               or re.search(r'class="account"[^>]*>(.*?)</a>', blk, re.S))
        ts = (re.search(r"timeConvert\('(\d{9,11})'\)", blk)
              or re.search(r't="(\d{9,11})"', blk))
        href = re.search(r'<h3>.*?href="([^"]+)"', blk, re.S)
        date = ""
        if ts:
            date = time.strftime("%Y-%m-%d", time.localtime(int(ts.group(1))))
        url = ("https://weixin.sogou.com" + unescape(href.group(1))) if href else ""
        out.append({
            "title": title,
            "source": clean_title(acc.group(1)) if acc else "公众号检索",
            "date": date,
            "url": url,
            "note": clean_title(info.group(1))[:60] if info else "",
        })
    return out


def scan_wx(queries, engine="sogou", verbose=True, days=30):
    """公众号巡检。engine=sogou（默认，纯 HTTP，稳定）；engine=opencli（浏览器，易被限流）。

    days：只保留最近 N 天发布的条目。⚠️ 搜狗是按"相关度"排序，不加时效过滤会
          混进 2016–2024 的陈旧文章（标题里照样有"南京校招"），必须用日期卡住。
    """
    items = []
    if engine == "opencli":
        return scan_wx_opencli(queries, verbose)

    from datetime import datetime, timedelta
    from urllib.parse import quote
    cutoff = (datetime.now() - timedelta(days=days)).date() if days else None

    for q in queries:
        url = SOGOU_URL.format(q=quote(q))
        try:
            html = fetch(url, timeout=25)
        except Exception as e:
            if verbose:
                print(f"  ⚠️  [{q}] 搜狗检索失败：{str(e)[:70]}", file=sys.stderr)
            continue
        if "antispider" in html or "请输入验证码" in html:
            if verbose:
                print(f"  ⚠️  [{q}] 触发搜狗验证码，跳过（稍后重试或换关键词）", file=sys.stderr)
            continue
        got = parse_sogou(html)
        kept = []
        for it in got:
            if cutoff and it["date"]:
                try:
                    if datetime.strptime(it["date"], "%Y-%m-%d").date() < cutoff:
                        continue
                except Exception:
                    pass
            kept.append(it)
        if verbose:
            print(f"  · [{q}] 命中 {len(got)} 条，时效内 {len(kept)} 条", file=sys.stderr)
        items += kept
        time.sleep(2)          # 温和一点，降低被限流概率
    return items


def scan_wx_opencli(queries, verbose=True):
    """备用通道：opencli 浏览器检索（首次慢、连续调用易被搜狗限流）。"""
    items, seen_q = [], set()
    env = dict(os.environ, OPENCLI_BROWSER_COMMAND_TIMEOUT="240",
               PATH=os.environ.get("PATH", "") + ":/usr/local/bin")
    for q in queries:
        if q in seen_q:
            continue
        seen_q.add(q)
        try:
            p = subprocess.run(
                [OPENCLI, "weixin", "search", q, "--limit", "10", "-f", "json"],
                capture_output=True, text=True, timeout=150, env=env,
            )
            out = p.stdout or ""
            i = out.find("[")
            if i < 0:
                if verbose:
                    print(f"  ⚠️  [{q}] 无 JSON 返回（多为搜狗限流）", file=sys.stderr)
                continue
            data = json.loads(out[i:])
        except subprocess.TimeoutExpired:
            if verbose:
                print(f"  ⚠️  [{q}] opencli 超时跳过", file=sys.stderr)
            continue
        except Exception as e:
            if verbose:
                print(f"  ⚠️  [{q}] 解析失败：{str(e)[:80]}", file=sys.stderr)
            continue

        for it in data if isinstance(data, list) else []:
            title = clean_title(it.get("title", ""))
            if not title:
                continue
            items.append({
                "title": title,
                "source": "公众号检索",
                "date": it.get("publish_time", ""),
                "url": it.get("url", ""),
                "note": (it.get("summary") or "")[:60].replace("\n", " "),
            })
        time.sleep(1)
    return items


# ══════════════════════════════════════════════════════════════════
#  通道 2：官网列表页
# ══════════════════════════════════════════════════════════════════
def scan_web(sources, verbose=True, verify_ssl=False):
    items, statuses = [], []
    for s in sources:
        ok = True
        try:
            html = fetch(s["url"], verify_ssl=verify_ssl)
        except Exception as e:
            ok = False
            if verbose:
                print(f"  ⚠️  [{s['name']}] 抓取失败：{str(e)[:70]}", file=sys.stderr)
            statuses.append((s.get("id", s["name"]), False, 0))
            continue
        for m in re.finditer(
                r'<a\s[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', html, re.S | re.I):
            href, inner = m.group(1), m.group(2)
            title = clean_title(inner)
            # 有些站把标题放在 title 属性里
            if not title or len(title) < 8:
                tm = re.search(r'title=["\']([^"\']{8,90})["\']', m.group(0))
                if tm:
                    title = clean_title(tm.group(1))
            if not is_hit(title):
                continue
            if href.lower().startswith(("javascript:", "#", "mailto:")):
                continue
            if re.search(r"/col/col\d+/index\.html$", href):
                continue   # 栏目首页导航，不是具体公告
            items.append({
                "title": title,
                "source": s["name"],
                "date": "",
                "url": abspath(href, s["base"]),
                "note": "",
            })
        statuses.append((s.get("id", s["name"]), True, 200))
    # 同一页里同名条目去重
    uniq, seen = [], set()
    for it in items:
        if it["title"] in seen:
            continue
        seen.add(it["title"])
        uniq.append(it)
    return uniq, statuses


# ══════════════════════════════════════════════════════════════════
#  sources.yaml 解析 + 源健康检查（P2）
# ══════════════════════════════════════════════════════════════════
SCAN_KINDS = {"gov_list", "gov_bm", "self_list", "hotjob"}
SENTINEL_KINDS = {"self_spa"}
ADAPTER_KINDS = {"zhaokao"}      # P3：recruit_adapters.scan_zhaokao


def load_sources_yaml(path):
    """解析 probe_sources.py 生成的扁平 YAML。返回 list[dict]；文件缺失返回 []。"""
    if not path or not os.path.exists(path):
        return []
    rows, cur = [], None
    with open(path, encoding="utf-8") as f:
        for ln in f:
            if ln.startswith("- id:"):
                cur = {"id": ln.split(":", 1)[1].strip()}
                rows.append(cur)
            elif cur is not None and ln.startswith("  "):
                m = re.match(r"  (\w+): (.*)\n?$", ln)
                if m and m.group(1) != "probe":
                    cur[m.group(1)] = m.group(2).strip().strip('"')
    return rows


def select_web_sources(yaml_path, line="all", verbose=True):
    """从 yaml 选出本次要跑的源。返回 (scan_list, sentinel_list, adapter_list, skipped)。"""
    rows = load_sources_yaml(yaml_path)
    if not rows:
        if verbose and yaml_path:
            print(f"  ⚠️  sources.yaml 不存在（{yaml_path}），回退内置 WEB_SOURCES", file=sys.stderr)
        return ([{"name": s["name"], "url": s["url"], "base": s["base"],
                  "id": s["name"], "kind": "gov_list"} for s in WEB_SOURCES], [], [], 0)
    scan, sentinel, adapter, skipped = [], [], [], 0
    for r in rows:
        if r.get("enabled") != "true":
            continue
        if line != "all" and r.get("line") != line:
            continue
        kind = r.get("kind", "gov_list")
        base = re.match(r"(https?://[^/]+)", r["url"]).group(1) + "/"
        entry = {"id": r["id"], "name": f"{r['name']}", "url": r["url"],
                 "base": base, "kind": kind, "group": r.get("group", "")}
        if kind in SCAN_KINDS:
            scan.append(entry)
        elif kind in SENTINEL_KINDS:
            sentinel.append(entry)
        elif kind in ADAPTER_KINDS:
            adapter.append(entry)
        else:
            skipped += 1
    return scan, sentinel, adapter, skipped


def load_health(path):
    if path and os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_health(path, health):
    if not path:
        return
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(health, f, ensure_ascii=False, indent=1)


def update_health(health, sid, ok, code=0):
    h = health.setdefault(sid, {"consecutive_fail": 0, "last_ok_at": "", "last_code": 0})
    if ok:
        h.update({"consecutive_fail": 0, "last_ok_at": time.strftime("%Y-%m-%d %H:%M"),
                  "last_code": code})
    else:
        h["consecutive_fail"] = h.get("consecutive_fail", 0) + 1
        h["last_code"] = code
        h["last_fail_at"] = time.strftime("%Y-%m-%d %H:%M")
    return h


def scan_sentinels(sentinels, health, verbose=True, verify_ssl=False):
    """哨兵：SPA 源只比 <title>+正文长度的 hash，变了就报「需人工查看」。"""
    alerts = []
    for s in sentinels:
        try:
            html = fetch(s["url"], verify_ssl=verify_ssl)
            title = re.search(r"<title[^>]*>(.*?)</title>", html, re.S | re.I)
            sig = (unescape(title.group(1)).strip() if title else "") + "|" + str(len(html))
            ok = True
        except Exception as e:
            sig = ""
            ok = False
            if verbose:
                print(f"  ⚠️  [哨兵·{s['name']}] 抓取失败：{str(e)[:60]}", file=sys.stderr)
        h = update_health(health, "sentinel::" + s["id"], ok)
        prev = h.get("last_sig", "")
        if ok and prev and prev != sig:
            alerts.append(f"🔔 哨兵·{s['name']} 页面有更新（hash 变化），需人工查看：{s['url']}")
        if ok:
            h["last_sig"] = sig
    return alerts


# ══════════════════════════════════════════════════════════════════
#  主流程
# ══════════════════════════════════════════════════════════════════
def load_state(path):
    if path and os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"seen": []}


def save_state(path, state):
    if not path:
        return
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    state["seen"] = sorted(set(state.get("seen", [])))[-4000:]   # 只留最近 4000 条
    state["updated"] = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=1)


def render_md(new_items, all_items, scanned_at, mode_desc, alerts=None):
    lines = [
        f"# 招聘信息巡检 · 新增 {len(new_items)} 条",
        "",
        f"> 巡检时间：{scanned_at} ｜ 通道：{mode_desc} ｜ 本次命中 {len(all_items)} 条（去重后）",
        "> 本文件由 `job-write/scripts/recruit_scan.py` 自动生成；标题去重基于状态快照，只列出**首次出现**的条目。",
        "",
    ]
    if alerts:
        lines += ["## 🚨 源告警（先处理，再看下面的新增）", ""]
        lines += [f"- {a}" for a in alerts]
        lines += [""]
    if not new_items:
        lines += ["**本次未发现新增招聘信息。**", ""]
        return "\n".join(lines)

    lines += ["| # | 标题 | 来源 | 时间 | 链接 |", "|---|---|---|---|---|"]
    for i, it in enumerate(new_items, 1):
        title = it["title"].replace("|", "丨")
        lines.append(
            f"| {i} | {title} | {it['source']} | {it.get('date') or '—'} | [打开]({it['url']}) |"
        )
    lines += ["", "---", "", "## 待分拣", "",
              "- [ ] 判断 A 线（2027 校招）/ B 线（事业单位招考）/ 其他（教师、社招）",
              "- [ ] 入库到对应台账（`2027年校园招聘/01-素材台账-ima招聘库.md` 或 `事业单位招考/01-素材台账.md`）",
              "- [ ] 图片海报型来源需回官方站补岗位与截止日", ""]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="招聘/招考信息源每日巡检")
    ap.add_argument("--mode", choices=["wx", "web", "both"], default="both")
    ap.add_argument("--wx-engine", choices=["sogou", "opencli"], default="sogou",
                    help="公众号检索引擎：sogou=HTTP 直抓（默认，稳）；opencli=浏览器（易限流）")
    ap.add_argument("--wx-days", type=int, default=30, help="公众号结果只保留最近 N 天（默认 30，0=不限）")
    ap.add_argument("--wx-query", action="append", default=[], metavar="关键词",
                    help="临时追加检索关键词（可多次；默认组见 WX_QUERIES）")
    ap.add_argument("--state", default="", help="状态文件（记录已见标题）")
    ap.add_argument("--out", default="", help="报告输出 Markdown 路径")
    ap.add_argument("--sources", default=DEFAULT_SOURCES_YAML,
                    help="sources.yaml 路径（P2 配置驱动；文件缺失回退内置 WEB_SOURCES）")
    ap.add_argument("--line", choices=["A", "B", "all"], default="all",
                    help="只扫某条线（A=校招 B=事业编，默认全扫）")
    ap.add_argument("--health", default="",
                    help="源健康状态文件（缺省取 state 同目录 sources-health.json）")
    ap.add_argument("--no-sources", action="store_true",
                    help="强制使用内置 WEB_SOURCES（忽略 sources.yaml）")
    ap.add_argument("--all", action="store_true", help="忽略状态，输出全部命中")
    ap.add_argument("--verify-ssl", action="store_true", help="严格校验 HTTPS 证书（默认放宽）")
    ap.add_argument("-q", "--quiet", action="store_true")
    args = ap.parse_args()

    verbose = not args.quiet
    scanned_at = time.strftime("%Y-%m-%d %H:%M")
    all_items = []
    alerts = []
    health_path = args.health or (
        os.path.join(os.path.dirname(os.path.abspath(args.state)), "sources-health.json")
        if args.state else "")
    health = load_health(health_path)

    if args.mode in ("wx", "both"):
        if verbose:
            print(f"📡 通道 1 · 公众号检索（{args.wx_engine}）……", file=sys.stderr)
        all_items += scan_wx(WX_QUERIES + list(args.wx_query), engine=args.wx_engine, verbose=verbose, days=args.wx_days)
    if args.mode in ("web", "both"):
        if args.no_sources:
            web_sources = [{"id": s["name"], "name": s["name"], "url": s["url"],
                            "base": s["base"], "kind": "gov_list"} for s in WEB_SOURCES]
            sentinels, adapters, skipped = [], [], 0
        else:
            web_sources, sentinels, adapters, skipped = select_web_sources(
                args.sources, line=args.line, verbose=verbose)
        if verbose:
            print(f"🌐 通道 2 · 官网列表页巡检（{len(web_sources)} 个列表源"
                  f" + {len(sentinels)} 个哨兵 + {len(adapters)} 个适配器，"
                  f"{skipped} 个跳过）……", file=sys.stderr)
        web_items, statuses = scan_web(web_sources, verbose, verify_ssl=args.verify_ssl)
        all_items += web_items
        # P3 适配器：智联招考型直接拉岗位数组
        for entry in adapters:
            try:
                from recruit_adapters import scan_zhaokao
                a_items, ok = scan_zhaokao(entry, verbose)
            except Exception as e:
                a_items, ok = [], False
                if verbose:
                    print(f"  ⚠️  [适配器·{entry['name']}] 异常：{str(e)[:60]}", file=sys.stderr)
            all_items += a_items
            statuses.append(("zhaokao::" + entry["id"], ok, 200 if ok else 0))
            if verbose:
                print(f"  · [适配器·{entry['name']}] 岗位 {len(a_items)} 条", file=sys.stderr)
        # 健康检查：连续失败 ≥3 → 告警（防"源静默失效"）
        for sid, ok, code in statuses:
            update_health(health, "web::" + sid, ok, code)
        for sid, h in health.items():
            if h.get("consecutive_fail", 0) >= 3:
                alerts.append(f"🚨 源连续失败 {h['consecutive_fail']} 次：{sid}"
                              f"（last_code={h.get('last_code')}）→ 请探活复核")
        # 哨兵：SPA 源 hash 变更告警
        if sentinels:
            alerts += scan_sentinels(sentinels, health, verbose, verify_ssl=args.verify_ssl)
        save_health(health_path, health)

    # 全局去重
    uniq, seen = [], set()
    for it in all_items:
        key = it["title"]
        if key in seen:
            continue
        seen.add(key)
        uniq.append(it)

    state = load_state(args.state)
    seen_before = set(state.get("seen", []))
    new_items = uniq if args.all else [it for it in uniq if it["title"] not in seen_before]

    state.setdefault("seen", [])
    state["seen"] = list(seen_before | {it["title"] for it in uniq})
    save_state(args.state, state)

    mode_desc = {"wx": "公众号检索", "web": "官网列表页", "both": "公众号 + 官网"}[args.mode]
    md = render_md(new_items, uniq, scanned_at, mode_desc, alerts=alerts)
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(md)
        if verbose:
            print(f"✅ 报告已写入：{args.out}", file=sys.stderr)
    else:
        print(md)

    if verbose:
        print(f"✅ 巡检完成：命中 {len(uniq)} 条，新增 {len(new_items)} 条", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
