"""planning/localization.py — B 模式本地化（WP2）。

两件事:
1. apply_edits:把本地化后的台词写回 segments.json(B模式,插在 plan 和 tts 之间)。
   agent 按 qianchuan/LOCALIZE.md 逐段改好台词 → 存成 edits.json {"S1":"新台词",...},
   本工具合并进 segments.json 的 dialogue 字段(口播段同时更新 prompt 里的 台词{...})。
   只改 dialogue,不动结构/路由/锚图。 ★离线可测。
2. rewrite:读 shotlist 源台词 + facts + qianchuan 弹药包 → 让 Seed2.1Pro 按千川方法论
   改写成目标产品口播文案。需要 Ark key(网络),离线不调用。

忠实复刻原项目 localize_apply.py / localize_seed.py。
"""

from __future__ import annotations

import json
import os
import re
import time

import requests

from ..config import Config

ARK_URL = "https://ark.cn-beijing.volces.com/api/v3/responses"
NO_PROXY: dict[str, str | None] = {"http": None, "https": None}

# 脚本改写相关的弹药包(按重要性)
QC_FILES = ["02-跨类目复制与机制.md", "01-选题与卖点.md", "03-句式库.md", "04-诊断rubric与红线.md"]


def apply_edits_dict(
    segs: list[dict], edits: dict[str, str]
) -> tuple[list[dict], list[str], list[str]]:
    """把 edits 合并进 segments(纯函数,返回 (新segs, changed行, missing段))。

    口播段(mm)提示词里的 台词{...} 也要同步替换,否则口型对不上音频。
    """
    changed, missing, seen = [], [], set()
    for s in segs:
        name = s["seg"]
        if name not in edits:
            continue
        seen.add(name)
        new = edits[name]
        old = s.get("dialogue", "")
        s["dialogue"] = new
        if s.get("type") == "mm" and "台词{" in s.get("prompt", ""):
            s["prompt"] = re.sub(r"台词\{[^}]*\}", "台词{" + new + "}", s["prompt"], count=1)
        d = len(new) - len(old)
        warn = (
            f"  (⚠字数{'+' if d >= 0 else ''}{d},配音时长会变,注意与镜时长)" if abs(d) > 8 else ""
        )
        changed.append(f"  {name}: {new[:40]}{warn}")
    for k in edits:
        if k not in seen:
            missing.append(k)
    return segs, changed, missing


def apply_edits(seg_path: str, edits_path: str, out_path: str | None = None) -> None:
    """文件版:读 segments.json + edits.json → 写回(默认覆盖原文件)。"""
    segs = json.load(open(seg_path, encoding="utf-8"))
    edits = json.load(open(edits_path, encoding="utf-8"))
    segs, changed, missing = apply_edits_dict(segs, edits)
    out_path = out_path or seg_path
    json.dump(segs, open(out_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"[localize] 更新 {len(changed)} 段 → {out_path}")
    for c in changed:
        print(c)
    if missing:
        print(f"[localize][警告] edits 里有 segments 中不存在的段: {missing}")


# --------------------------------------------------------------------------
# rewrite(网络,需 Ark key)
# --------------------------------------------------------------------------
def load_ammo(qc_dir: str) -> str:
    parts = []
    for f in QC_FILES:
        p = os.path.join(qc_dir, f)
        if os.path.exists(p):
            parts.append(f"# 【弹药包·{f}】\n{open(p, encoding='utf-8').read()}")
    return "\n\n".join(parts)


def call_seed(prompt: str, cfg: Config, timeout: int = 200) -> str:
    key = cfg.require_key("ark_api_key")
    model = cfg.ark_seed_model
    body = {
        "model": model,
        "input": [{"role": "user", "content": [{"type": "input_text", "text": prompt}]}],
        "thinking": {"type": "disabled"},
        "stream": True,
    }
    r = requests.post(
        ARK_URL,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json=body,
        proxies=NO_PROXY,  # pyright: ignore[reportArgumentType]
        timeout=(10, timeout),
        stream=True,
    )
    r.raise_for_status()
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
    return txt.strip()


def rewrite(
    shotlist_path: str,
    facts_path: str,
    out_path: str | None = None,
    qc_dir: str | None = None,
    cfg: Config | None = None,
) -> str:
    """B 模式脚本改写(Seed2.1Pro 起草,★真喂千川弹药包)。网络调用。"""
    cfg = cfg or Config.load()
    src = json.load(open(shotlist_path, encoding="utf-8"))["overall"].get("full_transcript", "")
    f = json.load(open(facts_path, encoding="utf-8"))
    qc_dir = qc_dir or os.path.join(os.path.dirname(__file__), "qianchuan")
    ammo = load_ammo(qc_dir)
    mode = f.get("mode", "同类目")
    mode_note = (
        "这是【跨类目】改写:只有说服结构/叙事节奏能复制,画面动作要理解后重构;"
        "别机械替换动词,要理解每个beat在说服什么再换成目标产品的自然表达。"
        if "跨" in mode
        else "这是【同类目】改写:结构一字不动,只换品牌/卖点/数字,字数贴原句。"
    )
    prompt = f"""你是千川带货爆款编导。严格按下面【千川方法论弹药包】改写口播文案,不是凭感觉写。

{ammo}

====================
【任务】把下面这条爆款口播,改写成卖【{f.get("product", "")}】的口播文案。
{mode_note}

原文案:
{src}

【必须遵守】
- 目标用户:{f.get("audience", "")};核心角度:{f.get("angle", "")}
- 产品事实(只用这些,别编):{f.get("facts", "")};品牌:{f.get("brand", "")}
- 活动/机制:{f.get("activity", "")}(参考弹药包02的买赠堆叠)
- 开头黄金3秒必须是弹药包03的三类句式之一(锚定对比/伪机制/指令式)
- 红线:{f.get("redlines", "")}(并守弹药包04合规红线)
- 保留原片说服结构和节奏,字数节奏尽量贴原文(便于套镜头时长)
只输出改写后的口播文案,一段,不要解释、不要标注用了哪个句式。"""
    print(
        f"[localize_seed] 弹药包 {len(ammo)}字 + 源台词 {len(src)}字 → Seed2.1Pro改写 ...",
        flush=True,
    )
    t0 = time.time()
    out = call_seed(prompt, cfg)
    out_path = out_path or os.path.join(
        os.path.dirname(os.path.abspath(shotlist_path)), "script.txt"
    )
    open(out_path, "w", encoding="utf-8").write(out)
    print(f"[localize_seed] {time.time() - t0:.0f}s → {out_path}\n")
    print(out)
    return out
