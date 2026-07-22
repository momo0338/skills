---
name: dy-cli
description: |
  专业的抖音 (Douyin/TikTok China) 命令行工具，支持搜索、无水印下载、热榜、点赞/评论/收藏互动、发布视频图文、直播录制与数据看板分析。
  核心优势：支持短索引（如 `dy search "AI"` 搜索后直接 `dy dl 1` 下载第 1 条，`dy like 1` 点赞）、格式化导出 (JSON/CSV/YAML)、多账号管理与发布排期。
  适用于抖音视频搜素、无水印视频/图文下载、热榜监控、自动发布与互动、创作者数据分析等场景。
  触发词：dy、dy-cli、抖音命令行、抖音搜素、抖音无水印下载、抖音发布视频、抖音热榜、抖音点赞评论。
version: 0.2.2
---

# dy-cli — 抖音全功能命令行 Skill

> 基于 [Youhai020616/douyin](https://github.com/Youhai020616/douyin) 开发，提供搜索、无水印下载、发布、互动、热榜、直播录制与数据分析一站式 CLI 操作。

## Overview

[dy-cli](https://github.com/Youhai020616/douyin) 是一个功能完备的抖音命令行工具。最大的亮点是支持**短索引流机制**（`dy search` 搜索后生成编号，后续操作直接使用 `dy read 1`、`dy dl 1`、`dy like 1`），大幅提升命令行操作效率。

## 安装与初始化 / Installation

```bash
# 1. pip 安装工具
pip install dy-cli

# 2. 检查版本
dy --version

# 3. 初始化配置与依赖检测
dy init

# 4. 扫码登录 (需要交互或无头浏览器支持)
dy login
```

## 常用命令速查

| 命令 | 别名 | 功能 | 示例 |
|------|------|------|------|
| `dy search` | `s` | 搜索抖音视频或用户 | `dy search "AI Agent 教程" --limit 10` |
| `dy download` | `dl` | 无水印下载视频/图文 | `dy dl <URL_or_index>` |
| `dy detail` | `read` | 查看视频详情 | `dy read 1` 或 `dy detail <URL>` |
| `dy trending` | `hot` | 查看实时抖音热榜 (Top 50) | `dy trending` |
| `dy like` | — | 点赞视频 | `dy like 1` |
| `dy favorite` | `fav` | 收藏视频 | `dy fav 1` |
| `dy comment` | — | 评论视频 | `dy comment 1 -c "讲得很清晰！"` |
| `dy comments` | — | 查看视频评论区 | `dy comments 1` |
| `dy follow` | — | 关注用户 | `dy follow <user_id>` |
| `dy publish` | `pub` | 发布视频或图文 | `dy publish -t "标题" -v video.mp4` |
| `dy live` | — | 直播流查看与录制 | `dy live <room_url>` |
| `dy analytics` | — | 创作者数据看板分析 | `dy analytics` |
| `dy status` | — | 查看当前登录状态 | `dy status` |
| `dy me` | — | 查看当前账号个人主页 | `dy me` |
| `dy account` | — | 多账号管理与切换 | `dy account list` |

---

## 核心工作流与短索引机制

`dy-cli` 内置了极便利的**短索引缓存**机制，上一条 `dy search` 产生的列表会缓存编号，后续指令直接传数字即可：

```bash
# 步骤 1：搜索关键词，生成序号 1, 2, 3...
dy search "美食教程"

# 步骤 2：查看第 1 个视频的详细文字与数据
dy read 1

# 步骤 3：直接无水印下载第 1 个视频
dy dl 1

# 步骤 4：给第 1 个视频点赞
dy like 1

# 步骤 5：发表评论
dy comment 1 -c "太赞了，今晚就试做！"
```

---

## 常用场景使用示例

### 1. 搜素与数据导出

```bash
# 搜索并导出 JSON 格式文件
dy search "大语言模型" -o results.json

# 按热度排序搜索
dy search "Python 爬虫" --sort most-liked
```

### 2. 无水印视频/图文下载

```bash
# 按短索引下载
dy dl 1

# 按 URL 直接下载
dy dl "https://www.douyin.com/video/7657851624437665070"

# 下载某个用户的全部公开作品
dy dl --user "https://www.douyin.com/user/MS4wLjABAAAA..."
```

### 3. 发布视频/图文

```bash
# 发布视频（设置标题、描述与标签）
dy publish -t "AI Agent 快速入门" -c "手把手带你搭建第一个智能体 #AI #Agent" -v agent.mp4

# 发布图文
dy publish -t "极简风摄影技巧" -c "用手机拍出大片感" --images img1.jpg,img2.jpg
```

### 4. 查看热榜

```bash
# 查看实时抖音热榜 Top 50
dy trending
```

---

## 故障排除与注意

- **`AUTH_REQUIRED` / 提示未登录**：运行 `dy login` 重新扫码登录，或检查 `dy status`。
- **需要 Chrome 环境**：某些搜索/互动/发布功能依赖 Playwright 无头浏览器，若提示缺失可运行 `playwright install chromium`。
