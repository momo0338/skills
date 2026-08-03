"""audio/voice.py — P3 配音：CosyVoice TTS + Seed-VC 换声（WP3）。

忠实复刻原项目 tts_segments.py / vc_segments.py 的算法，仅做冻结期改造：
1. 密钥/路径一律走 ``dy_fanpai.config.Config``（不再 ``from config import *``）。
2. 确定性函数（apply_pron_fix / parse_speakers / resolve_target / seedvc_status /
   cosyvoice_status）与重型 subprocess（synth / convert）解耦，便于离线单测；
   synth/convert 要 CosyVoice/Seed-VC 真实环境，不在单测范围。

业务铁律（必须保留）：
- 读音修正**只作用于喂 CosyVoice 的文本**，不改字幕/台词（音频与字幕解耦，字幕后期用正字）。
- 海参场景：几乎所有「参」读 shēn，但 wetext 易误读 cān → 全量 参→身（同音同调 shēn，
  字数不变），用 CAN_WORDS 黑名单保护少数 cān/cēn 词。控制字符占位（绝不用裸数字，
  台词里全是价格数字）。
- 台词与音频逐字一致 → 口播段口型才准。
"""

from __future__ import annotations

import glob
import json
import os
import re
import subprocess
import sys

from ..config import Config

# 默认 CosyVoice 家目录（与 config.cosyvoice_home 默认值一致，仅 synth 用）
_DEFAULT_COSY_HOME = os.path.expanduser("~/CosyVoice")
VDIR = f"{_DEFAULT_COSY_HOME}/asset/voices"
# A(女主播)默认音色：香香；B(闺蜜挑衅/画外音)默认音色：依秋（忠实保留原文件名语义）
DEF_REF = f"{VDIR}/香香（女）上身有堆叠感，有余量感，穿上去慵懒又宽松，像主播这样子.wav"
DEF_REF_TEXT = "上身有堆叠感，有余量感，穿上去慵懒又宽松，像主播这样子"
DEF_A_REF = f"{VDIR}/依秋（女）都可以去呃，条款看一下，你可以点开咱们那个一号链接，下面有咱们.wav"
DEF_A_TEXT = "都可以去呃，条款看一下，你可以点开咱们那个一号链接，下面有咱们"

# 读音修正黑名单：被「参→身」全量替换前先占位保护的 cān/cēn 词（顺序无关，apply 时按长词优先）
CAN_WORDS = ["参加", "参与", "参考", "参观", "参谋", "参军", "参赛", "参展", "参数",
             "参照", "参差", "参悟", "参禅", "参政", "参议", "参股", "参保"]

# 内置干净音色目录（随包分发，真人声纹不进 git）
BUILTIN_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "voices")
DEFAULT_BUILTIN = "内置女声1_古丽"


def apply_pron_fix(text: str, extra: dict[str, str] | None = None, haishen: bool = True) -> str:
    """喂 CosyVoice 前的读音修正（确定性）。

    1) 先按自定义词表替换（长词优先）；
    2) 保护 cān/cēn 词（CAN_WORDS），用控制字符占位；
    3) 全量 参(shēn) → 身(shēn 同音同调，字数不变)；
    4) 还原被保护的词。
    haishen=False 时跳过 参→身 全量替换（只用自定义词表）。
    """
    # 1) 先按自定义词表替换(长词优先)
    if extra:
        for k in sorted(extra, key=len, reverse=True):
            text = text.replace(k, extra[k])
    if not haishen:
        return text
    # 2) 保护 cān/cēn 词
    holders: dict[str, str] = {}
    for i, w in enumerate(CAN_WORDS):
        if w in text:
            h = f"\x01{i}\x02"
            holders[h] = w
            text = text.replace(w, h)  # 控制字符占位,绝不能用裸数字(台词里全是价格数字)
    # 3) 全量 参(shēn) → 身(shēn 同音同调,单字不变长度)
    text = text.replace("参", "身")
    # 4) 还原被保护的词
    for h, w in holders.items():
        text = text.replace(h, w)
    return text


_SP_DELIM = re.compile(r"([A-Z甲乙丙])[：:]")


def parse_speakers(text: str, default: str = "B") -> list[tuple[str, str]]:
    """按说话人标签(A：/B：/甲：)拆句，返回 [(说话人, 文本)..]。无标签→整段 default。"""
    parts = _SP_DELIM.split(text)
    res: list[tuple[str, str]] = []
    if parts[0].strip():
        res.append((default, parts[0].strip()))
    for i in range(1, len(parts) - 1, 2):
        spk, txt = parts[i], parts[i + 1].strip()
        if txt:
            res.append((spk, txt))
    return res or [(default, text)]


def builtin_voices_dir() -> str:
    """内置音色目录（随包）。"""
    return BUILTIN_DIR


