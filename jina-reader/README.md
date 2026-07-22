# Jina Reader Skill

> **中文** · [English below](#english)

基于 Jina AI (`r.jina.ai`) 的云端网页转 Markdown 工具。零本地依赖，发送 HTTP 请求即可将任意公开网页转换为大语言模型（LLM）友好的干净 Markdown 格式。

> Cloud-based web-to-markdown reader using Jina AI's `r.jina.ai` service. Instant, dependency-free Markdown extraction for LLMs.

---

## 这是什么 / What is this

一个极其轻量的云端网页阅读 Skill。当用户需要快速读取英文文档、公开技术博客或新闻页面时，只需将 `https://r.jina.ai/` 拼接到原 URL 前即可。

### 核心亮点 / Highlights

- **零本地依赖**：无需安装 Python 爬虫库或 Playwright 无头浏览器
- **极致速度**：云端解析，响应通常仅需 1-2 秒
- **AI 图片描述**：可通过 Header `X-With-Generated-Alt: true` 让 AI 自动为无 alt 的图片生成说明
- **灵巧过滤**：支持通过 `X-Target-Selector` 和 `X-Remove-Selector` 自由保留或裁切页面节点

---

## 快速开始 / Quick Start

```bash
# 基础调用
curl -s "https://r.jina.ai/https://example.com/article"

# 开启图片 AI captioning 并限制 Token
curl -s -H "X-With-Generated-Alt: true" -H "X-Token-Budget: 5000" "https://r.jina.ai/https://openai.com/index/gpt-4o/"

# JSON 输出格式
curl -s -H "Accept: application/json" "https://r.jina.ai/https://example.com"
```

---

## 注意事项 / Notes

- 免 API Key 使用受每日额度限制（约 200 次/天）。配置 `Authorization: Bearer <jina_api_key>` 可提升限额。
- 微信公众号、知乎专栏等具有严格 IP 防火墙的平台可能会返回 403 错误，不使用这个技能

---

<a name="english"></a>

# Jina Reader Skill — English

> Instant cloud web content extraction via `https://r.jina.ai/<url>`.

## Usage

```bash
curl -s "https://r.jina.ai/<url>"
```
