# OpenCLI — 万站合一命令行工具 Skill

> **中文** · [English below](#english)

把任意网站变成 CLI —— 覆盖 **1275+ 命令**，横跨 **164 个站点 + 10 个桌面应用 + 13 个外部 CLI**。知乎、Bilibili、小红书、YouTube、Twitter、抖音、雪球等一个 `opencli` 搞定。

> Convert any website into CLI — **1275+ commands** across **164 sites + 10 desktop apps + 13 external CLIs**. One tool to rule them all.

---

## 这是什么 / What is this

[OpenCLI](https://github.com/jackwener/OpenCLI) 让 AI 助手能够通过统一命令行操作各种网站和桌面应用。安装后，用自然语言描述需求，AI 自动调用对应的 `opencli` 命令完成任务——获取热榜、下载文章/视频、搜索内容、查看用户信息、操作桌面应用等。

### 核心亮点 / Highlights

- **164+ 站点覆盖**：知乎、Bilibili、小红书、YouTube、Twitter/X、抖音、雪球、Reddit、HackerNews 等
- **10 个桌面应用**：Cursor、ChatGPT、Codex、Discord、Antigravity 等 Electron 应用适配器
- **13 个外部 CLI**：GitHub CLI、Docker、Telegram、WeChat、Notion、Obsidian 等
- **浏览器自动化**：通过 `opencli browser` 操作任意网页（导航、点击、填表、提取）
- **登录态复用**：使用你已登录的 Chrome 浏览器会话，无需额外认证
- **自然语言驱动**：描述你想做的事，AI 自动选择和执行命令

---

## 快速开始 / Quick Start

### 1. 安装 OpenCLI

```bash
# 方式 A：npm 全局安装（需 Node.js >= 20）
npm install -g @jackwener/opencli

# 方式 B：OpenCLIApp 桌面版（推荐）
# 下载地址：https://opencli.info/download
```

### 2. 安装 Browser Bridge 扩展

从 [Chrome Web Store](https://chromewebstore.google.com/detail/opencli/ildkmabpimmkaediidaifkhjpohdnifk) 安装 OpenCLI 扩展。

### 3. 验证安装

```bash
opencli doctor
```

### 4. 开始使用

```bash
opencli list                            # 查看所有命令
opencli hackernews top --limit 5        # HN 热门
opencli bilibili hot --limit 5          # B站热门
opencli zhihu hot                       # 知乎热榜
```

---

## 使用示例 / Examples

**获取网站热榜：**

```bash
opencli zhihu hot                       # 知乎热榜
opencli bilibili hot                    # B站热门
opencli weibo hot                       # 微博热搜
opencli douyin hot                      # 抖音热搜
opencli xueqiu hot-stock                # 雪球热门股票
opencli hackernews top --limit 10       # HN 热门
```

**搜索网站内容：**

```bash
opencli zhihu search "深度学习"           # 知乎搜索
opencli youtube search "machine learning" # YouTube 搜索
opencli xiaohongshu search "旅游攻略"     # 小红书搜索
opencli xueqiu search "贵州茅台"          # 雪球搜索
```

**下载文章/视频：**

```bash
opencli zhihu download --url "https://zhuanlan.zhihu.com/p/xxx" --output /tmp/article --download-images true
opencli weixin download --url "https://mp.weixin.qq.com/s/xxx" --output /tmp/weixin
opencli bilibili download "https://www.bilibili.com/video/BVxxx"
opencli youtube transcript <video_id>   # YouTube 字幕
```

**查看用户/股票信息：**

```bash
opencli zhihu user <username>           # 知乎用户资料
opencli xueqiu stock SH600519           # 茅台实时行情
opencli xueqiu kline SH600519           # 茅台K线数据
```

---

## 站点覆盖 / Site Coverage

| 分类 | 站点 | 数量 |
|------|------|:----:|
| **中文社区** | 知乎、Bilibili、小红书、微博、抖音、豆瓣、掘金、V2EX、简书、少数派… | 40+ |
| **国际社区** | YouTube、Twitter/X、Reddit、HackerNews、Medium、Dev.to、Instagram… | 30+ |
| **视频/音乐** | Bilibili、YouTube、抖音、TikTok、优酷、爱奇艺、腾讯视频、网易云音乐… | 15+ |
| **金融投资** | 雪球、Yahoo Finance、长桥证券 | 3 |
| **工具/学术** | Z-Library、Google Scholar、DeepSeek、Kimi、有道云… | 10+ |
| **桌面应用** | Cursor、ChatGPT、Codex、Discord、Antigravity… | 10 |
| **外部 CLI** | gh、docker、tg、wx、ntn、obsidian、longbridge、vercel… | 13 |

> 完整列表：`opencli list`

---

## 命令类型 / Command Types

| 类型 | 含义 | 要求 |
|------|------|------|
| `public` | 公开 API | 无需登录 |
| `cookie` | 需要登录态 | 需在 Chrome 中登录对应网站 |
| `local` | 读取本地数据 | 无 |
| `ui` | CDP 操作桌面应用 | 需应用运行中 |
| `auto-install` | 首次使用自动安装 | 无 |

---

## 常见问题 / FAQ

**Q: 免费吗？**
完全免费开源（[MIT License](https://github.com/jackwener/OpenCLI/blob/main/LICENSE)）。

**Q: cookie 类型命令怎么使用？**
需要安装 Browser Bridge Chrome 扩展，并在 Chrome 中登录对应网站。OpenCLI 会复用你的登录态。

**Q: 支持哪些浏览器？**
Chrome 和 Chromium 系浏览器（通过 Browser Bridge 扩展通信）。

**Q: 命令不工作怎么办？**
运行 `opencli doctor` 诊断环境，检查 Browser Bridge 是否连接、Node.js 版本、网站登录状态。

**Q: 怎么更新？**
`npm update -g @jackwener/opencli`

---

## 依赖 / Dependencies

- [Node.js](https://nodejs.org/) >= 20
- [@jackwener/opencli](https://www.npmjs.com/package/@jackwener/opencli) (npm)
- [OpenCLI Browser Bridge](https://chromewebstore.google.com/detail/opencli/ildkmabpimmkaediidaifkhjpohdnifk)（Chrome 扩展，cookie 类型命令需要）

---

## 相关文档 / Related Docs

- **SKILL.md** — 完整命令速查表与触发规则
- **[OpenCLI GitHub](https://github.com/jackwener/OpenCLI)** — 官方仓库与文档
- **[opencli.info](https://opencli.info)** — 官方网站与 App 下载
- **weixin-article-save** — 配套的微信文章 Obsidian 保存技能
- **zhihu-article-save** — 配套的知乎文章 Obsidian 保存技能

---

<a name="english"></a>

# OpenCLI — Universal Website CLI Skill — English

> Convert any website into CLI — 1275+ commands across 164 sites + 10 desktop apps + 13 external CLIs.

## What is this

[OpenCLI](https://github.com/jackwener/OpenCLI) gives AI assistants the ability to operate websites and desktop apps through a unified CLI. Describe what you need, and the AI runs the right `opencli` command — trending content, article/video download, search, user info, browser automation, and more.

## Highlights

- **164+ sites**: Zhihu, Bilibili, Xiaohongshu, YouTube, Twitter/X, Douyin, Reddit, HackerNews, etc.
- **10 desktop apps**: Cursor, ChatGPT, Codex, Discord, Antigravity adapters
- **13 external CLIs**: GitHub CLI, Docker, Telegram, WeChat, Notion, Obsidian, etc.
- **Browser automation**: Navigate, click, fill forms, extract data via `opencli browser`
- **Session reuse**: Uses your logged-in Chrome session, no extra auth needed
- **Natural language driven**: Describe your goal, AI picks the right command

## Quick Start

1. Install: `npm install -g @jackwener/opencli`
2. Install Chrome extension: [OpenCLI Browser Bridge](https://chromewebstore.google.com/detail/opencli/ildkmabpimmkaediidaifkhjpohdnifk)
3. Verify: `opencli doctor`
4. Use: `opencli hackernews top --limit 5`

## FAQ

**Q: Is it free?** Yes, fully open source (MIT License).

**Q: How do cookie commands work?** Install the Browser Bridge extension and log in to sites in Chrome. OpenCLI reuses your session.

**Q: How to update?** `npm update -g @jackwener/opencli`

## Dependencies

- [Node.js](https://nodejs.org/) >= 20
- [@jackwener/opencli](https://www.npmjs.com/package/@jackwener/opencli) (npm)
- [OpenCLI Browser Bridge](https://chromewebstore.google.com/detail/opencli/ildkmabpimmkaediidaifkhjpohdnifk) (Chrome extension)
