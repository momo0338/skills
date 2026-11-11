#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""wx_cell_wrap_check.py — 表格单元格折行预检（零 Token，纯计算）

背景（2026-11-10 定）：
  当天 8 篇稿子里 6 篇因表格列宽不足导致「单字成行」，每次都要
  「改 facts → gen → preview → 看图」四步往返（约 40s），最深一次
  （中工国际）连踩 3 轮。本脚本在 gen 后、preview 前直接算出来，
  把这类返工归零。

参数来源（勿凭感觉改）：
  · 字体：mp-html/scripts/layout_kit.py 的 th/td 均为 font-size:12.5px
  · 内边距：td padding:5px 4px → 左右 8px；table 为 table-layout:fixed
  · 容器宽度：375px 视口下 table width:100% 的可用宽 ≈ 360px
  用当天实测边界反验：
    7 字 @28% 单行 ✓ / @26% 折 ✓        → 公式给出 7.4 字
    8 字 @33% 单行 ✓ / @28% 折 ✓        → 公式给出 8.9 / 7.4 字
    9 字 @34% 单行 ✓                     → 公式给出 9.2 字
    5 字 @22% 单行 ✓ / @16% 折 ✓        → 公式给出 5.7 / 4.0 字
  四组边界全部吻合，故参数可信。

用法：
  python3 wx_cell_wrap_check.py <facts.json>            # 检查并打印
  python3 wx_cell_wrap_check.py <facts.json> --strict   # 有孤字则 exit 1

判定口径：
  ⛔ 单字孤行 —— 某格折行后，最后一行有效字数 < 1.5（一个汉字左右），
     肉眼就是「上」「贴」「类」「员」这种孤立字，必须修；
  ⚠️ 折行 —— 内容超出一行但末行有实质内容，可接受，仅提示。
