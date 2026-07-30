#!/usr/bin/env python3
"""Archive Douyin posts with one portable metadata sidecar per post.

This is a skill-local compatibility wrapper for dy-cli 0.2.2. It does not
modify the installed package.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from zoneinfo import ZoneInfo


SUPPORTED_DY_CLI_VERSIONS = {"0.2.2"}
SENSITIVE_KEY = re.compile(
    r"(?:authorization|cookie|credential|passport|secret|session|ticket|token|x-bogus)",
    re.IGNORECASE,
)
SENSITIVE_QUERY_KEY = re.compile(
    r"(?:auth|credential|expires?|secret|session|signature|sign|ticket|token|x-bogus)",
    re.IGNORECASE,
)
SHANGHAI = ZoneInfo("Asia/Shanghai")
AWEME_ID_PATTERN = re.compile(r"^\d{15,25}$")
DOUYIN_URL_PATTERN = re.compile(r"https?://[^\s<>\"]+", re.IGNORECASE)
DIRECT_AWEME_URL_PATTERN = re.compile(
    r"/(?:(?:share/)?video|note)/(\d{15,25})(?:[/?#]|$)",
    re.IGNORECASE,
)
URL_TRAILING_PUNCTUATION = "，。！？；：、,!?;:）)]】}>'\""


class ArchiveError(RuntimeError):
    """Raised when the primary media cannot be archived."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def local_time_from_epoch(value: Any) -> str | None:
    try:
        return datetime.fromtimestamp(int(value), tz=SHANGHAI).isoformat(timespec="seconds")
    except (TypeError, ValueError, OSError):
        return None


def first_url(value: Any, *, prefer_last: bool = False) -> str | None:
    if isinstance(value, str):
        return value or None
    if not isinstance(value, dict):
        return None
    urls = value.get("url_list")
    if not isinstance(urls, list):
        return None
    valid = [item for item in urls if isinstance(item, str) and item]
    if not valid:
        return None
    return valid[-1] if prefer_last else valid[0]


def safe_filename(value: str, limit: int = 60) -> str:
    cleaned = re.sub(r'[\x00-\x1f\\/:*?"<>|]+', "_", value or "")
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ._")
    return cleaned[:limit].rstrip(" ._") or "untitled"


def strip_sensitive_url(value: str) -> str:
    try:
        parts = urlsplit(value)
    except ValueError:
        return value
    if parts.scheme not in {"http", "https"}:
        return value
    query = [
        (key, item)
        for key, item in parse_qsl(parts.query, keep_blank_values=True)
        if not SENSITIVE_QUERY_KEY.search(key)
    ]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), ""))


def sanitize_raw(value: Any, key: str = "") -> Any:
    if key and SENSITIVE_KEY.search(key):
        return "<redacted>"
    if isinstance(value, dict):
        return {str(k): sanitize_raw(v, str(k)) for k, v in value.items()}
    if isinstance(value, list):
        return [sanitize_raw(item) for item in value]
    if isinstance(value, str) and value.startswith(("http://", "https://")):
        return strip_sensitive_url(value)
    return value


