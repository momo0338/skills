"""Access Token 生命周期管理：持久化 + 过期自动刷新。

相对 mcp-cn-commerce 的核心增强：上游无 token 刷新机制（过期即报错），
本项目实现自动续期，access_token 刷新后原子写入 ~/.dy-doudian/tokens.json。
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

from dy_doudian.config import TOKENS_PATH, DoudianConfig

logger = logging.getLogger(__name__)

# 提前刷新阈值：剩余有效期低于此秒数则刷新（默认 10 分钟）
REFRESH_THRESHOLD_SECONDS = 600

# 抖店开放平台 token 刷新端点（与官方文档一致）
TOKEN_REFRESH_URL = "https://openapi-fxg.jinritemai.com/token/refresh/"


class TokenError(RuntimeError):
    """token 缺失或刷新失败。"""


def _iso_z(ts: int) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat(timespec="seconds")


def _parse_expiry(raw: str) -> float | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw).timestamp()
    except ValueError:
        return None


def _persist(app_key: str, token: str, expires_at: str, refresh_token: str = "") -> None:
    """原子写入 token 持久化文件。"""
    TOKENS_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "app_key": app_key,
        "access_token": token,
        "expires_at": expires_at,
        "refresh_token": refresh_token,
        "updated_at": _iso_z(int(time.time())),
    }
    tmp = TOKENS_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, TOKENS_PATH)


def _load_persisted(app_key: str) -> dict | None:
    if not TOKENS_PATH.exists():
        return None
    try:
        data = json.loads(TOKENS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if data.get("app_key") != app_key:
        return None
    return data


def refresh_access_token(app_key: str, app_secret: str, refresh_token: str) -> tuple[str, str]:
    """调用官方 /token/refresh/ 接口换新 token。

    Returns:
        (new_access_token, new_expires_at_iso)
    """
    params = {
        "app_key": app_key,
        "app_secret": app_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }
    resp = httpx.post(TOKEN_REFRESH_URL, data=params, timeout=15)
    resp.raise_for_status()
    result = resp.json()
    if result.get("code") != 10000:
        raise TokenError(f"token 刷新失败: {result.get('msg', 'unknown error')}")
    data = result.get("data", {})
    token = data.get("access_token", "")
    if not token:
        raise TokenError("token 刷新响应缺少 access_token")
    expires_in = int(data.get("expires_in", 86400))
    expires_at = _iso_z(int(time.time()) + expires_in)
    return token, expires_at


class TokenManager:
    """线程安全的 token 管理：内存缓存 + 持久化 + 自动刷新。"""

    def __init__(self, cfg: DoudianConfig, threshold: int = REFRESH_THRESHOLD_SECONDS):
        self.cfg = cfg
        self.threshold = threshold
        self._lock = threading.Lock()
        self._token = cfg.access_token
        self._expires_at = _parse_expiry(cfg.token_expires_at)
        self._refresh_token = cfg.refresh_token
        self._loaded_persisted = False

    def _load_if_needed(self) -> None:
        """首次访问时从持久化文件恢复（应对进程重启后 token 续期）。"""
        if self._loaded_persisted:
            return
        self._loaded_persisted = True
        if self._token:
            return
        saved = _load_persisted(self.cfg.app_key)
        if saved and saved.get("access_token"):
            self._token = saved["access_token"]
            self._expires_at = _parse_expiry(saved.get("expires_at", ""))
            self._refresh_token = saved.get("refresh_token", "") or self._refresh_token

    def _needs_refresh(self) -> bool:
        if not self._expires_at:
            return False  # 未知有效期，不自动刷新，直接尝试调用
        return (self._expires_at - time.time()) < self.threshold

    def get_token(self) -> str:
        """返回可用 access_token；临近过期时自动刷新。线程安全。"""
        with self._lock:
            self._load_if_needed()
            if self._needs_refresh():
                if not self._refresh_token:
                    raise TokenError(
                        "access_token 临近过期但无 refresh_token，无法自动刷新。"
                        "请重新走 OAuth 授权获取 refresh_token。"
                    )
                new_token, expires_at = refresh_access_token(
                    self.cfg.app_key, self.cfg.app_secret, self._refresh_token
                )
                self._token = new_token
                self._expires_at = _parse_expiry(expires_at)
                _persist(
                    self.cfg.app_key,
                    new_token,
                    expires_at,
                    refresh_token=self._refresh_token,
                )
                logger.info("access_token 已自动刷新，新有效期至 %s", expires_at)
            return self._token

    def set_token(self, token: str, expires_at: str, refresh_token: str = "") -> None:
        """手动写入 token（首次授权或手动换新后调用）。"""
        with self._lock:
            self._token = token
            self._expires_at = _parse_expiry(expires_at)
            if refresh_token:
                self._refresh_token = refresh_token
            _persist(self.cfg.app_key, token, expires_at, self._refresh_token)
