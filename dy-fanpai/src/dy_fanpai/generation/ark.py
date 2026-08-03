"""generation/ark.py — 火山方舟 Seedance 视频生成后端（WP4，即梦之外的第二条腿）。

忠实复刻原项目 ark_gen.py，仅做冻结期改造：
1. 密钥走 ``cfg.require_key("ark_api_key")``；模型走 ``cfg.ark_gen_model``
   （不再 ``from config import ark_key`` / 硬编码模型）；
2. 确定性函数（body builders / 参数拼装）与网络调用（submit_* / wait_download）解耦；
3. 国内 Ark endpoint 绝不走代理（NO_PROXY）。

业务铁律（必须保留）：
- 和 Seed2.1Pro 反推同一个 ark key，但走【异步任务 API】+ 按 token 计费
  （独立于 CLI 的 5500/月积分池）；
- 口播口型(音频驱动)标准 Seedance 不支持 → 那类段仍走即梦 CLI；
- 多图必须带 role（API 400 明示）；参考图用 reference_image；
- 已验证: text2video + image2video(传真产品图) 均可;9:16/时长/分辨率用文本参数控制。
契约: submit_*(...)->tid ; wait_download(tid,dst)->(size,usage)。
"""

from __future__ import annotations

import base64
import json
import os
import time
import urllib.request

import requests

from ..config import Config

BASE = "https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks"
# 火山国内 endpoint，绝不走代理（原项目硬编码 NO_PROXY，WP1 冻结保留）
NO_PROXY: dict[str, str | None] = {"http": None, "https": None}


def _headers(key: str) -> dict:
    return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}


def _mime_for_image(path: str) -> str:
    p = path.lower()
    if p.endswith(".png"):
        return "image/png"
    if p.endswith(".webp"):
        return "image/webp"
    return "image/jpeg"


def _mime_for_audio(path: str) -> str:
    p = path.lower()
    return "audio/wav" if p.endswith(".wav") else "audio/mpeg"


def image_data_uri(path: str) -> tuple[str, str]:
    """读图 → (mime, base64)。"""
    b64 = base64.b64encode(open(path, "rb").read()).decode()
    return _mime_for_image(path), b64


def audio_data_uri(path: str) -> tuple[str, str]:
    """读音频 → (mime, base64)。"""
    b64 = base64.b64encode(open(path, "rb").read()).decode()
    return _mime_for_audio(path), b64


def _text_param(prompt: str, duration: int, resolution: str, ratio: str) -> str:
    return f"{prompt} --resolution {resolution} --duration {duration} --ratio {ratio}"


def build_i2v_body(b64: str, mime: str, prompt: str, duration: int = 5,
                   resolution: str = "720p", ratio: str = "9:16", model: str = "") -> dict:
    """image2video 请求体（确定性）：首帧真图 + 文本指令。

    文本用 ``--resolution/--duration/--ratio`` 控制 9:16/时长/分辨率。
    """
    text = _text_param(prompt, duration, resolution, ratio)
    return {"model": model, "content": [
        {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
        {"type": "text", "text": text},
    ]}


def build_mm_body(img_items: list[tuple[str, str]], audio_item: tuple[str, str] | None,
                  prompt: str, duration: int = 5, resolution: str = "720p", ratio: str = "9:16",
                  model: str = "") -> dict:
    """多模态参考(Seedance 2.0):多张锚图(带 role=reference_image) + 段配音音频驱动口型 + 文本。

    img_items: [(mime, b64), ...]；audio_item: (mime, b64) | None。
    """
    content: list[dict] = []
    for mime, b64 in img_items:
        content.append({"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}, "role": "reference_image"})
    if audio_item:
        amime, ab64 = audio_item
        content.append({"type": "audio_url", "role": "reference_audio",
                        "audio_url": {"url": f"data:{amime};base64,{ab64}"}})
    text = _text_param(prompt, duration, resolution, ratio)
    content.append({"type": "text", "text": text})
    return {"model": model, "content": content}


def build_t2v_body(prompt: str, duration: int = 5, resolution: str = "720p",
                  ratio: str = "9:16", model: str = "") -> dict:
    """text2video 请求体（确定性）。"""
    text = _text_param(prompt, duration, resolution, ratio)
    return {"model": model, "content": [{"type": "text", "text": text}]}


def _post_body(body: dict, key: str, timeout: int) -> str:
    r = requests.post(BASE, headers=_headers(key), json=body, proxies=NO_PROXY,  # pyright: ignore[reportArgumentType]
                       timeout=timeout)
    r.raise_for_status()
    return r.json()["id"]


def submit_i2v(image_path: str, prompt: str, cfg: Config, duration: int = 5,
               resolution: str = "720p", ratio: str = "9:16") -> str:
    """image2video：传首帧真图 + 文本指令。返回 task id。"""
    mime, b64 = image_data_uri(image_path)
    body = build_i2v_body(b64, mime, prompt, duration, resolution, ratio, cfg.ark_gen_model)
    return _post_body(body, cfg.require_key("ark_api_key"), 60)


def submit_mm(image_paths: list[str], audio_path: str | None, prompt: str, cfg: Config,
              duration: int = 5, resolution: str = "720p", ratio: str = "9:16") -> str:
    """多锚图 + 段配音音频驱动口型 + 文本。返回 task id。"""
    img_items = [image_data_uri(p) for p in image_paths]
    audio_item = audio_data_uri(audio_path) if audio_path else None
    body = build_mm_body(img_items, audio_item, prompt, duration, resolution, ratio, cfg.ark_gen_model)
    return _post_body(body, cfg.require_key("ark_api_key"), 120)


def submit_t2v(prompt: str, cfg: Config, duration: int = 5, resolution: str = "720p",
               ratio: str = "9:16") -> str:
    body = build_t2v_body(prompt, duration, resolution, ratio, cfg.ark_gen_model)
    return _post_body(body, cfg.require_key("ark_api_key"), 60)


def wait_download(tid: str, dst: str, cfg: Config, tries: int = 40, gap: int = 12) -> tuple[int | str | None, dict]:
    """轮询 succeeded → 从 video_url 稳健下载(重试+完整性校验)。返回 (size|fail|None, usage)。"""
    key = cfg.require_key("ark_api_key")
    for _ in range(tries):
        R = requests.get(f"{BASE}/{tid}", headers=_headers(key), proxies=NO_PROXY,  # pyright: ignore[reportArgumentType]
                         timeout=30).json()
        st = R.get("status")
        if st == "succeeded":
            url = R["content"]["video_url"]
            for i in range(4):
                try:
                    urllib.request.urlretrieve(url, dst)  # TOS URL 公网可直连,不走代理
                    if os.path.getsize(dst) > 10240:
                        return os.path.getsize(dst), R.get("usage", {})
                except Exception:  # noqa: BLE001
                    pass
                time.sleep(3 * (i + 1))
            raise RuntimeError("下载失败")
        if st == "failed":
            return f"FAIL: {json.dumps(R.get('error', R), ensure_ascii=False)[:150]}", {}
        time.sleep(gap)
    return None, {}