def normalized_comments(items: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for item in items:
        user = item.get("user") if isinstance(item.get("user"), dict) else {}
        result.append(
            {
                "comment_id": item.get("cid"),
                "text": item.get("text"),
                "created_at": local_time_from_epoch(item.get("create_time")),
                "digg_count": item.get("digg_count"),
                "reply_count": item.get("reply_comment_total"),
                "user": {
                    "nickname": user.get("nickname"),
                    "sec_uid": user.get("sec_uid"),
                },
            }
        )
    return result


def normalize_detail(detail: dict[str, Any]) -> dict[str, Any]:
    author = detail.get("author") if isinstance(detail.get("author"), dict) else {}
    video = detail.get("video") if isinstance(detail.get("video"), dict) else {}
    music = detail.get("music") if isinstance(detail.get("music"), dict) else {}
    stats = detail.get("statistics") if isinstance(detail.get("statistics"), dict) else {}
    aweme_id = str(detail.get("aweme_id") or "")

    hashtags = []
    for item in detail.get("text_extra") or []:
        if isinstance(item, dict) and item.get("hashtag_name"):
            value = item["hashtag_name"]
            if value not in hashtags:
                hashtags.append(value)

    tags = []
    for item in detail.get("video_tag") or []:
        if isinstance(item, dict) and item.get("tag_name"):
            value = item["tag_name"]
            if value not in tags:
                tags.append(value)

    return {
        "identity": {
            "platform": "douyin",
            "aweme_id": aweme_id,
            "canonical_url": f"https://www.douyin.com/video/{aweme_id}" if aweme_id else None,
        },
        "content": {
            "title": detail.get("desc"),
            "caption": detail.get("caption"),
            "created_at": local_time_from_epoch(detail.get("create_time")),
            "hashtags": hashtags,
            "tags": tags,
            "content_type": "image" if detail.get("images") else "video",
        },
        "author": {
            "nickname": author.get("nickname"),
            "unique_id": author.get("unique_id"),
            "sec_uid": author.get("sec_uid"),
            "signature": author.get("signature"),
            "follower_count": author.get("follower_count"),
            "total_favorited": author.get("total_favorited"),
        },
        "statistics": {
            "observed_at": utc_now(),
            "play_count": stats.get("play_count") if stats.get("play_count") not in (0, "0") else None,
            "digg_count": stats.get("digg_count"),
            "comment_count": stats.get("comment_count"),
            "share_count": stats.get("share_count"),
            "collect_count": stats.get("collect_count"),
        },
        "platform_media": {
            "duration_ms": video.get("duration"),
            "width": video.get("width"),
            "height": video.get("height"),
            "music": {
                "title": music.get("title"),
                "author": music.get("author"),
                "duration_seconds": music.get("duration"),
            },
        },
    }


def extract_asset_urls(detail: dict[str, Any]) -> dict[str, list[str]]:
    video = detail.get("video") if isinstance(detail.get("video"), dict) else {}
    author = detail.get("author") if isinstance(detail.get("author"), dict) else {}
    music = detail.get("music") if isinstance(detail.get("music"), dict) else {}

    assets: dict[str, list[str]] = {
        "video": [],
        "image": [],
        "cover": [],
        "avatar": [],
        "music": [],
    }

    video_url = None
    bit_rate = video.get("bit_rate")
    if isinstance(bit_rate, list) and bit_rate:
        # 优先从 bit_rate 列表中获取最佳画质（通常索引 0 是最高画质）
        best_quality = bit_rate[0]
        if isinstance(best_quality, dict):
            video_url = first_url(best_quality.get("play_addr"), prefer_last=True)
    
    if not video_url:
        # 回退到默认的 play_addr
        video_url = first_url(video.get("play_addr"), prefer_last=True)

    if video_url:
        assets["video"].append(video_url.replace("playwm", "play"))

    for image in detail.get("images") or []:
        url = first_url(image, prefer_last=True)
        if url:
            assets["image"].append(url)

    for cover_key in ("origin_cover", "cover", "dynamic_cover"):
        url = first_url(video.get(cover_key), prefer_last=True)
        if url:
            assets["cover"].append(url)
            break

    for avatar_key in ("avatar_larger", "avatar_medium", "avatar_thumb"):
        url = first_url(author.get(avatar_key), prefer_last=True)
        if url:
            assets["avatar"].append(url)
            break

    music_url = first_url(music.get("play_url"))
    if music_url:
        assets["music"].append(music_url)
    return assets


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def probe_media(path: Path) -> dict[str, Any]:
    if not shutil.which("ffprobe"):
        return {}
    command = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=format_name,duration:stream=codec_type,codec_name,width,height",
        "-of",
        "json",
        str(path),
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True, timeout=30)
        data = json.loads(result.stdout)
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
        return {}

    streams = data.get("streams") if isinstance(data.get("streams"), list) else []
    video_stream = next((s for s in streams if s.get("codec_type") == "video"), {})
    audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), {})
    fmt = data.get("format") if isinstance(data.get("format"), dict) else {}
    duration = fmt.get("duration")
    try:
        duration_ms = round(float(duration) * 1000) if duration is not None else None
    except (TypeError, ValueError):
        duration_ms = None
    return {
        "container": fmt.get("format_name"),
        "duration_ms": duration_ms,
        "video_codec": video_stream.get("codec_name"),
        "audio_codec": audio_stream.get("codec_name"),
        "width": video_stream.get("width"),
        "height": video_stream.get("height"),
    }


