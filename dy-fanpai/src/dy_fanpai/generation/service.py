"""generation/service.py — P4 生成编排：路由 / 锁 / 提交意图 / 费用硬上限 / 断点续跑（WP4）。

忠实复刻原项目 gen_segments.run 的编排与铁律，收归一处并补齐 WP4 新要求
（EXECUTION_PLAN §P4）：
- 人物/口播走即梦；纯产品 i2v 可选即梦/Ark/小云雀/MiniMax/ComfyUI（route_backend）；
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
from . import ark, comfyui, dreamina, minimax, xyq


# ---------------------------------------------------------------------------
# 确定性函数（离线可测）
# ---------------------------------------------------------------------------
def route_backend(seg: dict, alt: str | None = None) -> str:
    """人物/口播(mm)默认走即梦（口型驱动）；纯产品 i2v 可走替代后端(ark/xyq)，否则即梦。

    硬规则放宽（2026-08-05）：mm 段**无真人出镜**（纯画外音 + 手部/产品展示，
    shots 全部 host_on_camera=False 或 person 不含面部）时不需要口型，
    允许走 alt 后端（如 comfyui_h3）；有主播出镜的 mm 段仍必须走即梦。
    """
    if seg["type"] == "mm":
        shots = seg.get("shots") or []
        has_host = any(
            (s.get("host_on_camera") is True)
            or ("脸" in (s.get("person") or "") or "面部" in (s.get("person") or ""))
            for s in shots
        )
        if not has_host:
            return alt if alt else "dreamina"
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

    文件不存在→创建并返回 True；已存在→检查持有进程是否存活：
    - 持有进程已死（如被 kill -9 / 沙盒超时）→ 视为陈旧锁，回收后加锁返回 True
      （2026-08-05 修复：此前 137 杀进程残留锁，导致工作区永久"被占用"需手工删）；
    - 持有进程存活 → 返回 False（真实并发占用）。
    测试可传 lock_path=None 跳过。
    """
    if lock_path is None:
        return True
    if os.path.exists(lock_path):
        # 读持有者 PID，判断是否还活着
        try:
            owner = int(open(lock_path, encoding="utf-8").read().strip())
        except (OSError, ValueError):
            owner = 0  # 文件损坏/空 → 视为陈旧
        if owner > 0 and _pid_alive(owner):
            return False
        # 陈旧锁：清除后继续加锁
        try:
            os.remove(lock_path)
        except OSError:
            pass
    os.makedirs(os.path.dirname(os.path.abspath(lock_path)), exist_ok=True)
    with open(lock_path, "w", encoding="utf-8") as f:
        f.write(str(os.getpid()))
    return True


def _pid_alive(pid: int) -> bool:
    """检查 PID 是否存活（跨平台 best-effort；macOS/Linux 用 kill 0）。"""

    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # 存在但无权限查看 → 视为存活
    except OSError:
        return False


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
        "minimax": {
            "submit": lambda seg, ad, cfg: minimax.submit_i2v(
                seg["anchor"], seg["prompt"], cfg, duration=int(seg["duration"])),
            "wait": lambda tid, dst, cfg: minimax.wait_download(tid, dst, cfg),
        },
        "comfyui": {
            "submit": lambda seg, ad, cfg: comfyui.submit_i2v(
                seg["anchor"], seg["prompt"], cfg, duration=int(seg["duration"])),
            "wait": lambda tid, dst, cfg: comfyui.wait_download(tid, dst, cfg),
        },
        "comfyui_h3": {
            "submit": lambda seg, ad, cfg: comfyui.submit_h3_i2v(
                seg["anchor"], seg["prompt"], cfg, duration=int(seg["duration"])),
            "wait": lambda tid, dst, cfg: comfyui.wait_download(tid, dst, cfg),
        },
        "comfyui_h3_t2v": {
            "submit": lambda seg, ad, cfg: comfyui.submit_h3_t2v(
                seg["prompt"], cfg, duration=int(seg["duration"])),
            "wait": lambda tid, dst, cfg: comfyui.wait_download(tid, dst, cfg),
        },
        "comfyui_h3_r2v": {
            "submit": lambda seg, ad, cfg: comfyui.submit_h3_r2v(
                [seg["anchor"]], seg["prompt"], cfg, duration=int(seg["duration"])),
            "wait": lambda tid, dst, cfg: comfyui.wait_download(tid, dst, cfg),
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
    - mm 段永远走即梦；i2v 段走 i2v_backend（ark/xyq/minimax/comfyui/默认即梦）；
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

    # 锚图路径解析：segments 里 anchor/images 是相对 planning/ 的（如 assets/hero.jpg），
    # 提交前基于 plan_path 所在目录解析为绝对路径，保证各后端上传能读到文件。
    base = os.path.dirname(os.path.abspath(plan_path))
    for seg in segs:
        for key in ("anchor",):
            v = seg.get(key)
            if isinstance(v, str) and v and not os.path.isabs(v):
                cand = os.path.join(base, v)
                seg[key] = cand if os.path.exists(cand) else v
        imgs = seg.get("images")
        if isinstance(imgs, list):
            resolved = []
            for v in imgs:
                if isinstance(v, str) and v and not os.path.isabs(v):
                    cand = os.path.join(base, v)
                    resolved.append(cand if os.path.exists(cand) else v)
                else:
                    resolved.append(v)
            seg["images"] = resolved

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

            backend = route_backend(seg, alt=i2v_backend)
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
