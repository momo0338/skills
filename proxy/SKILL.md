---
name: proxy
description: |
  提供来自于 momo0338/proxy 仓库的免费/公共代理池管理与轮换服务。
  包含 HTTP/HTTPS 与 SOCKS5 代理列表获取、自动同步、可用度测试、随机轮换与环境变量导出。
  当任何工具或技能（如 yt-dlp、scrapling、opencli、curl、requests 等）在访问网络时遭遇 IP 封禁、403 Forbidden、地域限制、429 请求超限或网络超时报错时自动触发使用。
  触发词：proxy、代理、代理服务器、HTTP代理、SOCKS5代理、网络封禁、403Forbidden、IP被封、代理轮换。
version: 1.0.0
---

# Proxy — 代理池获取与管理 Skill

> 数据同步自 [momo0338/proxy](https://github.com/momo0338/proxy/tree/main/data)，提供 HTTP/SOCKS5 代理轮换与测试。

## Overview

[proxy](file:///Users/zhugx/src/skills/proxy) 技能用于在其他网络工具/技能遇到 IP 屏蔽、防爬阻断、403 错误或地理限制时提供代理节点支持。代理数据实时缓存于本地，支持自动同 GitHub 仓库拉取最新有效节点。

## When to Use

在以下情况发生时，**必须优先使用此技能获取代理并配置到相应工具中**：
1. `yt-dlp` 下载报错 `HTTP Error 403: Forbidden` 或 `IP blocked`
2. `scrapling` 或 `requests` 网页提取遭遇 403/429 防爬墙拦截
3. `curl` 或 API 请求超时/拒绝连接
4. 需要模拟异地/海外网络环境发起请求

## 核心命令与脚本

使用脚本 `<SKILL_DIR>/scripts/proxy_manager.py` 操作代理池：

### 1. 同步最新代理数据 (From GitHub)

```bash
python3 <SKILL_DIR>/scripts/proxy_manager.py sync
```

### 2. 获取一个随机代理地址

```bash
# 获取随机代理 (默认协议)
python3 <SKILL_DIR>/scripts/proxy_manager.py get

# 获取 HTTP 代理
python3 <SKILL_DIR>/scripts/proxy_manager.py get --protocol http

# 获取 SOCKS5 代理 (JSON 格式)
python3 <SKILL_DIR>/scripts/proxy_manager.py get --protocol socks5 --json
```

### 3. 测试代理可用度与延迟

```bash
python3 <SKILL_DIR>/scripts/proxy_manager.py test --url "https://httpbin.org/ip" --limit 5
```

### 4. 导出环境变量设置命令

```bash
python3 <SKILL_DIR>/scripts/proxy_manager.py export --protocol http
```

---

## 常用工具集成方法

### 1. 与 yt-dlp 配合使用

```bash
# 获取一个 HTTP 代理
PROXY=$(python3 <SKILL_DIR>/scripts/proxy_manager.py get --protocol http)

# 传入 yt-dlp
yt-dlp --proxy "$PROXY" "https://www.youtube.com/watch?v=xxx"
```

### 2. 与 curl 配合使用

```bash
PROXY=$(python3 <SKILL_DIR>/scripts/proxy_manager.py get --protocol http)
curl -x "$PROXY" -s "https://httpbin.org/ip"
```

### 3. 与 Python requests / Scrapling 配合使用

```python
import os
import subprocess

# 动态调用 proxy_manager.py 获取代理
proxy_url = subprocess.check_output([
    "python3", "/Users/zhugx/src/skills/proxy/scripts/proxy_manager.py", "get", "--protocol", "http"
]).decode().strip()

# 在 requests 中配置
import requests
response = requests.get("https://example.com", proxies={"http": proxy_url, "https": proxy_url})

# 或设置环境变量
os.environ["HTTP_PROXY"] = proxy_url
os.environ["HTTPS_PROXY"] = proxy_url
```

---

## 错误恢复策略

- 如果获取到的代理无法连通（连接超时或拒绝）：
  1. 重新运行 `python3 <SKILL_DIR>/scripts/proxy_manager.py get` 获取另一个代理。
  2. 运行 `python3 <SKILL_DIR>/scripts/proxy_manager.py sync` 刷新本地代理池。
