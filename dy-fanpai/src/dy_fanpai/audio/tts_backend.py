"""audio/tts_backend.py — TTS 配音后端适配层（可插拔注册表）。

统一 TTS 后端接口，支持多种来源（本地 / 在线 / 未来新增），输出契约与
``audio/voice.py`` 的 ``synth()`` 对齐：

- 每段产出 ``out_dir/{seg}.wav``（统一 24kHz 单声道，与 service.py 的 ``_CUT_SR`` 一致）；
- 段时长对齐：超长段 atempo 压缩到段长，不足段 apad 补静音（绝不超段长，避免
  后续 gen 阶段「配音超长」误加时）；
- 写 ``out_dir/timing.json``：``{seg: [{speaker, text, dur}]}`` 句级记录。

后端通过 ``@register("name")`` 注册进 ``_REGISTRY``，新增来源只需实现
``available(cfg)`` 与 ``synth_segment(text, dst, cfg)`` 并注册，即自动出现在
``list_backends()`` 与 pipeline/CLI 的选择列表里——预留扩展点。

当前内置后端：
- ``voxcpm``：OpenBMB VoxCPM-Demo 在线 Space（Gradio API，zero-shot 克隆）；
- ``voicebox``：本地 Qwen3-TTS 服务（HTTP REST，zero-shot 克隆，支持 instruct 情绪）。

确定性函数（list_backends / get_backend / available / _align_duration /
_pad / timing 记录）与重型 IO（synth_segment 各后端实现）解耦，便于离线单测。
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from collections.abc import Callable
from typing import Any, Protocol

from ..config import Config

# 统一输出采样率：单声道 24k（与 audio/service.py 的 _CUT_SR 对齐）
TTS_SR = 24000
TTS_CH = 1

# 段长容差：超过段长 0.3s 才压缩，避免把本就刚好对齐的语音无故变速
_OVER_TOL = 0.3


class TTSBackend(Protocol):
    """后端协议：available 检查 + synth_segment 单段合成。"""

    name: str

    @staticmethod
    def available(cfg: Config) -> tuple[bool, str]:
        """返回 (可用?, 说明)。doctor / pipeline 用它预检。"""
        ...

    @staticmethod
    def synth_segment(text: str, dst: str, cfg: Config) -> float:
        """把 text 合成为 wav 写入 dst，返回实际时长（秒）。

        要求：输出 24kHz 单声道 wav（由 _normalize_wav 兜底统一，各后端可先
        产出任意采样率，适配层负责转换）。失败抛 RuntimeError。
        """
        ...


# ---------------------------------------------------------------------------
# 注册表
# ---------------------------------------------------------------------------
_REGISTRY: dict[str, Callable[[], Any]] = {}
# 顺序即 CLI/doctor 展示顺序
_ORDER: list[str] = []


def register(name: str):
    """注册后端类（模块加载时自动执行）。"""

    def deco(cls):
        _REGISTRY[name] = cls
        if name not in _ORDER:
            _ORDER.append(name)
        return cls

    return deco


def list_backends() -> list[str]:
    """已注册的后端名（按注册顺序）。"""
    return list(_ORDER)


def get_backend(name: str) -> Callable[[], Any] | None:
    return _REGISTRY.get(name)


def backend_available(name: str, cfg: Config) -> tuple[bool, str]:
    cls = _REGISTRY.get(name)
    if cls is None:
        return False, f"未知 TTS 后端 {name}"
    return cls.available(cfg)


# ---------------------------------------------------------------------------
# 通用工具（后端无关，确定性）
# ---------------------------------------------------------------------------
def _seg_plan_duration(seg: dict) -> float:
    """段规划时长（秒）：优先 duration 字段，否则 end-start。"""
    d = seg.get("duration")
    if d:
        return float(d)
    return max(0.0, float(seg.get("end", 0)) - float(seg.get("start", 0)))


def _ffmpeg_bin(cfg: Config) -> str:
    return cfg.ffmpeg_bin or "ffmpeg"


def _normalize_wav(src: str, dst: str, cfg: Config) -> None:
    """统一为 24kHz 单声道 wav（确定性 IO，失败抛 CalledProcessError）。"""
    subprocess.run(
        [_ffmpeg_bin(cfg), "-y", "-v", "error", "-i", src,
         "-ac", str(TTS_CH), "-ar", str(TTS_SR), dst],
        check=True,
    )


def _probe_duration(path: str, cfg: Config) -> float:
    r = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "csv=p=0", path],
        capture_output=True, text=True,
    )
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def _align_duration(src: str, dst: str, target: float, cfg: Config) -> float:
    """把 src 对齐到 target 秒：超长 atempo 压缩，不足 apad 补静音。

    返回最终时长。单次 atempo 上限 2.0，超出则级联。
    """
    d = _probe_duration(src, cfg)
    if d <= 0:
        # 空/坏音频：直接产出 target 秒静音
        subprocess.run(
            [_ffmpeg_bin(cfg), "-y", "-v", "error", "-f", "lavfi",
             "-i", f"anullsrc=r={TTS_SR}:cl=mono", "-t", f"{target:.3f}", dst],
            check=True,
        )
        return target
    if d > target + _OVER_TOL:
        # 压缩：atempo = d/target，最多两次级联（atempo 范围 0.5~2.0）
        ratio = d / target
        if ratio <= 2.0:
            filters = [f"atempo={ratio:.4f}"]
        else:
            filters = ["atempo=2.0", f"atempo={ratio / 2.0:.4f}"]
        tmp = dst + ".tmp.wav"
        subprocess.run(
            [_ffmpeg_bin(cfg), "-y", "-v", "error", "-i", src,
             "-af", ",".join(filters), "-ac", str(TTS_CH), "-ar", str(TTS_SR), tmp],
            check=True,
        )
        subprocess.run(
            [_ffmpeg_bin(cfg), "-y", "-v", "error", "-i", tmp,
             "-af", f"apad=whole_dur={target:.3f}",
             "-ac", str(TTS_CH), "-ar", str(TTS_SR), dst],
            check=True,
        )
        if os.path.exists(tmp):
            os.remove(tmp)
    elif d < target - 0.05:
        subprocess.run(
            [_ffmpeg_bin(cfg), "-y", "-v", "error", "-i", src,
             "-af", f"apad=whole_dur={target:.3f}",
             "-ac", str(TTS_CH), "-ar", str(TTS_SR), dst],
            check=True,
        )
    else:
        # 已对齐：直接归一化采样率即可
        subprocess.run(
            [_ffmpeg_bin(cfg), "-y", "-v", "error", "-i", src,
             "-ac", str(TTS_CH), "-ar", str(TTS_SR), dst],
            check=True,
        )
    return target


# ---------------------------------------------------------------------------
# 后端：VoxCPM（在线 HF Space，Gradio API）
# ---------------------------------------------------------------------------
@register("voxcpm")
class VoxCPMBackend:
    name = "voxcpm"

    @staticmethod
    def available(cfg: Config) -> tuple[bool, str]:
        url = cfg.voxcpm_space_url or "https://openbmb-voxcpm-demo.hf.space"
        if not cfg.voxcpm_reference_audio or not os.path.exists(cfg.voxcpm_reference_audio):
            return False, "VoxCPM 需要参考音色（config.voxcpm_reference_audio）"
        return True, f"VoxCPM 在线 Space({url})"

    @staticmethod
    def synth_segment(text: str, dst: str, cfg: Config) -> float:
        raise NotImplementedError("voxcpm 走批量 Space API 路径")


# ---------------------------------------------------------------------------
# 后端：Voicebox（本地 Qwen3-TTS，HTTP REST，zero-shot 克隆）
# ---------------------------------------------------------------------------
@register("voicebox")
class VoiceboxBackend:
    name = "voicebox"

    @staticmethod
    def available(cfg: Config) -> tuple[bool, str]:
        url = cfg.voicebox_base_url or "http://127.0.0.1:17493"
        # 只在配置了 profile 或参考音频时认为可配；实际就绪以 /health 为准
        if not (cfg.voicebox_profile_id or cfg.voicebox_reference_audio):
            return False, (
                "Voicebox 需要 voicebox_profile_id 或参考音频 "
                "（config.voicebox_profile_id / voicebox_reference_audio）"
            )
        return True, f"Voicebox 本地服务({url})"

    @staticmethod
    def synth_segment(text: str, dst: str, cfg: Config) -> float:
        raise NotImplementedError("voicebox 走批量 REST 路径")


# ---------------------------------------------------------------------------
# 批量编排：synthesize（后端无关的段循环 + 时长对齐 + timing）
# ---------------------------------------------------------------------------
def _seg_dialogue(seg: dict) -> str:
    """取段台词（去掉说话人标签，供单音色后端直接合成）。"""
    d = (seg.get("dialogue") or "").strip()
    if not d:
        return ""
    # 去掉 A：/B：/甲： 说话人标签（CosyVoice 多说话人标签，单音色后端拼成一句）。
    # 全局匹配（非仅行首），与 voice.parse_speakers 的 _SP_DELIM 约定一致。
    d = re.sub(r"[A-Z甲乙丙][：:]\s*", "", d).strip()
    return d


def synthesize(
    plan_path: str,
    out_dir: str,
    backend: str,
    cfg: Config,
    *,
    pron_fix_path: str | None = None,
    instruct: str = "",
    only: set[str] | None = None,
) -> dict:
    """批量 TTS 合成（P3 音频 stage 的配音模式入口）。

    输入 planning/segments.json → 输出 out_dir/{seg}.wav + out_dir/timing.json。
    返回 timing 字典（与 voice.synth 同构）。backend 未知 / 不可用 → RuntimeError。

    voxcpm / voicebox 走注册的批量合成器（见下方 _BATCH_SYNTHESIZERS）。
    only: 可选段号集合（如 {"S1","S2"}），只合成这些段；None=全部。
    """
    cls = _REGISTRY.get(backend)
    if cls is None:
        raise RuntimeError(f"未知 TTS 后端: {backend}（可选 {list_backends()}）")
    ok, msg = cls.available(cfg)
    if not ok:
        raise RuntimeError(f"TTS 后端 {backend} 不可用: {msg}")

    os.makedirs(out_dir, exist_ok=True)
    data: Any = json.load(open(plan_path, encoding="utf-8"))
    segs = data.get("segments", data) if isinstance(data, dict) else data
    if only:
        segs = [s for s in segs if s.get("seg") in only]

    # 逐段合成 + 对齐 + timing
    runner = _BATCH_SYNTHESIZERS.get(backend)
    if runner is None:
        raise RuntimeError(f"后端 {backend} 未实现批量合成器")

    timing: dict[str, list[dict]] = {}
    for s in segs:
        seg = s["seg"]
        text = _seg_dialogue(s)
        if not text:
            continue
        raw = os.path.join(out_dir, f"_{seg}_raw.wav")
        try:
            runner(text, raw, cfg)
        except Exception as e:  # noqa: BLE001 —— 单段失败不带崩整批
            print(f"[tts:{backend}] {seg} 合成失败: {e}", flush=True)
            continue
        target = _seg_plan_duration(s)
        dst = os.path.join(out_dir, f"{seg}.wav")
        _align_duration(raw, dst, target, cfg)
        if os.path.exists(raw):
            os.remove(raw)
        timing[seg] = [{"speaker": "default", "text": text, "dur": round(target, 3)}]
        print(f"[tts:{backend}] {seg} → {dst} ({target:.2f}s)", flush=True)

    with open(os.path.join(out_dir, "timing.json"), "w", encoding="utf-8") as f:
        json.dump(timing, f, ensure_ascii=False, indent=1)
    print(f"[tts:{backend}] {len(timing)} 段 → {out_dir} + timing.json", flush=True)
    return timing


# ---------------------------------------------------------------------------
# 各后端批量合成器（返回实际时长；失败抛异常）
# ---------------------------------------------------------------------------
def _voxcpm_synthesize(text: str, dst: str, cfg: Config) -> float:
    """VoxCPM：Gradio API 单段合成（upload → queue/join → SSE 轮询 → 下载 mp3）。"""
    from .voxcpm_client import synth_one

    mp3 = dst + ".mp3"
    dur = synth_one(text, mp3, cfg)
    _normalize_wav(mp3, dst, cfg)
    if os.path.exists(mp3):
        os.remove(mp3)
    return dur


def _voicebox_synthesize(text: str, dst: str, cfg: Config) -> float:
    """Voicebox：本地 REST 单段合成（ensure model → /generate → 轮询 → /audio）。"""
    from .voicebox_client import generate

    return generate(text, dst, cfg)


_BATCH_SYNTHESIZERS: dict[str, Callable[[str, str, Config], float]] = {
    "voxcpm": _voxcpm_synthesize,
    "voicebox": _voicebox_synthesize,
}


# 兼容导入：让 tts_backend 暴露 voice 的读音修正等复用函数
from . import voice as _voice  # noqa: E402  (循环安全:voice 不依赖本模块)

parse_speakers = _voice.parse_speakers
apply_pron_fix = _voice.apply_pron_fix
resolve_target = _voice.resolve_target

__all__ = [
    "TTSBackend", "register", "list_backends", "get_backend",
    "backend_available", "synthesize", "TTS_SR", "TTS_CH",
    "parse_speakers", "apply_pron_fix", "resolve_target",
]
