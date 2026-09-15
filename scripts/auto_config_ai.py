#!/usr/bin/env python3
"""
Momo Skills — 自动检测本机 AI 工具并配置技能共享
自动扫描系统中的 Claude Code、Gemini/Antigravity、Codex、WorkBuddy、Trae、OpenCode、Cursor、Windsurf、OpenClaw 等 AI 助手配置，
将本 repo 中的技能自动挂载/配置到各大 AI 助手中，实现全平台 AI 技能统一管理。

配置前自动检查各技能的依赖是否已安装，缺失时可自动安装。
支持 Windows 和 macOS，网络不通时自动使用 proxy 技能的代理池下载。

Usage:
  python3 scripts/auto_config_ai.py              # 检查依赖并配置所有已安装的 AI 助手
  python3 scripts/auto_config_ai.py --install    # 自动安装缺失依赖后再配置
  python3 scripts/auto_config_ai.py --dry-run    # 仅检测并预览将要执行的操作
  python3 scripts/auto_config_ai.py --skip-deps  # 跳过依赖检查直接配置
  python3 scripts/auto_config_ai.py --skills-dir /path/to/skills

Platform support:
  - Windows: 用 junction 创建链接，pip Scripts 目录搜索，GitHub 镜像 + 代理下载
  - macOS:   用 symlink 创建链接，pip bin 目录搜索，brew 优先安装
  - Linux:   同 macOS，支持 brew/go 安装
"""

import argparse
import json
import os
import platform
import re
import shlex
import shutil
import subprocess
import sys
import urllib.request

# 获取根技能目录
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_SKILLS_DIR = os.path.dirname(SCRIPT_DIR)
HOME_DIR = os.path.expanduser("~")

# ============================================================================
# 依赖声明注册表
# 每个技能可在此声明所需依赖，也可以在 SKILL.md frontmatter 中声明
# ============================================================================
SKILL_DEPS = {
    "competition-write": {},
    "geomap": {},
    "github-cli": {
        "bins": ["gh"],
        "brew_bins": ["gh"],
        "install_cmds": {
            "brew": "brew install gh",
        },
    },
    "guide-write": {},
    "ima-skill": {},
    "mp-html": {},
    "mp-publish": {},
    "mp-save": {},
    "dy-cli": {
        "bins": ["dy"],
        "pip": ["dy-cli", "playwright"],
        "pip_bins": {"dy": "dy-cli"},
        "install_cmds": {
            "pip": "pip install dy-cli playwright",
            "post_install": "playwright install",
        },
    },
    "dy-wode": {
        "bins": ["dy", "ego-browser"],
        "pip": ["dy-cli", "openpyxl"],
        "pip_bins": {"dy": "dy-cli"},
        "install_cmds": {
            "pip": "pip install dy-cli openpyxl",
        },
    },
    "opencli": {
        "bins": ["opencli"],
        "npm": ["@jackwener/opencli"],
        "npm_bins": {"opencli": "@jackwener/opencli"},
        "install_cmds": {
            "npm": "npm install -g @jackwener/opencli",
        },
    },
    "yt-dlp": {
        "bins": ["yt-dlp", "ffmpeg"],
        "pip": ["yt-dlp"],
        "pip_bins": {"yt-dlp": "yt-dlp[default]"},
        "brew_bins": ["ffmpeg", "yt-dlp"],
        "download_bins": ["ffmpeg"],
        "install_cmds": {
            "pip": "pip install -U yt-dlp",
            "brew": "brew install yt-dlp ffmpeg",
            "windows_download": "_install_ffmpeg_windows",
            "post_install": "_post_install_ffmpeg",
        },
    },
    "lux": {
        "bins": ["lux"],
        "brew_bins": ["lux"],
        "go_bins": ["lux"],
        "download_bins": ["lux"],
        "install_cmds": {
            "brew": "brew install lux",
            "go": "go install github.com/iawia002/lux@latest",
            "windows_download": "_install_lux_binary",
            "macos_download": "_install_lux_binary",
        },
    },
    "scrapling": {
        "pip": ["scrapling", "html2text"],
        "install_cmds": {
            "pip": "pip install scrapling html2text",
        },
    },
    "zhihu-search": {
        "bins": ["python3"],
        "env": ["ZHIHU_ACCESS_SECRET"],
    },
    "jina-reader": {},
    "defuddle": {
        "bins": ["defuddle"],
        "npm": ["defuddle"],
        "npm_bins": {"defuddle": "defuddle"},
        "install_cmds": {
            "npm": "npm install -g defuddle",
        },
    },
    "crawl4ai": {
        "pip": ["crawl4ai"],
        "install_cmds": {
            "pip": "pip install crawl4ai",
            "post_install": "crawl4ai-setup",
        },
    },
    "browser-use": {
        "pip": ["browser-use", "langchain-openai"],
        "install_cmds": {
            "pip": "pip install browser-use langchain-openai",
        },
    },
    "firecrawl": {
        "pip": ["firecrawl-py"],
        "env": ["FIRECRAWL_API_KEY"],
        "install_cmds": {
            "pip": "pip install firecrawl-py",
        },
    },
    "mptext-api": {
        "pip": ["requests"],
        "env": ["MPTEXT_API_KEY"],
        "install_cmds": {
            "pip": "pip install requests",
        },
    },
    "mp-hot": {},
    "mp-search": {},
    "gh-research": {
        "bins": ["gh"],
        "brew_bins": ["gh"],
        "install_cmds": {
            "brew": "brew install gh",
        },
    },
    "gh-write": {},
    "proxy": {
        "pip": ["requests"],
        "install_cmds": {
            "pip": "pip install requests",
        },
    },
    "dev-resource-accelerator": {
        "bins": ["git", "curl"],
    },
    "fengniao-search": {
        "env": ["FN_API_KEY"],
    },
    "qibook-company-profile": {
        "pip": ["requests"],
        "env": ["QIBOOK_ACCESS_KEY", "QIBOOK_BASE_URL"],
        "install_cmds": {
            "pip": "pip install requests",
        },
    },
    "qibook-company-wiki-deepresearch": {
        "pip": ["requests"],
        "env": ["QIBOOK_ACCESS_KEY", "QIBOOK_BASE_URL"],
        "install_cmds": {
            "pip": "pip install requests",
        },
    },
    "claude-real-video": {
        "bins": ["crv"],
        "pip": ["claude-real-video"],
        "pip_bins": {"crv": "claude-real-video[fast]"},
        "install_cmds": {
            "pip": 'pip install "claude-real-video[fast]"',
        },
    },
    "whispercpp": {
        "bins": ["whisper-cli", "ffmpeg", "tesseract"],
        "brew_bins": ["whisper-cli", "ffmpeg", "tesseract"],
        "install_cmds": {
            "brew": "brew install whisper-cpp ffmpeg tesseract tesseract-lang",
        },
    },
    "analyze-viral-commerce-video": {
        "bins": ["ffmpeg"],
        "pip": ["pillow", "openai-whisper"],
        "brew_bins": ["ffmpeg"],
        "install_cmds": {
            "pip": "pip install pillow openai-whisper",
            "brew": "brew install ffmpeg",
        },
    },
    "videodl": {
        "bins": ["videodl"],
        "pip": ["videodl"],
        "pip_bins": {"videodl": "videodl"},
        "install_cmds": {
            "pip": "pip install videodl",
        },
    },
    "dy-fanpai": {
        "bins": ["dy-fanpai", "ffmpeg", "ffprobe"],
        "pip": ["pydantic", "requests"],
        "pip_bins": {"dy-fanpai": "."},
        "pip_install": {"args": ["install", "-e", "."], "cwd": "dy-fanpai"},
        "brew_bins": ["ffmpeg", "ffprobe"],
        "install_cmds": {
            "pip": "cd dy-fanpai && pip install -e .",
            "brew": "brew install ffmpeg",
        },
    },
    "dy-doudian": {
        "bins": ["dy-doudian", "dy-doudian-mcp"],
        "pip": ["mcp", "httpx", "python-dotenv"],
        "pip_bins": {"dy-doudian": ".", "dy-doudian-mcp": "."},
        "pip_install": {"args": ["install", "-e", "."], "cwd": "dy-doudian"},
        "install_cmds": {
            "pip": "cd dy-doudian && pip install -e .",
        },
    },
    "dy-qianchuan": {
        "pip": ["requests", "pyyaml"],
        "install_cmds": {
            "pip": "pip install requests pyyaml",
        },
    },
}

