#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""facts_len.py — 标题/摘要字数批量预检（零 Token）

背景（2026-11-10 定）：
  当天多篇稿子写摘要时都是「写一版 → 量 → 超了 → 压 → 再量」，
  单篇 3~4 轮往返（每轮约 10s）。本脚本一次量完所有候选，
  直接标出达标项，把这一步压到 1 轮。

用法：
  # 一次量多个摘要候选（每行一个）
  python3 facts_len.py --digest < cands.txt
  python3 facts_len.py --digest <<'EOF'
  候选一……
  候选二……
  EOF

  # 一次量多个标题候选
  python3 facts_len.py --title < cands.txt

  # 直接检查已有 facts.json 的 title / digest
  python3 facts_len.py --facts /tmp/wxwork_xxx/facts.json

口径（与 job_poster_pipeline.py 的 facts-check 一致）：
  title  ≤ 64 字符
  digest 目标 115~119 字，硬上限 120
"""
import json
import sys

TITLE_MAX = 64
DIGEST_HARD = 120
DIGEST_LO, DIGEST_HI = 115, 119


def judge(n, mode):
    if mode == 'title':
        if n <= TITLE_MAX:
            return f'✅ {n}/{TITLE_MAX}'
        return f'❌ {n}/{TITLE_MAX} 超 {n - TITLE_MAX}'
    if n > DIGEST_HARD:
        return f'❌ {n} 超硬限 {n - DIGEST_HARD}'
    if DIGEST_LO <= n <= DIGEST_HI:
        return f'✅ {n}（达标 {DIGEST_LO}~{DIGEST_HI}）'
    if n < DIGEST_LO:
        return f'⚠️  {n} 偏短，还可加 {DIGEST_LO - n}~{DIGEST_HI - n} 字'
    return f'⚠️  {n} 略超目标 {n - DIGEST_HI}（未破硬限）'


def main():
    argv = sys.argv[1:]
    if not argv:
        sys.exit(__doc__)
    if '--facts' in argv:
        path = argv[argv.index('--facts') + 1]
        f = json.load(open(path, encoding='utf-8'))
        for key, mode in (('title', 'title'), ('digest', 'digest')):
            v = f.get(key, '')
            print(f'{key:8s} {judge(len(v), mode)}  {v[:60]}')
        return
    mode = 'title' if '--title' in argv else 'digest'
    lines = [ln.rstrip('\n') for ln in sys.stdin if ln.strip()]
    if not lines:
        sys.exit('没有输入候选（每行一个）')
    ok = 0
    for i, ln in enumerate(lines, 1):
        s = judge(len(ln), mode)
        if s.startswith('✅'):
            ok += 1
        print(f'{i:2d}. [{mode}] {s}')
        print(f'    {ln}')
    print(f'\n共 {len(lines)} 个候选，达标 {ok} 个' +
          (f'，建议直接用第 {next(i for i, ln in enumerate(lines, 1) if judge(len(ln), mode).startswith("✅"))} 个' if ok else '，都需调整'))


if __name__ == '__main__':
    main()
