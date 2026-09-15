---
name: firecrawl-fetcher
description: |
  使用 Firecrawl（开源 LLM 原生全站爬虫与内容提取服务）进行单页抓取、全站深度递归 Crawl、站点地图 Map 发现与结构化抽取。
  核心优势：整站递归爬取（/crawl）、全站 URL 索引发现（/map）、智能绕过复杂反爬（Cloudflare/验证码等）、多格式输出（Markdown/HTML/LLM Schema 抽取）。
  支持官方云端 API（需 FIRECRAWL_API_KEY）或本地/私有化 Docker 部署实例（FIRECRAWL_BASE_URL）。
  触发词：firecrawl、全站爬取、整站抓取、站点地图发现、map发现URL、递归爬虫、firecrawl提取。
version: 1.0.0
---

# Firecrawl Fetcher — LLM 原生全站爬虫与内容抽取 Skill

> 基于 [Firecrawl](https://github.com/firecrawl/firecrawl)（开源爬虫服务），将整个网站或指定页面转化为 LLM 友好的 Markdown 与结构化数据。

## Overview

Firecrawl 专为 AI Agent 和 LLM 设计，不仅支持单页渲染与正文提取，最核心的能力是**全站递归爬取（Crawl）**与**站点结构索引发现（Map）**。能够自动处理 JavaScript 动态渲染、绕过反爬机制并输出干净的 Markdown 或按指定 JSON Schema 进行字段抽取。

支持两种运行模式：
1. **官方云端 API**：通过 [firecrawl.dev](https://firecrawl.dev) 获取 API Key（含免费额度）。
2. **私有化 Docker 部署**：通过本地或局域网 Docker 容器运行 Firecrawl，配置 `FIRECRAWL_BASE_URL`。

---

## 环境与配置 / Configuration

### 1. 环境变量配置

在环境或 `~/.codex/.env` 中设置：

```bash
# 官方云端服务（必需 API Key）
export FIRECRAWL_API_KEY="fc-YOUR_API_KEY"

# 私有化/本地 Docker 部署（可选，默认指向官方 https://api.firecrawl.dev）
export FIRECRAWL_BASE_URL="http://localhost:3002"
```

### 2. 依赖安装

本技能内置原生 HTTP 客户端，同时也支持安装官方 SDK：

```bash
pip install firecrawl-py requests
```

---

## 快速使用 (CLI 封装)

仓库内置 `scripts/fetch.py`，无需编写代码即可快速执行各类任务：

### 1. 单页抓取 (Scrape -> Markdown)

```bash
# 抓取网页主体并输出 Markdown
python3 <SKILL_DIR>/scripts/fetch.py scrape "https://example.com/article"

# 包含完整元数据与 JSON 输出
python3 <SKILL_DIR>/scripts/fetch.py scrape "https://example.com/article" --json

# 等待 JS 渲染额外毫秒数
python3 <SKILL_DIR>/scripts/fetch.py scrape "https://example.com/spa" --wait-for 2000
```

### 2. 发现全站 URL (Map)

用于在不爬取全部页面内容的情况下，瞬间发现目标站点下的所有关联 URL：

```bash
# 发现目标站点的所有 URL
python3 <SKILL_DIR>/scripts/fetch.py map "https://docs.example.com"

# 按关键词过滤 URL
python3 <SKILL_DIR>/scripts/fetch.py map "https://docs.example.com" --query "api" --limit 50
```

### 3. 全站深度递归爬取 (Crawl)

从起始 URL 递归抓取整个网站或子目录的所有页面并输出各页 Markdown：

```bash
# 递归抓取最多 10 个页面（最大深度 2）
python3 <SKILL_DIR>/scripts/fetch.py crawl "https://example.com/docs" --limit 10 --max-depth 2

# 输出为 JSON 数据格式
python3 <SKILL_DIR>/scripts/fetch.py crawl "https://example.com/blog" --limit 5 --json
```

### 4. 结构化字段抽取 (Extract)

利用 LLM 按指定 JSON Schema 自动从页面中抽取结构化对象：

```bash
python3 <SKILL_DIR>/scripts/fetch.py extract "https://example.com/product/123" \
  --schema '{"title": "string", "price": "number", "features": ["string"]}'
```

---

## Python SDK 调用示例

```python
import os
from firecrawl import FirecrawlApp

app = FirecrawlApp(
    api_key=os.environ.get("FIRECRAWL_API_KEY"),
    api_url=os.environ.get("FIRECRAWL_BASE_URL", "https://api.firecrawl.dev")
)

# 1. Scrape 单页
scrape_result = app.scrape_url("https://example.com", params={"formats": ["markdown"]})
print(scrape_result["markdown"])

# 2. Map 发现链接
map_result = app.map_url("https://example.com")
print(map_result["links"])

# 3. 递归 Crawl 全站
crawl_result = app.crawl_url(
    "https://example.com",
    params={"limit": 10, "scrapeOptions": {"formats": ["markdown"]}},
    poll_interval=3
)
print(f"共爬取 {len(crawl_result['data'])} 页")
```

---

## 网页正文提取与爬取技能矩阵对比

| 技能 | 运行形式 | 核心优势 | 首选场景 |
|------|---------|---------|---------|
| **firecrawl-fetcher** | 云端 API / Docker 服务 | **整站递归 Crawl、站点地图 Map 发现、全站 URL 索引** | 整站文档抓取、批量知识库入库、站点全景探测 |
| **crawl4ai-fetcher** | 本地 Python + Playwright | 免费无配额、SPA 深度执行、BM25 精准过滤 ("Fit Markdown") | 复杂 JS 单页/多页、按主题过滤正文、CSS/XPath 字段抽取 |
| **scrapling-fetcher** | 本地 Python 双模式 | 轻量极速、微信公众号/知乎/掘金等国内反爬选择器预置 | 国内高频资讯、公众号文章、防爬内容抓取 |
| **jina-reader** | 云端零依赖 API | `r.jina.ai` 秒级响应，无需 API Key | 公开技术博客、英文文档、GitHub 快速读取 |
| **defuddle** | 本地 Node CLI | 快速 DOM 去杂，省 Token 纯净输出 | 标准静态 HTML 页面快速净化 |