"""
import json
import math
import sys

VIEW_W = 375.0      # 基准视口
TABLE_W = 345.0     # 375px 下 table 可用宽（375 - 左右各 15px 正文留白）
FONT = 12.5         # 字号
PAD = 3.0           # td 实际吃掉的左右留白（padding 8px 但字距会回卷，实测取 3 更贴边界）
WARN_LAST = 1.5     # 末行有效字数低于此值 → 单字孤行（一个汉字 ≈1.0，留 0.5 容差）


def char_eff(ch):
    """单字符等效中文字宽（1.0 = 一个汉字宽）。"""
    o = ord(ch)
    if o < 128:
        if ch == ' ':
            return 0.30
        if ch.isdigit():
            return 0.56
        if ch.isalpha():
            return 0.55
        if ch in ',.:;|/()[]':
            return 0.40
        return 0.50
    # 全角标点与汉字同宽
    return 1.0


def eff_len(s):
    s = str(s).replace('<br>', '').replace('<br/>', '')
    return sum(char_eff(c) for c in s)


def capacity(pct):
    """该列宽百分比下，一行能容纳的等效中文字数。"""
    return max(0.0, (TABLE_W * pct / 100.0 - PAD) / FONT)


def suggest_pct(need_eff):
    """要一行装下 need_eff 个字，至少需要多少列宽百分比。"""
    return (need_eff * FONT + PAD) / TABLE_W * 100.0


def simulate(text, cap):
    """贪心模拟换行，返回每行的有效字数列表。

    修 bug（2026-11-10 首版实测）：原实现换行时把触发字符同时算进新旧两行，
    导致每行少装一个字、虚报大量孤字（r38 报 5 处、实际只 1 处）。
    现改为换行时 cur 归零、由循环末尾统一累加。
    <br> 视为强制换行。
    """
    if cap <= 0:
        return [eff_len(text)]
    text = str(text).replace('<br>', '\n').replace('<br/>', '\n')
    lines = []
    for seg in text.split('\n'):
        cur = 0.0
        for ch in seg:
            w = char_eff(ch)
            if cur + w > cap + 1e-9 and cur > 0:
                lines.append(cur)
                cur = 0.0
            cur += w
        lines.append(cur)
    return lines


def check(facts_path, verbose=False):
    """返回 [(section, row_idx, col_idx, text, pct, cap, last_eff, kind)]，kind ∈ {'孤字','折行'}"""
    with open(facts_path, encoding='utf-8') as f:
        facts = json.load(f)
    issues = []
    total = 0
    for sec in facts.get('sections') or []:
        tb = sec.get('table')
        if not tb:
            continue
        widths = tb.get('widths') or []
        rows = tb.get('rows') or []
        for ri, row in enumerate(rows, 1):
            for ci, cell in enumerate(row):
                if ci >= len(widths):
                    continue
                pct = widths[ci]
                cap = capacity(pct)
                # 含空格/间隔号的内容可利用该断点，实测比纯逐字模拟多容约半字
                # （r38「硕士及以上 · 北京/海外」@20% 实测 2 行可读，不致孤字）
                cap_eff = cap + (0.5 if (' ' in str(cell) or '·' in str(cell)) else 0.0)
                total += 1
                # 含 URL/邮箱的格：长串必然折断，孤字判定无意义，跳过（2026-11-10）
                if any(k in str(cell) for k in ('www.', 'http', '@', '.com', '.cn')):
                    continue
                lines = simulate(cell, cap_eff)
                if len(lines) < 2:
                    continue
                last = lines[-1]
                if last < 0.6:
                    issues.append((sec.get('title', ''), ri, ci, str(cell),
                                   pct, cap, last, '孤字'))
                elif last < WARN_LAST:
                    issues.append((sec.get('title', ''), ri, ci, str(cell),
                                   pct, cap, last, '待确认'))
                elif verbose:
                    issues.append((sec.get('title', ''), ri, ci, str(cell),
                                   pct, cap, last, '折行'))
    return issues, total


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    path = sys.argv[1]
    strict = '--strict' in sys.argv
    verbose = '--all' in sys.argv
    issues, total = check(path, verbose=verbose)
    hard = [i for i in issues if i[7] == '孤字']
    mid = [i for i in issues if i[7] == '待确认']
    soft = [i for i in issues if i[7] == '折行']

    print(f'[折行预检] {VIEW_W:.0f}px 视口 | 检查 {total} 格 | '
          f'孤字 {len(hard)} | 待确认 {len(mid)} | 折行 {len(soft)}')
    for sec, ri, ci, text, pct, cap, last, kind in hard:
        need = suggest_pct(eff_len(text))
        if need > 60:
            tip = f'列宽需 ≥{need:.0f}%（过大，建议改写内容或拆分单元格）'
        else:
            tip = f'单行需 ≥{need:.0f}%'
        print(f'  ⛔ [{sec}] 第{ri}行第{ci+1}列 "{text[:26]}" '
              f'({eff_len(text):.1f}字) 列宽{pct}% 仅容{cap:.1f}字 → 末行只剩{last:.1f}字；{tip}')
    for sec, ri, ci, text, pct, cap, last, kind in mid:
        need = suggest_pct(eff_len(text))
        tip = '建议改写内容或拆分单元格' if need > 60 else f'可加宽至 ≥{need:.0f}%'
        print(f'  ⚠️  [{sec}] 第{ri}行第{ci+1}列 "{text[:26]}" '
              f'列宽{pct}% 末行约{last:.1f}字（边缘值，{tip}；以 preview 为准）')
    for sec, ri, ci, text, pct, cap, last, kind in soft:
        print(f'  ⚠️  [{sec}] 第{ri}行第{ci+1}列 "{text[:26]}" 折{math.ceil(eff_len(text)/max(cap,0.1))}行'
              f'（末行{last:.1f}字，可接受）')
    if not issues:
        print('  ✅ 无折行风险')
    elif not hard:
        print('  ✅ 无确定孤字' + ('（有边缘值待 preview 复核）' if mid else '（仅普通折行）'))
    else:
        print(f'  → 建议：把上面列宽调到建议值，或改写内容缩短；改完重跑 gen + 本脚本')
    if strict and hard:
        sys.exit(1)


if __name__ == '__main__':
    main()
