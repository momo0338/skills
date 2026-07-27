---
name: dy-cli
description: |
  专业的抖音 (Douyin/TikTok China) 命令行工具 (v0.2.2)，支持搜索、无水印下载、热榜、点赞/评论/收藏互动、发布视频图文、直播录制与数据看板分析。
  核心优势：支持短索引（如 `dy search` 搜索后直接 `dy read 1`、`dy dl 1`、`dy like 1`）、格式化导出 (JSON/CSV/YAML)、多账号管理与发布排期。
  适用于抖音视频搜索、无水印视频/图文下载、热榜监控、自动发布与互动、创作者数据分析等场景。
  触发词：dy、dy-cli、抖音命令行、抖音搜索、抖音无水印下载、抖音发布视频、抖音热榜、抖音点赞评论。
version: 0.2.2
---

# dy-cli — 抖音全功能命令行 Skill (v0.2.2)

> 基于 [Youhai020616/douyin](https://github.com/Youhai020616/douyin) 开发，提供搜索、无水印下载、发布、互动、热榜、直播录制与数据分析一站式 CLI 操作。

## 安装与初始化 / Installation

```bash
# 1. pip 安装工具
pip install dy-cli

# 2. 检查版本
dy --version

# 3. 初始化配置与依赖检测 (--skip-login / --skip-chromium / --proxy)
dy init

# 4. 账号登录 (支持标准扫码登录或从浏览器提取已登录 Cookie)
dy login
dy login --browser  # 从已登录抖音的浏览器直接提取 Cookie
```

## 完整命令速查表

| 命令 | 常用选项 / 标志 | 功能与示例 |
|------|----------------|------------|
| `dy status` | `--account <name>` | 查看账号登录状态与 Cookie 文件位置 |
| `dy search` | `--sort [综合\|最多点赞\|最新发布]`<br>`--time [不限\|一天内\|一周内\|半年内]`<br>`--type [general\|video\|user]`<br>`--count <N>` `-o <file>` `--json-output` | 搜索抖音视频/用户<br>示例: `dy search "Codex 教程" --sort 最多点赞 --count 10` |
| `dy detail` | `--comments` `--comment-count <N>` `--json-output` | 查看视频详情 (支持短索引: `dy detail 1` 或 `dy detail <URL>`) |
| `dy download` | `-o <dir>` `--music` `--user` `--limit <N>` `--json-output` | 无水印下载视频/图文<br>示例: `dy dl 1` 或 `dy dl --user <sec_user_id> --limit 10` |
| `dy trending` | `--count <N>` `--watch` `-o <file>` `--json-output` | 查看抖音热榜<br>示例: `dy trending --count 20` 或 `dy trending --watch` |
| `dy like` | `--unlike` `--account <name>` | 点赞/取消点赞视频 (支持短索引: `dy like 1`) |
| `dy favorite` | `--unfavorite` `--account <name>` | 收藏/取消收藏视频 (支持短索引: `dy fav 1`) |
| `dy comment` | `-c "评论内容"` `--account <name>` | 发送视频评论 (支持短索引: `dy comment 1 -c "讲得好"`) |
| `dy comments` | `--count <N>` `--json-output` | 查看视频评论区 (支持短索引: `dy comments 1 --count 20`) |
| `dy follow` | `--unfollow` | 关注/取消关注用户 (`dy follow <sec_user_id>`) |
| `dy profile` | `--posts` `--post-count <N>` `--json-output` | 查看用户主页及作品 (`dy profile <sec_user_id> --posts`) |
| `dy me` | `--json-output` | 查看当前登录账号的个人资料 |
| `dy publish` | `-t <标题>` `-c <正文>` `-v <视频>` `-i <图片>`<br>`--tags <标签>` `--visibility [公开\|好友可见\|仅自己可见]`<br>`--thumbnail <图片>` `--dry-run` `--headless` | 发布视频或图文到抖音<br>示例: `dy publish -t "标题" -c "描述" -v v.mp4 --tags AI` |
| `dy live` | `live info <url>` / `live record <url>` | 查看直播间信息与直播流录制 |
| `dy analytics` | `--csv <path>` `--page-size <N>` `--json-output` | 📊 创作者数据看板分析 |
| `dy notifications` | `--json-output` | 🔔 查看通知消息 |
| `dy account` | `add` / `list` / `default` / `remove` | 多账号添加、切换与管理 |
| `dy config` | `get` / `set` / `show` / `reset` | 管理与配置 CLI 内部参数 |

---

## 核心工作流与短索引机制

`dy-cli` 内置了极便利的**短索引缓存**机制，上一条 `dy search` 产生的列表会缓存编号，后续指令直接传数字即可：

```bash
# 步骤 1：搜索关键词，生成序号 1, 2, 3...
dy search "AI Agent 教程" --sort 最多点赞 --count 10

# 步骤 2：查看第 1 个视频的详细文字与评论
dy detail 1 --comments

# 步骤 3：直接无水印下载第 1 个视频
dy dl 1 -o ~/Downloads/

# 步骤 4：给第 1 个视频点赞与收藏
dy like 1
dy fav 1

# 步骤 5：发表评论
dy comment 1 -c "非常有用的教程，已转发！"
```

---

## 常见场景使用示例

### 1. 高级搜索与结果导出

```bash
# 导出为 JSON 格式文件
dy search "大语言模型" --count 20 -o results.json

# 按热度排序搜索 (注意: --sort 的值为中文选项)
dy search "Python 爬虫" --sort 最多点赞 --count 10

# 按发布时间与搜索类型组合过滤
dy search "Codex 教程" --time 一周内 --type video --count 15
```

### 2. 视频与作者作品批量下载

```bash
# 按短索引单条下载
dy dl 1

# 按 URL 直接下载
dy dl "https://www.douyin.com/video/7657851624437665070"

# 下载视频并同时保存背景音乐
dy dl 1 --music

# 批量下载指定用户的最新 10 个作品 (--user 配合 sec_user_id 和 --limit)
dy dl --user "MS4wLjABAAAA..." --limit 10 -o ~/Downloads/user_videos/
```

### 3. 发布视频/图文与定时排期

```bash
# 发布视频 (设置标题、正文描述、多标签及封面)
dy publish -t "AI Agent 快速入门" -c "手把手带你搭建第一个智能体" -v agent.mp4 --tags AI --tags Agent --thumbnail cover.png

# 发布图文作品 (传递多个 -i 图片参数)
dy publish -t "极简风摄影技巧" -c "用手机拍出大片感" -i img1.jpg -i img2.jpg --visibility 公开

# 预览排期任务 (--dry-run 不实际提交)
dy publish -t "预发布内容" -v video.mp4 --schedule "2026-03-16T10:00:00+08:00" --dry-run
```

---

## 故障排除与登录诊断工作流

1. **执行前 / 出错时优先诊断登录状态**：
   - 运行 `dy status` 检查 Cookie 验证状态。
   - 若提示未登录或 Cookie 过期，优先引导或运行：
     - `dy login`（弹窗/扫码登录）
     - `dy login --browser`（直接从浏览器提取 Cookie，免扫码）
2. **处理网络与沙盒阻断 (HTTP 403)**：
   - 在 AI Agent / CLI 环境中运行 `dy` 命令时，需开启网络提权 (Bypass Sandbox)，避免因网络隔离阻断官方 API (`https://www.douyin.com/aweme/v1/...`)。
3. **处理风控人机验证 (`verify_check`)**：
   - 若输出 `verify_check detected` 提示，说明触发了极验/滑块验证码。请先运行 `dy status` 确认登录状态，或通过 `dy login` / `dy login --browser` 重新更新合法的用户凭证。
