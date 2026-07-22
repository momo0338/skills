# Mptext API — 微信公众号内容采集 Skill

> **中文** · [English below](#english)

通过 [mptext.top](https://down.mptext.top) API 搜索微信公众号、获取文章列表、下载文章内容（HTML/Markdown/Text/JSON），支持批量下载和通过文章 URL 反查公众号信息。

> Search WeChat Official Accounts, list articles, download content (HTML/Markdown/Text/JSON), batch download, and reverse-lookup accounts by article URL — powered by [mptext.top](https://down.mptext.top) API.

---

## 这是什么 / What is this

一个让 AI 助手具备微信公众号内容采集能力的 Skill。安装后，用自然语言描述需求，AI 自动完成公众号搜索、文章列表获取、内容下载等操作，并支持多种输出格式。

### 核心亮点 / Highlights

- **公众号搜索**：关键词搜索微信公众号，获取 fakeid、名称、简介等信息
- **文章列表**：获取指定公众号的文章列表，支持分页和关键词过滤
- **多格式下载**：HTML / Markdown / 纯文本 / JSON 四种输出格式
- **批量下载**：一键批量下载公众号全部或指定数量的文章
- **URL 反查**：通过文章链接反查所属公众号信息
- **脚本驱动**：内置 Python 脚本，命令行直接调用

---

## 适用场景 / When to Use

| 场景 | 示例 |
|------|------|
| 搜索公众号 | "搜索关键词 XX 的公众号" |
| 获取文章列表 | "获取这个公众号的最新 20 篇文章" |
| 下载单篇文章 | "下载这篇文章为 Markdown 格式" |
| 批量下载 | "把这个公众号的文章全部下载下来" |
| URL 反查公众号 | "这篇文章是哪个公众号发的？" |
| 内容分析 | "获取这个公众号最近文章的标题列表" |

> **与 weixin-article-save 的区别**：mptext-api 负责 API 层的采集操作（搜索/列表/下载），weixin-article-save 负责将文章保存到 Obsidian vault 并生成标准 frontmatter。两者可组合使用。

---

## 快速开始 / Quick Start

### 1. 安装依赖

```bash
pip install requests
```

### 2. 获取 API 密钥

1. 访问 [https://down.mptext.top](https://down.mptext.top) 并登录
2. 在网站 API 页面查看自动生成的密钥
3. 密钥有效期为 **4 天**（与登录会话一致）

### 3. 配置密钥

```bash
# 方式一：环境变量（推荐）
export MPTEXT_API_KEY=YOUR_KEY

# 方式二：命令行参数
python3 scripts/mptext_api.py <command> --api-key YOUR_KEY
```

### 4. 开始使用

```bash
# 搜索公众号
python3 scripts/mptext_api.py search-account "南京文旅"

# 获取文章列表
python3 scripts/mptext_api.py list-articles "fakeid123"

# 下载文章
python3 scripts/mptext_api.py download-article "https://mp.weixin.qq.com/s/xxx" --format markdown
```

---

## 命令参考 / Command Reference

### 6 个核心命令

| # | 命令 | 功能 | 关键参数 |
|---|------|------|---------|
| 1 | `search-account` | 搜索公众号 | `keyword` |
| 2 | `list-articles` | 获取文章列表 | `fakeid`, `--begin`, `--size`, `--keyword` |
| 3 | `download-article` | 下载单篇文章 | `url`, `--format` |
| 4 | `get-account-by-url` | URL 反查公众号 | `url` |
| 5 | `verify-key` | 验证 API 密钥 | — |
| 6 | `batch-download` | 批量下载文章 | `fakeid`, `--format`, `--output-dir`, `--limit` |

---

## 使用示例 / Examples

### 搜索公众号

```bash
python3 scripts/mptext_api.py search-account "南京文旅"
```

返回：公众号列表（fakeid、名称、头像、简介）

### 获取文章列表

```bash
# 最新 20 篇（默认）
python3 scripts/mptext_api.py list-articles "fakeid123"

# 分页获取
python3 scripts/mptext_api.py list-articles "fakeid123" --begin 20 --size 20

# 按标题搜索
python3 scripts/mptext_api.py list-articles "fakeid123" --keyword "南京"

# 保存到文件
python3 scripts/mptext_api.py list-articles "fakeid123" -o articles.json
```

### 下载文章内容

```bash
# Markdown 格式（推荐）
python3 scripts/mptext_api.py download-article "https://mp.weixin.qq.com/s/xxx" --format markdown

# HTML 格式（默认）
python3 scripts/mptext_api.py download-article "https://mp.weixin.qq.com/s/xxx"

# 纯文本
python3 scripts/mptext_api.py download-article "https://mp.weixin.qq.com/s/xxx" --format text

# JSON 格式
python3 scripts/mptext_api.py download-article "https://mp.weixin.qq.com/s/xxx" --format json

# 保存到文件
python3 scripts/mptext_api.py download-article "https://mp.weixin.qq.com/s/xxx" --format markdown -o article.md
```

### URL 反查公众号

```bash
python3 scripts/mptext_api.py get-account-by-url "https://mp.weixin.qq.com/s/xxx"
```

### 批量下载

```bash
# 批量下载为 Markdown
python3 scripts/mptext_api.py batch-download "fakeid123" --format markdown --output-dir ./articles

# 限制数量
python3 scripts/mptext_api.py batch-download "fakeid123" --format markdown --output-dir ./articles --limit 50

# 按关键词筛选后批量下载
python3 scripts/mptext_api.py batch-download "fakeid123" --format markdown --output-dir ./articles --keyword "南京"
```

### 验证密钥

```bash
python3 scripts/mptext_api.py verify-key --api-key YOUR_KEY
# code: 0 → 有效 | code: -1 → 已过期
```

---

## 典型工作流 / Workflows

### 流程 1：搜索公众号 → 浏览文章 → 下载内容

```
① search-account "关键词"   → 获取 fakeid
② list-articles "fakeid"    → 浏览文章列表
③ download-article "URL"    → 下载指定文章
```

### 流程 2：一键批量下载公众号文章

```
① search-account "关键词"                                    → 获取 fakeid
② batch-download "fakeid" --format markdown --output-dir ./   → 批量下载
```

### 流程 3：从文章 URL 出发 → 找到公众号 → 批量下载

```
① get-account-by-url "文章URL"                                → 获取 fakeid
② batch-download "fakeid" --format markdown --output-dir ./    → 批量下载
```

---

## API 端点参考 / API Endpoints

| 功能 | 方法 | 端点 |
|------|:----:|------|
| 搜索公众号 | GET | `/api/public/v1/account?keyword=关键词` |
| 获取文章列表 | GET | `/api/public/v1/article?fakeid=xxx&begin=0&size=20` |
| 下载文章内容 | GET | `/api/public/v1/download?url=文章URL&format=html` |
| URL 反查公众号 | GET | `/api/public/v1/accountbyurl?url=文章URL` |
| 验证密钥 | GET | `/api/public/v1/authkey` |

**基础地址**：`https://down.mptext.top`

**认证方式**：Header `X-Auth-Key: YOUR_KEY`

---

## 输出格式 / Output Formats

| 格式 | 参数值 | 说明 | 适用场景 |
|------|--------|------|---------|
| HTML | `html` | 完整 HTML 内容（默认） | 保留原始排版 |
| Markdown | `markdown` | Markdown 格式文本 | 二次编辑、Obsidian 保存 |
| 纯文本 | `text` | 去除格式的纯文本 | 文本分析、NLP |
| JSON | `json` | 结构化数据 | 程序化处理 |

---

## 故障排除 / Troubleshooting

| 问题 | 原因 | 解决方案 |
|------|------|---------|
| 401 Unauthorized | API 密钥无效或已过期 | 重新登录 [down.mptext.top](https://down.mptext.top) 获取新密钥 |
| 密钥频繁过期 | 密钥有效期仅 4 天 | 每 4 天重新登录获取；可考虑自动化刷新 |
| 搜索无结果 | 关键词不匹配 | 尝试公众号全名或更短的关键词 |
| 文章下载失败 | URL 格式不正确 | 确保使用完整的 `mp.weixin.qq.com/s/xxx` 格式 |
| `requests` 未安装 | Python 依赖缺失 | `pip install requests` |
| 批量下载中断 | 网络波动或限频 | 减小 `--limit` 数量，重新执行 |

---

## 常见问题 / FAQ

**Q: 免费吗？**
mptext.top 提供免费 API 访问，无需付费。但需要登录获取密钥。

**Q: API 密钥多久过期？**
4 天，与登录会话一致。过期后需重新登录 [down.mptext.top](https://down.mptext.top) 获取。

**Q: 每页最多获取多少篇文章？**
每页最多 20 篇（`size` 参数上限为 20）。更多文章需通过 `begin` 参数分页获取。

**Q: 支持下载文章中的图片吗？**
API 返回的 HTML/Markdown 中包含图片链接。如需本地化图片，建议配合 `weixin-article-save` 技能使用。

**Q: 与 weixin-article-save 技能有什么关系？**
互补关系——mptext-api 提供底层 API 采集能力（搜索/列表/下载），weixin-article-save 提供上层 Obsidian 保存流程（分类/frontmatter/图片本地化）。

---

## 依赖 / Dependencies

- [Python](https://www.python.org/) ≥ 3.6
- [requests](https://pypi.org/project/requests/)（HTTP 客户端）
- mptext.top API 密钥（登录获取，免费）

---

## 项目结构 / Project Structure

```
mptext-api/
├── SKILL.md          # 技能触发规则与完整 API 参考
├── README.md         # 本文件
├── .env              # API 密钥配置（本地）
└── scripts/
    └── mptext_api.py # 核心脚本
```

---

## 相关文档 / Related Docs

- **SKILL.md** — 技能触发规则与完整命令参考
- **[mptext.top](https://down.mptext.top)** — API 平台与密钥管理
- **weixin-article-save** — 配套的 Obsidian 文章保存技能

---

<a name="english"></a>

# Mptext API — WeChat Official Account Content Extraction Skill — English

> Search WeChat Official Accounts, list articles, download content in multiple formats, batch download, and reverse-lookup accounts by article URL.

## What is this

A skill that enables AI assistants to extract content from WeChat Official Accounts. Search accounts by keyword, browse article lists, download content in HTML/Markdown/Text/JSON, and batch-download entire accounts.

## Highlights

- **Account search**: Find accounts by keyword, get fakeid, name, description
- **Article listing**: Paginated article lists with keyword filtering
- **Multi-format download**: HTML / Markdown / Text / JSON
- **Batch download**: Download all articles from an account at once
- **URL reverse lookup**: Find account info from any article URL
- **Script-driven**: Built-in Python script for CLI usage

## Quick Start

1. Install: `pip install requests`
2. Get API key: Login at [down.mptext.top](https://down.mptext.top) (free, 4-day validity)
3. Configure: `export MPTEXT_API_KEY=YOUR_KEY`
4. Search: `python3 scripts/mptext_api.py search-account "keyword"`

## FAQ

**Q: Is it free?** Yes, free API access. Login required for key.

**Q: How long does the key last?** 4 days per login session.

**Q: Max articles per page?** 20. Use `--begin` for pagination.

**Q: Does it download images?** HTML/Markdown include image URLs. For local images, use the `weixin-article-save` skill.

## Dependencies

- [Python](https://www.python.org/) ≥ 3.6
- [requests](https://pypi.org/project/requests/)
- mptext.top API key (free, login to get)
