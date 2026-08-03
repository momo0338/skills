"""generation/xyq.py — 小云雀(pippit-tool-cli)视频生成后端（WP4，即梦/Ark 之外的第三条腿）。

忠实复刻原项目 xyq_gen.py，仅做冻结期改造：
1. key 走 ``cfg.xyq_access_key``（环境变量 XYQ_ACCESS_KEY）；模型走 ``cfg.xyq_video_model``
   （不再 ``from config import xyq_key`` / 硬编码模型）；
2. 确定性函数（_common / build_*_args）与 CLI subprocess（submit_* / wait_download）解耦；
3. model 用配置，不改代码（XYQ_VIDEO_MODEL 覆盖）。

业务铁律（必须保留）：
- 走小云雀 generate-video 模型直出(独立的 credits 池,和即梦积分/Ark token 都不共享)；
- 小云雀会自生音画，产物音轨虽被 assemble 覆盖，但防它把嘴型/字幕画进画面 →
  非口播段加 AUDIO_GUARD（"无人声,无背景音乐。"）；
- 口播段 submit_mm 标记实验性：小云雀是否音频驱动口型未验证，验证前 mm 段默认走即梦；
- tid 形如 "thread_id/run_id"（query-result 两个都要）。
契约: submit_*(...)->tid ; wait_download(tid,dst)->(size,usage)。
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import time

from ..config import Config

# 小云雀会自生音画；产物音轨虽被 assemble 覆盖，但防它把嘴型/字幕画进画面
AUDIO_GUARD = "无人声,无背景音乐。"


def _cli() -> str:
    p = shutil.which("pippit-tool-cli")
    if not p:
        raise RuntimeError("pippit-tool-cli 不在 PATH(npx @pippit-dev/cli@latest install)")
    return p


def _env(cfg: Config) -> dict:
    e = dict(os.environ)
    e["XYQ_ACCESS_KEY"] = cfg.require_key("xyq_access_key")
    return e


def _run(args: list[str], cfg: Config, timeout: int = 300) -> str:
    r = subprocess.run([_cli()] + args, capture_output=True, text=True,
                       env=_env(cfg), timeout=timeout)
    return (r.stdout or "") + (r.stderr or "")


def _field(out: str, key: str) -> str | None:
    """从 CLI 输出提取字段: 先试 JSON 行,再退 `key=value` / `"key": "value"` 正则。"""
    for line in out.splitlines():
        line = line.strip()
        if line.startswith("{"):
            try:
                j = json.loads(line)
                v = j.get(key) or (j.get("data", {}).get("run", {}) or {}).get(key)
                if v:
                    return str(v)
            except Exception:  # noqa: BLE001
                pass
    m = re.search(rf'"{key}"\s*:\s*"([^"]+)"', out) or \
        re.search(rf'{key.replace("_", "[-_]")}\s*[=:]\s*(\S+)', out)
    return m.group(1) if m else None


def _common(prompt: str, duration: int, resolution: str, ratio: str, guard: bool, model: str) -> list[str]:
    """公共参数构造（确定性）。guard=True 且 prompt 无"无人声"时追加 AUDIO_GUARD。"""
    if guard and "无人声" not in prompt:
        prompt = prompt.rstrip() + AUDIO_GUARD
    a = ["--prompt", prompt, "--duration", str(int(duration)),
         "--ratio", ratio, "--resolution", resolution]
    if model:
        a += ["--model", model]
    return a


def build_i2v_args(image_path: str, prompt: str, duration: int = 5, resolution: str = "720p",
                  ratio: str = "9:16", model: str = "") -> list[str]:
    """image2video 命令参数（确定性）：真产品图 + 文本（+ AUDIO_GUARD）。"""
    return ["generate-video", "--image", image_path] + _common(prompt, duration, resolution, ratio, True, model)


def build_mm_args(image_paths: list[str], audio_path: str | None, prompt: str, duration: int = 5,
                  resolution: str = "720p", ratio: str = "9:16", model: str = "") -> list[str]:
    """⚠实验性：多锚图 + 段配音。口播段不加无人声限定(要的就是说话)。"""
    args = ["generate-video"]
    for p in image_paths:
        args += ["--image", p]
    if audio_path:
        args += ["--audio", audio_path]
    return args + _common(prompt, duration, resolution, ratio, False, model)


def build_t2v_args(prompt: str, duration: int = 5, resolution: str = "720p",
                  ratio: str = "9:16", model: str = "") -> list[str]:
    """text2video 命令参数（确定性，+ AUDIO_GUARD）。"""
    return ["generate-video"] + _common(prompt, duration, resolution, ratio, True, model)


def _submit(args: list[str], cfg: Config) -> str:
    out = _run(args, cfg, timeout=300)
    t, rid = _field(out, "thread_id"), _field(out, "run_id")
    if not (t and rid):
        raise RuntimeError(f"提交无 thread_id/run_id: {out[-300:]}")
    link = _field(out, "web_thread_link")
    if link:
        print(f"  xyq_link={link}", flush=True)
    return f"{t}/{rid}"


def submit_i2v(image_path: str, prompt: str, cfg: Config, duration: int = 5,
               resolution: str = "720p", ratio: str = "9:16") -> str:
    return _submit(build_i2v_args(image_path, prompt, duration, resolution, ratio, cfg.xyq_video_model), cfg)


def submit_mm(image_paths: list[str], audio_path: str | None, prompt: str, cfg: Config,
              duration: int = 5, resolution: str = "720p", ratio: str = "9:16") -> str:
    return _submit(build_mm_args(image_paths, audio_path, prompt, duration, resolution, ratio, cfg.xyq_video_model), cfg)


def submit_t2v(prompt: str, cfg: Config, duration: int = 5, resolution: str = "720p",
               ratio: str = "9:16") -> str:
    return _submit(build_t2v_args(prompt, duration, resolution, ratio, cfg.xyq_video_model), cfg)


def wait_download(tid: str, dst: str, cfg: Config, tries: int = 60, gap: int = 10) -> tuple[int | str | None, dict]:
    """轮询 query-result --download-dir 直到 completed；把落盘的 mp4 挪到 dst。"""
    t, rid = tid.split("/", 1)
    tmp = tempfile.mkdtemp(prefix="xyq_")
    try:
        for _ in range(tries):
            out = _run(["query-result", "--thread-id", t, "--run-id", rid,
                        "--download-dir", tmp], cfg, timeout=600)
            err = _field(out, "error_message")
            if err and err.lower() not in ("null", "none", ""):
                return f"FAIL: {err[:150]}", {}
            done = re.search(r'"completed"\s*:\s*true', out) or "completed=true" in out
            vids = [os.path.join(tmp, f) for f in os.listdir(tmp)
                    if f.lower().endswith((".mp4", ".mov", ".webm"))]
            if vids:
                src = max(vids, key=os.path.getsize)  # 多文件取最大(正片)
                if os.path.getsize(src) > 10240:
                    shutil.move(src, dst)
                    return os.path.getsize(dst), {"backend": "xyq"}
            if done:
                # completed 但没扫到文件 → 从 output_path/url 兜底
                u = _field(out, "output_path") or _field(out, "url")
                if u and u.startswith("http"):
                    _run(["download-result", "--url", u, "--output-path", dst], cfg, timeout=600)
                    if os.path.exists(dst) and os.path.getsize(dst) > 10240:
                        return os.path.getsize(dst), {"backend": "xyq"}
                return f"FAIL: completed 但无产物文件: {out[-200:]}", {}
            time.sleep(gap)
        return None, {}  # 超时未完成
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
