"""audio/voicebox_client.py — Voicebox (Qwen3-TTS) 本地 REST 客户端。

Voicebox 是本地运行的 Qwen3-TTS 语音克隆服务（OpenAI 风格 REST API，
默认 http://127.0.0.1:17493）。本模块封装合成一条语音的完整流程：

1. ``ensure_profile(cfg)`` —— 校验/复用克隆音色 profile（按配置的
   voicebox_profile_id；不存在时自动创建 + 上传参考样本）；
2. ``generate(text, dst, cfg)`` —— POST /generate → 轮询 /generate/{id}/status
   （SSE 流）→ 完成后 GET /audio/{id} 保存 wav，返回实际时长。

已知工程约束（2026-08-05 实测固化）：
- 服务重启后模型不自动加载，需 POST /models/load（客户端检测 health 后处理）；
- 状态接口返回 text/event-stream（``data: {...}`` 帧），需剥掉 ``data: `` 前缀；
- 参考样本 multipart 上传：字段 ``file`` + ``reference_text``；
- v0.5.0 曾有 MLX ``Stream(gpu,1)`` 线程 bug 与 Metal GPU 崩溃（重启后消失，
  生成连续 13 段稳定）；客户端对单段失败抛异常，由上层 synthesize 单段降级。

确定性函数（_strip_sse / _parse_status / _build_generate_payload /
_generation_to_status）与网络 IO（ensure_profile / generate）解耦，便于离线单测。
"""

from __future__ import annotations

import json
import os
import subprocess
import time
import urllib.error
import urllib.request

from ..config import Config

# 单段生成总超时（秒）：Qwen3-TTS 1.7B 单段 15~50s，留足余量
_GEN_TIMEOUT = 300
# 状态轮询间隔（秒）
_POLL_INTERVAL = 3
# 服务启动/模型加载等待（秒）
_BOOT_TIMEOUT = 120


def _base(cfg: Config) -> str:
    return (cfg.voicebox_base_url or "http://127.0.0.1:17493").rstrip("/")


