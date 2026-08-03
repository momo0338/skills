"""reverse/merge.py — 双反推合并器(证据准备,不做终审)。

背景(07-19 K3 vs Seed2.1Pro 对决结论):两家反推错误呈镜像——
  Seed 病 = 时序粗+模态混淆(静音字幕写进台词/漏机位调度);
  K3   病 = 实体幻觉(性别人数/物体认错/无中生有的陈列细节)。
故双反推合并的价值在"按验证过的分工裁决",本脚本只做机械部分:
  时间对齐 + 逐镜并排卡 + 分歧信号灯 + 分歧点自动抽帧 + 静音闸,
  终审由 agent 看着 dossier.md 与 frames/ 裁决,改 merged_draft.json 定稿。

裁决铁律(写进 dossier 头部):
  实体(人物性别人数/物体/颜色/屏上文字) → Seed 优先;
  运镜时序(绕拍/机位/跳剪/段内时间点)   → K3(alt) 优先;
  互斥分歧 → 看 frames/ 帧证据当庭对质;
  落在静音区的文字 → 只进 onscreen_text,严禁进台词(治幻听)。

重构说明(WP2):把原单文件 main() 拆成确定性核心 `build_merged`(纯函数,只依赖
传入的 sil/first_speech/dur,离线可单测)与 `merge` 编排层(跑 ffmpeg 取静音/抽帧)。
"""

from __future__ import annotations

import json
import os
import re
import subprocess

CAM_KW = re.compile(r"绕|摇|移|侧机位|跳剪|推[近进]|拉[远]|跟拍|机位|背拍|回正")
FIELDS = [
    "shot_size",
    "camera",
    "subject",
    "action",
    "scene",
    "lighting",
    "person",
    "host_on_camera",
    "product_in_frame",
    "product_role",
    "onscreen_text",
    "dialogue",
    "key_colors",
]


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True)


def silence_spans(video: str) -> list[tuple[float, float]]:
    """ffmpeg silencedetect → [(start,end)] 静音区间。"""
    r = _run(["ffmpeg", "-i", video, "-af", "silencedetect=n=-30dB:d=0.35", "-f", "null", "-"])
    starts = [float(x) for x in re.findall(r"silence_start: ([0-9.]+)", r.stderr)]
    ends = [float(x) for x in re.findall(r"silence_end: ([0-9.]+)", r.stderr)]
    spans = list(zip(starts, ends))
    if len(starts) == len(ends) + 1:  # 收尾静音无 end
        spans.append((starts[-1], 1e9))
    return spans


def speech_overlap(lo: float, hi: float, sil: list[tuple[float, float]]) -> float:
    """[lo,hi] 内非静音时长。"""
    silent = sum(max(0.0, min(hi, e) - max(lo, s)) for s, e in sil)
    return max(0.0, (hi - lo) - silent)


def ts_in_text(text: str, lo: float, hi: float) -> list[float]:
    """从描述文本里抠时间点(约37~39s / 52s 这类),限定在镜头区间内。"""
    out: set[float] = set()
    for m in re.finditer(r"(\d{1,3}(?:\.\d+)?)?\s*[s秒]", text or ""):
        out.add(float(m.group(1)))
    for m in re.finditer(r"(\d{1,3}(?:\.\d+)?)\s*[~～\-]\s*(\d{1,3}(?:\.\d+)?)", text or ""):
        out.update([float(m.group(1)), float(m.group(2))])
    return sorted(t for t in out if lo - 0.5 <= t <= hi + 0.5)


def gender_sig(person: str) -> tuple[int, int]:
    """性别计数签名,用于分歧信号灯。"""
    p = person or ""
    return (p.count("男"), p.count("女"))


def grab(video: str, t: float, dst: str) -> None:
    if not os.path.exists(dst):
        _run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-ss",
                str(round(t, 2)),
                "-i",
                video,
                "-frames:v",
                "1",
                "-q:v",
                "2",
                dst,
                "-y",
            ]
        )


def _first_speech(sil: list[tuple[float, float]]) -> float:
    """首个人声出现时间 = 连续首部静音之后的时间点。"""
    t = 0.0
    for s0, e0 in sorted(sil):
        if s0 <= t + 0.05:
            t = e0
        else:
            break
    return round(t, 2)


