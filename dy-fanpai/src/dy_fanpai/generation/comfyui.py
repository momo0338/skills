"""generation/comfyui.py — 自建 ComfyUI 视频生成后端（替代即梦，自有 GPU 部署）。

接入方式（AMD ROCm 官方容器 ComfyUI 0.18.2 + 原生 HTTP API）：
- 上传素材：`POST /upload/image`（图片）、`POST /upload/audio`（音频）→ 返回文件名；
- 提交工作流：`POST /prompt`（body = 工作流 JSON + client_id）→ 返回 `prompt_id`；
- 轮询结果：`GET /history/{prompt_id}` → outputs 里出现文件即完成；
- 下载产物：`GET /view?filename=...&subfolder=...&type=...` → 视频文件。

工作流模板（用户在两台机器上搭好后放模板路径）：
- `comfyui_workflow_i2v`：Wan2.1 图生视频（纯产品段），占位符见 TEMPLATE_PLACEHOLDERS；
- `comfyui_workflow_mm`：LatentSync 口型（口播段），占位符同。
- 模板 JSON 里用占位符（如 `__PROMPT__`）标注入点，本模块提交前原地替换。

业务铁律（沿用项目纪律）：
- 人物口播(mm) 默认仍走即梦（口型验证过）；本后端 mm 段需 LatentSync 工作流实测
  口型通过后才建议切换（experimental）。
- 下载复用 media.download.robust_download（坏流重下）。

契约（与 dreamina/ark/xyq/minimax 一致）：
- submit_i2v/submit_mm/submit_t2v(...) -> task_id(prompt_id)
- wait_download(task_id, dst, cfg) -> (size|fail|None, usage)
"""

from __future__ import annotations

import json
import os
import time

import requests

from ..config import Config
from ..media.download import robust_download

# 工作流模板注入占位符（模板 JSON 中这些字面量会被替换）
PH_PROMPT = "__PROMPT__"
PH_IMAGE = "__IMAGE__"
PH_IMAGE2 = "__IMAGE2__"
PH_AUDIO = "__AUDIO__"
PH_DURATION = "__DURATION__"
PH_WIDTH = "__WIDTH__"
PH_HEIGHT = "__HEIGHT__"
PH_RESOLUTION = "__RESOLUTION__"
PH_FRAMES = "__FRAMES__"
PH_ASPECT = "__ASPECT__"  # H3 ResolutionSelector 的 aspect_ratio 枚举串
PH_SEED = "__SEED__"  # H3 随机种子

# H3 模板 ResolutionSelector 支持的 8 档比例（与 scripts/h3_video_*.js 一致）
_ASPECT_OPTIONS: list[tuple[str, float]] = [
    ("1:1 (Square)", 1),
    ("2:3 (Portrait Photo)", 2 / 3),
    ("3:2 (Photo)", 3 / 2),
    ("3:4 (Portrait Standard)", 3 / 4),
    ("4:3 (Standard)", 4 / 3),
    ("9:16 (Portrait Widescreen)", 9 / 16),
    ("16:9 (Widescreen)", 16 / 9),
    ("21:9 (Ultrawide)", 21 / 9),
]

# 视频帧率:Wan2.2 = 16fps(帧数 = 秒数 × 16);MiniMax H3 = 24fps,
# 且帧数必须对齐 17k+5 网格(k 整数,如 5s→124 帧;官方训练范围 ~124-362)。
FPS = 16
FPS_H3 = 24
_H3_GRID = 17
_H3_GRID_OFFSET = 5
_H3_MIN_FRAMES = 124  # 官方训练范围 ~124-362(≈5s 起)


def frames_for(duration: int, kind: str = "i2v") -> int:
    """按后端计算视频帧数。

    - h3_i2v:24fps,向上对齐 17k+5 网格(与官方模板 ComfyMathExpression 同公式),
      且不低于 124 帧(模型训练下限,~5s)。
    - 其它:16fps(Wan 默认)。
    """
    if kind == "h3_i2v":
        raw = max(5, round(duration * FPS_H3))
        return max(_H3_MIN_FRAMES, raw + (_H3_GRID_OFFSET - raw % _H3_GRID) % _H3_GRID)
    return duration * FPS


