#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
measure_layout.py — 徽章排版「量测法」工具

把配置渲染成海报页，用无头浏览器实测：
  · 地图画板 / 排行卡 / 标题区的真实占位
  · 每个城市多边形的实际包围盒（getBBox）
  · 每个高亮徽章的实际位置与尺寸（getBoundingClientRect）
  · 引线锚点（未加 offset 的真实城市中心）

并按三条硬指标自动验收：
  ① 归属：徽章与自身行政色块的相交面积 ≥ MIN_COVER%（默认 45）
  ② 重叠：任意两徽章相交面积 = 0
  ③ 越界：徽章落在页面安全区内、不压到排行卡

用法：
  python measure_layout.py --config examples/jiangsu_metro.json
  python measure_layout.py --config xxx.json --min-cover 40 --json

先用它算出「目标中心 − 多边形中心」得到 offset，改完配置再跑一遍复核。
禁止靠截图肉眼反复试调。
"""

import os
import sys
import json
import argparse
import tempfile

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE_DIR = os.path.join(SKILL_DIR, "templates")
SCRIPTS_DIR = os.path.join(SKILL_DIR, "scripts")
sys.path.insert(0, SCRIPTS_DIR)

from render_poster import build_html  # noqa: E402

PAGE_W, PAGE_H = 1080, 2160

JS = """
(rankNames) => {
  const rankName = {};
  (rankNames || []).forEach((n, i) => { rankName[String(i + 1)] = n; });
  const mw = document.getElementById('map-wrapper');
  const mwRect = mw.getBoundingClientRect();
  const rel = r => ({l: r.left - mwRect.left, r: r.right - mwRect.left,
                     t: r.top - mwRect.top,  b: r.bottom - mwRect.top});
  const out = {
    page: {w: window.innerWidth, h: window.innerHeight},
    wrapper: {l: mwRect.left, t: mwRect.top, w: mwRect.width, h: mwRect.height},
    headerBottom: document.querySelector('.header-area').getBoundingClientRect().bottom,
    rank: rel(document.getElementById('rank-panel').getBoundingClientRect()),
    footerTop: document.querySelector('.footer-area').getBoundingClientRect().top,
    cities: {}, anchors: [], badges: [], leaders: []
  };
  document.querySelectorAll('#map-svg path.city-polygon').forEach(el => {
    const bb = el.getBBox();
    out.cities[el.__data__.properties.name] =
      {x: bb.x, y: bb.y, r: bb.x + bb.width, b: bb.y + bb.height};
  });
  document.querySelectorAll('#badges-container .badge-card, #badges-container .chip-marker').forEach(el => {
    const nameEl = el.querySelector('.badge-city');
    out.badges.push({
      city: nameEl ? nameEl.innerText : (rankName[el.innerText] || ('chip#' + el.innerText)),
      kind: el.classList.contains('chip-marker') ? 'chip' : 'badge',
      ...rel(el.getBoundingClientRect())
    });
  });
  document.querySelectorAll('#leader-svg line').forEach(el => {
    out.leaders.push({x1: +el.getAttribute('x1'), y1: +el.getAttribute('y1'),
                      x2: +el.getAttribute('x2'), y2: +el.getAttribute('y2'),
                      w: parseFloat(el.getAttribute('stroke-width')),
                      stroke: el.getAttribute('stroke')});
  });
  document.querySelectorAll('#leader-svg circle[data-city]').forEach(el => {
    out.anchors.push({city: el.getAttribute('data-city'),
                      cx: +el.getAttribute('cx'), cy: +el.getAttribute('cy')});
  });
  return out;
}
"""

LEADER_MAX = 320.0


def _seg_hits_rect(x1, y1, x2, y2, rect, pad=2.0):
    """线段是否穿过矩形（采样法，够用且不引入几何库）"""
    n = 60
    for i in range(n + 1):
        t = i / n
        px, py = x1 + (x2 - x1) * t, y1 + (y2 - y1) * t
        if (rect["l"] - pad <= px <= rect["r"] + pad and
                rect["t"] - pad <= py <= rect["b"] + pad):
            return True
    return False


def measure(config_path, min_cover=45.0):
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)
    html = build_html(config_path)
    with tempfile.NamedTemporaryFile(suffix=".html", delete=False, dir=TEMPLATE_DIR,
                                     mode="w", encoding="utf-8") as tmp:
        tmp.write(html)
        tmp_path = tmp.name
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            try:
                browser = p.chromium.launch(headless=True)
            except Exception:
                browser = p.chromium.launch(
                    executable_path="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                    headless=True)
            ctx = browser.new_context(viewport={"width": PAGE_W, "height": PAGE_H})
            page = ctx.new_page()
            page.goto(f"file://{tmp_path}")
            page.wait_for_function("window.__RENDER_READY__ === true", timeout=20000)
            rank_names = [r.get("name", "") for r in (config.get("ranking") or [])]
            data = page.evaluate(JS, rank_names)
            browser.close()
    finally:
        try:
            os.remove(tmp_path)
        except Exception:
            pass

    report = {"geometry": data, "coverage": [], "leader_check": [],
              "overlaps": [], "violations": []}

    badges = {b["city"]: b for b in data["badges"]}

    # ① 归属（信息项：引线制下徽章允许外置，覆盖率只作参考）
    for b in data["badges"]:
        c = data["cities"].get(b["city"])
        if not c:
            report["coverage"].append({"city": b["city"], "cover": None})
            continue
        ix = max(0, min(b["r"], c["r"]) - max(b["l"], c["x"]))
        iy = max(0, min(b["b"], c["b"]) - max(b["t"], c["y"]))
        area = (b["r"] - b["l"]) * (b["b"] - b["t"])
        cov = ix * iy / area * 100 if area else 0
        report["coverage"].append({"city": b["city"], "cover": round(cov, 1)})

    # ② 重叠
    bs = data["badges"]
    for i in range(len(bs)):
        for j in range(i + 1, len(bs)):
            a, c = bs[i], bs[j]
            ox = max(0, min(a["r"], c["r"]) - max(a["l"], c["l"]))
            oy = max(0, min(a["b"], c["b"]) - max(a["t"], c["t"]))
            if ox * oy > 0:
                report["overlaps"].append({"a": a["city"], "b": c["city"],
                                           "area": round(ox * oy, 1)})
                report["violations"].append(
                    f'{a["city"]} ∩ {c["city"]} = {ox*oy:.0f} px²  必须推开')

    # ③ 引线健全性：有锚点 ⟺ 有引线；长度受限；不穿过别的徽章
    drawn = {}
    for ln in data["leaders"]:
        if ln["w"] and ln["w"] > 4:      # 只看彩色内线，白色描边成对出现
            key = (round(ln["x1"], 1), round(ln["y1"], 1))
            drawn[key] = ln
    for a in data["anchors"]:
        city = a["city"]
        ln = drawn.get((round(a["cx"], 1), round(a["cy"], 1)))
        if not ln:
            report["leader_check"].append({"city": city, "ok": False, "why": "无引线"})
            report["violations"].append(f'{city} 锚点存在但引线缺失')
            continue
        length = ((ln["x2"] - ln["x1"]) ** 2 + (ln["y2"] - ln["y1"]) ** 2) ** 0.5
        crossed = [n for n, r in badges.items()
                   if n != city and _seg_hits_rect(ln["x1"], ln["y1"], ln["x2"], ln["y2"], r)]
        ok = length <= LEADER_MAX and not crossed
        report["leader_check"].append({"city": city, "length": round(length, 1),
                                       "crosses": crossed, "ok": ok})
        if length > LEADER_MAX:
            report["violations"].append(f'{city} 引线过长 {length:.0f}px（上限 {LEADER_MAX:.0f}）')
        if crossed:
            report["violations"].append(f'{city} 引线穿过 {"、".join(crossed)} 的徽章')

    # ④ 越界 / 压排行卡 / 顶标题区
    wl = data["wrapper"]["l"]
    for b in data["badges"]:
        L, R = b["l"] + wl, b["r"] + wl
        if L < 8 or R > PAGE_W - 8:
            report["violations"].append(f'{b["city"]} 横向越界 {L:.0f}~{R:.0f}')
        if b["b"] > data["rank"]["t"]:
            report["violations"].append(f'{b["city"]} 压到排行卡')
        if b["t"] + data["wrapper"]["t"] < data["headerBottom"] + 4:
            report["violations"].append(f'{b["city"]} 顶到标题区')

    report["ok"] = not report["violations"]
    return report


def main():
    ap = argparse.ArgumentParser(description="地图图说徽章排版量测与验收")
    ap.add_argument("--config", "-c", required=True, help="配置文件路径 (JSON)")
    ap.add_argument("--min-cover", type=float, default=45.0, help="徽章落入自身色块的最低占比%%，默认 45")
    ap.add_argument("--json", action="store_true", help="以 JSON 输出（便于程序化反算 offset）")
    args = ap.parse_args()

    rep = measure(args.config, args.min_cover)
    if args.json:
        print(json.dumps(rep, ensure_ascii=False, indent=2))
        return 0 if rep["ok"] else 1

    g = rep["geometry"]
    print(f'画板 wrapper: left={g["wrapper"]["l"]:.0f} top={g["wrapper"]["t"]:.0f} '
          f'{g["wrapper"]["w"]:.0f}x{g["wrapper"]["h"]:.0f}')
    print(f'标题区底部 y={g["headerBottom"]:.0f}   '
          f'排行卡 top={g["rank"]["t"]:.0f} bottom={g["rank"]["b"]:.0f}   '
          f'页脚 top={g["footerTop"]:.0f}')

    print("\n【城市色块实际包围盒】(wrapper 坐标)")
    for n, c in sorted(g["cities"].items(), key=lambda kv: kv[1]["y"]):
        print(f'  {n:6s} x {c["x"]:7.1f}~{c["r"]:7.1f}   y {c["y"]:7.1f}~{c["b"]:7.1f}')

    print("\n【徽章实测位置 / 归属 / 引线】")
    cov = {c["city"]: c for c in rep["coverage"]}
    lc = {c["city"]: c for c in rep["leader_check"]}
    for b in sorted(g["badges"], key=lambda d: d["t"]):
        c = cov.get(b["city"], {})
        l = lc.get(b["city"], {})
        if b.get("kind") == "chip":
            ltxt = "编号点（无引线）"
        else:
            ltxt = (f'引线 {l["length"]:.0f}px' if l.get("length") else "引线 —（压在城市上）")
        print(f'  {b["city"]:4s} x {b["l"]:7.1f}~{b["r"]:7.1f}  '
              f'y {b["t"]:7.1f}~{b["b"]:7.1f}  ({b["r"]-b["l"]:.0f}x{b["b"]-b["t"]:.0f})  '
              f'覆盖色块 {c.get("cover")}%  {ltxt}')

    print("\n【验收】（重叠 / 越界 / 引线健全）")
    if rep["ok"]:
        print("  ✅ 全部通过")
    else:
        for v in rep["violations"]:
            print(f"  ❌ {v}")
    return 0 if rep["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
