#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bulletin-write · 「壳 / 数据」分离加载器（v1 试点）

背景：每个 cfg_*.py 是「一次真实公告重排任务的完整输入」，结构高度重复——
      头部 30 行样板（WS/OUT/SOURCE_MD 路径拼装、`from layout_kit import Layout`、
      `_ = Layout`）+ 11 个固定字段（TITLE/DIGEST/HIGHLIGHT/GRID/POSITION_TABLE/
      ORIGINAL/FAQ/SOURCE_NOTE/DATE/SOURCE_URL/BRAND）。

本模块把「壳」抽出来：给定一个纯数据 JSON（只放每篇各不相同的文本/表格数据），
自动补齐 WS/OUT/SOURCE_MD 路径、初始化 Layout、填充默认 BRAND，最后产出一个
与 `gen_bulletin.load_config()` 行为完全一致的对象（通过 getattr 访问的 SimpleNamespace），
所以 gen_bulletin.build()/main() 一行都不用改。

设计原则：
  · 零侵入：不改 gen_bulletin.py，不动任何既有 cfg_*.py（新壳只会被显式调用）。
  · 字节级等价：同一篇文章走 json 壳 vs 走 py cfg，build() 出的 HTML 必须逐字节相同。
  · 表对象兼容：cfg 里 `HQ_TABLE = _L.table(...)` 是「字符串」，JSON 里无法放 Python 对象；
    约定 JSON 用 `{"layout_table": {"headers": [...], "rows": [[...]], "widths": [...]}}`
    表示一个由 Layout 渲染的表格，加载时用同一 Layout 实例现场渲染成字符串。
  · docstring 核查履历：JSON 的 `_notes` 字段承载原 cfg 头部 docstring 的硬信息纪律，
    加载时原样挂到对象的 `__notes__`，不丢失。

用法（独立出稿，不改 gen_bulletin.py）：
    python3 gen_bulletin_json.py <data.json 路径>        # 见同目录薄封装

JSON 结构见同目录 data/_schema_example.json。
"""
import json
import os

# gen_bulletin 里的默认 B 线蓝，延迟导入避免循环
DEFAULT_BRAND = '#1A4E93'
DEFAULT_BRAND_DARK = '#123C6E'


class _Spec:
    """一个可被 gen_bulletin.build() getattr 消费的配置对象。"""

    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)

    def __repr__(self):
        return f"<BulletinSpec title={getattr(self, 'TITLE', '?')!r}>"


def _make_layout(brand, brand_dark):
    """构造与 gen_bulletin.build() 内完全同参的 Layout 实例。"""
    import sys
    sys.path.insert(0, os.path.expanduser('~/src/skills/mp-html/scripts'))
    from layout_kit import Layout
    return Layout(brand=brand, brand_dark=brand_dark, bg_light='#EAF1F9',
                  border_light='#C5D5EA', faq_bg='#F7F8FA', faq_border='#E2E8F0')


def _resolve_table(value, L):
    """把 JSON 里的表格占位渲染成 layout_kit 的 HTML 字符串。

    支持两种写法：
      · 已是字符串（py cfg 直接内联的情形）→ 原样返回；
      · {"layout_table": {headers, rows, widths}} → 用 L.table(...) 现场渲染。
    """
    if isinstance(value, str):
        return value
    if isinstance(value, dict) and 'layout_table' in value:
        t = value['layout_table']
        return L.table(t['headers'], t['rows'], t['widths'])
    if isinstance(value, dict) and 'raw_html' in value:
        return value['raw_html']
    raise ValueError(f'无法识别的表格占位: {type(value)}')


def _walk_blocks(blocks, L, layouts=None):
    """把 ORIGINAL / EXTRA_SECTIONS 里的 raw 块（可能是表格占位）渲染成字符串。

    其它块（p/note/sub/url/img）是纯文本，原样保留。
    layouts: {ref_name: {headers, rows, widths}}，raw 块里的 {'layout_table_ref': name}
             会在这里用 L.table(...) 现场渲染。
    """
    layouts = layouts or {}
    out = []
    for item in blocks:
        kind, text = item
        if kind == 'raw':
            if isinstance(text, dict) and 'layout_table_ref' in text:
                t = layouts[text['layout_table_ref']]
                if '__html__' in t:
                    # 转换器未结构化的表格：直接内联原 HTML（与 py 内联等价）
                    text = t['__html__']
                else:
                    text = L.table(t['headers'], t['rows'], t['widths'])
            else:
                text = _resolve_table(text, L)
        out.append((kind, text))
    return out


def load_spec(path: str, base_ws: str = None):
    """从 JSON 数据文件构造 gen_bulletin 可消费的 spec 对象。

    参数:
        path     数据 JSON 路径
        base_ws  输出根目录（默认取 JSON 里的 _ws，缺省用占位）
    """
    with open(path, encoding='utf-8') as f:
        d = json.load(f)

    brand = d.get('brand') or DEFAULT_BRAND
    brand_dark = d.get('brand_dark') or DEFAULT_BRAND_DARK
    L = _make_layout(brand, brand_dark)

    # ── 路径壳：WS + OUT + SOURCE_MD 自动拼 ──
    ws = base_ws or d.get('_ws') or ''
    stem = d.get('file_stem') or os.path.splitext(os.path.basename(path))[0]
    out = d.get('out') or (ws + stem + '-排版.html' if ws else None)
    source_md = d.get('source_md') or (ws + stem + '-源稿.md' if ws else None)

    # ── ORIGINAL / EXTRA_SECTIONS 里的 raw 表格占位现场渲染 ──
    layouts = d.get('layouts', {})
    original = [(_h, _walk_blocks(_b, L, layouts)) for _h, _b in d['original']]
    extra = [(_h, _walk_blocks(_b, L, layouts)) for _h, _b in d.get('extra_sections', [])]

    # ── POSITION_TABLE：dict 直传或 None；若含表格占位也渲染 ──
    pt = d.get('position_table')
    if pt is not None and isinstance(pt, dict):
        pt = dict(pt)
        pt['rows'] = pt.get('rows')  # rows 本就是 list[list[str]]

    kw = dict(
        OUT=out,
        SOURCE_MD=source_md,
        TITLE=d['title'],
        DIGEST=d['digest'],
        HIGHLIGHT=d['highlight'],
        GRID=[tuple(x) for x in d['grid']],
        POSITION_TABLE=pt,
        EXTRA_SECTIONS=extra,
        ORIGINAL=original,
        FAQ=[tuple(x) for x in d['faq']],
        SOURCE_NOTE=d.get('source_note', ''),
        DATE=d.get('date', ''),
        SOURCE_URL=d.get('source_url', ''),
        BRAND=brand,
        BRAND_DARK=brand_dark,
        ALLOWLIST=d.get('allowlist', []),
    )
    if 'original_title' in d:
        kw['ORIGINAL_TITLE'] = d['original_title']

    spec = _Spec(**kw)
    spec.__notes__ = d.get('_notes', '')
    return spec


# ── 允许 gen_bulletin.build() 原生消费：给它一个「字段全在」的对象即可 ──
if __name__ == '__main__':
    import sys
    p = sys.argv[1] if len(sys.argv) > 1 else 'data/_schema_example.json'
    s = load_spec(p)
    print(repr(s))
    for k in ('TITLE', 'DATE', 'SOURCE_URL', 'OUT'):
        print(f'{k} = {getattr(s, k)}')