def build_merged(
    seed: dict, alt: dict, sil: list[tuple[float, float]], dur: float, alt_name: str = "K3"
) -> tuple[dict, list[str], list[float], int]:
    """确定性合并核心。返回 (merged_draft, dossier_lines, frame_ts, n_warns)。

    merged_draft = Seed 实体基底 + __alt_* 字段(K3 运镜时序候选);agent 裁决后吸收
    或删除全部 __alt_* 字段即为定稿 shotlist.json。纯函数,不碰 ffmpeg。
    """
    first_speech = _first_speech(sil)
    md = [
        f"# 双反推合并卷宗 — Seed(基底) vs {alt_name}(alt)",
        "",
        "**裁决铁律**:实体(性别人数/物体/颜色/屏字)→Seed优先;运镜时序(绕拍/机位/跳剪/段内时间点)→"
        f"{alt_name}优先;互斥分歧→看 frames/ 帧证据;静音区文字只进 onscreen_text 严禁进台词。",
        f"**静音闸**:首个人声出现于 **{first_speech}s**;静音区间(>0.35s):"
        + "、".join(f"{s:.2f}-{min(e, dur):.2f}" for s, e in sil)
        + "。",
        "",
    ]

    warns: list[str] = []
    frame_ts: set[float] = set()
    merged = json.loads(json.dumps(seed))  # 深拷贝,Seed 为基底
    merged["_merge_note"] = (
        "骨架稿:实体=Seed基底,__alt_*=候选运镜时序,"
        "agent 裁决后吸收有效信息并删除全部 __alt_* 字段即为定稿"
    )
    ov_alt = alt.get("overall", {})
    merged["__alt_overall"] = {
        k: ov_alt.get(k, "") for k in ("product", "style", "why_viral", "full_transcript")
    }

    for i, ss in enumerate(merged["shots"]):
        lo, hi = float(ss["start"]), float(ss["end"])
        hits = [
            t2
            for t2 in alt.get("shots", [])
            if min(hi, float(t2["end"])) - max(lo, float(t2["start"])) > 0.05
        ]
        subcuts = sorted(
            {
                round(float(t2["start"]), 2)
                for t2 in hits
                if lo + 0.3 < float(t2["start"]) < hi - 0.3
            }
        )
        ss["__alt_camera"] = " || ".join(t2.get("camera", "") for t2 in hits)
        ss["__alt_action"] = " || ".join(t2.get("action", "") for t2 in hits)
        ss["__alt_transition_in"] = hits[0].get("transition_in", "") if hits else ""
        if subcuts:
            ss["__alt_subcuts"] = subcuts

        md.append(
            f"## 镜{ss['shot_id']} [{lo:.2f}-{hi:.2f}] "
            f"(alt对应{len(hits)}镜{'+内部切点' + str(subcuts) if subcuts else ''})"
        )
        for f in FIELDS:
            sv = str(ss.get(f, ""))
            av = " || ".join(str(t2.get(f, "")) for t2 in hits)
            mark = ""
            if f == "person" and hits and gender_sig(sv) != gender_sig(av):
                mark = " ⚑性别/人数分歧"
            if f in ("camera", "action"):
                s_has, a_has = bool(CAM_KW.search(sv)), bool(CAM_KW.search(av))
                if s_has != a_has:
                    mark = f" ⚑运镜仅{'Seed' if s_has else alt_name}提及"
            if sv.strip() == av.strip():
                md.append(f"- {f}: (一致) {sv[:120]}")
            else:
                md.append(f"- {f}:{mark}\n  - SEED: {sv[:300]}\n  - {alt_name}: {av[:300]}")
        # ── 静音闸
        if ss.get("dialogue") and speech_overlap(lo, hi, sil) < 0.5:
            w = (
                f"镜{ss['shot_id']} 有台词但区间基本全静音 → 疑字幕残留被当口播,"
                f"台词应移入 onscreen_text"
            )
            warns.append(w)
            md.append(f"- ⚠️ **静音闸**: {w}")
        if lo < first_speech and ss.get("dialogue"):
            md.append(f"- ⚠️ **静音闸**: 本镜起点早于首个人声({first_speech}s),开头台词需帧证核对")
        # ── 抽帧点
        pts = {lo + 0.15, (lo + hi) / 2, max(lo, hi - 0.3)}
        pts.update(subcuts)
        pts.update(ts_in_text(ss.get("action", ""), lo, hi))
        pts.update(ts_in_text(ss.get("__alt_action", ""), lo, hi))
        frame_ts.update(round(min(max(p, 0.03), dur - 0.1), 2) for p in pts)
        md.append(
            "- 帧证据: " + " ".join(f"frames/t{p:06.2f}.jpg" for p in sorted(pts)[:12]) + "\n"
        )

    if warns:
        md.insert(4, "**⚠️ 静音闸警告**:\n" + "\n".join(f"- {w}" for w in warns) + "\n")
    return merged, md, sorted(frame_ts), len(warns)


def merge(
    seed_json: str,
    alt_json: str,
    video: str,
    outdir: str | None = None,
    alt_name: str = "K3",
    max_frames: int = 80,
) -> dict:
    """编排层:读两个反推 JSON + 原片 → 写 dossier.md / merged_draft.json / 抽帧。"""
    seed = json.load(open(seed_json))
    alt = json.load(open(alt_json))
    outdir = outdir or os.path.join(os.path.dirname(os.path.abspath(seed_json)), "merge")
    fdir = os.path.join(outdir, "frames")
    os.makedirs(fdir, exist_ok=True)

    sil = silence_spans(video)
    dur = seed.get("video_info", {}).get("duration") or max(float(s["end"]) for s in seed["shots"])

    merged, md, frame_ts, n_warns = build_merged(seed, alt, sil, dur, alt_name)
    frame_ts = frame_ts[:max_frames]
    for p in frame_ts:
        grab(video, p, os.path.join(fdir, f"t{p:06.2f}.jpg"))

    open(os.path.join(outdir, "dossier.md"), "w").write("\n".join(md))
    json.dump(
        merged, open(os.path.join(outdir, "merged_draft.json"), "w"), ensure_ascii=False, indent=2
    )
    print(
        f"[merge_reverse] {len(merged['shots'])}镜对照 | {len(frame_ts)}帧证据 | "
        f"{n_warns} 条静音闸警告 → {outdir}/dossier.md"
    )
    print(
        "[merge_reverse] 下一步:agent 按 dossier.md 铁律裁决,吸收并删除 "
        "merged_draft.json 的 __alt_* 字段 → 定稿 shotlist.json"
    )
    return merged
