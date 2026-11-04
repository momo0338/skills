#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gen_article.py —— md 驱动的教育线通用排版引擎（school-write）。

一份引擎吃所有稿：源稿 md（7 段骨架）＋色板 → 排版 HTML。
⛔ 不再每稿写一个 py。

用法：
  gen_article.py <源稿.md> --out <排版.html> [--brand #920303 --dark #5E0606] [--palette auto]

  --palette auto：按 frontmatter「单位」自动查内置 VI 台账（school-write §8.5 数据版），
                  未命中再回落到 --brand/--dark。

md 解析约定（源稿写作即排版约定）：
  ## 段名          → 蓝色段标题（七段名跑 must_have 断言）
  普通段落          → p（**加粗**→strong，URL 自动 word-break span）
  **Q…：** 行＋下一段 → FAQ 卡（「常见问答」段内）
  | 表格 |          → 斑马表格（首行表头）
  > 引用            → 小字注释行
  - / 1. 列表       → 列表段（无序不加点、编号加「N.」——正文永不出现「•」）
  ## 码上君划重点    → 划重点卡：首段=导语，「**第…，」开头段落 ≥2 自动聚为编号要点
  ## 源稿核验记录 及之后 → 不渲染
"""
import re, sys, os, argparse

sys.path.insert(0, os.path.expanduser('~/src/skills/mp-html/scripts'))
from layout_kit import Layout

# ── VI 台账（school-write §8.5 数据版；新增主体在此加一行）
PALETTES = {
    '江苏海洋大学': ('#0D59A7', '#08477F', '#eef4fa', '#cfdff0', '#f5f8fc', '#d5e2f0'),
    '扬州大学':     ('#016E34', '#014A24', '#edf5f0', '#cfe3d8', '#f4faf6', '#d8e8e0'),
    '南京特殊教育师范学院': ('#E10000', '#A30000', '#fdf3f3', '#eedcdc', '#faf6f6', '#eaddde'),
    '南京工程学院': ('#11509D', '#0C3D74', '#eef3fa', '#dce4ef', '#f6f9fc', '#dbe4f0'),
    '中国人民大学': ('#920303', '#5E0606', '#fdf3f3', '#eedcdc', '#faf6f6', '#eaddde'),
    '泰州学院':     ('#009BB2', '#006B7E', '#edf6f8', '#c9e2e8', '#f4fafb', '#d3e8ec'),
    '南京师范大学': ('#217050', '#14472F', '#eef5f1', '#cfe3d8', '#f7faf8', '#d8e8e0'),
    '吴江区教育':   ('#B20000', '#7A0000', '#fdf3f3', '#eedcdc', '#faf6f6', '#eaddde'),
    '大丰区':       ('#B00000', '#8A0000', '#fdf3f3', '#eedcdc', '#faf6f6', '#eaddde'),
    '盐城师范学院': ('#3A637B', '#2A4759', '#eef3f6', '#d3e0e8', '#f5f9fb', '#dbe6ed'),
}

MUST_SECTIONS = ['码上君划重点', '招聘速览', '单位与岗位性质', '招什么人',
                 '报考条件与禁报', '怎么报名', '考核·体检·公示·服务期', '常见问答']


def inline(md_text):
    """md 内联转换：URL→word-break span；**加粗**→strong。

    ⛔ 顺序必须先 URL 后加粗：先加粗会把 URL 变成 <strong>URL</strong>，
    其负向后顾 (?<!...) 遇到 strong 的 ">" 必失配，漏 word-break（390px 溢出风险）。
    先 URL 后加粗得 <strong><span word-break>URL</span></strong>（南师大稿形态）。
    """
    t = re.sub(r'(?<![\'"=\w>])(https?://[^\s<>）」」*]+)',
               r'<span style="word-break:break-all;">\1</span>', md_text)
    t = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', t)
    return t


def parse_md(path):
    """源稿 md → (title, sections=[(段名, [块…])])；块=('p'|'note'|'table'|'ul'|'faq'|'qa', 数据)"""
    raw = open(path, encoding='utf-8').read()
    m = re.match(r'^---\n(.*?)\n---\n', raw, re.S)
    fm = {}
    if m:
        for line in m.group(1).splitlines():
            if ':' in line:
                k, _, v = line.partition(':')
                fm[k.strip()] = v.strip()
        raw = raw[m.end():]
    raw = raw.split('## 源稿核验记录')[0]          # 核验记录不渲染

    lines = raw.splitlines()
    sections, cur_name, cur_blocks = [], None, []
    i = 0
    def flush():
        nonlocal cur_name, cur_blocks
        if cur_name is not None:
            sections.append((cur_name, cur_blocks))
        cur_name, cur_blocks = None, []

    while i < len(lines):
        ln = lines[i]
        if ln.startswith('## '):
            flush(); cur_name = ln[3:].strip(); i += 1; continue
        if ln.startswith('# ') or re.match(r'^> \*\*SEO 摘要', ln) or not ln.strip():
            i += 1; continue
        # 表格块
        if ln.lstrip().startswith('|'):
            tbl = []
            while i < len(lines) and lines[i].lstrip().startswith('|'):
                cells = [c.strip() for c in lines[i].strip().strip('|').split('|')]
                if not re.match(r'^:?-{2,}', cells[0] if cells else ''):
                    tbl.append(cells)
                i += 1
            cur_blocks.append(('table', tbl)); continue
        # 引用块（可多行）
        if ln.startswith('>'):
            buf = []
            while i < len(lines) and lines[i].startswith('>'):
                buf.append(lines[i].lstrip('> ').strip()); i += 1
            cur_blocks.append(('note', ' '.join(b for b in buf if b))); continue
        # 无序列表
        if re.match(r'^- ', ln):
            items = []
            while i < len(lines) and re.match(r'^- ', lines[i]):
                items.append(lines[i][2:].strip()); i += 1
            cur_blocks.append(('ul', (items, None))); continue
        # 编号列表
        if re.match(r'^\d+\. ', ln):
            items, nums = [], []
            while i < len(lines) and re.match(r'^\d+\. ', lines[i]):
                nums.append(re.match(r'^(\d+)\. ', lines[i]).group(1) + '.')
                items.append(re.sub(r'^\d+\. ', '', lines[i]).strip()); i += 1
            cur_blocks.append(('ul', (items, nums))); continue
        # FAQ 问答对（Q 行）
        qm = re.match(r'^\*\*(Q\d+[：:].+?)\*\*\s*$', ln)
        if qm:
            q = qm.group(1); i += 1
            ans = []
            while i < len(lines) and lines[i].strip() and not lines[i].startswith(('#', '|', '>')) \
                    and not re.match(r'^\*\*Q\d+', lines[i]):
                ans.append(lines[i].strip()); i += 1
            cur_blocks.append(('faq', (q, ' '.join(ans)))); continue
        # 普通段落（可跨行，到空行/结构行止）
        buf = [ln.strip()]
        i += 1
        while i < len(lines) and lines[i].strip() and not lines[i].startswith(('#', '|', '>', '- ')) \
                and not re.match(r'^\d+\. ', lines[i]) and not re.match(r'^\*\*Q\d+', lines[i]):
            buf.append(lines[i].strip()); i += 1
        cur_blocks.append(('p', ' '.join(buf)))
    flush()
    return fm, sections


def render(md_path, out, brand=None, dark=None):
    fm, sections = parse_md(md_path)
    unit = fm.get('单位', '')
    pal = None
    for key, v in PALETTES.items():
        if key in unit or key in fm.get('title', ''):
            pal = v; break
    if pal and not (brand and dark):
        brand, dark, bg, border, faq_bg, faq_border = pal
    else:
        brand = brand or '#333333'; dark = dark or '#111111'
        bg, border, faq_bg, faq_border = '#f5f5f5', '#dddddd', '#fafafa', '#e0e0e0'
        print(f'⚠️ VI 台账未命中「{unit}」，使用灰板（请核对色值）')
    L = Layout(brand, dark, bg, border, faq_bg, faq_border)

    h = [L.doc_open(f'<title>{fm.get("title", "")}</title>')]
    missing = list(MUST_SECTIONS)
    for name, blocks in sections:
        if name in missing: missing.remove(name)
        if name == '招聘信息不漏接':
            h.append(L.cta())          # md 该段文字仅占位，实体由 CTA 组件渲染
            continue
        h.append(L.sec_title(name))    # ⚠️ 段标题必须渲染（曾漏 → 全文无段标题）
        if name == '码上君划重点':
            intro, points = None, []
            for kind, data in blocks:
                if kind == 'p':
                    if intro is None and re.match(r'^\*\*第', data) is None:
                        intro = data
                    elif re.match(r'^\*\*第', data):
                        points.append(data)
                    else:
                        points.append(data) if intro is not None else None
            # 兜底：没有「第X」模式的，全部段落进卡
            if not points and intro is None:
                pts = [d for k, d in blocks if k == 'p']
                intro = pts[0] if pts else ''
                points = pts[1:]
            h.append(L.highlight_card('', inline(intro or ''),
                                       [inline(x) for x in points],
                                       numbers=[f'{i}.' for i in range(1, len(points) + 1)],
                                       pill_text=''))  # 段标题已是「码上君划重点」，卡内 pill 重复 → 不渲染
            continue
        if name == '招聘速览':
            # 速览四格：md 表（表头行 + 1 数据行 × 4 列）→ quad_grid[(值, 标签)×4]
            tbl = next((d for k, d in blocks if k == 'table'), None)
            if tbl and len(tbl) == 2 and len(tbl[0]) == 4:
                strip = lambda s: inline(re.sub(r'\*\*', '', s))
                cells = [(strip(v), strip(lab)) for lab, v in zip(tbl[0], tbl[1])]
                h.append(L.quad_grid(cells))
            else:
                h.append(L.p('⚠️ 速览段不是 2 行 × 4 列表，请检查源稿'))
            # 段内其余块（如「> 注：…」）照常渲染，只跳过已转四格的表
            for kind, data in blocks:
                if kind == 'note':
                    h.append(L.note(inline(data)))
                elif kind == 'p':
                    h.append(L.p(inline(data)))
            continue
        for kind, data in blocks:
            if kind == 'p':
                h.append(L.p(inline(data)))
            elif kind == 'note':
                h.append(L.note(inline(data)))
            elif kind == 'ul':
                items, nums = data
                h.append(L.ul([inline(x) for x in items], numbers=nums))
            elif kind == 'faq':
                q, a = data
                h.append(L.faq(inline(q), inline(a)))
            elif kind == 'table':
                tbl = data
                ncol = max(len(r) for r in tbl)
                widths = [f'{100//ncol}%' for _ in range(ncol)]
                rows = [[inline(c) for c in r] + [''] * (ncol - len(r)) for r in tbl[1:]]
                # 表头传纯文本列表（layout_kit.table 内部自行 zip(headers, widths)）；
                # 传 (文本,宽) 元组会被 str 进 HTML（大丰稿实测事故）
                h.append(L.table([inline(c) for c in tbl[0]], rows, widths))
    if missing:
        print(f'⚠️ 缺段: {missing}')

    h += L.doc_close()
    html = '\n'.join(h)
    o, c = html.count('<section'), html.count('</section>')
    if o != c:   # 失败自动 dump，便于定位不配平点
        open('/tmp/gen_debug.html', 'w', encoding='utf-8').write(html)
        raise AssertionError(f'section 配平失败: {o}/{c}（已 dump /tmp/gen_debug.html）')
    assert html.count('招聘信息不漏接') == 1, 'CTA 重复'
    # 别家主题色检查：排除本稿自己的主色/深端（大小写不敏感）
    own = {brand.lower().lstrip('#'), dark.lower().lstrip('#')}
    all_known = {'0085d0','003876','007068','016e34','11509d','0d59a7','e10000',
                 '217050','009bb2','b20000','920303'}
    others = '|'.join(sorted(all_known - own))
    if others:
        hit = re.findall(rf"#(?:{others})", html, re.I)
        assert not hit, f'残留别家主题色: {set(h)}'
    assert html.count('<th ') == 0 and 'src="http' not in html
    html = re.sub(r'(?<=>)(?=<)', chr(10), html)
    # 正文顶部首个段标题 margin-top 清零（微信不折叠 margin，24px 会形成标题下空白行）
    html = html.replace('margin:24px 0 12px', 'margin:0 0 12px', 1)
    open(out, 'w', encoding='utf-8').write(html)
    print(f'OK {out}\n色板 {brand}/{dark} ｜ section {o}/{c} ｜ <strong> {html.count("<strong>")}')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('md')
    ap.add_argument('--out', required=True)
    ap.add_argument('--brand'); ap.add_argument('--dark')
    a = ap.parse_args()
    render(a.md, a.out, a.brand, a.dark)