def aspect_ratio_for(width: int, height: int) -> str:
    """H3 ResolutionSelector 的 aspect_ratio 枚举串（取最接近的档位）。

    与 scripts/h3_video_*.js 的 pickAspectRatio 同逻辑:720x1280 → "9:16"。
    """
    ratio = (width or 16) / (height or 9)
    return min(_ASPECT_OPTIONS, key=lambda o: abs(o[1] - ratio))[0]


def prune_r2v_single(workflow: dict) -> dict:
    """R2V 单参考图时:移除第二个 LoadImage 与 ref_images.ref_image_1 引用。

    模板默认双图(LoadImage __IMAGE__/__IMAGE2__ + ref_image_0/1);只有一张
    参考图时删掉第二个 LoadImage 节点及其在所有 inputs 中的引用,避免提交
    空文件名导致 ComfyUI 报错。返回新 dict,不动原模板。
    """
    out = json.loads(json.dumps(workflow))  # 深拷贝
    rm_id: str | None = None
    for nid, node in out.items():
        ins = node.get("inputs", {})
        if node.get("class_type") == "LoadImage" and ins.get("image") == PH_IMAGE2:
            rm_id = nid
            break
    if rm_id is None:
        return out
    del out[rm_id]
    for node in out.values():
        ins = node.get("inputs", {})
        for k in [k for k, v in ins.items() if isinstance(v, list) and v and str(v[0]) == rm_id]:
            del ins[k]
    return out


# 上传素材类型 → ComfyUI /upload 端点
_UPLOAD_EP = {"image": "/upload/image", "audio": "/upload/audio"}

# 默认模板路径（config 未设置时回退到 resources/workflows/）
_DEFAULT_TEMPLATES = {
    "i2v": os.path.join(os.path.dirname(__file__), "..", "..", "..", "resources", "workflows", "comfyui_i2v.json"),
    "h3_i2v": os.path.join(os.path.dirname(__file__), "..", "..", "..", "resources", "workflows", "comfyui_h3_i2v.json"),
    "h3_t2v": os.path.join(os.path.dirname(__file__), "..", "..", "..", "resources", "workflows", "comfyui_h3_t2v.json"),
    "h3_r2v": os.path.join(os.path.dirname(__file__), "..", "..", "..", "resources", "workflows", "comfyui_h3_r2v.json"),
    "mm": os.path.join(os.path.dirname(__file__), "..", "..", "..", "resources", "workflows", "comfyui_mm.json"),
}


# ---------------------------------------------------------------------------
# 确定性函数（离线可测）
# ---------------------------------------------------------------------------
def graph_to_api_prompt(workflow: dict) -> dict:
    """把「画布图格式」(nodes/links) 工作流转为 ComfyUI /prompt API 扁平格式。

    ComfyUI 网页保存的是 graph 格式;HTTP API 需要:
        {"<node_id>": {"class_type": "<type>", "inputs": {...}}, ...}
    连接由 links 的 [id, from, from_slot, to, to_slot, type] 表示,
    在目标节点 inputs 中写成 {"<input_name>": ["<from_node_id>", <from_slot>]}。
    关键:link 的 to_slot 是**输入槽索引**,须映射到该节点 input 的 name
    (模板 nodes[i].inputs[to_slot].name;无 inputs 定义时退化为 str(to_slot))。
    widgets_values 只含「非 link」输入的值,按 node_inputs 顺序跳过 linked 后填充。
    """
    nodes = {n["id"]: n for n in workflow.get("nodes", [])}
    links = workflow.get("links", [])

    # 目标节点 -> {to_slot: [from_id, from_slot]}
    link_map: dict[int, dict[int, list]] = {}
    for lnk in links:
        _, frm, frm_slot, to, to_slot, _ = lnk
        link_map.setdefault(to, {})[to_slot] = [frm, frm_slot]

    prompt: dict = {}
    for nid, n in nodes.items():
        nid_str = str(nid)
        cls = n["type"]
        widgets = n.get("widgets_values", [])
        node_inputs = n.get("inputs", [])
        inputs: dict = {}

        def input_name(slot_idx: int) -> str:
            if slot_idx < len(node_inputs) and node_inputs[slot_idx].get("name"):
                return str(node_inputs[slot_idx]["name"])
            return str(slot_idx)

        # 1) link 连接:slot 索引 → input name(引用节点 id 必须为字符串!)
        linked_names = set()
        for to_slot, link_ref in link_map.get(nid, {}).items():
            nm = input_name(to_slot)
            inputs[nm] = [str(link_ref[0]), link_ref[1]]  # ComfyUI 用 str 节点 id
            linked_names.add(nm)

        # 2) widgets 填充未连接 input(按 node_inputs 顺序跳过 linked)
        if node_inputs:
            wi = 0
            for inp in node_inputs:
                nm = inp.get("name", str(wi))
                if nm not in linked_names and wi < len(widgets):
                    inputs[nm] = widgets[wi]
                    wi += 1
        else:
            # 旧模板:无 inputs 定义,所有 widgets 按 0..n 命名(仅当未被 link 占用)
            for wi, v in enumerate(widgets):
                nm = str(wi)
                if nm not in linked_names:
                    inputs[nm] = v
        prompt[nid_str] = {"class_type": cls, "inputs": inputs}
    return prompt


