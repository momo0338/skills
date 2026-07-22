# Defuddle — 网页清洁提取 Skill

> **中文** · [English below](#english)

从网页中提取干净的 Markdown 内容，自动去除导航栏、广告、侧边栏等杂乱元素，大幅节省 token 消耗。适用于在线文档、文章、博客等标准网页的内容提取。

> Extract clean Markdown from web pages, stripping navigation, ads, and clutter to save tokens. Ideal for documentation, articles, blog posts, and standard web pages.

---

## 这是什么 / What is this

一个让 AI 助手能够高效提取网页核心内容的 Skill。安装后，给出任意网页 URL，AI 自动调用 Defuddle CLI 提取干净的 Markdown 文本，去除所有无关内容。

### 核心亮点 / Highlights

- **智能去杂**：自动去除导航栏、广告、页脚、侧边栏等非核心内容
- **Markdown 输出**：直接输出格式化的 Markdown，便于阅读和二次处理
- **节省 Token**：相比直接抓取原始 HTML，Token 消耗大幅降低
- **元数据提取**：支持提取标题、描述、域名等页面元信息
- **多格式支持**：Markdown / JSON / HTML 三种输出格式
- **零配置启动**：安装即用，无需 API 密钥

---

## 适用场景 / When to Use

| 场景 | 是否适用 |
|------|:--------:|
| 阅读/分析标准网页内容 | ✅ |
| 在线文档提取 | ✅ |
| 文章、博客内容获取 | ✅ |
| 网页内容摘要 | ✅ |
| `.md` 结尾的 URL（已是 Markdown） | ❌ 直接用 WebFetch |
| 需要 JavaScript 渲染的 SPA 页面 | ❌ |

---

## 快速开始 / Quick Start

### 1. 安装

```bash
npm install -g defuddle
```

### 2. 验证安装

```bash
defuddle --version
```

### 3. 开始使用

```bash
# 提取网页内容为 Markdown
defuddle parse https://example.com/article --md

# 保存到文件
defuddle parse https://example.com/article --md -o content.md
```

---

## 使用示例 / Examples

**提取网页为 Markdown：**

```bash
defuddle parse https://docs.python.org/3/tutorial/index.html --md
```

**提取页面标题：**

```bash
defuddle parse https://example.com -p title
```

**提取页面描述：**

```bash
defuddle parse https://example.com -p description
```

**提取域名信息：**

```bash
defuddle parse https://example.com -p domain
```

**输出为 JSON（含 HTML 和 Markdown）：**

```bash
defuddle parse https://example.com --json
```

**保存结果到文件：**

```bash
defuddle parse https://example.com --md -o output.md
```

---

## 输出格式 / Output Formats

| 参数 | 格式 | 说明 |
|------|------|------|
| `--md` | Markdown | **推荐**，干净可读 |
| `--json` | JSON | 包含 HTML 和 Markdown 两种内容 |
| （无参数） | HTML | 原始清洁后的 HTML |
| `-p <name>` | 文本 | 提取指定元数据属性 |

---

## 与 WebFetch 的对比 / Defuddle vs WebFetch

| 特性 | Defuddle | WebFetch |
|------|:--------:|:--------:|
| 去除广告/导航 | ✅ | ❌ |
| Token 消耗 | 低 | 高 |
| Markdown 输出质量 | 高 | 一般 |
| `.md` URL 支持 | ❌ | ✅ |
| JavaScript 渲染 | ❌ | 部分 |
| 安装依赖 | npm 包 | 内置 |

> **选择建议**：标准网页优先用 Defuddle；`.md` 结尾的 URL 直接用 WebFetch。

---

## 常见问题 / FAQ

**Q: 免费吗？**
完全免费开源，无需 API 密钥，无使用次数限制。

**Q: 支持哪些网页？**
支持绝大多数标准 HTML 网页，包括文档站、博客、新闻网站等。不支持需要 JavaScript 渲染的 SPA 页面。

**Q: 与 readability 有什么区别？**
Defuddle 基于 Mozilla 的 Readability 算法进行了增强，在内容提取精度和格式化质量上更优。

**Q: 提取失败怎么办？**
1. 检查 URL 是否可访问
2. 尝试使用 `--json` 格式查看原始输出
3. 部分网站有反爬限制，可回退使用 WebFetch

---

## 依赖 / Dependencies

- [Node.js](https://nodejs.org/) ≥ 14
- [defuddle](https://www.npmjs.com/package/defuddle) (npm 全局安装)

---

## 相关文档 / Related Docs

- **SKILL.md** — 技能触发规则与完整命令参考

---

<a name="english"></a>

# Defuddle — Clean Web Content Extraction Skill — English

> Extract clean Markdown from web pages, stripping navigation, ads, and clutter. Save tokens, get readable content.

## What is this

A skill that enables AI assistants to efficiently extract core content from web pages. Given any URL, the AI uses Defuddle CLI to produce clean Markdown text with all irrelevant elements removed.

## Highlights

- **Smart de-cluttering**: Auto-removes navbars, ads, footers, sidebars
- **Markdown output**: Clean, formatted Markdown ready for reading or processing
- **Token-efficient**: Dramatically reduces token consumption vs raw HTML
- **Metadata extraction**: Title, description, domain and more
- **Multiple formats**: Markdown / JSON / HTML
- **Zero config**: Install and use, no API keys needed

## Quick Start

1. Install: `npm install -g defuddle`
2. Extract: `defuddle parse <url> --md`
3. Save: `defuddle parse <url> --md -o output.md`

## FAQ

**Q: Is it free?** Yes, fully open source, no API keys, no usage limits.

**Q: What pages are supported?** Most standard HTML pages. Not for JavaScript-heavy SPAs.

**Q: What if extraction fails?** Check URL accessibility, try `--json` for raw output, fall back to WebFetch.

## Dependencies

- [Node.js](https://nodejs.org/) ≥ 14
- [defuddle](https://www.npmjs.com/package/defuddle) (npm global install)
