"""planning/planner.py — 生成方案规划(转换/迁移阶段,WP2)。

吃 reverse 产出的分镜表 JSON + 素材配置 →
  ① 把镜头按「≤12s 且 ≤3 内部硬切」归并成生成段
  ② 每段路由:口播(multimodal双图) / hero_real(真图image2video) / package(真图image2video)
  ③ 写即梦提示词(★把分镜表里的 subject+action 原样带进去,治"漏动作")
  ④ 完备性关卡:核对提示词是否带全了该镜的关键动作,漏了就标 WARN
  ⑤ 产出 segments.json(机器用) + segments.md(给人审)

忠实复刻原项目 plan_segments.py。冻结期裁决(WP1 DESIGN §12):
- 时长双标统一:`SEGMENT_MAX_DURATION=15`(拆分触发) / `SEGMENT_TARGET_DURATION=12`(归并目标)。
  本模块 `split_long_shots(max_dur=15)` 触发拆分;`group_shots` 用 `MAX_DUR=12` 归并。
  ⚠ 原项目 split_long_shots 形参 max_dur=15 但函数体用全局 MAX_DUR=12 计算 n ——
  此行为直接决定样本分段结果,务必保留(不要"顺手修")。
- FORM_MAP:planner 优先读 merged_form_map(cfg)(用户 assets 存在时),默认 FORM_MAP 仅回退。
- 纯 stdlib,无密钥依赖,可离线单测与 parity。

素材配置 assets.json 示例:
{
  "host_anchor": "assets/host_anchor.jpg",
  "product_desc": "高小参鲜蒸海参,深蓝金色包装",
  "products": {"hero":"assets/单只海参正面.jpg","hero_alt":"assets/单只海参背面.jpg",
               "礼盒":"assets/礼盒.png","内包装":"assets/内包装.png","单根":"assets/单根包装.png"}
}
"""

from __future__ import annotations

import json
import math
import re

# 规划层时长常量(WP1 DESIGN §12 裁决):统一为单值语义
SEGMENT_TARGET_DURATION = 12  # 归并目标份数(= MAX_DUR)
SEGMENT_MAX_DURATION = 15  # 单段触发拆分与硬上限(= split_long_shots 的 max_dur 触发线)

TAIL = "电影质感,真实生活感。保持无字幕,不要生成BGM或背景音乐,不要生成Logo,不要生成水印。"
MAX_DUR = SEGMENT_TARGET_DURATION  # 单段目标时长上限
MAX_CUTS = 3  # 单段最多归并 3 个镜头(=2 个内部硬切)


def _distribute(sents: list[str], n: int) -> list[str]:
    """把句子列表按字数尽量均匀分成 n 组。"""
    total = sum(len(x) for x in sents) or 1
    target = total / n
    groups, cur, cur_len = [], [], 0
    for s in sents:
        cur.append(s)
        cur_len += len(s)
        if cur_len >= target and len(groups) < n - 1:
            groups.append("".join(cur))
            cur, cur_len = [], 0
    groups.append("".join(cur))
    while len(groups) < n:
        groups.append("")
    return groups[:n]


def split_long_shots(shots: list[dict], max_dur: int = SEGMENT_MAX_DURATION) -> list[dict]:
    """超过 max_dur 的单个长镜 → 按句子边界拆成多个子段(1a/1b…),台词按字数分配。

    ⚠ 形参 max_dur=15 仅作触发线语义;函数体沿用全局 MAX_DUR=12 计算拆分份数 n,
    与原项目行为一致(直接决定样本分段),不可改。
    """
    out = []
    for s in shots:
        dur = s["end"] - s["start"]
        if dur <= max_dur:
            out.append(s)
            continue
        n = math.ceil(dur / MAX_DUR)
        sents = [x for x in re.split(r"(?<=[。！？!?，,])", s.get("dialogue", "") or "") if x]
        chunks = _distribute(sents, n)
        seglen = dur / n
        for i in range(n):
            ns = dict(s)
            ns["start"] = round(s["start"] + i * seglen, 2)
            ns["end"] = round(s["start"] + (i + 1) * seglen, 2)
            ns["dialogue"] = chunks[i]
            ns["shot_id"] = f"{s['shot_id']}{chr(97 + i)}"
            ns["_split"] = True
            out.append(ns)
    return out