def inject_placeholders(workflow: dict, values: dict[str, str]) -> dict:
    """把工作流 JSON 中所有字符串字段里的占位符替换为实际值（确定性）。

    values: {PH_*: 实际值}。递归遍历 dict/list;未出现的占位符保持原样
    （便于发现模板缺参）。
    """
    out = json.loads(json.dumps(workflow))  # 深拷贝,不动原模板

    def walk(node):
        if isinstance(node, dict):
            return {k: walk(v) for k, v in node.items()}
        if isinstance(node, list):
            return [walk(v) for v in node]
        if isinstance(node, str):
            s = node
            for ph, val in values.items():
                if ph in s:
                    s = s.replace(ph, str(val))
            return s
        return node

    res = walk(out)
    return res if isinstance(res, dict) else out


def parse_submit_out(out: str) -> str | None:
    """解析 /prompt 响应：返回 prompt_id；失败返回 None。"""
    try:
        d = json.loads(out)
    except Exception:  # noqa: BLE001
        return None
    return d.get("prompt_id")


def parse_history_out(out: str) -> tuple[str, list[dict] | None]:
    """解析 /history/{id} 响应：返回 (status, files)。

    status: "success"（outputs 有文件）| "failed" | "pending"。
    files: [{filename, subfolder, type}, ...];ComfyUI 视频输出常见于
    outputs[node]["gifs"] 或 ["images"] 或 ["videos"]。
    """
    try:
        d = json.loads(out)
    except Exception:  # noqa: BLE001
        return "pending", None
    if not isinstance(d, dict):
        return "pending", None
    entry = next(iter(d.values()), None) if d else None
    if not entry:
        return "pending", None
    status = entry.get("status", {})
    if status.get("status_str") == "error" or status.get("completed") is False and status.get("status_str") == "error":
        return "failed", None
    outs = entry.get("outputs", {}) or {}
    files: list[dict] = []
    for node_out in outs.values():
        for key in ("gifs", "images", "videos"):
            for f in node_out.get(key, []):
                files.append({"filename": f.get("filename"), "subfolder": f.get("subfolder", ""),
                              "type": f.get("type", "output")})
    if status.get("completed") is True and files:
        return "success", files
    if status.get("completed") is True:
        return "failed", None
    return "pending", None


def _rand_seed() -> int:
    """H3 随机种子(0..2^31,与 JS 脚本 Math.random()*2**31 一致)。"""
    import random

    return random.randrange(0, 2**31)


def _template_path(cfg: Config, kind: str) -> str:
    """取工作流模板路径（config 优先,否则默认 resources/workflows/）。"""
    p = getattr(cfg, f"comfyui_workflow_{kind}", "") or _DEFAULT_TEMPLATES[kind]
    return p