def sniff_extension(path: Path, role: str) -> tuple[str, str]:
    head = path.read_bytes()[:16]
    if head.startswith(b"\xff\xd8\xff"):
        return ".jpg", "image/jpeg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png", "image/png"
    if head.startswith(b"RIFF") and head[8:12] == b"WEBP":
        return ".webp", "image/webp"
    if head.startswith(b"ID3") or head[:2] in {b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"}:
        return ".mp3", "audio/mpeg"
    if len(head) >= 12 and head[4:8] == b"ftyp":
        return (".m4a", "audio/mp4") if role == "music" else (".mp4", "video/mp4")
    defaults = {
        "video": (".mp4", "video/mp4"),
        "image": (".jpg", "image/jpeg"),
        "cover": (".jpg", "image/jpeg"),
        "avatar": (".jpg", "image/jpeg"),
        "music": (".m4a", "audio/mp4"),
    }
    return defaults[role]


def local_asset(path: Path, role: str, metadata_dir: Path, index: int | None = None) -> dict[str, Any]:
    value = {
        "role": role,
        "path": os.path.relpath(path, metadata_dir),
        "size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }
    if index is not None:
        value["index"] = index
    extension, content_type = sniff_extension(path, role)
    value["content_type"] = content_type
    if role in {"video", "music"}:
        value.update({k: v for k, v in probe_media(path).items() if v is not None})
    return value


def atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)


def initial_metadata(
    detail: dict[str, Any],
    *,
    dy_cli_version: str,
    detail_source: str,
    include_raw: bool,
    requested: dict[str, Any],
) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "schema_version": 1,
        **normalize_detail(detail),
        "local_assets": [],
        "acquisition": {
            "tool": "dy-cli-skill/download_with_metadata",
            "dy_cli_version": dy_cli_version,
            "detail_source": detail_source,
            "started_at": utc_now(),
            "updated_at": utc_now(),
            "completed_at": None,
            "status": "in_progress",
            "requested": requested,
            "components": {"detail": "complete"},
            "errors": [],
        },
    }
    if requested["comments"]:
        metadata["comments"] = {
            "requested": requested["comments"],
            "fetched": 0,
            "has_more": None,
            "cursor": None,
            "status": "pending",
            "items": [],
        }
    if include_raw:
        metadata["raw"] = sanitize_raw(detail)
    return metadata


def record_error(metadata: dict[str, Any], component: str, exc: Exception) -> None:
    metadata["acquisition"]["components"][component] = "failed"
    metadata["acquisition"]["errors"].append(
        {
            "component": component,
            "type": type(exc).__name__,
            "message": str(exc),
            "at": utc_now(),
        }
    )


def existing_asset(metadata: dict[str, Any], role: str, index: int | None, directory: Path) -> Path | None:
    base = directory.resolve()
    for item in metadata.get("local_assets", []):
        if item.get("role") != role or item.get("index") != index:
            continue
        relative = Path(str(item.get("path", "")))
        if relative.is_absolute():
            continue
        path = (base / relative).resolve()
        try:
            path.relative_to(base)
        except ValueError:
            continue
        if path.is_file() and path.stat().st_size > 0:
            return path
    return None


def download_asset(
    client: Any,
    url: str,
    *,
    role: str,
    stem: str,
    output_dir: Path,
    metadata: dict[str, Any],
    metadata_path: Path,
    index: int | None,
    force: bool,
) -> Path:
    old_path = existing_asset(metadata, role, index, output_dir)
    if old_path and not force:
        metadata["acquisition"]["components"][role] = "complete"
        metadata["acquisition"]["updated_at"] = utc_now()
        atomic_write_json(metadata_path, metadata)
        return old_path

    label = f"_{index:03d}" if index is not None else ""
    part_path = output_dir / f".{stem}.{role}{label}.part"
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            client.download_file(url, str(part_path))
            if not part_path.is_file() or part_path.stat().st_size == 0:
                raise ArchiveError(f"{role} 下载结果为空")
            break
        except Exception as exc:
            last_error = exc
            part_path.unlink(missing_ok=True)
            if attempt < 2:
                time.sleep(2**attempt)
    else:
        assert last_error is not None
        raise last_error

    extension, _ = sniff_extension(part_path, role)
    suffix = f"_{index:03d}" if index is not None else ""
    final_path = output_dir / f"{stem}.{role}{suffix}{extension}"
    os.replace(part_path, final_path)

    metadata["local_assets"] = [
        item
        for item in metadata.get("local_assets", [])
        if not (item.get("role") == role and item.get("index") == index)
    ]
    metadata["local_assets"].append(local_asset(final_path, role, output_dir, index))
    metadata["acquisition"]["components"][role] = "complete"
    metadata["acquisition"]["updated_at"] = utc_now()
    atomic_write_json(metadata_path, metadata)
    return final_path


