#!/usr/bin/env python3
"""Safely route public GitHub resources through mirror fallbacks."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import parse_qsl, urlparse


SKILL_DIR = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = SKILL_DIR / "references" / "mirrors.json"
ALLOWED_HOSTS = {
    "github.com",
    "www.github.com",
    "raw.githubusercontent.com",
    "codeload.github.com",
    "gist.github.com",
}
SENSITIVE_QUERY_KEYS = {
    "access_token",
    "auth",
    "authorization",
    "private_token",
    "signature",
    "token",
    "x-amz-signature",
}
SENSITIVE_TEXT = re.compile(
    r"(?:github_pat_|gh[pousr]_[A-Za-z0-9]{12,}|bearer\s+[A-Za-z0-9._~-]+)",
    re.IGNORECASE,
)


class AcceleratorError(ValueError):
    """Raised for invalid or unsafe inputs."""


@dataclass(frozen=True)
class Candidate:
    name: str
    url: str
    mirror: bool


@dataclass(frozen=True)
class CheckResult:
    name: str
    url: str
    ok: bool
    returncode: int
    detail: str


def load_config(path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    try:
        with path.open(encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise AcceleratorError(f"cannot load mirror config {path}: {exc}") from exc
    if data.get("schema_version") != 1 or not isinstance(data.get("github"), dict):
        raise AcceleratorError("unsupported mirror config schema")
    return data


def mirror_base(item: dict[str, Any]) -> str:
    base = str(item.get("base_url", ""))
    parsed = urlparse(base)
    if parsed.scheme != "https" or not parsed.hostname:
        raise AcceleratorError(f"mirror {item.get('name', '<unnamed>')} must use HTTPS")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise AcceleratorError(f"mirror {item.get('name', '<unnamed>')} has an unsafe base URL")
    return base.rstrip("/") + "/"


def validate_github_url(url: str, *, kind: str = "auto") -> None:
    if SENSITIVE_TEXT.search(url):
        raise AcceleratorError("refusing URL that appears to contain a credential or token")
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise AcceleratorError("only HTTPS GitHub URLs are supported")
    if parsed.username or parsed.password or "@" in parsed.netloc:
        raise AcceleratorError("refusing URL with embedded credentials")
    host = (parsed.hostname or "").lower()
    if host == "api.github.com":
        raise AcceleratorError("GitHub API requests must not use public mirrors")
    if host not in ALLOWED_HOSTS:
        raise AcceleratorError(f"unsupported GitHub host: {host or '<missing>'}")
    sensitive_keys = {key.lower() for key, _ in parse_qsl(parsed.query, keep_blank_values=True)}
    if sensitive_keys.intersection(SENSITIVE_QUERY_KEYS):
        raise AcceleratorError("refusing URL with a sensitive query parameter")
    if kind == "clone":
        clone_repo_path(url)


def clone_repo_path(url: str) -> str:
    parsed = urlparse(url)
    if (parsed.hostname or "").lower() not in {"github.com", "www.github.com"}:
        raise AcceleratorError("clone expects an https://github.com/owner/repo URL")
    if parsed.query or parsed.fragment:
        raise AcceleratorError("clone URL must not contain query parameters or fragments")
    path = parsed.path.strip("/")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:\.git)?", path):
        raise AcceleratorError("clone expects https://github.com/owner/repo(.git)")
    if not path.endswith(".git"):
        path += ".git"
    return path


def infer_kind(url: str) -> str:
    parsed = urlparse(url)
    if (parsed.hostname or "").lower() == "raw.githubusercontent.com":
        return "raw"
    path = parsed.path.strip("/")
    if re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\.git", path):
        return "clone"
    return "download"


def build_candidates(
    url: str,
    kind: str = "auto",
    config: dict[str, Any] | None = None,
) -> list[Candidate]:
    resolved_kind = infer_kind(url) if kind == "auto" else kind
    validate_github_url(url, kind=resolved_kind)
    if resolved_kind not in {"download", "raw", "clone"}:
        raise AcceleratorError(f"unsupported operation kind: {resolved_kind}")

    github = (config or load_config())["github"]
    candidates: list[Candidate] = []
    for item in github.get("prefix_mirrors", []):
        if resolved_kind in item.get("kinds", []):
            base = mirror_base(item)
            candidates.append(Candidate(str(item["name"]), base + url, True))

    if resolved_kind == "clone":
        repo_path = clone_repo_path(url)
        for item in github.get("clone_mirrors", []):
            if "clone" in item.get("kinds", []):
                base = mirror_base(item)
                candidates.append(Candidate(str(item["name"]), base + repo_path, True))

    candidates.append(Candidate(str(github.get("direct_name", "github-direct")), url, False))
    deduped: list[Candidate] = []
    seen: set[str] = set()
    for candidate in candidates:
        if candidate.url not in seen:
            deduped.append(candidate)
            seen.add(candidate.url)
    return deduped


def public_required(value: bool) -> None:
    if not value:
        raise AcceleratorError("network operations require --public confirmation")


def command_env() -> dict[str, str]:
    env = os.environ.copy()
    env.update({
        "GIT_TERMINAL_PROMPT": "0",
        "GCM_INTERACTIVE": "Never",
    })
    return env


def writable_parent(path: Path) -> bool:
    parent = path.parent if str(path.parent) else Path(".")
    return os.access(parent, os.W_OK | os.X_OK)


def resolve_destination(
    requested: Path,
    fallback_dir: Path | None,
    *,
    kind: str,
) -> Path:
    if writable_parent(requested):
        return requested
    if fallback_dir is None:
        raise AcceleratorError(
            f"destination directory is not writable: {requested.parent} "
            "(pass --fallback-dir to use a temporary location)"
        )
    fallback = Path(fallback_dir).expanduser()
    if not fallback.is_dir():
        raise AcceleratorError(f"fallback directory does not exist: {fallback}")
    if not writable_parent(fallback / "probe"):
        raise AcceleratorError(f"fallback directory is not writable: {fallback}")
    if kind == "file":
        actual = fallback / f"{requested.name}.accelerate"
    else:
        actual = fallback / f"{requested.name}-accelerate"
    if actual.exists():
        raise AcceleratorError(f"fallback destination already exists: {actual}")
    if kind == "file":
        actual.parent.mkdir(parents=True, exist_ok=True)
    else:
        actual.mkdir(parents=True)
    print(
        f"destination {requested.parent} is not writable; using {actual}",
        file=sys.stderr,
    )
    return actual


def run_command(command: list[str], *, timeout: int) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=command_env(),
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout.decode(errors="replace") if isinstance(exc.stdout, bytes) else exc.stdout or ""
        return subprocess.CompletedProcess(command, 124, stdout, "operation timed out")


def detail_from(result: subprocess.CompletedProcess[str]) -> str:
    detail = (result.stderr or result.stdout or "").strip().splitlines()
    return detail[-1][:300] if detail else f"exit {result.returncode}"


def check_candidate(candidate: Candidate, kind: str, timeout: int) -> CheckResult:
    if kind == "clone":
        command = [
            "git", "-c", "credential.helper=", "-c", "http.lowSpeedLimit=1",
            "-c", "http.lowSpeedTime=5", "ls-remote", candidate.url, "HEAD",
        ]
    else:
        command = [
            "curl", "-sS", "-I", "-L", "--fail", "--connect-timeout", "4",
            "--max-time", str(timeout), "-o", os.devnull, candidate.url,
        ]
    result = run_command(command, timeout=timeout + 2)
    return CheckResult(
        candidate.name,
        candidate.url,
        result.returncode == 0,
        result.returncode,
        "ok" if result.returncode == 0 else detail_from(result),
    )


def check_all(url: str, kind: str, timeout: int, config: dict[str, Any]) -> list[CheckResult]:
    resolved_kind = infer_kind(url) if kind == "auto" else kind
    ensure_binary("git" if resolved_kind == "clone" else "curl")
    return [check_candidate(candidate, resolved_kind, timeout) for candidate in build_candidates(url, kind, config)]


def ensure_binary(name: str) -> None:
    if shutil.which(name) is None:
        raise AcceleratorError(f"required command not found: {name}")


def download_public(
    url: str,
    output: Path,
    *,
    timeout: int,
    config: dict[str, Any],
    fallback_dir: Path | None = None,
) -> Candidate:
    ensure_binary("curl")
    resolved_kind = infer_kind(url)
    if resolved_kind == "clone":
        raise AcceleratorError("download received a clone URL; use the clone command")
    validate_github_url(url, kind=resolved_kind)
    if os.path.lexists(output):
        raise AcceleratorError(f"output already exists: {output}")
    output = resolve_destination(output, fallback_dir, kind="file")
    output.parent.mkdir(parents=True, exist_ok=True)

    for candidate in build_candidates(url, resolved_kind, config):
        temp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                prefix=f".{output.name}.accelerate-",
                dir=output.parent,
                delete=False,
            ) as handle:
                temp_path = Path(handle.name)
            print(f"trying {candidate.name}: {candidate.url}", file=sys.stderr)
            command = [
                "curl", "-sS", "-L", "--fail", "--connect-timeout", "5",
                "--max-time", str(timeout), "--output", str(temp_path), candidate.url,
            ]
            result = run_command(command, timeout=timeout + 2)
            if result.returncode == 0 and temp_path.is_file() and temp_path.stat().st_size > 0:
                temp_path.replace(output)
                print(f"selected {candidate.name}", file=sys.stderr)
                return candidate
            if result.returncode == 0:
                result = subprocess.CompletedProcess(command, 1, result.stdout, "download produced an empty file")
            print(f"failed {candidate.name}: {detail_from(result)}", file=sys.stderr)
        finally:
            if temp_path is not None and temp_path.exists():
                temp_path.unlink()
    raise AcceleratorError("all mirror and direct download candidates failed")


def clone_public(
    url: str,
    destination: Path,
    *,
    timeout: int,
    depth: int | None,
    config: dict[str, Any],
    fallback_dir: Path | None = None,
) -> Candidate:
    ensure_binary("git")
    validate_github_url(url, kind="clone")
    if os.path.lexists(destination):
        raise AcceleratorError(f"clone destination already exists: {destination}")
    destination = resolve_destination(destination, fallback_dir, kind="dir")
    destination.parent.mkdir(parents=True, exist_ok=True)

    for candidate in build_candidates(url, "clone", config):
        with tempfile.TemporaryDirectory(
            prefix=f".{destination.name}.accelerate-",
            dir=destination.parent,
        ) as temp_dir:
            temp_repo = Path(temp_dir) / "repo"
            command = [
                "git", "-c", "credential.helper=", "-c", "http.lowSpeedLimit=1",
                "-c", "http.lowSpeedTime=15", "clone",
            ]
            if depth is not None:
                command.extend(["--depth", str(depth)])
            command.extend([candidate.url, str(temp_repo)])
            print(f"trying {candidate.name}: {candidate.url}", file=sys.stderr)
            result = run_command(command, timeout=timeout)
            if result.returncode == 0 and temp_repo.is_dir():
                temp_repo.replace(destination)
                print(f"selected {candidate.name}", file=sys.stderr)
                return candidate
            print(f"failed {candidate.name}: {detail_from(result)}", file=sys.stderr)
    raise AcceleratorError("all mirror and direct clone candidates failed")


def emit_candidates(candidates: Iterable[Candidate], as_json: bool) -> None:
    values = list(candidates)
    if as_json:
        print(json.dumps([asdict(item) for item in values], ensure_ascii=False, indent=2))
    else:
        for item in values:
            print(f"{item.name}\t{item.url}")


def emit_checks(results: Iterable[CheckResult], as_json: bool) -> None:
    values = list(results)
    if as_json:
        print(json.dumps([asdict(item) for item in values], ensure_ascii=False, indent=2))
    else:
        for item in values:
            status = "OK" if item.ok else "FAIL"
            print(f"{status}\t{item.name}\t{item.detail}\t{item.url}")


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    root.add_argument(
        "--config",
        type=Path,
        default=Path(os.environ.get("DEV_ACCEL_CONFIG", DEFAULT_CONFIG)),
        help="mirror registry JSON",
    )
    sub = root.add_subparsers(dest="command", required=True)

    candidates = sub.add_parser("candidates", help="generate candidate URLs without network access")
    candidates.add_argument("url")
    candidates.add_argument("--kind", choices=["auto", "download", "raw", "clone"], default="auto")
    candidates.add_argument("--json", action="store_true")

    check = sub.add_parser("check", help="probe candidates against the real target")
    check.add_argument("url")
    check.add_argument("--kind", choices=["auto", "download", "raw", "clone"], default="auto")
    check.add_argument("--timeout", type=int, default=10)
    check.add_argument("--public", action="store_true")
    check.add_argument("--json", action="store_true")

    download = sub.add_parser("download", help="download a public GitHub resource with fallback")
    download.add_argument("url")
    download.add_argument("output", type=Path)
    download.add_argument("--timeout", type=int, default=300)
    download.add_argument("--public", action="store_true")
    download.add_argument("--fallback-dir", type=Path)

    clone = sub.add_parser("clone", help="clone a public GitHub repository with fallback")
    clone.add_argument("url")
    clone.add_argument("destination", type=Path)
    clone.add_argument("--timeout", type=int, default=900)
    clone.add_argument("--depth", type=int)
    clone.add_argument("--public", action="store_true")
    clone.add_argument("--fallback-dir", type=Path)
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        config = load_config(args.config)
        if args.command == "candidates":
            emit_candidates(build_candidates(args.url, args.kind, config), args.json)
        elif args.command == "check":
            public_required(args.public)
            emit_checks(check_all(args.url, args.kind, args.timeout, config), args.json)
        elif args.command == "download":
            public_required(args.public)
            selected = download_public(
                args.url,
                args.output,
                timeout=args.timeout,
                config=config,
                fallback_dir=args.fallback_dir,
            )
            print(json.dumps(asdict(selected), ensure_ascii=False))
        elif args.command == "clone":
            public_required(args.public)
            if args.depth is not None and args.depth < 1:
                raise AcceleratorError("--depth must be a positive integer")
            selected = clone_public(
                args.url,
                args.destination,
                timeout=args.timeout,
                depth=args.depth,
                config=config,
                fallback_dir=args.fallback_dir,
            )
            print(json.dumps(asdict(selected), ensure_ascii=False))
    except AcceleratorError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
