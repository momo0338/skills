"""generation/minimax.py — MiniMax H3 视频生成后端（即梦/Ark/小云雀之外的第四后端）。

接入依据（2026-08 官方文档核实）：
- 创建：`POST {base}/v2/video_generation`，Bearer 认证，响应 `{"task_id": ...}`；
- 查询：`GET {base}/v2/query/video_generation/{task_id}`，`task.status` 取
  queued/running/succeeded/failed/cancelled，成功时 `task.content.url` 为视频地址；
- 模型 `MiniMax-H3`：多模态 content 数组（text/image_url/video_url/audio_url），
  支持文生/图生（首帧/首尾帧）/多模态参考（reference_image/video/audio）三种场景；
- 媒体支持 Base64 Data URL（本地文件无需公网 URL）；请求体 ≤64MB（压缩 clip 远低于）；
- 音频参考 `reference_audio` 用于口播段口型驱动（能力未实测，experimental 标记）。

业务铁律（沿用项目纪律）：
- 人物口播(mm) 默认仍走即梦（口型验证过）；本后端 i2v 段可切（`--i2v-backend minimax`），
  mm 段默认不接管——除非口型实测通过后放开（显式设计变更）。
- 下载复用 media.download.robust_download（坏流重下）。
- 国内端点直连，不走代理。

契约（与 dreamina/ark/xyq 一致）：
- submit_i2v/submit_mm/submit_t2v(...) -> task_id
- wait_download(task_id, dst, cfg) -> (size|fail|None, usage)
"""

from __future__ import annotations

import base64
import json
import time

import requests

from ..config import Config
from ..media.download import robust_download

NO_PROXY: dict[str, str | None] = {"http": None, "https": None}

# 模型与默认参数（config 可覆盖）
DEFAULT_MODEL = "MiniMax-H3"
RESOLUTION = "768P"
RATIO = "9:16"


# ---------------------------------------------------------------------------
# 确定性构造
# ---------------------------------------------------------------------------
def _data_uri(path: str, mime: str) -> str:
    b64 = base64.b64encode(open(path, "rb").read()).decode()
    return f"data:{mime};base64,{b64}"


def _mime_image(path: str) -> str:
    p = path.lower()
    if p.endswith(".png"):
        return "image/png"
    if p.endswith(".webp"):
        return "image/webp"
    return "image/jpeg"


def _mime_audio(path: str) -> str:
    return "audio/wav" if path.lower().endswith(".wav") else "audio/mpeg"


def build_submit_body(
    prompt: str,
    duration: int,
    *,
    images: list[str] | None = None,
    audio: str | None = None,
    first_frame: str | None = None,
    resolution: str = RESOLUTION,
    ratio: str = RATIO,
    model: str = DEFAULT_MODEL,
) -> dict:
    """构造 MiniMax 创建任务请求体（确定性）。

    场景路由（与 content 组合对应官方文档）：
    - first_frame 给定 → 图生视频-首帧（i2v）：1 张 `role=first_frame`；
    - images+audio 给定 → 多模态参考（mm 口播）：参考图 `reference_image` +
      参考音频 `reference_audio`；
    - 仅 images → 多模态参考（纯图参考,不带音频）；
    - 均无 → 文生视频（t2v）。
    """
    content: list[dict] = []
    if first_frame:
        content.append({"type": "image_url", "role": "first_frame",
                        "image_url": {"url": _data_uri(first_frame, _mime_image(first_frame))}})
    for p in images or []:
        content.append({"type": "image_url", "role": "reference_image",
                        "image_url": {"url": _data_uri(p, _mime_image(p))}})
    if audio:
        content.append({"type": "audio_url", "role": "reference_audio",
                        "audio_url": {"url": _data_uri(audio, _mime_audio(audio))}})
    content.append({"type": "text", "text": prompt})
    # 图生视频(首帧)宽高比由输入图决定,ratio 恒为 adaptive(文档明示)
    eff_ratio = "adaptive" if first_frame else (ratio or "adaptive")
    return {
        "model": model,
        "content": content,
        "resolution": resolution,
        "duration": int(duration),
        "ratio": eff_ratio,
    }


