#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
dy-wode — 抖音「我的」个人数据整理（喜欢 / 收藏 / 观看历史 / 稍后再看 / 消息私信）

原理：
  1. 采集：用 ego-browser（继承抖音登录态）打开个人中心各分类页，滚动加载全部卡片，
     从卡片链接提取作品 ID；「消息」分类复用 scripts/im_videos.py 从私信会话提取。
  2. 统计：用 dy-cli 的登录凭证调用抖音批量详情接口 multi/aweme/detail，
     一次取回 视频名称 / 作者 / 发布时间 / 点赞 / 评论 / 收藏 / 转发。
  3. 输出：按分类整理成 Markdown 表格，并可写 CSV / JSON。

依赖：
  - ego lite（ego-browser CLI，抖音网页已登录）
  - dy-cli >= 0.2.2（已登录），dy-cli 技能目录 scripts/download_with_metadata.py（可选，下载用）

用法示例：
  # 只列 ID 与卡片标题（最快，不取统计）
  python3 dy_wode.py --list-only

  # 全部五个分类 + 统计表格（终端打印 Markdown）
  python3 dy_wode.py

  # 指定分类 + 写文件（md/csv/json 到输出目录）
  python3 dy_wode.py --categories like,favorite,record --out ~/Desktop/dy-wode

  # 消息分类：指定私信会话（近 2 天）
  python3 dy_wode.py --categories message --conv "亚马逊啊" --days 2 --out ~/Desktop/dy-wode
  # 或先用 --list-convs 看会话，再用 --index N
  python3 dy_wode.py --list-convs

  分类键：like=喜欢, favorite=收藏, record=观看历史, watch_later=稍后再看, message=消息/私信
"""

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
import time

SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
EGO = os.environ.get("EGO_BROWSER", "/Users/zhugx/.local/bin/ego-browser")
IM_SCRIPT = os.path.join(SKILL_DIR, "im_videos.py")

TABS = {
    "like": ("喜欢", "https://www.douyin.com/user/self?from_tab_name=main&showTab=like"),
    "favorite": ("收藏", "https://www.douyin.com/user/self?from_tab_name=main&showTab=favorite_collection"),
    "record": ("观看历史", "https://www.douyin.com/user/self?from_tab_name=main&showTab=record"),
    "watch_later": ("稍后再看", "https://www.douyin.com/user/self?from_tab_name=main&showTab=watch_later"),
}

# 滚动方式：滚轮事件（已验证，慢）或程序化 scrollTop（更快，需实测确认分页触发）
WHEEL_BODY = """if (box) await cdp('Input.dispatchMouseEvent', { type: 'mouseWheel', x: box.x, y: box.y, deltaX: 0, deltaY: 1200 })
      await wait(0.18)"""
FAST_BODY = """if (box) await js(`(() => { const s = window.__dyscroll; if (s) s.scrollTop += 1500 })()`)"""


def run_ego(node_code: str, timeout: int = 900) -> str:
    """把 node 脚本通过 stdin 交给 ego-browser nodejs 执行，合并 stdout+stderr 返回。"""
    if not os.path.exists(EGO):
        sys.exit(f"未找到 ego-browser CLI：{EGO}。请确认 ego lite 已安装并完成初始化。")
    proc = subprocess.run(
        [EGO, "nodejs"],
        input=node_code,
        text=True,
        capture_output=True,
        timeout=timeout,
    )
    combined = (proc.stdout or "") + (proc.stderr or "")
    if proc.returncode != 0:
        raise RuntimeError(
            f"ego-browser 执行失败 (rc={proc.returncode})\nOUTPUT: {combined[-2000:]}"
        )
    return combined


NODE_TEMPLATE = r"""
const task = await useOrCreateTaskSpace('dy-wode-tab-' + __KEY__ + '-' + Date.now())
try { await cdp('Network.enable', {}) } catch (e) {}
try { await cdp('Network.setCacheDisabled', { cacheDisabled: true }) } catch (e) {}