def _get_json(cfg: Config, path: str, timeout: int = 20) -> dict:
    with urllib.request.urlopen(_base(cfg) + path, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def _post_json(cfg: Config, path: str, payload: dict, timeout: int = 60) -> dict:
    req = urllib.request.Request(
        _base(cfg) + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def _strip_sse(text: str) -> str:
    """剥掉 SSE 帧的 ``data: `` 前缀（状态接口返回 text/event-stream）。"""
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("data:"):
            return line[5:].strip()
    return text.strip()


def _parse_status(text: str) -> dict:
    """解析 /generate/{id}/status 响应 → {status, duration?, error?}（确定性）。"""
    try:
        obj = json.loads(_strip_sse(text))
    except json.JSONDecodeError:
        return {"status": "unknown"}
    return {
        "status": obj.get("status", "unknown"),
        "duration": obj.get("duration"),
        "error": obj.get("error"),
    }


def _build_generate_payload(text: str, profile_id: str, cfg: Config) -> dict:
    """构造 POST /generate 请求体（确定性）。"""
    return {
        "profile_id": profile_id,
        "text": text,
        "language": cfg.voicebox_language or "zh",
        "model_size": cfg.voicebox_model_size or "1.7B",
        "normalize": True,
        "instruct": cfg.voicebox_instruct or None,
    }


def _generation_to_status(gen: dict) -> dict:
    """POST /generate 返回体 → 状态字典（确定性）。"""
    return {
        "status": gen.get("status", "unknown"),
        "duration": gen.get("duration"),
        "error": gen.get("error"),
        "id": gen.get("id"),
    }


# ---------------------------------------------------------------------------
# 网络 IO（不在单测范围）
# ---------------------------------------------------------------------------
def ensure_model_loaded(cfg: Config) -> None:
    """等待服务健康；若模型未加载则触发 /models/load（重启后需手动加载）。"""
    deadline = time.time() + _BOOT_TIMEOUT
    while time.time() < deadline:
        try:
            h = _get_json(cfg, "/health", timeout=5)
            if h.get("model_loaded"):
                return
            # 模型未加载 → 触发加载
            try:
                _post_json(cfg, "/models/load", {"model_name": cfg.voicebox_model_size or "1.7B"},
                           timeout=30)
            except Exception:
                pass
        except Exception:
            pass
        time.sleep(5)
    raise RuntimeError(
        f"voicebox 服务未就绪（{_base(cfg)}/health 无响应或模型加载超时）"
    )


def find_profile_id(cfg: Config) -> str | None:
    """按配置 id 或名字找已存在的 profile；找不到返回 None（确定性 + 轻 IO）。

    - 优先 ``cfg.voicebox_profile_id``（精确 id 或名字）；
    - 未配置时回退按 ``cfg.voicebox_profile_name`` 查找（2026-08-05 修复：
      之前只在 id 配置非空时查找，未配置时每段都重复 create_profile → S2 起 400）。
    """
    want = cfg.voicebox_profile_id
    want_name = cfg.voicebox_profile_name or "dyfanpai-voice"
    try:
        profiles = _get_json(cfg, "/profiles", timeout=15)
    except Exception:
        return None
    for p in profiles or []:
        if want and (p.get("id") == want or p.get("name") == want):
            return p["id"]
        if not want and p.get("name") == want_name:
            return p["id"]
    return None


def create_profile_with_sample(cfg: Config) -> str:
    """创建克隆 profile 并上传参考样本，返回 profile_id。

    需要 cfg.voicebox_profile_name / voicebox_reference_audio /
    voicebox_reference_text。参考音频必须存在，否则 RuntimeError。
    """
    name = cfg.voicebox_profile_name or "dyfanpai-voice"
    ref = cfg.voicebox_reference_audio
    ref_text = cfg.voicebox_reference_text or ""
    if not ref or not os.path.exists(ref):
        raise RuntimeError(
            f"voicebox 克隆需要参考音频: config.voicebox_reference_audio={ref!r} 不存在"
        )
    prof = _post_json(cfg, "/profiles", {
        "name": name,
        "language": cfg.voicebox_language or "zh",
        "voice_type": "cloned",
        "default_engine": "qwen",
    }, timeout=30)
    pid = prof["id"]
    # multipart 上传参考样本
    cmd = ["curl", "-s", "-m", "120", "-X", "POST",
           f"{_base(cfg)}/profiles/{pid}/samples",
           "-F", f"file=@{ref}",
           "-F", f"reference_text={ref_text}"]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=140)
    if r.returncode != 0 or not r.stdout.strip().startswith("{"):
        raise RuntimeError(f"voicebox 上传参考样本失败: {r.stdout[:200]}")
    return pid


def generate(text: str, dst: str, cfg: Config) -> float:
    """合成一条语音：text → dst(wav)，返回实际时长（秒）。失败抛 RuntimeError。"""
    ensure_model_loaded(cfg)

    pid = find_profile_id(cfg)
    if not pid:
        pid = create_profile_with_sample(cfg)

    gen = _post_json(cfg, "/generate", _build_generate_payload(text, pid, cfg), timeout=60)
    gid = gen.get("id")
    if not gid:
        raise RuntimeError(f"voicebox /generate 未返回 id: {gen}")

    # 轮询状态（SSE 帧）
    deadline = time.time() + _GEN_TIMEOUT
    while time.time() < deadline:
        time.sleep(_POLL_INTERVAL)
        try:
            with urllib.request.urlopen(
                f"{_base(cfg)}/generate/{gid}/status", timeout=15
            ) as r:
                raw = r.read().decode("utf-8", "replace")
        except urllib.error.URLError as e:
            raise RuntimeError(f"voicebox 状态查询失败: {e}")
        st = _parse_status(raw)
        if st["status"] == "completed":
            break
        if st["status"] == "failed":
            raise RuntimeError(f"voicebox 生成失败: {st.get('error')}")
        if st["status"] == "unknown":
            continue
    else:
        raise RuntimeError(f"voicebox 生成超时（{_GEN_TIMEOUT}s）")

    # 取音频
    try:
        with urllib.request.urlopen(f"{_base(cfg)}/audio/{gid}", timeout=60) as r:
            data = r.read()
    except urllib.error.URLError as e:
        raise RuntimeError(f"voicebox 音频获取失败: {e}")
    if len(data) < 1000 or data[:4] != b"RIFF":
        raise RuntimeError(f"voicebox 音频异常（{len(data)}B, 非 WAV）")
    with open(dst, "wb") as f:
        f.write(data)

    dur = st.get("duration") or 0.0
    return float(dur)
