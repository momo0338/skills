---
name: mp-search
version: 3.2.0
description: 微信公众号文章与官方标准短链检索采集技能。支持八个 CLI 子命令：全网文章关键词检索（search，微信端/公众平台/搜狗三级降级）、公众号主体搜索（biz：fakeid/微信号/认证）、指定公众号历史推文与号内关键词过滤（account）、合集整卷抓取（album，零凭据）、搜一搜互动指标 Markdown 对比表（format），以及通道 E 搜狗真实链解析+正文 Markdown+主体反查（sogou / who / content）。
homepage: https://github.com/zhugx/skills
metadata: {"openclaw":{"emoji":"⚡","requires":{"bins":["python3"]}}}
---

# MP-Search: 微信文章检索、公众号主体/合集采集与正文 Markdown 提取技能 (v3.2)

## 一、概述

本技能专为**高效率、轻量化、多层级**的微信公众号文章检索与短链采集场景打造，共 8 个 CLI 子命令，分两套体系：

- **原有三级自适应检索引擎（通道 A ➜ B ➜ C）**：`search` 关键词检索，按环境可用性自动降级；配套 `biz` / `account` / `album` / `format`。
- **通道 E（2026-11-09 新增，零凭据免费链路）**：`sogou` / `who` / `content`，从搜狗入口贯通到文章正文 Markdown，不依赖微信客户端与后台登录态。详见 §6。

1. **三级关键词检索（Search）** ✅：
   - **通道 A（高精需求 · macOS 微信桌面端搜一搜直读）**：针对 S 级核心选题，直接联动 macOS 微信桌面端「搜一搜」窗口（`微信 (窗口)`），深度获取正文底部**真实阅读量（10w+ / 2.8w）、点赞数、转发数、收藏数**与官方短链（`mp.weixin.qq.com/s/...`），是高精对标的首选通道。
   - **通道 B（轻量高效 · 公众平台超链接接口）**：通过公众平台有效会话（`appmsg?action=search_biz`），免客户端窗口秒级获取官方标题、公众号名与官方短链。
   - **通道 C（自动兜底 · 搜狗开放检索 opencli）**：当桌面端与后台通道未就绪时自动平滑降级，获取前排收录标题与核心摘要，表格自适应聚焦于「爆点切入与长尾分析」，不暴露无效数据。
2. **公众号主体精准搜索（Biz Search）** ✅ 真实可用：输入任意名称或关键词，直接调用公众平台 `searchbiz` 接口检索认证公众号列表，秒级输出 `fakeid`、微信号（Alias）、头像与认证描述（已现场实测验通）。
3. **指定公众号号内推文拉取（Account & Query）** ⛔ 当前不可用：微信公众平台服务端对他人账号的 `appmsg?action=list_ex` 与 `appmsgpublish` 接口已施加全域频控拦截（返回 `ret: 200013 freq control`），目前仅能拉取自己账号的历史发表，无法通过该接口批量拉取外部公众号的文章列表。
4. **公众号合集整卷抓取（Album Fetcher）** ✅：直接调用微信公开的合集 JSON 接口，**无需登录、零凭据**，极速抓取指定合集内几十到上百篇推文的标题、官方链接、发布时间，并生成 Markdown 索引表。
4. **全维度互动数据格式化（Format）** ✅：自适应格式化输出 Markdown 对比总表，端内通道展示完整阅读量/点赞，降级通道展示摘要/切入点。

---

## 二、CLI 快速使用指南

统一入口脚本：`scripts/mp_search.py`

### 1. 关键词全网检索（最热 / 最新）

```bash
# 检索「最新」发布的 5 篇文章并保存为 JSON
python3 scripts/mp_search.py search "hypit" -s new -n 5 -o /tmp/hypit_new.json

# 在指定公众号内定向检索关键词（走公众平台官方接口）
python3 scripts/mp_search.py search "招聘" --account "江苏国资" -n 10

# 检索「最热」文章并同步生成 Markdown 对比总表
python3 scripts/mp_search.py search "hypit" -s hot -n 5 --format-md /tmp/hypit_hot.md

# 终端直接查看对比表
python3 scripts/mp_search.py search "Recordly" -n 5
```

