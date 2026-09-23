#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
微信公众平台扫码登录、公众号主体搜索与号内文章检索模块

功能：
1. 扫码登录微信公众平台与 Cookie/Token 动态持久化
2. 搜索公众号主体（获取 fakeid、微信号、认证信息等）
3. 获取指定公众号历史文章列表与短链接（支持号内关键词检索过滤）
4. 多通道凭据加载（支持文件、环境变量与直接传参）
"""

import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse, parse_qs, quote

try:
    from playwright.sync_api import sync_playwright, Page, BrowserContext
except ImportError:
    print("⚠️ 需要安装 playwright: pip install playwright")
    print("⚠️ 然后运行: playwright install chromium")
    raise

# 微信公众平台配置
MP_BASE_URL = "https://mp.weixin.qq.com"
MP_LOGIN_URL = "https://mp.weixin.qq.com/"
MP_ARTICLE_LIST_API = "https://mp.weixin.qq.com/cgi-bin/appmsgpublish"
MP_SEARCH_API = "https://mp.weixin.qq.com/cgi-bin/searchbiz"

# 凭据存储路径
COOKIE_FILE = os.path.join(os.path.dirname(__file__), ".mp_cookies.json")
TOKEN_FILE = os.path.join(os.path.dirname(__file__), ".mp_token")
QRCODE_FILE = "/tmp/mp_login_qrcode.png"


class MPLoginError(Exception):
    """公众平台登录错误"""
    def __init__(self, message: str, code: int = 0):
        self.message = message
        self.code = code
        super().__init__(self.message)


class WeChatMPClient:
    """微信公众平台客户端"""

    def __init__(self, cookie_file: str = None, token: str = None):
        """初始化客户端
        
        Args:
            cookie_file: Cookie文件路径，默认使用 .mp_cookies.json
            token: 直接传入的 token（如通过环境变量或 CLI 注入）
        """
        self.cookie_file = cookie_file or COOKIE_FILE
        self.token_file = os.path.join(os.path.dirname(self.cookie_file), ".mp_token")
        self.token = token or os.environ.get("MP_TOKEN")
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.cookies = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def close(self):
        """安全关闭浏览器与 Playwright 引擎"""
        if self.browser:
            try:
                self.browser.close()
            except Exception:
                pass
            self.browser = None
        if self.playwright:
            try:
                self.playwright.stop()
            except Exception:
                pass
            self.playwright = None

    def _save_cookies(self):
        """保存 Cookie 与 Token 到本地"""
        try:
            if self.context:
                self.cookies = self.context.cookies()
            payload = {
                "token": self.token,
                "cookies": self.cookies,
                "updated_at": time.time()
            }
            with open(self.cookie_file, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            print(f"✅ Cookie 与 Token 已保存到: {self.cookie_file}")

            if self.token:
                with open(self.token_file, "w", encoding="utf-8") as tf:
                    tf.write(self.token.strip())
        except Exception as e:
            print(f"⚠️ 保存 Cookie 失败: {e}")

    def _load_cookies(self) -> bool:
        """从文件或环境变量加载凭据"""
        # 1. 尝试从环境变量加载
        env_token = os.environ.get("MP_TOKEN")
        if env_token:
            self.token = env_token.strip()

        # 2. 从文件加载
        if os.path.exists(self.cookie_file):
            try:
                with open(self.cookie_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    if not self.token:
                        self.token = data.get("token")
                    self.cookies = data.get("cookies", [])
                elif isinstance(data, list):
                    self.cookies = data
            except Exception as e:
                print(f"⚠️ 加载 Cookie 文件失败: {e}")

        # 3. 检查单独的 token 文件
        if not self.token and os.path.exists(self.token_file):
            try:
                with open(self.token_file, "r", encoding="utf-8") as tf:
                    self.token = tf.read().strip()
            except Exception:
                pass

        # 注入 context
        if self.context and self.cookies:
            try:
                self.context.add_cookies(self.cookies)
                return True
            except Exception as e:
                print(f"⚠️ context 注入 Cookie 失败: {e}")
                return False

        return bool(self.token or self.cookies)

    def check_session_fast(self) -> bool:
        """纯 HTTP 快速验证存量 Token 和 Cookie 是否依然有效（无需启动浏览器）"""
        if not self.token or not self.cookies:
            return False
        try:
            import urllib.request
            cookie_str = "; ".join([f"{c['name']}={c['value']}" for c in self.cookies if 'name' in c and 'value' in c])
            url = f"{MP_SEARCH_API}?action=search_biz&begin=0&count=1&token={self.token}&lang=zh_CN&f=json&ajax=1&query=test"
            headers = {
                "Cookie": cookie_str,
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                "Referer": f"{MP_BASE_URL}/cgi-bin/appmsg?token={self.token}&lang=zh_CN"
            }
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                ret = data.get("base_resp", {}).get("ret")
                return ret == 0
        except Exception:
            return False

    def _validate_cookies(self) -> bool:
        """验证已保存凭据的有效性"""
        if not self.page:
            return False
        try:
            self.page.goto(f"{MP_BASE_URL}/cgi-bin/home", wait_until="domcontentloaded", timeout=12000)
            self.page.wait_for_timeout(2000)

            current_url = self.page.url
            if "cgi-bin/home" in current_url or "cgi-bin/frame" in current_url:
                body_text = self.page.inner_text("body")
                if "登录超时" in body_text or "请重新登录" in body_text or "二维码" in body_text:
                    return False
                return True
            return False
        except Exception:
            return False

    def _extract_token(self) -> Optional[str]:
        """从页面 URL 或 DOM 中提取当前有效 token"""
        if not self.page:
            return self.token

        # 方法 1：从 URL 参数提取
        url = self.page.url
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        tokens = params.get("token")
        if tokens and tokens[0]:
            return tokens[0]

        # 方法 2：从页面链接属性中正则提取
        try:
            links = self.page.eval_on_selector_all('a[href*="token="]', 'elements => elements.map(e => e.href)')
            for l in links:
                m = parse_qs(urlparse(l).query).get("token")
                if m and m[0]:
                    return m[0]
        except Exception:
            pass

        # 方法 3：从 Cookie 提取
        if self.context:
            try:
                cookies = self.context.cookies()
                for cookie in cookies:
                    if cookie.get("name") == "token" and cookie.get("value"):
                        return cookie["value"]
            except Exception:
                pass

        return self.token

    LAUNCH_ARGS = ["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]

    def _launch_usable_browser(self, headless: bool):
        """优先系统 Chrome，回退自带 Chromium"""
        last_err = None
        for kwargs in ({"channel": "chrome"}, {}):
            tag = kwargs.get("channel", "bundled-chromium")
            try:
                browser = self.playwright.chromium.launch(
                    headless=headless, args=self.LAUNCH_ARGS, **kwargs
                )
            except Exception as e:
                last_err = e
                continue
            try:
                probe = browser.new_page()
                probe.goto(MP_BASE_URL, wait_until="domcontentloaded", timeout=20000)
                probe.close()
                return browser
            except Exception as e:
                last_err = e
                try:
                    browser.close()
                except Exception:
                    pass
        raise RuntimeError(f"无可用浏览器通道（系统 Chrome 与自带 Chromium 均失败）: {last_err}")

    def login(self, headless: bool = False, timeout: int = 120) -> Dict[str, Any]:
        """登录微信公众平台（带凭据复用与扫码兜底）"""
        # 1. 尝试加载凭据
        self._load_cookies()
        if self.check_session_fast():
            print("✅ 现有公众平台会话凭据有效（快速探活通过，免拉起浏览器）")
            return {
                "success": True,
                "token": self.token,
                "cookies": self.cookies,
                "message": "快速验证登录成功"
            }

        try:
            self.playwright = sync_playwright().start()
            self.browser = self._launch_usable_browser(headless)
            self.context = self.browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 800}
            )
            if self.cookies:
                self.context.add_cookies(self.cookies)
            self.page = self.context.new_page()

            # 2. 检查存量登录态
            print("正在验证现有公众平台登录凭据...")
            if self._validate_cookies():
                self.token = self._extract_token()
                if self.token:
                    print(f"✅ 登录凭据有效，Token: {self.token}")
                    self._save_cookies()
                    return {
                        "success": True,
                        "token": self.token,
                        "cookies": self.cookies,
                        "message": "凭据复用登录成功"
                    }

            print("⚠️ 登录凭据已过期或缺失，正在拉取微信公众平台登录页...")
            self.page.goto(MP_LOGIN_URL, wait_until="domcontentloaded", timeout=15000)

            # 截图保存二维码供终端/无头用户扫码
            try:
                self.page.wait_for_selector("img.login__type__container__scan__qrcode", timeout=10000)
                self.page.wait_for_function('() => { const el = document.querySelector("img.login__type__container__scan__qrcode"); return el && el.naturalWidth > 50; }', timeout=10000)
                self.page.locator("img.login__type__container__scan__qrcode").screenshot(path=QRCODE_FILE)
                print(f"📱 微信扫码二维码已就绪，已保存至本地图片: {QRCODE_FILE}")
                print("👉 请在终端或查看该图片，使用绑定了公众号的微信扫码授权")
            except Exception as qre:
                print(f"⚠️ 截取二维码图片异常: {qre}")

            # 轮询等待登录完成
            start_time = time.time()
            while time.time() - start_time < timeout:
                current_url = self.page.url
                if "cgi-bin/home" in current_url or "cgi-bin/frame" in current_url:
                    self.page.wait_for_timeout(1000)
                    self.token = self._extract_token()
                    if self.token:
                        self.cookies = self.context.cookies()
                        self._save_cookies()
                        print(f"\n✅ 扫码登录成功！Token: {self.token}")
                        return {
                            "success": True,
                            "token": self.token,
                            "cookies": self.cookies,
                            "message": "扫码登录成功"
                        }
                if "loginpage" in current_url:
                    print("✅ 已扫码，请在微信端点击确认登录...", end="\r", flush=True)

                self.page.wait_for_timeout(1500)

            print(f"\n❌ 登录超时（{timeout}秒）")
            return {
                "success": False,
                "token": None,
                "cookies": [],
                "message": f"登录超时（{timeout}秒），请扫码重试"
            }

        except Exception as e:
            print(f"\n❌ 登录异常: {e}")
            return {
                "success": False,
                "token": None,
                "cookies": [],
                "message": str(e)
            }

    def _api_get(self, url: str) -> Dict[str, Any]:
        """执行公众平台后台 API 请求（优先使用 page.request，否则退回标准 urllib）"""
        if self.page:
            resp = self.page.request.get(url)
            return resp.json()

        import urllib.request
        cookie_str = "; ".join([f"{c['name']}={c['value']}" for c in self.cookies if 'name' in c and 'value' in c])
        headers = {
            "Cookie": cookie_str,
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": f"{MP_BASE_URL}/cgi-bin/appmsg?token={self.token}&lang=zh_CN"
        }
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=12) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def search_accounts(self, query: str, count: int = 10) -> List[Dict[str, Any]]:
        """搜索公众号列表
        
        Args:
            query: 搜索关键词（如「江苏国资」、「金陵人才」）
            count: 最大返回数量 (默认 10)
            
        Returns:
            公众号信息列表
        """
        if not self.token:
            raise MPLoginError("未登录或 Token 缺失，请先调用 login()")

        print(f"🔍 正在检索公众号: 「{query}」...")
        try:
            url = (
                f"{MP_SEARCH_API}?"
                f"action=search_biz&begin=0&count={count}&"
                f"token={self.token}&lang=zh_CN&f=json&ajax=1&"
                f"query={quote(query)}"
            )

            data = self._api_get(url)
            if data.get("base_resp", {}).get("ret") != 0:
                error_msg = data.get("base_resp", {}).get("err_msg", "未知错误")
                print(f"❌ 搜索失败 (ret={data.get('base_resp', {}).get('ret')}): {error_msg}")
                return []

            biz_list = data.get("list", [])
            accounts = []
            for item in biz_list:
                accounts.append({
                    "fakeid": item.get("fakeid", ""),
                    "nickname": item.get("nickname", ""),
                    "alias": item.get("alias", ""),
                    "round_head_img": item.get("round_head_img", ""),
                    "service_type": item.get("service_type", 0),
                    "signature": item.get("signature", "")
                })
            print(f"✅ 成功命中 {len(accounts)} 个匹配公众号")
            return accounts
        except Exception as e:
            print(f"❌ 搜索公众号主体异常: {e}")
            return []

    def search_account(self, nickname: str) -> Optional[Dict[str, Any]]:
        """精确或优选匹配单个公众号"""
        accounts = self.search_accounts(nickname, count=5)
        if not accounts:
            return None
        for a in accounts:
            if a["nickname"] == nickname:
                return a
        return accounts[0]

    def get_articles(
        self,
        fakeid: str,
        begin: int = 0,
        count: int = 5,
        nickname: str = "",
        query: str = ""
    ) -> Dict[str, Any]:
        """获取公众号文章列表（单页，支持号内关键词搜索）"""
        if not self.token:
            raise MPLoginError("未登录或 Token 缺失，请先调用 login()")

        log_q = f" | 关键词:「{query}」" if query else ""
        print(f"📚 拉取文章列表: fakeid={fakeid}, begin={begin}, count={count}{log_q}")

        try:
            url = (
                f"{MP_ARTICLE_LIST_API}?"
                f"sub=list&search_field=null&"
                f"begin={begin}&count={count}&query={quote(query)}&"
                f"fakeid={fakeid}&type=101_1&"
                f"free_publish_type=1&sub_action=list_ex&"
                f"token={self.token}&lang=zh_CN&f=json&ajax=1"
            )

            data = self._api_get(url)
            if data.get("base_resp", {}).get("ret") != 0:
                error_msg = data.get("base_resp", {}).get("err_msg", "未知错误")
                return {
                    "success": False,
                    "articles": [],
                    "total": 0,
                    "message": f"获取失败: {error_msg}"
                }

            publish_page = json.loads(data.get("publish_page", "{}"))
            publish_list = publish_page.get("publish_list", [])

            articles = []
            for item in publish_list:
                publish_info = json.loads(item.get("publish_info", "{}"))
                appmsgex_list = publish_info.get("appmsgex", [])

                for appmsg in appmsgex_list:
                    article = {
                        "aid": appmsg.get("aid", ""),
                        "title": appmsg.get("title", ""),
                        "url": appmsg.get("link", ""),
                        "cover": appmsg.get("cover", ""),
                        "digest": appmsg.get("digest", ""),
                        "author": appmsg.get("author_name", ""),
                        "create_time": appmsg.get("create_time", 0),
                        "update_time": appmsg.get("update_time", 0),
                        "item_show_type": appmsg.get("item_show_type", 0),
                        "is_deleted": appmsg.get("is_deleted", False),
                        "album_id": appmsg.get("album_id", ""),
                        "copyright_type": appmsg.get("copyright_type", 0),
                        "nickname": nickname
                    }
                    articles.append(article)

            total = publish_page.get("total_count", 0)
            return {
                "success": True,
                "articles": articles,
                "total": total,
                "message": f"成功获取 {len(articles)} 篇文章"
            }

        except Exception as e:
            return {
                "success": False,
                "articles": [],
                "total": 0,
                "message": f"获取文章异常: {e}"
            }

    def get_all_articles(
        self,
        fakeid: str,
        nickname: str = "",
        max_count: int = None,
        query: str = "",
        delay: tuple = (1, 2)
    ) -> Dict[str, Any]:
        """获取公众号文章（支持号内关键词过滤与自动翻页）"""
        import random

        if not self.token:
            raise MPLoginError("未登录，请先调用 login()")

        log_q = f" | 关键词过滤:「{query}」" if query else ""
        print(f"📚 开始获取推文列表: {nickname or fakeid}{log_q}")

        all_articles = []
        begin = 0
        total = 0

        try:
            while True:
                result = self.get_articles(
                    fakeid=fakeid,
                    begin=begin,
                    count=5,
                    nickname=nickname,
                    query=query
                )
                if not result["success"]:
                    return result

                if total == 0:
                    total = result["total"]
                    print(f"   匹配文章总数: {total}")

                articles = result["articles"]
                if not articles:
                    break

                for article in articles:
                    if max_count and len(all_articles) >= max_count:
                        break
                    all_articles.append(article)

                if max_count and len(all_articles) >= max_count:
                    break
                if len(all_articles) >= total:
                    break

                begin += 5
                if delay:
                    wait_time = random.uniform(delay[0], delay[1])
                    time.sleep(wait_time)

            return {
                "success": True,
                "articles": all_articles,
                "total": total,
                "message": f"成功获取 {len(all_articles)} 篇文章"
            }

        except Exception as e:
            return {
                "success": False,
                "articles": all_articles,
                "total": total,
                "message": f"获取失败: {e}"
            }


def mp_search_accounts(
    query: str,
    count: int = 10,
    headless: bool = True,
    output_file: str = None
) -> Dict[str, Any]:
    """一键搜索公众号主体列表"""
    client = WeChatMPClient()
    try:
        login_res = client.login(headless=headless)
        if not login_res["success"]:
            return {"success": False, "accounts": [], "message": login_res["message"]}

        accounts = client.search_accounts(query, count=count)
        if output_file and accounts:
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(accounts, f, ensure_ascii=False, indent=2)
            print(f"✅ 公众号列表已保存至: {output_file}")

        return {
            "success": True,
            "accounts": accounts,
            "total": len(accounts),
            "message": f"成功检索到 {len(accounts)} 个公众号"
        }
    finally:
        client.close()


def mp_login_and_get_articles(
    nickname: str,
    max_count: int = 20,
    query: str = "",
    headless: bool = True,
    output_file: str = None
) -> Dict[str, Any]:
    """一键登录并获取/搜索指定公众号文章"""
    client = WeChatMPClient()
    try:
        login_res = client.login(headless=headless)
        if not login_res["success"]:
            return login_res

        account = client.search_account(nickname)
        if not account:
            return {
                "success": False,
                "articles": [],
                "total": 0,
                "message": f"未找到指定公众号: {nickname}"
            }

        result = client.get_all_articles(
            fakeid=account["fakeid"],
            nickname=nickname,
            max_count=max_count,
            query=query
        )

        if output_file and result.get("success"):
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(result.get("articles", []), f, ensure_ascii=False, indent=2)
            print(f"✅ 文章列表已保存至: {output_file}")

        return result
    finally:
        client.close()
