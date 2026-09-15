---
name: gh-write
version: 1.0.0
description: 微信公众号「GitHub 项目推荐」专栏文章自动化采写技能。消费 gh-research 深度技术调研数据与 mp-search 微信搜一搜双维度热度数据（最热 + 最新 Top 5~10 篇），融合硬核技术特性与移动端爆款排版规范，自动生成可直接发布的公众号技术深度长文草稿。
homepage: https://github.com/zhugx/skills
metadata: {"openclaw":{"emoji":"✍️","requires":{"bins":["python3"]}}}
---

# GH-Write: 微信公众号 GitHub 专栏采写技能

## 一、概述

本技能专为**「满宝看未来」**微信公众号的「GitHub 项目推荐」精品专栏打造。技能通过流水线将 GitHub 第一手技术数据与微信生态真实读者舆情进行深度融合，兼顾技术专业深度与移动端高可读排版，实现公众号深度技术推文的一站式全自动产出。

---

## 二、适用场景与触发词

- **触发词**：`gh-write`、`GitHub推荐`、`开源项目推荐`、`满宝看未来专栏`、`GitHub推文写作`
- **典型场景**：
  1. 结合 `gh-research` 抓取的技术指标与 `mp-search` 微信搜一搜舆情，自动组装规范的微信推文草稿
  2. 为开源项目生成高兼容移动端「科技卡片 UI」、搜一搜双维度（最热 vs 最新）对比总表
  3. 按照公众号技术长文排版规范（严禁 `---` 分割线、明文开源短链、H2/H3 标准层级）输出至 Obsidian 知识库草稿区

---

## 三、标准执行流水线 (Standard Pipeline)

```
1. GitHub 深度调研
   └─ 调用 gh-research 获取目标项目的实时 Stars、Forks、Issue、Release、多语言构成与 README 特性

2. 微信搜一搜双维度舆情检索
   ├─ 调用 mp-search 检索【最热】Top 5~10 篇：提炼历史沉淀高热度爆款的标题模式、痛点共鸣与读者关注重点
   └─ 调用 mp-search 检索【最新】Top 5~10 篇：捕捉近期时效推文、社区对新版本的讨论与部署踩坑反馈

3. 结构化长文创作与组装
   ├─ 生成 3 个备选爆款标题（痛点反问 / 权威开源 / 极客生产力）
   ├─ 痛点直击 + 硬核名片徽标表
   ├─ 3 大杀手级核心特性深度剖析
   ├─ 微信搜一搜【最热 vs 最新】双维度对比表 + 读者真实痛点洞察
   └─ 5 分钟本地部署命令、避坑建议与选型总结

4. 成果落盘与知识库联动
   ├─ 输出 Markdown 草稿至: 03-工作记录/满宝看未来/草稿/GitHub推荐-[项目名].md
   └─ 自动关联对应知识库收藏卡片双链
```

> **注意**：`gh_writer.py` 负责极速生成结构化草稿脚手架（包含科技卡片 UI、搜一搜双维度对比表与安装指令）；针对具体的痛点直击与三大杀手级特性深度剖析，AI 应结合目标项目实际业务领域与 README/代码细节进行针对性扩写，避免套用泛化套话。

---

## 四、文章结构与排版规范（符合微信公众号与知识库规则）

1. **Frontmatter 强制标准**：
   ```yaml
   ---
   title: 文章标题
   date: YYYY-MM-DD
   category: 满宝看未来
   source: 原创
   status: draft
   tags: [GitHub推荐, 开发工具/Vue, 开源项目]
   description: 100-150字文章精炼摘要
   github_repo: owner/repo
   github_url: https://github.com/owner/repo
   stars: 2347
   ---
   ```
2. **移动端友好排版规范（高转化规范）**：
   - **严禁使用 `---` 水平分割线**：避免微信排版工具渲染出粗硬割裂的灰色横线，改用适度段落留白与层级标题自然呼吸；
   - **项目名片强制采用「科技卡片 UI」**：杜绝传统 3 列表格在手机上的挤压与文字竖排折行；必须包含仓库主名、开源 License 徽标、**独立开源地址复制栏（明文 URL，长按即复制，杜绝转成“文末链接”）**、3 个数据宫格（热度、协议、语言）及核心定位；
   - **标题层级**：严控在 H1（文章名）、H2（大模块）、H3（小特性），杜绝深层嵌套；
   - **终端代码块**：带有全选复制指引与终端样式，避免小屏横向滚动条；
   - **搜一搜对比**：双维度对比表展示最热 vs 最新，客观复盘舆情。

---

## 五、命令行调用与辅助脚本

```bash
# 步骤 1: 提取 GitHub 实时数据
python3 /Users/zhugx/src/skills/gh-research/scripts/gh_research.py julyx10/lap --json /tmp/lap_gh.json

# 步骤 2: 汇总生成公众号草稿（可同时传入搜一搜最热和最新数据）
python3 /Users/zhugx/src/skills/gh-write/scripts/gh_writer.py \
  --gh-json /tmp/lap_gh.json \
  --hot-json /tmp/lap_hot.json \
  --new-json /tmp/lap_new.json \
  --output "/Users/zhugx/codeup/obsidian/03-工作记录/满宝看未来/草稿/GitHub推荐-lap.md"
```
