---
name: videodl
description: |
  使用 videodl 命令行工具下载各大平台的视频。
  支持通过指定视频 URL (-i) 直接下载。
  触发词：videodl, 下载视频, videodl下载
---

# videodl — 视频下载命令行 Skill

> 基于 CharlesPikachu/videodl，支持终端命令行直接下载视频。

## 安装

如果尚未安装，可以使用 `pip` 安装：
```bash
pip install videodl
```

## 使用方法

### 基本下载
通过 `-i` 参数指定想要下载的视频链接。它会自动匹配支持的平台并下载。
默认下载路径为执行命令时的当前目录。
```bash
videodl -i "https://example.com/video/123"
```

### 指定保存目录
可以通过 `-c` 参数指定下载路径（通过 JSON 配置中的 `work_dir`）：
```bash
videodl -i "https://example.com/video/123" -c '{"work_dir": "/absolute/path/to/downloads"}'
```

### 环境要求与沙箱问题
因为该命令依赖网络请求，在受限执行环境（沙箱）中，例如在使用 rich 库时可能会因获取当前工作目录失败而报错 `PermissionError`，或遭遇网络隔离。
在 AI Agent 自动执行此工具时，必须请求**网络提权 (Bypass Sandbox = true)** 以便顺利执行。

## 参数说明

- `-i, --index-url` : 指定视频的 URL 链接。
- `-a, --allowed-video-sources` : 指定要搜索和使用的平台名称，多个用逗号隔开。
- `-c, --init-video-clients-cfg` : 通过 JSON 字符串指定初始配置，例如 `work_dir`。
- `-r, --requests-overrides` : 通过 JSON 配置覆盖 requests 参数，例如 `proxies`。
