"""浏览器自动化基类：持久化登录态 + 通用页面操作。

抖店网页版（fxg.jinritemai.com）的运营操作封装。
与 API 层互补：API 只读查询，浏览器负责写操作（上下架/发货/审核）。

登录态管理：
- 首次使用时通过 `login` 打开浏览器让用户手动登录（扫码/验证码）
- 登录后 Cookie 持久化到 ~/.dy-doudian/browser-state.json
- 后续启动复用持久化登录态，无需重复登录
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

from playwright.sync_api import Browser, BrowserContext, Page, Playwright, sync_playwright

from dy_doudian.config import CONFIG_DIR

logger = logging.getLogger(__name__)

FXG_DOMAIN = "https://fxg.jinritemai.com"
STATE_PATH = CONFIG_DIR / "browser-state.json"
HEADLESS = False  # 抖店需要真实浏览器（登录/风控），默认有头


class DoudianBrowserError(RuntimeError):
    """浏览器操作失败。"""


class DoudianBrowser:
    """抖店网页版浏览器会话。"""

    def __init__(self, headless: bool = HEADLESS, timeout_ms: int = 30000):
        self.headless = headless
        self.timeout_ms = timeout_ms
        self._pw: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None

    # ── 会话生命周期 ─────────────────────────────

    def start(self) -> "DoudianBrowser":
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(headless=self.headless)
        self._context = self._browser.new_context(
            storage_state=str(STATE_PATH) if STATE_PATH.exists() else None,
            viewport={"width": 1440, "height": 900},
        )
        return self

    def close(self) -> None:
        if self._context:
            self._context.close()
        if self._browser:
            self._browser.close()
        if self._pw:
            self._pw.stop()
        self._context = self._browser = self._pw = None

    def __enter__(self) -> "DoudianBrowser":
        return self.start()

    def __exit__(self, *exc) -> None:
        self.close()

    # ── 页面 ─────────────────────────────────────

    def new_page(self) -> Page:
        assert self._context is not None
        page = self._context.new_page()
        page.set_default_timeout(self.timeout_ms)
        return page

    def is_logged_in(self, page: Page) -> bool:
        """通过跳转行为判断登录态：未登录会重定向到登录页。"""
        try:
            page.goto(f"{FXG_DOMAIN}/ffa/morder/order/list", wait_until="domcontentloaded", timeout=20000)
            time.sleep(2)
        except Exception:
            return False
        return "login" not in page.url and page.url.startswith(FXG_DOMAIN)

    def save_state(self) -> None:
        if self._context:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            self._context.storage_state(path=str(STATE_PATH))

    # ── 通用操作辅助 ─────────────────────────────

    @staticmethod
    def click_by_text(page: Page, text: str) -> bool:
        """点击包含指定文本的按钮（处理 ref 过期场景）。"""
        try:
            btn = page.get_by_role("button", name=text).first
            btn.click(timeout=5000)
            return True
        except Exception:
            try:
                page.evaluate(
                    """(text) => {
                        const btn = [...document.querySelectorAll('button')]
                            .find(b => b.textContent.trim().includes(text));
                        if (btn) { btn.click(); return true; }
                        return false;
                    }""",
                    text,
                )
                return True
            except Exception:
                return False