def fetch_comments(client: Any, aweme_id: str, requested: int) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    cursor = 0
    has_more = True
    while has_more and len(items) < requested:
        data = client.get_comments(aweme_id, cursor=cursor, count=min(20, requested - len(items)))
        page = data.get("comments") if isinstance(data.get("comments"), list) else []
        items.extend(item for item in page if isinstance(item, dict))
        has_more = bool(data.get("has_more"))
        next_cursor = data.get("cursor")
        if not page or next_cursor in (None, cursor):
            break
        cursor = next_cursor
    return {
        "requested": requested,
        "fetched": len(items),
        "has_more": has_more,
        "cursor": cursor,
        "status": "complete" if len(items) >= requested or not has_more else "partial",
        "items": normalized_comments(items[:requested]),
    }


def archive_one(
    client: Any,
    detail: dict[str, Any],
    output_dir: Path,
    options: argparse.Namespace,
    dy_cli_version: str,
    detail_source: str = "video_detail",
) -> tuple[Path, str]:
    aweme_id = str(detail.get("aweme_id") or "")
    if not aweme_id:
        raise ArchiveError("详情中缺少 aweme_id")

    title = safe_filename(str(detail.get("desc") or "untitled"))
    stem = f"{aweme_id}_{title}"
    metadata_path = output_dir / f"{stem}.metadata.json"
    previous_paths = sorted(output_dir.glob(f"{aweme_id}_*.metadata.json"))
    if previous_paths:
        metadata_path = previous_paths[0]
        stem = metadata_path.name.removesuffix(".metadata.json")
    include_raw = bool(options.include_raw)
    requested = {
        "cover": bool(options.cover or options.archive),
        "avatar": bool(options.avatar or options.archive),
        "music": bool(options.music or options.archive),
        "comments": max(0, options.comments),
    }
    metadata = initial_metadata(
        detail,
        dy_cli_version=dy_cli_version,
        detail_source=detail_source,
        include_raw=include_raw,
        requested=requested,
    )

    if metadata_path.exists() and not options.force:
        try:
            previous = json.loads(metadata_path.read_text(encoding="utf-8"))
            if previous.get("identity", {}).get("aweme_id") == aweme_id:
                metadata["local_assets"] = previous.get("local_assets", [])
        except (OSError, json.JSONDecodeError):
            pass
    output_dir.mkdir(parents=True, exist_ok=True)
    atomic_write_json(metadata_path, metadata)

    urls = extract_asset_urls(detail)
    primary_roles = ["image"] if urls["image"] else ["video"]
    for role in primary_roles:
        if not urls[role]:
            record_error(metadata, role, ArchiveError(f"未找到{role}下载链接"))
            atomic_write_json(metadata_path, metadata)
            continue
        for position, url in enumerate(urls[role], 1):
            index = position if len(urls[role]) > 1 else None
            try:
                download_asset(
                    client,
                    url,
                    role=role,
                    stem=stem,
                    output_dir=output_dir,
                    metadata=metadata,
                    metadata_path=metadata_path,
                    index=index,
                    force=options.force,
                )
            except Exception as exc:
                record_error(metadata, role, exc)
                atomic_write_json(metadata_path, metadata)

    for role in ("cover", "avatar", "music"):
        if not requested[role]:
            metadata["acquisition"]["components"][role] = "skipped"
            continue
        if not urls[role]:
            record_error(metadata, role, ArchiveError(f"未找到{role}下载链接"))
            continue
        try:
            download_asset(
                client,
                urls[role][0],
                role=role,
                stem=stem,
                output_dir=output_dir,
                metadata=metadata,
                metadata_path=metadata_path,
                index=None,
                force=options.force,
            )
        except Exception as exc:
            record_error(metadata, role, exc)

    if requested["comments"]:
        try:
            metadata["comments"] = fetch_comments(client, aweme_id, requested["comments"])
            metadata["acquisition"]["components"]["comments"] = metadata["comments"]["status"]
        except Exception as exc:
            metadata["comments"]["status"] = "failed"
            record_error(metadata, "comments", exc)
    else:
        metadata["acquisition"]["components"]["comments"] = "skipped"

    primary_complete = any(
        item.get("role") in {"video", "image"} for item in metadata.get("local_assets", [])
    )
    degraded = any(
        value in {"failed", "partial"}
        for value in metadata["acquisition"]["components"].values()
    )
    metadata["acquisition"]["status"] = (
        "failed" if not primary_complete else "partial" if degraded else "complete"
    )
    metadata["acquisition"]["completed_at"] = utc_now()
    metadata["acquisition"].pop("updated_at", None)
    atomic_write_json(metadata_path, metadata)
    return metadata_path, metadata["acquisition"]["status"]