# ============================================================================
# 代理支持 — 网络失败时自动使用 proxy 技能的代理池
# ============================================================================

PROXY_DATA_DIR = os.path.join(DEFAULT_SKILLS_DIR, "proxy", "data")
PROXY_CACHE_FILE = os.path.join(PROXY_DATA_DIR, "valid_proxies.json")
PROXY_TXT_FILE = os.path.join(PROXY_DATA_DIR, "valid_http.txt")


def _load_proxy_list():
    """从 proxy 技能的本地缓存加载代理列表"""
    # 优先读 JSON
    if os.path.exists(PROXY_CACHE_FILE):
        try:
            with open(PROXY_CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            by_proto = data.get("by_protocol", {})
            proxies = []
            for proto in ("http", "socks5"):
                proxies.extend(by_proto.get(proto, {}).get("addresses", []))
            if proxies:
                return proxies
        except Exception:
            pass
    # 回退: 读 txt
    if os.path.exists(PROXY_TXT_FILE):
        try:
            with open(PROXY_TXT_FILE, "r", encoding="utf-8") as f:
                return [line.strip() for line in f if line.strip() and not line.startswith("#")]
        except Exception:
            pass
    return []


def _download_url(url, dest_path, timeout=30, max_proxy_attempts=3):
    """
    下载 URL 到本地文件。先尝试直连，失败后自动走代理。
    返回: True 成功 / False 失败
    """
    import random

    # 1. 先尝试直连
    try:
        print(f"      Trying direct download...")
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            with open(dest_path, "wb") as f:
                f.write(resp.read())
        return True
    except Exception as e:
        print(f"      Direct failed: {type(e).__name__}")

    # 2. 加载代理池
    proxies = _load_proxy_list()
    if not proxies:
        print("      No proxies available in local cache")
        return False

    print(f"      Trying {min(max_proxy_attempts, len(proxies))} proxies from pool...")
    random.shuffle(proxies)

    for proxy_url in proxies[:max_proxy_attempts]:
        try:
            print(f"      Trying proxy: {proxy_url}")
            handler = urllib.request.ProxyHandler({"http": proxy_url, "https": proxy_url})
            opener = urllib.request.build_opener(handler)
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with opener.open(req, timeout=timeout) as resp:
                with open(dest_path, "wb") as f:
                    f.write(resp.read())
            print(f"      OK via proxy: {proxy_url}")
            return True
        except Exception as e:
            print(f"      Proxy failed: {type(e).__name__}")
            continue

    return False


# ============================================================================
# 依赖检查工具函数
# ============================================================================

def _get_pip_scripts_dir():
    """获取 pip Scripts 目录路径（Windows 上安装的 CLI 工具通常在此）"""
    try:
        for py in ["python3", "python", "py"]:
            try:
                result = _safe_subprocess_run(
                    [py, "-c", "import sysconfig; print(sysconfig.get_path('scripts'))"],
                    timeout=5,
                )
                if result.returncode == 0:
                    scripts_dir = result.stdout.strip()
                    if os.path.isdir(scripts_dir):
                        return scripts_dir
            except (FileNotFoundError, OSError):
                continue
    except Exception:
        pass
    return None


def command_exists(cmd):
    """跨平台检测命令是否存在（额外搜索 pip scripts 目录）"""
    try:
        if platform.system() == "Windows":
            result = subprocess.run(
                ["where", cmd],
                capture_output=True,
                shell=True,
            )
            if result.returncode == 0:
                return True
        else:
            result = subprocess.run(
                ["which", cmd],
                capture_output=True,
            )
            if result.returncode == 0:
                return True
        # 回退: 搜索 pip scripts 目录（Windows 用 Scripts，macOS/Linux 用 bin）
        scripts_dir = _get_pip_scripts_dir()
        if scripts_dir:
            for ext in ("", ".exe", ".cmd", ".bat"):
                if os.path.isfile(os.path.join(scripts_dir, cmd + ext)):
                    return True
        return False
    except (FileNotFoundError, OSError):
        return False


def _safe_subprocess_run(cmd, **kwargs):
    """Windows-safe subprocess.run that handles encoding errors"""
    kwargs.setdefault("capture_output", True)
    kwargs.setdefault("text", True)
    if platform.system() == "Windows":
        kwargs.setdefault("encoding", "utf-8")
        kwargs.setdefault("errors", "replace")
    return subprocess.run(cmd, **kwargs)


def get_pip_packages():
    """获取已安装的 pip 包列表"""
    try:
        for py in ["python3", "python", "py"]:
            try:
                result = _safe_subprocess_run(
                    [py, "-m", "pip", "list", "--format=json"],
                    timeout=10,
                )
                if result.returncode == 0:
                    packages = json.loads(result.stdout)
                    return {_canonical_package_name(p["name"]) for p in packages}
            except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
                continue
        # 回退: pip list
        result = _safe_subprocess_run(
            ["pip", "list", "--format=json"],
            timeout=10,
        )
        if result.returncode == 0:
            packages = json.loads(result.stdout)
            return {_canonical_package_name(p["name"]) for p in packages}
    except Exception:
        pass
    return set()


def get_npm_global_packages():
    """获取全局安装的 npm 包列表"""
    try:
        result = _safe_subprocess_run(
            ["npm", "list", "-g", "--json", "--depth=0"],
            shell=True,
            timeout=10,
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            deps = data.get("dependencies", {})
            return {k.lower() for k in deps.keys()}
    except Exception:
        pass
    return set()


def _canonical_package_name(value):
    """将 Python requirement 归一化为 pip list 使用的发行包名。"""
    match = re.match(r"^([A-Za-z0-9][A-Za-z0-9._-]*)", value.strip())
    if not match:
        return None
    return re.sub(r"[-_.]+", "-", match.group(1)).lower()


def _is_local_install_target(value):
    value = value.strip().strip("\"'")
    return (
        value in {".", ".."}
        or value.startswith(("./", "../", "/", "~", "file:", "git+", "http://", "https://"))
    )


def _pip_targets_from_body(body):
    """从 Markdown 命令行中提取发行包，忽略选项、URL 与本地 editable 安装。"""
    targets = []
    option_with_value = {
        "-c", "--constraint", "-f", "--find-links", "-i", "--index-url",
        "--extra-index-url", "--trusted-host", "-r", "--requirement", "-t", "--target",
        "--prefix", "--root", "--src", "--python-version", "--platform",
    }
    for line in body.replace("\\\n", " ").splitlines():
        try:
            tokens = shlex.split(line, comments=True)
        except ValueError:
            continue
        install_at = None
        for index, token in enumerate(tokens[:-1]):
            if token.lower() in {"pip", "pip3"} and tokens[index + 1].lower() == "install":
                install_at = index + 2
                break
        if install_at is None:
            continue

        skip_next = False
        for token in tokens[install_at:]:
            if token in {"&&", "||", ";", "|"}:
                break
            if skip_next:
                skip_next = False
                continue
            if token in {"-e", "--editable"} or token in option_with_value:
                skip_next = True
                continue
            if token.startswith(("--editable=", "-")):
                continue
            if _is_local_install_target(token):
                continue
            name = _canonical_package_name(token)
            if name:
                targets.append(name)
    return targets


def _dedupe(values):
    return list(dict.fromkeys(values))


def parse_skill_md_deps(skill_path):
    """从 SKILL.md 的 frontmatter 和内容中提取依赖信息。"""
    skill_md = os.path.join(skill_path, "SKILL.md")
    if not os.path.exists(skill_md):
        return {}

    deps = {"bins": [], "pip": [], "npm": [], "env": []}

    try:
        with open(skill_md, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception:
        return deps

    # 解析 YAML frontmatter
    fm_match = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
    if fm_match:
        fm_text = fm_match.group(1)

        # 提取 openclaw.requires.bins
        bins_match = re.search(r'"bins"\s*:\s*\[([^\]]+)\]', fm_text)
        if bins_match:
            bins_str = bins_match.group(1)
            deps["bins"].extend(
                b.strip().strip('"').strip("'")
                for b in bins_str.split(",")
                if b.strip()
            )

        # 提取 requirements.packages
        pkg_match = re.search(r"packages\s*:\s*\n((?:\s+- name:\s+\S+\n?)+)", fm_text)
        if pkg_match:
            for line in pkg_match.group(1).strip().split("\n"):
                name_m = re.search(r"name:\s+(\S+)", line)
                if name_m:
                    name = _canonical_package_name(name_m.group(1))
                    if name:
                        deps["pip"].append(name)

        # 提取 requirements.environment_variables
        env_match = re.search(
            r"environment_variables\s*:\s*\n((?:\s+- name:\s+\S+\n(?:\s+.*\n)*?)+)",
            fm_text,
        )
        if env_match:
            for line in env_match.group(1).strip().split("\n"):
                name_m = re.search(r"name:\s+(\S+)", line)
                if name_m:
                    deps["env"].append(name_m.group(1))

    # 扫描 markdown body 中的安装命令
    body = content[fm_match.end():] if fm_match else content

    deps["pip"].extend(_pip_targets_from_body(body))

    # npm install -g xxx (also matches "npm i -g xxx")
    npm_matches = re.findall(r"npm\s+(?:install|i)\s+-g\s+([^\s\\`]+)", body)
    for pkg in npm_matches:
        deps["npm"].append(pkg.strip("\"'").lower())

    return {kind: _dedupe(values) for kind, values in deps.items()}


def check_skill_deps(skill_name, skill_path, pip_pkgs, npm_pkgs):
    """
    检查单个技能的依赖。
    返回: (all_ok: bool, missing: dict)
    missing 的格式: {"bins": [...], "pip": [...], "npm": [...], "env": [...]}
    """
    # 合并注册表 + SKILL.md 声明
    registry_deps = SKILL_DEPS.get(skill_name, {})
    md_deps = parse_skill_md_deps(skill_path)

    # 注册表对已声明的类别具有权威性；仅在类别未登记时采用 SKILL.md 推断值。
    def declared_or_inferred(kind):
        if kind in registry_deps:
            return list(registry_deps[kind])
        return list(md_deps.get(kind, []))

    all_bins = declared_or_inferred("bins")
    all_pip = declared_or_inferred("pip")
    all_npm = declared_or_inferred("npm")
    all_env = declared_or_inferred("env")

    missing = {"bins": [], "pip": [], "npm": [], "env": []}

    for b in all_bins:
        if not command_exists(b):
            missing["bins"].append(b)

    pip_bin_map = registry_deps.get("pip_bins", {})
    npm_bin_map = registry_deps.get("npm_bins", {})

    for p in all_pip:
        # 如果该 pip 包仅用于提供某个已存在的 CLI 二进制，则视为已满足
        provided_bins = [b for b, pkg in pip_bin_map.items() if pkg == p]
        if provided_bins and all(command_exists(b) for b in provided_bins):
            continue
        p_normalized = _canonical_package_name(p)
        if p_normalized not in pip_pkgs:
            missing["pip"].append(p)

    for n in all_npm:
        # 如果该 npm 包仅用于提供某个已存在的 CLI 二进制，则视为已满足
        provided_bins = [b for b, pkg in npm_bin_map.items() if pkg == n]
        if provided_bins and all(command_exists(b) for b in provided_bins):
            continue
        if n.lower() not in npm_pkgs:
            missing["npm"].append(n)

    # 加载 ~/.codex/.env 中的键值作为备用环境检测
    codex_env = {}
    codex_env_path = os.path.expanduser("~/.codex/.env")
    if os.path.exists(codex_env_path):
        try:
            with open(codex_env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if "=" in line and not line.startswith("#"):
                        k, v = line.split("=", 1)
                        codex_env[k.strip()] = v.strip().strip('"\'')
        except Exception:
            pass

    # 检查技能目录内是否有本地 key 文件（如 mptext-api/scripts/.mpkey）
    local_key_files = {
        "MPTEXT_API_KEY": [os.path.join(skill_path, "scripts", ".mpkey"), os.path.join(skill_path, ".mpkey")],
    }

    for e in all_env:
        # 检查环境变量、codex_env 或本地 key 文件
        if os.environ.get(e) or codex_env.get(e):
            continue
        if e in local_key_files and any(os.path.exists(kf) for kf in local_key_files[e]):
            continue
        missing["env"].append(e)

    all_ok = all(len(v) == 0 for v in missing.values())
    return all_ok, missing


def print_deps_report(skill_name, missing, install_cmds):
    """打印单个技能的依赖缺失报告"""
    registry = SKILL_DEPS.get(skill_name, {})
    missing_bins = set(missing["bins"])
    pip_bin_missing = missing_bins.intersection(registry.get("pip_bins", {}))
    npm_bin_missing = missing_bins.intersection(registry.get("npm_bins", {}))
    brew_bin_missing = missing_bins.intersection(registry.get("brew_bins", []))
    go_bin_missing = missing_bins.intersection(registry.get("go_bins", []))
    download_bin_missing = missing_bins.intersection(registry.get("download_bins", []))
    if missing["bins"]:
        print(f"    Missing binaries: {', '.join(missing['bins'])}")
    if missing["pip"]:
        print(f"    Missing pip packages: {', '.join(missing['pip'])}")
    if missing["npm"]:
        print(f"    Missing npm packages: {', '.join(missing['npm'])}")
    if missing["env"]:
        print(f"    Missing env vars: {', '.join(missing['env'])}")
    # 推荐安装命令
    if install_cmds:
        is_windows = platform.system() == "Windows"
        for method, cmd in install_cmds.items():
            if method == "pip" and (missing["pip"] or pip_bin_missing):
                print(f"    -> Try: {cmd}")
            elif method == "npm" and (missing["npm"] or npm_bin_missing):
                print(f"    -> Try: {cmd}")
            elif method == "brew" and brew_bin_missing and not is_windows:
                print(f"    -> Try: {cmd}")
            elif method == "go" and go_bin_missing:
                print(f"    -> Try: {cmd}")
            elif method in ("windows_download", "macos_download") and download_bin_missing:
                download_key = "windows_download" if is_windows else "macos_download"
                if method == download_key:
                    print(f"    -> Auto-install: run with --install")


def _find_pip_cmd():
    """找到可用的 pip 命令"""
    for py in ["python3", "python", "py"]:
        try:
            result = _safe_subprocess_run([py, "-m", "pip", "--version"], timeout=5)
            if result.returncode == 0:
                return [py, "-m", "pip"]
        except (FileNotFoundError, OSError):
            continue
    return ["pip"]


def _install_lux_binary(dry_run=False):
    """从 GitHub Releases 下载 lux 二进制（跨平台，自动代理回退）"""
    import tempfile
    import zipfile

    scripts_dir = _get_pip_scripts_dir()
    if not scripts_dir:
        print("    WARNING: Cannot find pip scripts directory")
        return False

    is_windows = platform.system() == "Windows"
    ext = ".exe" if is_windows else ""
    target = os.path.join(scripts_dir, f"lux{ext}")
    if os.path.isfile(target):
        print(f"    lux already at {target}")
        return True

    # 检测架构和 OS
    machine = platform.machine().lower()
    if machine in ("amd64", "x86_64", "x64"):
        arch = "x86_64"
    elif machine in ("arm64", "aarch64"):
        arch = "arm64"
    else:
        arch = "i386"

    version = "v0.24.1"
    ver = version.lstrip("v")

    if is_windows:
        os_name = "Windows"
        zip_name = f"lux_{ver}_Windows_{arch}.zip"
        bin_name = "lux.exe"
    elif platform.system() == "Darwin":
        os_name = "macOS"
        zip_name = f"lux_{ver}_macOS_{arch}.tar.gz"
        bin_name = "lux"
    else:
        os_name = "Linux"
        zip_name = f"lux_{ver}_Linux_{arch}.tar.gz"
        bin_name = "lux"

    # 尝试的下载源
    github_base = f"https://github.com/iawia002/lux/releases/download/{version}"
    urls = [
        f"{github_base}/{zip_name}",
        f"https://ghfast.top/{github_base}/{zip_name}",
        f"https://mirror.ghproxy.com/{github_base}/{zip_name}",
    ]

    print(f"    Downloading lux {version} ({os_name}/{arch})...")
    if dry_run:
        print(f"    [DryRun] Would download lux binary")
        return True

    for url in urls:
        print(f"    Trying: {url[:80]}...")
        tmp_file = os.path.join(tempfile.gettempdir(), f"lux_download{'.zip' if is_windows else '.tar.gz'}")
        if _download_url(url, tmp_file, timeout=30):
            try:
                if is_windows:
                    with zipfile.ZipFile(tmp_file, "r") as zf:
                        for member in zf.namelist():
                            if member.endswith("lux.exe"):
                                with zf.open(member) as src, open(target, "wb") as dst:
                                    dst.write(src.read())
                                break
                else:
                    # macOS/Linux: tar.gz
                    import tarfile
                    with tarfile.open(tmp_file, "r:gz") as tf:
                        for member in tf.getmembers():
                            if member.isfile() and (member.name.endswith(bin_name) or member.name.endswith("lux")):
                                extracted = tf.extractfile(member)
                                if extracted:
                                    with open(target, "wb") as dst:
                                        dst.write(extracted.read())
                                    os.chmod(target, 0o755)
                                    break

                os.remove(tmp_file)
                if os.path.isfile(target):
                    print(f"    OK: lux installed to {target}")
                    return True
            except Exception as e:
                print(f"    Extract failed: {e}")
        if os.path.exists(tmp_file):
            os.remove(tmp_file)

    # 所有源都失败
    print("    FAILED: Could not download lux from any source")
    if is_windows:
        print("    Manual install options:")
        print("      1. scoop install lux")
        print("      2. choco install lux")
        print("      3. go install github.com/iawia002/lux@latest")
    else:
        print("    Manual install options:")
        print("      1. brew install lux")
        print("      2. go install github.com/iawia002/lux@latest")
    print(f"      Or download from https://github.com/iawia002/lux/releases")
    return False


def _post_install_ffmpeg(dry_run=False):
    """将 imageio-ffmpeg 捆绑的 ffmpeg 复制到 pip Scripts 目录"""
    scripts_dir = _get_pip_scripts_dir()
    if not scripts_dir:
        print("    WARNING: Cannot find pip scripts directory")
        return False

    target = os.path.join(scripts_dir, "ffmpeg.exe" if platform.system() == "Windows" else "ffmpeg")
    if os.path.isfile(target):
        print(f"    ffmpeg already at {target}")
        return True

    # 在 site-packages 中查找 imageio-ffmpeg 的 ffmpeg 二进制
    ffmpeg_bin = None
    try:
        for py in ["python3", "python", "py"]:
            try:
                result = _safe_subprocess_run(
                    [py, "-c", "import imageio_ffmpeg; import os; print(os.path.dirname(imageio_ffmpeg.__file__))"],
                    timeout=5,
                )
                if result.returncode == 0:
                    pkg_dir = result.stdout.strip()
                    binaries_dir = os.path.join(pkg_dir, "binaries")
                    if os.path.isdir(binaries_dir):
                        for f in os.listdir(binaries_dir):
                            if f.startswith("ffmpeg") and f.endswith((".exe", "")):
                                ffmpeg_bin = os.path.join(binaries_dir, f)
                                break
                    break
            except (FileNotFoundError, OSError):
                continue
    except Exception:
        pass

    if not ffmpeg_bin or not os.path.isfile(ffmpeg_bin):
        print("    WARNING: Cannot find ffmpeg binary in imageio-ffmpeg package")
        return False

    print(f"    Copying ffmpeg -> {target}")
    if not dry_run:
        shutil.copy2(ffmpeg_bin, target)
    return True


def _install_ffmpeg_windows(dry_run=False):
    """Windows 下安装 ffmpeg: 先尝试 winget, 若失败则尝试从 imageio-ffmpeg 复制"""
    print("    Trying to install ffmpeg via winget...")
    if not dry_run:
        result = _safe_subprocess_run("winget install Gyan.FFmpeg --accept-package-agreements --accept-source-agreements", shell=True, timeout=300)
        if result.returncode == 0:
            print("    OK: winget install Gyan.FFmpeg succeeded")
            return True
        else:
            print("    winget install failed, fallback to imageio-ffmpeg...")
            return _post_install_ffmpeg(dry_run=dry_run)
    else:
        print("    [DryRun] Would run: winget install Gyan.FFmpeg or fallback to imageio-ffmpeg")
        return True


def install_missing_deps(skill_name, missing, dry_run=False):
    """
    尝试自动安装缺失的 pip/npm 依赖。
    返回: (installed_pip: list, installed_npm: list, failed: list)
    """
    registry = SKILL_DEPS.get(skill_name, {})
    install_cmds = registry.get("install_cmds", {})
    installed_pip = []
    installed_npm = []
    failed = []
    handled_bins = set()

    pip_bin_map = registry.get("pip_bins", {})
    npm_bin_map = registry.get("npm_bins", {})
    pip_bin_targets = [pip_bin_map[b] for b in missing["bins"] if b in pip_bin_map]
    npm_bin_targets = [npm_bin_map[b] for b in missing["bins"] if b in npm_bin_map]
    pip_targets = _dedupe(list(missing["pip"]) + pip_bin_targets)
    npm_targets = _dedupe(list(missing["npm"]) + npm_bin_targets)

    # --- pip 安装 ---
    if pip_targets and "pip" in install_cmds:
        cmd_str = install_cmds["pip"]
        print(f"    Installing pip packages: {cmd_str}")
        if dry_run:
            print(f"    [DryRun] Would run: {cmd_str}")
            installed_pip.extend(pip_targets)
            handled_bins.update(b for b in missing["bins"] if b in pip_bin_map)
        else:
            pip_cmd = _find_pip_cmd()
            install_spec = registry.get("pip_install")
            if install_spec:
                full_cmd = pip_cmd + list(install_spec["args"])
                install_cwd = os.path.join(DEFAULT_SKILLS_DIR, install_spec["cwd"])
            else:
                full_cmd = pip_cmd + [
                    "install", "-i", "https://pypi.tuna.tsinghua.edu.cn/simple", *pip_targets,
                ]
                install_cwd = None
            print(f"    Running: {shlex.join(full_cmd)}")
            result = _safe_subprocess_run(full_cmd, cwd=install_cwd, timeout=120)
            if result.returncode == 0:
                installed_pip.extend(pip_targets)
                handled_bins.update(b for b in missing["bins"] if b in pip_bin_map)
                print(f"    OK: pip packages installed")
            else:
                failed.extend(missing["pip"])
                print(f"    FAILED: pip install failed")
                if result.stdout:
                    for line in result.stdout.strip().split("\n")[-3:]:
                        print(f"      {line}")
                if result.stderr:
                    for line in result.stderr.strip().split("\n")[-3:]:
                        print(f"      {line}")

    # --- pip post_install (如 playwright install, ffmpeg copy) ---
    if installed_pip and "post_install" in install_cmds:
        post_cmd = install_cmds["post_install"]
        # 支持命名函数（以 _ 开头）
        if post_cmd.startswith("_"):
            func_name = post_cmd
            print(f"    Running post-install: {func_name}()")
            if not dry_run:
                # 查找并调用同名函数
                import importlib
                mod = importlib.import_module(__name__)
                func = getattr(mod, func_name, None)
                if func:
                    func(dry_run=dry_run)
                else:
                    print(f"    WARNING: Function {func_name} not found")
        else:
            print(f"    Running post-install: {post_cmd}")
            if not dry_run:
                result = _safe_subprocess_run(shlex.split(post_cmd), timeout=120)
                if result.returncode != 0:
                    print(f"    WARNING: post-install command failed (non-fatal)")

    # --- npm 安装 ---
    if npm_targets and "npm" in install_cmds:
        cmd_str = install_cmds["npm"]
        print(f"    Installing npm packages: {cmd_str}")
        if dry_run:
            print(f"    [DryRun] Would run: {cmd_str}")
            installed_npm.extend(npm_targets)
            handled_bins.update(b for b in missing["bins"] if b in npm_bin_map)
        else:
            full_cmd = [
                "npm", "install", "-g", "--registry=https://registry.npmmirror.com", *npm_targets,
            ]
            print(f"    Running: {shlex.join(full_cmd)}")
            result = _safe_subprocess_run(full_cmd, timeout=120)
            if result.returncode == 0:
                installed_npm.extend(npm_targets)
                handled_bins.update(b for b in missing["bins"] if b in npm_bin_map)
                print(f"    OK: npm packages installed")
            else:
                failed.extend(missing["npm"])
                print(f"    FAILED: npm install failed")
                if result.stderr:
                    for line in result.stderr.strip().split("\n")[-3:]:
                        print(f"      {line}")

    # --- 无法自动安装的依赖 ---
    if missing["bins"]:
        for b in missing["bins"]:
            if b in handled_bins:
                continue
            # 按优先级尝试: brew (macOS) > go > 平台下载 > 失败
            can_auto = False
            is_windows = platform.system() == "Windows"

            # 优先尝试 brew (macOS)
            if not is_windows and b in registry.get("brew_bins", []) and "brew" in install_cmds:
                cmd_str = install_cmds["brew"]
                print(f"    Installing via brew: {cmd_str}")
                if not dry_run:
                    result = _safe_subprocess_run(shlex.split(cmd_str), timeout=120)
                    if result.returncode == 0:
                        can_auto = True
                        handled_bins.update(set(missing["bins"]).intersection(registry["brew_bins"]))
                        print(f"    OK: brew install succeeded")
                    else:
                        print(f"    brew install failed, trying next method...")
                else:
                    print(f"    [DryRun] Would run: {cmd_str}")
                    can_auto = True
                    handled_bins.update(set(missing["bins"]).intersection(registry["brew_bins"]))

            # 尝试 go install
            if not can_auto and b in registry.get("go_bins", []) and "go" in install_cmds:
                cmd_str = install_cmds["go"]
                print(f"    Installing via go: {cmd_str}")
                if not dry_run:
                    result = _safe_subprocess_run(shlex.split(cmd_str), timeout=120)
                    if result.returncode == 0:
                        can_auto = True
                        print(f"    OK: go install succeeded")
                    else:
                        print(f"    go install failed, trying next method...")
                else:
                    print(f"    [DryRun] Would run: {cmd_str}")
                    can_auto = True

            # 尝试平台下载 (windows_download / macos_download)
            if not can_auto:
                download_key = "windows_download" if is_windows else "macos_download"
                if b in registry.get("download_bins", []) and download_key in install_cmds:
                    func_name = install_cmds[download_key]
                    if func_name.startswith("_"):
                        print(f"    Running: {func_name}()")
                        if not dry_run:
                            import importlib
                            mod = importlib.import_module(__name__)
                            func = getattr(mod, func_name, None)
                            if func:
                                can_auto = func(dry_run=dry_run)
                            else:
                                print(f"    WARNING: Function {func_name} not found")
                        else:
                            print(f"    [DryRun] Would download binary")
                            can_auto = True

            if not can_auto:
                failed.append(f"binary: {b}")

    if missing["env"]:
        for e in missing["env"]:
            failed.append(f"env var: {e}")

    return installed_pip, installed_npm, failed


# ============================================================================
# AI 工具检测与配置
# ============================================================================

# 支持自动配置的 AI 工具目标列表
AI_TARGETS = [
    {
        "name": "Claude Code / Claude Agent",
        "detect_bins": ["claude"],
        "detect_apps": ["/Applications/Claude.app", os.path.join(HOME_DIR, "Applications", "Claude.app")],
        "detect_paths": [os.path.join(HOME_DIR, ".claude"), os.path.join(HOME_DIR, ".claude.json.backup")],
        "skills_dir": os.path.join(HOME_DIR, ".claude", "skills"),
        "type": "symlink_dir",
    },
    {
        "name": "Google Gemini / Antigravity Agent",
        "detect_bins": ["gemini", "antigravity"],
        "detect_apps": ["/Applications/Google Gemini.app", "/Applications/Antigravity.app"],
        "detect_paths": [os.path.join(HOME_DIR, ".gemini"), os.path.join(HOME_DIR, ".antigravity-ide")],
        "skills_config_json": os.path.join(HOME_DIR, ".gemini", "config", "skills.json"),
        "skills_dir": os.path.join(HOME_DIR, ".gemini", "config", "skills"),
        "type": "gemini_config",
    },
    {
        "name": "OpenAI Codex Agent",
        "detect_bins": ["codex"],
        "detect_apps": ["/Applications/ChatGPT.app", "/Applications/Codex.app", os.path.join(HOME_DIR, "Applications", "ChatGPT.app")],
        "detect_paths": [os.path.join(HOME_DIR, ".codex")],
        "skills_dir": os.path.join(HOME_DIR, ".codex", "skills"),
        "type": "symlink_dir",
    },
    {
        "name": "WorkBuddy AI",
        "detect_bins": ["workbuddy"],
        "detect_apps": ["/Applications/WorkBuddy.app", "/Applications/Workbuddy.app", os.path.join(HOME_DIR, "Applications", "WorkBuddy.app")],
        "detect_paths": [os.path.join(HOME_DIR, ".workbuddy")],
        "skills_dir": os.path.join(HOME_DIR, ".workbuddy", "skills"),
        "type": "symlink_dir",
    },
    {
        "name": "Trae CN / Trae IDE",
        "detect_bins": ["trae"],
        "detect_apps": [
            "/Applications/Trae.app",
            "/Applications/Trae CN.app",
            os.path.join(HOME_DIR, "Applications", "Trae.app"),
            os.path.join(HOME_DIR, "Applications", "Trae CN.app"),
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\Trae"),
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\Trae CN"),
        ],
        "skills_dir": os.path.join(HOME_DIR, ".trae-cn", "skills"),
        "type": "symlink_dir",
    },
    {
        "name": "OpenCode Agent",
        "detect_bins": ["opencode"],
        "detect_paths": [os.path.join(HOME_DIR, ".opencode"), os.path.join(HOME_DIR, "opencode")],
        "skills_dir": os.path.join(HOME_DIR, ".opencode", "skills"),
        "type": "symlink_dir",
    },
    {
        "name": "Cursor IDE",
        "detect_bins": ["cursor"],
        "detect_apps": [
            "/Applications/Cursor.app",
            os.path.join(HOME_DIR, "Applications", "Cursor.app"),
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\cursor"),
        ],
        "skills_dir": os.path.join(HOME_DIR, ".cursor", "skills"),
        "type": "symlink_dir",
    },
    {
        "name": "Windsurf IDE",
        "detect_bins": ["windsurf"],
        "detect_apps": [
            "/Applications/Windsurf.app",
            os.path.join(HOME_DIR, "Applications", "Windsurf.app"),
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\Windsurf"),
        ],
        "skills_dir": os.path.join(HOME_DIR, ".codeium", "windsurf", "skills"),
        "type": "symlink_dir",
    },
    {
        "name": "OpenClaw Agent",
        "detect_bins": ["openclaw"],
        "detect_paths": [os.path.join(HOME_DIR, ".openclaw")],
        "skills_dir": os.path.join(HOME_DIR, ".openclaw", "skills"),
        "type": "symlink_dir",
    },
    {
        "name": "Cline / Roo Code",
        "detect_bins": ["cline", "roocode"],
        "detect_paths": [os.path.join(HOME_DIR, ".cline")],
        "skills_dir": os.path.join(HOME_DIR, ".cline", "skills"),
        "type": "symlink_dir",
    },
    {
        "name": "OpenHands Agent",
        "detect_bins": ["openhands"],
        "detect_paths": [os.path.join(HOME_DIR, ".openhands")],
        "skills_dir": os.path.join(HOME_DIR, ".openhands", "skills"),
        "type": "symlink_dir",
    },
]

def discover_valid_skills(skills_root):
    """扫描技能根目录下包含 SKILL.md 的有效技能目录"""
    skills = []
    if not os.path.exists(skills_root):
        return skills
        
    for entry in sorted(os.listdir(skills_root)):
        if entry.startswith(".") or entry in ["scripts", "data", "node_modules"]:
            continue
        skill_path = os.path.join(skills_root, entry)
        if os.path.isdir(skill_path) and os.path.exists(os.path.join(skill_path, "SKILL.md")):
            skills.append((entry, skill_path))
    return skills

def is_target_installed(target):
    """检查某个 AI 工具是否存在于本机（优先检测 CLI 二进制或应用安装包）"""
    # 1. 检测 CLI 二进制命令
    for cmd in target.get("detect_bins", []):
        if command_exists(cmd):
            return True

    # 2. 检测 GUI 应用安装路径（.app / Programs 目录）
    for app_path in target.get("detect_apps", []):
        if app_path and os.path.exists(app_path):
            return True

    # 3. 检测主配置/运行时目录（仅对非 IDE 类纯 CLI/Agent 工具生效）
    for p in target.get("detect_paths", []):
        if p and os.path.exists(p):
            return True
    return False

def _create_link(source, link_name):
    """跨平台创建目录链接：Windows 用 junction（无需管理员），其他平台用 symlink"""
    if platform.system() == "Windows":
        # Windows: 优先使用 junction（无需特权），失败则回退到 symlink
        ret = subprocess.run(
            ["cmd", "/c", "mklink", "/J", link_name, source],
            capture_output=True, text=True
        )
        if ret.returncode == 0:
            return True
        # junction 失败，尝试 symlink（需要管理员或开发者模式）
        os.symlink(source, link_name)
        return True
    else:
        os.symlink(source, link_name)
        return True

def _readlink_compat(link_name):
    """跨平台读取链接目标路径（支持 junction 和 symlink）"""
    if platform.system() == "Windows":
        # Python 3.12+ 原生支持 readlink junction
        try:
            return os.readlink(link_name)
        except (OSError, NotImplementedError):
            pass
        # 回退：用 subst 命令解析 junction
        try:
            out = _safe_subprocess_run(["cmd", "/c", "dir", link_name])
            for line in out.stdout.splitlines():
                if "<JUNCTION>" in line or "<SYMLINK>" in line:
                    # 格式: <JUNCTION>     link_name [target]
                    parts = line.split("[")
                    if len(parts) > 1:
                        return parts[-1].rstrip("]")
        except Exception:
            pass
        return None
    else:
        return os.readlink(link_name)


def _is_link(path):
    """跨平台检测路径是否为 symlink 或 junction"""
    if os.path.islink(path):
        return True
    # Windows Python < 3.12 不识别 junction 为 symlink，用 junction 属性检测
    if platform.system() == "Windows" and os.path.exists(path):
        try:
            out = _safe_subprocess_run(["cmd", "/c", "dir", os.path.dirname(path)])
            basename = os.path.basename(path)
            for line in out.stdout.splitlines():
                if ("<JUNCTION>" in line or "<SYMLINK>" in line) and basename in line:
                    return True
        except Exception:
            pass
    return False

def configure_symlink_dir(target_name, target_skills_dir, valid_skills, dry_run=False, skip_deps=False, pip_pkgs=None, npm_pkgs=None):
    """创建软链接共享技能到 AI 工具的技能目录（含依赖检查）"""
    print(f"\n[TARGET] 配置 {target_name} -> 技能目录: {target_skills_dir}")
    
    if not dry_run:
        os.makedirs(target_skills_dir, exist_ok=True)

    # 依赖检查（使用外部传入的缓存，避免重复获取）
    if pip_pkgs is None:
        pip_pkgs = set()
    if npm_pkgs is None:
        npm_pkgs = set()
    if not skip_deps and not pip_pkgs and not npm_pkgs:
        print("  [*] Checking dependencies...")
        pip_pkgs = get_pip_packages()
        npm_pkgs = get_npm_global_packages()

    linked_count = 0
    skipped_deps = 0
    for skill_name, skill_path in valid_skills:
        link_target = os.path.join(target_skills_dir, skill_name)
        
        # 依赖检查
        if not skip_deps:
            all_ok, missing = check_skill_deps(skill_name, skill_path, pip_pkgs, npm_pkgs)
            if not all_ok:
                skipped_deps += 1
                print(f"  [SKIP] {skill_name} (deps missing)")
                print_deps_report(skill_name, missing, SKILL_DEPS.get(skill_name, {}).get("install_cmds", {}))
                continue

        if _is_link(link_target):
            existing_src = _readlink_compat(link_target)
            if existing_src and os.path.normpath(existing_src) == os.path.normpath(skill_path):
                print(f"  [OK] {skill_name} (linked)")
                linked_count += 1
                continue
            else:
                print(f"  [UPDATE] {skill_name} (updating link)")
                if not dry_run:
                    try:
                        os.unlink(link_target)
                    except OSError:
                        subprocess.run(
                            ["cmd", "/c", "rmdir", link_target],
                            capture_output=True
                        )
        elif os.path.exists(link_target):
            print(f"  [WARN] {skill_name} (dir exists, skip)")
            continue
            
        if dry_run:
            print(f"  [DryRun] {skill_name} -> {link_target}")
        else:
            try:
                _create_link(skill_path, link_target)
                print(f"  [DONE] {skill_name}")
                linked_count += 1
            except Exception as e:
                print(f"  [FAIL] {skill_name}: {e}")
                
    if not skip_deps and skipped_deps > 0:
        print(f"  [INFO] {skipped_deps} skill(s) skipped due to missing dependencies")
    return linked_count

def configure_gemini(target_name, skills_json_path, target_skills_dir, skills_root, valid_skills, dry_run=False, skip_deps=False, pip_pkgs=None, npm_pkgs=None):
    """配置 Gemini / Antigravity 专用的 skills.json 自动识别"""
    print(f"\n[TARGET] 配置 {target_name} -> {skills_json_path}")
    
    # 1. 链接技能到 skills 目录
    configure_symlink_dir(target_name, target_skills_dir, valid_skills, dry_run=dry_run, skip_deps=skip_deps, pip_pkgs=pip_pkgs, npm_pkgs=npm_pkgs)
    
    # 2. 写入或更新 skills.json
    skills_json_dir = os.path.dirname(skills_json_path)
    if not dry_run:
        os.makedirs(skills_json_dir, exist_ok=True)
        
    current_config = {"entries": []}
    if os.path.exists(skills_json_path):
        try:
            with open(skills_json_path, "r", encoding="utf-8") as f:
                current_config = json.load(f)
        except Exception:
            pass
            
    entries = current_config.get("entries", [])
    already_has_root = any(entry.get("path") == skills_root for entry in entries if isinstance(entry, dict))
    
    if not already_has_root:
        entries.append({"path": skills_root})
        current_config["entries"] = entries
        if dry_run:
            print(f"  [DryRun] Add {skills_root} to {skills_json_path}")
        else:
            try:
                with open(skills_json_path, "w", encoding="utf-8") as f:
                    json.dump(current_config, f, indent=2, ensure_ascii=False)
                print(f"  [DONE] Updated {skills_json_path}")
            except Exception as e:
                print(f"  [FAIL] Write {skills_json_path} failed: {e}")
    else:
        print(f"  [OK] {skills_json_path} already indexed")

def main():
    parser = argparse.ArgumentParser(description="Auto-detect AI tools and configure skill sharing with dependency checking")
    parser.add_argument("--dry-run", action="store_true", help="Preview actions without modifying system")
    parser.add_argument("--skip-deps", action="store_true", help="Skip dependency checking")
    parser.add_argument("--install", action="store_true", help="Auto-install missing pip/npm dependencies before configuring")
    parser.add_argument("--skills-dir", default=DEFAULT_SKILLS_DIR, help="Skills repo root path")
    
    args = parser.parse_args()
    skills_root = os.path.abspath(args.skills_dir)
    
    print("=" * 60)
    print("Momo Skills — AI Assistant Skill Auto-Configuration")
    print(f"  Skills dir: {skills_root}")
    if args.dry_run:
        print("  [Dry-Run] Preview mode — no changes will be made")
    if args.skip_deps:
        print("  [Skip-Deps] Dependency checking disabled")
    if args.install:
        print("  [Install] Auto-install missing dependencies")
    print("=" * 60)
    
    valid_skills = discover_valid_skills(skills_root)
    print(f"\nScanned {len(valid_skills)} valid skills:")
    for sname, _ in valid_skills:
        print(f"  - {sname}")
        
    if not valid_skills:
        print("ERROR: No valid SKILL.md skills found.", file=sys.stderr)
        sys.exit(1)

    # 预检依赖概览 + 自动安装
    if not args.skip_deps:
        print(f"\n{'=' * 60}")
        print("Dependency Pre-Check")
        print("=" * 60)
        pip_pkgs = get_pip_packages()
        npm_pkgs = get_npm_global_packages()
        ok_count = 0
        warn_count = 0
        install_summary = {"pip_ok": [], "npm_ok": [], "failed": []}

        for sname, spath in valid_skills:
            all_ok, missing = check_skill_deps(sname, spath, pip_pkgs, npm_pkgs)
            if all_ok:
                ok_count += 1
            else:
                warn_count += 1
                print(f"\n  {sname}:")
                print_deps_report(sname, missing, SKILL_DEPS.get(sname, {}).get("install_cmds", {}))

                # 自动安装模式
                if args.install and (missing["pip"] or missing["npm"] or missing["bins"]):
                    pip_ok, npm_ok, failed = install_missing_deps(
                        sname, missing, dry_run=args.dry_run
                    )
                    install_summary["pip_ok"].extend(pip_ok)
                    install_summary["npm_ok"].extend(npm_ok)
                    install_summary["failed"].extend(failed)

        # 安装后汇总
        if args.install:
            installed_total = len(install_summary["pip_ok"]) + len(install_summary["npm_ok"])
            failed_total = len(install_summary["failed"])
            print(f"\n  {'=' * 50}")
            print(f"  Install Summary: {installed_total} packages installed, {failed_total} items need manual action")
            if install_summary["failed"]:
                print("  Manual steps needed:")
                for item in install_summary["failed"]:
                    print(f"    - {item}")
            print(f"  {'=' * 50}")

            # 重新检测 pip/npm 包（安装后刷新）
            pip_pkgs = get_pip_packages()
            npm_pkgs = get_npm_global_packages()

            # 重新统计
            ok_count = 0
            warn_count = 0
            for sname, spath in valid_skills:
                all_ok, _ = check_skill_deps(sname, spath, pip_pkgs, npm_pkgs)
                if all_ok:
                    ok_count += 1
                else:
                    warn_count += 1

        print(f"\n  Summary: {ok_count} ready, {warn_count} have missing dependencies")
        if warn_count > 0:
            if not args.install:
                print("  Skills with missing deps will be SKIPPED during configuration.")
                print("  Use --install to auto-install pip/npm dependencies.")
            else:
                print("  Remaining skills have unresolvable deps (env vars / binaries).")
                print("  Use --skip-deps to force-configure all skills regardless.")
        print("=" * 60)
        
    detected_count = 0
    configured_count = 0
    
    # 获取一次 pip/npm 包列表，传递给所有配置目标
    pip_pkgs = get_pip_packages() if not args.skip_deps else set()
    npm_pkgs = get_npm_global_packages() if not args.skip_deps else set()

    print("\nScanning installed AI assistants...")
    for target in AI_TARGETS:
        tname = target["name"]
        installed = is_target_installed(target)
        
        if installed:
            detected_count += 1
            print(f"\n  [Detected] {tname}")
            
            ttype = target["type"]
            if ttype == "gemini_config":
                configure_gemini(
                    tname,
                    target["skills_config_json"],
                    target["skills_dir"],
                    skills_root,
                    valid_skills,
                    dry_run=args.dry_run,
                    skip_deps=args.skip_deps,
                    pip_pkgs=pip_pkgs,
                    npm_pkgs=npm_pkgs,
                )
                configured_count += 1
            elif ttype == "symlink_dir":
                configure_symlink_dir(
                    tname,
                    target["skills_dir"],
                    valid_skills,
                    dry_run=args.dry_run,
                    skip_deps=args.skip_deps,
                    pip_pkgs=pip_pkgs,
                    npm_pkgs=npm_pkgs,
                )
                configured_count += 1
        else:
            print(f"  [Not found] {tname}")
            
    print("\n" + "=" * 60)
    print(f"Done! Detected {detected_count} AI tool(s), configured {configured_count}.")
    print("=" * 60)

if __name__ == "__main__":
    main()
