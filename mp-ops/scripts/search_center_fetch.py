#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
微信搜一搜数据中心 抓取（wsad.weixin.qq.com，需登录态）

本脚本填补 2026-09-24 之前的空缺：此前 mp-ops 只有本文件的姊妹脚本
search_fetch.py（抓**单篇阅读渠道构成**），而「搜一搜数据中心」这一独立数据源
**只有文档、没有任何脚本**，每次都要人工翻 iframe。现已打通并自动化。

══════════════════════════════════════════════════════════════════════
一、数据源与取数路径（2026-09-24 实测逆向，非猜测）
══════════════════════════════════════════════════════════════════════

导航链（三跳，缺一不可）：
  ① mp.weixin.qq.com 首页 → 取 ?token=（**必须用首页**；/cgi-bin/home 失效时是
     「登录超时」死页，无二维码；且首页运营文案含「扫码」二字，不能用文本黑名单
     判定登录态，要以 URL 带 token + 落在 cgi-bin/(home|appmsg|masssend) 为准）
  ② /misc/pluginloginpage?pluginuin=10071&token=<t>  → 页面内 iframe#mpIFrame
     的 src 指向 wsad.weixin.qq.com/mpindex?jsonparam=...&appid=<本号 appid>
     &token=<wsad 专属 token>&mp_token=<后台 token>
  ③ 打开该 src → SPA 站，真实数据接口是 POST /official/official，
     域名为 wsad.weixin.qq.com（**同源，故可用页内 fetch**）

真实接口（挂 XHR 监听器抓到的原文，非文档抄写）：
  wsad_action=get-search-channel    → fans_list / reader_list / channel_list
                                       （关键数据 + 粉丝来源 + 30 天趋势）
  wsad_action=get-hot-passage-list  → passage_list（热门文章，含命中搜索词）
  wsad_action=get-hot-query-list    → query_list（热门搜索词，含相关搜索词）
  另有 get-service-data（热门服务菜单，本脚本未取）与 /servicesearch/servicesearch
  的 mmdata_report（**埋点上报，非数据接口**，不要当接口用）

⚠️ 该 iframe 是 Vue SPA，接口路径不在 HTML 里，而在
   res.wx.qq.com/.../js/data_center_comp.<hash>.js 中，且随版本漂移 —— 所以本脚本
   **不硬编码 JS 资源地址**，改为运行时挂 XHR/fetch 记录器 + 直接调用已验证的
   wsad_action（这三个 action 2026-09-24 实测稳定）。

══════════════════════════════════════════════════════════════════════
二、时效红线（违反＝数据永久丢失）
══════════════════════════════════════════════════════════════════════

**后台每日 12:00 更新前一日数据，且只保留 30 日。** 过期后无法补取。
所以本脚本第一件事就是把原始响应落盘，落盘成功才算取到数据。

══════════════════════════════════════════════════════════════════════
三、账号纪律（⛔ 写错号＝数据污染）
══════════════════════════════════════════════════════════════════════

脚本默认 **--profile mashang（码上职业）**，appid **不写死**，运行时从
`mp-publish/scripts/wx_account.py env <profile>` 读（账号表是唯一真源）。

⛔ **硬拦截**：ego 浏览器当前登录账号与目标 profile 不符时直接退出（exit 2），
绝不允许「用 A 号登录态 + B 号 appid」取数——那会把别号数据当本号数据落盘。
2026-09-24 实测正是靠这条抓出：登录态是「满爸爱生活」，而脚本默认 appid
曾误抄成满爸号（09-22 样本热门词全是南京亲子内容，可证）。

══════════════════════════════════════════════════════════════════════
四、用法
══════════════════════════════════════════════════════════════════════

  export GZH_WORK_DIR="/path/to/账号目录"      # 可选，仅用于报告标注
  python3 search_center_fetch.py --check        # 只探登录态+目标appid，不取数
  python3 search_center_fetch.py                # 默认抓 mashang 近 30 天
  python3 search_center_fetch.py --profile manba   # 抓另一个已登记账号
  python3 search_center_fetch.py --days 7       # 近 7 天
  python3 search_center_fetch.py --days 1       # 仅昨天（配合 12:00 后跑）
  python3 search_center_fetch.py --out <路径>   # 指定落盘位置
  python3 search_center_fetch.py --appid <appid> # 绕过账号表直接指定（不推荐）