def load_dy_cli(allow_unsupported: bool) -> tuple[Any, Any, str]:
    try:
        version = importlib.metadata.version("dy-cli")
        from dy_cli.engines.api_client import DouyinAPIClient
        from dy_cli.utils.index_cache import resolve_id
    except (ImportError, importlib.metadata.PackageNotFoundError) as exc:
        raise ArchiveError("未安装 dy-cli；请先运行 pip install dy-cli==0.2.2") from exc
    if version not in SUPPORTED_DY_CLI_VERSIONS and not allow_unsupported:
        supported = ", ".join(sorted(SUPPORTED_DY_CLI_VERSIONS))
        raise ArchiveError(
            f"当前 dy-cli 版本 {version} 未经验证；支持版本: {supported}。"
            "如需自行承担兼容风险，请加 --allow-unsupported-version"
        )
    return DouyinAPIClient, resolve_id, version


def is_douyin_host(hostname: str | None) -> bool:
    host = (hostname or "").lower().rstrip(".")
    return (
        host == "douyin.com"
        or host.endswith(".douyin.com")
        or host == "iesdouyin.com"
        or host.endswith(".iesdouyin.com")
    )


def extract_douyin_url(target: str) -> str | None:
    for match in DOUYIN_URL_PATTERN.finditer(target):
        url = match.group(0).rstrip(URL_TRAILING_PUNCTUATION)
        try:
            parts = urlsplit(url)
        except ValueError:
            continue
        if parts.scheme in {"http", "https"} and is_douyin_host(parts.hostname):
            return url
    return None


def direct_aweme_id_from_url(url: str) -> str | None:
    match = DIRECT_AWEME_URL_PATTERN.search(urlsplit(url).path)
    return match.group(1) if match else None


def validate_aweme_id(value: Any, *, source: str) -> str:
    aweme_id = str(value or "")
    if not AWEME_ID_PATTERN.fullmatch(aweme_id):
        raise ArchiveError(f"{source} 未解析出有效作品 ID: {aweme_id or '<empty>'}")
    return aweme_id


def resolve_aweme_id(client: Any, resolve_id: Any, target: str) -> str:
    """Resolve one target through a deterministic ID/index/URL decision tree."""
    value = target.strip()
    if AWEME_ID_PATTERN.fullmatch(value):
        return value

    url = extract_douyin_url(value)
    if url:
        direct_id = direct_aweme_id_from_url(url)
        if direct_id:
            return direct_id
        return validate_aweme_id(client.resolve_share_url(url), source="短链接")

    if "://" in value:
        raise ArchiveError("只接受 douyin.com 或 iesdouyin.com 的作品链接")

    resolved = str(resolve_id(value))
    if AWEME_ID_PATTERN.fullmatch(resolved):
        return resolved
    resolved_url = extract_douyin_url(resolved)
    if not resolved_url:
        raise ArchiveError(f"短索引未解析为有效抖音作品: {value}")
    direct_id = direct_aweme_id_from_url(resolved_url)
    if direct_id:
        return direct_id
    return validate_aweme_id(client.resolve_share_url(resolved_url), source="短索引")


