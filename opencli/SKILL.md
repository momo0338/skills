---
name: opencli
description: |
  使用 OpenCLI 操作 100+ 网站和桌面应用的统一命令行工具。
  内置 1275+ 命令，覆盖 Bilibili、知乎、小红书、Twitter/X、YouTube、抖音、微信、Discord、雪球等 164 个站点 + 10 个桌面应用 + 13 个外部 CLI。
  支持文章/视频下载、热榜获取、搜索、账号信息、浏览器自动化等。
  当用户需要操作网站内容（如获取热榜、下载文章/视频、搜索内容、查看用户信息等）时触发。
  触发词：opencli、获取热榜、下载文章、下载视频、搜索XX网站、查看XX用户、XX热门、bilibili、知乎、小红书、YouTube、抖音、雪球、微博、Twitter、Reddit、HackerNews。
version: 1.0.0
---

# OpenCLI — 万站合一命令行工具

> 把任意网站变成 CLI & 在你的登录态浏览器上跑 Browser Use。

## Overview

[OpenCLI](https://github.com/jackwener/OpenCLI) 是一个统一命令行工具，覆盖 **1275+ 命令**，横跨 **164 个站点 + 10 个桌面应用 + 13 个外部 CLI**。它能把网站、浏览器会话、Electron 应用和本地工具统一变成确定性接口。

## 安装状态

- **安装路径**：`/usr/local/bin/opencli`
- **当前版本**：1.8.6
- **npm 包**：`@jackwener/opencli`
- **Node.js 要求**：>= 20

## When to Use

- 用户要获取网站热榜/热门内容
- 用户要下载网站文章或视频
- 用户要搜索网站内容
- 用户要查看网站用户信息
- 用户要操作桌面应用（Cursor、ChatGPT、Discord 等）
- 用户要通过浏览器自动化完成网页操作

## 核心命令模式

```
opencli <site> <command> [options]
```

## 系统命令

| 命令 | 用途 |
|------|------|
| `opencli list` | 列出所有可用命令 |
| `opencli doctor` | 诊断环境和浏览器连接 |
| `opencli profile list` | 列出已连接的 Chrome 配置 |
| `opencli external register <name>` | 注册本地 CLI 工具 |

## 常用站点命令速查

### 知乎 (zhihu)

| 命令 | 用途 | 类型 |
|------|------|------|
| `opencli zhihu hot` | 知乎热榜 | cookie |
| `opencli zhihu search <query>` | 知乎搜索 | cookie |
| `opencli zhihu question <id>` | 问题详情和回答 | cookie |
| `opencli zhihu download --url <URL> --output <DIR> --download-images true` | 下载文章为 Markdown | cookie |
| `opencli zhihu recommend` | 首页推荐 | cookie |
| `opencli zhihu user <username>` | 用户主页资料 | cookie |
| `opencli zhihu user-articles <username>` | 用户文章列表 | cookie |
| `opencli zhihu user-answers <username>` | 用户回答列表 | cookie |
| `opencli zhihu answer-detail <answer_id>` | 单个回答完整内容 | cookie |
| `opencli zhihu collection <collection_id>` | 收藏夹内容 | cookie |
| `opencli zhihu like <id>` | 点赞 | cookie |
| `opencli zhihu follow <id>` | 关注用户/问题 | cookie |

### Bilibili (bilibili)

| 命令 | 用途 | 类型 |
|------|------|------|
| `opencli bilibili hot` | B站热门视频 | cookie |
| `opencli bilibili search <query>` | B站搜索 | cookie |
| `opencli bilibili video <bvid>` | 视频详情 | cookie |
| `opencli bilibili download <URL>` | 下载视频 | cookie |
| `opencli bilibili ranking` | 排行榜 | cookie |
| `opencli bilibili feed` | 首页推荐 | cookie |
| `opencli bilibili user <uid>` | 用户信息 | cookie |
| `opencli bilibili history` | 历史记录 | cookie |

### 小红书 (xiaohongshu)

| 命令 | 用途 | 类型 |
|------|------|------|
| `opencli xiaohongshu hot` | 小红书热门 | cookie |
| `opencli xiaohongshu search <query>` | 搜索笔记 | cookie |
| `opencli xiaohongshu note <id>` | 笔记详情 | cookie |
| `opencli xiaohongshu download <URL>` | 下载笔记（图片/视频） | cookie |
| `opencli xiaohongshu comments <note_id>` | 笔记评论 | cookie |
| `opencli xiaohongshu user <user_id>` | 用户公开笔记 | cookie |

### YouTube (youtube)

| 命令 | 用途 | 类型 |
|------|------|------|
| `opencli youtube search <query>` | 搜索视频 | cookie |
| `opencli youtube video <video_id>` | 视频元数据 | cookie |
| `opencli youtube channel <channel>` | 频道信息 | cookie |
| `opencli youtube transcript <video_id>` | 获取字幕/转录 | cookie |
| `opencli youtube comments <video_id>` | 视频评论 | cookie |
| `opencli youtube feed` | 首页推荐 | cookie |
| `opencli youtube history` | 观看历史 | cookie |
| `opencli youtube playlist <playlist_id>` | 播放列表 | cookie |
| `opencli youtube subscriptions` | 订阅列表 | cookie |

### 微信文章 (weixin)

| 命令 | 用途 | 类型 |
|------|------|------|
| `opencli weixin download --url <URL> --output <DIR>` | 下载文章为 Markdown + 图片 | cookie |

### 抖音 (douyin)

| 命令 | 用途 | 类型 |
|------|------|------|
| `opencli douyin hot` | 抖音热搜 | cookie |
| `opencli douyin search <query>` | 搜索视频 | cookie |
| `opencli douyin video <id>` | 视频详情 | cookie |
| `opencli douyin download <URL>` | 下载视频 | cookie |
| `opencli douyin user <id>` | 用户信息 | cookie |

### Twitter/X (twitter)

| 命令 | 用途 | 类型 |
|------|------|------|
| `opencli twitter search <query>` | 搜索推文 | cookie |
| `opencli twitter thread <id>` | 抓取完整推文串 | cookie |
| `opencli twitter trending` | 热门趋势 | cookie |
| `opencli twitter user <username>` | 用户资料 | cookie |
| `opencli twitter timeline` | 时间线 | cookie |
| `opencli twitter download <URL>` | 下载媒体 | cookie |

> **Twitter Thread/推文串避坑方案**：
> 当使用 `opencli twitter thread` 遇到登录墙或 429 限流时，使用技能内置的免登录并发抓取脚本：
> ```bash
> python3 <SKILL_DIR>/scripts/fetch_twitter_thread.py <URL_or_StatusID>
> ```
> 机制：结合 Twitter Syndication API + `opencli twitter search "from:<author>"` 免登录抓取并自动拼合整个 Thread。


### 雪球 (xueqiu)

| 命令 | 用途 | 类型 |
|------|------|------|
| `opencli xueqiu hot` | 热门动态 | cookie |
| `opencli xueqiu hot-stock` | 热门股票榜 | cookie |
| `opencli xueqiu stock <symbol>` | 股票实时行情 | cookie |
| `opencli xueqiu search <query>` | 搜索股票 | cookie |
| `opencli xueqiu kline <symbol>` | K线数据 | cookie |
| `opencli xueqiu watchlist` | 自选股列表 | cookie |
| `opencli xueqiu fund-snapshot` | 蛋卷基金快照 | cookie |
| `opencli xueqiu feed` | 首页时间线 | cookie |

### Reddit

| 命令 | 用途 | 类型 |
|------|------|------|
| `opencli reddit hot` | Reddit 热门 | cookie |
| `opencli reddit search <query>` | 搜索帖子 | cookie |
| `opencli reddit subreddit <name>` | 子版块内容 | cookie |
| `opencli reddit post <id>` | 帖子详情 | cookie |

### HackerNews

| 命令 | 用途 | 类型 |
|------|------|------|
| `opencli hackernews top --limit <N>` | HN 热门帖子 | public |
| `opencli hackernews new --limit <N>` | HN 最新帖子 | public |
| `opencli hackernews show --limit <N>` | Show HN | public |
| `opencli hackernews ask --limit <N>` | Ask HN | public |
| `opencli hackernews comments <id>` | 帖子评论 | public |

### 微博 (weibo)

| 命令 | 用途 | 类型 |
|------|------|------|
| `opencli weibo hot` | 微博热搜 | cookie |
| `opencli weibo search <query>` | 搜索微博 | cookie |
| `opencli weibo feed` | 首页动态 | cookie |
| `opencli weibo user <id>` | 用户信息 | cookie |

## 桌面应用适配器

| 应用 | 主要命令 | 说明 |
|------|---------|------|
| **Antigravity** | `send`, `read`, `ask`, `model`, `new`, `history` | AI 编辑器控制 |
| **Cursor** | `send`, `read`, `ask`, `model`, `new`, `history` | AI 编辑器控制 |
| **ChatGPT App** | `send`, `read`, `ask`, `model`, `new` | ChatGPT 桌面版控制 |
| **Codex** | `send`, `read`, `ask`, `model`, `new`, `history` | OpenAI Codex 控制 |
| **Discord** | `send`, `read`, `channels`, `servers`, `search` | Discord 桌面版 |

## 外部 CLI 集成

| 工具 | 标识 | 说明 |
|------|------|------|
| `gh` | GitHub CLI | PR、Issues、Releases |
| `docker` | Docker CLI | 容器管理 |
| `obsidian` | Obsidian CLI | 笔记/搜索/标签/任务 |
| `tg` | Telegram CLI | 消息/搜索/导出 |
| `wx` | WeChat CLI | 本地微信数据 |
| `discord` | Discord CLI | 本地同步/搜索/导出 |
| `ntn` | Notion CLI | 页面/数据库/搜索 |
| `longbridge` | 长桥证券 CLI | 行情/交易 |
| `vercel` | Vercel CLI | 部署/域名管理 |
| `wrangler` | Cloudflare CLI | Workers/R2/D1 |

## 浏览器自动化命令 (browser)

当需要操作没有现成适配器的网站时，使用 browser 命令：

```bash
# 打开页面
opencli browser <session> open <url>

# 获取页面状态
opencli browser <session> state

# 点击元素
opencli browser <session> click <selector>

# 输入文本
opencli browser <session> type <selector> <text>

# 填充表单
opencli browser <session> fill <selector> <value>

# 提取内容
opencli browser <session> extract <selector>

# 等待元素
opencli browser <session> wait <selector>

# 截图
opencli browser <session> screenshot

# 执行 JS
opencli browser <session> eval <code>

# Tab 管理
opencli browser <session> tab list
opencli browser <session> tab new [url]
opencli browser <session> tab select <targetId>
opencli browser <session> tab close <targetId>
```

## 命令类型说明

| 类型 | 含义 | 要求 |
|------|------|------|
| `public` | 公开 API，无需登录 | 无 |
| `cookie` | 需要浏览器登录态 | 需安装 Browser Bridge 扩展并登录 |
| `local` | 读取本地数据 | 无 |
| `ui` | 通过 CDP 操作 UI | 需桌面应用运行中 |
| `auto-install` | 首次使用自动安装 | 无 |

## 常用通用参数

| 参数 | 说明 | 示例 |
|------|------|------|
| `--limit <N>` | 限制结果数量 | `opencli hackernews top --limit 5` |
| `--url <URL>` | 指定文章/内容网页链接 | `opencli zhihu download --url "https://zhuanlan.zhihu.com/p/xxx"` |
| `--output <DIR>` | 指定文件/下载保存目录 | `opencli zhihu download --url "https://..." --output /tmp/article` |
| `--download-images <bool>` | 下载文章中的图片 (true/false) | `opencli zhihu download --url "https://..." --download-images true` |
| `-f <fmt>` | 输出格式: `json`, `md`, `csv`, `yaml`, `table` | `opencli xueqiu stock SH600519 -f json` |
| `--profile <name>` | 指定 Chrome 配置名 | `opencli --profile work browser main state` |

## 环境诊断与登录排查工作流

如果命令不工作或提示超时 (`did not render result cards within the timeout`)，按以下步骤排查：

1. **环境诊断**：
   ```bash
   opencli doctor
   ```
2. **账号登录排查**（标注为 `cookie` 类型的站点）：
   - 若遇到 403、429 或卡在无头浏览器渲染，先确认对应站点是否已在 Chrome 浏览器中登录；
   - 支持特定站点的交互式登录命令，例如：
     ```bash
     opencli twitter login
     ```
   - 确认 Chrome 已安装并启用了 OpenCLI Browser Bridge 扩展。

常见问题排查汇总：

| 问题 | 解决方案 |
|------|---------| 
| opencli 未安装 | `npm i -g @jackwener/opencli` |
| 权限错误 EACCES | `sudo chown -R $(whoami) ~/.opencli` |
| Browser Bridge 未连接 | 安装 Chrome 扩展并确保 Chrome 已在后台打开 |
| Node.js 版本过低 | 升级到 Node.js >= 20 |
| cookie 类型命令失败 / 超时 | 需先在浏览器中登录对应网站，或运行 `opencli <site> login` |


## 完整站点覆盖

164 个站点包括但不限于：

**中文站点**：知乎、Bilibili、小红书、微博、抖音、腾讯视频、优酷、爱奇艺、雪球、知识星球、有道、今日头条、豆瓣、掘金、CSDN、简书、36kr、少数派、V2EX、微信读书、喜马拉雅、网易云音乐等

**国际站点**：YouTube、Twitter/X、Reddit、HackerNews、GitHub、Facebook、Instagram、TikTok、Vimeo、Product Hunt、Medium、Dev.to、Stack Overflow、Wikipedia、Google 等

**金融站点**：雪球、Yahoo Finance、长桥证券等

**工具站点**：Z-Library、Yollomi AI、Google Scholar、DeepSeek、Kimi 等
