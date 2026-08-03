---
name: dy-cli
description: |
  专业的抖音 (Douyin/TikTok China) 命令行工具，支持搜索、无水印下载、元数据归档、热榜、点赞/评论/收藏互动、发布视频图文、直播录制与数据看板分析。
  核心优势：支持短索引（如 `dy search` 搜索后直接 `dy read 1`、`dy dl 1`、`dy like 1`）、格式化导出 (JSON/CSV/YAML)、多账号管理与发布排期。
  适用于抖音视频搜索、无水印视频/图文下载、作品及作者元数据下载、单一 JSON 侧车归档、批量归档、热榜监控、自动发布与互动、创作者数据分析等场景。
  触发词：dy、dy-cli、抖音命令行、抖音搜索、抖音无水印下载、抖音元数据、抖音归档、抖音发布视频、抖音热榜、抖音点赞评论。
---

# dy-cli — 抖音全功能命令行 Skill (v0.2.2)

> 基于 [Youhai020616/douyin](https://github.com/Youhai020616/douyin) 开发，提供搜索、无水印下载、发布、互动、热榜、直播录制与数据分析一站式 CLI 操作。

## 明确作品 ID 下载快速路径（最高优先级）

当用户要求下载单个视频，且输入包含一个 15–25 位纯数字作品 ID 时，立即执行本节；不要进入搜索、短索引或通用故障诊断流程。

1. 将数字原样作为 `aweme_id`，不要搜索作品、匹配标题、查询短索引、拼接作品链接、解析跳转、预查详情或预检登录状态。
2. 将输出目录设为用户指定的绝对路径；用户未指定时，使用当前任务目录下的 `downloads/<aweme_id>/`。
3. 直接运行以下命令。脚本会下载视频并生成用于哈希、大小和媒体探测校验的 `.metadata.json`；除非用户明确要求，否则不要增加 `--archive`、封面、头像、音乐、评论或原始详情。

```bash
python "$SKILL_DIR/scripts/download_with_metadata.py" \
  "<aweme_id>" \
  -o "<absolute-output-dir>"
```

4. 在已知网络受限的代理环境中，首次执行即申请完成该命令所需的最小网络权限，不要先等待 DNS、连接或 403 重试失败。若环境是否受限未知，保持同一命令和同一 ID 取得权限后重试。
5. 仅在真实返回未登录、Cookie 过期或 `verify_check` 时运行 `dy status` 或登录诊断；不要把这些检查作为下载前置步骤。
6. 成功后优先读取脚本生成的 `.metadata.json` 核对作品 ID、媒体状态、格式、大小、哈希和可用的 `ffprobe` 结果；仅在元数据缺项时补充运行 `file`、`du` 或 `ffprobe`。
7. 向用户返回视频文件、绝对输出目录、格式、大小和时长。不要展开后台规则读取或本地说明检索过程。

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
| `dy download` | `-o <dir>` `--music` `--user` `--limit <N>` `--json-output` | 普通无水印下载视频/图文<br>示例: `dy dl 1` 或 `dy dl <sec_user_id> --user --limit 10` |
| 技能归档脚本 | `--archive` `--cover` `--avatar` `--music` `--include-raw` `--comments <N>` `--user` `--favorite` `--mix` `--limit <N>` | 下载作品 (含实况动图提取)，并为每个作品生成一个统一的 `.metadata.json` |
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
dy dl "MS4wLjABAAAA..." --user --limit 10 -o ~/Downloads/user_videos/
```

### 3. 视频与元数据统一归档

明确作品 ID 的单视频下载始终优先使用上述快速路径。其他普通媒体下载使用 `dy dl`。当用户要求元数据、归档、原始详情、封面、头像、评论、本地文件哈希或可恢复下载时，使用技能目录中的 `scripts/download_with_metadata.py`，不要修改已安装的 `dy_cli` 包。

按以下固定顺序识别单作品输入，不要先搜索标题，也不要手工改写链接：

| 输入 | 识别规则 | 处理路径 |
|------|----------|----------|
| 明确作品 ID | 15–25 位纯数字，例如 `7635914294399817961` | 直接作为 `aweme_id` 获取详情，不访问短索引缓存，不解析跳转 |
| 正式作品链接 | `douyin.com/video/<ID>`、`iesdouyin.com/share/video/<ID>` 或 `douyin.com/note/<ID>` | 从路径直接提取 ID，不发起跳转请求 |
| 短链接 | `v.douyin.com/<token>/` | 将原短链接交给 `dy-cli` 解析 302 跳转，取得 ID 后获取详情 |
| 整段分享口令 | 文本中包含上述抖音链接 | 先提取第一个受信任的抖音链接，再按正式链接或短链接路径处理 |
| 搜索短索引 | 较短的数字，例如搜索结果中的 `1` | 先查 `dy search` 缓存；缓存值再按正式链接或短链接路径处理 |

只接受 `douyin.com`、其子域名、`iesdouyin.com` 及其子域名中的 HTTP(S) 链接。短链接解析失败时，报告原短链接和网络/登录错误；不要回退到标题搜索，因为搜索结果可能对应错误作品。若运行环境因网络隔离报 DNS、连接或 403 错误，保持同一条命令和原始输入，在取得网络授权后重试。

先解析当前 `SKILL.md` 所在目录为 `SKILL_DIR`，再运行：

```bash
# 明确作品 ID：直接获取，不走短链接解析
python "$SKILL_DIR/scripts/download_with_metadata.py" \
  "7635914294399817961" \
  -o /absolute/output/path

# 视频/图文 + 一个标准化 metadata.json
python "$SKILL_DIR/scripts/download_with_metadata.py" \
  "https://www.douyin.com/video/7657851624437665070" \
  -o /absolute/output/path

# 短链接：脚本内部解析跳转，不要预先手工 curl 或拼正式链接
python "$SKILL_DIR/scripts/download_with_metadata.py" \
  "https://v.douyin.com/lSvQylqiJwA/" \
  -o /absolute/output/path

# 整段分享口令：可原样传入，脚本先提取其中的抖音链接
python "$SKILL_DIR/scripts/download_with_metadata.py" \
  "7.17 03/15 N@j.cA :0pm VyT:/ 开甲陀螺 https://v.douyin.com/lSvQylqiJwA/ 复制此链接，打开Dou音搜索" \
  -o /absolute/output/path

# 完整媒体归档：增加封面、头像和音乐
python "$SKILL_DIR/scripts/download_with_metadata.py" \
  "https://www.douyin.com/video/7657851624437665070" \
  -o /absolute/output/path \
  --archive

# 仅在调试或研究接口结构时显式保存脱敏原始详情
python "$SKILL_DIR/scripts/download_with_metadata.py" \
  "https://www.douyin.com/video/7657851624437665070" \
  -o /absolute/output/path \
  --archive --include-raw

# 评论必须显式请求；评论接口失败时保留媒体并标记 partial
python "$SKILL_DIR/scripts/download_with_metadata.py" 1 \
  -o /absolute/output/path \
  --archive --comments 100

# 二级评论：--reply-depth 默认 1（一级评论+每条回复），--reply-depth 0 仅一级
python "$SKILL_DIR/scripts/download_with_metadata.py" 1 \
  -o /absolute/output/path \
  --archive --comments 100 --reply-depth 1
# 评论采集降级链（metadata.comments.source 标记来源）：
#   1. douyin      dy-cli 原生签名接口
#   2. douyin_web  内置 a_bogus 签名 + Cookie（vendor/abogus.py，零第三方依赖）
#   3. iesdouyin   分享 API 免签名（最终兜底）

# 批量归档用户作品
python "$SKILL_DIR/scripts/download_with_metadata.py" "MS4wLjABAAAA..." \
  --user --limit 20 \
  -o /absolute/output/path \
  --archive

# 批量归档用户喜欢/收藏的作品 (依赖已登录的关联账号 Cookie)
python "$SKILL_DIR/scripts/download_with_metadata.py" "MS4wLjABAAAA..." \
  --favorite --limit 20 \
  -o /absolute/output/path \
  --archive

# 批量归档合集作品 (传入 mix_id 或合集内任一作品的分享链接)
python "$SKILL_DIR/scripts/download_with_metadata.py" "https://www.douyin.com/video/7657851624437665070" \
  --mix --limit 50 \
  -o /absolute/output/path \
  --archive

# 实况照片 (Live Photo) 的提取说明
# 如果目标作品是“实况图集”，本脚本会自动提取出各帧背后的动态 `.mp4` 视频部分，而抛弃纯静态的封面图，从而实现实况动态媒体的无损下载。
```

每个作品只生成一个 JSON：

```text
<aweme_id>_<title>.video.mp4
<aweme_id>_<title>.cover.jpg
<aweme_id>_<title>.music.m4a
<aweme_id>_<title>.metadata.json
```

归档脚本必须遵守：

1. 保持作品 ID 为文件名前缀，避免标题碰撞。
2. 在 JSON 中使用相对文件路径，并记录大小、SHA-256 与可用的 `ffprobe` 探测结果。
3. 将隐藏或不可信的播放量保存为 `null`，不要把接口返回的 `0` 当作真实零播放。
4. 默认及 `--archive` 均不保存原始详情；仅在显式指定 `--include-raw` 时保存脱敏后的 `raw`。
5. 将评论数量、游标、是否还有下一页及部分失败状态一并保存。
6. 对每次阶段结果原子更新 JSON；整体状态使用 `complete`、`partial` 或 `failed`。
7. 返回码 `0` 表示完成，`2` 表示媒体完成但附加项部分失败，`1` 表示主要下载失败。
8. 批量下载保持串行，避免增加风控概率。下载完成后报告绝对输出目录，并核对媒体数量、格式与大小。
9. 精简常规元数据：不要保存重复时间戳、平台内部推荐指标、无用作者内部 ID 或未请求评论的空结构。

脚本当前验证兼容 `dy-cli 0.2.2`。检测到其他版本时应停止并说明；只有用户明确接受兼容风险时才使用 `--allow-unsupported-version`。

### 4. 发布视频/图文与定时排期

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

1. **仅在下载返回登录或风控错误后诊断登录状态**：
   - 明确作品 ID 下载不得预先运行 `dy status`。
   - 运行 `dy status` 检查 Cookie 验证状态。
   - 若提示未登录或 Cookie 过期，优先引导或运行：
     - `dy login`（弹窗/扫码登录）
     - `dy login --browser`（直接从浏览器提取 Cookie，免扫码）
2. **处理网络与沙盒阻断 (HTTP 403)**：
   - 在 AI Agent / CLI 环境中运行 `dy` 命令时，需开启网络提权 (Bypass Sandbox)，避免因网络隔离阻断官方 API (`https://www.douyin.com/aweme/v1/...`)。
3. **处理风控人机验证 (`verify_check`)**：
   - 若输出 `verify_check detected` 提示，说明触发了极验/滑块验证码。请先运行 `dy status` 确认登录状态，或通过 `dy login` / `dy login --browser` 重新更新合法的用户凭证。
