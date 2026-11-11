#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""cfg2json.py · 把老的 cfg_*.py 稿件配置转成纯数据 JSON（bulletin_spec 消费）。

用途：批量迁移历史 py cfg → data/*.json，让新稿不再粘贴 30 行样板。
转换后必须用 verify 做「字节级等价」校验（见 batch_migrate.py）。

表格处理策略：
  · py 里 `XXX = _L.table(headers, rows, widths)` 生成的字符串，若能在 AST 里
    找到对应的纯字面量调用 → 转成结构化 {headers, rows, widths}（体积小、可编辑）；
  · 找不到（动态生成、或来自 org_sections_ctg 等外部模块）→ 退化为内联 {__html__} 字符串。
两种形态 bulletin_spec 都能渲染，且与 py 内联字节等价。
"""
import importlib.util
import json
import os
import sys
import ast


def load(path):
    spec = importlib.util.spec_from_file_location('cfg_' + str(abs(hash(path))), path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _structured_tables_from_ast(path):
    """从 py 源码解析 `NAME = _L.table(headers, rows, widths)` 纯字面量调用。

    返回 {NAME: {headers, rows, widths}}；非纯字面量（含变量/函数调用）的跳过。
    """
    out = {}
    try:
        src = open(path, encoding='utf-8').read()
        tree = ast.parse(src)
    except Exception:
        return out
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Assign) and len(node.targets) == 1):
            continue
        tgt = node.targets[0]
        if not isinstance(tgt, ast.Name):
            continue
        val = node.value
        # 形如 _L.table(...) 或 .table(...)
        if not (isinstance(val, ast.Call) and isinstance(val.func, ast.Attribute)
                and val.func.attr == 'table' and len(val.args) >= 3):
            continue
        try:
            headers = ast.literal_eval(val.args[0])
            rows = ast.literal_eval(val.args[1])
            widths = ast.literal_eval(val.args[2])
        except (ValueError, SyntaxError):
            continue  # 非纯字面量，跳过（走 __html__ 退化）
        out[tgt.id] = {'headers': headers, 'rows': rows, 'widths': widths}
    return out


def _tables_in_namespace(m):
    """收集 py 模块里所有 Layout.table 生成的 HTML 字符串 -> 变量名映射。"""
    out = {}
    for name in dir(m):
        v = getattr(m, name)
        if isinstance(v, str) and v.startswith('<section') and '<table' in v:
            out.setdefault(v, name)  # 保留首个
    return out


def _register_table(ref, html, layouts, ast_tables):
    """把表格注册进 layouts：**默认 __html__ 内联（字节级零风险）**。

    注：早期尝试用 AST 抽取 headers/rows/widths 再经 L.table 重新渲染，但
    部分 cfg 用了**不同主题色的独立 Layout 实例**（如中国烟草的 BG_TABLE 斑马纹
    是 #F2F7FD 而非主 Layout 的 #f0f7f5），重新渲染会改变字节。为绝对安全，
    一律内联原 HTML；结构化提取仅在确认同主题时手动启用。
    """
    if ref in layouts:
        return
    layouts[ref] = {'__html__': html}


def _blocks_to_json(blocks, table_map, layouts, ast_tables):
    res = []
    for k, t in blocks:
        if k == 'raw':
            if isinstance(t, str) and t in table_map:
                ref = table_map[t]
                _register_table(ref, t, layouts, ast_tables)
                res.append([k, {'layout_table_ref': ref}])
            elif isinstance(t, str):
                res.append([k, {'raw_html': t}])
            else:
                res.append([k, t])
        else:
            res.append([k, t])
    return res


def _pt_to_json(pt, table_map, layouts, ast_tables):
    """POSITION_TABLE 是 dict 或 None，原样保留；若其 rows 是模板字符串则不动。"""
    if pt is None:
        return None
    return dict(pt)


def convert(path, ws_override=None):
    m = load(path)
    ast_tables = _structured_tables_from_ast(path)
    table_map = _tables_in_namespace(m)
    layouts = {}

    d = {
        '_ws': ws_override if ws_override is not None else getattr(m, 'WS', ''),
        '_notes': (m.__doc__ or '').strip(),
        'file_stem': '',
        'date': getattr(m, 'DATE', ''),
        'source_url': getattr(m, 'SOURCE_URL', ''),
        'title': m.TITLE,
        'digest': m.DIGEST,
        'highlight': m.HIGHLIGHT,
        'grid': [list(x) for x in m.GRID],
        'brand': getattr(m, 'BRAND', None),
        'brand_dark': getattr(m, 'BRAND_DARK', None),
    }
    if hasattr(m, 'ORIGINAL_TITLE'):
        d['original_title'] = m.ORIGINAL_TITLE

    d['position_table'] = _pt_to_json(getattr(m, 'POSITION_TABLE', None),
                                       table_map, layouts, ast_tables)
    extra = getattr(m, 'EXTRA_SECTIONS', [])
    d['extra_sections'] = [[h, _blocks_to_json(b, table_map, layouts, ast_tables)]
                           for h, b in extra]
    d['original'] = [[h, _blocks_to_json(b, table_map, layouts, ast_tables)]
                     for h, b in m.ORIGINAL]
    d['faq'] = [list(x) for x in m.FAQ]
    d['source_note'] = getattr(m, 'SOURCE_NOTE', '')
    d['allowlist'] = getattr(m, 'ALLOWLIST', [])
    if layouts:
        d['layouts'] = layouts

    out = getattr(m, 'OUT', '')
    base = os.path.basename(out)
    if base.endswith('-排版.html'):
        d['file_stem'] = base[:-len('-排版.html')]
    return d


if __name__ == '__main__':
    path = sys.argv[1]
    outjson = sys.argv[2] if len(sys.argv) > 2 else '/tmp/out.json'
    d = convert(path)
    json.dump(d, open(outjson, 'w'), ensure_ascii=False, indent=2)
    print('written', outjson, len(json.dumps(d, ensure_ascii=False).encode()), 'bytes')
