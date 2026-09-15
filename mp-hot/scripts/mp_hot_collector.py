#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
mp_hot_collector.py: 微信搜一搜热门文章数据收集与归档辅助脚本
"""

import sys
import json
import os

def format_markdown_report(keyword: str, items: list) -> str:
    lines = [
        f"# 微信搜一搜「{keyword}」最热公众号文章 Top {len(items)} 深度调研与原文归档",
        "",
        "- **检索渠道**：微信桌面端内置「搜一搜」",
        f"- **检索关键词**：{keyword}",
        "- **分类筛选**：文章",
        "- **排序方式**：最热",
        "",
        "---",
        "",
        "## 一、全量互动数据与微信官方直达链接对比表",
        "",
        "| 序号 | 文章标题 | 发布公众号 / 作者 | 发布时间 | 底部实测阅读量 | 点赞数 | 转发/分享 | 收藏数 | 评论数 | 微信官方标准文章链接 |",
        "| :---: | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |"
    ]
    
    for i, item in enumerate(items, 1):
        title = item.get("title", "")
        acc_author = f"{item.get('account', '')}（{item.get('author', '')}）" if item.get("author") else item.get("account", "")
        pub_date = item.get("publish_date", "")
        read_cnt = item.get("read_count", "-")
        like_cnt = item.get("like_count", 0)
        share_cnt = item.get("share_count", 0)
        collect_cnt = item.get("collect_count", 0)
        comment_cnt = item.get("comment_count", 0)
        url = item.get("mp_url", "")
        link_md = f"[{url}]({url})" if url.startswith("http") else url
        
        lines.append(f"| {i} | 《{title}》 | {acc_author} | {pub_date} | **{read_cnt}** | {like_cnt:,} | {share_cnt:,} | {collect_cnt:,} | {comment_cnt:,} | {link_md} |")
        
    lines.extend([
        "",
        "---",
        "",
        "## 二、各篇核心要点与原文摘录",
        ""
    ])
    
    for i, item in enumerate(items, 1):
        lines.extend([
            f"### {i}. 《{item.get('title', '')}》",
            f"- **发布账号**：{item.get('account', '')}",
            f"- **发布日期**：{item.get('publish_date', '')}",
            f"- **微信官方链接**：{item.get('mp_url', '')}",
            f"- **互动数据**：阅读 {item.get('read_count', '-')} ｜ 点赞 {item.get('like_count', 0)} ｜ 转发 {item.get('share_count', 0)} ｜ 收藏 {item.get('collect_count', 0)} ｜ 评论 {item.get('comment_count', 0)}",
            "- **原文核心要点**：",
            f"  > {item.get('core_summary', '')}",
            ""
        ])
        
    return "\n".join(lines)

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 mp_hot_collector.py <data.json> [output.md]")
        sys.exit(1)
        
    with open(sys.argv[1], 'r', encoding='utf-8') as f:
        payload = json.load(f)
        
    keyword = payload.get("keyword", "微信搜一搜")
    items = payload.get("items", [])
    
    md_content = format_markdown_report(keyword, items)
    
    if len(sys.argv) >= 3:
        out_path = sys.argv[2]
        os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(md_content)
        print(f"Report written to: {out_path}")
    else:
        print(md_content)

if __name__ == "__main__":
    main()
