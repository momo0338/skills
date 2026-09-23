#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
gh_research.py: 深度提取 GitHub 仓库实时多维度数据（Stars/Forks/Release/多语言/README解析）
"""

import sys
import os
import re
import json
import subprocess
import shutil
import urllib.parse
import argparse
import base64
from concurrent.futures import ThreadPoolExecutor

# gh CLI 的兜底路径。取值优先级见 run_gh_api()：先 shutil.which("gh") 走 PATH，
# 再退回这里。用 GH_CLI 环境变量可覆盖，避免换平台（Linux/CI）时该常量失效。
GH_CLI_PATH = os.environ.get("GH_CLI") or "/opt/homebrew/bin/gh"

def parse_repo_identifier(raw: str) -> str:
    """提取标准化 owner/repo"""
    raw = raw.strip()
    m = re.search(r"github\.com/([a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+)", raw)
    if m:
        repo = m.group(1).rstrip("/")
        if repo.endswith(".git"):
            repo = repo[:-4]
        return repo
    m2 = re.match(r"^([a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+)$", raw)
    if m2:
        repo = m2.group(1).rstrip("/")
        if repo.endswith(".git"):
            repo = repo[:-4]
        return repo
    return raw

def run_gh_api(endpoint: str) -> dict:
    """调用 gh api 获取数据"""
    gh_bin = shutil.which("gh") or (GH_CLI_PATH if os.path.exists(GH_CLI_PATH) else "gh")
    cmd = [gh_bin, "api", endpoint]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        return {"_error": res.stderr.strip()}
    try:
        return json.loads(res.stdout)
    except Exception as e:
        return {"_error": str(e), "_raw": res.stdout[:500]}

def extract_readme_summary(readme_text: str) -> dict:
    """从 README 中提取核心模块：定位简介、特性列表、安装部署方式"""
    if not readme_text:
        return {"summary": "", "features": [], "install_guide": ""}
        
    lines = readme_text.split("\n")
    intro = []
    features = []
    install_blocks = []
    
    recording_features = False
    recording_install = False
    current_header_level = 0
    
    for line in lines:
        s = line.strip()
        header_m = re.match(r"^(#{1,4})\s*(.*)", s)
        if header_m:
            level = len(header_m.group(1))
            title = header_m.group(2).strip()
            if re.search(r"^(features|core features|key features|highlights|核心功能|主要特性|功能特性)", title, re.I):
                recording_features = True
                recording_install = False
                current_header_level = level
                continue
            elif re.search(r"^(installation|getting started|get started|quick start|quickstart|setup|download|install|build from source|deploy|docker|快速开始|安装|部署|使用方法|上手指引)", title, re.I):
                recording_features = False
                recording_install = True
                current_header_level = level
                continue
            elif (recording_features or recording_install) and level <= current_header_level:
                recording_features = False
                recording_install = False
            
        if recording_features:
            if s.startswith("- ") or s.startswith("* ") or s.startswith("1. "):
                clean_feat = re.sub(r"^[-*0-9.]+\s*", "", s)
                if clean_feat and len(features) < 8:
                    features.append(clean_feat)
        elif recording_install:
            if len(install_blocks) < 25:
                install_blocks.append(line)
        elif not intro and s:
            if not s.startswith("#") and not s.startswith("<") and not s.startswith("[!") and not s.startswith("<!--"):
                clean_s = re.sub(r"\[.*?\]\(.*?\)", "", s).strip()
                if clean_s and not clean_s.startswith("<") and len(clean_s) > 10:
                    intro.append(clean_s)
            
    summary_text = " ".join(intro[:3]) if intro else ""
    if len(summary_text) > 300:
        summary_text = summary_text[:300] + "..."
        
    return {
        "summary": summary_text,
        "features": features,
        "install_guide": "\n".join(install_blocks).strip()
    }

def research_repo(repo_id: str) -> dict:
    repo = parse_repo_identifier(repo_id)
    if "/" not in repo:
        encoded_q = urllib.parse.quote(repo)
        search_res = run_gh_api(f"search/repositories?q={encoded_q}&sort=stars&order=desc&per_page=1")
        if "_error" in search_res:
            return {"error": f"Search API error: {search_res['_error']}"}
        if "items" in search_res and search_res["items"]:
            repo = search_res["items"][0]["full_name"]
        else:
            return {"error": f"Cannot find repository: {repo_id}"}
            
    print(f"[*] Fetching metadata for: {repo} ...", file=sys.stderr)
    meta = run_gh_api(f"repos/{repo}")
    if "_error" in meta:
        return {"error": f"API error: {meta['_error']}"}
        
    # 并发拉取语言分布、最新Release与README（3倍提速）
    with ThreadPoolExecutor(max_workers=3) as executor:
        f_langs = executor.submit(run_gh_api, f"repos/{repo}/languages")
        f_release = executor.submit(run_gh_api, f"repos/{repo}/releases/latest")
        f_readme = executor.submit(run_gh_api, f"repos/{repo}/readme")
        
        langs_data = f_langs.result()
        release_data = f_release.result()
        readme_resp = f_readme.result()

    total_bytes = sum(v for v in langs_data.values() if isinstance(v, int))
    languages_percent = {}
    if total_bytes > 0:
        for lang, b in langs_data.items():
            if isinstance(b, int):
                pct = round((b / total_bytes) * 100, 1)
                if pct >= 1.0:
                    languages_percent[lang] = f"{pct}%"

    latest_release = {}
    if "_error" not in release_data:
        latest_release = {
            "tag_name": release_data.get("tag_name", ""),
            "name": release_data.get("name", ""),
            "published_at": (release_data.get("published_at") or "")[:10],
            "html_url": release_data.get("html_url", ""),
            "body_excerpt": (release_data.get("body", "") or "")[:200].replace("\r", " ").replace("\n", " ").strip()
        }
    else:
        tags_data = run_gh_api(f"repos/{repo}/tags?per_page=1")
        if isinstance(tags_data, list) and tags_data:
            tag0 = tags_data[0]
            latest_release = {
                "tag_name": tag0.get("name", ""),
                "name": tag0.get("name", ""),
                "published_at": "",
                "html_url": f"https://github.com/{repo}/releases/tag/{tag0.get('name', '')}",
                "body_excerpt": "滚动更新 Tag"
            }
    readme_content = ""
    if "content" in readme_resp and readme_resp.get("encoding") == "base64":
        try:
            readme_content = base64.b64decode(readme_resp["content"]).decode("utf-8", errors="ignore")
        except Exception:
            pass
            
    readme_extracted = extract_readme_summary(readme_content)

    result = {
        "repo": repo,
        "name": meta.get("name", ""),
        "full_name": meta.get("full_name", ""),
        "html_url": meta.get("html_url", f"https://github.com/{repo}"),
        "description": meta.get("description", "") or "",
        "stars": meta.get("stargazers_count", 0),
        "forks": meta.get("forks_count", 0),
        "watchers": meta.get("watchers_count", 0),
        "open_issues": meta.get("open_issues_count", 0),
        "license": meta.get("license", {}).get("spdx_id", "") if meta.get("license") else "",
        "primary_language": meta.get("language", "") or "",
        "languages": languages_percent,
        "topics": meta.get("topics", []),
        "created_at": (meta.get("created_at") or "")[:10],
        "updated_at": (meta.get("updated_at") or "")[:10],
        "pushed_at": (meta.get("pushed_at") or "")[:10],
        "homepage": meta.get("homepage", "") or "",
        "owner": {
            "login": meta.get("owner", {}).get("login", ""),
            "type": meta.get("owner", {}).get("type", ""),
            "html_url": meta.get("owner", {}).get("html_url", "")
        },
        "latest_release": latest_release,
        "readme_analysis": readme_extracted
    }
    
    return result

def format_markdown_summary(data: dict) -> str:
    r = data
    topics_str = " ".join([f"`#{t}`" for t in r.get("topics", [])])
    langs_str = ", ".join([f"{k} ({v})" for k, v in r.get("languages", {}).items()]) or r.get("primary_language", "Unknown")
    rel = r.get("latest_release", {})
    rel_str = f"[{rel.get('tag_name')}]({rel.get('html_url')}) ({rel.get('published_at')})" if rel.get("tag_name") else "暂无发布版本 (滚动更新)"
    
    feats = "\n".join([f"- {f}" for f in r.get("readme_analysis", {}).get("features", [])]) or "- （未在 README 中显式列出）"
    install = r.get("readme_analysis", {}).get("install_guide", "").strip() or "# 参见项目仓库 README"

    md = f"""# GitHub 深度调研卡片: {r.get('full_name')}

