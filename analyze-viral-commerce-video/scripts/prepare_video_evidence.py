#!/usr/bin/env python3
"""Prepare a reproducible evidence bundle for commerce-video analysis."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont, ImageOps


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="生成媒体信息、带时间戳抽帧、联络表、场景候选、音量诊断和正式交付骨架。"
    )
    parser.add_argument("video", type=Path, help="本地视频绝对或相对路径")
    parser.add_argument("--output-dir", required=True, type=Path, help="分析输出目录")
    parser.add_argument("--metadata", type=Path, help="同作品元数据 JSON")
    parser.add_argument(
        "--interval",
        type=float,
        default=0.5,
        help="抽帧间隔秒数，默认 0.5",
    )
    parser.add_argument(
        "--frame-width",
        type=int,
        default=360,
        help="证据帧宽度，默认 360",
    )
    parser.add_argument(
        "--sheet-columns",
        type=int,
        default=6,
        help="联络表列数，默认 6",
    )
    parser.add_argument(
        "--scene-threshold",
        type=float,
        default=0.20,
        help="场景变化候选阈值，默认 0.20",
    )
    parser.add_argument(
        "--asr-model",
        help="可选 Whisper 模型，例如 base；不提供时跳过 ASR",
    )
    parser.add_argument("--language", default="zh", help="Whisper 语言，默认 zh")
    return parser.parse_args()


def require_program(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise RuntimeError(f"缺少依赖：{name}")
    return path


def run(command: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        check=check,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def tool_version(program: str) -> str:
    completed = run([program, "-version"], check=False)
    first_line = (completed.stdout or completed.stderr).splitlines()
    return first_line[0] if first_line else "unknown"


def parse_rate(value: str | None) -> float | None:
    if not value or value == "0/0":
        return None
    if "/" in value:
        numerator, denominator = value.split("/", 1)
        if float(denominator) == 0:
            return None
        return float(numerator) / float(denominator)
    return float(value)


def duration_from_probe(probe: dict[str, Any]) -> float:
    value = probe.get("format", {}).get("duration")
    if value is not None:
        return float(value)
    durations = [
        float(stream["duration"])
        for stream in probe.get("streams", [])
        if stream.get("duration") is not None
    ]
    if not durations:
        raise RuntimeError("ffprobe 未返回可用时长")
    return max(durations)


def validate_metadata_for_video(
    metadata_path: Path,
    video_hash: str,
) -> dict[str, Any]:
    payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError("元数据必须是 JSON 对象")
    assets = payload.get("local_assets")
    if not isinstance(assets, list):
        raise RuntimeError("元数据缺少 local_assets，无法核对视频")
    video_assets = [
        item
        for item in assets
        if isinstance(item, dict) and item.get("role") == "video"
    ]
    matched = next(
        (
            item
            for item in video_assets
            if str(item.get("sha256") or "").lower() == video_hash.lower()
        ),
        None,
    )
    if not matched:
        raise RuntimeError("元数据中的视频 SHA-256 与输入视频不一致")
    identity = payload.get("identity")
    identity = identity if isinstance(identity, dict) else {}
    return {
        "aweme_id": identity.get("aweme_id"),
        "canonical_url": identity.get("canonical_url"),
        "matched_asset_path": matched.get("path"),
        "matched_sha256": matched.get("sha256"),
    }


def requested_parameters(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "interval": args.interval,
        "frame_width": args.frame_width,
        "sheet_columns": args.sheet_columns,
        "scene_threshold": args.scene_threshold,
        "asr_model": args.asr_model,
        "language": args.language if args.asr_model else None,
    }


def required_output_paths(output_dir: Path, *, require_asr: bool) -> list[Path]:
    paths = [
        output_dir / "evidence" / "media-info.json",
        output_dir / "evidence" / "contact-sheet.jpg",
        output_dir / "evidence" / "scene-changes.json",
        output_dir / "evidence" / "audio-diagnostics.json",
        output_dir / "deliverables" / "breakdown.json",
        output_dir / "deliverables" / "breakdown.md",
        output_dir / "deliverables" / "transcript-reviewed.md",
    ]
    if require_asr:
        paths.append(output_dir / "evidence" / "asr-raw.json")
    return paths


def existing_output_state(
    output_dir: Path,
    video_hash: str,
    parameters: dict[str, Any],
) -> str:
    """Return new, reuse, or rebuild without mutating the output directory."""
    if not output_dir.exists():
        return "new"
    if not output_dir.is_dir():
        raise RuntimeError("--output-dir 已存在且不是目录")
    if not any(output_dir.iterdir()):
        return "new"

    manifest_path = output_dir / "evidence" / "evidence-manifest.json"
    if not manifest_path.is_file():
        raise RuntimeError(
            "输出目录非空且没有可验证清单。请使用新目录，避免覆盖未知文件。"
        )
    existing = json.loads(manifest_path.read_text(encoding="utf-8"))
    if existing.get("source", {}).get("sha256") != video_hash:
        raise RuntimeError(
            "输出目录已有另一视频的证据清单。请使用新的 --output-dir，避免覆盖证据。"
        )
    require_asr = bool(parameters.get("asr_model"))
    complete = (
        existing.get("status") == "complete"
        and existing.get("parameters") == parameters
        and all(path.is_file() for path in required_output_paths(output_dir, require_asr=require_asr))
        and any((output_dir / "evidence" / "frames").glob("frame_*.jpg"))
    )
    if require_asr:
        complete = complete and existing.get("components", {}).get("asr") == "complete"
    return "reuse" if complete else "rebuild"


def publish_output(staging_dir: Path, output_dir: Path) -> None:
    """Atomically swap a completed staging directory into the requested path."""
    backup: Path | None = None
    if output_dir.exists():
        if any(output_dir.iterdir()):
            backup = output_dir.parent / f".{output_dir.name}.backup-{uuid.uuid4().hex}"
            output_dir.rename(backup)
        else:
            output_dir.rmdir()
    try:
        staging_dir.rename(output_dir)
    except Exception:
        if backup and backup.exists() and not output_dir.exists():
            backup.rename(output_dir)
        raise
    if backup and backup.exists():
        try:
            shutil.rmtree(backup)
        except OSError as error:
            print(f"警告：旧证据包备份未清理：{backup}（{error}）", file=sys.stderr)


def evidence_bundle_status(
    scene_status: str,
    audio_status: str,
    asr_status: str,
    *,
    asr_requested: bool,
) -> str:
    degraded = scene_status != "complete" or audio_status == "failed"
    if asr_requested and asr_status != "complete":
        degraded = True
    return "partial" if degraded else "complete"


def extract_frames(
    ffmpeg: str,
    video: Path,
    frames_dir: Path,
    interval: float,
    frame_width: int,
) -> list[tuple[Path, float]]:
    fps = 1.0 / interval
    pattern = frames_dir / "raw_%06d.jpg"
    run(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(video),
            "-vf",
            f"fps={fps:.8f},scale={frame_width}:-2",
            "-q:v",
            "2",
            str(pattern),
        ]
    )
    raw_frames = sorted(frames_dir.glob("raw_*.jpg"))
    if not raw_frames:
        raise RuntimeError("没有生成证据帧")
    renamed: list[tuple[Path, float]] = []
    for index, raw_path in enumerate(raw_frames):
        seconds = index * interval
        target = frames_dir / f"frame_{round(seconds * 1000):09d}ms.jpg"
        raw_path.rename(target)
        renamed.append((target, seconds))
    return renamed


def format_timestamp(seconds: float) -> str:
    milliseconds = int(round(seconds * 1000))
    minutes, remainder = divmod(milliseconds, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{minutes:02d}:{secs:02d}.{millis:03d}"


def build_contact_sheet(
    frames: list[tuple[Path, float]],
    target: Path,
    columns: int,
    cell_width: int = 240,
) -> None:
    font = ImageFont.load_default()
    prepared: list[tuple[Image.Image, str]] = []
    max_image_height = 0
    for path, seconds in frames:
        with Image.open(path) as source:
            image = ImageOps.exif_transpose(source).convert("RGB")
            image.thumbnail((cell_width, 520), Image.Resampling.LANCZOS)
            prepared.append((image.copy(), format_timestamp(seconds)))
            max_image_height = max(max_image_height, image.height)

    label_height = 22
    padding = 4
    cell_height = max_image_height + label_height
    rows = math.ceil(len(prepared) / columns)
    sheet = Image.new(
        "RGB",
        (columns * (cell_width + padding) - padding, rows * (cell_height + padding) - padding),
        "white",
    )
    draw = ImageDraw.Draw(sheet)
    for index, (image, label) in enumerate(prepared):
        row, column = divmod(index, columns)
        x = column * (cell_width + padding)
        y = row * (cell_height + padding)
        image_x = x + (cell_width - image.width) // 2
        sheet.paste(image, (image_x, y))
        label_y = y + max_image_height
        draw.rectangle((x, label_y, x + cell_width, label_y + label_height), fill="black")
        draw.text((x + 6, label_y + 5), label, fill="white", font=font)
    sheet.save(target, quality=90, optimize=True)


def detect_scene_changes(
    ffmpeg: str,
    video: Path,
    threshold: float,
) -> tuple[list[dict[str, float]], str]:
    filter_expression = f"select=gt(scene\\,{threshold}),showinfo"
    completed = run(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "info",
            "-i",
            str(video),
            "-vf",
            filter_expression,
            "-an",
            "-f",
            "null",
            "-",
        ],
        check=False,
    )
    matches = re.findall(r"pts_time:([0-9.]+)", completed.stderr)
    candidates = [{"time_seconds": float(value)} for value in matches]
    status = "complete" if completed.returncode == 0 else "failed"
    return candidates, status


def audio_diagnostics(
    ffmpeg: str,
    probe: dict[str, Any],
    video: Path,
) -> dict[str, Any]:
    audio_streams = [
        stream for stream in probe.get("streams", []) if stream.get("codec_type") == "audio"
    ]
    diagnostics: dict[str, Any] = {
        "audio_stream_present": bool(audio_streams),
        "streams": audio_streams,
        "analysis_scope": "技术音轨与音量检测，不等于实际听取音乐、音效、说话人或语气",
    }
    if not audio_streams:
        diagnostics["status"] = "unavailable"
        return diagnostics
    completed = run(
        [
            ffmpeg,
            "-hide_banner",
            "-i",
            str(video),
            "-af",
            "volumedetect",
            "-vn",
            "-f",
            "null",
            "-",
        ],
        check=False,
    )
    mean_match = re.search(r"mean_volume:\s*(-?[0-9.]+) dB", completed.stderr)
    max_match = re.search(r"max_volume:\s*(-?[0-9.]+) dB", completed.stderr)
    diagnostics.update(
        {
            "status": "complete" if completed.returncode == 0 else "failed",
            "mean_volume_db": float(mean_match.group(1)) if mean_match else None,
            "max_volume_db": float(max_match.group(1)) if max_match else None,
        }
    )
    return diagnostics


def run_asr(
    whisper: str | None,
    video: Path,
    evidence_dir: Path,
    model: str | None,
    language: str,
) -> dict[str, Any]:
    if not model:
        return {"status": "skipped", "reason": "未提供 --asr-model"}
    if not whisper:
        return {"status": "unavailable", "reason": "whisper 命令不可用"}
    completed = run(
        [
            whisper,
            str(video),
            "--model",
            model,
            "--language",
            language,
            "--output_format",
            "json",
            "--output_dir",
            str(evidence_dir),
            "--fp16",
            "False",
            "--verbose",
            "False",
        ],
        check=False,
    )
    generated = evidence_dir / f"{video.stem}.json"
    target = evidence_dir / "asr-raw.json"
    if completed.returncode == 0 and generated.exists():
        generated.rename(target)
        return {
            "status": "complete",
            "model": model,
            "language": language,
            "path": str(target),
            "reviewed": False,
        }
    return {
        "status": "failed",
        "model": model,
        "language": language,
        "error_tail": completed.stderr[-1000:],
    }


def create_delivery_skeletons(
    deliverables_dir: Path,
    video: Path,
    metadata: Path | None,
    interval: float,
    audio_present: bool,
) -> None:
    skill_root = Path(__file__).resolve().parents[1]
    template = skill_root / "assets" / "breakdown-template.md"
    shutil.copyfile(template, deliverables_dir / "breakdown.md")
    (deliverables_dir / "transcript-reviewed.md").write_text(
        "# 经复核转写\n\n> 尚未复核。不要把 evidence/asr-raw.json 直接作为正式转写。\n",
        encoding="utf-8",
    )
    timing_precision = (
        "half_second_approx"
        if abs(interval - 0.5) < 1e-9
        else "one_second_approx"
        if abs(interval - 1.0) < 1e-9
        else "unknown"
    )
    skeleton = {
        "schema_version": "1.0",
        "source": {
            "platform": None,
            "video_id": None,
            "canonical_url": None,
            "local_video": str(video),
            "metadata_file": str(metadata) if metadata else None,
        },
        "evidence_coverage": {
            "video": "unchecked",
            "audio": "stream_only" if audio_present else "unavailable",
            "text": "unchecked",
            "timing_precision": timing_precision,
        },
        "segments": [],
        "claims": [],
        "mechanism": {
            "one_sentence": "",
            "attention": "",
            "understanding": "",
            "proof": "",
            "trust": "",
            "conversion": "",
        },
        "decisions": {"adopt": [], "conditional": [], "avoid": []},
        "experiment": {
            "variable": "",
            "controls": [],
            "primary_metric": "",
            "success_rule": "",
            "window": "",
        },
        "limitations": ["这是自动生成的正式交付骨架，所有内容仍需人工复核。"],
    }
    write_json(deliverables_dir / "breakdown.json", skeleton)


def main() -> int:
    args = parse_args()
    if args.interval <= 0:
        raise RuntimeError("--interval 必须大于 0")
    if args.frame_width < 120:
        raise RuntimeError("--frame-width 不能小于 120")
    if args.sheet_columns < 1:
        raise RuntimeError("--sheet-columns 必须大于 0")
    if not 0 < args.scene_threshold < 1:
        raise RuntimeError("--scene-threshold 必须在 0 和 1 之间")

    video = args.video.expanduser().resolve()
    output_dir = args.output_dir.expanduser().resolve()
    metadata = args.metadata.expanduser().resolve() if args.metadata else None
    if not video.is_file():
        raise RuntimeError(f"视频不存在：{video}")
    if metadata and not metadata.is_file():
        raise RuntimeError(f"元数据不存在：{metadata}")

    ffmpeg = require_program("ffmpeg")
    ffprobe = require_program("ffprobe")
    whisper = shutil.which("whisper")
    video_hash = sha256_file(video)
    metadata_identity = (
        validate_metadata_for_video(metadata, video_hash)
        if metadata
        else None
    )
    parameters = requested_parameters(args)
    output_state = existing_output_state(output_dir, video_hash, parameters)
    if output_state == "reuse":
        print(f"证据包已完整且视频哈希与参数一致：{output_dir}")
        return 0

    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging_dir = Path(
        tempfile.mkdtemp(
            prefix=f".{output_dir.name}.staging-",
            dir=output_dir.parent,
        )
    )
    try:
        evidence_dir = staging_dir / "evidence"
        frames_dir = evidence_dir / "frames"
        deliverables_dir = staging_dir / "deliverables"
        frames_dir.mkdir(parents=True)
        deliverables_dir.mkdir(parents=True)

        probe_completed = run(
            [
                ffprobe,
                "-v",
                "error",
                "-show_format",
                "-show_streams",
                "-of",
                "json",
                str(video),
            ]
        )
        probe = json.loads(probe_completed.stdout)
        write_json(evidence_dir / "media-info.json", probe)

        frames = extract_frames(ffmpeg, video, frames_dir, args.interval, args.frame_width)
        build_contact_sheet(
            frames,
            evidence_dir / "contact-sheet.jpg",
            args.sheet_columns,
        )

        scene_candidates, scene_status = detect_scene_changes(
            ffmpeg,
            video,
            args.scene_threshold,
        )
        write_json(
            evidence_dir / "scene-changes.json",
            {
                "status": scene_status,
                "threshold": args.scene_threshold,
                "candidates": scene_candidates,
                "reviewed": False,
                "limitation": "候选时间必须人工区分硬切、闪光、遮挡和大面积动作",
            },
        )

        audio = audio_diagnostics(ffmpeg, probe, video)
        write_json(evidence_dir / "audio-diagnostics.json", audio)
        asr = run_asr(whisper, video, evidence_dir, args.asr_model, args.language)
        if asr.get("path"):
            asr["path"] = "evidence/asr-raw.json"
        create_delivery_skeletons(
            deliverables_dir,
            video,
            metadata,
            args.interval,
            bool(audio.get("audio_stream_present")),
        )

        frame_rate = None
        for stream in probe.get("streams", []):
            if stream.get("codec_type") == "video":
                frame_rate = parse_rate(stream.get("avg_frame_rate"))
                break
        status = evidence_bundle_status(
            scene_status,
            str(audio.get("status")),
            str(asr.get("status")),
            asr_requested=bool(args.asr_model),
        )
        components = {
            "media_probe": "complete",
            "frames": "complete",
            "contact_sheet": "complete",
            "scene_detection": scene_status,
            "audio_diagnostics": audio.get("status"),
            "asr": asr.get("status"),
            "delivery_skeleton": "complete",
        }
        manifest = {
            "schema_version": "1.0",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": status,
            "components": components,
            "parameters": parameters,
            "source": {
                "video": str(video),
                "sha256": video_hash,
                "size_bytes": video.stat().st_size,
                "metadata": str(metadata) if metadata else None,
                "metadata_identity": metadata_identity,
                "duration_seconds": duration_from_probe(probe),
                "average_frame_rate": frame_rate,
            },
            "tools": {
                "ffmpeg": tool_version(ffmpeg),
                "ffprobe": tool_version(ffprobe),
                "pillow": Image.__version__,
                "whisper": "available" if whisper else "unavailable",
            },
            "outputs": {
                "frame_interval_seconds": args.interval,
                "frame_count": len(frames),
                "contact_sheet": "evidence/contact-sheet.jpg",
                "scene_detection": scene_status,
                "scene_candidate_count": len(scene_candidates),
                "audio_diagnostics": audio.get("status"),
                "asr": asr,
                "delivery_skeleton": "deliverables/breakdown.json",
            },
            "review_required": [
                "完整播放视频",
                "人工确认场景变化候选",
                "实际听取人声、音乐和音效",
                "复核字幕与自动转写",
                "核验数字、等级、材料和功效宣称",
                "填写正式报告和单变量实验",
            ],
        }
        write_json(evidence_dir / "evidence-manifest.json", manifest)
        publish_output(staging_dir, output_dir)
        print(f"证据包已生成：{output_dir}")
        print(f"证据包状态：{status}")
        print(f"带时间戳联络表：{output_dir / 'evidence' / 'contact-sheet.jpg'}")
        print(f"正式交付目录：{output_dir / 'deliverables'}")
        return 2 if status == "partial" else 0
    finally:
        if staging_dir.exists():
            shutil.rmtree(staging_dir, ignore_errors=True)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (RuntimeError, subprocess.CalledProcessError, json.JSONDecodeError) as error:
        print(f"错误：{error}", file=sys.stderr)
        sys.exit(1)
