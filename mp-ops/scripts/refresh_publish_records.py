#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
刷新公众号发表记录（后台接口，需登录态）

接口与解析规则照抄 `mp-publish/SKILL.md` §八.1：
  GET /cgi-bin/appmsgpublish?sub=list&begin=<0,20,...>&count=20&token=<t>&lang=zh_CN&f=json&ajax=1
  - 两跳解析：publish_page（字符串）→ publish_list[i].publish_info（字符串）→ appmsg_info[]
  - 时间字段分两处：已通知在 sent_info.time；**未通知没有 sent_info，时间在
    appmsg_info[0].line_info.send_time**（只读前者会让未通知记录全部没日期）
  - 指标字段：read_num / like_num / share_num / old_like_num(在看) / comment_num
  - 分页：begin 步进 20，遇空壳（约 380 字节、非 JSON）提前 break

用法：
    export GZH_WORK_DIR="/path/to/账号目录"
    python3 refresh_publish_records.py            # 抓取 + 落盘 JSON + 生成 CSV
    python3 refresh_publish_records.py --no-csv   # 只落原始 JSON

产出：
    ~/.cache/weixin/publish_records/<账号>_发表记录_<YYYYMMDD_HHMM>.json
    <GZH_WORK_DIR>/发表记录-<账号>-<YYYY-MM-DD>.csv
"""
import os, sys, json, csv, re, subprocess, tempfile
from datetime import datetime

EGO = os.path.expanduser("~/.local/bin/ego-browser")
UID = os.popen("id -u").read().strip() or "501"
CACHE_DIR = os.path.expanduser("~/.cache/weixin/publish_records")


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


def get_token() -> str:
    out = run_ego('''
const task = await useOrCreateTaskSpace('发表记录刷新')
await openOrReuseTab('https://mp.weixin.qq.com/', { wait: true, timeout: 40 })
await new Promise(r => setTimeout(r, 2000))
const href = String(await js('location.href'))
const m = href.match(/token=(\\d+)/)
cliLog('TOKEN=' + (m ? m[1] : 'none'))
''', timeout=90)
    m = re.search(r"TOKEN=(\d+)", out)
    if not m:
        sys.exit("取不到 token：请在 ego 浏览器里登录 mp.weixin.qq.com（登录入口用首页）")
    return m.group(1)


def fetch_all(token: str, max_pages: int = 12) -> dict:
    js = f'''
const task = await useOrCreateTaskSpace('发表记录刷新')
for (let p = 0; p < {max_pages}; p++) {{
  const r = await js(String.raw`(async () => {{
    const url = '/cgi-bin/appmsgpublish?sub=list&begin=${{p*20}}&count=20&token={token}&lang=zh_CN&f=json&ajax=1';
    return await (await fetch(url, {{credentials:'include'}})).text();
  }})()`)
  cliLog('@@@PAGE_' + p + '@@@')
  cliLog(String(r))
  await new Promise(r => setTimeout(r, 800))
}}
'''
    out = run_ego(js, timeout=600)
    pages = {}
    for seg in out.split("@@@PAGE_")[1:]:
        idx, _, body = seg.partition("@@@")
        try: pages[int(idx)] = body.strip()
        except ValueError: pass
    return pages


def parse(pages: dict) -> list:
    """两跳解析，产出扁平化的文章行。"""
    rows, raw_batches = [], []
    for p in sorted(pages):
        body = pages[p]
        if len(body) < 500:            # 空壳（约 380 字节，非 JSON）
            continue
        try:
            j = json.loads(body)
        except Exception:
            continue
        pp = j.get("publish_page")
        if isinstance(pp, str):
            try: pp = json.loads(pp)
            except Exception: continue
        if not isinstance(pp, dict): continue
        for item in pp.get("publish_list", []) or []:
            raw_batches.append(item)
            pi = item.get("publish_info")
            if isinstance(pi, str):
                try: pi = json.loads(pi)
                except Exception: continue
            if not isinstance(pi, dict): continue
            msgid = pi.get("msgid", "")
            sent = pi.get("sent_info") or {}
            succ = (pi.get("sent_status") or {}).get("succ", 0)
            ts = sent.get("time")
            notified = bool(ts)
            arts = pi.get("appmsg_info") or []
            for i, a in enumerate(arts, 1):
                if not ts:                       # 未通知：时间藏在 line_info
                    ts = (a.get("line_info") or {}).get("send_time") or 0
                dt = datetime.fromtimestamp(ts) if ts else None
                alb = (a.get("appmsg_album_info") or {}).get("title", "")
                rows.append({
                    "date": dt.strftime("%Y-%m-%d") if dt else "",
                    "time": dt.strftime("%H:%M") if dt else "",
                    "notified": "已通知" if notified else "未通知",
                    "original": "原创" if a.get("copyright_status") == 100 else "",
                    "title": (a.get("title") or "").strip(),
                    "read": a.get("read_num", 0), "like": a.get("like_num", 0),
                    "share": a.get("share_num", 0), "haokan": a.get("old_like_num", 0),
                    "comment": a.get("comment_num", 0),
                    "sent_succ": succ, "deleted": bool(a.get("is_deleted")),
                    "album": alb, "url": a.get("content_url", ""),
                    "msgid": msgid, "itemidx": i, "article_count": len(arts),
                    "digest": (a.get("digest") or "").strip(),
                })
    rows.sort(key=lambda x: (x["date"], x["time"]), reverse=True)
    return rows, raw_batches


FIELDS = ["date", "time", "notified", "original", "title", "read", "like", "share",
          "haokan", "comment", "sent_succ", "deleted", "album", "url", "msgid",
          "itemidx", "article_count", "digest"]


def main():
    work = os.environ.get("GZH_WORK_DIR") or os.getcwd()
    account = os.path.basename(work.rstrip("/"))
    token = get_token()
    print(f"token={token}｜账号目录={work}")
    pages = fetch_all(token)
    print(f"取回 {len(pages)} 页")
    rows, raw = parse(pages)
    if not rows:
        sys.exit("解析出 0 条，接口可能变了或未登录（检查返回体是否含 publish_page）")
    stamp = datetime.now()
    os.makedirs(CACHE_DIR, exist_ok=True)
    raw_path = os.path.join(CACHE_DIR, f"{account}_发表记录_{stamp:%Y%m%d_%H%M}.json")
    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump({"account": account, "fetched_at": stamp.strftime("%Y-%m-%d %H:%M %z"),
                   "endpoint": "/cgi-bin/appmsgpublish?sub=list", "publish_list": raw},
                  f, ensure_ascii=False, indent=1)
    print(f"[原始落盘] {raw_path}（{len(raw)} 个批次 / {len(rows)} 篇文章）")
    if "--no-csv" in sys.argv:
        return
    csv_path = os.path.join(work, f"发表记录-{account}-{stamp:%Y-%m-%d}.csv")
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS); w.writeheader()
        for r in rows: w.writerow(r)
    print(f"[CSV] {csv_path}")
    live = [r for r in rows if not r["deleted"]]
    print(f"\n在库 {len(live)} 篇（含已删 {len(rows)-len(live)}）"
          f"｜累计阅读 {sum(r['read'] for r in live):,}"
          f"｜最新粉丝送达 {max((r['sent_succ'] for r in rows), default=0):,}")
    print(f"时间范围：{min(r['date'] for r in rows if r['date'])} ~ {max(r['date'] for r in rows if r['date'])}")


if __name__ == "__main__":
    # 有副作用的脚本：--help 只打印用法，绝不执行抓取
    if "-h" in sys.argv or "--help" in sys.argv:
        print(__doc__); sys.exit(0)
    main()
