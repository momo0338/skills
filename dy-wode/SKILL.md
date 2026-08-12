---
name: dy-wode
description: |
  整理抖音登录账号「我的」数据：消息/私信、喜欢、收藏、观看历史、稍后再看。
  用 ego-browser 继承登录态采集作品 ID，用 dy-cli 登录凭证批量取 视频名称/作者/发布时间/点赞/评论/收藏/转发，
  按分类输出 Markdown 表格与 CSV/JSON。
  当用户要求查看或整理自己抖音账号的喜欢、收藏、观看历史、稍后再看、私信视频，
  或把「我的」数据导出成表格时使用。
  触发词：dy-wode、抖音我的、我的喜欢、我的收藏、观看历史、稍后再看、抖音私信视频、抖音个人数据整理、抖音作品统计表。
---

# dy-wode — 抖音「我的」个人数据整理

## 快速开始

运行主脚本（默认全部分类，终端打印 Markdown 表格）：

```bash
python3 "$SKILL_DIR/scripts/dy_wode.py"
```

常用变体：

```bash
# 只列 ID 与卡片文本（最快，不取统计、不写文件）
python3 dy_wode.py --list-only

# 指定分类 + 写 md/csv/json 到输出目录
python3 dy_wode.py --categories like,favorite,record --out ~/Desktop/dy-wode

# 消息分类：指定私信会话（近 2 天）；先 --list-convs 看会话，再用 --conv 或 --index
python3 dy_wode.py --categories message --conv "会话昵称" --days 2 --out ~/Desktop/dy-wode
python3 dy_wode.py --list-convs

# 每类限量
python3 dy_wode.py --categories like,favorite --limit 20 --out ~/Desktop/dy-wode

# 采集缓存 + 中断续跑（先跑一次落盘，中断后加 --resume 续跑）
python3 dy_wode.py --cache-dir ~/.cache/dy-wode --out ~/Desktop/dy-wode
python3 dy_wode.py --resume --out ~/Desktop/dy-wode

# 喜欢是大列表（实测 4500+ 条），完整采集要给足预算
python3 dy_wode.py --categories like --max-steps 3000 --tab-timeout 3600 --out ~/Desktop/dy-wode

# 把生成的 dy_wode.json 转成多工作表 Excel（每分类一页 + 汇总）
python3 "$SKILL_DIR/scripts/export_xlsx.py" ~/Desktop/dy-wode/dy_wode.json
```

分类键：`like` 喜欢、`favorite` 收藏、`record` 观看历史、`watch_later` 稍后再看、`message` 消息/私信。

## 流程

1. **采集**：`scripts/dy_wode.py` 用 ego-browser 打开个人中心各分类页
   （`https://www.douyin.com/user/self?showTab=<分类>`），滚动加载全部卡片并从 `/video/{id}`、`/note/{id}`
   链接提取作品 ID；「消息」分类调用 `scripts/im_videos.py` 从私信会话提取近 N 天视频（复用已固化的消息采集逻辑）。
2. **统计**：用 dy-cli 登录凭证调用批量详情接口 `multi/aweme/detail`（每批约 40 个 ID），取回
   视频名称、作者、发布时间、点赞数、评论数、收藏数、转发数；缺失时回退单条 detail。
3. **输出**：按分类整理为表格，终端打印 Markdown，`--out` 时写 `dy_wode.md` / `dy_wode.csv` / `dy_wode.json`。

## 依赖与登录态

- ego lite（`ego-browser` CLI，默认 `/Users/zhugx/.local/bin/ego-browser`，可用 `EGO_BROWSER` 覆盖）：
  抖音网页需已登录，登录态由 ego-browser 继承，无需额外处理。
- dy-cli（`dy login` 已登录）：提供详情接口签名与 Cookie。未登录时脚本会报错，先运行 `dy login`。

## 注意事项

- 全程只读：不发送消息、不点赞、不评论、不取消收藏，不做任何状态变更。
- 抖音网页会 A/B 切换界面，网格 UL 保留全部已加载项，脚本滚动触发分页后一次性读取 UL；
  若某分类采到 0 条或明显偏少，重跑一次（或先用 `--list-only` 看采集数）。
- **风控/验证码**：连续高频运行会触发抖音验证码，页面网格不再渲染（表现为采到 0 条并提示警告）。
  遇到时立即停止，冷却数小时再跑；常规使用默认 `--pace 3` 在分类间加冷却，不要并行多个采集进程。
- **大列表预算**：喜欢列表可能数千条，完整采集需要 `--max-steps` 给足步数、`--tab-timeout` 给足超时
  （默认 1200 步/30 分钟）；输出里会显示“已到底”或“步数预算用尽，可能不完整！”，据此判断是否完整。
- **中断续跑**：加 `--cache-dir` 会逐分类落盘；中断后加 `--resume` 重跑会复用已完成分类，只补缺的。
- 消息分类按自然日过滤（`--days 2` = 昨天 00:00 至今）；每个会话约 3–4 分钟（需滚动加载历史消息）。
- 批量统计请求带登录 Cookie 即可（无需 Playwright 签名），每批 40 条约 1 秒；
  大批量（数百条）时间很短，仍可先用 `--limit` 限量。
- 详情缺失（视频已删除/不可见）时统计字段为 0，名称回退为卡片文本。
- `--fast-scroll` 用程序化 scrollTop 滚动（更快），但分页触发未经充分实测，遇到漏采请回退到默认滚轮模式。

## 参考资料

- 分类页面 URL、DOM 结构、接口与故障排查：见 [references/pages.md](references/pages.md)。
- 私信采集细节（消息面板新旧 UI、会话选择、时间标签解析）：见 `scripts/im_videos.py` 头部说明。
