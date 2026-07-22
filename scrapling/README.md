# Scrapling Content Fetcher Skill

> **中文** · [English below](#english)

基于 Python `scrapling` 和 `html2text` 的本地网页正文提取 Skill。能自动去除网页噪音，保留标题、链接、图片与代码块，并智能处理微信公众号、知乎等平台的 `data-src` 懒加载图片。

> Local web content extraction skill powered by Python `scrapling` and `html2text`. Automatically converts web pages to clean Markdown, handling lazy-loaded images and dynamic JS rendering.

---

## 这是什么 / What is this

一个基于 Python Scrapling 的本地网页正文提取工具。当用户需要抓取、阅读或总结某个具体网页（尤其是国内复杂的微信公众号、知乎、CSDN、掘金文章）时使用。

### 核心亮点 / Highlights

- **双模式引擎**：Fast 模式（~1-3s 高速 HTTP）与 Stealth 模式（~5-15s 无头浏览器），支持自动降级
- **懒加载图片修复**：自动提升 `data-src` 为 `src`，解决微信/知乎转换 Markdown 时图片丢失问题
- **精细 DOM 选择器**：内置 18+ 常用文章正文 CSS 选择器，避免抓到导航与侧边栏
- **结构化输出**：支持纯 Markdown 文本与 JSON 元数据格式输出

---

## 快速开始 / Quick Start

### 1. 安装依赖

```bash
pip install scrapling html2text
```

### 2. 命令行使用

```bash
# 通用网页提取
python3 scripts/fetch.py "https://sspai.com/post/73145"

# 微信公众号/知乎专栏（使用无头浏览器）
python3 scripts/fetch.py "https://mp.weixin.qq.com/s/xxx" --stealth

# 限制输出字符数并使用 JSON 格式
python3 scripts/fetch.py "https://example.com/article" 10000 --json
```

---

## 依赖 / Dependencies

- Python ≥ 3.10
- `scrapling`
- `html2text`

---

<a name="english"></a>

# Scrapling Content Fetcher Skill — English

> Extract clean Markdown content from web pages using local Scrapling Python fetchers.

## Features

- Fast HTTP & Stealth Headless Browser modes
- Fixes lazy-loaded images (`data-src` -> `src`)
- Preserves code blocks, headings, images, and links
- Built-in DOM selector cascade for tech blogs and social platforms