# ---------------------------------------------------------------------------
# 素材上传（网络层）
# ---------------------------------------------------------------------------
def _upload(path: str, kind: str, cfg: Config) -> str:
    """上传图片/音频到 ComfyUI,返回服务端文件名。"""
    ep = _UPLOAD_EP[kind]
    with open(path, "rb") as f:
        r = requests.post(
            f"{cfg.comfyui_base_url}{ep}",
            files={"image" if kind == "image" else "file": (os.path.basename(path), f)},
            data={"type": "input", "overwrite": "true"},
            timeout=(10, 300),
        )
    if r.status_code != 200:
        raise RuntimeError(f"上传{kind}失败 HTTP {r.status_code}: {r.text[:200]}")
    return r.json().get("name") or os.path.basename(path)


def _submit_workflow(workflow: dict, cfg: Config, timeout: int = 120) -> str:
    """POST /prompt 提交工作流,返回 prompt_id。"""
    r = requests.post(
        f"{cfg.comfyui_base_url}/prompt",
        json={"prompt": workflow, "client_id": "dy-fanpai"},
        timeout=(10, timeout),
    )
    if r.status_code != 200:
        raise RuntimeError(f"提交工作流失败 HTTP {r.status_code}: {r.text[:300]}")
    pid = parse_submit_out(r.text)
    if not pid:
        raise RuntimeError(f"提交无 prompt_id: {r.text[:300]}")
    return pid


def submit(
    prompt: str,
    cfg: Config,
    *,
    images: list[str] | None = None,
    audio: str | None = None,
    first_frame: str | None = None,
    duration: int = 5,
    width: int = 720,
    height: int = 1280,
    kind: str = "i2v",
    retries: int = 3,
    seed: int | None = None,
) -> tuple[str | None, str]:
    """提交 ComfyUI 工作流（编排层，含退避重试）。返回 (prompt_id|None, err)。

    流程:上传素材(图/音频)→ 注入占位符 → POST /prompt。
    kind: "i2v"(纯产品) | "mm"(口播,需 LatentSync 工作流)
          | "h3_t2v"(H3 文生) | "h3_r2v"(H3 参考图生,1~2 张参考图)。
    模板兼容两种格式:graph(nodes/links,走 graph_to_api_prompt)与
    扁平(顶层即 {node_id: {class_type, inputs}},直接提交)。
    """
    tmpl_path = _template_path(cfg, kind)
    if not os.path.exists(tmpl_path):
        raise RuntimeError(f"缺少工作流模板: {tmpl_path}(在 ComfyUI 搭好后保存为模板 JSON)")
    workflow = json.load(open(tmpl_path, encoding="utf-8"))

    # 1) 上传素材
    img_names, audio_name = [], None
    for p in (images or []):
        img_names.append(_upload(p, "image", cfg))
    if first_frame:
        img_names.append(_upload(first_frame, "image", cfg))
    if audio:
        audio_name = _upload(audio, "audio", cfg)

    # 2) 注入占位符(帧数按后端:Wan 16fps / H3 24fps+17k+5 网格;
    #    H3 模板用 aspect_ratio 枚举 + 随机种子)
    values = {
        PH_PROMPT: prompt,
        PH_IMAGE: img_names[0] if img_names else "",
        PH_IMAGE2: img_names[1] if len(img_names) > 1 else "",
        PH_AUDIO: audio_name or "",
        PH_DURATION: str(int(duration)),
        PH_WIDTH: str(int(width)),
        PH_HEIGHT: str(int(height)),
        PH_RESOLUTION: f"{width}x{height}",
        PH_FRAMES: str(frames_for(int(duration), kind)),
        PH_ASPECT: aspect_ratio_for(int(width), int(height)),
        PH_SEED: str(seed if seed is not None else _rand_seed()),
    }
    if kind == "h3_r2v" and len(img_names) < 2:
        # 单参考图:先裁剪模板(移除第二个 LoadImage 与 ref_image_1 引用),
        # 再注入,避免 __IMAGE2__ 已被替换成空串而匹配不到
        workflow = prune_r2v_single(workflow)
    workflow = inject_placeholders(workflow, values)
    # 图格式 → API 扁平格式(扁平模板已可直接提交)
    if "nodes" in workflow:
        workflow = graph_to_api_prompt(workflow)

    # 3) 提交(退避重试;参数级 4xx 不重试)
    for attempt in range(retries):
        try:
            pid = _submit_workflow(workflow, cfg, timeout=120)
            return pid, ""
        except RuntimeError as e:
            msg = str(e)
            if "HTTP 4" in msg:
                raise
            if attempt == retries - 1:
                raise
            time.sleep(10 * (attempt + 1))
    return None, "提交失败"


