#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
抖音私信视频批量下载工具（ego-browser + dy-cli）

背景：dy-cli / opencli 均无法读取抖音私信，私信视频只能先拿到作品 ID 再下载。
本脚本把"浏览器取 ID + dy-cli 下载"固化为一条命令：
  1. 用 ego-browser（已安装、继承用户登录态）打开抖音消息面板
  2. 定位指定会话，滚动加载全部历史消息
  3. 识别视频分享卡片，逐个点击读取 modal_id（作品 ID），记录时间/作者
  4. 按时间窗口过滤（近 N 天）
  5. 用 dy-cli 技能脚本串行下载 + metadata 校验

依赖（均已就绪）：
  - ego-browser CLI（ego lite 应用，已装；抖音已登录）
  - dy-cli 0.2.2（已装、已登录），技能目录 /Users/zhugx/src/skills/dy-cli

用法：
  # 只看结果不下载（先确认筛选是否正确）
  python3 dy_im_videos.py --conv "亚马逊啊" --days 2 --list-only

  # 正式下载到指定目录
  python3 dy_im_videos.py --conv "亚马逊啊" --days 2 --out ~/Downloads/xxx

  # 会话名匹配不到时，用 --list-convs 先看会话列表，再用 --index N 指定
  python3 dy_im_videos.py --list-convs
  python3 dy_im_videos.py --index 1 --days 2 --out ~/Downloads/xxx

说明：
  - 时间窗口口径：近 N 天按自然日算（days=2 即 昨天 00:00 至今），与本次"这两天"一致
  - 下载保持串行，避免触发风控
  - 全程只读私信并下载，不做任何发送/点赞/评论等操作
"""

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
import tempfile

EGO = os.environ.get("EGO_BROWSER", "/Users/zhugx/.local/bin/ego-browser")
DY_SKILL_DIR = os.environ.get(
    "DY_SKILL_DIR", "/Users/zhugx/src/skills/dy-cli"
)


def run_ego(node_code: str, timeout: int = 900) -> str:
    """把 node 脚本通过 stdin 交给 ego-browser nodejs 执行，返回全部输出。

    注意：ego-browser 的 cliLog 输出走 stderr，因此合并 stdout+stderr 返回。
    """
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
            f"ego-browser 执行失败 (rc={proc.returncode})\n"
            f"OUTPUT: {combined[-2000:]}"
        )
    return combined


NODE_TEMPLATE = r"""
// 每次运行使用唯一任务空间名，避免复用上次失败残留的脏状态
const task = await useOrCreateTaskSpace('dy-im-videos-' + Date.now())

// 1. 打开抖音首页
await openOrReuseTab('https://www.douyin.com/', { wait: true, timeout: 25 })
await wait(6)

// 2. 打开消息面板（点顶部「消息」入口）
const msgBtn = await js(`(() => {
  const ps = [...document.querySelectorAll('p, span')];
  const p = ps.find(el => el.textContent.trim() === '消息');
  if (!p) return null;
  const r = p.getBoundingClientRect();
  return { x: Math.round(r.x + r.width / 2), y: Math.round(r.y + r.height / 2) };
})()`)
if (!msgBtn) { cliLog('ERROR: 未找到消息入口'); throw new Error('no msg button') }
await click([msgBtn.x, msgBtn.y], { label: 'open messages' })
await wait(4)

// 开启网络捕获（必须在点开会话之前，会话打开时会发出批量详情请求）
try { await cdp('Network.enable', {}) } catch (e) {}
try { await cdp('Network.setCacheDisabled', { cacheDisabled: true }) } catch (e) {}
await drainEvents()

// 3. 定位并打开会话（最多 4 次尝试，每次验证聊天区是否真的打开）
__SELECT_CONV__

await wait(3)

// 4. 滚动加载全部历史消息，边滚边记录卡片时间/作者

