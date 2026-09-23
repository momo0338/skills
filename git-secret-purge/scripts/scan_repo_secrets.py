#!/usr/bin/env python3
"""
扫描 git 仓库中的凭据残留（cookie / token / API key / 私钥）。

三种模式：
  --tracked            扫描所有【已跟踪文件】（找尚未暴露的隐患）
  --objects            扫描【对象库全部 blob】（验证历史清理是否彻底，含悬空对象）
  --verify <blob-sha>  定点确认某个 blob 是否还在对象库里

安全约定：输出只报【文件路径 / 对象名 + 命中数 + 类别】，绝不回显凭据明文。

用法：
  python3 scan_repo_secrets.py --repo /path/to/repo --tracked
  python3 scan_repo_secrets.py --repo . --objects
  python3 scan_repo_secrets.py --repo . --objects --exclude '*.md' 'git-secret-purge/*'
  python3 scan_repo_secrets.py --repo . --verify 504bcc0d5d24727936128edb3aaa779c500290e8

关于误报：本脚本与 SKILL.md 本身会【描述】这些关键词（slave_sid / ghp_ 等），
因此扫自己所在仓库时会自命中；测试文件里的构造样例（如 ghp_abcd...wxyz）也会命中。
用 --exclude 排除即可，属预期行为，不代表真实泄露。
"""
from __future__ import annotations

import argparse
import fnmatch
import re
import subprocess
import sys

# 全部使用 bytes 正则：遍历 blob 时二进制文件（PNG/ZIP 等）无法按 utf-8 解码，
# 用 str 模式读会抛 UnicodeDecodeError。这里一律走字节比较。
PATTERNS: list[tuple[str, bytes]] = [
    # 关键词拆开拼接，避免本脚本源码自命中
    ("微信后台 cookie",
     rb"slave_" rb"sid|slave_" rb"user|data_" rb"ticket|slave_" rb"bizuin|"
     rb"data_" rb"bizuin|appmsg_" rb"token"),
    ("cookie/session 赋值",
     rb"(?i)(cookie|sessionid|session_id|csrf|xsrf|auth[_-]?token)"
     rb"[\"']?\s*[:=]\s*[\"']?[A-Za-z0-9_\-]{16,}"),
    ("API key 赋值",
     rb"(?i)(api[_-]?key|apikey|access[_-]?key|secret[_-]?key|app[_-]?secret"
     rb"|client[_-]?secret|private[_-]?key)[\"']?\s*[:=]\s*[\"'][A-Za-z0-9_\-]{16,}"),
    ("私钥文件",
     rb"-----BEGIN [A-Z ]*PRIVATE " rb"KEY-----"),
    ("服务商 token 前缀",
     rb"\b(" rb"sk-" rb"[A-Za-z0-9]{20,}|" rb"ghp_" rb"[A-Za-z0-9]{20,}|"
     rb"github_" rb"pat_[A-Za-z0-9_]{20,}|" rb"xox[baprs]-[A-Za-z0-9\-]{10,}|"
     rb"AKIA" rb"[0-9A-Z]{16})"),
    ("JWT",
     rb"\beyJ" rb"[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}"),
]

MAX_BLOB = 5 * 1024 * 1024  # 超过 5MB 的 blob 跳过，避免拖慢


def git(repo: str, *args: str, text: bool = True):
    """执行 git 命令。text=False 时返回 bytes（用于读二进制安全的内容）。"""
    return subprocess.run(["git", "-C", repo, *args], capture_output=True, text=text)


def match_bytes(data: bytes) -> list[tuple[str, int]]:
    """返回 [(类别, 命中数)]，只统计数量，不回显明文。"""
    out = []
    for label, pat in PATTERNS:
        n = len(re.findall(pat, data))
        if n:
            out.append((label, n))
    return out


def is_excluded(path: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(path, p) for p in patterns)


