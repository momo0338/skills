#!/usr/bin/env python3
"""
Momo Proxy Manager — 代理服务获取与管理脚本
同步并解析 https://github.com/momo0338/proxy 的数据，提供代理选择、轮换、测试与环境变量导出。

用法:
  python3 proxy_manager.py sync                       # 从 GitHub 同步最新代理列表
  python3 proxy_manager.py get [--protocol http|socks5] [--random|--first] [--json]
  python3 proxy_manager.py export [--protocol http|socks5]
  python3 proxy_manager.py test [--url TARGET_URL] [--timeout 5] [--limit 5]
  python3 proxy_manager.py list [--protocol http|socks5] [--limit 20]
"""

import sys
import os
import json
import random
import argparse
import urllib.request
import urllib.error
import socket

# 默认缓存数据目录
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.join(SKILL_DIR, "data")
CACHE_FILE = os.path.join(DATA_DIR, "valid_proxies.json")

RAW_DATA_URLS = {
    "json": "https://raw.githubusercontent.com/momo0338/proxy/main/data/valid_proxies.json",
    "http": "https://raw.githubusercontent.com/momo0338/proxy/main/data/valid_http.txt",
    "socks5": "https://raw.githubusercontent.com/momo0338/proxy/main/data/valid_socks5.txt",
}

def ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)

def fetch_url(url, timeout=10):
    req = urllib.request.Request(url, headers={"User-Agent": "MomoProxySkill/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8")

def sync_data():
    """从 GitHub 同步最新代理列表到本地缓存"""
    ensure_data_dir()
    print("🔄 正在从 https://github.com/momo0338/proxy 同步最新代理数据...", file=sys.stderr)
    
    success_count = 0
    for key, url in RAW_DATA_URLS.items():
        try:
            content = fetch_url(url)
            filename = "valid_proxies.json" if key == "json" else f"valid_{key}.txt"
            filepath = os.path.join(DATA_DIR, filename)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"  ✅ 已更新 {filename} ({len(content)} 字节)", file=sys.stderr)
            success_count += 1
        except Exception as e:
            print(f"  ❌ 同步 {key} 失败: {e}", file=sys.stderr)
            
    return success_count > 0

def load_proxies():
    """读取本地缓存的代理列表（若不存在则自动同步）"""
    if not os.path.exists(CACHE_FILE):
        sync_data()
        
    if not os.path.exists(CACHE_FILE):
        return {"total": 0, "by_protocol": {}}
        
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"⚠️ 读取缓存代理失败: {e}", file=sys.stderr)
        return {"total": 0, "by_protocol": {}}

def get_proxy_list(protocol=None):
    """获取所有可用代理地址列表"""
    data = load_proxies()
    by_proto = data.get("by_protocol", {})
    
    results = []
    if protocol and protocol.lower() in by_proto:
        results = by_proto[protocol.lower()].get("addresses", [])
    else:
        for proto, pdata in by_proto.items():
            results.extend(pdata.get("addresses", []))
            
    return results

def test_proxy(proxy_url, target_url="https://httpbin.org/ip", timeout=5):
    """验证单台代理连接可用度与延迟"""
    start_time = socket.gettimeofday() if hasattr(socket, "gettimeofday") else None
    
    try:
        import time
        start_t = time.time()
        
        handler = urllib.request.ProxyHandler({
            "http": proxy_url,
            "https": proxy_url
        })
        opener = urllib.request.build_opener(handler)
        req = urllib.request.Request(target_url, headers={"User-Agent": "MomoProxyTester/1.0"})
        
        with opener.open(req, timeout=timeout) as resp:
            data = resp.read().decode("utf-8", errors="ignore")
            latency_ms = round((time.time() - start_t) * 1000, 2)
            return True, latency_ms, data[:200]
    except Exception as e:
        return False, 0, str(e)

def main():
    parser = argparse.ArgumentParser(description="Momo Proxy Manager — 代理服务获取与管理脚本")
    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # sync
    subparsers.add_parser("sync", help="从 GitHub 同步最新代理数据")

    # get
    get_parser = subparsers.add_parser("get", help="随机获取一个可用代理")
    get_parser.add_argument("--protocol", choices=["http", "socks5"], help="筛选代理协议")
    get_parser.add_argument("--random", action="store_true", default=True, help="随机选取一个")
    get_parser.add_argument("--json", action="store_true", help="JSON 格式输出")

    # export
    export_parser = subparsers.add_parser("export", help="输出环境变量设置指令")
    export_parser.add_argument("--protocol", choices=["http", "socks5"], default="http", help="代理协议")

    # list
    list_parser = subparsers.add_parser("list", help="列出已知代理")
    list_parser.add_argument("--protocol", choices=["http", "socks5"], help="筛选代理协议")
    list_parser.add_argument("--limit", type=int, default=20, help="限制返回数量")

    # test
    test_parser = subparsers.add_parser("test", help="测试代理可用性与延迟")
    test_parser.add_argument("--url", default="https://httpbin.org/ip", help="测试目标 URL")
    test_parser.add_argument("--protocol", choices=["http", "socks5"], help="筛选代理协议")
    test_parser.add_argument("--timeout", type=int, default=5, help="超时时间 (秒)")
    test_parser.add_argument("--limit", type=int, default=5, help="测试数量")

    args = parser.parse_args()

    if args.command == "sync":
        ok = sync_data()
        sys.exit(0 if ok else 1)

    elif args.command == "get":
        proxies = get_proxy_list(args.protocol)
        if not proxies:
            print("❌ 未获取到可用的代理。尝试运行 python3 proxy_manager.py sync", file=sys.stderr)
            sys.exit(1)

        selected = random.choice(proxies) if args.random else proxies[0]

        if args.json:
            print(json.dumps({"proxy": selected, "total_available": len(proxies)}, ensure_ascii=False, indent=2))
        else:
            print(selected)

    elif args.command == "export":
        proxies = get_proxy_list(args.protocol)
        if not proxies:
            print("❌ 没有可用代理", file=sys.stderr)
            sys.exit(1)
        selected = random.choice(proxies)
        print(f"export HTTP_PROXY=\"{selected}\"")
        print(f"export HTTPS_PROXY=\"{selected}\"")
        print(f"export ALL_PROXY=\"{selected}\"")

    elif args.command == "list":
        proxies = get_proxy_list(args.protocol)
        limit = args.limit
        for p in proxies[:limit]:
            print(p)
        print(f"\nTotal shown: {min(len(proxies), limit)} / {len(proxies)}", file=sys.stderr)

    elif args.command == "test":
        proxies = get_proxy_list(args.protocol)
        if not proxies:
            print("❌ 没有可用代理", file=sys.stderr)
            sys.exit(1)

        sample = random.sample(proxies, min(len(proxies), args.limit))
        print(f"🔍 开始测试 {len(sample)} 个代理Against: {args.url} (Timeout: {args.timeout}s)...")

        valid_count = 0
        for p in sample:
            ok, latency, msg = test_proxy(p, target_url=args.url, timeout=args.timeout)
            if ok:
                valid_count += 1
                print(f"  ✅ [可用] {p} - 延迟: {latency}ms")
            else:
                print(f"  ❌ [失败] {p} - 错误: {msg}")

        print(f"\n测试完成: {valid_count}/{len(sample)} 个代理可直连。")

    else:
        parser.print_help()

if __name__ == "__main__":
    main()