const recordSeen = async () => {
  await js(`(() => {
    // 兼容新旧两套抖音私信 UI
    const list = document.querySelector('.messageMessageListlist') ||
                 document.querySelector('#messageContent .NiBeo9E2') ||
                 document.getElementById('messageContent');
    if (!list) return;
    const cards = [...list.querySelectorAll('.MessageItemShareAwemecontainer, .RptWjOTU')];
    const known = window.__seenMap || (window.__seenMap = {});
    const ordered = window.__seenList || (window.__seenList = []);
    for (const card of cards) {
      const a = card.querySelector('.MessageItemShareAwemeauthorName, .DVAX4Fpn');
      const author = a ? a.textContent.trim() : '';
      if (!author || author in known) continue;
      // 精确定位消息项：最外层 messageMessageBox* 祖先（每个消息的独立容器）
      let cur = card;
      let itemWrap = null;
      while (cur && cur.parentElement) {
        if ((cur.className || '').toString().includes('messageMessageBox')) itemWrap = cur;
        cur = cur.parentElement;
      }
      const t = itemWrap ? itemWrap.querySelector('.MessageBoxTimetimeLayout, .BuKRiTiA') : null;
      known[author] = t ? t.textContent.trim() : '';
      ordered.push({ author, time: known[author] });
    }
  })()`)
}

const box = await js(`(() => {
  const l = document.querySelector('.messageMessageListlist') ||
            document.querySelector('#messageContent .NiBeo9E2') ||
            document.getElementById('messageContent');
  if (!l) return { x: 1260, y: 400 };
  const r = l.getBoundingClientRect();
  return { x: Math.round(r.x + r.width / 2), y: Math.round(r.y + r.height / 2) };
})()`)

// 分阶段收集 multi/aweme/detail 请求中的作品 ID（防止事件缓冲溢出）
const ids = []
const collectIds = (evs) => {
  for (const e of (evs || [])) {
    if (e.method !== 'Network.requestWillBeSent') continue
    const url = (e.params && e.params.request && e.params.request.url) || ''
    const m = url.match(/aweme_ids=%5B(.*?)%5D/)
    if (!m) continue
    for (const p of m[1].split('%2C')) {
      const d = decodeURIComponent(p)
      if (/^\d+$/.test(d) && !ids.includes(d)) ids.push(d)
    }
  }
}

// 会话打开时的初始批量请求（最新的视频 ID）
collectIds(await drainEvents())
await recordSeen()
// 上下双向滚动加载更旧消息，自适应停止
let noNew = 0
for (let cycle = 0; cycle < 8 && noNew < 2; cycle++) {
  const before = ids.length
  for (let i = 0; i < 12; i++) {
    await cdp('Input.dispatchMouseEvent', { type: 'mouseWheel', x: box.x, y: box.y, deltaX: 0, deltaY: 500 })
    await wait(0.25)
    await recordSeen()
  }
  collectIds(await drainEvents())
  for (let i = 0; i < 12; i++) {
    await cdp('Input.dispatchMouseEvent', { type: 'mouseWheel', x: box.x, y: box.y, deltaX: 0, deltaY: -500 })
    await wait(0.25)
    await recordSeen()
  }
  collectIds(await drainEvents())
  if (ids.length === before) noNew++; else noNew = 0
}

// 5. 按顺序配对输出 TIME|AUTHOR|ID（ids 与记录列表均为新 → 旧）
const seenList = await js(`window.__seenList || []`)
for (let i = 0; i < ids.length; i++) {
  const s = seenList[i] || {}
  cliLog('LINE|' + (s.time || '') + '|' + (s.author || '') + '|' + ids[i])
}
try { await completeTaskSpace(task.id, { keep: false }) } catch (e) {}
"""


def conv_selector(args) -> str:
    if args.list_convs:
        return r"""
const items = await js(`(() => {
  // 会话列表项：私信面板里带 分享/消息预览 的条目
  const all = [...document.querySelectorAll('div')]
  const seen = new Set()
  const out = []
  for (const el of all) {
    const t = (el.textContent || '').trim()
    if (t.length > 5 && t.length < 60 && /分享|私信|消息|昨天|星期/.test(t) && !seen.has(t)) {
      seen.add(t)
      out.push(t.slice(0, 40))
    }
  }
  return out.slice(0, 15)
})()`)
for (const it of items) cliLog('CONV|' + it)
throw new Error('list-convs done')
"""
    if args.index is not None:
        return f"""
