"""配置加载：环境变量 + .env 文件，与 dy-cli 的 `dy config` 风格一致。"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

CONFIG_DIR = Path.home() / ".dy-doudian"
ENV_PATH = CONFIG_DIR / ".env"
TOKENS_PATH = CONFIG_DIR / "tokens.json"


@dataclass
class DoudianConfig:
    app_key: str = ""
    app_secret: str = ""
    shop_id: str = ""
    access_token: str = ""
    refresh_token: str = ""
    token_expires_at: str = ""  # ISO8601，空表示未知

    missing: list[str] = field(default_factory=list)

    @property
    def is_complete(self) -> bool:
        return all([self.app_key, self.app_secret, self.shop_id, self.access_token])

    def has_refresh_capability(self) -> bool:
        return bool(self.refresh_token)


def load_config() -> DoudianConfig:
    """从环境变量 + ~/.dy-doudian/.env 加载配置。环境变量优先。"""
    load_dotenv(ENV_PATH)

    cfg = DoudianConfig(
        app_key=os.environ.get("DOUDIAN_APP_KEY", ""),
        app_secret=os.environ.get("DOUDIAN_APP_SECRET", ""),
        shop_id=os.environ.get("DOUDIAN_SHOP_ID", ""),
        access_token=os.environ.get("DOUDIAN_ACCESS_TOKEN", ""),
        refresh_token=os.environ.get("DOUDIAN_REFRESH_TOKEN", ""),
        token_expires_at=os.environ.get("DOUDIAN_TOKEN_EXPIRES_AT", ""),
    )

    required = {
        "DOUDIAN_APP_KEY": cfg.app_key,
        "DOUDIAN_APP_SECRET": cfg.app_secret,
        "DOUDIAN_SHOP_ID": cfg.shop_id,
        "DOUDIAN_ACCESS_TOKEN": cfg.access_token,
    }
    cfg.missing = [name for name, value in required.items() if not value]
    return cfg


class ConfigError(RuntimeError):
    """配置缺失或不合法。"""


def ensure_config() -> DoudianConfig:
    """加载并校验配置，缺失时抛 ConfigError。"""
    cfg = load_config()
    if cfg.missing:
        raise ConfigError(
            "缺少必要配置: " + ", ".join(cfg.missing)
            + "。请设置环境变量或在 ~/.dy-doudian/.env 中填写。"
        )
    return cfg