const cfg = __CFG__

  try {
    await openOrReuseTab(cfg.url, { wait: true, timeout: 30 })
  } catch (e) {
    cliLog('TABERR|' + cfg.key + '|nav failed: ' + e.message)
  }
  // 轮询等待网格真正渲染：找到含 >=5 张视频卡片的 UL（页面底部有 source=Baiduspider 的 SEO 链接，
  // 它们会先渲染，不能当成网格；A/B 界面类名会变，用祖先结构定位）
  let gridReady = false
  for (let i = 0; i < 20 && !gridReady; i++) {
    gridReady = await js(`(() => {
      const as = [...document.querySelectorAll('a[href*="/video/"], a[href*="/note/"]')]
      for (const a of as) {
        let el = a.parentElement
        while (el && el.tagName !== 'UL' && el.parentElement) el = el.parentElement
        if (el && el.tagName === 'UL' && el.querySelectorAll('a[href*="/video/"], a[href*="/note/"]').length >= 5) {
          window.__dygrid = el
          return true
        }
      }
      return false
    })()`)
    if (!gridReady) await wait(2)
  }
  if (!gridReady) {
    cliLog('TABSUMMARY|' + cfg.key + '|0')
    try { await completeTaskSpace(task.id, { keep: false }) } catch (e) {}
  } else {

  // 缓存滚动容器（一次性定位，避免每步重复祖先遍历导致布局抖动）
  const box = await js(`(() => {
    const grid = window.__dygrid
    const first = grid && grid.querySelector('a[href*="/video/"], a[href*="/note/"]')
    if (!first) return null
    let el = first.parentElement
    while (el && el.scrollHeight <= el.clientHeight + 100) el = el.parentElement
    if (!el) return null
    window.__dyscroll = el
    const r = el.getBoundingClientRect()
    return { x: Math.round(r.x + r.width / 2), y: Math.round(Math.min(r.y + r.height / 2, 900)) }
  })()`)

  // 网格 UL 保留全部已加载项（不回收 DOM）：一次持续向下滚动触发分页加载，
  // 到底（滚动到底 + 计数连续不变）后一次性读 UL 内全部 ID + 文本。
  let quiet = 0
  let lastN = -1
  const t0 = Date.now()
  let reason = 'budget'
  for (let i = 0; i < __MAXSTEPS__; i++) {
    __SCROLLBODY__
    const st = await js(`(() => {
      const g = window.__dygrid, s = window.__dyscroll
      if (!s || !g) return { n: -1, atBottom: true }
      const n = g.children.length
      const atBottom = (s.scrollTop + s.clientHeight >= s.scrollHeight - 80)
      return { n, atBottom }
    })()`)
    if (st.n < 0) { reason = 'lost'; break }
    if (st.n === lastN) quiet++; else { quiet = 0; lastN = st.n }
    if (i >= 40 && st.atBottom && quiet >= 25) { reason = 'end'; break }
  }
  cliLog('SCROLLDONE|' + cfg.key + '|' + lastN + '|' + Math.round((Date.now() - t0) / 1000) + '|' + reason)

  // 一次性读 UL 内全部卡片 ID + 文本
  const cards = await js(`(() => {
    const root = window.__dygrid || null
    if (!root) return []
    const seen = new Set()
    const out = []
    for (const a of root.querySelectorAll('a[href*="/video/"], a[href*="/note/"]')) {
      const m = (a.getAttribute('href') || '').match(/(\\d{15,25})/)
      if (!m || seen.has(m[1])) continue
      seen.add(m[1])
      out.push({ id: m[1], text: (a.textContent || '').trim().replace(/\\s+/g, ' ').slice(0, 200) })
    }
    return out
  })()`)
  cliLog('TABSUMMARY|' + cfg.key + '|' + cards.length)
  for (const c of cards) cliLog('CARD|' + cfg.key + '|' + c.id + '|' + c.text)
  }

