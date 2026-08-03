"""generation/service.py — P4 生成编排：路由 / 锁 / 提交意图 / 费用硬上限 / 断点续跑（WP4）。

忠实复刻原项目 gen_segments.run 的编排与铁律，收归一处并补齐 WP4 新要求
（EXECUTION_PLAN §P4）：
- 人物/口播走即梦；纯产品 i2v 可选即梦/Ark/小云雀（route_backend）；
- 同一工作区加锁（acquire_lock）；
- 每段提交前写提交意图（GenerationTask 文件 + provenance）；
- max_submits 由代码硬执行（within_cap）；
- 有 task ID 优先查询和下载（断点续跑/崩溃恢复）；
- 下载后做解码检查（media.download 复用）；
- 单段失败不带崩整批，状态显示部分失败；
- usage/费用写入 run.json（cost_ledger）。

确定性函数（route_backend / submits_so_far / within_cap / load_task / save_task /
acquire_lock）与网络编排（run）解耦，便于离线单测与 Mock。

为支持 T4 Mock，run 接受 ``backends`` 依赖注入：{"dreamina"/"ark"/"xyq":
{"submit": fn(seg,audio_dir,cfg)->task_id|None, "wait": fn(tid,dst,cfg)->size|fail|None}}。
不注入时用真实后端（需 CLI/API 与凭证，默认不跑）。
"""

from __future__ import annotations

import json
import os

from ..config import Config
from ..models import (
    CostEntry,
    GenerationTask,
    ProvenanceEntry,
    ProviderName,
    RunManifest,
    Stage,
)
from . import ark, dreamina, xyq


# ---------------------------------------------------------------------------
# 确定性函数（离线可测）
# ---------------------------------------------------------------------------
def route_backend(seg: dict, alt: str | None = None) -> str:
    """人物/口播(mm)必须走即梦（口型驱动）；纯产品 i2v 可走替代后端(ark/xyq)，否则即梦。

    mm 段因需口型不被 i2v 后端接管——这是路由硬规则。
    """
    if seg["type"] == "mm":
        return "dreamina"
    return alt if alt else "dreamina"


def submits_so_far(manifest: RunManifest) -> int:
    """已记录的生成提交数（provenance 中 stage==GENERATE 的条目）。"""
    return len([p for p in manifest.provenance if p.stage == Stage.GENERATE])


def within_cap(manifest: RunManifest, max_submits: int) -> bool:
    """提交数是否仍在 max_submits 硬上限内。"""
    if max_submits <= 0:
        return False
    return submits_so_far(manifest) < max_submits


def load_task(path: str) -> GenerationTask | None:
    """读取段任务文件（断点续跑用）。不存在/损坏返回 None。"""
    if not os.path.exists(path):
        return None
    try:
        return GenerationTask.model_validate(json.load(open(path, encoding="utf-8")))
    except Exception:  # noqa: BLE001
        return None


def save_task(path: str, task: GenerationTask) -> None:
    """写段任务文件（提交意图 + 崩溃恢复）。"""
    json.dump(task.model_dump(), open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)


def acquire_lock(lock_path: str | None) -> bool:
    """同一工作区加锁（best-effort）。

    文件不存在→创建并返回 True；已存在（视为并发占用）→返回 False。
    测试可传 lock_path=None 跳过。真实并发由调用方在 run 前先 acquire。
    """
    if lock_path is None:
        return True
    if os.path.exists(lock_path):
        return False
    os.makedirs(os.path.dirname(os.path.abspath(lock_path)), exist_ok=True)
    with open(lock_path, "w", encoding="utf-8") as f:
        f.write(str(os.getpid()))
    return True


def release_lock(lock_path: str | None) -> None:
    if lock_path and os.path.exists(lock_path):
        try:
            os.remove(lock_path)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# 后端装配（默认真实；可 DI 注入 Mock）
# ---------------------------------------------------------------------------
def _default_backends() -> dict:
    return {
        "dreamina": {
            "submit": lambda seg, ad, cfg: dreamina.submit(seg, ad, cfg)[0],
            "wait": lambda tid, dst, cfg: dreamina.wait_download(tid, dst, cfg),
        },
        "ark": {
            "submit": lambda seg, ad, cfg: ark.submit_i2v(
                seg["anchor"], seg["prompt"], cfg, duration=int(seg["duration"])),
            "wait": lambda tid, dst, cfg: ark.wait_download(tid, dst, cfg)[0],
        },
        "xyq": {
            "submit": lambda seg, ad, cfg: xyq.submit_i2v(
                seg["anchor"], seg["prompt"], cfg, duration=int(seg["duration"])),
            "wait": lambda tid, dst, cfg: xyq.wait_download(tid, dst, cfg)[0],
        },
    }


