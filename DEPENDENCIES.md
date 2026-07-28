# 依赖项下载与安装指南

本文档整理了 Momo Skills 运行所需要的系统软件及语言包依赖，提供官网下载地址与国内高速镜像下载地址。如果您不希望使用 `scripts/auto_config_ai.py --install` 自动安装，可以参考本指南进行手动配置。

## 1. 系统级基础软件

| 软件名称 | 官方下载地址 | 镜像/加速下载推荐 | 安装方式参考 |
|---------|------------|-----------------|-------------|
| **Node.js** (v18+) | [nodejs.org](https://nodejs.org/) | [淘宝 NPM 镜像 (npmmirror)](https://npmmirror.com/) | `brew install node` |
| **Python 3** (v3.10+) | [python.org](https://www.python.org/downloads/) | [清华大学开源软件镜像站](https://mirrors.tuna.tsinghua.edu.cn/python/) | `brew install python3` |
| **FFmpeg** | [ffmpeg.org](https://ffmpeg.org/download.html) | / | `brew install ffmpeg` |
| **yt-dlp** | [GitHub Releases](https://github.com/yt-dlp/yt-dlp/releases) | [ghproxy 代理加速下载](https://mirror.ghproxy.com/https://github.com/yt-dlp/yt-dlp/releases) | `brew install yt-dlp` |
| **lux** | [GitHub Releases](https://github.com/iawia002/lux/releases) | [ghproxy 代理加速下载](https://mirror.ghproxy.com/https://github.com/iawia002/lux/releases) | `brew install lux` 或 `go install github.com/iawia002/lux@latest` |

## 2. Python 依赖包 (pip)

包含以下核心依赖：
- `scrapling`, `html2text`, `browserforge` （网页正文提取）
- `requests` （HTTP 请求）
- `yt-dlp`, `dy-cli` （音视频相关工具）
- `playwright` （动态网页渲染）

### 安装命令（推荐使用清华镜像）
```bash
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple --break-system-packages scrapling html2text browserforge requests yt-dlp dy-cli playwright
```
*注：在较新的系统环境 (如 Ubuntu 23.04+, macOS Homebrew Python) 中，如果出现 externally-managed-environment 错误，请加上 `--break-system-packages` 参数，或者使用 venv。*

### 额外配置 (Playwright)
安装后还需要初始化 Playwright 的内置浏览器环境：
```bash
playwright install
```

## 3. Node.js 依赖包 (npm)

包含以下全局 CLI 工具：
- `defuddle` （网页内容纯净化提取）
- `@jackwener/opencli` （万站多端操作工具）

### 安装命令（推荐使用淘宝镜像）
```bash
npm install -g --registry=https://registry.npmmirror.com defuddle @jackwener/opencli
```

---

## 4. 使用自动化脚本配置（推荐）

如果您已克隆本仓库，我们强烈建议您直接使用内置的 Python 脚本一键安装并挂载全部依赖。该脚本**已经默认配置了上述的国内加速镜像**，并能根据您的系统自动完成二进制和依赖包的下载及关联。

```bash
python3 scripts/auto_config_ai.py --install
```
