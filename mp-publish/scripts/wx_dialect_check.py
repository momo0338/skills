#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""微信公众号草稿正文方言校验器
基于「微信排版原生方言规范」逐条断言；返回违例清单（exit 0=全过，1=有违例）
用法: python wx_dialect_check.py <正文HTML文件路径>
"""
import re, sys
from bs4 import BeautifulSoup

PATTERNS = [
    ("a.href",       re.compile(r'<a\b[^>]*\bhref\s*=', re.I),    "正文 <a href> 链接会被微信剥光，链接改用文字或文末列出"),
    ("position:relative", re.compile(r'position\s*:\s*relative', re.I), "position:relative 会被微信从 style 里静默剥除（left/top 留下无意义），改用 flex / border 自绘布局"),
    ("position:absolute", re.compile(r'position\s*:\s*(absolute|fixed|sticky)', re.I), "position:absolute/fixed/sticky 会被微信静默剥除"),
    ("空 style 属性 style=\"\"", re.compile(r'style\s*=\s*""'), 'style="" 空属性一般是输入端 style 用了 &#39; 等实体或无效值导致整个属性被清空，逐元素排查'),
    ("class= 残留", re.compile(r'\sclass\s=', re.I), "class 属性体积冗余且无渲染作用（styles 已内联），建议删除（非阻断）"),
]

BLOCK_TAGS = {"p", "h1", "h2", "h3", "h4", "h5", "h6", "section", "div",
              "ul", "ol", "li", "table", "figure", "figcaption", "blockquote",
              "article", "aside", "header", "footer", "main", "nav", "img"}

def _div_block_child_count(content):
    """检测 div 是否包含块级子元素（包括嵌套层级）。"""
    try:
        soup = BeautifulSoup(content, "html.parser")
    except Exception:
        return 0
    count = 0
    for div in soup.find_all("div"):
        for child in div.children:
            if getattr(child, "name", None) in BLOCK_TAGS:
                count += 1
                break
    return count

def check(content):
    issues = []
    for name, pat, fix in PATTERNS:
        if name == "class= 残留":
            # 非阻断，单独列表
            extra = len(pat.findall(content))
            if extra:
                issues.append(("warn", name, f"出现 {extra} 次（建议清理）", fix))
            continue
        n = len(pat.findall(content))
        if n:
            issues.append(("fail", name, f"出现 {n} 次", fix))

    # 微信会把 <div> 溶解成 p/span 并丢样式；块级容器必须改用 <section>
    bad_divs = _div_block_child_count(content)
    if bad_divs:
        issues.append(("fail", "div 含块级子元素",
                       f"出现 {bad_divs} 个",
                       "<div> 含块级子元素会被微信溶解并丢样式，块级容器全部改用 <section>"))
    # 统计
    n_section = content.count("<section")
    n_p       = content.count("<p>")
    n_img     = content.count("<img")
    n_div     = content.count("<div")
    n_style   = content.count('style="')
    print(f"统计: section={n_section} p={n_p} img={n_img} div={n_div} style={n_style}")
    fails = [i for i in issues if i[0] == "fail"]
    warns = [i for i in issues if i[0] == "warn"]
    if fails:
        print(f"\n❌ 违例 {len(fails)} 条：")
        for sev, name, msg, fix in fails:
            print(f"  - [{name}] {msg}\n      修复：{fix}")
    if warns:
        print(f"\n⚠️  建议 {len(warns)} 条：")
        for sev, name, msg, fix in warns:
            print(f"  - [{name}] {msg}\n      修复：{fix}")
    if not fails:
        print("\n✅ 方言校验通过")
    return 1 if fails else 0

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python wx_dialect_check.py <content.html>")
        sys.exit(2)
    content = open(sys.argv[1], encoding="utf-8").read()
    sys.exit(check(content))