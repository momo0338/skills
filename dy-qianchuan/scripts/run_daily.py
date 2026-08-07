#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
千川每日一键执行入口
流程: 拉取数据 -> 双引擎分析 -> 生成看板
用法:
  python3 scripts/run_daily.py            # 真实API（需配置config/api_config.yaml）
  python3 scripts/run_daily.py --mock     # 示例数据演示
  python3 scripts/run_daily.py --manual   # 手动录入
"""
import argparse
import os
import sys

SYS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(SYS_DIR, "scripts")


def main():
    parser = argparse.ArgumentParser(description="千川每日执行")
    parser.add_argument("--mock", action="store_true", help="使用示例数据")
    parser.add_argument("--manual", action="store_true", help="手动输入")
    args = parser.parse_args()

    py = sys.executable
    steps = []

    if args.manual:
        steps.append([py, os.path.join(SCRIPTS, "fetch_data.py"), "--manual"])
    elif args.mock:
        steps.append([py, os.path.join(SCRIPTS, "fetch_data.py"), "--mock"])
    else:
        steps.append([py, os.path.join(SCRIPTS, "fetch_data.py")])

    steps.append([py, os.path.join(SCRIPTS, "analyze.py")])
    steps.append([py, os.path.join(SCRIPTS, "build_report.py")])

    for i, cmd in enumerate(steps):
        print(f"\n=== 步骤{i+1}/{len(steps)} ===")
        rc = os.system(" ".join(f'"{c}"' for c in cmd))
        if rc != 0:
            print(f"步骤失败: {' '.join(cmd)}", file=sys.stderr)
            sys.exit(1)

    print("\n✅ 今日流程完成！看板路径见上方输出。")


if __name__ == "__main__":
    main()
