#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
mp_search_formatter.py: 微信搜一搜文章与全维度互动数据格式化输出工具
"""

import sys
import json
import os

def format_markdown_table(keyword: str, rank_type: str, items: list, channel: str = None) -> str:
    is_opencli = (channel == "opencli") or (all(item.get("read_count") == "-" for item in items) if items else False)
    
    if is_opencli:
        channel_desc = "搜狗微信开放检索（opencli 降级通道，聚焦爆点切入与长尾选题）"
        notice_line = "> 💡 **降级通道提示**：当前通过搜狗开放接口检索，重点展示文章切入角度与摘要。端内私有数据（精确阅读/点赞）请使用通道 A（微信桌面端搜一搜）。"
    else:
        channel_desc = "微信客户端原生「搜一搜」（含端内互动指标）"
        notice_line = ""

    lines = [
        f"# 微信搜一搜「{keyword}」【{rank_type}】文章对标数据表",
        ""
    ]
    if notice_line:
        lines.extend([notice_line, ""])
        
    lines.extend([
        f"- **检索渠道**：{channel_desc}",
        f"- **检索关键词**：{keyword}",
        f"- **分类筛选**：文章",
        f"- **排序方式**：{rank_type}",
        f"- **采集条数**：Top {len(items)}",
        "",
        "---",
        ""
    ])
    
    if is_opencli:
        lines.extend([
            "| 序号 | 文章完整标题 | 发布公众号 | 发布时间 | 核心摘要 / 爆点切入 | 来源链接 |",
            "| :---: | :--- | :--- | :---: | :--- | :--- |"
        ])
        for i, item in enumerate(items, 1):
            title = item.get("title", "")
            account = item.get("account", "-")
            pub_date = item.get("publish_date", "-")
            summary = item.get("summary", "").replace("|", "/")
            url = item.get("mp_url", "")
            link_md = f"[查看原文]({url})" if url.startswith("http") else "-"
            lines.append(f"| {i} | 《{title}》 | {account} | {pub_date} | {summary[:60]} | {link_md} |")
    else:
        lines.extend([
            "| 序号 | 文章完整标题 | 发布公众号 | 发布时间 | 实测阅读量 | 点赞数 | 转发/分享数 | 收藏数 | 评论数 | 微信官方链接 |",
            "| :---: | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |"
        ])
        for i, item in enumerate(items, 1):
            title = item.get("title", "")
            account = item.get("account", "-")
            pub_date = item.get("publish_date", "-")
            read_cnt = item.get("read_count", "-")
            like_cnt = item.get("like_count", 0)
            share_cnt = item.get("share_count", 0)
            collect_cnt = item.get("collect_count", 0)
            comment_cnt = item.get("comment_count", 0)
            url = item.get("mp_url", "")
            link_md = f"[{url}]({url})" if url.startswith("https://mp.weixin.qq.com/s/") else (f"[查看链接]({url})" if url.startswith("http") else url)
            lines.append(f"| {i} | 《{title}》 | {account} | {pub_date} | **{read_cnt}** | {like_cnt:,} | {share_cnt:,} | {collect_cnt:,} | {comment_cnt:,} | {link_md} |")
        
    return "\n".join(lines)

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 mp_search_formatter.py <data.json> [output.md]")
        sys.exit(1)
        
    with open(sys.argv[1], 'r', encoding='utf-8') as f:
        payload = json.load(f)
        
    keyword = payload.get("keyword", "微信搜一搜")
    rank_type = payload.get("rank_type", "最热")
    items = payload.get("items", [])
    channel = payload.get("channel")
    
    md_content = format_markdown_table(keyword, rank_type, items, channel)
    
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