**参数说明**：
- `keyword`：搜索关键词（必填）
- `--account`：限定在指定公众号内精确检索（官方公众平台通道）
- `-s, --sort`：排序方式，`hot`（最热/综合相关，默认）或 `new`（最新时效）
- `--engine`：检索引擎通道，`auto`（默认，优先微信端，失败自动降级到 opencli）、`wechat`（强制微信端）、`opencli`（强制走搜狗开放搜索）
- `-n, --limit`：返回条数（默认 10）
- `-o, --output`：输出标准化 JSON 文件路径（包含 keyword、rank_type、channel 与 items 列表）
- `--format-md`：同步输出 Markdown 对比表格文件路径

---

### 2. 搜索公众号主体（获取 fakeid、微信号与认证状态）

```bash
# 搜索公众号主体信息
python3 scripts/mp_search.py biz "江苏国资" -n 5

# 搜索并导出 JSON
python3 scripts/mp_search.py biz "金陵人才" -o /tmp/jinling.json
```

---

### 3. 指定公众号推文获取与号内关键词搜索

```bash
# 获取指定公众号最近 50 篇文章
python3 scripts/mp_search.py account "江苏国资" -n 50 -o articles.json

# 在指定公众号内按关键词过滤推文（如只看招聘公告）
python3 scripts/mp_search.py account "江苏国资" -q "招聘" -n 20
```

---

### 4. 抓取公众号合集（Album）整卷文章

```bash
python3 scripts/mp_search.py album "https://mp.weixin.qq.com/mp/appmsgalbum?__biz=xxx&album_id=xxx"
```

**参数说明**：
- `-o, --output`：输出目录（默认 `./weixin-albums`）
- `-b, --batch-size`：每页获取数量（默认 20，最大 20）

---

### 5. 搜一搜全维度互动数据表格格式化

将桌面搜一搜（包含真实阅读量、点赞数等）采集到的 JSON 数据渲染为标准的 Markdown 对比总表：

```bash
python3 scripts/mp_search.py format data.json -o report.md
```

---

### 6. 通道 E：搜狗 → 官方签名链 → 正文 Markdown（2026-11-09 新增并实测通过）

```bash
# 搜索文章并解析出可访问的链接（默认不抓正文）
python3 scripts/mp_search.py sogou "南京 遛娃" -n 5

# 同时抓取前 3 篇正文 Markdown，导出 JSON + Markdown 表格
python3 scripts/mp_search.py sogou "南京 遛娃" -n 5 --with-body --body-limit 3 \
  -o /tmp/sogou.json --format-md /tmp/sogou.md

# 直接抓单篇正文（输出纯 Markdown）
python3 scripts/mp_search.py content "https://mp.weixin.qq.com/s?src=11&..." -o /tmp/article.json

# 按关键词反查公众号主体（搜狗 type=1 已全域失效的免费替代方案）
python3 scripts/mp_search.py who "南京 遛娃" -n 5 --probe 6 -o /tmp/who.json
```

**实现要点**（脚本 `scripts/sogou_channel_e.py`，仅依赖 `requests` + `lxml`）：
- **自持会话**：先访问搜狗首页拿当前 IP 的 `ABTEST/SUID/SNUID`，不使用任何硬编码 Cookie；
  搜狗 `SNUID` 与 IP 绑定，硬编码别人的 Cookie 会直接触发验证码。
- **反爬检测**：命中 `antispider` / `seccoderight` / `anti.min.css` 时抛明确错误并停，
  不做打码或代理绕过；默认请求间隔 1.2 秒，可用 `--delay` 调整。
- **正文双路兜底**：微信新版文章页已移除 DOM 中的 `js_content`，正文改存于
  `window.cgiDataNew.content_noencode`。先试 `js_content`，失败自动回落 SSR 数据并还原 `\xHH` 转义。
  实测两路都命中过，正文成功率从原项目的 2/5 提升到 3/3（限定抓取篇数内）。
- **图片**：优先取 `data-src`（微信正文懒加载），转成标准 `![](url)` Markdown。
- **签名链时效**：输出的 `kind` 为 `signed_temporary` 时，附带 `signed_at`、`expires_at`、
  `archivable: false`、`expiry_risk`。**这不是官方永久短链**，`timestamp` 是签名生成时刻，
  约 2 小时后失效；禁止入库归档、禁止作为长期引用链接。仅 `kind=permanent_short` 才可归档。
