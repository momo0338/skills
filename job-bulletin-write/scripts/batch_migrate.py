#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""batch_migrate.py · 把 scripts/cfg_*.py 全量迁移成 scripts/data/*.json。

流程：
  1. 逐篇 import py cfg，用 gen_bulletin.build 生成基线 HTML；
  2. cfg2json.convert → JSON；bulletin_spec 读回来再 build；
  3. 字节级比对，一致才落盘到 scripts/data/<file_stem>.json；
  4. 汇总报告：OK / MISMATCH / IMPORT_FAIL（缺外部数据）。

用法：
  python3 batch_migrate.py            # dry-run，只报告不落盘
  python3 batch_migrate.py --write    # 实际落盘
"""
import glob
import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bulletin_spec          # noqa: E402
import gen_bulletin           # noqa: E402
import cfg2json               # noqa: E402

DATA_DIR = os.path.join(HERE, 'data')


def load_cfg_module(path):
    spec = importlib.util.spec_from_file_location(
        'cfg_' + str(abs(hash(path))), path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def build_from_cfg(path):
    m = load_cfg_module(path)
    return '\n'.join(gen_bulletin.build(m))


def build_from_json(jsonpath):
    s = bulletin_spec.load_spec(jsonpath)
    return '\n'.join(gen_bulletin.build(s))


def main():
    write = '--write' in sys.argv
    files = sorted(glob.glob(os.path.join(HERE, 'cfg_*.py')))
    ok, mismatch, import_fail = [], [], []

    for f in files:
        name = os.path.basename(f)[:-3]
        try:
            base = build_from_cfg(f)
        except Exception as e:
            import_fail.append((name, f'{type(e).__name__}: {str(e)[:80]}'))
            continue
        try:
            d = cfg2json.convert(f)
            if not d.get('file_stem'):
                d['file_stem'] = name.replace('cfg_', '', 1)
            outpath = os.path.join('/tmp', name + '.json')
            json.dump(d, open(outpath, 'w'), ensure_ascii=False)
            got = build_from_json(outpath)
            if got == base:
                ok.append((name, d, outpath))
            else:
                mismatch.append((name, len(base.encode()), len(got.encode())))
        except Exception as e:
            mismatch.append((name, 'EXC', f'{type(e).__name__}: {str(e)[:80]}'))

    print(f'=== 全量迁移 {"(WRITE)" if write else "(dry-run)"} ===')
    print(f'TOTAL {len(files)} | OK {len(ok)} | MISMATCH {len(mismatch)} | IMPORT_FAIL {len(import_fail)}')

    if write and ok:
        os.makedirs(DATA_DIR, exist_ok=True)
        for name, d, src in ok:
            dst = os.path.join(DATA_DIR, d['file_stem'] + '.json')
            json.dump(d, open(dst, 'w'), ensure_ascii=False, indent=2)
        print(f'已落盘 {len(ok)} 篇 → {DATA_DIR}/')

    if mismatch:
        print('--- MISMATCH ---')
        for row in mismatch:
            print('  ', row)
    if import_fail:
        print('--- IMPORT_FAIL (缺外部数据，无法迁移) ---')
        for name, msg in import_fail:
            print('  ', name, msg)
    return 0 if not mismatch and not import_fail else 1


if __name__ == '__main__':
    sys.exit(main())
