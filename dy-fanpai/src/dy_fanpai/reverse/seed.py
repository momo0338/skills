"""reverse/seed.py — 反推引擎腿 1（Ark Seed 2.1 Pro 原生视频）。

忠实复刻原项目 seed_reverse.py 的算法与 Prompt，仅做两处冻结期要求的改造：
1. 密钥/模型一律走 `dy_fanpai.config.Config`（不再 `from config import ark_key`）。
2. 确定性函数（detect_cuts / video_info / make_upload_clip / extract_json /
   build_prompt）与网络调用（ark_reverse）解耦，便于离线单测；网络调用仅在
   live 模式下、经 `cfg.require_key("ark_api_key")` 取密钥后发生。

业务规则（WP1 DESIGN §12 裁决，必须保留）：
- `detect_cuts` 默认阈值冻结为 **0.15**（经验证抓同机位跳剪）。
- 国内 Ark endpoint **绝不走代理**（`NO_PROXY`）。
- thinking 关、流式 —— 快且精度不掉。
- 台词只收录真实人声；静音字幕残留只进 onscreen_text，严禁进 dialogue。

依赖: ffmpeg/ffprobe（detect_cuts/video_info/make_upload_clip 用）、requests（ark_reverse 用）。
"""

from __future__ import annotations

import base64
import json
import os
import re
import subprocess
import time

import requests

from ..config import Config

ARK_URL = "https://ark.cn-beijing.volces.com/api/v3/responses"
# 火山国内 endpoint，绝不走代理（原项目硬编码 NO_PROXY，WP1 冻结保留）
NO_PROXY: dict[str, str | None] = {"http": None, "https": None}

# 分镜表 schema —— 复刻管线下游消费的字段（与 kimi 腿共用，保证双反推同构）
SCHEMA = """{
 "overall": {
   "product": "原片产品是什么形态(逐组件写死材质/颜色/形状)",
   "style": "整体风格/色调/场景",
   "narrative_arc": "带货叙事主线一句话",
   "why_viral": "前3秒钩子机制",
   "full_transcript": "全片台词逐字转写"
 },
 "shots": [{
   "shot_id": 1, "start": 0.0, "end": 0.0,
   "is_opening_3s": false,
   "shot_size": "特写/近景/中景/远景",
   "camera": "固定/推/拉/摇/移/跟 + 速度",
   "subject": "主体是谁/什么 + 画面位置",
   "action": "具体动作(力学级,主体+动作都要带全,别只写结果)",
   "scene": "环境",
   "lighting": "光线方向/冷暖/明暗",
   "person": "有无真人+谁(主播/质检员等)+穿着",
   "host_on_camera": "布尔:有完整真人出镜说话=true;仅露手/仅背影/无人=false(决定口播还是真图路由,判准)",
   "product_in_frame": "产品如何出现(无/手持/桌面/特写/使用中/包装/成品)+占比",
   "product_role": "none(无产品) | dynamic(产品动态主体,质感不必极真) | hero_real(产品真实质感特写,如剖面/参刺/弹性,AI易翻车需真图锚定) | package_text(包装且文字需清晰,建议后期贴图)",
   "onscreen_text": "屏上所有贴字原文,无则空",
   "dialogue": "该镜对应台词(按时间对齐),无则空",
   "key_colors": "画面关键物体颜色,尤其液体/产品颜色(这个字段帮你别漏爆点细节)"
 }]
}"""


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True)


def detect_cuts(video: str, thresh: float = 0.15) -> list[float]:
    """ffmpeg 场景检测 → 硬切时间点列表。

    默认阈值 0.15（WP1 冻结；实测 0.3 会漏检同机位跳剪）。返回 >0.3s 的切点，
    首帧噪声（<0.3s）已剔除。
    """
    r = _run(
        [
            "ffmpeg",
            "-i",
            video,
            "-filter:v",
            f"select='gt(scene,{thresh})',showinfo",
            "-f",
            "null",
            "-",
        ]
    )
    ts = [round(float(x), 2) for x in re.findall(r"pts_time:([0-9.]+)", r.stderr)]
    return [t for t in ts if t > 0.3]  # 去掉首帧噪声


def video_info(video: str) -> dict:
    """ffprobe → {duration, width, height}。"""
    r = _run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", video]
    )
    d = json.loads(r.stdout)
    v = [s for s in d["streams"] if s["codec_type"] == "video"][0]
    return {
        "duration": round(float(d["format"]["duration"]), 1),
        "width": v["width"],
        "height": v["height"],
    }


