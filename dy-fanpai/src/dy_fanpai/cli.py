"""dy_fanpai CLI 骨架（WP1）。

八组命令（EXECUTION_PLAN §7）：doctor / new / status / run / approve /
retry / deliver / clean。WP1 仅实现骨架与可立即落地的 new/status/doctor；
其余命令的参数与闸口拦截已就位，业务逻辑由各工作包（WP2–WP5）填充。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import pipeline, workflow
from .config import Config, ConfigError
from .delivery import cleanup
from .models import Gate, Stage
from .workspace import Workspace, WorkspaceError


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="dy-fanpai", description="抖音翻拍")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("doctor", help="环境体检")

    nw = sub.add_parser("new", help="创建工作区")
    nw.add_argument("--video", required=True)
    nw.add_argument("--workspace", required=True)
    nw.add_argument("--project-id", default="")

    st = sub.add_parser("status", help="查看工作区状态")
    st.add_argument("workspace")

    rn = sub.add_parser("run", help="执行流程")
    rn.add_argument("workspace")
    rn.add_argument("--stage", choices=[s.value for s in Stage], default=None)

    ap = sub.add_parser("approve", help="闸口批准")
    ap.add_argument("workspace")
    ap.add_argument("gate", choices=[g.value for g in Gate])
    ap.add_argument("--by", default="integrator")

    rt = sub.add_parser("retry", help="断点续跑")
    rt.add_argument("workspace")
    rt.add_argument("--segments", default=None)

    dl = sub.add_parser("deliver", help="交付")
    dl.add_argument("workspace")
    dl.add_argument("--mode", choices=["final", "jianying", "both"], default="final")
    dl.add_argument("--bgm", default=None, help="可选 BGM 音频路径")

    cl = sub.add_parser("clean", help="清理（dry-run）")
    cl.add_argument("workspace")
    cl.add_argument("--yes", action="store_true", help="实际删除（默认仅 dry-run 报告）")
    return p


def _doctor() -> int:
    try:
        cfg = Config.load()
        for name, (ok, msg) in cfg.key_status().items():
            print(f"[{'OK' if ok else 'WARN'}] {name}: {msg}")
    except ConfigError as e:
        print(f"[BAD] 配置: {e}")
    return 0


def _new(args) -> int:
    try:
        ws = Workspace.create(args.workspace, args.video, args.project_id)
        run = ws.load()
        print(f"[new] 工作区已创建: {ws.root}  stage={run.current_stage.value}")
        return 0
    except WorkspaceError as e:
        print(f"[new] 失败: {e}", file=sys.stderr)
        return 1


def _status(args) -> int:
    try:
        ws = Workspace(Path(args.workspace))
        run = ws.load()
    except WorkspaceError as e:
        print(f"[status] 失败: {e}", file=sys.stderr)
        return 1
    print(f"project_id : {run.project_id}")
    print(f"stage      : {run.current_stage.value}")
    print(f"status     : {run.status.value}")
    print(f"live       : {run.live}  max_submits={run.max_submits}")
    print(f"approvals  : {', '.join(run.approvals) or '(none)'}")
    print(f"cost entries: {len(run.cost_ledger)}")
    return 0


def _not_implemented(cmd: str, wp: str) -> int:
    print(f"[TODO] `{cmd}` 由 {wp} 实现（WP1 仅冻结接口与闸口拦截）", file=sys.stderr)
    return 2


def _deliver(args) -> int:
    try:
        ws = Workspace(Path(args.workspace))
        run = ws.load()
    except WorkspaceError as e:
        print(f"[deliver] 失败: {e}", file=sys.stderr)
        return 1
    try:
        pipeline.execute_stage(Stage.DELIVER, ws, run, bgm=args.bgm)
    except workflow.GateBlocked as e:
        print(f"[deliver] 闸口拦截：{e}", file=sys.stderr)
        return 1
    return 0


def _clean(args) -> int:
    try:
        ws = Workspace(Path(args.workspace))
    except WorkspaceError as e:
        print(f"[clean] 失败: {e}", file=sys.stderr)
        return 1
    cands = cleanup.plan_cleanup(str(ws.root), dry_run=not args.yes)
    if args.yes:
        print(f"[clean] 已删除 {len(cands)} 个临时文件")
        for c in cands:
            print(f"  删除 {c}")
    else:
        print(f"[clean] dry-run：{len(cands)} 个候选临时文件（--yes 实际删除）")
        for c in cands:
            print(f"  将删除 {c}")
    return 0


def _approve(args) -> int:
    try:
        ws = Workspace(Path(args.workspace))
        run = ws.load()
    except WorkspaceError as e:
        print(f"[approve] 失败: {e}", file=sys.stderr)
        return 1
    gate = Gate(args.gate)
    workflow.approve_gate(run, gate, by=args.by, note=f"CLI approve {gate.value}")
    ws.save(run)
    print(f"[approve] 闸口 {gate.value} 已批准（by {args.by}）")
    return 0


def _run(args) -> int:
    try:
        ws = Workspace(Path(args.workspace))
        run = ws.load()
    except WorkspaceError as e:
        print(f"[run] 失败: {e}", file=sys.stderr)
        return 1
    try:
        if args.stage:
            pipeline.execute_stage(Stage(args.stage), ws, run)
        else:
            pipeline.run_flow(ws, run)
    except workflow.GateBlocked as e:
        print(f"[run] 闸口拦截，已停止：{e}", file=sys.stderr)
        return 1
    except RuntimeError as e:
        print(f"[run] 失败：{e}", file=sys.stderr)
        return 1
    return 0


def _retry(args) -> int:
    try:
        ws = Workspace(Path(args.workspace))
        run = ws.load()
    except WorkspaceError as e:
        print(f"[retry] 失败: {e}", file=sys.stderr)
        return 1
    if not run.live:
        print(
            "[retry] 离线模式：不重跑需 Live 的生成；用已批准 Live Pilot 运行以续跑",
            file=sys.stderr,
        )
        return 0
    from .generation import service as G

    try:
        workflow.require_gate(run, Gate.COST)
    except workflow.GateBlocked as e:
        print(f"[retry] 闸口拦截：{e}", file=sys.stderr)
        return 1
    cfg = Config.load()
    segs = ws.planning / "segments.json"
    if not segs.exists():
        print("[retry] 缺少 planning/segments.json，无法续跑生成", file=sys.stderr)
        return 1
    only = set(args.segments.split(",")) if args.segments else None
    summary = G.run(
        str(segs), str(ws.clips), str(ws.audio), cfg,
        only=only, manifest=run, lock_path=str(ws.lock_path),
    )
    print(f"[retry] 生成续跑摘要：{summary}")
    ws.save(run)
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.cmd == "doctor":
        return _doctor()
    if args.cmd == "new":
        return _new(args)
    if args.cmd == "status":
        return _status(args)
    if args.cmd == "run":
        return _run(args)
    if args.cmd == "approve":
        return _approve(args)
    if args.cmd == "retry":
        return _retry(args)
    if args.cmd == "deliver":
        return _deliver(args)
    if args.cmd == "clean":
        return _clean(args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
