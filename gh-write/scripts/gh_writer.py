#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
gh_writer.py: 结合 GitHub 深度数据与微信搜一搜双维度热度数据，自动化辅助生成公众号草稿
"""

import sys
import os
import json
import argparse
from datetime import datetime

VAULT_DRAFTS_DIR = "/Users/zhugx/codeup/obsidian/03-工作记录/满宝看未来/草稿"

def safe_num(v) -> str:
    """安全格式化数字，避免字符串类型触发格式化异常"""
    if v is None:
        return "-"
    if isinstance(v, int):
        return f"{v:,}"
    return str(v)

def format_wechat_table(hot_items: list, new_items: list) -> str:
    """生成最热与最新的微信搜一搜对比表格"""
    if not hot_items and not new_items:
        return "> *暂未检索到微信搜一搜公开收录推文，该项目当前在微信生态处于高潜蓝海阶段。*"
        
    lines = [
        "| 维度 | 序号 | 文章标题 | 公众号 | 发布时间 | 实测阅读量 | 点赞 | 转发 | 收藏 | 微信官方链接 |",
        "| :---: | :---: | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :--- |"
    ]
    
    for i, it in enumerate(hot_items[:5], 1):
        t = it.get("title", "")
        acc = it.get("account", "-")
        dt = it.get("publish_date", "-")
        rd = it.get("read_count", "-")
        lk = safe_num(it.get("like_count", 0))
        sh = safe_num(it.get("share_count", 0))
        cl = safe_num(it.get("collect_count", 0))
        url = it.get("mp_url", "")
        link_str = f"[查看原文]({url})" if url.startswith("http") else "-"
        lines.append(f"| **【最热】** | {i} | 《{t}》 | {acc} | {dt} | **{rd}** | {lk} | {sh} | {cl} | {link_str} |")
        
    for i, it in enumerate(new_items[:5], 1):
        t = it.get("title", "")
        acc = it.get("account", "-")
        dt = it.get("publish_date", "-")
        rd = it.get("read_count", "-")
        lk = safe_num(it.get("like_count", 0))
        sh = safe_num(it.get("share_count", 0))
        cl = safe_num(it.get("collect_count", 0))
        url = it.get("mp_url", "")
        link_str = f"[查看原文]({url})" if url.startswith("http") else "-"
        lines.append(f"| **【最新】** | {i} | 《{t}》 | {acc} | {dt} | **{rd}** | {lk} | {sh} | {cl} | {link_str} |")
        
    return "\n".join(lines)

def build_draft_content(gh: dict, hot_items: list, new_items: list, custom_title: str = None) -> str:
    name = gh.get("name", "开源项目")
    full_name = gh.get("full_name", name)
    stars = gh.get("stars", 0)
    forks = gh.get("forks", 0)
    stars_str = safe_num(stars)
    forks_str = safe_num(forks)
    license_type = gh.get("license") or "开源"
    primary_lang = gh.get("primary_language", "通用")
    desc = gh.get("description", "")
    topics = gh.get("topics", [])
    today = datetime.now().strftime("%Y-%m-%d")
    
    # 标题生成
    title = custom_title or f"GitHub 爆火 {stars_str}⭐ 神器「{name}」：彻底告别传统痛点，{primary_lang} 打造的极客生产力！"
    title_alt_1 = f"比商用软件好用10倍！开源神器 {name} 深度测评与本地部署避坑指南"
    title_alt_2 = f"终于有人把这个功能做完美了！GitHub {stars_str} 星的 {name} 究竟有多香？"
    title_alt_3 = f"告别臃肿与隐私顾虑！用 {name} 打造你的终极本地离线工作流"
    
    # 标签处理
    tags_list = ["GitHub推荐", f"开发工具/{primary_lang}", "开源项目"]
    if topics:
        tags_list.extend(topics[:3])
    tags_str = ", ".join(tags_list)
    
    # 徽标数据卡片（采用微信原生高兼容科技卡片 UI，带独立项目地址复制栏与开源协议）
    lang_display = f"{primary_lang} (" + ", ".join([f"{k} {v}" for k, v in gh.get('languages', {}).items()][:2]) + ")" if gh.get('languages') else primary_lang
    tag_name = gh.get('latest_release', {}).get('tag_name') or '滚动更新'
    pub_at = gh.get('latest_release', {}).get('published_at') or '持续活跃维护'
    repo_url = gh.get('html_url') or f"https://github.com/{full_name}"

    badge_table = f"""<div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:12px;padding:16px;margin:18px 0;box-shadow:0 1px 3px rgba(0,0,0,0.03);font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
    <div style="font-size:16px;font-weight:700;color:#0f172a;display:flex;align-items:center;gap:6px;">
      <svg style="width:18px;height:18px;fill:#1e293b;" viewBox="0 0 16 16"><path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"></path></svg>
      {full_name}
    </div>
    <span style="font-size:12px;background:#e2e8f0;color:#475569;padding:2px 8px;border-radius:12px;font-weight:600;">{license_type}</span>
  </div>

  <div style="background:#ffffff;border:1px solid #e2e8f0;border-radius:8px;padding:10px 12px;margin-bottom:12px;">
    <div style="font-size:11px;color:#64748b;margin-bottom:3px;font-weight:500;">🌐 项目开源地址（长按直接复制）：</div>
    <div style="font-size:13px;color:#0969da;font-family:ui-monospace,Menlo,Consolas,monospace;word-break:break-all;font-weight:600;line-height:1.4;">
      {repo_url}
    </div>
  </div>

  <div style="display:flex;gap:8px;margin-bottom:12px;">
    <div style="flex:1;background:#ffffff;border:1px solid #e2e8f0;border-radius:8px;padding:8px 4px;text-align:center;">
      <div style="font-size:11px;color:#64748b;">社区热度</div>
      <div style="font-size:14px;font-weight:700;color:#0f172a;margin-top:2px;">⭐ {stars_str}</div>
      <div style="font-size:10px;color:#94a3b8;margin-top:2px;">{forks_str} 🍴</div>
    </div>
    <div style="flex:1;background:#ffffff;border:1px solid #e2e8f0;border-radius:8px;padding:8px 4px;text-align:center;">
      <div style="font-size:11px;color:#64748b;">开源协议</div>
      <div style="font-size:14px;font-weight:700;color:#e11d48;margin-top:2px;">{license_type}</div>
      <div style="font-size:10px;color:#10b981;margin-top:2px;">自由开源商用</div>
    </div>
    <div style="flex:1;background:#ffffff;border:1px solid #e2e8f0;border-radius:8px;padding:8px 4px;text-align:center;">
      <div style="font-size:11px;color:#64748b;">核心语言</div>
      <div style="font-size:14px;font-weight:700;color:#0f172a;margin-top:2px;">{primary_lang}</div>
      <div style="font-size:10px;color:#94a3b8;margin-top:2px;">现代化架构</div>
    </div>
  </div>

  <div style="font-size:13px;color:#334155;line-height:1.8;margin-bottom:6px;">
    <div>📜 <strong>开源协议</strong>：<span style="background:#f1f5f9;color:#e11d48;padding:1px 5px;border-radius:4px;font-family:monospace;font-size:12px;">{license_type}</span> 协议（完全自由开源、代码可任意商用）</div>
    <div>🛠️ <strong>技术栈详情</strong>：{lang_display}</div>
    <div>🚀 <strong>最新版本</strong>：{tag_name} ({pub_at})</div>
  </div>

  <div style="border-top:1px dashed #cbd5e1;padding-top:8px;margin-top:6px;font-size:12px;color:#64748b;line-height:1.6;">
    💡 <strong>核心定位</strong>：{desc or '专为解决上述痛点打造的高性能开源利器'}
  </div>
