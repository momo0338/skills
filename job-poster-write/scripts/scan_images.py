#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scan_images.py — 图片清单 + OCR 摸底（用于决定「哪几张值得精读」）

背景（2026-11-10 定）：
  当天中工国际篇 12 张图读了 8 张，其中 img_10（slogan）、img_11（END）、
  img_08（三格图，OCR 基本准）属于「不读也行」，白花 3 轮往返（约 30s）。
  先跑本脚本拿到每张图的规模与首行，就能只对表格/岗位类图精读。

用法：
  python3 scan_images.py /tmp/wxwork_r38            # 扫 images/ 下全部图
  python3 scan_images.py /tmp/wxwork_r38 --ocr      # 附带 OCR 首行（慢约 0.25s/张）

输出：idx / 尺寸 / 高 / OCR 行数 / 首行文字，并按「是否值得精读」分组。
零 Token：OCR 走 macOS Vision（vision_ocr.swift），不经过大模型。
"""
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
OCR_SWIFT = os.path.join(HERE, 'vision_ocr.swift')

# 出现这些词基本说明是「有硬信息的表/段落」，值得精读
TABLE_HINTS = ('岗位', '专业', '学历', '人数', '截止', '报名', '要求', '条件',
               '薪酬', '福利', '流程', '联系', '地址', '邮箱', '招聘', '计划')


def dims(path):
    try:
        from PIL import Image
        im = Image.open(path)
        return im.size
    except Exception:
        return (0, 0)


def ocr_lines(path):
    """返回 (行数, 首行文本)；失败返回 (0, '')"""
    try:
        out = subprocess.run(['swift', OCR_SWIFT, path, '--json'],
                             capture_output=True, text=True, timeout=60)
        d = json.loads(out.stdout or '{}')
        lines = d.get('lines') or []
        first = lines[0]['text'] if lines else ''
        return len(lines), first
    except Exception:
        return 0, ''


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    work = sys.argv[1]
    do_ocr = '--ocr' in sys.argv
    img_dir = os.path.join(work, 'images')
    if not os.path.isdir(img_dir):
        sys.exit(f'找不到图片目录: {img_dir}')

    files = sorted(f for f in os.listdir(img_dir)
                   if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')))
    if not files:
        sys.exit('图片目录为空')

    rows = []
    for f in files:
        p = os.path.join(img_dir, f)
        w, h = dims(p)
        n, first = ocr_lines(p) if do_ocr else (0, '')
        rows.append((f, w, h, n, first))

    print(f'[图片摸底] {work} | 共 {len(rows)} 张' + ('（含 OCR）' if do_ocr else '（未跑 OCR，加 --ocr）'))
    print(f'{"文件":12s} {"尺寸":12s} {"高":>5s} {"行数":>4s}  首行')
    hot, cold = [], []
    for f, w, h, n, first in rows:
        print(f'{f:12s} {f"{w}x{h}":12s} {h:5d} {n:4d}  {first[:40]}')
        if not do_ocr:
            continue
        if n >= 6 and any(k in first for k in TABLE_HINTS):
            hot.append(f)
        elif n >= 10:
            hot.append(f)
        elif n <= 2:
            cold.append(f)

    if do_ocr:
        print()
        if hot:
            print(f'→ 建议精读（{len(hot)} 张）: ' + '、'.join(hot))
        if cold:
            print(f'→ 可跳过（{len(cold)} 张，几乎无文字）: ' + '、'.join(cold))
        rest = [f for f, *_ in rows if f not in hot and f not in cold]
        if rest:
            print(f'→ 酌情（{len(rest)} 张）: ' + '、'.join(rest))
        print('提示：OCR 对图形化表格会串行错乱，表格类图仍需 ViewImage 逐字核；'
              '本表只用来筛掉纯装饰/slogan 图。')


if __name__ == '__main__':
    main()
