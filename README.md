# Momo Skills Core Library (AI Agent 技能库)

> 包含 **11 个通用与专项 AI Agent 技能**，覆盖网页正文提取、媒体音视频下载、万站 CLI 操作、企业情报深度调研及微信公众号采集等场景。

---

## 📚 技能目录与概览

| 技能名称 | 目录路径 | 核心用途 | 主要依赖 / 接口 |
|---------|---------|---------|----------------|
| **[opencli](./opencli)** | `opencli/` | 万站合一 CLI 工具（覆盖抖音、知乎、B站、YouTube、小红书、雪球等 164 站点 + 10 桌面应用） | Node.js, `@jackwener/opencli`, Chrome Extension |
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
pip install --break-system-packages scrapling html2text browserforge requests yt-dlp

# npm 全局工具
npm install -g defuddle @jackwener/opencli
```

### 2. 核心技能命令示例

#### 网页正文提取与阅读

```bash
# 使用 Scrapling 本地抓取并提取 Markdown (支持 Fast 和 Stealth 无头浏览器模式)
python3 scrapling/scripts/fetch.py "https://sspai.com/post/73145" --json

# 使用 Jina Reader 云端即时读取网页
curl -s "https://r.jina.ai/https://example.com"

# 使用 Defuddle 清洁抓取
defuddle parse https://example.com --md
```

#### 音视频搜索与下载

```bash
# 搜索抖音视频 (需在 Chrome/Edge 中登录抖音并启用 OpenCLI 插件)
opencli douyin search "AI Agent 教程" --limit 5 -f json

# 使用 yt-dlp 下载无水印视频 (自动复用浏览器 Cookie)
yt-dlp --cookies-from-browser edge "https://www.douyin.com/video/7657851624437665070"

# 仅提取最高音质 MP3 并嵌入封面
yt-dlp -x --audio-format mp3 --embed-thumbnail "https://www.youtube.com/watch?v=xxx"
```

#### 微信公众号采集

```bash
# 验证 mptext-api 密钥状态
python3 mptext-api/scripts/mptext_api.py verify-key --api-key YOUR_KEY

# 批量下载公众号文章为 Markdown
python3 mptext-api/scripts/mptext_api.py batch-download "fakeid123" --format markdown --output-dir ./articles
```

#### 企业情报与风险尽调

```bash
# 使用风鸟探索企业查询工具
node fengniao-search/scripts/tool.mjs discover "企业股东信息"

# 企书企业组合查询
python3 qibook-company-profile/scripts/combined_query.py --entmark "企业标识"
```

---

## 📄 技能开发与贡献规范

每个技能子目录必须遵循标准 Skill 结构：
1. **`SKILL.md`**：技能元数据（YAML Frontmatter，包含 `name`, `description`, `version`）及 AI Agent 触发规则。
2. **`README.md`**：中英双语用户指南，包含快速开始、命令行示例、参数说明与 FAQ。
3. **`scripts/`**（可选）：可被调用的 Python / Node.js 独立执行脚本。

---

## 🔗 远程仓库与同步

- **GitHub 仓库**：[https://github.com/momo0338/skills.git](https://github.com/momo0338/skills.git)
- **默认分支**：`main`
