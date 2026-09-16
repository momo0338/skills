---
name: mp-search
version: 3.1.0
description: 微信公众号文章与官方标准短链检索采集技能。支持四维一体：全网文章关键词检索（search：支持最热/最新时效）、搜一搜全维度互动指标对比（原生取链+format）、公众号合集（album：公开API免登录）以及公众平台号内历史文章批量获取（account：永久短链）。
homepage: https://github.com/zhugx/skills
metadata: {"openclaw":{"emoji":"⚡","requires":{"bins":["python3"]}}}
---

# MP-Search: 微信搜一搜检索、公众号合集与号内推文极速采集技能 (v3.1)

## 一、概述

本技能专为**高效率、轻量化、多层级**的微信公众号文章检索与短链采集场景打造，整合四大核心能力，构建**三级自适应检索引擎（通道 A ➜ 通道 B ➜ 通道 C）**：

1. **三级关键词检索（Search）** ✅：
   - **通道 A（高精需求 · macOS 微信桌面端搜一搜直读）**：针对 S 级核心选题，直接联动 macOS 微信桌面端「搜一搜」窗口（`微信 (窗口)`），深度获取正文底部**真实阅读量（10w+ / 2.8w）、点赞数、转发数、收藏数**与官方短链（`mp.weixin.qq.com/s/...`），是高精对标的首选通道。
   - **通道 B（轻量高效 · 公众平台超链接接口）**：通过公众平台有效会话（`appmsg?action=search_biz`），免客户端窗口秒级获取官方标题、公众号名与官方短链。
   - **通道 C（自动兜底 · 搜狗开放检索 opencli）**：当桌面端与后台通道未就绪时自动平滑降级，获取前排收录标题与核心摘要，表格自适应聚焦于「爆点切入与长尾分析」，不暴露无效数据。
2. **公众号合集整卷抓取（Album Fetcher）** ✅：直接调用微信公开的合集 JSON 接口，**无需登录、零凭据**，极速抓取指定合集内几十到上百篇推文的标题、官方链接、发布时间，并生成 Markdown 索引表。
3. **指定公众号历史推文批量获取（MP Account History）** ⚠️ 需扫码：通过微信公众平台超链接接口，按公众号名称搜索并批量提取该账号近期或历史发布的全部推文与官方短链。
4. **全维度互动数据格式化（Format）** ✅：自适应格式化输出 Markdown 对比总表，端内通道展示完整阅读量/点赞，降级通道展示摘要/切入点。

---

## 二、CLI 快速使用指南

统一入口脚本：`scripts/mp_search.py`

### 1. 关键词全网检索（最热 / 最新）

```bash
# 检索「最新」发布的 5 篇文章并保存为 JSON
python3 scripts/mp_search.py search "hypit" -s new -n 5 -o /tmp/hypit_new.json

# 检索「最热」文章并同步生成 Markdown 对比总表
python3 scripts/mp_search.py search "hypit" -s hot -n 5 --format-md /tmp/hypit_hot.md

# 终端直接查看对比表
python3 scripts/mp_search.py search "Recordly" -n 5
```

**参数说明**：
- `keyword`：搜索关键词（必填）
- `-s, --sort`：排序方式，`hot`（最热/综合相关，默认）或 `new`（最新时效）
- `--engine`：检索引擎通道，`auto`（默认，优先微信端，失败自动降级到 opencli）、`wechat`（强制微信端）、`opencli`（强制走搜狗开放搜索）
- `-n, --limit`：返回条数（默认 10）
- `-o, --output`：输出标准化 JSON 文件路径（包含 keyword、rank_type、channel 与 items 列表）
- `--format-md`：同步输出 Markdown 对比表格文件路径

---

### 2. 抓取公众号合集（Album）整卷文章

```bash
python3 scripts/mp_search.py album "https://mp.weixin.qq.com/mp/appmsgalbum?__biz=xxx&album_id=xxx"
```

**参数说明**：
- `-o, --output`：输出目录（默认 `./weixin-albums`）
- `-b, --batch-size`：每页获取数量（默认 20，最大 20）

---

### 3. 批量获取指定公众号的历史推文

```bash
# 获取指定公众号最近 50 篇文章
python3 scripts/mp_search.py account "目标公众号名称" -n 50 -o articles.json
```

---

### 4. 搜一搜全维度互动数据表格格式化

将桌面搜一搜（包含真实阅读量、点赞数等）采集到的 JSON 数据渲染为标准的 Markdown 对比总表：

```bash
python3 scripts/mp_search.py format data.json -o report.md
```

---

## 三、双轨工作流说明

- **日常快速调研 / gh-write 技术专栏对标**：直接使用 `python3 scripts/mp_search.py search "<关键词>" -s hot/new -o ...`，秒级产出近期公众讨论热点与标题模式；
- **深度竞品拆解 / 真实阅读量审计**：在具备桌面微信的环境中，通过桌面端搜一搜进入文章底部采样阅读量、点赞数，点击「••• -> 复制链接」获取标准短链，最后由 `mp_search.py format` 汇总出具交付级报告。

---

## 四、⚠️ 通道可用性现状（2026-09-16 实测，先看这条再决定用哪条）

| 通道 | 状态 | 说明 |
|---|---|---|
| A 微信桌面端搜一搜 | ❌ 多数环境不可用 | 依赖 `微信 (窗口)`，**只有 ChatGPT / Antigravity 环境能调**；WorkBuddy / Codex 下报"未就绪"并自动降级 |
| B 公众平台超链接接口 | ⚠️ 需扫码 | 依赖后台登录态，登录过期即失效 |
| C 搜狗开放检索（`opencli weixin search`） | ❌ **当前超时不可用** | 实测 `TIMEOUT: weixin/search timed out after 60s`，exit 69 / 75 / 137；`OPENCLI_BROWSER_COMMAND_TIMEOUT=200` 调大后仍被终止。**命令本身在 PATH 里，不是"找不到命令"问题** |

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
