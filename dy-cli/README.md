# dy-cli — 抖音全功能命令行 Skill

> **中文** · [English below](#english)

基于 [Youhai020616/douyin](https://github.com/Youhai020616/douyin) 开发的抖音 CLI 工具。支持搜索、无水印音视频/图文下载、热榜监控、点赞/评论/收藏互动、视频图文发布、直播录制与数据看板分析。

> Douyin (TikTok China) CLI skill supporting search, no-watermark download, trending topics, interaction, publishing, live recording, and analytics.

---

## 这是什么 / What is this

一个基于 `dy-cli` Python 包的抖音工具 Skill。让 AI 助手或用户能够通过命令行极速搜索抖音内容、无水印下载视频/图文、发布作品、查看实时热榜等。

### 核心亮点 / Highlights

- **短索引高效流**：`dy search` 搜索后直接用数字索引（`dy read 1`, `dy dl 1`, `dy like 1`）操作，无需复制长 URL
- **无水印下载**：一键下载高清视频与高清图文，支持单个视频或用户全量批量下载
- **作品发布**：支持命令行发布视频与图文，设置标题、话题标签、封面与定时排期
- **实时热榜**：一键获取抖音热搜榜单 Top 50
- **数据分析**：内置创作者看板与数据统计命令

---

## 快速开始 / Quick Start

### 1. 安装

```bash
pip install dy-cli
```

### 2. 初始化与登录

```bash
dy init
dy login
```

### 3. 基础体验

```bash
# 搜索视频
dy search "AI Agent 教程"

# 查看第 1 条搜索结果
dy read 1

# 下载第 1 条搜索结果 (无水印)
dy dl 1

# 给第 1 条点赞
dy like 1
```

---

## 命令清单 / Commands

| 命令 | 说明 |
|------|------|
| `dy search <query>` | 搜索视频或用户 |
| `dy download <url|index>` | 下载视频/图文（无水印） |
| `dy detail <url|index>` | 查看视频详情 |
| `dy trending` | 查看实时抖音热榜 Top 50 |
| `dy like <url|index>` | 点赞视频 |
| `dy favorite <url|index>` | 收藏视频 |
| `dy comment <url|index> -c "内容"` | 评论视频 |
| `dy comments <url|index>` | 查看评论区 |
| `dy publish -t "标题" -v video.mp4` | 发布视频 |
| `dy live <room_url>` | 直播流查看/录制 |
| `dy analytics` | 创作者数据看板 |
| `dy me` | 查看个人账号 |
| `dy status` | 查看登录状态 |

---

<a name="english"></a>

# dy-cli Skill — English

> Douyin CLI skill supporting search, no-watermark download, trending, publish, live, and analytics.

## Installation & Usage

```bash
pip install dy-cli
dy search "keyword"
dy dl 1
```
