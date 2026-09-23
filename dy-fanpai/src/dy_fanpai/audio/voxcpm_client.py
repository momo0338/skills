"""audio/voxcpm_client.py — VoxCPM 在线 Space 单段合成客户端。

封装 OpenBMB VoxCPM-Demo 的 Gradio API（实测验证的调用流程）：
1. ``POST /gradio_api/upload`` 上传参考音色，拿 Space 临时路径；
2. ``POST /gradio_api/queue/join`` 提交任务（fn_index=2 即 /generate；
   reference_wav 必须带 ``meta: {"_type": "gradio.FileData"}``，否则 pydantic 校验失败）；
3. ``GET /gradio_api/queue/data?session_hash=`` 轮询 SSE，直到 process_completed；
4. 下载 ``output.data[0].url`` 音频。

已知坑（已在别处踩过，此处固化）：
- FileData 缺 meta 字段 → "The 'meta' field must be explicitly provided"；
- 不带参考音频 → "Ultimate Cloning Mode requires a reference audio clip"；
- SSE 长连接会被 Space 负载均衡断开 → 超时重连继续读；
- 免费 Space CPU 生成约 13s/段，且可能排队/限流 → 单段超时重试。

确定性函数（_build_payload / _extract_audio_url）与网络 IO（synth_one）解耦，
网络 IO 不做单测（需公网），只测确定性部分。
"""

from __future__ import annotations

import json
import os
import subprocess
import time

from ..config import Config

_JOIN_TIMEOUT = 120      # queue/join 响应超时
_POLL_WINDOW = 180       # 单次 SSE 读取窗口（秒），超时重连
_TOTAL_TIMEOUT = 900     # 单段总上限（秒）
_MAX_RETRY = 3           # 上传重试


def _space_url(cfg: Config) -> str:
    return (cfg.voxcpm_space_url or "https://openbmb-voxcpm-demo.hf.space").rstrip("/")


def _upload_ref(ref: str, base: str) -> str:
    """上传参考音色，返回 Space 临时路径。失败重试 _MAX_RETRY 次。"""
    last = ""
    for _ in range(_MAX_RETRY):
        r = subprocess.run(
            ["curl", "-s", "-m", "60", "-X", "POST", f"{base}/gradio_api/upload",
             "-H", "Content-Type: multipart/form-data", "-F", f"files=@{ref}"],
            capture_output=True, text=True, timeout=70,
        )
        out = r.stdout.strip()
        if out.startswith("["):
            return json.loads(out)[0]
        last = out[:120]
        time.sleep(3)
    raise RuntimeError(f"VoxCPM 上传参考音色失败: {last}")


def _build_payload(text: str, ref_path: str, prompt_text: str) -> dict:
    """构造 queue/join 的 data 数组（与 /generate 参数顺序一致）。"""
    filedata = {"path": ref_path, "orig_name": os.path.basename(ref_path),
                "meta": {"_type": "gradio.FileData"}}
    return {
        "data": [text, "", filedata, True, prompt_text, 2.0, False, False],
        "fn_index": 2,
        "session_hash": f"sess_{int(time.time() * 1000)}",
    }


def _extract_audio_url(completed: dict) -> str | None:
    """从 process_completed 帧提取音频下载 URL（确定性）。"""
    out = completed.get("output") or {}
    data = out.get("data") or []
    if data and data[0]:
        return data[0].get("url") or data[0].get("path")
    return None


def synth_one(text: str, dst: str, cfg: Config) -> float:
    """VoxCPM 单段合成：text → dst(mp3)。返回实际时长（秒）。

    成功返回时长；失败抛 RuntimeError（含超时/排队/校验错误信息）。
    """
    ref = cfg.voxcpm_reference_audio
    if not ref or not os.path.exists(ref):
        raise RuntimeError("VoxCPM 参考音色缺失: config.voxcpm_reference_audio")
    prompt_text = cfg.voxcpm_prompt_text or (
        "大家好，欢迎来到这个声音示范，希望你会喜欢这一段简单的朗读。"
    )
    base = _space_url(cfg)

    ref_path = _upload_ref(ref, base)
    payload = _build_payload(text, ref_path, prompt_text)
    sh = payload["session_hash"]

    rj = subprocess.run(
        ["curl", "-s", "-m", str(_JOIN_TIMEOUT), "-X", "POST",
         f"{base}/gradio_api/queue/join",
         "-H", "Content-Type: application/json", "-d", json.dumps(payload)],
        capture_output=True, text=True, timeout=_JOIN_TIMEOUT + 10,
    )
    try:
        json.loads(rj.stdout)  # 只验证是合法 JSON（event_id 不必再用）
    except json.JSONDecodeError:
        raise RuntimeError(f"VoxCPM join 失败: {rj.stdout[:200]}")

    # SSE 轮询：窗口内读数据，超时重连，直到 process_completed / error
    deadline = time.time() + _TOTAL_TIMEOUT
    while time.time() < deadline:
        r = subprocess.run(
            ["curl", "-s", "-N", "-m", str(_POLL_WINDOW),
             f"{base}/gradio_api/queue/data?session_hash={sh}"],
            capture_output=True, text=True, timeout=_POLL_WINDOW + 10,
        )
        for line in r.stdout.splitlines():
            if not line.startswith("data:"):
                continue
            try:
                obj = json.loads(line[5:].strip())
            except json.JSONDecodeError:
                continue
            msg = obj.get("msg")
            if msg == "process_completed":
                url = _extract_audio_url(obj)
                if not url:
                    raise RuntimeError(
                        f"VoxCPM 完成但无音频: {json.dumps(obj, ensure_ascii=False)[:300]}"
                    )
                _download(url, dst, base)
                return _probe_mp3_duration(dst)
            if msg == "error":
                raise RuntimeError(f"VoxCPM 任务错误: {line[:400]}")
        time.sleep(3)
    raise RuntimeError(f"VoxCPM 单段超时({_TOTAL_TIMEOUT}s)")


def _download(url: str, dst: str, base: str) -> None:
    full = url if url.startswith("http") else f"{base}/gradio_api/file={url}"
    subprocess.run(
        ["curl", "-s", "-m", "90", full, "-o", dst],
        check=True, capture_output=True, text=True, timeout=100,
    )
    if not os.path.exists(dst) or os.path.getsize(dst) < 1000:
        raise RuntimeError(f"VoxCPM 音频下载失败/过小: {dst}")


def _ffprobe_bin() -> str:
    """ffprobe 可执行文件：优先 PATH 探测，其次回退 Homebrew。

    勿硬编码 /opt/homebrew/bin/ffprobe —— Linux/CI 下该路径不存在，
    会让 _probe_mp3_duration 直接抛 FileNotFoundError（2026-09-23 修）。
    """
    import shutil

    return shutil.which("ffprobe") or "/opt/homebrew/bin/ffprobe"


def _probe_mp3_duration(path: str) -> float:
    r = subprocess.run(
        [_ffprobe_bin(), "-v", "quiet", "-show_entries",
         "format=duration", "-of", "csv=p=0", path],
        capture_output=True, text=True,
    )
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0