def iter_user_posts(client: Any, sec_user_id: str, limit: int) -> Iterable[dict[str, Any]]:
    cursor = 0
    seen: set[str] = set()
    while len(seen) < limit:
        seen_before_page = len(seen)
        data = client.get_user_posts(sec_user_id, max_cursor=cursor, count=min(20, limit - len(seen)))
        posts = data.get("aweme_list") if isinstance(data.get("aweme_list"), list) else []
        if not posts:
            break
        for post in posts:
            if not isinstance(post, dict):
                continue
            aweme_id = str(post.get("aweme_id") or "")
            if aweme_id and aweme_id not in seen:
                seen.add(aweme_id)
                yield post
                if len(seen) >= limit:
                    return
        if len(seen) == seen_before_page:
            break
        if not data.get("has_more"):
            break
        next_cursor = data.get("max_cursor")
        if next_cursor in (None, cursor):
            break
        cursor = next_cursor


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="下载抖音作品并为每个作品生成一个统一的 .metadata.json"
    )
    parser.add_argument("target", help="作品 URL、aweme_id、搜索短索引，或 --user 模式的 sec_user_id")
    parser.add_argument("-o", "--output-dir", default=None, help="输出目录")
    parser.add_argument("--user", action="store_true", help="将 target 视为 sec_user_id 并批量下载")
    parser.add_argument("--limit", type=int, default=20, help="批量下载数量，默认 20")
    parser.add_argument("--account", default=None, help="dy-cli 账号名称")
    parser.add_argument("--archive", action="store_true", help="下载封面、头像和音乐")
    parser.add_argument("--cover", action="store_true", help="下载封面")
    parser.add_argument("--avatar", action="store_true", help="下载作者头像")
    parser.add_argument("--music", action="store_true", help="下载背景音乐")
    parser.add_argument("--include-raw", action="store_true", help="在 metadata.json 中保存脱敏原始详情")
    parser.add_argument("--comments", type=int, default=0, metavar="N", help="尝试下载前 N 条评论")
    parser.add_argument("--force", action="store_true", help="重新下载已有资源")
    parser.add_argument(
        "--allow-unsupported-version",
        action="store_true",
        help="允许使用未经验证的 dy-cli 版本",
    )
    args = parser.parse_args(argv)
    if args.limit < 1:
        parser.error("--limit 必须大于 0")
    if args.comments < 0:
        parser.error("--comments 不能小于 0")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        client_class, resolve_id, dy_cli_version = load_dy_cli(args.allow_unsupported_version)
        if args.output_dir:
            output_dir = Path(args.output_dir).expanduser().resolve()
        else:
            output_dir = Path.home() / "Downloads" / "douyin"
        client = client_class.from_config(args.account)
    except ArchiveError as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 1

    statuses: list[str] = []
    try:
        if args.user:
            posts = list(iter_user_posts(client, args.target, args.limit))
            if not posts:
                raise ArchiveError("未找到用户作品")
            for position, detail in enumerate(posts, 1):
                try:
                    urls = extract_asset_urls(detail)
                    detail_source = "user_posts"
                    if not urls["video"] and not urls["image"]:
                        aweme_id = str(detail.get("aweme_id") or "")
                        if not aweme_id:
                            raise ArchiveError("用户作品条目缺少 aweme_id")
                        detail = client.get_video_detail(aweme_id)
                        detail_source = "video_detail"
                    path, status = archive_one(
                        client,
                        detail,
                        output_dir,
                        args,
                        dy_cli_version,
                        detail_source=detail_source,
                    )
                    statuses.append(status)
                    print(f"[{position}/{len(posts)}] {status}: {path}")
                except Exception as exc:
                    statuses.append("failed")
                    print(f"[{position}/{len(posts)}] failed: {exc}", file=sys.stderr)
        else:
            aweme_id = resolve_aweme_id(client, resolve_id, args.target)
            detail = client.get_video_detail(aweme_id)
            path, status = archive_one(client, detail, output_dir, args, dy_cli_version)
            statuses.append(status)
            print(f"{status}: {path}")
    except Exception as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 1
    finally:
        client.close()

    if any(status == "failed" for status in statuses):
        return 1
    if any(status == "partial" for status in statuses):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