def resolve_target(target: str | None, builtin_dir: str | None = None) -> str:
    """--target 三种给法：wav 路径 / 内置音色名(如'内置男声1_广智'或'男声') / 空=默认内置女声。

    素材收集阶段应优先向用户要干净参考(≥30dB)；不给才落到内置。
    找不到时抛 ValueError（库代码不 sys.exit，便于上层 doctor/编排捕获）。
    """
    bdir = builtin_dir or BUILTIN_DIR
    if not target:
        target = DEFAULT_BUILTIN
    if os.path.exists(target):
        return target
    cands = sorted(glob.glob(os.path.join(bdir, "*.wav")))
    hits = [c for c in cands if target in os.path.basename(c)]
    if hits:
        return hits[0]
    names = [os.path.splitext(os.path.basename(c))[0] for c in cands]
    raise ValueError(f"[vc] 找不到音色参考 {target};内置可选: {names}")


def seedvc_status(home: str) -> tuple[bool, str]:
    """给 doctor 用：返回 (ok, 说明)。"""
    py = os.path.join(home, ".venv", "bin", "python")
    if not os.path.isdir(home):
        return False, (
            "Seed-VC 未装(可选,换声不换演用) → 装法: VPS中转下载 Plachtaa/seed-vc 到 ~/seed-vc,"
            "python3 -m venv .venv && .venv/bin/pip install -i 清华源 -r requirements.txt"
        )
    if not os.path.exists(py):
        return False, f"Seed-VC 在 {home} 但缺 .venv → 进目录建venv装requirements"
    return True, f"Seed-VC 就位({home})"


def cosyvoice_status(cfg: Config) -> tuple[bool, str]:
    """给 doctor 用：返回 CosyVoice 就位情况。"""
    home = cfg.cosyvoice_home
    py = os.path.join(home, ".venv", "bin", "python")
    script = cfg.tts_drama_script
    if not os.path.isdir(home):
        return False, f"CosyVoice 未装(可选,TTS 用) → {home}"
    if not os.path.exists(py):
        return False, f"CosyVoice 在 {home} 但缺 .venv"
    if not os.path.exists(script):
        return False, f"tts-drama 脚本缺失: {script}"
    return True, f"CosyVoice 就位({home})"