def scan_tracked(repo: str, excludes: list[str]) -> int:
    files = [f for f in git(repo, "ls-files").stdout.split()
             if not is_excluded(f, excludes)]
    print(f"已跟踪文件 {len(files)} 个待扫描"
          + (f"（已排除 {len(excludes)} 条规则）" if excludes else "") + "\n")
    hits = 0
    for f in files:
        try:
            data = open(f"{repo}/{f}", "rb").read()
        except OSError:
            continue
        found = match_bytes(data)
        if found:
            hits += 1
            print(f"  ⚠️  {f}")
            for label, n in found:
                print(f"        - {label}: {n} 处")
    print(f"\n{'⚠️  命中 ' + str(hits) + ' 个文件' if hits else '✅ 未发现凭据'}")
    return 1 if hits else 0


def blob_path_map(repo: str) -> dict[str, str]:
    """从所有可达对象建立 blob -> 路径 映射（用于把残留 blob 对应回文件）。"""
    out = git(repo, "rev-list", "--objects", "--all").stdout
    m: dict[str, str] = {}
    for line in out.splitlines():
        parts = line.split(" ", 1)
        if len(parts) == 2:
            m.setdefault(parts[0], parts[1])
    return m


def scan_objects(repo: str, excludes: list[str]) -> int:
    raw = git(repo, "cat-file", "--batch-all-objects",
              "--batch-check=%(objecttype) %(objectname) %(objectsize)").stdout
    blobs = [l.split() for l in raw.splitlines() if l.startswith("blob")]
    paths = blob_path_map(repo)
    print(f"对象库 blob 共 {len(blobs)} 个（含悬空对象）\n")
    hits = 0
    for _, sha, size in blobs:
        if int(size) > MAX_BLOB:
            continue
        path = paths.get(sha, "")
        if path and is_excluded(path, excludes):
            continue
        data = git(repo, "cat-file", "-p", sha, text=False).stdout  # ← 字节模式，关键
        found = match_bytes(data)
        if found:
            hits += 1
            tag = f" <- {path}" if path else " <- (悬空/无路径)"
            print(f"  ⚠️  blob {sha} ({size} B){tag}")
            for label, n in found:
                print(f"        - {label}: {n} 处")
    print(f"\n{'⚠️  命中 ' + str(hits) + ' 个 blob' if hits else '✅ 对象库中未发现凭据残留'}")
    return 1 if hits else 0


def verify_blob(repo: str, sha: str) -> int:
    t = git(repo, "cat-file", "-t", sha).stdout.strip()
    if not t:
        print(f"✅ blob {sha} 已不在对象库中（清理彻底）")
        return 0
    data = git(repo, "cat-file", "-p", sha, text=False).stdout
    is_reach = sha in git(repo, "rev-list", "--objects", "--all").stdout
    print(f"⚠️  blob {sha} 仍存在于对象库（type={t}, {len(data)} B）")
    print("    是否仍被任何 ref 可达: "
          + ("是 ← 会随 push 泄露，必须处理" if is_reach
             else "否（悬空，push 不会带走，但建议 gc）"))
    for label, n in match_bytes(data):
        print(f"    - 命中 «{label}»: {n} 处")
    return 1


def main() -> int:
    ap = argparse.ArgumentParser(description="扫描 git 仓库中的凭据残留")
    ap.add_argument("--repo", default=".", help="仓库路径（默认当前目录）")
    ap.add_argument("--exclude", nargs="*", default=[],
                    help="排除路径 glob（可多个），如 --exclude '*.md' 'git-secret-purge/*'")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--tracked", action="store_true", help="扫描已跟踪文件")
    g.add_argument("--objects", action="store_true", help="扫描对象库全部 blob")
    g.add_argument("--verify", metavar="BLOB_SHA", help="确认某 blob 是否仍在对象库")
    a = ap.parse_args()

    if a.tracked:
        return scan_tracked(a.repo, a.exclude)
    if a.objects:
        return scan_objects(a.repo, a.exclude)
    return verify_blob(a.repo, a.verify)


if __name__ == "__main__":
    sys.exit(main())