# ---------------------------------------------------------------------------
# 编排主入口
# ---------------------------------------------------------------------------
def run(
    plan_path,
    clips_dir: str,
    audio_dir: str | None,
    cfg: Config,
    *,
    only: set[str] | None = None,
    dry: bool = False,
    i2v_backend: str = "dreamina",
    manifest: RunManifest | None = None,
    lock_path: str | None = None,
    backends: dict | None = None,
) -> dict:
    """生成主循环（编排层；默认真实后端需凭证/CLI，测试用 backends= 注入 Mock）。

    返回摘要：{submitted, downloaded, skipped, restored, failed, cap_hit}。

    铁律：
    - mm 段永远走即梦；i2v 段走 i2v_backend（ark/xyq/默认即梦）；
    - 已存在 clip → 跳过（断点续跑）；有 task 文件 → 优先查询下载；
    - 每段提交前检查 within_cap（max_submits 硬上限），超限即停；
    - 单段失败 caught，继续下一段，计入 failed。
    """
    segs = json.load(open(plan_path, encoding="utf-8"))
    if only:
        segs = [s for s in segs if s["seg"] in only]
    manifest = manifest or RunManifest()
    backend_map = backends or _default_backends()
    os.makedirs(clips_dir, exist_ok=True)

    if not acquire_lock(lock_path):
        print("[gen][锁] 工作区已被占用,放弃本次运行")
        return {"locked": True}

    summary = {"submitted": 0, "downloaded": 0, "skipped": 0, "restored": 0,
               "failed": 0, "cap_hit": False}
    try:
        for seg in segs:
            name = seg["seg"]
            dst = os.path.join(clips_dir, f"{name}.mp4")
            if os.path.exists(dst):
                print(f"[skip] {name} 已存在")
                summary["skipped"] += 1
                continue

            backend = route_backend(seg, alt=i2v_backend if seg["type"] != "mm" else None)
            tag = {"mm": "口播", "i2v": "image2video"}[seg["type"]]
            print(f"\n===== {name} {tag} {seg['duration']}s [{backend}] =====", flush=True)

            # 断点续跑：有 task 文件 → 优先查询下载
            meta_path = os.path.join(clips_dir, f"{name}.meta.json")
            existing = load_task(meta_path)
            if existing and existing.task_id:
                if dry:
                    print(f"  [dry-run] 恢复 {backend} task={existing.task_id}")
                    continue
                try:
                    res = backend_map[backend]["wait"](existing.task_id, dst, cfg)
                    if isinstance(res, int) and res > 0:
                        print(f"  [restored] {name}.mp4 {res // 1024}KB")
                        summary["restored"] += 1
                        manifest.provenance.append(ProvenanceEntry(
                            stage=Stage.GENERATE, provider=ProviderName(backend), task_id=existing.task_id))
                        continue
                    if res is None:
                        print(f"  [pending] 未完成,task={existing.task_id} 稍后补抓")
                        continue
                    print(f"  [{res}]")
                except Exception as e:  # noqa: BLE001 - 恢复失败不崩批
                    print(f"  [ERR 恢复 {type(e).__name__}: {str(e)[:120]}] 转重新提交")

            # 费用硬上限：提交前检查。max_submits 来自 run.json(manifest),Config 无此字段
            if not within_cap(manifest, manifest.max_submits) and not dry:
                print(f"[gen][上限] 已达 max_submits={manifest.max_submits},停止提交")
                summary["cap_hit"] = True
                break

            if dry:
                print("  [dry-run] 跳过真实提交")
                continue

            try:
                # 提交意图：先写 task 文件占位,再真实提交
                task = GenerationTask(segment=name, provider=ProviderName(backend), status="submitted")
                save_task(meta_path, task)
                tid = backend_map[backend]["submit"](seg, audio_dir, cfg)
                if not tid:
                    print("  [FAIL 提交无id]")
                    summary["failed"] += 1
                    continue
                task.task_id = tid
                task.submit_id = tid
                task.status = "polling"
                task.submitted_at = _now()
                save_task(meta_path, task)
                manifest.provenance.append(ProvenanceEntry(
                    stage=Stage.GENERATE, provider=ProviderName(backend), task_id=tid))
                manifest.cost_ledger.append(CostEntry(
                    provider=ProviderName(backend), task_id=tid,
                    note=f"submit {name} via {backend}"))
                summary["submitted"] += 1
                print(f"  submit_id={tid}", flush=True)

                # 等待下载
                res = backend_map[backend]["wait"](tid, dst, cfg)
                if isinstance(res, int) and res > 0:
                    print(f"  [downloaded] {name}.mp4 {res // 1024}KB")
                    task.status = "done"
                    save_task(meta_path, task)
                    summary["downloaded"] += 1
                elif res is None:
                    print(f"  [pending] 未完成,submit_id={tid} 稍后补抓")
                else:
                    print(f"  [{res}]")
                    summary["failed"] += 1
            except Exception as e:  # noqa: BLE001 - 单段失败不带崩整批
                print(f"  [ERR {type(e).__name__}: {str(e)[:120]}] 继续下一段")
                summary["failed"] += 1
    finally:
        release_lock(lock_path)

    print(f"\n[gen] 本轮: 提交 {summary['submitted']} / 下载 {summary['downloaded']} / "
          f"跳过 {summary['skipped']} / 恢复 {summary['restored']} / 失败 {summary['failed']}")
    return summary


def _now() -> str:
    from datetime import UTC, datetime
    return datetime.now(UTC).isoformat()