def wait_download(
    pid: str, dst: str, cfg: Config, tries: int = 240, gap: int = 10
) -> int | str | None:
    """轮询 /history/{pid} → 完成时从 /view 下载。返回 (size|"FAIL: .."|None)。

    默认 240 次 × 10s ≈ 40 分钟(视频生成慢,尤其 14B 模型);tries 可调。
    """
    for _ in range(tries):
        try:
            r = requests.get(f"{cfg.comfyui_base_url}/history/{pid}", timeout=(10, 30))
        except Exception:  # noqa: BLE001
            time.sleep(gap)
            continue
        if r.status_code != 200:
            time.sleep(gap)
            continue
        status, files = parse_history_out(r.text)
        if status == "success" and files:
            f = files[0]
            url = f"{cfg.comfyui_base_url}/view?filename={f['filename']}" \
                  + (f"&subfolder={f['subfolder']}" if f["subfolder"] else "") \
                  + f"&type={f['type']}"
            return robust_download(url, dst)
        if status == "failed":
            return "FAIL: ComfyUI 工作流执行失败"
        time.sleep(gap)
    return None  # 超时未完成


# ---------------------------------------------------------------------------
# 后端统一入口（与 generation/service.py backends 契约一致）
# ---------------------------------------------------------------------------
def submit_i2v(image_path: str, prompt: str, cfg: Config, duration: int = 5) -> str | None:
    """纯产品 image2video：Wan2.1 i2v 工作流。"""
    pid, _ = submit(prompt, cfg, first_frame=image_path, duration=duration, kind="i2v")
    return pid


def submit_h3_i2v(
    image_path: str, prompt: str, cfg: Config, duration: int = 5,
    width: int = 768, height: int = 1344,
) -> str | None:
    """纯产品 image2video：MiniMax H3(FL2VA) i2v 工作流(24fps + 原生立体声)。

    H3 原生画布短边 768,9:16 上限 768x1344;默认 768x1344。
    """
    pid, _ = submit(prompt, cfg, first_frame=image_path, duration=duration,
                    width=width, height=height, kind="h3_i2v")
    return pid


def submit_mm(image_paths: list[str], audio_path: str | None, prompt: str, cfg: Config,
              duration: int = 5) -> str | None:
    """口播（LatentSync 工作流,experimental）：参考图 + 段配音。"""
    pid, _ = submit(prompt, cfg, images=image_paths, audio=audio_path, duration=duration, kind="mm")
    return pid


def submit_h3_t2v(
    prompt: str, cfg: Config, duration: int = 5,
    width: int = 768, height: int = 1344, seed: int | None = None,
) -> str | None:
    """文生视频：MiniMax H3(FL2VA) t2v 工作流(24fps + 原生立体声,无图输入)。

    默认 768x1344(9:16, H3 画布短边 768 上限)。
    """
    pid, _ = submit(prompt, cfg, duration=duration, width=width, height=height,
                    kind="h3_t2v", seed=seed)
    return pid


def submit_h3_r2v(
    image_paths: list[str], prompt: str, cfg: Config, duration: int = 5,
    width: int = 768, height: int = 1344, seed: int | None = None,
) -> str | None:
    """参考生视频：MiniMax H3(ref2va) r2v 工作流(1~2 张参考图,24fps)。

    参考图驱动(动作/姿态/风格迁移);单图时自动移除第二个 LoadImage 与
    ref_image_1 引用。默认 768x1344。
    """
    pid, _ = submit(prompt, cfg, images=image_paths, duration=duration,
                    width=width, height=height, kind="h3_r2v", seed=seed)
    return pid


def submit_t2v(prompt: str, cfg: Config, duration: int = 5) -> str | None:
    """文生视频（如模板支持;一般不用）。"""
    pid, _ = submit(prompt, cfg, duration=duration, kind="i2v")
    return pid
