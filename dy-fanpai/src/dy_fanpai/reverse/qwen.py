"""reverse/qwen.py — 反推引擎腿 3（通义千问 Qwen，阿里云百炼原生视频输入）。

与 seed.py / kimi.py 同契约：输入视频 → 同一套 ffmpeg 硬切 → Qwen 原生视频理解 →
输出同 SCHEMA 的 shotlist json。供 merge.py 与 Seed 结果合并裁决（alt 腿）。

接入依据（2026-08 官方文档核实）：
- 百炼视觉理解：`qwen3.7-plus` 等原生支持**文本、图像、视频**输入；
  视频上限 2 小时 / 2GB / 64 个视频，1M 上下文，支持结构化 JSON 输出。
- OpenAI 兼容接口（compatible-mode/v1）：content 用 `video_url` 类型，
  本地视频以 `data:video/mp4;base64,...` data URI 传入（与 seed.py 的 Ark 同构）。
- 国内端点直连，不走代理。

能力定位（2026-08-03 实测：12s 合成视频真实反推成功，返回 637 字/16.7s，
shot 的 scene/action/colors/host_on_camera/product_role 均正确）：
- Qwen-VL 系实体与运镜描述能力均较强；已做一次受控 Live 冒烟（合成视频），
  真实带货视频的完整验收仍需对应素材（Live 前置 U6）。

⚠ 验收状态：已做一次受控 Live 冒烟（2026-08-03 合成视频实测通过）；真实带货视频
完整验收仍需合法素材与预算（Live 前置 U6），未完成前按 DEGRADATION 4b 记录。

依赖：ffmpeg/ffprobe（detect_cuts/video_info/make_upload_clip 复用 seed）、
requests（qwen_call 用）。
"""

from __future__ import annotations

import base64
import json
import os
import time

import requests

from ..config import Config
from .seed import SCHEMA, detect_cuts, extract_json, make_upload_clip, video_info

# 百炼国内端点，直连不走代理
NO_PROXY: dict[str, str | None] = {"http": None, "https": None}


def build_prompt(cuts: list[float], duration: float) -> str:
    """构造 Qwen 反推 Prompt。复用 Seed 的 7 条硬纪律，补 Qwen 特性：
    - 第 8 条 实体纪律（与 K3 一致：性别人数逐人核对、不脑补陈列、屏字逐字抄）。
    Qwen-VL 系对指令跟随好，强调「只输出 JSON」降低 markdown 围栏概率。
    """
    segs = []
    bounds = sorted(set([0.0] + list(cuts) + [duration]))
    for i in range(len(bounds) - 1):
        segs.append([bounds[i], bounds[i + 1]])
    return (
        f"这是一个 {duration}秒 的竖屏带货短视频。ffmpeg 已检出硬切边界,把它切成 "
        f"{len(segs)} 个镜头段(秒):{json.dumps(segs, ensure_ascii=False)}\n"
        f"口播长镜可能超过15秒,你先按硬切如实标,生成时再拆。\n"
        f"请观看视频(含音频),逐镜分析并转写台词,**只输出一个JSON对象**,"
        f"不要markdown不要解释,严格用这个结构:\n{SCHEMA}\n"
        f"要求:1.shots 严格对应 {len(segs)} 个段,start/end 用给定值。"
        f"2.前3秒内的镜头 is_opening_3s=true,描述要特别精细(爆点)。"
        f"3.action 要把主体+动作都写全(如'一只手把海参掰开'而非'海参剖面')。"
        f"4.product_role 判断要准(剖面/参刺/弹性这类真实质感判 hero_real,包装盒判 package_text)。"
        f"5.材质/颜色写死。只描述不评判。"
        f"6.台词只收录真实人声:只出现在字幕/花字上而无对应人声的文字(短视频开头常有静音字幕残留),"
        f"只进 onscreen_text,严禁写进 dialogue 和 full_transcript。"
        f"7.onscreen_text 逐句原样采集屏上每条字幕/花字(保留自动字幕的错字),句间用;分隔。"
        f"8.实体纪律:人物性别/人数逐人核对,看不清就写'看不清',严禁按穿着推断;"
        f"背景物件的数量/颜色/种类只写画面确凿可见的,不要脑补补全陈列;屏上文字逐字抄不要改字。"
    )


def build_request_body(
    clip_path: str, prompt: str, model: str, timeout: int = 900
) -> dict:
    """构造百炼 chat/completions 请求体（确定性）。

    视频以 base64 data URI 传入 `video_url`（与 seed.py 的 Ark 同构，
    本地文件无需公网 URL）。关闭流式以便直接收完整 JSON。
    """
    b64 = base64.b64encode(open(clip_path, "rb").read()).decode()
    return {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "video_url",
                        "video_url": {"url": f"data:video/mp4;base64,{b64}"},
                    },
                    {"type": "text", "text": prompt},
                ],
            }
        ],
        "stream": False,
    }


def qwen_call(clip_path: str, prompt: str, cfg: Config, timeout: int = 900) -> tuple[str, float]:
    """调百炼 Qwen 视频理解，返回 (原始文本, 耗时秒)。

    仅在 live 且已取密钥时调用；NO_PROXY 强制不走代理。
    """
    key = cfg.require_key("dashscope_api_key")
    body = build_request_body(clip_path, prompt, cfg.qwen_model, timeout)
    t0 = time.time()
    r = requests.post(
        f"{cfg.qwen_base_url}/chat/completions",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json=body,
        proxies=NO_PROXY,  # pyright: ignore[reportArgumentType]
        timeout=(10, timeout),
    )
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}: {r.text[:300]}")
    data = r.json()
    try:
        txt = data["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError, TypeError) as e:
        raise RuntimeError(f"Qwen 响应异常: {str(data)[:300]}") from e
    return txt, round(time.time() - t0, 1)


def reverse(
    video: str,
    out: str | None = None,
    cuts: list[float] | None = None,
    scene_thresh: float = 0.15,
    scale: int = 480,
    timeout: int = 900,
    cfg: Config | None = None,
) -> dict:
    """Qwen 单反推主入口（与 seed.reverse / kimi.reverse 同契约）。

    - 离线（无 key / dry）时不会调用 qwen_call；本函数本身是编排层，
      确定性逻辑在 detect_cuts/video_info/make_upload_clip/build_prompt/
      build_request_body/extract_json 内。
    """
    cfg = cfg or Config.load()
    vi = video_info(video)
    if cuts is None:
        cuts = detect_cuts(video, scene_thresh)
    workdir = (
        os.path.dirname(os.path.abspath(out)) if out else os.path.dirname(os.path.abspath(video))
    )
    os.makedirs(workdir, exist_ok=True)
    clip = make_upload_clip(video, scale, True, workdir)
    print(
        f"[qwen_reverse] {vi['duration']}s {vi['width']}x{vi['height']} | "
        f"{len(cuts)}硬切 | clip {os.path.getsize(clip) // 1024}KB",
        flush=True,
    )
    raw, secs = qwen_call(clip, build_prompt(cuts, vi["duration"]), cfg, timeout)
    print(f"[qwen_reverse] {cfg.qwen_model} 返回 {len(raw)}字 / {secs}s", flush=True)
    data = extract_json(raw)
    data.setdefault("video_info", vi)
    data["cuts"] = cuts
    out = out or os.path.join(workdir, "shotlist_qwen.json")
    json.dump(data, open(out, "w"), ensure_ascii=False, indent=2)
    print(f"[qwen_reverse] {len(data.get('shots', []))} 镜 → {out}", flush=True)
    return data
