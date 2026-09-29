#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
微信正文横向溢出检测（2026-09-26 建成）

为什么需要这个脚本
------------------
`wx_dialect_check.py` 只能校验"微信会不会剥掉我的语法"，管不了"排版在手机上会不会撑破"。
后者是纯视觉问题，**肉眼看截图基本看不出来**——肉眼只能看到 6px 级别的偏差，
而且必须逐元素比较 `scrollWidth > clientWidth` 才能抓到（`documentElement` 层面常常是 false）。

三个必须知道的坑（都是实测踩出来的）
------------------------------------
1. **不能只看 `documentElement.scrollWidth`**：它常常返回 false，但子元素真实溢出。
   必须遍历元素逐个比 `scrollWidth > clientWidth + 1`。
2. **CSS 断行属性对 CJK 禁则标点全部失效**：
   `word-break:break-all` / `overflow-wrap:anywhere` / `line-break:anywhere`
   都无法让 `）`(U+FF09) `」`(U+300D) `』`(U+300F) 换行。
   因为它们是"行首禁则标点"，浏览器宁可撑破容器也不肯让它们落在行首。
   **唯一可靠解法：输出层把全角括号/引号换成半角/直角。**
3. **letter-spacing 是累积量**：每字符都加，末行必然溢出 2~4px。字段行一律 0，
   呼吸感靠 line-height 补，不要靠字距。

用法
----
    python wx_overflow_check.py <排版稿.html> [宽度,逗号分隔]
    python wx_overflow_check.py 稿.html --json
    python wx_overflow_check.py 稿.html --locate     # 逐字符定位溢出点（排障用）

默认宽度 320,360,375,414,677。375/414 是微信 iOS/Android 主力宽度，
320 是老机型下限，360/677 用于覆盖 Android 常见宽度与 PC 预览。
全部通过才算过；--locate 模式会在最窄失败宽度下逐字符打出越界字符。
"""
import asyncio
import json
import pathlib
import sys

DEFAULT_WIDTHS = [320, 360, 375, 414, 677]
TOL = 1  # px 容差，规避亚像素舍入

# 逐元素溢出扫描（含 strong/span，flex 布局里子元素是主要溢出源）
COUNT_JS = """
(tol) => {
  const bad = [];
  for (const e of document.querySelectorAll('section,p,strong,span,table,td,th,li')) {
    if (e.clientWidth > 0 && e.scrollWidth > e.clientWidth + tol) {
      bad.push({tag: e.tagName, sw: e.scrollWidth, cw: e.clientWidth,
                d: e.scrollWidth - e.clientWidth,
                txt: (e.textContent||'').trim().slice(0, 45)});
    }
  }
  const de = document.documentElement;
  return {docOverflow: de.scrollWidth > de.clientWidth + tol,
          docSW: de.scrollWidth, docCW: de.clientWidth,
          bad: bad.slice(0, 20), badCount: bad.length};
}
"""

# 逐字符定位：Range 量每个字的 getBoundingClientRect，找出真正越界的字符
LOCATE_JS = """
() => {
  const out = [];
  const els = [...document.querySelectorAll('p')]
      .filter(e => e.scrollWidth > e.clientWidth + 1 && e.clientWidth > 0);
  for (const p of els) {
    const pr = p.getBoundingClientRect();
    const range = document.createRange();
    const over = [];
    for (const n of p.childNodes) {
      if (n.nodeType !== 3) continue;
      const s = n.textContent;
      for (let i = 0; i < s.length; i++) {
        range.setStart(n, i); range.setEnd(n, i + 1);
        const b = range.getBoundingClientRect();
        if (b.width === 0 && b.height === 0) continue;
        if (b.right > pr.right + 0.5)
          over.push({ch: s[i], cp: 'U+' + s.codePointAt(i).toString(16).toUpperCase(),
                     over: +(b.right - pr.right).toFixed(2)});
      }
    }
    // 顺便报出最长的不可断 ASCII 串（word-break:break-all 理论上能断它）
    const txt = p.textContent || '';
    out.push({txt: txt.slice(0, 60), cw: p.clientWidth, sw: p.scrollWidth,
              wordBreak: getComputedStyle(p).wordBreak,
              letterSpacing: getComputedStyle(p).letterSpacing,
              fontSize: getComputedStyle(p).fontSize,
              textAlign: getComputedStyle(p).textAlign,
              lines: (txt.match(/[!-~]{4,}/g) || []),
              overChars: over});
  }
  return out;
}
"""


async def _run(path, widths, locate):
    from playwright.async_api import async_playwright
    url = pathlib.Path(path).resolve().as_uri()
    results = []
    async with async_playwright() as pw:
        b = await pw.chromium.launch()
        for w in widths:
            pg = await b.new_page(viewport={"width": w, "height": 900})
            await pg.goto(url, wait_until="load")
            await pg.wait_for_timeout(220)
            r = await pg.evaluate(COUNT_JS, TOL)
            r["width"] = w
            r["locate"] = await pg.evaluate(LOCATE_JS) if (locate and r["badCount"]) else None
            results.append(r)
            await pg.close()
        await b.close()
    return results


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return 1
    path = args[0]
    if not pathlib.Path(path).exists():
        print(f"文件不存在：{path}")
        return 1
    as_json = "--json" in args
    locate = "--locate" in args
    wpos = [i for i, a in enumerate(args) if not a.startswith("--") and i > 0]
    widths = ([int(x) for x in args[wpos[0]].split(",")] if wpos else DEFAULT_WIDTHS)

    results = asyncio.run(_run(path, widths, locate))
    if as_json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return 0 if all(not r["docOverflow"] and r["badCount"] == 0 for r in results) else 1

    print(f"横向溢出检测：{pathlib.Path(path).name}")
    allpass = True
    for r in results:
        ok = not r["docOverflow"] and r["badCount"] == 0
        allpass = allpass and ok
        print(f"  {'OK  ' if ok else 'FAIL'} {r['width']:>4}px  "
              f"文档溢出={str(r['docOverflow']):5s} ({r['docSW']}/{r['docCW']})  "
              f"子元素溢出={r['badCount']}")
        for x in r["bad"]:
            print(f"        <{x['tag']}> +{x['d']}px (sw={x['sw']} cw={x['cw']})  {x['txt']}")
        if r.get("locate"):
            for e in r["locate"]:
                print(f"      定位：cw={e['cw']} fontSize={e['fontSize']} "
                      f"letterSpacing={e['letterSpacing']} wordBreak={e['wordBreak']} "
                      f"textAlign={e['textAlign']}")
                print(f"        文本：{e['txt']}")
                print(f"        越界字符：{e['overChars']}")
                if e["lines"]:
                    print(f"        ASCII 串：{e['lines']}")
    print("✅ 全部通过" if allpass else "❌ 存在溢出（--locate 看逐字符定位）")
    return 0 if allpass else 1


if __name__ == "__main__":
    sys.exit(main())
