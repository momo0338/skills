---
name: mptext-api
description: 通过 mptext.top API 搜索微信公众号、获取文章列表、下载文章内容（支持 HTML/Markdown/Text/JSON 格式）、通过文章 URL 反查公众号信息。适用于微信公众号文章采集、内容提取、公众号分析等场景。
---

# 微信公众号 API 工具 (mptext.top)

通过 RESTful API 快速操作微信公众号内容，支持搜索公众号、获取文章列表、下载文章内容等多种格式。

## 适用场景

- 搜索微信公众号："搜索某个关键词的公众号"
- 获取公众号文章列表："获取这个公众号的最新文章"
- 下载文章内容："下载这篇文章为 Markdown 格式"
- 批量下载文章："把这个公众号的文章全部下载下来"
- 通过文章 URL 查找公众号："这篇文章是哪个公众号发的"
- 需要多种输出格式：HTML、Markdown、纯文本、JSON

## 安装依赖

```bash
pip install requests
```

## 配置 API 密钥

> **当前状态（2026-09-04 实测更新）**
> - Key 已配置在 `scripts/.mpkey`（600 权限），实测 `verify-key` 有效（code:0）。
> - ⚠️ **WorkBuddy 沙箱内直接跑本脚本会被 Cloudflare 盾拦（down.mptext.top 全域 403，连首页都挑战）**，requests/curl 均不可用。
> - ✅ **可用姿势**：用 ego-browser 打开 `https://down.mptext.top/`（本机浏览器已登录，过 CF）后在页面上下文里 `fetch('/api/public/v1/...', { headers: { 'X-Auth-Key': <key> } })` 同源调用。
> - ⚠️ **响应格式与下文文档不符**：实际返回 `{"base_resp":{"ret":0,"err_msg":"ok"},"list":[...]}`（搜索）/ `article_list`（文章），不是 `{"code":..,"data":..}`。
> - ⚠️ 2026-09-04 实测 `list-articles` 对所有 fakeid 返回 `ret=200013`（0 篇），疑似 mptext 服务端公众号会话失效，与本地 key 无关；`search-account`、`verify-key` 正常。

所有 API 请求需要在 Header 中携带 `X-Auth-Key` 进行认证。

API 密钥在登录 https://down.mptext.top 后自动生成，可在网站的 API 页面查看。密钥有效期与登录会话一致（4 天）。

使用方式：
- 命令行参数：`--api-key YOUR_KEY`
- 环境变量：`export MPTEXT_API_KEY=YOUR_KEY`

## 工作流程

### 命令1：search-account - 搜索公众号

```bash
python3 scripts/mptext_api.py search-account "关键词"
```

示例：
```bash
# 基本搜索
python3 scripts/mptext_api.py search-account "南京文旅"

# 指定 API 密钥
python3 scripts/mptext_api.py search-account "南京文旅" --api-key YOUR_KEY
```

返回：公众号列表，包含 fakeid、名称、头像、简介等信息。

### 命令2：list-articles - 获取文章列表

```bash
python3 scripts/mptext_api.py list-articles "fakeid"
```

示例：
```bash
# 获取最新文章（默认 20 篇）
python3 scripts/mptext_api.py list-articles "fakeid123"

# 分页获取（从第 20 篇开始，获取 20 篇）
python3 scripts/mptext_api.py list-articles "fakeid123" --begin 20 --size 20

# 按标题关键词搜索
python3 scripts/mptext_api.py list-articles "fakeid123" --keyword "南京"

# 保存到文件
python3 scripts/mptext_api.py list-articles "fakeid123" -o articles.json
```

返回：文章列表，包含标题、链接、发布时间、摘要等信息。

### 命令3：download-article - 下载文章内容

```bash
python3 scripts/mptext_api.py download-article "文章URL"
```

示例：
```bash
# 下载为 HTML（默认）
python3 scripts/mptext_api.py download-article "https://mp.weixin.qq.com/s/xxx"

# 下载为 Markdown 格式
python3 scripts/mptext_api.py download-article "文章URL" --format markdown

# 下载为纯文本
python3 scripts/mptext_api.py download-article "文章URL" --format text

# 下载为 JSON 格式
python3 scripts/mptext_api.py download-article "文章URL" --format json

# 保存到文件
python3 scripts/mptext_api.py download-article "文章URL" --format markdown -o article.md
```

