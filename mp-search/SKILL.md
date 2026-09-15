---
name: mp-search
version: 3.1.0
description: 微信公众号文章与官方标准短链检索采集技能。支持四维一体：全网文章关键词检索（search：支持最热/最新时效）、搜一搜全维度互动指标对比（原生取链+format）、公众号合集（album：公开API免登录）以及公众平台号内历史文章批量获取（account：永久短链）。
homepage: https://github.com/zhugx/skills
metadata: {"openclaw":{"emoji":"⚡","requires":{"bins":["python3"]}}}
---

# MP-Search: 微信搜一搜检索、公众号合集与号内推文极速采集技能 (v3.1)

## 一、概述

本技能专为**高效率、轻量化**的微信公众号文章检索与短链采集场景打造，整合四大核心数据获取能力：

1. **关键词检索（Search，微信优先 + opencli 降级）** ✅：
   - **默认优先走微信端原生搜索**（公众平台超链接检索接口 / 微信搜一搜），获取微信官方标准短链（`https://mp.weixin.qq.com/s/...`）与真实公众号名称；
   - **自动降级兜底**：当微信端通道未就绪、无登录凭据或异常时，自动无缝降级为 `opencli weixin search`（搜狗微信开放接口）；
   - **透明化数据源标注**：格式化输出时严格区分渠道，若降级走搜狗，明确标注“搜狗开放检索（降级通道，无端内阅读/点赞私有数据）”，严禁冒充端内搜一搜。
2. **公众号合集整卷抓取（Album Fetcher）** ✅：直接调用微信公开的合集 JSON 接口，**无需登录、零凭据**，极速抓取指定合集内几十到上百篇推文的标题、官方链接、发布时间，并生成 Markdown 索引表。
3. **指定公众号历史推文批量获取（MP Account History）** ⚠️ 需扫码：通过微信公众平台超链接接口，按公众号名称搜索并批量提取该账号近期或历史发布的全部推文与官方短链。
4. **微信搜一搜全维度互动数据格式化（Format）** ✅：将微信桌面端（或 CUA 自动化）采集到的包含真实阅读量、点赞、在看、评论的 JSON 数据，格式化为符合排版标准的 Markdown 对比总表。

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