</div>"""

    # 特性列表
    features = gh.get("readme_analysis", {}).get("features", [])
    f1_t = features[0] if len(features) > 0 else "极致轻量与本地优先架构"
    f2_t = features[1] if len(features) > 1 else "多维智能检索与高效组织"
    f3_t = features[2] if len(features) > 2 else "跨平台支持与开箱即用"
    
    # 搜一搜表格
    wechat_table = format_wechat_table(hot_items, new_items)
    
    # 安装命令
    install_guide = gh.get("readme_analysis", {}).get("install_guide") or f"git clone {gh.get('html_url')}\ncd {name}"

    draft = f"""---
title: {title}
date: {today}
category: 满宝看未来
source: 原创
status: draft
tags: [{tags_str}]
description: GitHub 爆款开源项目 {full_name} 深度推荐！斩获 {stars:,} Stars，基于 {primary_lang} 架构，为你彻底解决痛点。本文带来核心特性拆解、微信生态热度对比与本地极速部署实操指南。
github_repo: {full_name}
github_url: {gh.get('html_url')}
stars: {stars}
---

# {title}

> **备选爆款标题**：
> 1. 《{title_alt_1}》
> 2. 《{title_alt_2}》
> 3. 《{title_alt_3}》

## 痛点直击：为什么你需要关注这个开源神器？

在日常开发、办公与个人数字资产管理中，大家几乎都踩过这些典型痛点：
1. **商业软件越做越臃肿**：动辄几百 MB 内存占用、弹窗泛滥、后台常驻，甚至随时面临订阅涨价或功能砍单；
2. **云端存储的隐私顾虑**：敏感个人数据、私密代码或家庭媒体被上传至云端服务器，时常担心数据泄露与平台服务突然停运；
3. **性能与检索瓶颈**：当数据体量积累到数十万级时，传统工具卡顿明显，搜索更是犹如大海捞针。

**如果你也深受其扰，那么今天推荐的 GitHub 高分开源神器 —— `{name}`，正是为此而生！**