def make_upload_clip(video: str, scale: int, keep_audio: bool, workdir: str) -> str:
    """压成小体积供 base64 上传。"""
    out = os.path.join(workdir, "_seed_upload.mp4")
    vf = f"scale={scale}:-2"
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        video,
        "-vf",
        vf,
        "-c:v",
        "libx264",
        "-crf",
        "30",
        "-preset",
        "veryfast",
    ]
    cmd += ["-c:a", "aac", "-b:a", "48k"] if keep_audio else ["-an"]
    cmd += [out, "-loglevel", "error"]
    _run(cmd)
    return out


def build_prompt(cuts: list[float], duration: float) -> str:
    """构造 Seed 反推 Prompt（与 ark_reverse 共用，确定性）。"""
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
    )


def ark_reverse(
    clip_path: str, cuts: list[float], duration: float, cfg: Config, timeout: int = 600
) -> tuple[str, float]:
    """调 Seed 2.1 Pro 原生视频反推,返回 (原始文本, 耗时秒)。

    仅在 live 且已取密钥时调用;NO_PROXY 强制不走代理。
    """
    key = cfg.require_key("ark_api_key")
    model = cfg.ark_seed_model
    b64 = base64.b64encode(open(clip_path, "rb").read()).decode()
    prompt = build_prompt(cuts, duration)
    body = {
        "model": model,
        "input": [
            {
                "role": "user",
                "content": [
                    {"type": "input_video", "video_url": f"data:video/mp4;base64,{b64}"},
                    {"type": "input_text", "text": prompt},
                ],
            }
        ],
        "thinking": {"type": "disabled"},  # ★关键:关推理 → 快17倍,精度不掉
        "stream": True,
    }
    t0 = time.time()
    r = requests.post(
        ARK_URL,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json=body,
        proxies=NO_PROXY,  # pyright: ignore[reportArgumentType]
        timeout=(10, timeout),
        stream=True,
    )
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}: {r.text[:300]}")
    txt = ""
    for line in r.iter_lines():
        if not line:
            continue
        s = line.decode("utf-8", "ignore")
        if s.startswith("data:"):
            s = s[5:].strip()
        if s == "[DONE]":
            break
        try:
            ev = json.loads(s)
        except Exception:
            continue
        if ev.get("type", "").endswith("output_text.delta"):
            txt += ev.get("delta", "")
    return txt, round(time.time() - t0, 1)


def extract_json(txt: str) -> dict:
    """从模型原始输出里抠出 JSON 对象（兼容 ```json 围栏与前后噪点）。"""
    s = txt.strip()
    if s.startswith("```"):
        s = re.sub(r"^```\w*", "", s).rsplit("```", 1)[0].strip()
    a, b = s.find("{"), s.rfind("}")
    return json.loads(s[a : b + 1])


def reverse(
    video: str,
    out: str | None = None,
    cuts: list[float] | None = None,
    scene_thresh: float = 0.15,
    scale: int = 480,
    keep_audio: bool = True,
    timeout: int = 600,
    cfg: Config | None = None,
) -> dict:
    """Seed 单反推主入口。

    - 离线（无 key / dry）时不会调用 ark_reverse;本函数本身是编排层,确定性逻辑
      在 detect_cuts/video_info/make_upload_clip/build_prompt/extract_json 内。
    """
    cfg = cfg or Config.load()
    vi = video_info(video)
    if cuts is None:
        cuts = detect_cuts(video, scene_thresh)
    workdir = (
        os.path.dirname(os.path.abspath(out)) if out else os.path.dirname(os.path.abspath(video))
    )
    os.makedirs(workdir, exist_ok=True)
    clip = make_upload_clip(video, scale, keep_audio, workdir)
    print(
        f"[seed_reverse] {vi['duration']}s {vi['width']}x{vi['height']} | "
        f"{len(cuts)}硬切 | clip {os.path.getsize(clip) // 1024}KB",
        flush=True,
    )
    raw, secs = ark_reverse(clip, cuts, vi["duration"], cfg, timeout)
    print(f"[seed_reverse] Seed 2.1 Pro 返回 {len(raw)}字 / {secs}s", flush=True)
    data = extract_json(raw)
    data.setdefault("video_info", vi)
    data["cuts"] = cuts
    out = out or os.path.join(workdir, "shotlist.json")
    json.dump(data, open(out, "w"), ensure_ascii=False, indent=2)
    print(f"[seed_reverse] {len(data.get('shots', []))} 镜 → {out}", flush=True)
    return data
