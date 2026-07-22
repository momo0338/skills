---
name: jina-reader
description: |
  使用 Jina Reader 云端 API (r.jina.ai) 将任意公开网页即据转换为 LLM 友好的 Markdown 正文。
  免去本地 Python 或无头浏览器依赖，响应速度极快 (~1-2s)。
  支持高级 Header 配置：图像 AI 描述 (X-With-Generated-Alt)、Token 预算 (X-Token-Budget)、指定 CSS 选择器 (X-Target-Selector) 等。
  适用于公开博客、英文技术文档、新闻资讯、GitHub/StackOverflow 页面的快速正文提取。
  注意：对微信公众号 (403) 或强防爬国内平台效果较差，此类平台建议优先使用 scrapling-fetcher。
  触发词：jina、jina-reader、r.jina.ai、云端网页提取、网页转markdown、快速读网页。
version: 1.0.0
---

# Jina Reader — 云端网页转 Markdown Skill

> 基于 Jina AI 的 `r.jina.ai` 服务，将任意 URL 即时解析为适用于大语言模型的干净 Markdown。

## Overview

[Jina Reader](https://jina.ai/reader) 是一个云端网页转 Markdown 接口。无需本地安装浏览器或复杂的爬虫环境，只需在 URL 前加上 `https://r.jina.ai/` 即可通过简单的 HTTP GET 请求提取正文。

## Quick Usage / 快捷调用

### 1. 基础 curl 调用

```bash
curl -s "https://r.jina.ai/https://example.com/article"
```

### 2. 在 Agent/代码中直接读取

向 `https://r.jina.ai/<URL>` 发送 HTTP GET 请求即可直接获取 Markdown 内容。

## 高级 Header 配置

Jina Reader 支持丰富自订 Header 参数来控制解析行为：

| Header 名称 | 说明 / 作用 | 示例 |
|------------|------------|------|
| `X-With-Generated-Alt` | 开启 AI 生成图片 alt 描述 | `X-With-Generated-Alt: true` |
| `X-Target-Selector` | 指定提取的 CSS 选择器 | `X-Target-Selector: main` |
| `X-Remove-Selector` | 指定排除的 CSS 选择器 | `X-Remove-Selector: nav, footer, .sidebar` |
| `X-Token-Budget` | 限制返回的最大 Token 数量 | `X-Token-Budget: 8000` |
| `X-With-Images-Summary` | 收集并附带页面图片的摘要说明 | `X-With-Images-Summary: true` |
| `X-With-Links-Summary` | 在文章末尾列出页面所有链接索引 | `X-With-Links-Summary: true` |
| `Accept` | 返回格式（默认 text/plain 为 Markdown） | `Accept: application/json` |

## 命令示例

### 带 AI 图片描述与 Token 预算提取

```bash
curl -s -H "X-With-Generated-Alt: true" -H "X-Token-Budget: 10000" "https://r.jina.ai/https://openai.com/index/gpt-4o/"
```

### 返回 JSON 结构化数据（包含 title, content, description 等）

```bash
curl -s -H "Accept: application/json" "https://r.jina.ai/https://sspai.com/post/73145"
```

## 适用与不适用场景

| 场景 | 是否适用 | 原因 |
|------|:--------:|------|
| 英文技术文档 / 博客 | ✅ | 解析非常速度且格式完美 |
| GitHub / Wikipedia / HackerNews | ✅ | 支持云端无阻访问 |
| 需本地执行 JS 的页面 | ✅ | Jina 云端引擎支持动态渲染 |
| 微信公众号文章 | ❌ | 腾讯风控会拦截 Jina 云端 IP (返回 403) |
| 需要登录后可见的内容 | ❌ | 无登录态 Cookie 支持 |

> **建议**：公开国际/技术网页优先使用 `jina-reader`；微信公众号、知乎等受限制网页不使用这个。
