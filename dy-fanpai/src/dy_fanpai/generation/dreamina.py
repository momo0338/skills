"""generation/dreamina.py — 即梦(Dreamina CLI)生成后端（WP4）。

忠实复刻原项目 gen_segments.py 的即梦分支，仅做冻结期改造：
1. 二进制路径走 ``cfg.dreamina_bin``（不再硬编码 ~/.local/bin/dreamina）；
2. 确定性函数（wav_dur / fitted_duration / fit_duration_to_audio / build_submit_cmd /
   parse_submit_out / is_fatal / parse_query_out）与 subprocess（submit / wait_download）
   解耦，便于离线单测；
3. 下载复用 media.download.robust_download（坏流重下）。

业务铁律（必须保留）：
- type=mm 口播段: multimodal2video，双图(主播@图1 + 产品@图2) + 段配音对口型；
- type=i2v hero/包装段: image2video，真实产品图慢运镜；
- --poll 0 提交 → 轮询 query_result success → 从 video_url 直接 urllib 下载
  （CLI 的 --download_dir 会截断成坏文件，实测踩过）；
- 提交带退避重试：WSL 对即梦偶发瞬时 EOF，一枪打空整段就废(07-22 实翻车)；
- 配音比规划时长长会被 assemble 掐掉半句话 → 口播段生成时长按实际 wav 自动上调(上限15s)。
"""

from __future__ import annotations

import math
import os
import re
import subprocess
import time

from ..config import Config
from ..media.download import robust_download

# 即梦模型版本（原硬编码 seedance2.0_vip，现收归常量）
MULTIMODAL_MODEL = "seedance2.0_vip"
I2V_MODEL = "seedance2.0_vip"
RATIO = "9:16"
RESOLUTION = "720p"
UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")


def wav_dur(path: str) -> float:
    """ffprobe 取 wav 时长；失败返回 0.0（确定性 IO）。"""
    try:
        return float(subprocess.check_output(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
             "-of", "csv=p=0", path]).strip())
    except Exception:  # noqa: BLE001
        return 0.0


def fitted_duration(planned: float, audio_dur: float, cap: int = 15, tol: float = 0.25) -> float:
    """口播段生成时长按实际 wav 自动上调（确定性）。

    audio_dur 比 planned 多出一个容差(tol)才算超长，避免配音恰好等长(静音垫尾)误加时。
    上限 cap(15s)。返回新时长；无需调整则返回 planned。
    """
    if audio_dur > planned + tol:
        return min(cap, math.ceil(audio_dur + 0.5))
    return planned


def fit_duration_to_audio(seg: dict, audio_dir: str | None) -> None:
    """★配音比规划时长长会被 assemble 掐掉半句话——口播段生成时长按实际 wav 自动上调(上限15s)。

    原地修改 seg["duration"]；仅 mm 段且有对应 wav 时生效（副作用：打印告警）。
    """
    if seg["type"] != "mm" or not audio_dir:
        return
    wav = os.path.join(audio_dir, f"{seg['seg']}.wav")
    if not os.path.exists(wav):
        return
    ad = wav_dur(wav)
    if ad > seg["duration"] + 0.25:  # 留容差:配音恰好等长(如静音垫尾)不算超长,别误加时白烧积分
        new_d = min(15, math.ceil(ad + 0.5))
        if new_d > seg["duration"]:
            print(f"  [时长] 配音{ad:.1f}s > 规划{seg['duration']}s → 生成时长调为 {new_d}s")
            seg["duration"] = new_d
        if ad > 14.5:
            print(f"  [⚠时长] 配音{ad:.1f}s 逼近 15s 上限,放不下会截尾——请回 plan 拆段或精简台词")


def build_submit_cmd(seg: dict, audio_dir: str | None, bin_path: str) -> list[str]:
    """构造即梦提交命令（确定性）。

    - mm: multimodal2video，逐张 --image，存在段配音则 --audio，固定 --prompt/--duration/
      --ratio/--model_version/--video_resolution/--poll 0；
    - i2v: image2video，单 --image=seg["anchor"]，其余同。
    """
    t = seg["type"]
    dur = str(seg["duration"])
    if t == "mm":
        cmd = [bin_path, "multimodal2video"]
        for img in seg["images"]:
            cmd += ["--image", img]
        wav = os.path.join(audio_dir, f"{seg['seg']}.wav") if audio_dir else None
        if wav and os.path.exists(wav):
            cmd += ["--audio", wav]
        cmd += ["--prompt", seg["prompt"], "--duration", dur, "--ratio", RATIO,
                "--model_version", MULTIMODAL_MODEL, "--video_resolution", RESOLUTION, "--poll", "0"]
    else:
        cmd = [bin_path, "image2video", "--image", seg["anchor"],
               "--prompt", seg["prompt"], "--duration", dur,
               "--model_version", I2V_MODEL, "--video_resolution", RESOLUTION, "--poll", "0"]
    return cmd


def parse_submit_out(out: str) -> tuple[str | None, str, str]:
    """解析即梦提交输出（确定性）：返回 (submit_id|None, credit_count, raw)。"""
    m = UUID.search(out)
    if m:
        cc = re.search(r'"credit_count"\s*:\s*(\d+)', out)
        return m.group(0), (cc.group(1) if cc else "?"), out
    return None, "?", out


def is_fatal(out: str) -> bool:
    """参数级错误(如音频<2s)，重试无意义。"""
    return "out of allowed range" in out


def submit(seg: dict, audio_dir: str | None, cfg: Config, retries: int = 3) -> tuple[str | None, str, str]:
    """提交即梦任务（编排层，含退避重试）。

    返回 (submit_id|None, credit_count, raw)。submit_id 为 None 表示提交失败。
    """
    bin_path = cfg.dreamina_bin
    out = ""
    for attempt in range(retries):
        r = subprocess.run(build_submit_cmd(seg, audio_dir, bin_path), capture_output=True, text=True)
        out = r.stdout + r.stderr
        sid, cc, _ = parse_submit_out(out)
        if sid:
            return sid, cc, out
        if is_fatal(out):
            break  # 参数级错误,重试无意义
        time.sleep(20 * (attempt + 1))
    return None, "?", out


def parse_query_out(out: str) -> tuple[str | None, str | None]:
    """解析 query_result 轮询输出（确定性）：返回 (status, payload)。

    status: "success"|"fail"|None(pending)；success→payload=video_url，
    fail→payload=fail_reason，pending→(None, None)。
    """
    if '"gen_status": "success"' in out or '"gen_status":"success"' in out:
        u = re.search(r'"video_url"\s*:\s*"([^"]+)"', out)
        return "success", (u.group(1) if u else None)
    if '"gen_status": "fail"' in out or '"gen_status":"fail"' in out:
        fr = re.search(r'"fail_reason"\s*:\s*"([^"]+)"', out)
        return "fail", (fr.group(1) if fr else "即梦返回失败,无 fail_reason")
    return None, None


def wait_download(sid: str, dst: str, cfg: Config, tries: int = 40, gap: int = 15) -> int | str | None:
    """轮询 success → 从 video_url 稳健下载（避开 CLI 截断）。

    返回下载字节数(int) 或 "FAIL: ..." 失败串 或 None(超时未完成)。
    """
    bin_path = cfg.dreamina_bin
    for _ in range(tries):
        out = subprocess.run([bin_path, "query_result", "--submit_id=" + sid],
                              capture_output=True, text=True).stdout
        status, payload = parse_query_out(out)
        if status == "success" and payload:
            return robust_download(payload, dst)
        if status == "fail":
            return f"FAIL: {payload}"
        time.sleep(gap)
    return None  # 超时未完成
