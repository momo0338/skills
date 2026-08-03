"""reverse/kimi.py — 双反推第二腿（Kimi K3 原生视频）。

与 seed.py 同契约:输入视频 → 同一套 ffmpeg 硬切 → K3 原生视频分析 → 输出同
schema 的 shotlist json。供 merge.py 与 Seed 结果合并裁决。

07-19 对决实证的 K3 脾性(prompt 里针对性加了实体纪律):
  强项=运镜时序(绕拍/机位/跳剪时间线);弱项=实体幻觉(性别人数/物体/编造陈列细节)。
合并裁决时本腿产物的实体描述一律存疑,以 Seed 为准。

接口(platform.kimi.com 文档):files.create(purpose="video") → ms://<file-id>;
K3 始终开思考(reasoning_effort 仅 max),流式响应分 reasoning_content/content 两路,
只收 content。api.moonshot.cn 国内直连不走代理。慢(全程思考),必后台跑。

依赖: ffmpeg/ffprobe（detect_cuts/video_info/make_upload_clip 复用 seed）、
requests（upload/k3_call 用）。
"""

from __future__ import annotations

import json
import os
import time

import requests

from ..config import Config
from .seed import SCHEMA, detect_cuts, extract_json, make_upload_clip, video_info

NO_PROXY: dict[str, str | None] = {"http": None, "https": None}


def _headers(cfg: Config) -> dict[str, str]:
    return {"Authorization": f"Bearer {cfg.require_key('kimi_api_key')}"}


def upload_video(clip_path: str, cfg: Config) -> str:
    """files API 上传视频 → file id。"""
    with open(clip_path, "rb") as f:
        r = requests.post(
            f"{cfg.kimi_base_url}/files",
            headers=_headers(cfg),
            files={"file": (os.path.basename(clip_path), f, "video/mp4")},
            data={"purpose": "video"},
            proxies=NO_PROXY,  # pyright: ignore[reportArgumentType]
            timeout=(10, 300),
        )
    if r.status_code != 200:
        raise RuntimeError(f"上传失败 HTTP {r.status_code}: {r.text[:300]}")
    return r.json()["id"]


def delete_file(fid: str, cfg: Config) -> None:
    try:
        requests.delete(
            f"{cfg.kimi_base_url}/files/{fid}",
            headers=_headers(cfg),
            proxies=NO_PROXY,  # pyright: ignore[reportArgumentType]
            timeout=(10, 60),
        )
    except Exception:
        pass


def build_prompt(cuts: list[float], duration: float) -> str:
    """构造 K3 反推 Prompt。在 Seed 的 7 条基础上新增:
    - 第 3 条补「段内运镜变化带时间点」;
    - 第 8 条实体纪律(性别人数逐人核对、不脑补陈列、屏上文字逐字抄)。"""
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
        f"3.action 要把主体+动作都写全(如'一只手把海参掰开'而非'海参剖面'),"
        f"段内的运镜变化(绕拍/机位移动/跳剪)带上大致时间点。"
        f"4.product_role 判断要准(剖面/参刺/弹性这类真实质感判 hero_real,包装盒判 package_text)。"
        f"5.材质/颜色写死。只描述不评判。"
        f"6.台词只收录真实人声:只出现在字幕/花字上而无对应人声的文字(短视频开头常有静音字幕残留),"
        f"只进 onscreen_text,严禁写进 dialogue 和 full_transcript。"
        f"7.onscreen_text 逐句原样采集屏上每条字幕/花字(保留自动字幕的错字),句间用;分隔。"
        f"8.实体纪律:人物性别/人数逐人核对,看不清就写'看不清',严禁按穿着推断;"
        f"背景物件的数量/颜色/种类只写画面确凿可见的,不要脑补补全陈列;屏上文字逐字抄不要改字。"
    )


def k3_call(fid: str, prompt: str, cfg: Config, timeout: int = 1200) -> tuple[str, float]:
    """K3 chat.completions 流式,只收 content(思考流丢弃)。连接抖动自动重试。"""
    body = {
        "model": cfg.kimi_k3_model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "video_url", "video_url": {"url": f"ms://{fid}"}},
                    {"type": "text", "text": prompt},
                ],
            }
        ],
        "stream": True,
    }
    t0 = time.time()
    resp: requests.Response | None = None
    for attempt in range(3):  # WSL 新建 TLS 连接偶发抖动,连接失败重试
        try:
            resp = requests.post(
                f"{cfg.kimi_base_url}/chat/completions",
                headers={**_headers(cfg), "Content-Type": "application/json"},
                json=body,
                proxies=NO_PROXY,  # pyright: ignore[reportArgumentType]
                timeout=(20, timeout),
                stream=True,
            )
            break
        except (requests.ConnectionError, requests.exceptions.ConnectTimeout) as e:
            if attempt == 2:
                raise
            print(
                f"[k3_reverse] 连接抖动({type(e).__name__}),{5 * (attempt + 1)}s后重试…", flush=True
            )
            time.sleep(5 * (attempt + 1))
    if resp is None:
        raise RuntimeError("[k3_reverse] 三次重试后仍无法建立连接")
    r = resp
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
        for ch in ev.get("choices", []):
            c = (ch.get("delta") or {}).get("content")
            if c:
                txt += c
    return txt, round(time.time() - t0, 1)


def reverse(
    video: str,
    out: str | None = None,
    cuts: list[float] | None = None,
    scene_thresh: float = 0.15,
    scale: int = 480,
    timeout: int = 1200,
    cfg: Config | None = None,
) -> dict:
    """K3 单反推主入口(编排层;网络调用在 upload_video/k3_call)。"""
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
        f"[k3_reverse] {vi['duration']}s {vi['width']}x{vi['height']} | "
        f"{len(cuts)}硬切 | clip {os.path.getsize(clip) // 1024}KB",
        flush=True,
    )
    fid = upload_video(clip, cfg)
    print(f"[k3_reverse] 上传完成 file={fid},K3 思考中(全程开思考,慢)…", flush=True)
    try:
        raw, secs = k3_call(fid, build_prompt(cuts, vi["duration"]), cfg, timeout)
    finally:
        delete_file(fid, cfg)
    print(f"[k3_reverse] K3 返回 {len(raw)}字 / {secs}s", flush=True)
    data = extract_json(raw)
    data.setdefault("video_info", vi)
    data["cuts"] = cuts
    out = out or os.path.join(workdir, "shotlist_k3.json")
    json.dump(data, open(out, "w"), ensure_ascii=False, indent=2)
    print(f"[k3_reverse] {len(data.get('shots', []))} 镜 → {out}", flush=True)
    return data
