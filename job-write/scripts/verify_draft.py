#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify_draft.py —— 码上职业 / job-write 本地成稿三件套自动化质检门禁
用途：
    在写作完成、推送微信草稿箱前，执行本地闭环质量与合规检查：
    1. 源稿 (Markdown)：标题长度(≤64)、单行式 SEO 摘要字数(≤120且无emoji)、必要章节骨架
    2. 排版 (HTML)：桌面 677px 居中约束、调用 mp-html 官方方言检查器 (wx_dialect_check.py)
    3. 封面 (PNG)：尺寸必须为 900×383、色彩模式必须为 RGB (禁止 RGBA)

用法：
    python3 verify_draft.py <稿件前缀或任一文件路径>
    python3 verify_draft.py 事业单位招考/待发布/2026-09-18-南京市卫健委所属事业单位高层次338人
    python3 verify_draft.py --dir 事业单位招考/待发布/
"""
import argparse
import glob
import os
import re
import subprocess
import sys
from PIL import Image

DIALECT_CHECKER = "/Users/zhugx/src/skills/mp-html/scripts/wx_dialect_check.py"


def contains_emoji(text):
    for ch in text:
        cp = ord(ch)
        if (0x1F600 <= cp <= 0x1F64F or
            0x1F300 <= cp <= 0x1F5FF or
            0x1F680 <= cp <= 0x1F6FF or
            0x1F700 <= cp <= 0x1F77F or
            0x1F780 <= cp <= 0x1F7FF or
            0x1F800 <= cp <= 0x1F8FF or
            0x1F900 <= cp <= 0x1F9FF or
            0x1FA00 <= cp <= 0x1FA6F or
            0x1FA70 <= cp <= 0x1FAFF or
            0x2600 <= cp <= 0x26FF or
            0x2700 <= cp <= 0x27BF):
            return True
    return False


def verify_single(prefix):
    print(f"\n🔍 开始质检稿件：{os.path.basename(prefix)}")
    md_file = prefix + "-源稿.md"
    html_file = prefix + "-排版.html"
    cover_file = prefix + "-封面.png"

    errors = []
    warnings = []

    # 1. 检查源稿 Markdown
    if not os.path.exists(md_file):
        errors.append(f"缺少源稿文件：{md_file}")
    else:
        with open(md_file, "r", encoding="utf-8") as f:
            md_text = f.read()

        # 标题检查
        m_title = re.search(r"^#\s+(.+)$", md_text, re.MULTILINE)
        if not m_title:
            errors.append("源稿缺少一级标题 (# 标题)")
        else:
            title = m_title.group(1).strip()
            title_len = len(title)
            if title_len > 64:
                errors.append(f"标题超长：{title_len} 字符 (硬上限 ≤64)：{title}")
            else:
                print(f"  [1/3] 源稿标题：{title_len} 字符 (≤64) ✅")

        # SEO 摘要检查
        m_seo = re.search(r"^>\s+\*\*SEO\s*摘要\*\*[^：:]*[：:](.+)$", md_text, re.MULTILINE)
        if not m_seo:
            errors.append("源稿缺少单行式 SEO 摘要 (> **SEO 摘要**（NNN字，无 emoji）：<正文>)")
        else:
            digest = m_seo.group(1).strip()
            d_len = len(digest)
            if d_len > 120:
                errors.append(f"SEO 摘要超长：{d_len} 字符 (硬上限 ≤120)")
            elif contains_emoji(digest):
                errors.append("SEO 摘要包含 emoji 表情 (微信会渲染为豆腐块，禁止使用)")
            else:
                print(f"  [1/3] SEO 摘要：{d_len} 字符 (≤120, 无 emoji) ✅")

        # 关键段落检查
        must_keywords = ["码上君划重点", "数据三宫格", "怎么报名", "防骗提醒"]
        for kw in must_keywords:
            if kw not in md_text:
                warnings.append(f"源稿建议包含核心段落「{kw}」")

    # 2. 检查排版 HTML
    if not os.path.exists(html_file):
        errors.append(f"缺少排版 HTML 文件：{html_file}")
    else:
        with open(html_file, "r", encoding="utf-8") as f:
            html_text = f.read()

        # 居中约束
        if "max-width:677px" not in html_text and "max-width: 677px" not in html_text:
            warnings.append("排版 HTML 根容器建议显式声明 max-width:677px; margin:0 auto; 居中约束")
        else:
            print("  [2/3] 排版结构：桌面 677px 居中约束已就绪 ✅")

        # 调用 mp-html 官方方言检查器
        if not os.path.exists(DIALECT_CHECKER):
            errors.append(f"未找到 mp-html 方言检查脚本：{DIALECT_CHECKER}")
        else:
            p = subprocess.run(
                [sys.executable, DIALECT_CHECKER, html_file],
                capture_output=True,
                text=True
            )
            if p.returncode != 0:
                errors.append(f"微信原生方言校验未通过 (mp-html):\n{p.stdout}\n{p.stderr}")
            else:
                print("  [2/3] 方言合规：调用 mp-html/wx_dialect_check.py 校验全绿 ✅")

    # 3. 检查封面图
    if not os.path.exists(cover_file):
        errors.append(f"缺少封面图文件：{cover_file}")
    else:
        try:
            im = Image.open(cover_file)
            w, h = im.size
            if (w, h) != (900, 383):
                errors.append(f"封面尺寸错误：{w}×{h}，必须为 900×383")
            elif im.mode != "RGB":
                errors.append(f"封面色彩模式错误：{im.mode}，必须为 RGB (RGBA 模式在推草稿时会抛异常)")
            else:
                print(f"  [3/3] 封面规格：900×383 RGB 格式验证通过 ✅")
        except Exception as e:
            errors.append(f"无法读取封面图片：{e}")

    # 汇总输出
    if errors:
        print(f"❌ 质检失败 ({len(errors)} 项错误)：")
        for err in errors:
            print(f"   • {err}")
        return False
    if warnings:
        print(f"⚠️  提示建议 ({len(warnings)} 项)：")
        for w in warnings:
            print(f"   • {w}")

    print(f"🎉 交付三件套质检全绿！符合 job-write & mp-html 标准，可放心入库。")
    return True


def main():
    parser = argparse.ArgumentParser(description="job-write 本地成稿三件套质检门禁")
    parser.add_argument("target", nargs="?", default="", help="稿件前缀或任一文件路径")
    parser.add_argument("--dir", default="", help="扫描指定目录下的全部三件套")
    args = parser.parse_args()

    prefixes = []
    if args.dir:
        for f in glob.glob(os.path.join(args.dir, "*-源稿.md")):
            pref = f[:-len("-源稿.md")]
            prefixes.append(pref)
    elif args.target:
        p = args.target
        for sfx in ["-源稿.md", "-排版.html", "-封面.png"]:
            if p.endswith(sfx):
                p = p[:-len(sfx)]
                break
        prefixes.append(p)
    else:
        parser.print_help()
        sys.exit(2)

    if not prefixes:
        print("未找到需要质检的稿件。")
        sys.exit(1)

    all_ok = True
    for pref in prefixes:
        if not verify_single(pref):
            all_ok = False

    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
