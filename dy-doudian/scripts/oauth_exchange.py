#!/usr/bin/env python3
"""用 OAuth authorization code 换发 access_token + refresh_token，并写入配置。

用法:
  python3 scripts/oauth_exchange.py <app_key> <app_secret> <code>
"""

from __future__ import annotations

import sys
import time
from datetime import datetime, timezone

import httpx

from dy_doudian.config import CONFIG_DIR, ENV_PATH, load_config


def exchange(app_key: str, app_secret: str, code: str) -> dict:
    resp = httpx.post(
        "https://openapi-fxg.jinritemai.com/oauth/access/token/",
        data={
            "app_key": app_key,
            "app_secret": app_secret,
            "code": code,
            "grant_type": "authorization_code",
        },
        timeout=15,
    )
    resp.raise_for_status()
    result = resp.json()
    if result.get("code") != 10000:
        raise RuntimeError(f"换发失败: {result.get('msg', 'unknown')}")
    return result.get("data", {})


def write_env(updates: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    if ENV_PATH.exists():
        lines = ENV_PATH.read_text(encoding="utf-8").splitlines()
    keys = {line.split("=", 1)[0] for line in lines if "=" in line and not line.startswith("#")}
    for k, v in updates.items():
        if k in keys:
            lines = [f"{k}={v}" if line.split("=", 1)[0] == k else line for line in lines]
        else:
            lines.append(f"{k}={v}")
    ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"已写入 {ENV_PATH}")


def main() -> int:
    if len(sys.argv) < 4:
        print(__doc__, file=sys.stderr)
        return 1
    app_key, app_secret, code = sys.argv[1], sys.argv[2], sys.argv[3]
    try:
        data = exchange(app_key, app_secret, code)
    except Exception as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 1

    token = data.get("access_token", "")
    refresh = data.get("refresh_token", "")
    expires_in = int(data.get("expires_in", 86400))
    expires_at = datetime.fromtimestamp(
        time.time() + expires_in, tz=timezone.utc
    ).isoformat(timespec="seconds")

    write_env({
        "DOUDIAN_APP_KEY": app_key,
        "DOUDIAN_APP_SECRET": app_secret,
        "DOUDIAN_ACCESS_TOKEN": token,
        "DOUDIAN_REFRESH_TOKEN": refresh,
        "DOUDIAN_TOKEN_EXPIRES_AT": expires_at,
    })
    print(f"access_token 换发成功，有效期至 {expires_at}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