def parse_create_out(out: str) -> str | None:
    """解析创建响应：返回 task_id；失败返回 None。"""
    try:
        d = json.loads(out)
    except Exception:  # noqa: BLE001
        return None
    return d.get("task_id")


def parse_query_out(out: str) -> tuple[str, str | None]:
    """解析查询响应（确定性）：返回 (status, video_url|fail_reason)。

    status: "success" | "fail" | "pending"。
    """
    try:
        d = json.loads(out)
    except Exception:  # noqa: BLE001
        return "pending", None
    task = d.get("task", {})
    st = task.get("status", "")
    if st == "succeeded":
        return "success", (task.get("content", {}) or {}).get("url")
    if st in ("failed", "cancelled"):
        return "fail", (task.get("error", {}) or {}).get("message", st)
    return "pending", None


# ---------------------------------------------------------------------------
# 网络层
# ---------------------------------------------------------------------------
def _post(body: dict, cfg: Config, timeout: int = 60) -> str:
    r = requests.post(
        f"{cfg.minimax_base_url}/v2/video_generation",
        headers={"Authorization": f"Bearer {cfg.require_key('minimax_api_key')}",
                 "Content-Type": "application/json"},
        json=body,
        proxies=NO_PROXY,  # pyright: ignore[reportArgumentType]
        timeout=(10, timeout),
    )
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}: {r.text[:300]}")
    return r.text


def submit(
    prompt: str,
    cfg: Config,
    *,
    images: list[str] | None = None,
    audio: str | None = None,
    first_frame: str | None = None,
    duration: int = 5,
    retries: int = 3,
) -> tuple[str | None, str]:
    """提交 MiniMax 任务（编排层，含退避重试）。返回 (task_id|None, raw)。

    连接抖动/瞬时 5xx 重试；参数级错误（HTTP 400/422）不重试。
    """
    body = build_submit_body(
        prompt, duration, images=images, audio=audio, first_frame=first_frame,
        model=cfg.minimax_model,
    )
    out = ""
    for attempt in range(retries):
        try:
            out = _post(body, cfg, timeout=60)
        except RuntimeError as e:
            msg = str(e)
            if any(f"HTTP {c}" in msg for c in (400, 401, 402, 422)):
                raise  # 参数/鉴权/余额/内容违规,重试无意义
            if attempt == retries - 1:
                raise
            time.sleep(10 * (attempt + 1))
            continue
        tid = parse_create_out(out)
        if tid:
            return tid, out
        time.sleep(5 * (attempt + 1))
    return None, out


def wait_download(
    tid: str, dst: str, cfg: Config, tries: int = 60, gap: int = 15
) -> int | str | None:
    """轮询 succeeded → 从 content.url 稳健下载。返回 (size|"FAIL: .."|None)。"""
    for _ in range(tries):
        r = requests.get(
            f"{cfg.minimax_base_url}/v2/query/video_generation/{tid}",
            headers={"Authorization": f"Bearer {cfg.require_key('minimax_api_key')}"},
            proxies=NO_PROXY,  # pyright: ignore[reportArgumentType]
            timeout=(10, 30),
        )
        if r.status_code != 200:
            time.sleep(gap)
            continue
        status, payload = parse_query_out(r.text)
        if status == "success" and payload:
            return robust_download(payload, dst)
        if status == "fail":
            return f"FAIL: {payload}"
        time.sleep(gap)
    return None  # 超时未完成


# ---------------------------------------------------------------------------
# 后端统一入口（与 generation/service.py backends 契约一致）
# ---------------------------------------------------------------------------
def submit_i2v(image_path: str, prompt: str, cfg: Config, duration: int = 5) -> str | None:
    """纯产品 image2video：首帧真图 + 文本。"""
    tid, _ = submit(prompt, cfg, first_frame=image_path, duration=duration)
    return tid


def submit_mm(image_paths: list[str], audio_path: str | None, prompt: str, cfg: Config,
              duration: int = 5) -> str | None:
    """多模态参考（口播实验性）：参考图 + 段配音（reference_audio）。"""
    tid, _ = submit(prompt, cfg, images=image_paths, audio=audio_path, duration=duration)
    return tid


def submit_t2v(prompt: str, cfg: Config, duration: int = 5) -> str | None:
    tid, _ = submit(prompt, cfg, duration=duration)
    return tid
