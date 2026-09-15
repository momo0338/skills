---
name: gh-research
version: 1.1.0
description: 深度提取 GitHub 仓库实时多维度数据（实时 Stars/Forks/Release 版本/多语言分布/README 核心功能提炼），为技术文章创作和开源项目选品提供一手详实依据。
homepage: https://github.com/zhugx/skills
metadata: {"openclaw":{"emoji":"🔭","requires":{"bins":["python3", "gh"]}}}
---

# GH-Research: GitHub 开源项目深度数据调研技能

## 一、概述

本技能专为开源项目研究、技术选型与文章采写打造。通过本机已鉴权的 GitHub CLI (`gh api`)，通过 ThreadPoolExecutor 并发机制秒级抽取任意 GitHub 仓库的权威一手数据，彻底避免 AI 幻觉、陈旧数据与串行网络超时。

---

## 二、适用场景与触发词

- **触发词**：`gh-research`、`GitHub调研`、`开源项目调研`、`GitHub仓库数据`、`开源选品`、`GitHub项目分析`
- **典型场景**：
  1. 深度分析任意 GitHub 项目的实时数据（Stars、Forks、Issues、活跃度）
  2. 获取项目真实代码构成与语言百分比分布
  3. 提取 README 核心特性列表与安装部署指引
  4. 输出标准化数据卡片或结构化 JSON，作为公众号文章写作（`gh-write`）的上游输入

---

## 三、支持采集的核心维度

1. **项目名片与热度指标**：
   - 仓库全名 (`owner/repo`)、官方主页、开源 License
   - 实时精确 Stars 数量、Forks 数量、Open Issues 数量、Watchers 数量
2. **技术构成与开发语言**：
   - 主语言与所有开发语言的精确百分比（如 `Vue 52.0%, Rust 39.1%`）
   - 官方定义的 Topics 标签分类
3. **活跃度与版本生命周期**：
   - 仓库创建日期、最新代码 Push 时间
   - 最新正式发布版本 (Release Tag、发布日期与更新日志摘要)
4. **README 结构化提炼**：
   - 项目一句话定位
   - 核心功能特性（Features 列表抽取）
   - 快速上手与安装指引命令

---

## 四、命令行调用方式

```bash
# 1. 打印 Markdown 格式的项目调研卡片
python3 /Users/zhugx/src/skills/gh-research/scripts/gh_research.py <owner/repo 或 仓库URL>

# 2. 导出完整结构化 JSON 数据文件（供 gh-write 消费）
python3 /Users/zhugx/src/skills/gh-research/scripts/gh_research.py julyx10/lap --json /tmp/lap_research.json
```

---

## 五、输入兼容格式

- 仓库短名称：`julyx10/lap`
- 完整网页 URL：`https://github.com/julyx10/lap` 或 `https://github.com/julyx10/lap/`
- 项目名称模糊匹配：`lap`（自动检索最高星同名仓库）
