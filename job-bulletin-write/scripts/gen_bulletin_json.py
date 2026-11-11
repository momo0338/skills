#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gen_bulletin_json.py · 用纯数据 JSON 出稿的薄封装。

完全复用 gen_bulletin.build()/main() 的全部断言与逻辑，只是把一个
JSON 数据文件先经 bulletin_spec.load_spec() 转成 cfg 对象再喂进去。

用法:
    python3 gen_bulletin_json.py <data.json 路径>

这样 gen_bulletin.py 一行都不用改；老 cfg_*.py 的 `python3 gen_bulletin.py <cfg>` 也照旧。
"""
import os
import sys

SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SKILL_DIR)

import gen_bulletin  # noqa: E402
import bulletin_spec  # noqa: E402


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    spec = bulletin_spec.load_spec(sys.argv[1])
    # 用 gen_bulletin 的原生流程：把 spec 当作 cfg 塞进它的断言/写盘逻辑。
    # gen_bulletin.main() 里固定读 sys.argv[1] 当 config 路径，所以这里复刻其主体：
    _run_with_spec(spec)


def _run_with_spec(cfg):
    """与 gen_bulletin.main() 完全相同的断言与写盘，只是 cfg 来自 JSON。"""
    import re
    parts = gen_bulletin.build(cfg)
    html = '\n'.join(parts)

    strip_bold = gen_bulletin.strip_bold

    # ── 断言（写盘前）── 与 gen_bulletin.main() 逐条对应 ──
    assert html.count('<section') == html.count('</section>'), 'section 配平失败'
    assert html.count('<th') == 0 and '<div' not in html and 'position:' not in html
    assert f'<title>{cfg.TITLE}</title>' in html, 'doc_open 须带 <title> 标签'
    assert html.count('招聘信息不漏接') == 1, 'CTA 重复或缺失'
    assert 'src="http' not in html, '外链图片（须 base64 内嵌）'
    assert cfg.DIGEST and len(strip_bold(cfg.DIGEST)) <= 120, 'DIGEST 缺失或超 120 字'

    for heading, blocks in cfg.ORIGINAL:
        for kind, text in blocks:
            if kind in ('p', 'note', 'sub'):
                plain = strip_bold(text)
                if plain not in strip_bold(html):
                    raise AssertionError(f'原文守恒失败（一字不改被破坏）: {plain[:50]}…')

    ref_text = strip_bold('\n'.join(
        t for _, blocks in cfg.ORIGINAL for k, t in blocks if k in ('p', 'note', 'sub')))
    ref_text += '\n' + re.sub(r'<[^>]+>', '', '\n'.join(
        t for _, blocks in cfg.ORIGINAL for k, t in blocks if k == 'raw'))
    addi_parts = [cfg.TITLE, cfg.DIGEST,
                  cfg.HIGHLIGHT['sub'], cfg.HIGHLIGHT['intro'], *cfg.HIGHLIGHT['items']]
    addi_parts += [f'{a} {b}' for a, b in cfg.GRID]
    if getattr(cfg, 'POSITION_TABLE', None):
        pt = cfg.POSITION_TABLE
        addi_parts += [pt.get('note', ''), pt.get('footnote', '') or '']
        addi_parts += [' '.join(map(str, r)) for r in pt['rows']]
    for _sec_title, _blocks in getattr(cfg, 'EXTRA_SECTIONS', []):
        if _sec_title:
            addi_parts.append(_sec_title)
        for _k, _t in _blocks:
            addi_parts.append(_t)
    addi_parts += [f'{q} {a}' for q, a in cfg.FAQ]
    if getattr(cfg, 'SOURCE_NOTE', ''):
        addi_parts.append(cfg.SOURCE_NOTE)
    addi_text = strip_bold('\n'.join(addi_parts))
    allow = set(getattr(cfg, 'ALLOWLIST', []))
    bad = [w for w in gen_bulletin.FINGERPRINTS
           if w in addi_text and w not in ref_text and w not in allow]
    if bad:
        raise AssertionError('⛔ 编造嫌疑：' + '、'.join(bad))
    self_hit = [w for w in gen_bulletin.SELF_REFERENCE if w in addi_text]
    if self_hit:
        raise AssertionError(f'⛔ A 类自证句: {self_hit} —— 全删')
    for w in ['最多', '最大', '最好', '最全', '唯一']:
        if w in addi_text and w not in ref_text and w not in allow:
            raise AssertionError(f'⛔ 比较级「{w}」无实测数据支撑')

    os.makedirs(os.path.dirname(cfg.OUT), exist_ok=True)
    with open(cfg.OUT, 'w', encoding='utf-8') as f:
        f.write(html)

    src_md = getattr(cfg, 'SOURCE_MD', None)
    if src_md:
        gen_bulletin.write_source_md(cfg, src_md)

    chk = open(cfg.OUT, encoding='utf-8').read()
    for m in re.finditer(r'<span[^>]*>(.*?)</span>', chk, re.S):
        assert m.group(1).strip(), '存在空 span（微信会剥掉）'
    o, c = chk.count('<section'), chk.count('</section>')
    assert o == c, (o, c)
    print(f'OK {cfg.OUT}')
    if src_md:
        print(f'OK {src_md}')
    print(f'section {o}/{c} | 字节 {len(chk.encode())} | strong {chk.count("<strong>")}')
    print(f'DIGEST({len(strip_bold(cfg.DIGEST))}字):')
    print(strip_bold(cfg.DIGEST))


if __name__ == '__main__':
    main()