支持的格式：
- `html`（默认）- 完整 HTML 内容
- `markdown` - Markdown 格式文本
- `text` - 纯文本内容
- `json` - JSON 结构化数据

### 命令4：get-account-by-url - 通过文章 URL 获取公众号信息

```bash
python3 scripts/mptext_api.py get-account-by-url "文章URL"
```

示例：
```bash
# 通过文章 URL 查找公众号
python3 scripts/mptext_api.py get-account-by-url "https://mp.weixin.qq.com/s/xxx"

# 保存到文件
python3 scripts/mptext_api.py get-account-by-url "文章URL" -o account.json
```

返回：公众号信息，包含 fakeid、名称、头像、简介等。

### 命令5：verify-key - 验证 API 密钥

```bash
python3 scripts/mptext_api.py verify-key
```

示例：
```bash
# 验证 API 密钥是否有效
python3 scripts/mptext_api.py verify-key --api-key YOUR_KEY
```

返回：`code: 0` 表示密钥有效，`code: -1` 表示已过期。

### 命令6：batch-download - 批量下载文章（高级功能）

```bash
python3 scripts/mptext_api.py batch-download "fakeid" --format markdown --output-dir ./articles
```

示例：
```bash
# 批量下载公众号所有文章为 Markdown
python3 scripts/mptext_api.py batch-download "fakeid123" --format markdown --output-dir ./articles

# 批量下载并限制数量
python3 scripts/mptext_api.py batch-download "fakeid123" --format markdown --output-dir ./articles --limit 50

# 批量下载包含关键词的文章
python3 scripts/mptext_api.py batch-download "fakeid123" --format markdown --output-dir ./articles --keyword "南京"
```

## 典型工作流

### 流程1：搜索公众号并下载文章

```bash
# 1. 搜索公众号
python3 scripts/mptext_api.py search-account "南京文旅"

# 2. 使用返回的 fakeid 获取文章列表
python3 scripts/mptext_api.py list-articles "返回的fakeid" -n 10

# 3. 下载指定文章为 Markdown
python3 scripts/mptext_api.py download-article "文章URL" --format markdown -o article.md
```

### 流程2：批量下载公众号文章

```bash
# 一键批量下载
python3 scripts/mptext_api.py batch-download "fakeid" --format markdown --output-dir ./articles --limit 20
```

### 流程3：通过文章 URL 查找公众号并下载文章

```bash
# 1. 通过 URL 获取公众号信息
python3 scripts/mptext_api.py get-account-by-url "文章URL"

# 2. 使用返回的 fakeid 批量下载该公众号文章
python3 scripts/mptext_api.py batch-download "返回的fakeid" --format markdown --output-dir ./articles
```

## API 端点参考

| 功能 | 方法 | 端点 |
|------|------|------|
| 搜索公众号 | GET | `/api/public/v1/account?keyword=关键词` |
| 获取文章列表 | GET | `/api/public/v1/article?fakeid=xxx&begin=0&size=20` |
| 下载文章内容 | GET | `/api/public/v1/download?url=文章URL&format=html` |
| 通过 URL 获取公众号 | GET | `/api/public/v1/accountbyurl?url=文章URL` |
| 验证 API 密钥 | GET | `/api/public/v1/authkey` |

基础地址：`https://down.mptext.top`

## 参数说明

### 搜索公众号
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| keyword | string | 是 | 公众号名称关键词 |

### 获取文章列表
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| fakeid | string | 是 | 公众号的 fakeid |
| begin | number | 否 | 起始位置，默认 0 |
| size | number | 否 | 每页数量，默认 20（最大 20） |
| keyword | string | 否 | 文章标题搜索关键词 |

### 下载文章内容
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| url | string | 是 | 微信文章 URL |
| format | string | 否 | 输出格式：html（默认）/ markdown / text / json |

### 通过 URL 获取公众号
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| url | string | 是 | 微信文章 URL |

## 注意事项

- API 密钥有效期为 4 天，过期后需重新登录获取
- 每页最多获取 20 篇文章
- 所有 API 请求需要在 Header 中携带 `X-Auth-Key`
- 如果遇到 401 错误，说明 API 密钥无效或已过期