def group_shots(shots: list[dict]) -> list[list[dict]]:
    """按 ≤MAX_DUR 且 ≤MAX_CUTS 把连续镜头归并成段。"""
    segs, cur = [], []
    for s in shots:
        if not cur:
            cur = [s]
            continue
        dur = s["end"] - cur[0]["start"]
        if dur > MAX_DUR or len(cur) >= MAX_CUTS:
            segs.append(cur)
            cur = [s]
        else:
            cur.append(s)
    if cur:
        segs.append(cur)
    return segs


def _host_on_camera(s: dict) -> bool:
    """有完整真人出镜吗?新版 shotlist 有结构化布尔字段 host_on_camera(可靠);
    旧版 shotlist 回退老口径:person 含「真人」子串。"""
    v = s.get("host_on_camera")
    if isinstance(v, bool):
        return v
    return "真人" in (s.get("person") or "")


def seg_role(shots: list[dict]) -> str:
    """段的主导类型:有人说话→口播; 否则看 product_role 多数。"""
    if any((s.get("dialogue") or "").strip() and _host_on_camera(s) for s in shots):
        return "kou"
    roles = [s.get("product_role", "") for s in shots]
    if any(r == "hero_real" for r in roles):
        return "hero"
    if any(r == "package_text" for r in roles):
        return "package"
    return "kou" if any((s.get("dialogue") or "").strip() for s in shots) else "dynamic"


# 产品/包装形态词 → products 键 的同义映射(反推文本里的说法可能和素材键不同)。
# 这是【默认表】:包装类词是通用的;hero 的默认词表偏生鲜(源自海参案例)。
# ★换产品时在 assets.json 加 "forms": {"键": ["别名",..]} 合并/新增——键可以是 products 里任何键。
FORM_MAP = [
    (["礼袋", "礼盒", "手提袋", "提袋", "礼品盒"], "礼盒"),
    (["内包装", "包装盒", "塑料盒", "保鲜盒", "盒装", "包装袋"], "内包装"),
    (["真空", "独立", "单根", "独立包装", "小包装"], "单根"),
    (["海参", "参刺", "剖面", "解冻", "肉质", "内筋", "底足", "产品特写", "裸品", "实物"], "hero"),
]


def merged_form_map(cfg: dict) -> list[tuple[list[str], str]]:
    """默认 FORM_MAP + assets.json 的 forms 字段(别名扩充/新形态键)。"""
    fm = [(list(w), k) for w, k in FORM_MAP]
    for key, aliases in (cfg.get("forms") or {}).items():
        for w, k in fm:
            if k == key:
                w.extend(a for a in aliases if a not in w)
                break
        else:
            fm.append((list(aliases), key))
    return fm


def _seg_text(shots: list[dict]) -> str:
    return " ".join(
        (s.get("product_in_frame", "") + s.get("action", "") + s.get("subject", "")) for s in shots
    )


def pick_product_anchors(
    shots: list[dict], products: dict, form_map: list[tuple[list[str], str]] | None = None
) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """★返回该段提示词提到的【所有】产品形态对应的图 [(label,path)..],不是只选一张。
    同时返回 missing: 提到了但用户没提供对应图的形态(→即梦会自由发挥,需报警)。"""
    text = _seg_text(shots)
    anchors, seen, missing = [], set(), []
    for words, key in form_map or FORM_MAP:
        if any(w in text for w in words):
            if key in products and key not in seen:
                anchors.append((key, products[key]))
                seen.add(key)
            elif key not in products and key != "hero":
                missing.append((words[0], key))
    if not anchors:  # 兜底 hero
        h = products.get("hero") or (next(iter(products.values())) if products else None)
        if h:
            anchors.append(("hero", h))
    return anchors[:4], missing  # multimodal 总图 ≤9(含主播),产品图控 4 张内


