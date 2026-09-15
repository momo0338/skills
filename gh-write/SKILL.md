---
name: gh-write
version: 1.1.0
description: 微信公众号「GitHub 项目推荐」专栏文章自动化采写技能。消费 gh-research 深度技术调研数据与 mp-search 微信搜一搜双维度热度数据（最热 + 最新 Top 5~10 篇），融合硬核技术特性与移动端爆款排版规范，自动生成可直接发布的公众号技术深度长文草稿。
homepage: https://github.com/zhugx/skills
metadata: {"openclaw":{"emoji":"✍️","requires":{"bins":["python3"]}}}
---

# GH-Write: 微信公众号 GitHub 专栏采写技能 (v1.1.0)

## 一、概述

本技能专为**「满宝看未来」**微信公众号的「GitHub 项目推荐」精品专栏打造。技能通过流水线将 GitHub 第一手技术数据与微信生态真实读者舆情（基于 mp-search 检索的最热与最新推文）进行深度融合，兼顾技术专业深度与移动端高可读排版，实现公众号深度技术推文的高质高效产出。

---

## 二、适用场景与触发词

- **触发词**：`gh-write`、`GitHub推荐`、`开源项目推荐`、`满宝看未来专栏`、`GitHub推文写作`
- **典型场景**：
  1. 结合 `gh-research` 抓取的实时技术指标与 `mp-search` 微信搜一搜双维度舆情，自动组装规范的微信推文草稿
  2. 为开源项目生成结构化三列表格项目名片、搜一搜双维度（最热 vs 最新）对比总表
  3. 按照公众号技术长文排版规范（严禁 `---` 分割线、明文开源短链、H2/H3 标准层级）输出至 Obsidian 知识库草稿区

---

## 三、标准执行流水线 (Standard Pipeline)

```
1. GitHub 深度调研
   └─ 调用 gh-research 并发获取目标项目的实时 Stars、Forks、Issue、Release、多语言构成与 README 特性

2. 微信搜一搜双维度舆情检索
   ├─ 调用 mp-search search 检索【最热】Top 5~10 篇：提炼历史沉淀高热度爆款的标题模式、痛点共鸣与读者关注重点
   └─ 调用 mp-search search 检索【最新】Top 5~10 篇：捕捉近期时效推文、同行一线实测反馈与最新版本讨论

3. 爆款叙事长文创作（反说明书规范）
   ├─ 拟定 3~4 个极具张力与反差感的爆款标题（反问痛点 / 极客爽点 / 场景反差）
   ├─ 导读直击具体戏剧化场景（杜绝空泛套话，带出核心实测反差）
   ├─ 戳破行业痛点（结合同行共鸣，把受众最痛的神经摆上台面）
   ├─ 项目名片（标准 Markdown 三列表格，剥离内联 HTML 到排版阶段）
   ├─ 核心特性深度剖析（现场感代码演示 + 原理深挖 + 真实成本算账）
   ├─ 搜一搜双维度【最热 vs 最新】对比总表 + 读者痛点洞察
   └─ 5 分钟本地极速上手命令、避坑建议与客观选型总结

4. 成果落盘与下游排版
   ├─ 输出纯语义 Markdown 草稿至: 03-工作记录/满宝看未来/草稿/GitHub推荐-[项目名].md
   └─ 调用 mp-html 编译为 100% 微信原生方言合规的 HTML 视觉排版稿 (-排版.html)
```

---

## 四、命令行调用全流程示例

```bash
# 步骤 1: 并发抽取 GitHub 实时数据
python3 /Users/zhugx/src/skills/gh-research/scripts/gh_research.py hypit-ai/hypit --json /tmp/repo_gh.json

# 步骤 2: mp-search 极速获取最热与最新推文
python3 /Users/zhugx/src/skills/mp-search/scripts/mp_search.py search "hypit" -s hot -n 5 -o /tmp/repo_hot.json
python3 /Users/zhugx/src/skills/mp-search/scripts/mp_search.py search "hypit" -s new -n 5 -o /tmp/repo_new.json

# 步骤 3: 汇总生成初版草稿脚手架
python3 /Users/zhugx/src/skills/gh-write/scripts/gh_writer.py \
  --gh-json /tmp/repo_gh.json \
  --hot-json /tmp/repo_hot.json \
  --new-json /tmp/repo_new.json \
  --output "/Users/zhugx/codeup/obsidian/03-工作记录/满宝看未来/草稿/GitHub推荐-hypit.md"
```
