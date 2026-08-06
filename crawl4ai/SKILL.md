---
name: crawl4ai-fetcher
description: |
  使用 Crawl4AI（LLM 原生的开源爬虫框架）从任意网页提取干净的 Markdown 正文与结构化数据。
  核心能力：Playwright 无头浏览器完整渲染 JS 动态页面（SPA/懒加载/登录后内容）、内置 BM25/Pruning 内容过滤得到"Fit Markdown"、JSON CSS/XPath 结构化提取、多策略（Cosine/LLM）精准抽取、深度爬取与流式并发。
  与 scrapling-fetcher（轻量双模式）形成互补：需要执行复杂 JS、按主题过滤正文、抽取结构化字段时优先使用本技能。
  触发词：crawl4ai、动态网页提取、JS渲染页面、SPA提取、内容过滤提取、Fit Markdown、结构化提取、LLM网页爬取、网页转markdown。
version: 1.0.0
---

# Crawl4AI Fetcher — LLM 原生网页提取 Skill

> 基于 [Crawl4AI](https://github.com/unclecode/crawl4ai)（Apache 2.0，专为 LLM 设计的网页爬取框架），将网页转化为 LLM 友好的 Markdown 与结构化数据。

## Overview

Crawl4AI 是当前最活跃的 LLM 原生爬虫框架之一（v0.9.x，1.5k+ commits），基于 Playwright 实现真实浏览器渲染，内置多种内容过滤与提取策略。相比静态 HTTP 抓取（scrapling Fast 模式 / trafilatura / BeautifulSoup），它能完整执行 JavaScript，处理 SPA、懒加载、反爬重页面；相比纯云端服务（jina-reader），它支持本地自定义提取策略、结构化字段抽取与大规模并发。

## 安装依赖 / Installation

```bash
pip install crawl4ai
crawl4ai-setup          # 初始化 Playwright 浏览器依赖（首次必须）
```

> - 需 Python >= 3.10
> - 排错可用 `crawl4ai-doctor` 诊断环境
> - 高级特性（Torch 聚类 / Transformers 摘要）按需安装 `crawl4ai[torch]` / `crawl4ai[transformer]`，体积大，默认不装

## 快速开始

### 1. 基础提取（自动渲染 + 输出干净 Markdown）

```python
import asyncio
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig

async def main():
    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(
            url="https://example.com/article",
            config=CrawlerRunConfig()
        )
        print(result.markdown[:3000])

asyncio.run(main())
```

### 2. 主题内容过滤（BM25 提取"Fit Markdown"）

按用户主题过滤噪音，只保留与主题相关的正文段落：

```python
import asyncio
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator
from crawl4ai.content_filter_strategy import BM25ContentFilter

async def main():
    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(
            url="https://example.com/docs",
            config=CrawlerRunConfig(markdown_generator=DefaultMarkdownGenerator(
                content_filter=BM25ContentFilter(user_query="如何配置代理", bm25_threshold=1.0)
            ))
        )
        print(result.markdown.fit_markdown)  # 过滤后的精准内容

asyncio.run(main())
```

### 3. 等待动态内容 / 执行 JS 后提取

```python
import asyncio
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig

async def main():
    browser = BrowserConfig(headless=True, viewport_width=1440, viewport_height=900)
    config = CrawlerRunConfig(
        wait_for="css:.article-content",   # 等待选择器出现
        delay_before_return_html=2.0,      # 额外等待秒数
        js_code="window.scrollTo(0, document.body.scrollHeight)",  # 触发懒加载
    )
    async with AsyncWebCrawler(config=browser) as crawler:
        result = await crawler.arun(url="https://example.com/spa", config=config)
        print(result.markdown)

asyncio.run(main())
```

### 4. 结构化字段抽取（JSON CSS 策略）

```python
import asyncio, json
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig
from crawl4ai.extraction_strategy import JsonCssExtractionStrategy

schema = {
    "name": "商品",
    "baseSelector": "div.product",
    "fields": [
        {"name": "标题", "selector": "h2.title", "type": "text"},
        {"name": "价格", "selector": "span.price", "type": "text"},
        {"name": "链接", "selector": "a", "type": "attribute", "attribute": "href"},
    ],
}

async def main():
    strategy = JsonCssExtractionStrategy(schema)
    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(
            url="https://example.com/products",
            config=CrawlerRunConfig(extraction_strategy=strategy)
        )
        print(json.dumps(json.loads(result.extracted_content), ensure_ascii=False, indent=2))

asyncio.run(main())
```

## 一键命令行封装

仓库内置 `scripts/fetch.py`，无需写代码即可提取：

```bash
# 基础提取（渲染 + Markdown 输出）
python3 <SKILL_DIR>/scripts/fetch.py "https://example.com/article"

# 按主题过滤正文（Fit Markdown）
python3 <SKILL_DIR>/scripts/fetch.py "https://example.com/article" --query "如何配置代理"

# 指定 CSS 选择器定向提取
python3 <SKILL_DIR>/scripts/fetch.py "https://example.com/article" --selector "article"

# JSON 结构化输出（含 title/markdown/fit_markdown/links）
python3 <SKILL_DIR>/scripts/fetch.py "https://example.com/article" --json

# 限制输出字符数
python3 <SKILL_DIR>/scripts/fetch.py "https://example.com/article" --max-chars 8000
```

## 技能分工建议（网页正文提取四件套）

| 技能 | 特点 | 首选场景 |
|------|------|---------|
| **crawl4ai-fetcher** | 完整浏览器渲染 + 智能过滤 + 结构化提取 | SPA/JS 重页面、按主题过滤、抽取结构化字段、复杂动态页 |
| **scrapling-fetcher** | Fast 极速 + Stealth 无头，轻量双模式 | 微信公众号/知乎/掘金等国内平台正文（自带选择器库） |
| **jina-reader** | 云端零依赖，~1-2s | 公开国际博客/文档/GitHub 快速读取 |
| **defuddle** | Node CLI 去杂提取 | 标准静态网页快速省 Token 提取 |

## 关键支持与故障排查

1. **首次安装必须执行 `crawl4ai-setup`**，否则报浏览器缺失；报错时运行 `crawl4ai-doctor` 按提示修复（Linux 常见缺 libnss3 等系统库）。
2. **动态页面提取不到内容**：加 `wait_for="css:..."` 或 `delay_before_return_html`；懒加载页面用 `js_code` 滚动触发。
3. **过滤效果差**：调低 `BM25ContentFilter` 的 `bm25_threshold`（默认 1.0，越小保留越多）。
4. **结构化抽取为空**：检查 `baseSelector`/字段 selector 是否匹配实际 DOM（可用浏览器 DevTools 验证）。
5. **性能**：单次启动浏览器约 2-5s，批量抓取建议复用同一个 `AsyncWebCrawler` 实例或使用 `arun_many` / Dispatcher 流式并发。
6. **强反爬站点**：实测知乎返回 403、少数派等待超时——国内强风控平台（微信/知乎/少数派等）建议优先使用 scrapling-fetcher（自带针对性的选择器与 Stealth 模式）；crawl4ai 更适合公开站、文档站、SPA 与结构化抽取。
7. **协议**：Apache 2.0，可自由商用；遵守目标网站 robots 与服务条款。
