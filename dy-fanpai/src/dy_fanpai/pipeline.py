"""pipeline.py — WP6 全流程编排（CLI run/retry 落地）。

- 阶段 → 闸口映射（§6 四闸口）：进入任一阶段前先 ``workflow.require_gate``，未批准立即停
  （抛 ``GateBlocked``，CLI 捕获后返回非零）。闸口不可被 ``run`` 或任何 flag 绕过。
- 离线安全阶段（plan / deliver）真实执行；需 Live/网络 或 依赖生成产物的阶段在离线
  （``run.live is False``）模式跳过并明确提示，绝不假装完成。
- 确定性函数与 IO 解耦；generate 走 ``generation/service.run``（支持 ``backends=`` DI，
  测试可注入 Mock；真实运行需已批准 Live Pilot 与凭证）。
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from . import workflow
from .config import Config
from .delivery import final, jianying
from .models import Gate, Stage
from .planning import planner
from .workspace import Workspace

# 阶段进入前必须批准的闸口（§6 四闸口语义）：
# - reverse / plan 处理源素材与上传，需 rights(G1)；
# - audio / generate / assemble 消费计划与生成产物，需 plan(G2) 已审 + cost(G3) 已批
#   （generate 直接花钱；assemble 复用生成产物，沿用 cost 已批状态）；
# - deliver 需 qc(G4) 最终人工 QC，技术通过不能自动越过。
STAGE_GATE: dict[Stage, Gate] = {
    Stage.REVERSE: Gate.RIGHTS,
    Stage.PLAN: Gate.RIGHTS,
    Stage.AUDIO: Gate.PLAN,
    Stage.GENERATE: Gate.COST,
    Stage.ASSEMBLE: Gate.COST,
    Stage.DELIVER: Gate.QC,
}

# PREPARE → DELIVER 的线性推进顺序（run 无 --stage 时跑全程）。
_STAGE_ORDER: list[Stage] = [
    Stage.PREPARE, Stage.REVERSE, Stage.PLAN, Stage.AUDIO,
    Stage.GENERATE, Stage.ASSEMBLE, Stage.DELIVER,
]


def required_gate(stage: Stage) -> Gate | None:
    """进入该阶段前必须批准的闸口；PREPARE 无需闸口。"""
    return STAGE_GATE.get(stage)


def _skip_offline(stage: Stage, *, live: bool) -> None:
    if live:
        raise RuntimeError(
            f"Live 阶段 {stage.value} 需已批准 Live Pilot 与对应凭证，本环境不自动执行"
        )
    print(
        f"[run] 离线模式：跳过需 {'Live/网络' if stage in (Stage.REVERSE, Stage.GENERATE) else '生成产物/ffmpeg'} 的阶段 {stage.value}"
        f"（需已批准 Live Pilot 与生成产物）",
        file=sys.stderr,
    )


def _exec_plan(ws: Workspace, run) -> None:
    shotlist_path = ws.planning / "shotlist.json"
    assets_path = ws.planning / "assets.json"
    if not shotlist_path.exists():
        # reverse 阶段产物在 reverse/shotlist.json;若规划前已反推,自动带过来
        rev = ws.reverse / "shotlist.json"
        if rev.exists():
            import shutil

            shutil.copy(rev, shotlist_path)
            print("[run] 从 reverse/shotlist.json 带入反推产物 → planning/")
    if not shotlist_path.exists():
        raise RuntimeError("缺少 planning/shotlist.json，无法规划（先 reverse 产出 shotlist）")
    shotlist = json.loads(shotlist_path.read_text(encoding="utf-8"))
    assets = json.loads(assets_path.read_text(encoding="utf-8")) if assets_path.exists() else {}
    segs = planner.plan(shotlist, assets, str(ws.planning / "segments.json"))
    run.stage_results["plan"] = {"segments": len(segs)}
    print(f"[run] 规划完成：{len(segs)} 段 → planning/segments.json")


def _exec_reverse(ws: Workspace, run, *, leg: str | None = None) -> None:
    """P1 反推：调反推腿（seed 默认 / kimi / qwen），产物写 reverse/shotlist.json。

    仅 live 模式真调（需对应密钥与预算）；离线模式正确跳过、不虚报完成。
    leg 由 CLI `run --stage reverse --leg qwen|kimi` 选择；默认 seed。
    """
    src = ws.inputs / run.source_video
    src = src if src.exists() else Path(run.source_video)
    if not src.exists():
        raise RuntimeError(f"源视频不存在：{src}")
    rev_dir = ws.reverse
    rev_dir.mkdir(parents=True, exist_ok=True)

    from .reverse import kimi, qwen, seed

    legs = {"seed": seed, "kimi": kimi, "qwen": qwen}
    mod = legs.get(leg or "seed")
    if mod is None:
        raise RuntimeError(f"未知反推腿: {leg}（可选 seed/kimi/qwen）")
    out = rev_dir / "shotlist.json"
    print(f"[run] 反推腿={mod.__name__.split('.')[-1]} → {out}", flush=True)
    mod.reverse(str(src), out=str(out))
    run.stage_results["reverse"] = {"leg": mod.__name__.split('.')[-1], "shotlist": str(out)}
    print("[run] 反推完成 → reverse/shotlist.json")


def _exec_deliver(ws: Workspace, run, *, bgm: str | None = None, jy_drafts: str | None = None) -> None:
    out = ws.output
    full = out / "FULL.mp4"
    if not full.exists():
        raise RuntimeError("缺少 output/FULL.mp4，请先装配（assemble）")
    segs_path = ws.planning / "segments.json"
    segments: list[dict] = []
    if segs_path.exists():
        data = json.loads(segs_path.read_text(encoding="utf-8"))
        segments = data.get("segments", data) if isinstance(data, dict) else data

    srt = out / "FULL.srt"
    n = final.write_srt(final.build_srt_entries(segments), str(srt))
    print(f"[deliver] SRT → {srt} ({n} 条)")

    final_path = out / "FINAL.mp4"
    try:
        final.build_final(str(full), str(final_path), srt=str(srt), bgm=bgm, burn=True)
    except subprocess.CalledProcessError:
        print(
            "[deliver] 烧字幕失败(ffmpeg 缺 libass?),回退为无烧字幕 FINAL(SRT 侧载)",
            file=sys.stderr,
        )
        final.build_final(str(full), str(final_path), srt=str(srt), bgm=bgm, burn=False)
    ws.register_artifact(run, "final", str(final_path), Stage.DELIVER)
    print(f"[deliver] FINAL → {final_path}")

    cfg = Config.load()
    draft_dir = Path(jy_drafts) if jy_drafts else (Path(cfg.jy_drafts) / run.project_id if cfg.jy_drafts else out / "草稿")
    spec = jianying.build_draft_spec(video=str(full), srt=str(srt), bgm=bgm)
    p = jianying.write_draft(spec, str(draft_dir), engine="json")
    print(f"[deliver] 剪映草稿(规格) → {p}")


def _exec_audio(ws: Workspace, run, *, tts_backend: str | None = None) -> None:
    """P3 音频：原音切段 + 可选 TTS 配音（纯本地 ffmpeg / 配音后端）。

    输入 planning/segments.json + 源视频 → 输出 audio/segments/{seg}.wav +
    audio/timing.json。

    - tts_backend 为空/None → 原音切段（忠实复刻 cut_original_audio）；
    - tts_backend 指定（voxcpm / voicebox / 注册表扩展）→ 原音切段
      后调用 tts_backend.synthesize 生成配音（产物同名 wav 覆盖，供 gen 的
      reference_audio 用）。仅在 live 模式调用（离线跳过不虚报）。
    """
    plan_path = ws.planning / "segments.json"
    if not plan_path.exists():
        raise RuntimeError("缺少 planning/segments.json，无法切音频（先 plan 产出 segments）")
    src = ws.inputs / run.source_video
    src = src if src.exists() else Path(run.source_video)
    if not src.exists():
        raise RuntimeError(f"源视频不存在：{src}")
    shotlist = ws.planning / "shotlist.json"
    shotlist_arg = str(shotlist) if shotlist.exists() else None
    seg_dir = ws.root / "audio" / "segments"
    seg_dir.mkdir(parents=True, exist_ok=True)

    from .audio.service import cut_original_audio

    timing = cut_original_audio(
        str(plan_path), str(src), shotlist_arg, str(seg_dir), cfg=None
    )
    # 规范布局:timing.json 放 audio/timing.json(cut_original_audio 写在 segments/ 内,复制过去)
    timing_dst = ws.root / "audio" / "timing.json"
    src_timing = seg_dir / "timing.json"
    if src_timing.exists() and not timing_dst.exists():
        import shutil

        shutil.copy(src_timing, timing_dst)

    mode = "source"
    if tts_backend:
        cfg = Config.load()
        from .audio import tts_backend as tb

        mode = f"tts:{tts_backend}"
        timing = tb.synthesize(str(plan_path), str(seg_dir), tts_backend, cfg)
        # 配音 timing 同步到 audio/timing.json（原音切段的 timing 被配音时序替代）
        if timing:
            timing_dst.write_text(
                json.dumps(timing, ensure_ascii=False, indent=1), encoding="utf-8"
            )

    run.stage_results["audio"] = {"mode": mode, "segments": len(timing)}
    print(f"[run] 音频完成（{mode}）：{len(timing)} 段 → audio/segments/ + timing.json")


def execute_stage(
    stage: Stage,
    ws: Workspace,
    run,
    *,
    backends: dict | None = None,
    bgm: str | None = None,
    jy_drafts: str | None = None,
    leg: str | None = None,
    tts_backend: str | None = None,
    i2v_backend: str | None = None,
) -> Stage:
    """执行单个阶段（先闸口检查，未批准抛 GateBlocked）。返回该阶段。"""
    gate = required_gate(stage)
    if gate is not None:
        workflow.require_gate(run, gate)  # 未批准 → GateBlocked

    executed = False
    if stage == Stage.REVERSE:
        if run.live:
            _exec_reverse(ws, run, leg=leg)
            executed = True
        else:
            _skip_offline(stage, live=False)
    elif stage == Stage.PLAN:
        _exec_plan(ws, run)
        executed = True
    elif stage == Stage.AUDIO:
        if run.live:
            _exec_audio(ws, run, tts_backend=tts_backend)
            executed = True
        else:
            _skip_offline(stage, live=False)
    elif stage == Stage.GENERATE:
        if run.live:
            _exec_generate(ws, run, i2v_backend=i2v_backend)
            executed = True
        else:
            _skip_offline(stage, live=False)
    elif stage == Stage.ASSEMBLE:
        _exec_assemble(ws, run)
        executed = True
    elif stage == Stage.DELIVER:
        _exec_deliver(ws, run, bgm=bgm, jy_drafts=jy_drafts)
        executed = True
    # PREPARE：无操作

    if executed:
        workflow.mark_stage_done(run, stage)
    run.current_stage = stage
    ws.save(run)
    return stage


def _exec_generate(ws: Workspace, run, *, i2v_backend: str | None = None) -> None:
    """P5 生成：跑 generation.service.run（口播 mm 默认即梦；i2v/无主播 mm 走 i2v_backend）。

    仅 live 模式真调（需已批准 G3 cost 与凭证）；产物 clips/{seg}.mp4。
    """
    from .generation import service as G

    segs = ws.planning / "segments.json"
    if not segs.exists():
        raise RuntimeError("缺少 planning/segments.json，无法生成（先 plan）")
    summary = G.run(
        str(segs), str(ws.clips), str(ws.audio), Config.load(),
        manifest=run, lock_path=str(ws.lock_path),
        i2v_backend=i2v_backend or "dreamina",
    )
    run.stage_results["generate"] = summary
    print(f"[run] 生成完成：{summary}")


def _exec_assemble(ws: Workspace, run) -> None:
    """P5 装配：clips/{seg}.mp4 + audio/segments/{seg}.wav → output/FULL.mp4。

    离线可跑（无需 live/密钥）；按段目标时长裁剪 clip（兼容 H3 帧数网格
    导致的超长段），成片时长与 segments 规划对齐。
    """
    from .media import ffmpeg as F

    segs = ws.planning / "segments.json"
    if not segs.exists():
        raise RuntimeError("缺少 planning/segments.json，无法装配（先 plan）")
    if not (ws.clips / "S1.mp4").exists() and not list(ws.clips.glob("*.mp4")):
        raise RuntimeError("clips/ 无生成片段，先 generate")
    out_dir = ws.output
    out_dir.mkdir(parents=True, exist_ok=True)
    F.assemble(
        plan_path=str(segs),
        clips_dir=str(ws.clips),
        audio_dir=str(ws.audio / "segments"),
        out=str(out_dir / "FULL.mp4"),
    )
    run.stage_results["assemble"] = {"full": str(out_dir / "FULL.mp4")}
    print(f"[run] 装配完成 → {out_dir / 'FULL.mp4'}")


def run_flow(
    ws: Workspace,
    run,
    *,
    stage: Stage | None = None,
    backends: dict | None = None,
    bgm: str | None = None,
    jy_drafts: str | None = None,
    leg: str | None = None,
    tts_backend: str | None = None,
    i2v_backend: str | None = None,
) -> None:
    """从 current_stage 跑到目标 stage（默认 DELIVER）；遇未批准闸口即停。"""
    target = stage or Stage.DELIVER
    order = _STAGE_ORDER
    start_idx = order.index(run.current_stage) if run.current_stage in order else 0
    end_idx = order.index(target)
    for st in order[start_idx:end_idx + 1]:
        execute_stage(st, ws, run, backends=backends, bgm=bgm, jy_drafts=jy_drafts,
                      leg=leg, tts_backend=tts_backend, i2v_backend=i2v_backend)