def build_kou_prompt(
    shots: list[dict],
    host: str,
    prod_desc: str,
    anchors: list[tuple[str, str]],
    host_desc: str = "",
) -> tuple[str, str, list[str]]:
    """anchors=[(label,path)..]。@图片1=主播,@图片2..N=各产品形态,提示词逐一声明。"""
    scene = shots[0].get("scene", "")
    acts = []
    for i, s in enumerate(shots):
        cut = "" if i == 0 else "硬切至"
        acts.append(f"{cut}{s.get('shot_size', '')}{s.get('camera', '')},{s.get('action', '')}")
    body = "。".join(acts)
    dialogue = "".join((s.get("dialogue") or "") for s in shots)
    # 逐图声明: @图片2是<产品desc>的<形态>
    prod_lines = "".join(
        f"@图片{i + 2}是{prod_desc}的{label}(以此图为准,不要改产品外观和包装文字)。"
        for i, (label, _) in enumerate(anchors)
    )
    images = [host] + [p for _, p in anchors]
    host_line = (
        f"@图片1是带货主播本人({host_desc}),每一个镜头都保持与@图片1完全一致的"
        f"长相、发型和这身穿着:{host_desc}。"
        if host_desc
        else "@图片1是带货主播本人,全程保持@图片1长相穿着一致。"
    )
    p = (
        f"{host_line}{prod_lines}"
        f"竖屏9:16。场景:{scene}。{body}。"
        f"台词{{{dialogue}}}@音频1,主播嘴巴跟随音频节奏自然说话,口型同步。{TAIL}"
    )
    return p, dialogue, images


# 说话/口播性动作词:hero 段一律剔除(哪怕从句里也提了产品)
TALK_WORDS = ["说话", "讲解", "对着镜头", "做手势", "比划", "介绍", "号召", "促单", "讲述"]
# 产品操作动词:完备性关卡核对这些有没有漏进提示词(治 G3 漏动作)。
# 默认表偏食品;★换品类在 assets.json 加 "product_verbs": ["涂","抹","喷","穿","抖开",..] 扩充。
PRODUCT_VERBS = [
    "掰",
    "切",
    "撕",
    "捏",
    "夹",
    "按压",
    "按",
    "拉扯",
    "拉开",
    "浇",
    "淋",
    "舀",
    "挤",
    "转动",
    "放",
    "夹起",
    "咬",
    "涂",
    "抹",
    "喷",
    "擦",
    "滴",
    "敷",
    "穿",
    "戴",
    "拧开",
    "打开",
]


def _clauses(action: str) -> list[str]:
    return [
        x.strip() for x in re.split(r"[，,；;。]|随后|切回|切到|再切|然后", action) if x.strip()
    ]


def product_actions_only(shots: list[dict]) -> list[str]:
    """只保留产品动作从句,凡含说话/讲解/对镜头从句一律剔除。"""
    keep = []
    for s in shots:
        for c in _clauses(s.get("action", "")):
            if any(w in c for w in TALK_WORDS):
                continue
            keep.append(c)
    return keep


def build_hero_prompt(shots: list[dict], prod_desc: str) -> str:
    # ★把分镜表的 action 原样带进来(治漏动作),但剔掉主播说话从句
    acts = "；".join(product_actions_only(shots)) or "展示产品"
    colors = shots[0].get("key_colors", "")
    return (
        f"{acts}。微距特写,镜头轻微跟随动作,展示{prod_desc}的真实生鲜质感、"
        f"自然光泽({colors})。真实质感,自然光。画面纯净,不要额外文字,不要Logo水印。"
    )


def build_package_prompt(shots: list[dict], prod_desc: str, anchor_label: str) -> str:
    return (
        f"镜头缓慢轻微推近并平移,展示{prod_desc}的{anchor_label},质感高级,"
        f"放在桌面上,室内柔和灯光。画面纯净,不要额外文字,不要Logo水印。"
    )


def completeness_check(prompt: str, shots: list[dict], verbs: list[str] | None = None) -> list[str]:
    """只核对【产品操作动词】有没有漏进提示词(忽略主播说话从句),漏了返回 warns。"""
    verbs = verbs or PRODUCT_VERBS
    warns = []
    for s in shots:
        for c in _clauses(s.get("action", "")):
            if any(w in c for w in TALK_WORDS):  # 主播从句不检
                continue
            miss = [v for v in verbs if v in c and v not in prompt]
            if miss:
                warns.append(f"#{s['shot_id']} 漏产品动作{miss}: {c[:20]}")
    return warns


