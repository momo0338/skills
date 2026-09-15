---
name: browser-use
description: |
  使用 browser-use（大模型驱动的自主浏览器操作 Agent）完成复杂的网页交互、跨页面多步操作、表单填写与动态数据抽取。
  核心能力：结合视觉（截图）与 DOM 树智能定位网页元素，像真人一样自主点击、滚动、输入、切换标签页并完成复杂任务闭环。
  支持主流大模型（GPT-4o、Claude 3.5 Sonnet、DeepSeek 等），提供 CLI 一键调用脚本与 Python API。
  与现有工具定位区别：只读抓取优先用 crawl4ai/scrapling；固定脚本用 playwright；需要多步自主探索与交互决策时使用本技能。
  触发词：browser-use、操作浏览器、自主浏览、网页自动化Agent、跨页面操作、自动填表、模拟人类操作网页。
version: 1.0.0
---

# Browser-Use — LLM 自主浏览器操作 Agent Skill

> 基于 [browser-use](https://github.com/browser-use/browser-use)（开源 AI 网页自主操作库），让大语言模型拥有“看图 + 理解 DOM + 自主决策并操作浏览器”的能力。

## Overview

传统爬虫和 Playwright 工具依赖人工预先写好选择器（CSS/XPath）或确定性的操作脚本。而 `browser-use` 是一个**自主 Agent**：
1. **感知**：自动捕获浏览器视口截图，解析可交互 DOM 树并给元素打上坐标标记。
2. **决策**：大模型根据任务目标和当前视觉画面，规划下一步动作（点击某按钮、在输入框键入文本、向下滚动等）。
3. **执行**：通过 Playwright 驱动浏览器执行动作并验证结果，直到任务完成。

---

## 安装依赖 / Installation

```bash
pip install browser-use langchain-openai langchain-anthropic
playwright install
```

---

## 环境变量配置

在环境或 `~/.codex/.env` 中配置模型 API Key：

```bash
# 推荐使用具有强视觉/推理能力的大模型
export OPENAI_API_KEY="sk-..."
# 或使用 Claude
export ANTHROPIC_API_KEY="sk-ant-..."
# 或使用 DeepSeek / 兼容平台
export DEEPSEEK_API_KEY="sk-..."
export OPENAI_BASE_URL="https://api.deepseek.com"
```

---

## 快速使用 (CLI 封装)

仓库内置 `scripts/run_agent.py`，直接传入自然语言任务：

### 1. 基础任务（默认无头模式）

```bash
# 搜索并总结信息
python3 <SKILL_DIR>/scripts/run_agent.py "打开 HackerNews，找到前 3 篇 AI 相关文章的标题和链接"

# 跨页面操作
python3 <SKILL_DIR>/scripts/run_agent.py "去 GitHub 搜索 browser-use，查看最新的 Release 版本号并返回"
```

### 2. 观察 Agent 实时操作（弹出可见浏览器）

```bash
python3 <SKILL_DIR>/scripts/run_agent.py "在百度搜索杭州天气并查看未来三天的预报" --no-headless
```

### 3. 指定模型与步数限制

```bash
# 使用指定模型
python3 <SKILL_DIR>/scripts/run_agent.py "在电商网站搜索机械键盘并对比前两款价格" --model gpt-4o --max-steps 15

# 输出 JSON 结构化执行报告
python3 <SKILL_DIR>/scripts/run_agent.py "查看某网站的定价页面并提取方案差异" --json
```

---

## Python 代码调用

```python
import asyncio
import os
from langchain_openai import ChatOpenAI
from browser_use import Agent, Browser, BrowserConfig

async def main():
    llm = ChatOpenAI(model="gpt-4o", api_key=os.environ.get("OPENAI_API_KEY"))
    browser = Browser(config=BrowserConfig(headless=True))
    
    agent = Agent(
        task="打开 Google，搜索 'Crawl4AI GitHub'，进入仓库页面并获取 README 第一段介绍",
        llm=llm,
        browser=browser
    )
    
    history = await agent.run(max_steps=20)
    print("最终结果:", history.final_result())
    await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 浏览器与网页类技能分工表

| 技能 | 核心机制 | 适合场景 | 消耗成本 |
|------|---------|---------|---------|
| **browser-use** | **自主 LLM 视觉交互 Agent** | 复杂多步探索、无固定规则的跨页点击填表、动态交互任务闭环 | 需消耗 LLM Token（每步多模态交互） |
| **playwright** | 确定性代码 / CLI 指令 | 规则明确的批量操作、固定表单提交、自动化测试、精准截图 | 零 Token 消耗，执行速度极快 |
| **crawl4ai** | Playwright 动态渲染 + 本地智能提取 | 单页/多页 JS 渲染正文、BM25 主题过滤、CSS/XPath 字段抽取 | 零 API 费用，本地高速运行 |
| **firecrawl** | 全站递归 Crawl / Map 服务 | 整站文档抓取、站点地图链接发现、全站入库 | 依赖 Firecrawl 服务配额 |
| **scrapling** | 本地双模式（Fast/Stealth） | 微信公众号、知乎等国内高防反爬页面快速抓取 | 零费用，轻量极速 |
| **ego-browser** | 宿主桌面登录态 Chromium 交互 | 复用当前用户已登录态（抖音后台、微信等）进行业务操作 | 依赖本机已登录 Session |