> **官方定位**：{desc or '专为解决上述痛点打造的高性能开源利器'}

## 项目名片：一眼看懂它的硬核实力

{badge_table}

## 三大杀手级核心特性深度剖析

### 1. {f1_t}
传统同类工具往往要求用户全面妥协，而 `{name}` 从架构底层即坚持了**本地优先（Local-First）**与数据主权自控的设计理念。所有核心运算与业务逻辑均在用户本地运行，不绑定任何强制云端服务。

### 2. {f2_t}
项目精心打磨了交互体验与操作性能。无论是数据检索、批量处理还是状态管理，都兼具极低资源开销与极速响应，即使面对庞大的数据集也能做到秒级反馈。

### 3. {f3_t}
完善的生态兼容性与模块化扩展设计。支持多端跨平台部署，社区提供了丰富的开箱即用预设，真正做到了“降低配置门槛，开箱即是生产力”。

## 微信生态观察：大家都在讨论它什么？

为了解国内微信技术圈对 `{name}` 的真实认知与反响，我们通过微信「搜一搜」对该项目的**【最热】爆款文章**与**【最新】时效文章**进行了双维度检索与全指标对比：

{wechat_table}

### 💡 读者高频共鸣与舆情洞察
- **最受追捧的卖点**：对比【最热】推文的数据可以看出，能够切中“免费可控”、“离线免订阅”、“隐私无忧”等角度的内容阅读量与转发量显著最高；
- **当下最新关注点**：在近期【最新】推文中，读者更多在讨论新版本的功能迭代、与周边生态工具的联动以及在群晖/NAS/本地服务器上的部署技巧；
- **本文差异化定位**：市面文章大多停留在粗浅的概念搬运，而本文重点给出实测环境验证、可复用的快速起步脚本与核心配置注意事项。

## 极速实操：5分钟本地部署与上手体验

### 1. 环境依赖准备
- 对应运行时环境（如 Node.js / Python / Docker 等）
- 本地终端与 Git 工具支持

### 2. 核心部署与运行命令
```bash
{install_guide}
```

### 3. 部署关键避坑提醒
- **端口与权限检查**：确保运行端口未被其他服务占用，本地存储目录具备读写权限；
- **网络镜像配置**：依赖拉取过程中建议配置国内镜像源以保障下载流畅；
- **定期备份机制**：因数据完全保存在本地磁盘，建议配置简单的 Cron 脚本定期冷备份关键数据。

## 总结与选型建议

- **强烈推荐给**：追求数据自主权、注重个人隐私、需要轻量高性能工具的极客、程序员与内容创作者；
- **暂不推荐给**：重度依赖商业云端协同、无任何本地部署动手能力的小白用户；
- **总体评价**：`{name}` 是近期 GitHub 上非常亮眼的诚意之作，无论在架构选型还是细节体验上都极具匠心，值得 Star 收藏并深度把玩！

*关注公众号「满宝看未来」，每周带你深度拆解一个真正能落地的 GitHub 宝藏开源项目！欢迎在评论区留下你希望我们测评的开源工具。*
"""
    return draft

def main():
    parser = argparse.ArgumentParser(description="公众号 GitHub 项目专栏采写助手")
    parser.add_argument("--gh-json", required=True, help="gh_research 生成的项目数据 JSON 路径")
    parser.add_argument("--hot-json", help="mp-search 生成的最热推文数据 JSON 路径")
    parser.add_argument("--new-json", help="mp-search 生成的最新推文数据 JSON 路径")
    parser.add_argument("--title", help="自定义文章主标题")
    parser.add_argument("--output", help="输出草稿路径，默认写入 03-工作记录/满宝看未来/草稿/")
    args = parser.parse_args()

    with open(args.gh_json, "r", encoding="utf-8") as f:
        gh_data = json.load(f)
        
    hot_items = []
    if args.hot_json and os.path.exists(args.hot_json):
        with open(args.hot_json, "r", encoding="utf-8") as f:
            hot_data = json.load(f)
            hot_items = hot_data.get("items", hot_data if isinstance(hot_data, list) else [])

    new_items = []
    if args.new_json and os.path.exists(args.new_json):
        with open(args.new_json, "r", encoding="utf-8") as f:
            new_data = json.load(f)
            new_items = new_data.get("items", new_data if isinstance(new_data, list) else [])

    draft_text = build_draft_content(gh_data, hot_items, new_items, args.title)
    
    repo_name = gh_data.get("name", "project")
    out_file = args.output
    if not out_file:
        os.makedirs(VAULT_DRAFTS_DIR, exist_ok=True)
        out_file = os.path.join(VAULT_DRAFTS_DIR, f"GitHub推荐-{repo_name}.md")
    else:
        out_dir = os.path.dirname(os.path.abspath(out_file))
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
        
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(draft_text)
        
    print(f"[✓] Draft successfully written to: {out_file}")

if __name__ == "__main__":
    main()
