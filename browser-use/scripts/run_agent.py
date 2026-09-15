#!/usr/bin/env python3
"""browser-use CLI 驱动脚本: 通过大模型自主操作浏览器完成多步交互任务。

用法:
  # 1. 基础任务执行（默认无头模式）
  python3 run_agent.py "打开 HackerNews，找到排名第一的文章标题和链接并返回"

  # 2. 显示可见浏览器窗口
  python3 run_agent.py "去 Google 搜索 Python 教程并点击第一个结果" --no-headless

  # 3. 指定模型与最大步数
  python3 run_agent.py "在 GitHub 搜索 browser-use 并查看 Stars 数量" --model gpt-4o --max-steps 15

  # 4. 指定自定义兼容 OpenAI 接口 (如 DeepSeek / OneAPI / 聚合平台)
  python3 run_agent.py "搜索并总结关于 AI Agent 的最新新闻" --model deepseek-chat --base-url "https://api.deepseek.com"

环境变量:
  OPENAI_API_KEY      : OpenAI API Key（若使用 OpenAI 或兼容接口）
  OPENAI_BASE_URL     : OpenAI API Base URL（可选）
  ANTHROPIC_API_KEY   : Anthropic API Key（若使用 Claude）
  DEEPSEEK_API_KEY    : DeepSeek API Key（若使用 DeepSeek）
"""

import argparse
import asyncio
import json
import os
import sys


def load_env_fallback():
    """若当前进程未设置关键环境变量，自动从 ~/.codex/.env 读取补全"""
    env_path = os.path.expanduser("~/.codex/.env")
    if os.path.exists(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if "=" in line and not line.startswith("#"):
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip().strip('"\'')
                        if k and not os.environ.get(k):
                            os.environ[k] = v
        except Exception:
            pass


def get_llm(model_name: str, base_url: str = None, api_key: str = None):
    """根据模型名称动态创建 LLM 实例"""
    model_lower = model_name.lower()

    # Anthropic Claude
    if "claude" in model_lower:
        try:
            from langchain_anthropic import ChatAnthropic
            key = api_key or os.environ.get("ANTHROPIC_API_KEY")
            if not key:
                print("错误: 使用 Claude 模型需配置 ANTHROPIC_API_KEY", file=sys.stderr)
                sys.exit(1)
            return ChatAnthropic(model_name=model_name, api_key=key)
        except ImportError:
            print("请先安装 langchain-anthropic: pip install langchain-anthropic", file=sys.stderr)
            sys.exit(1)

    # 默认 OpenAI / 兼容模型 (GPT-4o, DeepSeek, Qwen 等)
    try:
        from langchain_openai import ChatOpenAI
        key = api_key or os.environ.get("OPENAI_API_KEY") or os.environ.get("DEEPSEEK_API_KEY")
        url = base_url or os.environ.get("OPENAI_BASE_URL")

        if not key:
            print("错误: 未检测到 OPENAI_API_KEY / DEEPSEEK_API_KEY。", file=sys.stderr)
            print("请在环境变量或 ~/.codex/.env 中配置 API Key。", file=sys.stderr)
            sys.exit(1)

        kwargs = {"model": model_name, "api_key": key}
        if url:
            kwargs["base_url"] = url
        return ChatOpenAI(**kwargs)
    except ImportError:
        print("请先安装 langchain-openai: pip install langchain-openai", file=sys.stderr)
        sys.exit(1)


async def run_task(args):
    load_env_fallback()

    try:
        from browser_use import Agent, Browser, BrowserConfig
    except ImportError:
        print("错误: 尚未安装 browser-use 库。", file=sys.stderr)
        print("请执行: pip install browser-use langchain-openai", file=sys.stderr)
        sys.exit(1)

    llm = get_llm(args.model, args.base_url, args.api_key)

    browser_config = BrowserConfig(
        headless=not args.no_headless,
        disable_security=True,
    )
    browser = Browser(config=browser_config)

    agent = Agent(
        task=args.task,
        llm=llm,
        browser=browser,
        max_actions_per_step=args.max_actions_per_step,
        use_vision=not args.no_vision,
    )

    print(f"[*] 启动 browser-use Agent 任务: {args.task}")
    print(f"[*] 模型: {args.model} | Headless: {not args.no_headless} | 最大步数: {args.max_steps}")
    print()

    history = await agent.run(max_steps=args.max_steps)

    print("=" * 50)
    print("任务执行结果 (Final Result):")
    print("=" * 50)
    final_res = history.final_result()
    if final_res:
        print(final_res)
    else:
        print("Agent 已完成任务，未返回明确的最终文本摘要。")

    if args.json:
        print()
        print("=" * 50)
        print("执行历史概要 (JSON):")
        print("=" * 50)
        summary = {
            "task": args.task,
            "model": args.model,
            "steps": len(history.history),
            "final_result": final_res,
            "errors": history.errors(),
            "urls": history.urls(),
        }
        print(json.dumps(summary, ensure_ascii=False, indent=2))

    await browser.close()


def main():
    p = argparse.ArgumentParser(description="browser-use 浏览器自主操作 Agent CLI")
    p.add_argument("task", help="需要完成的浏览器自然语言任务描述")
    p.add_argument("--model", default="gpt-4o", help="底层驱动 LLM (默认: gpt-4o)")
    p.add_argument("--base-url", default=None, help="LLM API Base URL (如使用聚合转发或自建端点)")
    p.add_argument("--api-key", default=None, help="LLM API Key (未指定时读取环境变量)")
    p.add_argument("--no-headless", action="store_true", help="以可见界面启动真实浏览器窗口")
    p.add_argument("--max-steps", type=int, default=20, help="Agent 最大允许执行步数 (默认: 20)")
    p.add_argument("--max-actions-per-step", type=int, default=5, help="单步最多允许动作数")
    p.add_argument("--no-vision", action="store_true", help="禁用截图视觉输入（仅使用 DOM 树）")
    p.add_argument("--json", action="store_true", help="输出结构化 JSON 执行摘要")

    args = p.parse_args()
    asyncio.run(run_task(args))


if __name__ == "__main__":
    main()