try { await completeTaskSpace(task.id, { keep: false }) } catch (e) {}
"""


def collect_tabs(keys: list[str], args) -> dict[str, list[dict]]:
    """返回 {分类键: [{aweme_id, card_text}]}；支持缓存落盘与 --resume 续跑。"""
    result: dict[str, list[dict]] = {k: [] for k in keys}
    cache_dir = args.cache_dir
    for k in keys:
        if args.resume and cache_dir:
            cpath = os.path.join(cache_dir, f"{k}.json")
            if os.path.exists(cpath):
                try:
                    with open(cpath, encoding="utf-8") as f:
                        result[k] = json.load(f)
                    print(f"  「{TABS[k][0]}」使用缓存：{len(result[k])} 条（--resume）", flush=True)
                    continue
                except Exception:
                    pass
        # 每个分类单独一个浏览器进程：单个分类超时/失败不影响其他分类
        print(f"正在通过 ego-browser 采集「{TABS[k][0]}」…", flush=True)
        code = NODE_TEMPLATE.replace("__KEY__", json.dumps(k)).replace(
            "__CFG__", json.dumps({"key": k, "url": TABS[k][1]}, ensure_ascii=False)
        ).replace("__MAXSTEPS__", str(args.max_steps)).replace(
            "__SCROLLBODY__", FAST_BODY if args.fast_scroll else WHEEL_BODY
        )
        try:
            out = run_ego(code, timeout=args.tab_timeout)
        except (RuntimeError, subprocess.TimeoutExpired) as exc:
            print(f"  {TABS[k][0]} 采集失败（已跳过）：{str(exc)[-300:]}", file=sys.stderr, flush=True)
            continue
        n = 0
        done = None
        for line in out.splitlines():
            if line.startswith("CARD|"):
                _, key, vid, text = line.split("|", 3)
                if key in result:
                    result[key].append({"aweme_id": vid, "card_text": text})
            elif line.startswith("TABSUMMARY|"):
                _, key, n = line.split("|", 2)
                n = int(n)
            elif line.startswith("SCROLLDONE|"):
                _, key, cnt, secs, reason = line.split("|", 4)
                done = (int(cnt), int(secs), reason)
        label = TABS[k][0]
        if done:
            cnt, secs, reason = done
            note = {"end": "已到底", "budget": "步数预算用尽，可能不完整！", "lost": "页面异常"}.get(reason, reason)
            print(f"  {label}：{n} 个视频（滚到 {cnt} 条，{secs}s，{note}）", flush=True)
        else:
            print(f"  {label}：{n} 个视频", flush=True)
        if n == 0:
            print(f"  警告：{label} 采到 0 条，可能触发验证码/页面未渲染，建议冷却后再试。", flush=True)
        if cache_dir:
            os.makedirs(cache_dir, exist_ok=True)
            with open(os.path.join(cache_dir, f"{k}.json"), "w", encoding="utf-8") as f:
                json.dump(result[k], f, ensure_ascii=False, indent=1)
        if args.pace > 0 and k is not keys[-1]:
            print(f"  冷却 {args.pace}s 再继续（降低风控概率）…", flush=True)
            time.sleep(args.pace)
    return result


def collect_messages(args) -> list[dict]:
    """调用 im_videos.py --json 获取私信会话视频；支持缓存与 --resume。"""
    if args.resume and args.cache_dir:
        cpath = os.path.join(args.cache_dir, "message.json")
        if os.path.exists(cpath):
            try:
                with open(cpath, encoding="utf-8") as f:
                    items = json.load(f)
                print(f"  「消息」使用缓存：{len(items)} 条（--resume）", flush=True)
                return items
            except Exception:
                pass
    cmd = [sys.executable, IM_SCRIPT, "--json", "--days", str(args.days)]
    if args.conv:
        cmd += ["--conv", args.conv]
    elif args.index is not None:
        cmd += ["--index", str(args.index)]
    else:
        sys.exit("消息分类需要指定 --conv 会话名，或 --index 序号（先运行 --list-convs 查看）。")
    print(f"正在通过 ego-browser 采集私信会话视频（近 {args.days} 天）…", flush=True)
    proc = subprocess.run(cmd, text=True, capture_output=True, timeout=1200)
    if proc.returncode != 0:
        print(proc.stderr[-2000:], file=sys.stderr)
        sys.exit("im_videos.py 采集失败，请检查会话名或网络。")
    try:
        items = json.loads(proc.stdout)
    except json.JSONDecodeError:
        print(proc.stdout[-2000:])
        sys.exit("im_videos.py 输出解析失败。")
    if args.cache_dir:
        os.makedirs(args.cache_dir, exist_ok=True)
        with open(os.path.join(args.cache_dir, "message.json"), "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=1)
    return items


def list_convs() -> None:
    cmd = [sys.executable, IM_SCRIPT, "--list-convs"]
    proc = subprocess.run(cmd, text=True, capture_output=True, timeout=600)
    print((proc.stdout or "") + (proc.stderr or ""))


def fetch_details(ids: list[str]) -> dict[str, dict]:
    """批量取详情：multi/aweme/detail（每批 ~40 个，带登录 Cookie 即可，无需 Playwright 签名），
    缺失回退单条 detail。"""
    from urllib.parse import urlencode

    import httpx
    from dy_cli.engines.api_client import DouyinAPIClient
    from dy_cli.utils.signature import get_base_params, get_headers

    client = DouyinAPIClient.from_config()
    results: dict[str, dict] = {}
    failed: set[str] = set()
    ids = list(dict.fromkeys(ids))
    chunk = 40
    batches = [ids[i : i + chunk] for i in range(0, len(ids), chunk)]
    for n, part in enumerate(batches, 1):
        try:
            params = {**get_base_params(), "aweme_ids": "[" + ",".join(part) + "]"}
            url = "https://www.douyin.com/aweme/v1/web/multi/aweme/detail/?" + urlencode(params)
            resp = httpx.get(url, headers=get_headers(client.cookie), timeout=20)
            data = resp.json()
            got = 0
            for d in data.get("aweme_details") or []:
                results[str(d.get("aweme_id"))] = d
                got += 1
            print(f"  批量详情 {n}/{len(batches)}：{got}/{len(part)}", flush=True)
        except Exception as exc:  # noqa: BLE001
            print(f"  批量详情第 {n} 批失败：{exc}", file=sys.stderr, flush=True)
        time.sleep(0.4)

    missing = [v for v in ids if v not in results]
    if missing:
        print(f"  回退单条详情：{len(missing)} 个", flush=True)
        for vid in missing:
            try:
                results[vid] = client.get_video_detail(vid)
            except Exception as exc:  # noqa: BLE001
                failed.add(vid)
                print(f"  单条详情失败 {vid}: {exc}", file=sys.stderr, flush=True)
    return results, failed


def fmt_ts(epoch) -> str:
    try:
        return dt.datetime.fromtimestamp(int(epoch)).strftime("%Y-%m-%d %H:%M")
    except (TypeError, ValueError, OSError):
        return ""


def build_rows(category_items: dict[str, list[dict]], details: dict[str, dict]) -> list[dict]:
    rows = []
    for key, items in category_items.items():
        label = TABS.get(key, ("消息", ""))[0] if key != "message" else "消息"
        for item in items:
            vid = item["aweme_id"]
            detail = details.get(vid) or {}
            st = detail.get("statistics") or {}
            row = {
                "分类": label,
                "视频名称": (detail.get("desc") or item.get("card_text") or item.get("title") or "").strip(),
                "视频ID": vid,
                "作者": (detail.get("author") or {}).get("nickname") or "",
                "发布时间": fmt_ts(detail.get("create_time")),
                "点赞数": st.get("digg_count") or 0,
                "评论数": st.get("comment_count") or 0,
                "收藏数": st.get("collect_count") or 0,
                "转发数": st.get("share_count") or 0,
                "备注": "",
            }
            if key == "message":
                row["作者"] = item.get("author") or row["作者"]
                ts = item.get("ts") or item.get("time_label") or ""
                row["备注"] = f"私信时间 {ts}"
            elif item.get("card_text") and not detail:
                row["备注"] = f"卡片: {item['card_text'][:80]}"
            rows.append(row)
    return rows


def render_markdown(rows: list[dict]) -> str:
    if not rows:
        return "（无数据）"
    cols = ["分类", "视频名称", "视频ID", "作者", "发布时间", "点赞数", "评论数", "收藏数", "转发数", "备注"]
    header = "| " + " | ".join(cols) + " |"
    sep = "|" + "|".join(["---"] * len(cols)) + "|"
    lines = [header, sep]
    for r in rows:
        cells = []
        for c in cols:
            raw = r.get(c)
            v = "" if raw is None else str(raw)
            v = v.replace("|", "\\|").replace("\n", " ")
            if c == "视频名称" and len(v) > 60:
                v = v[:60] + "…"
            cells.append(v)
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="抖音「我的」个人数据整理")
    ap.add_argument(
        "--categories",
        default="like,favorite,record,watch_later,message",
        help="分类（逗号分隔）：like,favorite,record,watch_later,message，默认全部",
    )
    ap.add_argument("--conv", help="消息分类：私信会话名（昵称子串）")
    ap.add_argument("--index", type=int, help="消息分类：会话序号（从 1 开始）")
    ap.add_argument("--days", type=int, default=2, help="消息分类：时间窗口（自然日），默认 2")
    ap.add_argument("--list-convs", action="store_true", help="只列出私信会话列表")
    ap.add_argument("--list-only", action="store_true", help="只列 ID 与卡片文本，不取统计、不写文件")
    ap.add_argument("--out", help="输出目录（写 md/csv/json）")
    ap.add_argument("--limit", type=int, default=0, help="每个分类最多保留 N 条（0=不限）")
    ap.add_argument("--max-steps", type=int, default=1200, help="每个分类最大滚动步数（喜欢是大列表，可调大）")
    ap.add_argument("--tab-timeout", type=int, default=1800, help="单个分类浏览器进程超时秒数")
    ap.add_argument("--pace", type=int, default=3, help="分类之间的冷却秒数（降低风控概率，0=不冷却）")
    ap.add_argument("--fast-scroll", action="store_true", help="用程序化 scrollTop 滚动（更快，需实测确认分页触发）")
    ap.add_argument("--cache-dir", default="", help="采集缓存目录（逐分类落盘，中断可续跑）")
    ap.add_argument("--resume", action="store_true", help="优先读取缓存目录中已有分类，跳过重新采集（需 --cache-dir）")
    args = ap.parse_args()

    if args.resume and not args.cache_dir:
        args.cache_dir = os.path.expanduser("~/.cache/dy-wode")
        print(f"未指定 --cache-dir，默认使用 {args.cache_dir}", flush=True)

    if args.list_convs:
        list_convs()
        return 0

    keys = [k.strip() for k in args.categories.split(",") if k.strip()]
    unknown = [k for k in keys if k not in TABS and k != "message"]
    if unknown:
        sys.exit(f"未知分类：{unknown}。可用：like,favorite,record,watch_later,message")

    tab_keys = [k for k in keys if k != "message"]
    collected: dict[str, list[dict]] = {}
    if tab_keys:
        collected.update(collect_tabs(tab_keys, args))
    if "message" in keys:
        if args.conv or args.index is not None:
            collected["message"] = collect_messages(args)
        else:
            print("消息分类需要 --conv 会话名或 --index 序号（先运行 --list-convs 查看），本次跳过消息分类。", flush=True)

    for k, items in collected.items():
        if args.limit > 0:
            collected[k] = items[: args.limit]

    all_ids = [it["aweme_id"] for items in collected.values() for it in items]
    print(f"\n共采集 {len(all_ids)} 个作品：", flush=True)
    for k, items in collected.items():
        print(f"  {TABS.get(k, ('消息', ''))[0] if k != 'message' else '消息'}：{len(items)}", flush=True)

    if args.list_only:
        for k, items in collected.items():
            label = TABS.get(k, ("消息", ""))[0] if k != "message" else "消息"
            print(f"\n== {label} ==", flush=True)
            for it in items:
                print(f"  {it['aweme_id']}  {it.get('card_text') or it.get('author') or ''}", flush=True)
        return 0

    print("\n正在批量获取作品统计…", flush=True)
    details, failed = fetch_details(all_ids)
    rows = build_rows(collected, details)
    for row in rows:
        if row["视频ID"] in failed:
            row["备注"] = (row["备注"] + " " if row["备注"] else "") + "详情获取失败(可能已删除/仅自己可见)"

    print("\n" + render_markdown(rows), flush=True)

    if not args.out:
        return 0
    out_dir = os.path.abspath(os.path.expanduser(args.out))
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "dy_wode.md"), "w", encoding="utf-8") as f:
        f.write(render_markdown(rows) + "\n")
    with open(os.path.join(out_dir, "dy_wode.json"), "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)
    import csv

    with open(os.path.join(out_dir, "dy_wode.csv"), "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else ["分类"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"\n已写入：{out_dir}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
