# Proxy — 代理池获取与管理 Skill

> **中文** · [English below](#english)

数据源同步自 [momo0338/proxy](https://github.com/momo0338/proxy/tree/main/data)，提供可自动同步、轮换与测试的 HTTP/SOCKS5 代理池服务。

> Proxy management skill syncing data from [momo0338/proxy](https://github.com/momo0338/proxy/tree/main/data). Provides automatic sync, rotation, testing, and environment export for HTTP/SOCKS5 proxies.

---

## 这是什么 / What is this

一个让 AI 助手和其他技能能够便捷复用代理节点的 Skill。当其他网络请求或下载工具（如 `yt-dlp`、`scrapling`、`curl`、`requests`）遇到 IP 封禁、403 错误或地域限制时，可调用本技能获取有效代理并进行流量转发。

### 核心亮点 / Highlights

- **实时 GitHub 同步**：一键同步 `momo0338/proxy` 仓库中的最新验证节点
- **多协议支持**：支持 HTTP/HTTPS 与 SOCKS5 协议节点
- **智能轮换**：支持随机选择节点与可用性连接延迟测试
- **无缝集成**：可直接输出环境变量 `export HTTP_PROXY=...` 或供其他 Shell/Python 脚本直接调用

---

## 快速开始 / Quick Start

### 1. 同步最新代理

```bash
python3 scripts/proxy_manager.py sync
```

### 2. 获取可用代理

```bash
# 获取随机 HTTP 代理
python3 scripts/proxy_manager.py get --protocol http

# 获取随机 SOCKS5 代理 (JSON 格式)
python3 scripts/proxy_manager.py get --protocol socks5 --json
```

### 3. 测试代理延迟

```bash
python3 scripts/proxy_manager.py test --limit 5
```

---

## 数据格式说明

缓存数据存储于 `data/` 目录下：
- `data/valid_proxies.json`: 包含 `total`, `by_protocol` 分类汇总及节点列表
- `data/valid_http.txt`: HTTP 代理纯文本列表
- `data/valid_socks5.txt`: SOCKS5 代理纯文本列表

---

<a name="english"></a>

# Proxy Skill — English

> Free proxy manager and rotation tool synced with `momo0338/proxy`.

## Usage

```bash
# Sync proxies from GitHub
python3 scripts/proxy_manager.py sync

# Get random proxy
python3 scripts/proxy_manager.py get --protocol http

# Test proxies
python3 scripts/proxy_manager.py test --limit 5
```