const clicked = await js(`(() => {{
  const all = [...document.querySelectorAll('div')]
  // 会话列表条目标记：文本短、包含时间/分享预览的容器
  const candidates = all.filter(el => {{
    const t = (el.textContent || '').trim()
    return t.length > 5 && t.length < 80 && el.children.length >= 2
  }})
  return candidates.length
}})()`)
cliLog('DEBUG: conv candidates ' + clicked)
"""
    # 按名称匹配：带重试与打开验证
    return f"""
const chatReady = false
let convOpened = false
for (let i = 0; i < 4 && !convOpened; i++) {{
  // 先验证当前是否已打开，避免重复点击把会话点关
  convOpened = await js(`!!(document.querySelector('.messageMessageListlist') || document.getElementById('messageContent') || document.body.innerText.includes('发送消息'))`)
  if (convOpened) break
  const found = await js(`(() => {{
    // 优先按会话列表类名找，其次回退到文本搜索
    let hit = [...document.querySelectorAll('.conversationConversationItemwrapper')]
      .find(it => (it.textContent || '').includes('{args.conv}'))
    if (!hit) {{
      const all = [...document.querySelectorAll('div')]
      hit = all.find(el => {{
        const t = (el.textContent || '').trim()
        return t.includes('{args.conv}') && t.length < 60 && el.children.length < 8
      }})
    }}
    if (!hit) return null
    const r = hit.getBoundingClientRect()
    if (r.width < 50 || r.height < 10) return null  // 面板未渲染完成时坐标为 0，视为未找到
    return {{ x: Math.round(r.x + r.width / 2), y: Math.round(r.y + r.height / 2) }}
  }})()`)
  if (!found) {{ cliLog('WARN: 未找到会话「{args.conv}」，重试中…'); await wait(3); continue }}
  await click([found.x, found.y], {{ label: 'open conversation' }})
  await wait(2.5)
  convOpened = await js(`!!(document.querySelector('.messageMessageListlist') || document.getElementById('messageContent') || document.body.innerText.includes('发送消息'))`)
  if (!convOpened) cliLog('WARN: 会话未打开，重试中…')
}}
if (!convOpened) {{
  cliLog('ERROR: 未能打开会话「{args.conv}」。请先运行 --list-convs 查看可用会话，再用 --index N 指定。')
  throw new Error('conv not open')
}}
"""


WEEKDAY = {"一": 0, "二": 1, "三": 2, "四": 3, "五": 4, "六": 5, "日": 6}


def parse_time_label(label: str, today: dt.date) -> dt.datetime | None:
    label = label.strip()
    if not label:
        return None
    m = re.match(r"^(\d{2}):(\d{2})$", label)
    if m:
        return dt.datetime.combine(today, dt.time(int(m.group(1)), int(m.group(2))))
    m = re.match(r"^昨天\s+(\d{2}):(\d{2})$", label)
    if m:
        return dt.datetime.combine(
            today - dt.timedelta(days=1),
            dt.time(int(m.group(1)), int(m.group(2))),
        )
    if label == "前天":
        return dt.datetime.combine(today - dt.timedelta(days=2), dt.time.min)
    m = re.match(r"^星期([一二三四五六日])\s+(\d{2}):(\d{2})$", label)
    if m:
        wd = WEEKDAY[m.group(1)]
        days_back = (today.weekday() - wd) % 7
        d = today - dt.timedelta(days=days_back)
        return dt.datetime.combine(d, dt.time(int(m.group(2)), int(m.group(3))))
    m = re.match(r"^(\d{2})/(\d{2})$", label)
    if m:
        mon, day = int(m.group(1)), int(m.group(2))
        try:
            d = dt.date(today.year, mon, day)
        except ValueError:
            return None
        if d > today:
            d = dt.date(today.year - 1, mon, day)
        return dt.datetime.combine(d, dt.time.min)
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})\s+(\d{2}):(\d{2})$", label)
    if m:
        return dt.datetime(
            int(m.group(1)), int(m.group(2)), int(m.group(3)),
            int(m.group(4)), int(m.group(5)),
        )
    return None


def filter_by_days(lines, days):
    """lines: [(time_label, author, id)]，DOM 顺序新→旧。返回过滤后的列表。"""
    today = dt.date.today()
    parsed = [parse_time_label(t, today) for t, _, _ in lines]
    # 空时间标签继承最近的有标签邻居（索引距离最小者）
    for i in range(len(parsed)):
        if parsed[i] is not None:
            continue
        best = None
        best_dist = None
        for j, p in enumerate(parsed):
            if p is None:
                continue
            dist = abs(i - j)
            if best_dist is None or dist < best_dist or (dist == best_dist and j < i):
                best = p
                best_dist = dist
        parsed[i] = best
    cutoff = dt.datetime.combine(today - dt.timedelta(days=days - 1), dt.time.min)
    out = []
    for (t, a, vid), ts in zip(lines, parsed):
        if vid and vid not in ("NONE", "SKIP") and ts and ts >= cutoff:
            out.append((t, a, vid, ts))
    return out


def main():
    ap = argparse.ArgumentParser(description="抖音私信视频批量下载")
    ap.add_argument("--conv", help="会话名（昵称子串）")
    ap.add_argument("--index", type=int, help="会话列表序号（从 1 开始）")
    ap.add_argument("--days", type=int, default=2, help="时间窗口（自然日），默认 2")
    ap.add_argument("--out", help="输出目录（缺省仅列出，不下载）")
    ap.add_argument("--list-only", action="store_true", help="只列出视频，不下载")
    ap.add_argument("--list-convs", action="store_true", help="列出会话列表")
    ap.add_argument("--json", action="store_true", help="输出 JSON 数组（供 dy-wode 主脚本消费），不下载")
    args = ap.parse_args()

    if args.list_convs:
        code = NODE_TEMPLATE.replace("__SELECT_CONV__", conv_selector(args))
        out = run_ego(code)
        for line in out.splitlines():
            if line.startswith("CONV|"):
                print(line[5:])
        return

    if not args.conv and args.index is None:
        sys.exit("请指定 --conv 会话名，或 --index 序号（先用 --list-convs 查看）。")

    code = NODE_TEMPLATE.replace("__SELECT_CONV__", conv_selector(args))
    if not args.json:
        print("正在通过 ego-browser 打开抖音并收集私信视频 ID…")
    out = run_ego(code)
    lines = []
    for line in out.splitlines():
        if line.startswith("LINE|"):
            _, t, a, vid = line.split("|", 3)
            lines.append((t, a, vid))
    if not lines:
        print("未收集到视频消息。输出片段：")
        print(out[-1500:])
        sys.exit(1)

    picked = filter_by_days(lines, args.days)

    if args.json:
        print(json.dumps(
            [
                {"category": "message", "time_label": t, "author": a, "aweme_id": vid, "ts": ts.isoformat()}
                for t, a, vid, ts in picked
            ],
            ensure_ascii=False,
            indent=2,
        ))
        return

    print("\n收集到的全部视频（时间 | 作者 | ID）：")
    for t, a, vid in lines:
        print(f"  {t or '—':<16} [{a}]  {vid}")
    print(f"\n会话中共 {len(lines)} 个视频，近 {args.days} 天内 {len(picked)} 个：")
    for t, a, vid, ts in picked:
        print(f"  {ts:%m-%d %H:%M}  [{a}]  {vid}")

    if args.list_only:
        return

    out_dir = args.out
    if not out_dir:
        sys.exit("未指定 --out 输出目录（或加 --list-only 只查看）。")
    os.makedirs(out_dir, exist_ok=True)
    script = os.path.join(DY_SKILL_DIR, "scripts", "download_with_metadata.py")
    if not os.path.exists(script):
        sys.exit(f"未找到 dy-cli 下载脚本：{script}")
    for _, _, vid, _ in picked:
        print(f"\n== 下载 {vid} ==")
        proc = subprocess.run(
            [sys.executable, script, vid, "-o", out_dir],
            text=True,
            capture_output=True,
        )
        tail = (proc.stdout or proc.stderr).strip().splitlines()
        print(tail[-1] if tail else f"rc={proc.returncode}")

    print(f"\n完成。输出目录：{out_dir}")


if __name__ == "__main__":
    main()
