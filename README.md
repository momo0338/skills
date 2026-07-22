# Momo Skills Core Library (AI Agent 技能库)

> 包含 **13 个通用与专项 AI Agent 技能**，覆盖网页正文提取、媒体音视频下载、万站 CLI 操作、抖音专项 CLI、网络代理管理、企业情报深度调研及微信公众号采集等场景。

---

## 📚 技能目录与概览

| 技能名称 | 目录路径 | 核心用途 | 主要依赖 / 接口 |
|---------|---------|---------|----------------|
| **[opencli](./opencli)** | `opencli/` | 万站合一 CLI 工具（覆盖抖音、知乎、B站、YouTube、小红书、雪球等 164 站点 + 10 桌面应用） | Node.js, `@jackwener/opencli`, Chrome Extension |
| **[dy-cli](./dy-cli)** | `dy-cli/` | 抖音全功能 CLI 工具（搜索、无水印音视频/图文下载、热榜 Top 50、点赞/评论/收藏互动、发布与数据分析） | Python `dy-cli` |
| **[proxy](./proxy)** | `proxy/` | 代理池获取与管理工具（实时同步 `momo0338/proxy` 节点，支持 HTTP/SOCKS5 轮换、延迟测试与环境变量导出） | Python `proxy_manager.py`, GitHub raw |
| **[yt-dlp](./yt-dlp)** | `yt-dlp/` | 全能音视频下载（最高画质/音质、字幕提取、播放列表批处理、Cookie 认证） | `yt-dlp`, `ffmpeg` |
| **[scrapling](./scrapling)** | `scrapling/` | 本地网页正文提取（Fast/Stealth 无头双模式，自动修复懒加载图片 `data-src`） | Python `scrapling`, `html2text`, `browserforge` |
| **[jina-reader](./jina-reader)** | `jina-reader/` | 云端网页转 Markdown 工具（零本地依赖，支持 AI 图片描述与 Token 过滤） | HTTP API (`r.jina.ai`) |
| **[defuddle](./defuddle)** | `defuddle/` | 网页去杂清洁提取 CLI，快速提取纯净 Markdown，大幅节省 Token | Node.js `defuddle` CLI |
| **[lux](./lux)** | `lux/` | 多平台视频下载 CLI（YouTube、Bilibili、抖音、TikTok 等） | Homebrew `lux`, `ffmpeg` |
| **[mptext-api](./mptext-api)** | `mptext-api/` | 微信公众号 API 工具（支持公众号搜索、文章列表获取、多格式/批量下载） | Python `requests`, mptext.top API |
| **[fengniao-search](./fengniao-search)** | `fengniao-search/` | 风鸟企业与风险情报检索（工商信息、司法风险、经营异常、股东背景等） | Node.js `tool.mjs`, 风鸟 API |
| **[zhihu-search](./zhihu-search)** | `zhihu-search/` | 知乎内容搜索工具 | Python `zhihu-search.py`, 知乎 API |
| **[qibook-company-profile](./qibook-company-profile)** | `qibook-company-profile/` | 企书企业/人员组合查询工具 | Python `combined_query.py`, 企书 API |
| **[qibook-company-wiki-deepresearch](./qibook-company-wiki-deepresearch)** | `qibook-company-wiki-deepresearch/` | 企书企业百科深度调研与结构化报告生成工具 | Python `skill_runner.py`, 企书 API |

---

## 🛠️ 快速安装与配置指南

### 1. 基础系统依赖安装

```bash
# macOS (Homebrew)
brew install node ffmpeg yt-dlp lux

# Python 全局依赖包
pip install --break-system-packages scrapling html2text browserforge requests yt-dlp dy-cli

# npm 全局工具
npm install -g defuddle @jackwener/opencli
```

### 2. 核心技能命令示例

#### 抖音专项与搜索/下载

```bash
# 抖音关键词搜索 (短索引流机制)
dy search "AI Agent 教程" --limit 10

# 抖音无水印视频/图文下载 (按编号 1 或 URL)
dy dl 1

# 抖音实时热榜 Top 50
dy trending
```

#### 代理管理与请求转发

```bash
# 从 GitHub 同步最新代理数据
python3 proxy/scripts/proxy_manager.py sync

# 随机获取一个 HTTP 代理
python3 proxy/scripts/proxy_manager.py get --protocol http
```

#### 网页正文提取与阅读

```bash
# 使用 Scrapling 本地抓取并提取 Markdown (支持 Fast 和 Stealth 无头浏览器模式)
python3 scrapling/scripts/fetch.py "https://sspai.com/post/73145" --json

# 使用 Jina Reader 云端即时读取网页
curl -s "https://r.jina.ai/https://example.com"
```

---

## 🔗 远程仓库与同步

- **GitHub 仓库**：[https://github.com/momo0338/skills.git](https://github.com/momo0338/skills.git)
- **默认分支**：`main`