def plan(shotlist, assets, out_path: str | None = None) -> list[dict]:
    """规划主入口。shotlist / assets 可为路径(str/Path)或已加载的 dict。

    返回 segments 列表(机器用);同时写 segments.json 与 segments.md(人审)。
    """
    sl = json.load(open(shotlist, encoding="utf-8")) if not isinstance(shotlist, dict) else shotlist
    cfg = json.load(open(assets, encoding="utf-8")) if not isinstance(assets, dict) else assets
    host = cfg.get("host_anchor", "")
    host_desc = cfg.get("host_desc", "")  # 主播外形一句话(发型/上衣/气质),钉死跨段穿着一致
    prod_desc = cfg.get("product_desc", "产品")
    products = cfg.get("products", {})
    form_map = merged_form_map(cfg)
    verbs = PRODUCT_VERBS + [v for v in (cfg.get("product_verbs") or []) if v not in PRODUCT_VERBS]
    shots = split_long_shots(sl["shots"])  # 修1: 先拆超长单镜
    groups = group_shots(shots)

    segments, md = [], [f"# 生成方案 ({len(groups)}段)\n", f"产品: {prod_desc}\n"]
    for gi, shots in enumerate(groups, 1):
        role = seg_role(shots)
        start, end = shots[0]["start"], shots[-1]["end"]
        dur = max(4, min(15, math.ceil(end - start)))
        sid = f"S{gi}"
        warns = []
        if role == "kou":
            anchors, missing = pick_product_anchors(shots, products, form_map)
            prompt, dialogue, images = build_kou_prompt(shots, host, prod_desc, anchors, host_desc)
            warns = completeness_check(prompt, shots, verbs)
            warns += [
                f"⚠锚图缺失:提示词提到'{w}'但assets无对应图,即梦会自由发挥编产品→请补图或删该形态"
                for w, _ in missing
            ]
            seg = {
                "seg": sid,
                "type": "mm",
                "images": images,
                "anchor_labels": [label for label, _ in anchors],
                "dialogue": dialogue,
                "prompt": prompt,
            }
        elif role == "hero":
            anchor = products.get("hero_alt") or products.get("hero")
            prompt = build_hero_prompt(shots, prod_desc)
            warns = completeness_check(prompt, shots, verbs)
            seg = {"seg": sid, "type": "i2v", "anchor": anchor, "prompt": prompt}
        elif role == "package":
            anchors, missing = pick_product_anchors(shots, products, form_map)
            label, anchor = anchors[0] if anchors else ("产品", products.get("hero"))
            prompt = build_package_prompt(shots, prod_desc, label)
            warns = [f"⚠锚图缺失:'{w}'无对应图" for w, _ in missing]
            seg = {"seg": sid, "type": "i2v", "anchor": anchor, "prompt": prompt}
        else:
            anchors, _ = pick_product_anchors(shots, products, form_map)
            anchor = anchors[0][1] if anchors else products.get("hero")
            prompt = build_hero_prompt(shots, prod_desc)
            seg = {"seg": sid, "type": "i2v", "anchor": anchor, "prompt": prompt}
        # 每段都记连续旁白(hero/包装段也要,装配时铺完整配音轨)
        seg_dialogue = "".join((s.get("dialogue") or "") for s in shots)
        seg.update(
            {
                "shots": [s["shot_id"] for s in shots],
                "start": start,
                "end": end,
                "duration": dur,
                "dialogue": seg_dialogue,
                "opening_3s": any(s.get("is_opening_3s") for s in shots),
                "warns": warns,
            }
        )
        segments.append(seg)
        # md 卡片
        flag = " ★前3秒" if seg["opening_3s"] else ""
        w = ("  ⚠️ " + "; ".join(warns)) if warns else ""
        md.append(f"\n## {sid} [{start}-{end}] {dur}s  {role}{flag}{w}\n```\n{seg['prompt']}\n```")

    if out_path:
        json.dump(segments, open(out_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        mdp = str(out_path).replace(".json", ".md")
        open(mdp, "w", encoding="utf-8").write("\n".join(md))
        print(f"[plan] {len(segments)}段 → {out_path}")
        nwarn = sum(len(s["warns"]) for s in segments)
        for s in segments:
            tag = {"mm": "口播", "i2v": "image2video"}[s["type"]]
            print(
                f"  {s['seg']} [{s['start']}-{s['end']}] {s['duration']}s {tag}"
                + (f"  ⚠️{len(s['warns'])}漏" if s["warns"] else "")
            )
        if nwarn:
            print(f"  ⚠️ 完备性关卡: {nwarn} 处漏动作,见 {mdp}")
        print(f"  人审稿: {mdp}")
    return segments
