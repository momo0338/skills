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

## 🤖 自动配置全平台 AI 助手技能

内置自动化脚本，可自动扫描本机已安装的 AI 工具（Claude Code、Gemini/Antigravity、OpenAI Codex、Cursor、Windsurf、OpenClaw 等），并将本仓库中的全量技能自动软链接/配置到各个 AI 助手中：

```bash
# 自动检测本机已安装的 AI 助手并一键挂载全量技能
python3 scripts/auto_config_ai.py

# 预览拟配置的 AI 助手与路径 (不实际写文件)
python3 scripts/auto_config_ai.py --dry-run
```

### 支持的 AI 助手与配置路径

- **Claude Code / Claude Agent** (`~/.claude/skills/`)
- **Google Gemini / Antigravity Agent** (`~/.gemini/config/skills.json` 与 `~/.gemini/config/skills/`)
- **OpenAI Codex Agent** (`~/.codex/skills/`)
- **Cursor IDE** (`~/.cursor/skills/`)
- **Windsurf IDE** (`~/.codeium/windsurf/skills/`)
- **OpenClaw Agent** (`~/.openclaw/skills/`)

---

## 🛠️ 基础系统依赖安装

```bash
# macOS (Homebrew)
brew install node ffmpeg yt-dlp lux

# Python 全局依赖包
pip install --break-system-packages scrapling html2text browserforge requests yt-dlp dy-cli

# npm 全局工具
npm install -g defuddle @jackwener/opencli
```

---

## 🔗 远程仓库与同步

- **GitHub 仓库**：[https://github.com/momo0338/skills.git](https://github.com/momo0338/skills.git)
- **默认分支**：`main`
