#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bulletin-write · 官方公告重排生成器

用法:
    python3 gen_bulletin.py <config.py 路径>

config 模块须定义:
    OUT            排版 HTML 输出绝对路径
    TITLE          页面 <title>（同时用于断言）
    HIGHLIGHT      dict(sub=, intro=, items=[...], numbers=[...])
    GRID           [(大字, 小字), ×3]
    POSITION_TABLE dict(note=, headers=[...], rows=[[...]], widths=[...]) 或 None
    ORIGINAL       [(节标题|None, [("p"|"note"|"sub"|"url", 文本), ...]), ...]
    FAQ            [(问, 答), ...]
    DIGEST         ≤120 字手动摘要（gen 结束时打印，推送时复制到 --digest）

可选:
    SOURCE_NOTE    原文尾部小字（附件+落款+原文链接）
    BRAND / BRAND_DARK   品牌色覆盖（默认 B 线蓝；有主体官方 logo 时取众数色）
    ALLOWLIST      指纹词豁免清单（确需保留且原文确实无出处时，须在源稿「待核」登记）
    SOURCE_MD      同步产出的 -源稿.md 路径（三件套交付标准；不传则跳过）
    DATE / SOURCE_URL  源稿 frontmatter 用

内建断言: section 配平 / 禁空 span / 禁 div·th·position / 必含 <title> /
原文守恒（ORIGINAL 原样出现在成品）/
🔴 编造话术机检（指纹词命中增值件但不在公告原文=断言失败；吸收自 job-write §2.5）/
🔴 A 类自证句查杀 / 🔴 无据比较级查杀。
"""
import importlib.util
import re
import sys
import os

SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.expanduser('~/src/skills/mp-html/scripts'))
from layout_kit import Layout  # noqa: E402

# 默认 B 线蓝；config 里给 BRAND/BRAND_DARK 可按主体官方 logo 众数色覆盖
# （job-write §八：主色取 logo 有彩度像素众数色，同系列逐篇重取，禁沿用上一篇色板）
BRAND = '#1A4E93'
BRAND_DARK = '#123C6E'

# 🔴 编造话术指纹（吸收自 job-write §2.5，2026-09-28 三家运营商稿立规）：
# 这些词出现在增值件（划重点/三宫格/岗位表注脚/FAQ/来源小字）但**不在公告原文**里 = 编造嫌疑，
# 直接断言失败——要么把原文依据补进 ORIGINAL，要么从增值件删掉。
# ⚠️ 指纹不是禁用词表：官方原文真写了就是硬信息（在原文里→放行）。
FINGERPRINTS = [
    'CET-4', 'CET-6', '四级', '六级', '行测', '色盲', '色弱',
    'A类编制', 'A类正式编', '正式编制', '直签', '企业年金', '六险二金', '六险一金',
    '补充医疗', '食堂', '公寓', '班车', '落户', '租房补贴', '安家费',
    '雏鹰', '项目制承包', '劳务外包', '第三方派遣',
    '报录比', '竞争最小', '待遇最好', '全省唯一', '全国首家', '首创', '最多之一',
]
# A 类「自证句」指纹（job-write §八·补）：向读者解释编辑决策过程的句子，一律不许出现
SELF_REFERENCE = ['本文不做', '本文只给', '本文不写', '本文不再', '要说明白', '不再赘述', '此处不列']


def strip_bold(t: str) -> str:
    """去掉 <strong> 标签但保留内部文字——原文守恒校验用。"""
    return t.replace('<strong>', '').replace('</strong>', '')


def load_config(path: str):
    spec = importlib.util.spec_from_file_location('bulletin_cfg', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def build(cfg):
    brand = getattr(cfg, 'BRAND', BRAND)
    brand_dark = getattr(cfg, 'BRAND_DARK', BRAND_DARK)
    L = Layout(brand=brand, brand_dark=brand_dark, bg_light='#EAF1F9',
               border_light='#C5D5EA', faq_bg='#F7F8FA', faq_border='#E2E8F0')
    parts = [L.doc_open(f'<title>{cfg.TITLE}</title>')]

    # 1 划重点
    hl = cfg.HIGHLIGHT
    parts.append(L.highlight_card(hl['sub'], hl['intro'], hl['items'],
                                  numbers=hl.get('numbers')))

    # 2 三宫格
    parts.append(L.quad_grid(cfg.GRID))

    # 3 岗位表
    pt = getattr(cfg, 'POSITION_TABLE', None)
    if pt:
        parts.append(L.sec_title(pt.get('title', '招什么人：岗位表（官方附件提取）')))
        if pt.get('note'):
            parts.append(L.note(pt['note']))
        parts.append(L.table(pt['headers'], pt['rows'], pt['widths']))
        if pt.get('footnote'):
            parts.append(L.note(pt['footnote']))

    # 4 公告原文（一字不改）
    parts.append(L.sec_title(cfg.ORIGINAL_TITLE if hasattr(cfg, 'ORIGINAL_TITLE') else '公告原文'))
    for heading, blocks in cfg.ORIGINAL:
        if heading:
            parts.append(L.sec_title(heading))
        for kind, text in blocks:
            if kind == 'p':
                parts.append(L.p(text))
            elif kind == 'note':
                parts.append(L.note(text))
            elif kind == 'sub':
                parts.append(f'<p style="margin:12px 0 6px;font-size:15px;'
                             f'font-weight:800;color:{brand_dark};">{text}</p>')
            elif kind == 'url':
                parts.append(
                    '<section style="background:#E5EDF7;border:1px solid #C5D5EA;'
                    'border-radius:8px;padding:12px 14px;margin:0 0 10px;">'
                    f'<p style="margin:0 0 6px;font-size:14.5px;color:{brand};font-weight:800;">'
                    '报名网址（请手动复制到浏览器打开）</p>'
                    '<p style="margin:0;font-size:14.5px;font-weight:700;color:#333;'
                    'word-break:break-all;line-height:1.7;">' + text + '</p></section>')
            else:
                raise ValueError(f'未知块类型: {kind}')

    # 5 FAQ
    parts.append(L.sec_title('常见问答'))
    for q, a in cfg.FAQ:
        parts.append(L.faq(q, a))

    # 6 CTA + 收尾
    parts.append(L.cta())
    parts += L.doc_close()
    return parts


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    cfg = load_config(sys.argv[1])
    parts = build(cfg)
    html = '\n'.join(parts)

    # ── 断言（写盘前）──
    assert html.count('<section') == html.count('</section>'), 'section 配平失败'
    assert html.count('<th') == 0 and '<div' not in html and 'position:' not in html
    assert f'<title>{cfg.TITLE}</title>' in html, 'doc_open 须带 <title> 标签'
    assert html.count('招聘信息不漏接') == 1, 'CTA 重复或缺失'
    assert 'src="http' not in html, '外链图片（须 base64 内嵌）'
    assert cfg.DIGEST and len(strip_bold(cfg.DIGEST)) <= 120, 'DIGEST 缺失或超 120 字'

    # 原文守恒：strip_bold 后每段文本必须原样出现在成品（原文一字不改的机器校验）
    for heading, blocks in cfg.ORIGINAL:
        for kind, text in blocks:
            if kind in ('p', 'note', 'sub'):
                plain = strip_bold(text)
                if plain not in strip_bold(html):
                    raise AssertionError(f'原文守恒失败（一字不改被破坏）: {plain[:50]}…')

    # ── 🔴 编造话术机检（吸收自 job-write §2.5/§八·补，比它更狠：手里有原文全文可交叉）──
    # 增值件（划重点/三宫格/岗位表/FAQ/来源小字）是 AI 写的，是编造的唯一温床；
    # 原文区块是照抄的，天然干净。指纹词命中增值件、却不在原文 → 断言失败。
    ref_text = strip_bold('\n'.join(
        t for _, blocks in cfg.ORIGINAL for k, t in blocks if k in ('p', 'note', 'sub')))
    addi_parts = [cfg.TITLE, cfg.DIGEST,          # TITLE/DIGEST 也是 AI 写的，必须进机检
                  cfg.HIGHLIGHT['sub'], cfg.HIGHLIGHT['intro'], *cfg.HIGHLIGHT['items']]
    addi_parts += [f'{a} {b}' for a, b in cfg.GRID]
    if getattr(cfg, 'POSITION_TABLE', None):
        pt = cfg.POSITION_TABLE
        addi_parts += [pt.get('note', ''), pt.get('footnote', '') or '']
        addi_parts += [' '.join(map(str, r)) for r in pt['rows']]
    addi_parts += [f'{q} {a}' for q, a in cfg.FAQ]
    if getattr(cfg, 'SOURCE_NOTE', ''):
        addi_parts.append(cfg.SOURCE_NOTE)
    addi_text = strip_bold('\n'.join(addi_parts))
    allow = set(getattr(cfg, 'ALLOWLIST', []))
    bad = [w for w in FINGERPRINTS
           if w in addi_text and w not in ref_text and w not in allow]
    if bad:
        raise AssertionError(
            '⛔ 编造嫌疑：以下指纹词出现在增值件、但公告原文里没有（命中且无出处=编造）：\n  '
            + '、'.join(bad)
            + '\n  → 官方原文确实有：把该原文句子补进 ORIGINAL 对应节；确实要写：加进 config 的 ALLOWLIST 并在源稿「待核」登记')
    self_hit = [w for w in SELF_REFERENCE if w in addi_text]
    if self_hit:
        raise AssertionError(f'⛔ A 类自证句（向读者解释编辑决策过程）: {self_hit} —— 全删')

    # 比较级红线（job-write §七）：最高级/「之一」必须落成可核实排名
    for w in ['最多', '最大', '最好', '最全', '唯一']:
        if w in addi_text and w not in ref_text and w not in allow:
            raise AssertionError(f'⛔ 比较级「{w}」无实测数据支撑 —— 删掉或写成可核实的排名'
                                 f'（有原文依据也建议换成数值区间表述，如「可加3至10分」）')

    os.makedirs(os.path.dirname(cfg.OUT), exist_ok=True)
    with open(cfg.OUT, 'w', encoding='utf-8') as f:
        f.write(html)

    # 可选：同步产出一源稿.md（三件套交付标准；不传 SOURCE_MD 则跳过）
    src_md = getattr(cfg, 'SOURCE_MD', None)
    if src_md:
        write_source_md(cfg, src_md)

    # 重读校验
    chk = open(cfg.OUT, encoding='utf-8').read()
    for m in re.finditer(r'<span[^>]*>(.*?)</span>', chk, re.S):
        assert m.group(1).strip(), '存在空 span（微信会剥掉）'
    o, c = chk.count('<section'), chk.count('</section>')
    assert o == c, (o, c)
    print(f'OK {cfg.OUT}')
    if src_md:
        print(f'OK {src_md}')
    print(f'section {o}/{c} | 字节 {len(chk.encode())} | strong {chk.count("<strong>")}')
    print(f'DIGEST({len(strip_bold(cfg.DIGEST))}字，推送时复制到 --digest):')
    print(strip_bold(cfg.DIGEST))


def write_source_md(cfg, out_md: str):
    """从 config 生成 -源稿.md（三件套之一；frontmatter+SEO摘要行+骨架正文）。"""
    today = getattr(cfg, 'DATE', '')
    md = [f'---\ntitle: {cfg.TITLE}\ndate: {today}\ncategory: 招聘\nline: B\nsource: 原创\n',
          f'tags: [招聘, 事业单位, 公告重排]\nsource_url: {getattr(cfg, "SOURCE_URL", "")}\n---\n',
          f'\n# {cfg.TITLE}\n',
          f'\n> **SEO 摘要**（{len(strip_bold(cfg.DIGEST))}字，无 emoji）：{strip_bold(cfg.DIGEST)}\n']
    hl = cfg.HIGHLIGHT
    md.append(f'\n## 码上君划重点\n\n**{strip_bold(hl["intro"])}**\n')
    nums = hl.get('numbers') or [''] * len(hl['items'])
    for n, it in zip(nums, hl['items']):
        md.append(f'{n} {strip_bold(it)}\n')
    md.append('\n## 数据三宫格\n\n| ' + ' | '.join(a for a, _ in cfg.GRID)
              + ' |\n|' + '---|' * len(cfg.GRID) + '\n| '
              + ' | '.join(b for _, b in cfg.GRID) + ' |\n')
    pt = getattr(cfg, 'POSITION_TABLE', None)
    if pt:
        md.append(f'\n## {pt.get("title", "岗位表")}\n')
        if pt.get('note'):
            md.append(f'> {pt["note"]}\n')
        md.append('\n| ' + ' | '.join(pt['headers']) + ' |\n|' + '---|' * len(pt['headers']) + '\n')
        for r in pt['rows']:
            md.append('| ' + ' | '.join(strip_bold(str(c)) for c in r) + ' |\n')
        if pt.get('footnote'):
            md.append(f'\n{pt["footnote"]}\n')
    for heading, blocks in cfg.ORIGINAL:
        md.append(f'\n## {heading}\n' if heading else '\n')
        for kind, t in blocks:
            if kind == 'p':
                md.append(f'\n{strip_bold(t)}\n')
            elif kind == 'note':
                md.append(f'\n> {strip_bold(t)}\n')
            elif kind == 'sub':
                md.append(f'\n**{t}**\n')
            elif kind == 'url':
                md.append(f'\n{t}\n')
    md.append('\n## 常见问答\n')
    for q, a in cfg.FAQ:
        md.append(f'\n**{q}**\n{a}\n')
    if getattr(cfg, 'SOURCE_NOTE', ''):
        md.append(f'\n{cfg.SOURCE_NOTE}\n')
    with open(out_md, 'w', encoding='utf-8') as f:
        f.write(''.join(md))
    # 重读
    assert cfg.TITLE in open(out_md, encoding='utf-8').read()


if __name__ == '__main__':
    main()
