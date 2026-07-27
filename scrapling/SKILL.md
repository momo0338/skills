---
name: scrapling-fetcher
description: |
  使用 Scrapling + html2text 从任意网页中提取干净的 Markdown 正文。
  支持 Fast (普通 HTTP) 与 Stealth (无头浏览器) 双模式，内置 DOM 选择器优先级（优先匹配 article, main, div#js_content 等）与懒加载图片修复（data-src 自动提升为 src）。
  特别适用于微信公众号、知乎、掘金、CSDN、36氪、少数派等国内复杂网页的正文提取。
  触发词：scrapling、网页提取、提取正文、抓取网页、微信公众号文章提取、抓取知乎文章。
version: 1.0.0
---

# Scrapling Content Fetcher — 本地网页正文提取 Skill

> 基于 Scrapling 的智能网页正文提取工具，自动转换为干净的 Markdown 格式。

## Overview

采用 Python 的 Scrapling 库 + html2text 工具，通过精确的 DOM 选择器策略（Article / JS_Content 等）提取网页核心内容，并自动修补微信/知乎等平台的 `data-src` 懒加载图片。

## 安装依赖 / Installation

```bash
pip install scrapling html2text
```

> 如果在系统 Python 环境下提示，可使用 `pip install --break-system-packages scrapling html2text` 或虚拟环境。

## 提取策略与模式

```
URL 输入
  │
  ├─ Fast 模式 (默认)
  │   - 基于 Scrapling Fetcher HTTP 请求 (~1-3s)
  │   - 自动检测提取字符长度，低于 200 字自动降级至 Stealth 模式
  │
  └─ Stealth 模式 (--stealth)
      - 基于 StealthyFetcher 无头浏览器 (~5-15s)
      - 完整执行 JavaScript，绕过反爬机制与动态渲染
      - 适用于微信公众号、知乎专栏、掘金等 JS 渲染页面
```

## 常用命令与标准传参语法

> 传参格式：`python3 <SKILL_DIR>/scripts/fetch.py <url> [max_chars] [--stealth] [--json]`

```bash
# 1. 基础提取 (自动选择 Fast 快速模式 / 低于 200 字自动降级 Stealth 无头浏览器)
python3 <SKILL_DIR>/scripts/fetch.py "https://sspai.com/post/73145"

# 2. 强制 Stealth 无头浏览器模式 (用于微信公众号/知乎等需执行 JS 的页面)
python3 <SKILL_DIR>/scripts/fetch.py "https://mp.weixin.qq.com/s/xxx" --stealth

# 3. 指定最大字符数 (默认 30000 字符上限，位置参数放 URL 之后)
python3 <SKILL_DIR>/scripts/fetch.py "https://example.com/article" 15000

# 4. 组合使用：指定 15000 字符限制 + 无头浏览器模式 + JSON 结构化输出
python3 <SKILL_DIR>/scripts/fetch.py "https://example.com/article" 15000 --stealth --json
```

## 关键支持与故障排查

1. **选择器优先级**：内置 `div#js_content` (微信)、`article`、`main`、`.Post-RichText` (知乎)、`#article_content` (CSDN)、`.article-area` (掘金) 等 18+ 常用文章正文 CSS 选择器。
2. **懒加载图片修复**：自动将 `data-src` 链接转换为 `src`，解决微信/知乎转换成 Markdown 后图片丢失或变成占位符的问题。
3. **安全降级机制**：Fast 模式抓取字数小于 200 字时，自动触发无头浏览器重试。
4. **无头浏览器依赖排查**：若使用 `--stealth` 模式报错提示缺少 Chromium 驱动，可运行：
   ```bash
   playwright install chromium
   ```

