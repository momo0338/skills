#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
抓回线上已发布文章的正文存档（内容资产补档）

场景：早期发布后未在本地留档，vault 里缺大量已发稿。本脚本从发表记录的 content_url
逐篇抓回正文，转成带 frontmatter 的 Markdown 存进 `已发布存档/`。

- **不需要登录态**（走 mp-save 记录的 curl 通道，UA 伪装 Safari）
- 图片**只保留链接不下载文件**（147 篇 × 平均 6 张规模过大；需要时再按 URL 取）
- **幂等**：目标文件已存在则跳过，可反复运行
- 正文范围：`id="js_content"` → `rich_media_area_extra`（避免混入推荐位）

用法：
    export GZH_WORK_DIR="/path/to/账号目录"
    python3 fetch_published_archive.py                  # 全量（跳过已存档）
    python3 fetch_published_archive.py --limit 5        # 先试 5 篇
    python3 fetch_published_archive.py --records <json> # 指定发表记录 JSON

产出：<GZH_WORK_DIR>/已发布存档/<YYYY-MM>/<DD>-<标题>.md
"""
import os, sys, re, json, glob, time, html, subprocess
from datetime import datetime

BASE = os.environ.get("GZH_WORK_DIR") or os.getcwd()
OUT_ROOT = os.path.join(BASE, "已发布存档")
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
      "(KHTML, like Gecko) Version/17.0 Safari/605.1.15")
CACHE = os.path.expanduser("~/.cache/weixin/publish_records")


def latest_records() -> str:
    hits = sorted(glob.glob(os.path.join(CACHE, "*_发表记录_*.json")))
    if not hits:
        sys.exit(f"未找到发表记录 JSON（{CACHE}）")
    # 优先账号目录名匹配
    acc = os.path.basename(BASE.rstrip("/"))
    mine = [h for h in hits if acc in os.path.basename(h)]
    return (mine or hits)[-1]


def load_articles(path: str) -> list:
    d = json.load(open(path, encoding="utf-8"))
    out = []
    for it in d.get("publish_list", []):
        pi = it.get("publish_info")
        if isinstance(pi, str):
            try: pi = json.loads(pi)
            except Exception: continue
        if not isinstance(pi, dict): continue
        sent = pi.get("sent_info") or {}
        ts = sent.get("time")
        for a in (pi.get("appmsg_info") or []):
            if a.get("is_deleted"): continue
            if not ts:
                ts = (a.get("line_info") or {}).get("send_time") or 0
            dt = datetime.fromtimestamp(ts) if ts else None
            out.append({
                "title": (a.get("title") or "").strip(),
                "url": a.get("content_url", ""),
                "album": (a.get("appmsg_album_info") or {}).get("title", ""),
                "read": a.get("read_num", 0), "like": a.get("like_num", 0),
                "share": a.get("share_num", 0),
                "date": dt.strftime("%Y-%m-%d") if dt else "",
                "digest": (a.get("digest") or "").strip(),
            })
    out.sort(key=lambda x: x["date"])
    return out


def fetch(url: str, timeout=40) -> str:
    r = subprocess.run(["curl", "-sL", "--max-time", str(timeout), "-A", UA, url],
                       capture_output=True, text=True, errors="ignore")
    return r.stdout or ""


def to_markdown(body: str) -> str:
    """极简 HTML→Markdown：只处理正文里的图片、标题、段落、加粗。"""
    body = re.sub(r"<(script|style)[\s\S]*?</\1>", "", body, flags=re.I)
    # 图片：一律在 data-src
    def img_repl(m):
        u = html.unescape(m.group(1)).split("#")[0]
        return f"\n\n![配图]({u})\n\n"
    body = re.sub(r'<img[^>]*data-src="([^"]+)"[^>]*>', img_repl, body, flags=re.I)
    body = re.sub(r"<img[^>]*>", "", body, flags=re.I)
    for lv in range(1, 7):
        body = re.sub(rf"<h{lv}[^>]*>([\s\S]*?)</h{lv}>",
                      lambda m, lv=lv: f"\n\n{'#' * (lv + 1)} {m.group(1).strip()}\n\n",
                      body, flags=re.I)
    body = re.sub(r"<br\s*/?>", "\n", body, flags=re.I)
    body = re.sub(r"</(p|section|div|li|blockquote)>", "\n\n", body, flags=re.I)
    body = re.sub(r"<(strong|b)>([\s\S]*?)</\1>", r"**\2**", body, flags=re.I)
    body = re.sub(r"<[^>]+>", "", body)
    body = html.unescape(body)
    body = re.sub(r"[ \t\u00a0]+", " ", body)
    body = re.sub(r"\n{3,}", "\n\n", body)
    return body.strip()


def extract_body(page: str) -> str:
    i = page.find('id="js_content"')
    if i < 0: return ""
    j = page.find("rich_media_area_extra", i)
    seg = page[i:j] if j > i else page[i:i + 60000]
    seg = seg[seg.find(">") + 1:]
    return to_markdown(seg)


def safe_name(t: str) -> str:
    t = re.sub(r'[\\/:*?"<>|]', "－", t).strip()
    return t[:60] or "未命名"


def main():
    limit = None
    for i, a in enumerate(sys.argv[1:]):
        if a == "--limit": limit = int(sys.argv[i + 2])
    rec = None
    if "--records" in sys.argv:
        rec = sys.argv[sys.argv.index("--records") + 1]
    rec = rec or latest_records()
    arts = load_articles(rec)
    print(f"发表记录：{os.path.basename(rec)}｜在库 {len(arts)} 篇")
    if limit: arts = arts[-limit:]     # 试跑取最近的

    done = skipped = failed = 0
    fail_list = []
    for n, a in enumerate(arts, 1):
        if not a["url"]:
            continue
        ymd = a["date"].split("-") if a["date"] else ["0000", "00", "00"]
        folder = os.path.join(OUT_ROOT, "-".join(ymd[:2]))
        os.makedirs(folder, exist_ok=True)
        fn = os.path.join(folder, f"{ymd[2]}-{safe_name(a['title'])}.md")
        if os.path.exists(fn):
            skipped += 1; continue
        page = fetch(a["url"])
        # ⚠️ 已删除/违规的文章会返回 HTTP 200 + 2.6MB 的提示页（不是 404），
        #    必须按提示文本判定，只看状态码或长度会误判成"抓取失败"。
        if any(k in page for k in ("已被发布者删除", "该内容已被删除", "内容已被删除", "无法查看该内容")):
            failed += 1; fail_list.append((a["title"], "线上已删除/违规，无法补档"))
            print(f"  [{n}/{len(arts)}] ⊘ {a['title'][:28]}（线上已删除）")
            time.sleep(0.4); continue
        if len(page) < 5000:
            failed += 1; fail_list.append((a["title"], f"页面过短 {len(page)}"))
            print(f"  [{n}/{len(arts)}] ✗ {a['title'][:28]}（{len(page)} 字节）")
            time.sleep(1); continue
        body = extract_body(page)
        if len(body) < 200:
            failed += 1; fail_list.append((a["title"], f"正文过短 {len(body)}"))
            print(f"  [{n}/{len(arts)}] ✗ {a['title'][:28]}（正文 {len(body)} 字）")
            time.sleep(1); continue
        fm = (f"---\ntitle: {a['title']}\ndate: {a['date']}\ncategory: 已发布存档\n"
              f"source: 微信公众号\naccount: {os.path.basename(BASE.rstrip('/'))}\n"
              f"album: {a['album']}\nurl: {a['url']}\n"
              f"read: {a['read']}\nlike: {a['like']}\nshare: {a['share']}\n"
              f"tags: [已发布, 补档]\n---\n\n")
        meta = (f"> **原发布**：{a['date']}｜阅读 {a['read']:,}｜在看 {a['like']}｜分享 {a['share']}"
                f"｜合集 {a['album'] or '无'}\n> **原文**：{a['url']}\n\n")
        if a["digest"]:
            meta += f"> **摘要**：{a['digest']}\n\n"
        with open(fn, "w", encoding="utf-8") as f:
            f.write(fm + f"# {a['title']}\n\n" + meta + "---\n\n" + body + "\n")
        done += 1
        print(f"  [{n}/{len(arts)}] ✓ {a['title'][:30]}（{len(body)} 字）")
        time.sleep(0.6)

    print(f"\n新增 {done}｜跳过（已存档）{skipped}｜失败 {failed}")
    if fail_list:
        print("失败清单：")
        for t, r in fail_list[:20]:
            print(f"  - {t[:34]}：{r}")


if __name__ == "__main__":
    if "-h" in sys.argv or "--help" in sys.argv:
        print(__doc__); sys.exit(0)
    main()