- **仓库地址**: [{r.get('html_url')}]({r.get('html_url')})
- **一句话介绍**: {r.get('description')}
- **核心数据**: ⭐ **{r.get('stars'):,}** Stars ｜ 🍴 **{r.get('forks'):,}** Forks ｜ 🐛 **{r.get('open_issues'):,}** Issues
- **协议与主语言**: License: `{r.get('license') or 'None'}` ｜ 主语言: `{r.get('primary_language')}`
- **技术构成比例**: {langs_str}
- **标签/Topics**: {topics_str}
- **最新版本**: {rel_str}
- **更新活跃度**: 创建时间 `{r.get('created_at')}` ｜ 最近推送 `{r.get('pushed_at')}`

---

## 一、README 核心特性提炼
{feats}

## 二、快速上手与安装指引
```bash
{install}
```
"""
    return md

def main():
    parser = argparse.ArgumentParser(description="GitHub 仓库深度数据调研工具")
    parser.add_argument("repo", help="仓库名称或完整URL，例如 julyx10/lap 或 https://github.com/julyx10/lap")
    parser.add_argument("--json", help="输出完整 JSON 文件路径")
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown", help="标准输出格式")
    args = parser.parse_args()

    data = research_repo(args.repo)
    if "error" in data:
        print(f"Error: {data['error']}", file=sys.stderr)
        sys.exit(1)

    if args.json:
        os.makedirs(os.path.dirname(os.path.abspath(args.json)), exist_ok=True)
        with open(args.json, "w", encoding="utf-8") as fp:
            json.dump(data, fp, ensure_ascii=False, indent=2)
        print(f"[✓] JSON data saved to: {args.json}", file=sys.stderr)

    if args.format == "json":
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print(format_markdown_summary(data))

if __name__ == "__main__":
    main()
