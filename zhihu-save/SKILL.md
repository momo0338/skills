---
name: zhihu-save
version: 1.0.2
description: Use when user provides a Zhihu article URL (zhuanlan.zhihu.com/p/xxx) and wants to save it to the vault. Automates download via opencli, category classification, frontmatter generation, and proper vault placement.
metadata: {"openclaw":{"emoji":"📥","requires":{"bins":["opencli"]}}}
---

# 知乎文章自动保存

## Overview

自动下载知乎文章并保存到 Obsidian vault 的正确分类目录，包含标准 frontmatter 和本地图片。

## When to Use

- 用户提供知乎文章链接：`https://zhuanlan.zhihu.com/p/xxx`
- 用户请求保存、收藏、下载知乎文章

## Workflow

```dot
digraph zhihu_save {
    "收到知乎链接" [shape=doublecircle];
    "下载文章" [shape=box];
    "读取内容判断分类" [shape=box];
    "生成frontmatter" [shape=box];
    "保存到分类目录" [shape=box];
    "验证保存成功" [shape=box];
    "完成" [shape=doublecircle];

    "收到知乎链接" -> "下载文章";
    "下载文章" -> "读取内容判断分类";
    "读取内容判断分类" -> "生成frontmatter";
    "生成frontmatter" -> "保存到分类目录";
    "保存到分类目录" -> "验证保存成功";
    "验证保存成功" -> "完成";
}
```

## Step 1: Download Article

```bash
opencli zhihu download --url "https://zhuanlan.zhihu.com/p/xxx" --output "/tmp/zhihu-article" --download-images true
```

Output creates directory with:
- `文章标题.md` - Markdown content
- `images/` - Downloaded images (if enabled)

## Step 2: Classify Article

Read article content to determine category:

| 内容关键词 | category | 存放目录 |
|-----------|----------|---------|
| AI、Claude Code、OpenClaw、Skills、Agent | `AI与编程` | `08-知识收藏/01-AI与编程/` |
| GitHub、API、爬虫、开发工具、编程 | `开发工具与项目` | `08-知识收藏/02-开发工具与项目/` |
| OpenClaw 相关 | `OpenClaw生态` | `08-知识收藏/03-OpenClaw生态/` |
| 技术趋势、架构方案 | `技术方案与趋势` | `08-知识收藏/04-技术方案与趋势/` |
| 运营、自媒体、增长 | `产品运营与自媒体` | `08-知识收藏/05-产品运营与自媒体/` |
| 股票、量化、金融、投资 | `投资与金融` | `08-知识收藏/06-投资与金融/` |
| 亲子、研学、生活 | `生活与亲子` | `08-知识收藏/07-生活与亲子/` |
| 历史、人文 | `历史人文` | `08-知识收藏/08-历史人文/` |
| 教育、学校 | `教育资讯` | `08-知识收藏/09-教育资讯/` |

## Step 3: Generate Frontmatter

```yaml
---
title: 文章标题
date: 当前日期 (YYYY-MM-DD)
category: 根据内容判断
source: 知乎
url: 原文链接
tags: [相关标签]
---
```

**注意：**
- 知乎作者字段可能为 `unknown`，如果无法获取则省略 author 字段
- Tags 使用文章中的关键词，最多 3-5 个

## Step 4: Save to Vault

1. Create directory: `08-知识收藏/{分类}/文章标题/`
2. Copy images to: `08-知识收藏/{分类}/文章标题/images/`
3. Write markdown with frontmatter

**Image path format:**
- 本地图片：`![描述](images/img_xxx.jpg)`
- 外部图片（未下载）：保留原 URL `![描述](https://picx.zhimg.com/xxx.jpg)`

## Step 5: Verify

- Check file exists
- Check images directory (if any)
- Report wikilink: `[[08-知识收藏/{分类}/文章标题/文章标题.md]]`

## Quick Reference

| 命令 | 用途 |
|------|------|
| `opencli zhihu download --url URL --output DIR --download-images true` | 下载文章 |
| `opencli zhihu hot` | 知乎热榜 |
| `opencli zhihu search <query>` | 知乎搜索 |
| `opencli zhihu question <id>` | 问题详情 |

## Common Mistakes

| 问题 | 解决方案 |
|------|---------|
| 权限错误 EACCES | 运行 `sudo chown -R $(whoami) ~/.opencli` |
| 作者显示 unknown | 知乎部分文章无法获取作者，省略 author 字段 |
| 图片未下载 | 确保 `--download-images true` 参数 |
| opencli 未安装 | `npm i -g @jackwener/opencli` |

## Example Output

```
✅ 文章已保存成功！

保存位置：[[08-知识收藏/02-开发工具与项目/Google Play APK下载教程/Google Play APK下载教程.md]]

**保存内容：**
- 📄 Markdown 文件（带标准 frontmatter）
- 🖼️ 7 张配图

**Frontmatter 信息：**
title: Google Play APK下载教程：无需谷歌三件套
date: 2026-04-17
category: 开发工具与项目
source: 知乎
url: https://zhuanlan.zhihu.com/p/2013662010991198799
tags: [Google Play, APK下载, Appteka, 应用商店]
```