产出：
  ~/.cache/weixin/publish_records/search_center_<YYYYMMDD>.json   结构化
  ~/.cache/weixin/publish_records/search_center_raw_<YYYYMMDD>.json  接口原始响应

口径提醒：这里的 exp_qv=展示、clk_qv=点击、ctr=clk/exp*100（**推算值**）；
search_follow=搜索后关注。与「单篇阅读渠道构成」的搜一搜占比是**两个不同口径**，
不要混用（前者是账号/内容在搜一搜的曝光回搜数据，后者是单篇阅读的来源构成）。
"""
import os, sys, json, re, subprocess, tempfile
from datetime import datetime, timedelta

EGO = os.path.expanduser("~/.local/bin/ego-browser")
UID = os.popen("id -u").read().strip() or "501"
CACHE = os.path.expanduser("~/.cache/weixin/publish_records")
PLUGIN_UIN = "10071"

# 目标账号：默认「码上职业」。appid 不写死在这里，运行时从 mp-publish 账号表读，
# 避免「改了账号却还用旧 appid」把别号数据当成本号数据。
DEFAULT_PROFILE = "mashang"
MP_PUBLISH = os.path.expanduser("~/src/skills/mp-publish")
APPID_RUNTIME = ""  # 本次实际使用的 appid，由 main() 写入 parse 结果


def run_ego(js: str, timeout: int = 300) -> str:
    """把 JS 交给 ego-browser 执行，返回 stdout+stderr 合并文本。"""
    if not os.path.exists(EGO):
        sys.exit(f"未找到 ego-browser：{EGO}\n"
                 f"安装：https://github.com/... 或用 ego lite 官方渠道；"
                 f"本机标准路径 {EGO}")
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
        f.write(js)
        path = f.name
    try:
        p = subprocess.run(["launchctl", "asuser", UID, EGO, "nodejs"],
                           stdin=open(path), capture_output=True, text=True, timeout=timeout)
        return (p.stdout or "") + (p.stderr or "")
    finally:
        os.unlink(path)


def log_line(out: str, key: str) -> str:
    """从 ego 输出里取一行标记内容。"""
    m = re.search(rf"^{re.escape(key)}=(.*)$", out, re.M)
    return m.group(1).strip() if m else ""


def probe_login(timeout=120) -> tuple:
    """第一道闸门：探登录态。返回 (token, 账号昵称)；取不到 token 返回 ('', '')。"""
    out = run_ego(r'''
const task = await useOrCreateTaskSpace('搜一搜数据中心抓取')
await openOrReuseTab('https://mp.weixin.qq.com/', { wait: true, timeout: 45 })
const href = String(await js('location.href'))
const t = String(await snapshotText())
const m = href.match(/token=(\d+)/)
cliLog('HREF=' + href)
cliLog('TOKEN=' + (m ? m[1] : 'none'))
// 强信号优先：URL 带 token 且落在后台页 => 必定已登录。
// 不可只用文本黑名单：首页运营文案「推荐带来6.5万阅读量，微信扫码查看…」含「扫码」。
const strongIn = /token=\d+/.test(href) && /cgi-bin\/(home|appmsg|masssend)/.test(href)
const strongOut = href.includes('loginpage') || /微信扫一扫|登录超时|请重新登录/.test(t)
const ok = strongIn || (!strongOut && /token=\d+/.test(href))
cliLog('LOGGED_IN=' + (ok ? 'yes' : 'no'))
// 账号昵称：后台顶部栏的当前账号名，用于落盘标注（防止把满爸号数据误当码上职业）
const nick = await js(String.raw`(() => {
  const sels = ['.weui-desktop-account__nickname', '.account_setting_info__nickname',
                '.weui-desktop-menu__title', '[class*=nickname]', '.profile_nickname']
  for (const s of sels) {
    const e = document.querySelector(s)
    if (e && e.innerText && e.innerText.trim()) return e.innerText.trim()
  }
  const m2 = (document.body.innerText || '').match(/编辑\s*(\S{2,20})\s*功能/)
  return m2 ? m2[1] : ''
})()`)
cliLog('NICK=' + String(nick).replace(/\n/g, ' ').slice(0, 30))
''', timeout=timeout)
    if "LOGGED_IN=yes" not in out:
        return "", ""
    return log_line(out, "TOKEN"), log_line(out, "NICK")


def fetch_all(token: str, from_ds: str, to_ds: str, appid: str, timeout=300) -> dict:
    """三跳进 iframe，然后页内 fetch 三个数据接口，原始响应返回 Python。"""
    js = f'''
const task = await useOrCreateTaskSpace('搜一搜数据中心抓取')
const TOKEN = {json.dumps(token)}
// ① 插件页
await openOrReuseTab(
  `https://mp.weixin.qq.com/misc/pluginloginpage?pluginuin={PLUGIN_UIN}&token=${{TOKEN}}&lang=zh_CN`,
  {{ wait: true, timeout: 50 }})
await new Promise(r => setTimeout(r, 2500))
// ② 取 iframe#mpIFrame 的 src（wsad 真实入口，含 wsad 专属 token）
const src = await js(String.raw`(() => {{
  const f = document.querySelector('iframe#mpIFrame') || document.querySelector('iframe')
  return f ? f.src : ''
}})()`)
cliLog('SRC_LEN=' + String(src).length)
if (!src || String(src).length < 40) {{ cliLog('FATAL=no_iframe_src'); process.exit(3) }}
// ③ 打开 wsad SPA
await openOrReuseTab(String(src), {{ wait: true, timeout: 60 }})
await new Promise(r => setTimeout(r, 3500))
cliLog('WSAD=' + String(await js('location.href')).slice(0, 90))
// ④ 页内同源 fetch（域名为 wsad.weixin.qq.com，与页面同源）
const raw = await js(String.raw`(async () => {{
  const post = async (action, extra) => {{
    const body = 'wsad_action=' + action + '&' + (extra || '') + '&appid=' + {json.dumps(appid)}
    const r = await fetch('/official/official', {{
      method: 'POST',
      headers: {{'Content-Type': 'application/x-www-form-urlencoded'}},
      body
    }})
    return await r.text()
  }}
  const out = {{}}
  out.channel = await post('get-search-channel',
    'from_ds={from_ds}&to_ds={to_ds}&last_from_ds={from_ds}&last_to_ds={to_ds}')
  out.passage = await post('get-hot-passage-list',
    'from_ds={from_ds}&to_ds={to_ds}&limit=20')
  out.query = await post('get-hot-query-list',
    'from_ds={from_ds}&to_ds={to_ds}&limit=20')
  return JSON.stringify(out)
}})()`)
cliLog('@@@DATA@@@' + String(raw))
'''
    out = run_ego(js, timeout=timeout)
    seg = out.split("@@@DATA@@@")[-1].strip()
    if not seg or seg == "@@@DATA@@@":
        print(out[-1500:])
        sys.exit("未取到数据（iframe 打开失败或页内 fetch 报错），见上方 ego 输出。")
    try:
        return json.loads(seg)
    except json.JSONDecodeError:
        sys.exit(f"数据不是合法 JSON（可能被截断，{len(seg)} 字节）：{seg[:300]}")


def resolve_appid(profile: str):
    """从 mp-publish 账号登记表取 appid（唯一真源），不写死、不猜。"""
    env = os.environ.get("WX_APPID")
    if profile == os.environ.get("WX_PROFILE") and env:
        return env, "env:WX_APPID"
    try:
        p = subprocess.run(
            [sys.executable, os.path.join(MP_PUBLISH, "scripts", "wx_account.py"), "env", profile],
            capture_output=True, text=True, timeout=30,
            env={**os.environ, "GZH_WORK_DIR": os.environ.get("GZH_WORK_DIR", CACHE)})
        m = re.search(r'export WX_APPID="([^"]+)"', p.stdout or "")
        if m:
            return m.group(1), f"mp-publish:profile={profile}"
    except Exception as e:
        print(f"⚠️ 读 mp-publish 账号表失败：{e}")
    return None, f"profile={profile}(未取到 appid)"


def nick_matches(nick: str, profile: str) -> bool:
    """昵称与 profile 是否对得上；识别不出昵称时返回 True（交由 _warn 提示人工确认）。"""
    if not nick:
        return True
    table = {"mashang": ("码上职业",), "manba": ("满爸爱生活",)}
    keys = table.get(profile)
    if not keys:
        return True
    return any(k in nick for k in keys)


def _ok_json(s):
    try:
        json.loads(s)
        return True
    except Exception:
        return False


def _assert_ok(raw: dict):
    """三个接口都必须回 errcode=0 才算取到数；任一失败即停，不落半份数据。"""
    names = {"channel": "get-search-channel",
             "passage": "get-hot-passage-list",
             "query": "get-hot-query-list"}
    for key, action in names.items():
        s = raw.get(key, "")
        if not _ok_json(s):
            sys.exit(f"接口 {action} 返回非 JSON（{len(s)} 字节）：{s[:200]}")
        obj = json.loads(s)
        if obj.get("errcode") not in (0, "0", None):
            sys.exit(f"接口 {action} 报错：errcode={obj.get('errcode')} msg={obj.get('msg')}")


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _i(v):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


BLOCK_MAP = {"MP": "文章", "biz": "公众号", "other": "其它"}


def parse(raw: dict, from_ds: str, to_ds: str, account: str = "", profile: str = "") -> dict:
    """把三份接口原始响应整成与 2026-09-22 手工样本同构的结构。"""
    def jload(s):
        try:
            return json.loads(s)
        except Exception:
            return {}

    ch = jload(raw.get("channel", ""))
    pa = jload(raw.get("passage", ""))
    qu = jload(raw.get("query", ""))

    for name, obj in (("get-search-channel", ch), ("get-hot-passage-list", pa), ("get-hot-query-list", qu)):
        if obj.get("errcode") not in (0, "0", None):
            sys.exit(f"接口 {name} 返回错误：errcode={obj.get('errcode')} msg={obj.get('msg')}")

    # 关键数据：区间合计（reader_list=搜索后阅读，fans_list=搜索后关注）
    search_read = sum(_i(x.get("num")) or 0 for x in ch.get("reader_list", []))
    search_follow = sum(_i(x.get("num")) or 0 for x in ch.get("fans_list", []))

    fan_source = []
    for it in ch.get("channel_list", []):
        exp, clk = _i(it.get("exp_qv")), _i(it.get("clk_qv"))
        fan_source.append({
            "block": BLOCK_MAP.get(it.get("type"), it.get("type")),
            "imp": exp, "click": clk,
            "ctr": round(clk / exp * 100, 2) if exp else None,
            "fans": _i(it.get("fans")),
        })
    if fan_source:
        fan_source.append({"block": "总计", "imp": None, "click": None, "ctr": None,
                           "fans": sum(x["fans"] or 0 for x in fan_source)})
    hot_articles = []
    for it in pa.get("passage_list", []):
        exp, clk = _i(it.get("exp_qv")), _i(it.get("clk_qv"))
        hot_articles.append({
            "title": (it.get("title") or "").strip(),
            "url": it.get("url") or "",
            "imp": exp, "click": clk,
            "ctr": round(clk / exp * 100, 2) if exp else None,
            "avg_rank": round(_f(it.get("avg_exp_pos")), 2) if _f(it.get("avg_exp_pos")) is not None else None,
            "words": [w.strip() for w in (it.get("related_query") or "").split("，") if w.strip()],
        })

    hot_words = []
    for it in qu.get("query_list", []):
        exp, clk = _i(it.get("exp_qv")), _i(it.get("clk_qv"))
        hot_words.append({
            "word": (it.get("query") or "").strip(),
            "block": it.get("type") or "",
            "imp": exp, "click": clk,
            "ctr": round(clk / exp * 100, 2) if exp else None,
            "related": [w.strip() for w in (it.get("related_query") or "").split("，") if w.strip()],
        })

    return {
        "fetched_at": datetime.now().isoformat(timespec="seconds"),
        "profile": profile or "",
        "appid": APPID_RUNTIME or "",
        "account": account or "(未识别)",
        "source": "微信搜一搜数据中心 wsad.weixin.qq.com（#/dataCenter）",
        "data_range": f"{from_ds} ~ {to_ds}",
        "data_date": f"{to_ds}（每日12:00更新前一日，仅保留30日）",
        "kpi": {"search_read": search_read, "search_follow": search_follow},
        "fan_source": fan_source,
        "hot_articles": hot_articles,
        "hot_words": hot_words,
        "note": "ctr 为 clk/exp 推算值，非后台直接给出；与「单篇阅读渠道构成」的搜一搜占比口径不同，勿混用。",
    }


def print_summary(d: dict):
    k = d["kpi"]
    print(f"\n数据区间 {d['data_range']}（后台每日 12:00 更新前一日）")
    print(f"  搜索后阅读 {k['search_read']} ｜ 搜索后关注 {k['search_follow']}")
    fs = [x for x in d["fan_source"] if x["block"] != "总计"]
    if fs:
        top = max(fs, key=lambda x: (x["imp"] or 0))
        print(f"  粉丝来源主入口 {top['block']}（展示 {top['imp']} / 点击 {top['click']} / 转化粉丝 {top['fans']}）")
    if d["hot_articles"]:
        a = d["hot_articles"][0]
        print(f"  热门文章 TOP1《{a['title'][:26]}》曝光 {a['imp']} 点击 {a['click']} CTR {a['ctr']}% 平均排序 {a['avg_rank']}")
    if d["hot_words"]:
        print("  热门搜索词 TOP5：" + " / ".join(w["word"] for w in d["hot_words"][:5]))


def main():
    if "-h" in sys.argv or "--help" in sys.argv:
        print(__doc__)
        sys.exit(0)
    a = sys.argv[1:]
    work = os.environ.get("GZH_WORK_DIR") or os.getcwd()
    profile = a[a.index("--profile") + 1] if "--profile" in a else DEFAULT_PROFILE

    if "--check" in a:
        tk, nick = probe_login()
        appid, src = resolve_appid(profile)
        print(f"账号目录：{work}")
        print(f"目标 profile：{profile}（appid={appid or '未取到'}，来源 {src}）")
        print("登录态：" + (f"有效，token={tk}，账号={nick or '未识别'}" if tk
                           else "失效 → 请在 ego 浏览器扫码登录 mp.weixin.qq.com"))
        if tk and nick and not nick_matches(nick, profile):
            print(f"⛔ 账号不符：当前登录「{nick}」，但目标 profile 是「{profile}」。"
                  f"请先在 ego 浏览器切换到对应账号，或加 --profile 匹配当前账号。")
            sys.exit(2)
        sys.exit(0 if tk else 1)

    days = int(a[a.index("--days") + 1]) if "--days" in a else 30
    to_ds = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    from_ds = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    appid = a[a.index("--appid") + 1] if "--appid" in a else None
    appid_src = "--appid 显式传入"
    if not appid:
        appid, appid_src = resolve_appid(profile)
    if not appid:
        sys.exit(f"取不到 profile「{profile}」的 appid。请先在 mp-publish 登记该账号"
                 f"（wx_account.py list 查看），或用 --appid 显式指定。")

    print(f"[1/3] 探登录态 …（目标 profile={profile}，appid={appid}，来源 {appid_src}）")
    token, account = probe_login()
    if not token:
        sys.exit("登录态失效：需朱总在 ego 浏览器扫码登录 mp.weixin.qq.com 后重试。\n"
                 "⛔ 本脚本绝不尝试自动登录或绕验证。")
    print(f"      token={token}  当前登录账号={account or '(未识别)'}")
    if not account:
        print("      ⚠️ 未识别账号昵称：落盘 account 字段标为「(未识别)」，使用前请人工确认当前登录的是目标账号。")
    elif not nick_matches(account, profile):
        sys.exit(f"⛔ 账号不符，硬停：当前浏览器登录「{account}」，但本次要抓 profile「{profile}」"
                 f"（appid={appid}）。\n"
                 f"   继续跑会把别号数据当本号数据落盘。\n"
                 f"   请在 ego 浏览器切换到「{profile}」对应账号后重试；"
                 f"或明确要抓当前账号时加 --profile {account}。")

    print(f"[2/3] 进 iframe 并取三个数据接口（{from_ds} ~ {to_ds}）…")
    raw = fetch_all(token, from_ds, to_ds, appid)
    for k, v in raw.items():
        print(f"      {k}: {len(v)} 字节 " + ("✓JSON" if _ok_json(v) else "✗非JSON"))
    _assert_ok(raw)

    print("[3/3] 落盘 …")
    os.makedirs(CACHE, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d")
    raw_path = os.path.join(CACHE, f"search_center_raw_{stamp}.json")
    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump(raw, f, ensure_ascii=False, indent=1)

    global APPID_RUNTIME
    APPID_RUNTIME = appid
    parsed = parse(raw, from_ds, to_ds, account, profile)
    if "--out" in a:
        out_path = a[a.index("--out") + 1]
        os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    else:
        out_path = os.path.join(CACHE, f"search_center_{stamp}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(parsed, f, ensure_ascii=False, indent=1)

    print(f"  [原始响应] {raw_path}")
    print(f"  [结构化]   {out_path}")
    print_summary(parsed)
    print(f"\n⚠️ 该数据后台仅保留 30 日，过期无法补取。已落盘即安全。")


if __name__ == "__main__":
    main()
