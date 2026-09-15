#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
工具模块
包含HTTP客户端管理、限流器、缓存管理器、User-Agent池
"""

import hashlib
import json
import os
import random
import re
import sys
import time
import urllib.request
import urllib.error
import urllib.parse
from typing import Dict, Tuple, Any, Optional

# 可选HTTP库
REQUESTS_AVAILABLE = False
HTTPX_AVAILABLE = False

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    pass

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    pass


# ============================================================
# 限流器
# ============================================================

class RateLimiter:
    """请求限流器"""
    
    def __init__(self, max_per_minute=10, max_per_hour=100):
        self.max_per_minute = max_per_minute
        self.max_per_hour = max_per_hour
        self.minute_requests = []
        self.hour_requests = []
    
    def wait_if_needed(self):
        """如果需要限流则等待"""
        now = time.time()
        
        # 清理过期记录
        self.minute_requests = [t for t in self.minute_requests if now - t < 60]
        self.hour_requests = [t for t in self.hour_requests if now - t < 3600]
        
        # 检查分钟限制
        if len(self.minute_requests) >= self.max_per_minute:
            wait_time = 60 - (now - self.minute_requests[0])
            if wait_time > 0:
                print(f"⏱️  限流：等待{wait_time:.1f}秒（分钟限制）", file=sys.stderr)
                time.sleep(wait_time)
        
        # 检查小时限制
        if len(self.hour_requests) >= self.max_per_hour:
            wait_time = 3600 - (now - self.hour_requests[0])
            if wait_time > 0:
                print(f"⏱️  限流：等待{wait_time:.1f}秒（小时限制）", file=sys.stderr)
                time.sleep(wait_time)
        
        # 记录请求
        self.minute_requests.append(now)
        self.hour_requests.append(now)


# ============================================================
# 缓存管理器
# ============================================================

class CacheManager:
    """简单文件缓存管理器"""
    
    def __init__(self, cache_dir='.wechat_cache', ttl=3600):
        self.cache_dir = cache_dir
        self.ttl = ttl
        os.makedirs(cache_dir, exist_ok=True)
    
    def _get_cache_file(self, key: str) -> str:
        """生成缓存文件路径"""
        key_hash = hashlib.md5(key.encode()).hexdigest()
        return os.path.join(self.cache_dir, f"{key_hash}.json")
    
    def get(self, key: str) -> Optional[Any]:
        """获取缓存"""
        cache_file = self._get_cache_file(key)
        
        if not os.path.exists(cache_file):
            return None
        
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 检查是否过期
            if time.time() - data['timestamp'] > self.ttl:
                os.remove(cache_file)
                return None
            
            print(f"💾 缓存命中: {key[:50]}...", file=sys.stderr)
            return data['value']
        except (json.JSONDecodeError, KeyError, IOError):
            return None
    
    def set(self, key: str, value: Any):
        """设置缓存"""
        cache_file = self._get_cache_file(key)
        
        try:
            data = {
                'timestamp': time.time(),
                'value': value,
            }
            
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False)
        except Exception as e:
            print(f"⚠️  写入缓存失败: {e}", file=sys.stderr)
    
    def clear(self):
        """清空缓存"""
        if os.path.exists(self.cache_dir):
            import shutil
            shutil.rmtree(self.cache_dir)
            os.makedirs(self.cache_dir, exist_ok=True)
            print("🗑️  缓存已清空", file=sys.stderr)


# ============================================================
# User-Agent 池
# ============================================================

USER_AGENTS = [
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_2_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1',
    'Mozilla/5.0 (Linux; Android 14; Pixel 8 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Mobile Safari/537.36',
]

MOBILE_USER_AGENTS = [
    'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
]


def get_random_user_agent(mobile: bool = False) -> str:
    """获取随机User-Agent"""
    if mobile:
        return random.choice(MOBILE_USER_AGENTS)
    return random.choice(USER_AGENTS)


# ============================================================
# HTTP客户端管理（智能降级策略）
# ============================================================

class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """自定义不跟随重定向的处理器"""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None
    
    def http_error_302(self, req, fp, code, msg, headers):
        return fp


class HTTPClientManager:
    """HTTP客户端管理器，支持智能降级"""
    
    def __init__(self):
        self.preference_order = []
        if REQUESTS_AVAILABLE:
            self.preference_order.append('requests')
        if HTTPX_AVAILABLE:
            self.preference_order.append('httpx')
        self.preference_order.append('urllib')
    
    def get(self, url: str, headers: Dict = None, timeout: int = 10, allow_redirects: bool = True) -> Tuple[bool, str]:
        """发送GET请求，自动降级"""
        if headers is None:
            headers = {}
        
        for client in self.preference_order:
            try:
                if client == 'requests':
                    return self._requests_get(url, headers, timeout, allow_redirects)
                elif client == 'httpx':
                    return self._httpx_get(url, headers, timeout, allow_redirects)
                elif client == 'urllib':
                    return self._urllib_get(url, headers, timeout, allow_redirects)
            except Exception as e:
                print(f"  {client}请求失败: {e}，尝试下一个...", file=sys.stderr)
                continue
        
        return False, ""
    
    def _requests_get(self, url: str, headers: Dict, timeout: int, allow_redirects: bool) -> Tuple[bool, str]:
        """使用requests发送请求"""
        try:
            response = requests.get(url, headers=headers, timeout=timeout, allow_redirects=allow_redirects)
            response.raise_for_status()
            return True, response.text
        except requests.exceptions.HTTPError as e:
            if response and 300 <= response.status_code < 400:
                return True, response.text
            raise
    
    def _httpx_get(self, url: str, headers: Dict, timeout: int, allow_redirects: bool) -> Tuple[bool, str]:
        """使用httpx发送请求"""
        with httpx.Client(follow_redirects=allow_redirects) as client:
            response = client.get(url, headers=headers, timeout=timeout)
            if 300 <= response.status_code < 400:
                return True, response.text
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError:
                if 300 <= response.status_code < 400:
                    return True, response.text
                raise
            return True, response.text
    
    def _urllib_get(self, url: str, headers: Dict, timeout: int, allow_redirects: bool) -> Tuple[bool, str]:
        """使用urllib发送请求"""
        req = urllib.request.Request(url, headers=headers)
        if not allow_redirects:
            opener = urllib.request.build_opener(NoRedirectHandler)
            response = opener.open(req, timeout=timeout)
        else:
            response = urllib.request.urlopen(req, timeout=timeout)
        html = response.read().decode('utf-8', errors='replace')
        return True, html


# 全局实例
rate_limiter = RateLimiter(max_per_minute=10, max_per_hour=100)
cache_manager = CacheManager(cache_dir='.wechat_cache', ttl=3600)
http_manager = HTTPClientManager()