# ---------------------------------------------------------------------------
# 以下为重型 subprocess（需 CosyVoice / Seed-VC 真实环境），不在单测范围
# ---------------------------------------------------------------------------
def synth(plan_path, out_dir, voices, instruct, cfg: Config, pron_fix_path=None,
          default_spk="B", pron_profile="auto"):
    """voices: {说话人: {ref, ref_text}}。段内可含多说话人(A：/B：),分别合成再拼。

    pron_profile: auto=台词出现"海参"才启用参→身修正 | haishen=强制 | off=只用自定义词表
    """
    segs = json.load(open(plan_path, encoding="utf-8"))
    os.makedirs(out_dir, exist_ok=True)
    extra = json.load(open(pron_fix_path, encoding="utf-8")) if pron_fix_path and os.path.exists(pron_fix_path) else None
    all_d = "".join(s.get("dialogue") or "" for s in segs)
    haishen = (pron_profile == "haishen") or (pron_profile == "auto" and "海参" in all_d)
    if haishen:
        print("[tts] 海参读音修正已启用(参→身,CAN词黑名单保护)")
    lines, fixed_any, seg_subs = [], [], {}
    for s in segs:
        d = (s.get("dialogue") or "").strip()
        if not d:
            continue
        subs = parse_speakers(d, default_spk)
        ids = []
        for j, (spk, txt) in enumerate(subs):
            if spk not in voices:
                spk = default_spk
            t2 = apply_pron_fix(txt, extra, haishen)  # ★读音修正
            if t2 != txt:
                fixed_any.append(s["seg"])
            sid = f"{s['seg']}__{j}"
            lines.append({"id": sid, "voice": spk, "instruct": instruct, "text": t2})
            ids.append((sid, spk, txt))  # txt=正字原文(字幕用),t2=读音修正后(只喂TTS)
        seg_subs[s["seg"]] = ids
    if fixed_any:
        print(f"[tts] 读音修正生效于段: {sorted(set(fixed_any))}")
    if not lines:
        print("[tts] 无台词段")
        return
    manifest = {"voices": {k: {"ref": v["ref"], "ref_text": v.get("ref_text", "")} for k, v in voices.items()},
                "lines": lines}
    mf = os.path.join(out_dir, "_tts_manifest.json")
    json.dump(manifest, open(mf, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    spk_note = "多说话人" if any(len(v) > 1 for v in seg_subs.values()) else "单说话人"
    print(f"[tts] {len(lines)}句/{len(seg_subs)}段({spk_note}) → {out_dir}", flush=True)
    cosy_py = os.path.join(cfg.cosyvoice_home, ".venv", "bin", "python")
    r = subprocess.run([cosy_py, cfg.tts_drama_script, mf, out_dir], capture_output=True, text=True)
    print(r.stdout[-600:])
    if r.returncode != 0:
        print("[tts][ERR]", r.stderr[-500:])
        return
    # 句级时长 → timing.json(句级粗对齐;合并前量,单句段合并会 move 掉子 wav)
    timing = {}
    for seg, subids in seg_subs.items():
        rows = []
        for sid, spk, txt in subids:
            w = os.path.join(out_dir, f"{sid}_{spk}.wav")
            if os.path.exists(w):
                d = float(subprocess.check_output(
                    ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                     "-of", "csv=p=0", w]).strip())
                rows.append({"speaker": spk, "text": txt, "dur": round(d, 3)})
        if rows:
            timing[seg] = rows
    json.dump(timing, open(os.path.join(out_dir, "timing.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"[tts] 句级时长 → {os.path.join(out_dir, 'timing.json')}({sum(len(v) for v in timing.values())}句)")
    # 每段: 把子句 wav(<sid>_<spk>.wav)按顺序拼成 <seg>.wav
    for seg, subids in seg_subs.items():
        subwavs = [os.path.join(out_dir, f"{sid}_{spk}.wav") for sid, spk, _ in subids]
        subwavs = [w for w in subwavs if os.path.exists(w)]
        dst = os.path.join(out_dir, f"{seg}.wav")
        if len(subwavs) == 1:
            os.replace(subwavs[0], dst)
        elif len(subwavs) > 1:
            lst = os.path.join(out_dir, f"_{seg}_cat.txt")
            open(lst, "w").write("\n".join(f"file '{w}'" for w in subwavs))
            subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", lst,
                            "-c", "copy", dst, "-loglevel", "error"])
    ok = [seg for seg in seg_subs if os.path.exists(os.path.join(out_dir, f"{seg}.wav"))]
    print(f"[tts] 完成 {len(ok)}/{len(seg_subs)} 段: {ok}")


def convert(audio_dir, target, out_dir, cfg: Config, steps=30, f0=False, only=None):
    """换声不换演：原片切段音频逐段转目标音色（内容/节奏/停顿保留，只换嗓子）。"""
    ok, msg = seedvc_status(cfg.seedvc_home)
    if not ok:
        sys.exit(f"[vc] {msg}")
    seedvc_py = os.path.join(cfg.seedvc_home, ".venv", "bin", "python")
    target = resolve_target(target)
    # 参考体检:VC 会把参考的环境底噪学进产物,先量信噪比
    try:
        r = subprocess.run([seedvc_py, "-c", (
            "import librosa,numpy as np,sys;"
            "y,sr=librosa.load(sys.argv[1],sr=16000);"
            "rms=librosa.feature.rms(y=y,frame_length=512,hop_length=256)[0];"
            "f=np.percentile(rms,10);s=np.percentile(rms,90);"
            "print(round(20*np.log10(s/max(f,1e-6))))"), target],
            capture_output=True, text=True, timeout=120)
        snr = int(r.stdout.strip())
        note = "干净" if snr >= 30 else ("偏脏,底噪会转进产物,建议换更干净的参考" if snr >= 25 else "很脏,强烈建议换参考")
        print(f"[vc] 参考信噪比≈{snr}dB({note})")
    except Exception:
        pass  # 体检失败不拦路
    os.makedirs(out_dir, exist_ok=True)
    env = dict(os.environ, HF_ENDPOINT="https://hf-mirror.com")  # 模型自动下载走国内镜像
    for p in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY", "all_proxy", "ALL_PROXY"):
        env.pop(p, None)  # hf-mirror 是国内站,必须直连
    wavs = sorted(glob.glob(os.path.join(audio_dir, "*.wav")))
    wavs = [w for w in wavs if not os.path.basename(w).startswith("_")]
    if only:
        keep = set(only.split(","))
        wavs = [w for w in wavs if os.path.splitext(os.path.basename(w))[0] in keep]
    if not wavs:
        sys.exit(f"[vc] {audio_dir} 下没有可转换的 wav")
    print(f"[vc] {len(wavs)} 段 → 目标音色 {os.path.basename(target)} (steps={steps})")
    fails = []
    for w in wavs:
        name = os.path.splitext(os.path.basename(w))[0]
        dst = os.path.join(out_dir, f"{name}.wav")
        if os.path.exists(dst):
            print(f"  [skip] {name}(已存在)")
            continue
        tmp = os.path.join(out_dir, f"_tmp_{name}")
        os.makedirs(tmp, exist_ok=True)
        r = subprocess.run(
            [seedvc_py, "inference.py", "--source", os.path.abspath(w),
             "--target", os.path.abspath(target), "--output", os.path.abspath(tmp),
             "--diffusion-steps", str(steps), "--f0-condition", str(f0)],
            cwd=cfg.seedvc_home, capture_output=True, text=True, env=env, timeout=1800)
        outs = glob.glob(os.path.join(tmp, "vc_*.wav"))
        if r.returncode != 0 or not outs:
            fails.append(name)
            print(f"  [FAIL] {name}: {(r.stderr or '')[-200:]}")
        else:
            import shutil
            shutil.move(outs[0], dst)
            print(f"  ✓ {name}")
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)
    done = len(wavs) - len(fails)
    print(f"[vc] 完成 {done}/{len(wavs)}" + (f",失败: {fails}" if fails else "") +
          f" → {out_dir}(assemble/deliver 用 --audio-dir 指过来)")
