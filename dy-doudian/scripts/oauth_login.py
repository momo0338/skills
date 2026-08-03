#!/usr/bin/env python3
"""抖店 OAuth 授权向导：生成授权 URL，用户授权后回填 token 到 ~/.dy-doudian/.env。

用法:
  python3 scripts/oauth_login.py <app_key> <app_secret> <scope>
说明:
  抖店开放平台 OAuth 流程（authorization code）：
  1. 打开生成的授权 URL，商家登录并点击授权
  2. 回调 URL 会带 ?code=xxx
  3. 本脚本用 code 换 access_token + refresh_token 并写入配置
"""

from __future__ import annotations

import sys
import urllib.parse
import webbrowser

from dy_doudian.config import CONFIG_DIR, ENV_PATH


def build_auth_url(app_key: str, redirect_uri: str = "https://www.douyin.com/") -> str:
    params = {
        "app_id": app_key,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "order,product,after_sale,data",
    }
    return "https://op.jinritemai.com/open/douyin/auth?" + urllib.parse.urlencode(params)


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__, file=sys.stderr)
        return 1
    app_key, app_secret = sys.argv[1], sys.argv[2]
    scope = sys.argv[3] if len(sys.argv) > 3 else ""

    url = build_auth_url(app_key)
    print("=" * 60)
    print("1. 打开以下授权链接，用商家账号登录并完成授权：")
    print(f"   {url}")
    print()
    webbrowser.open(url)
    print("2. 授权后浏览器跳转的地址会包含 ?code=xxx，复制 code 值")
    print("3. 运行以下命令完成 token 换发：")
    print(f"   python3 scripts/oauth_exchange.py {app_key} {app_secret} <code>")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
