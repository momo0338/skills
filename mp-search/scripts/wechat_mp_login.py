#!/usr/bin/env python3
"""
微信公众平台扫码登录和文章获取模块

参考项目：
- wechat-article-assistant: 扫码登录 + Cookie管理 + 文章列表API
- weChat_collector: 短链接解析 + fakeid搜索

功能：
1. 扫码登录微信公众平台
2. 保存和复用Cookie
3. 搜索公众号获取fakeid
4. 获取公众号文章列表（返回短链接）
"""

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse, parse_qs

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

# Cookie文件路径
COOKIE_FILE = os.path.join(os.path.dirname(__file__), ".mp_cookies.json")


class MPLoginError(Exception):
    """公众平台登录错误"""
    def __init__(self, message: str, code: int = 0):
        self.message = message
        self.code = code
        super().__init__(self.message)


class WeChatMPClient:
    """微信公众平台客户端"""

    def __init__(self, cookie_file: str = None):
        """初始化客户端
        
        Args:
            cookie_file: Cookie文件路径，默认使用.mp_cookies.json
        """
        self.cookie_file = cookie_file or COOKIE_FILE
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.token = None
        self.cookies = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def close(self):
        """关闭浏览器"""
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()

    def _save_cookies(self):
        """保存Cookie到文件"""
        try:
            cookies = self.context.cookies()
            with open(self.cookie_file, "w", encoding="utf-8") as f:
                json.dump(cookies, f, ensure_ascii=False, indent=2)
            print(f"✅ Cookie已保存到: {self.cookie_file}")
        except Exception as e:
            print(f"⚠️ 保存Cookie失败: {e}")

    def _load_cookies(self) -> bool:
        """从文件加载Cookie
        
        Returns:
            是否加载成功
        """
        if not os.path.exists(self.cookie_file):
            return False
        
        try:
            with open(self.cookie_file, "r", encoding="utf-8") as f:
                cookies = json.load(f)
            self.context.add_cookies(cookies)
            print(f"✅ 已从文件加载Cookie: {self.cookie_file}")
            return True
        except Exception as e:
            print(f"⚠️ 加载Cookie失败: {e}")
            return False

    def _validate_cookies(self) -> bool:
        """验证Cookie是否有效
        
        Returns:
            Cookie是否有效
        """
        try:
            self.page.goto(f"{MP_BASE_URL}/cgi-bin/home", wait_until="domcontentloaded", timeout=10000)
            self.page.wait_for_timeout(2000)
            
            current_url = self.page.url
            if "cgi-bin/home" in current_url or "cgi-bin/frame" in current_url:
                return True
            return False
        except Exception:
            return False

    def _extract_token(self) -> Optional[str]:
        """从页面URL或Cookie中提取token
        
        Returns:
            token字符串或None
        """
        # 方法1：从URL参数提取
        url = self.page.url
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        tokens = params.get("token")
        if tokens:
            return tokens[0]

        # 方法2：从Cookie提取
        try:
            cookies = self.context.cookies()
            for cookie in cookies:
                if cookie["name"] == "token":
                    return cookie["value"]
        except Exception:
            pass

        return None

    def login(self, headless: bool = False, timeout: int = 120) -> Dict[str, Any]:
        """扫码登录微信公众平台
        
        Args:
            headless: 是否无头模式
            timeout: 登录超时时间（秒）
            
        Returns:
            {
                "success": bool,
                "token": str,
                "cookies": list,
                "message": str
            }
        """
        print("=" * 60)
        print("微信公众平台扫码登录")
        print("=" * 60)

        try:
            # 启动Playwright
            self.playwright = sync_playwright().start()
            self.browser = self.playwright.chromium.launch(headless=headless)
            self.context = self.browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 800}
            )
            self.page = self.context.new_page()

            return self._do_login(timeout)

        except Exception as e:
            print(f"\n❌ 登录失败: {e}")
            self.close()
            return {
                "success": False,
                "token": None,
                "cookies": [],
                "message": f"登录失败: {e}"
            }

    def _do_login(self, timeout: int) -> Dict[str, Any]:
        """执行登录流程（内部方法）"""
        try:
            # 尝试加载已有Cookie
            if self._load_cookies():
                print("\n尝试试用已有Cookie...")
                self.page.goto(MP_BASE_URL, wait_until="domcontentloaded", timeout=15000)
                self.page.wait_for_timeout(2000)

                # 检查Cookie是否有效
                if self._validate_cookies():
                    self.token = self._extract_token()
                    self.cookies = self.context.cookies()
                    
                    if self.token:
                        print("✅ Cookie有效，无需重新登录")
                        return {
                            "success": True,
                            "token": self.token,
                            "cookies": self.cookies,
                            "message": "Cookie登录成功"
                        }
                    else:
                        print("⚠️ Cookie中未找到token，需要重新登录")
                else:
                    print("⚠️ Cookie已失效，需要重新登录")

            # 打开登录页面
            print("\n正在打开登录页面...")
            self.page.goto(MP_LOGIN_URL, wait_until="domcontentloaded", timeout=15000)
            self.page.wait_for_timeout(3000)

            # 等待二维码出现
            print("等待二维码加载...")
            self.page.wait_for_timeout(2000)

            # 截取二维码
            print("\n📱 请用微信扫码登录（需要绑定公众号的微信）")
            print("⏳ 等待扫码中...")

            # 轮询等待登录成功
            start_time = time.time()
            while time.time() - start_time < timeout:
                current_url = self.page.url
                
                # 检查是否登录成功
                if "cgi-bin/home" in current_url or "cgi-bin/frame" in current_url:
                    print("\n✅ 登录成功！")
                    
                    # 提取token
                    self.token = self._extract_token()
                    if not self.token:
                        print("⚠️ 未获取到token")
                        return {
                            "success": False,
                            "token": None,
                            "cookies": [],
                            "message": "未获取到token"
                        }

                    # 保存Cookie
                    self.cookies = self.context.cookies()
                    self._save_cookies()

                    print(f"✅ Token: {self.token[:20]}...")
                    print(f"✅ Cookie数量: {len(self.cookies)}")

                    return {
                        "success": True,
                        "token": self.token,
                        "cookies": self.cookies,
                        "message": "扫码登录成功"
                    }

                # 检查是否已扫码（在loginpage页面）
                if "loginpage" in current_url:
                    print("✅ 已扫码，请在手机上确认登录...")

                self.page.wait_for_timeout(1000)

            # 超时
            print(f"\n❌ 登录超时（{timeout}秒）")
            self.close()
            return {
                "success": False,
                "token": None,
                "cookies": [],
                "message": f"登录超时（{timeout}秒）"
            }

        except Exception as e:
            print(f"\n❌ 登录失败: {e}")
            self.close()
            return {
                "success": False,
                "token": None,
                "cookies": [],
                "message": f"登录失败: {e}"
            }

    def search_account(self, nickname: str) -> Optional[Dict[str, Any]]:
        """搜索公众号获取fakeid
        
        Args:
            nickname: 公众号名称
            
        Returns:
            {
                "fakeid": str,
                "nickname": str,
                "alias": str,
                "round_head_img": str
            } 或 None
        """
        if not self.token:
            raise MPLoginError("未登录，请先调用login()")

        print(f"\n🔍 搜索公众号: {nickname}")

        try:
            from urllib.parse import quote
            
            url = (
                f"{MP_SEARCH_API}?"
                f"action=search_biz&begin=0&count=5&"
                f"token={self.token}&lang=zh_CN&f=json&ajax=1&"
                f"query={quote(nickname)}"
            )

            response = self.page.request.get(url)
            data = response.json()

            if data.get("base_resp", {}).get("ret") != 0:
                error_msg = data.get("base_resp", {}).get("err_msg", "未知错误")
                print(f"❌ 搜索失败: {error_msg}")
                return None

            biz_list = data.get("list", [])
            if not biz_list:
                print(f"❌ 未找到公众号: {nickname}")
                return None

            # 精确匹配
            for item in biz_list:
                if item.get("nickname") == nickname:
                    print(f"✅ 找到公众号: {nickname}")
                    print(f"   fakeid: {item.get('fakeid')}")
                    return {
                        "fakeid": item.get("fakeid"),
                        "nickname": item.get("nickname"),
                        "alias": item.get("alias", ""),
                        "round_head_img": item.get("round_head_img", "")
                    }

            # 取第一个结果
            item = biz_list[0]
            print(f"⚠️ 未精确匹配，使用第一个结果: {item.get('nickname')}")
            return {
                "fakeid": item.get("fakeid"),
                "nickname": item.get("nickname"),
                "alias": item.get("alias", ""),
                "round_head_img": item.get("round_head_img", "")
            }

        except Exception as e:
            print(f"❌ 搜索公众号失败: {e}")
            return None

    def get_articles(
        self,
        fakeid: str,
        begin: int = 0,
        count: int = 5,
        nickname: str = ""
    ) -> Dict[str, Any]:
        """获取公众号文章列表（单页）
        
        Args:
            fakeid: 公众号fakeid
            begin: 起始位置
            count: 获取数量（最大5）
            nickname: 公众号名称（用于显示）
            
        Returns:
            {
                "success": bool,
                "articles": list,
                "total": int,
                "message": str
            }
        """
        if not self.token:
            raise MPLoginError("未登录，请先调用login()")

        print(f"\n📚 获取文章列表: fakeid={fakeid}, begin={begin}, count={count}")

        try:
            url = (
                f"{MP_ARTICLE_LIST_API}?"
                f"sub=list&search_field=null&"
                f"begin={begin}&count={count}&query=&"
                f"fakeid={fakeid}&type=101_1&"
                f"free_publish_type=1&sub_action=list_ex&"
                f"token={self.token}&lang=zh_CN&f=json&ajax=1"
            )

            response = self.page.request.get(url)
            data = response.json()

            if data.get("base_resp", {}).get("ret") != 0:
                error_msg = data.get("base_resp", {}).get("err_msg", "未知错误")
                return {
                    "success": False,
                    "articles": [],
                    "total": 0,
                    "message": f"获取失败: {error_msg}"
                }

            # 解析文章数据
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
                        "url": appmsg.get("link", ""),  # 这就是短链接！
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

            print(f"✅ 获取成功，本页 {len(articles)} 篇，总计 {total} 篇")

            return {
                "success": True,
                "articles": articles,
                "total": total,
                "message": f"成功获取 {len(articles)} 篇文章"
            }

        except Exception as e:
            print(f"❌ 获取文章列表失败: {e}")
            return {
                "success": False,
                "articles": [],
                "total": 0,
                "message": f"获取失败: {e}"
            }

    def get_all_articles(
        self,
        fakeid: str,
        nickname: str = "",
        max_count: int = None,
        delay: tuple = (1, 3)
    ) -> Dict[str, Any]:
        """获取公众号全部文章（自动翻页）
        
        Args:
            fakeid: 公众号fakeid
            nickname: 公众号名称
            max_count: 最大获取数量，None表示全部
            delay: 请求间隔（最小值，最大值）
            
        Returns:
            {
                "success": bool,
                "articles": list,
                "total": int,
                "message": str
            }
        """
        import random

        if not self.token:
            raise MPLoginError("未登录，请先调用login()")

        print(f"\n📚 开始获取全部文章: {nickname or fakeid}")
        if max_count:
            print(f"   最大数量: {max_count}")

        all_articles = []
        begin = 0
        total = 0

        try:
            while True:
                # 获取一页数据
                result = self.get_articles(fakeid, begin=begin, count=5, nickname=nickname)
                
                if not result["success"]:
                    return result

                # 首次获取时记录总数
                if total == 0:
                    total = result["total"]
                    print(f"   文章总数: {total}")

                articles = result["articles"]
                if not articles:
                    print("   没有更多文章")
                    break

                # 添加到列表
                for article in articles:
                    if max_count and len(all_articles) >= max_count:
                        break
                    all_articles.append(article)

                # 检查是否达到最大数量
                if max_count and len(all_articles) >= max_count:
                    print(f"   已达到最大数量: {max_count}")
                    break

                # 检查是否获取完毕
                if len(all_articles) >= total:
                    print("   已获取全部文章")
                    break

                # 翻页
                begin += 5

                # 随机延时
                if delay:
                    wait_time = random.uniform(delay[0], delay[1])
                    print(f"   等待 {wait_time:.1f} 秒...")
                    time.sleep(wait_time)

            print(f"\n✅ 获取完成，共 {len(all_articles)} 篇文章")

            return {
                "success": True,
                "articles": all_articles,
                "total": total,
                "message": f"成功获取 {len(all_articles)} 篇文章"
            }

        except Exception as e:
            print(f"\n❌ 获取全部文章失败: {e}")
            return {
                "success": False,
                "articles": all_articles,
                "total": total,
                "message": f"获取失败: {e}"
            }


def mp_login_and_get_articles(
    nickname: str,
    max_count: int = 20,
    headless: bool = False,
    output_file: str = None
) -> Dict[str, Any]:
    """一键登录并获取公众号文章
    
    Args:
        nickname: 公众号名称
        max_count: 最大获取数量
        headless: 是否无头模式
        output_file: 输出文件路径
        
    Returns:
        {
            "success": bool,
            "articles": list,
            "total": int,
            "message": str
        }
    """
    client = WeChatMPClient()
    
    try:
        # 1. 登录
        login_result = client.login(headless=headless)
        if not login_result["success"]:
            return login_result

        # 2. 搜索公众号
        account = client.search_account(nickname)
        if not account:
            return {
                "success": False,
                "articles": [],
                "total": 0,
                "message": f"未找到公众号: {nickname}"
            }

        # 3. 获取文章
        result = client.get_all_articles(
            fakeid=account["fakeid"],
            nickname=nickname,
            max_count=max_count
        )

        # 4. 保存结果
        if output_file and result["success"]:
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(result["articles"], f, ensure_ascii=False, indent=2)
            print(f"\n✅ 结果已保存到: {output_file}")

        return result

    finally:
        client.close()