- **文章时效**：每条结果带 `age_days` / `freshness`（`fresh` ≤90 天、`normal` ≤365 天、`old` 更久）。
  搜狗「综合」排序会混入多年前的老文（实测「南京 中考」返回 2020/2021 年的作文题），
  **做选题监控时务必先看 `freshness`，不要默认结果都是近期内容**。
- **主体反查**：`who` 从文章页抽取 `nick_name` / `user_name`(gh_) / `bizuin` / 头像聚合去重，
  输出命中文章样例。注意搜狗列表里的 `all-time-y2` 常是显示名，**主体名以文章页 `nick_name` 为准**。

---

## 三、双轨工作流说明

- **日常快速调研 / gh-write 技术专栏对标**：直接使用 `python3 scripts/mp_search.py search "<关键词>" -s hot/new -o ...`，秒级产出近期公众讨论热点与标题模式；
- **深度竞品拆解 / 真实阅读量审计**：在具备桌面微信的环境中，通过桌面端搜一搜进入文章底部采样阅读量、点赞数，点击「••• -> 复制链接」获取标准短链，最后由 `mp_search.py format` 汇总出具交付级报告。

---

## 四、⚠️ 通道可用性现状（2026-09-16 实测，2026-11-09 补充复测；先看这条再决定用哪条）

| 通道 | 状态 | 说明 |
|---|---|---|
| A 微信桌面端搜一搜 | ❌ 多数环境不可用 | 依赖 `微信 (窗口)`，**只有 ChatGPT / Antigravity 环境能调**；WorkBuddy / Codex 下报"未就绪"并自动降级 |
| B 公众平台接口 · 账号搜索 (searchbiz) | ✅ 真实可用 | 依赖后台登录态。可秒级检索已认证公众号列表，拿到精确 fakeid、微信号（已实测验证）。本机需先 `pip install playwright && playwright install chromium` |
| B 公众平台接口 · 外部文章拉取 (list_ex) | ⛔ 微信服务端拦截 | 依赖后台登录态，但腾讯目前对所有外部账号列表返回 `ret: 200013 freq control`，无法拉取他号文章 |
| C 搜狗开放检索（`opencli weixin search`） | ❌ 命令本身超时不可用 | 实测 `TIMEOUT: weixin/search timed out after 60s`，exit 69 / 75 / 137；`OPENCLI_BROWSER_COMMAND_TIMEOUT=200` 调大后仍被终止。**但 `mp_search.py` 内置的 HTTP 兜底 `search_via_sogou_http` 在 2026-11-09 复测可用**，能返回标题/号名/摘要（无发布时间、无阅读量） |
| **E 搜狗真实链 + 正文 + 主体反查** | ✅ 2026-11-09 实测通过 | 新增 `sogou` / `who` / `content` 三个子命令。签名链 4/4 解析成功、正文 3/3 抓取成功、主体反查拿到 3 个真实 `user_name`/`bizuin`。见本文 §6 |
| 搜狗公众号主体搜索（type=1） | ⛔ 已全域失效 | 2026-11-09 实测「十点读书」「南京本地宝」等均返回"暂无相关的官方认证订阅号"。改走 `who` 反查 |

**由此推出的作业原则**：
1. **不要因为通道失效就跳过"爆款对标"这一步**——见 `guide-write` §0.3 的合规替代方案：
   **用本号后台「发表记录」的真实互动数据做同题材对标**（可信度与可比性都高于搜狗降级数据），
   再用 `WebSearch` 补公开渠道的套路观察；**正文对标块里如实写明降级原因与缺失指标**。
2. 需要端内真实互动数据时，**先出「对标采集清单」交给朱总在 ChatGPT / Antigravity 环境跑**，回传后用 `format` 渲染。
3. 复测命令（判定通道是否恢复）：
   ```bash
   OPENCLI_BROWSER_COMMAND_TIMEOUT=200 /usr/local/bin/opencli weixin search "测试词" --limit 3
   # 返回 ok:true 即恢复；TIMEOUT 则仍不可用
   ```
