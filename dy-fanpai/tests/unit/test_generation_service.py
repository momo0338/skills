"""generation/service.py 离线单测(编排逻辑 + Mock 后端,不碰即梦/Ark/小云雀)。

验证 WP4 铁律:路由 / 费用硬上限 / 提交意图 / 断点续跑 / 崩溃恢复 / 单段失败隔离 / 锁。
"""

import json
import os

from dy_fanpai.config import Config
from dy_fanpai.generation import service as S
from dy_fanpai.models import GenerationTask, ProvenanceEntry, ProviderName, RunManifest, Stage


def _plan(path, segs):
    json.dump(segs, open(path, "w", encoding="utf-8"))


def _fake_backends(state, fail_seg=None):
    def submit(seg, ad, cfg):
        if fail_seg and seg["seg"] == fail_seg:
            raise RuntimeError("boom")
        state["submitted"] += 1
        return f"tid-{seg['seg']}"

    def wait(tid, dst, cfg):
        open(dst, "wb").write(b"fakeclip")
        return 1024 * 50

    return {
        "dreamina": {"submit": submit, "wait": wait},
        "ark": {"submit": submit, "wait": wait},
        "xyq": {"submit": submit, "wait": wait},
    }


# ---------------------------------------------------------------------------
# 确定性路由 / 上限 / 任务文件 / 锁
# ---------------------------------------------------------------------------
def test_route_backend():
    assert S.route_backend({"type": "mm"}) == "dreamina"
    assert S.route_backend({"type": "i2v"}, alt="ark") == "ark"
    assert S.route_backend({"type": "i2v"}) == "dreamina"
    # mm 段不被 i2v 替代后端接管(口型需即梦)
    assert S.route_backend({"type": "mm"}, alt="ark") == "dreamina"


def test_within_cap():
    m = RunManifest(max_submits=2)
    assert S.within_cap(m, 2) is True
    m.provenance.append(ProvenanceEntry(
        stage=Stage.GENERATE, provider=ProviderName("dreamina"), task_id="t1"))
    assert S.within_cap(m, 2) is True
    m.provenance.append(ProvenanceEntry(
        stage=Stage.GENERATE, provider=ProviderName("dreamina"), task_id="t2"))
    assert S.within_cap(m, 2) is False
    assert S.within_cap(RunManifest(max_submits=0), 0) is False


def test_load_save_task(tmp_path):
    p = str(tmp_path / "S1.meta.json")
    t = GenerationTask(
        segment="S1", provider=ProviderName("dreamina"), task_id="tid1", status="polling")
    S.save_task(p, t)
    t2 = S.load_task(p)
    assert t2.task_id == "tid1" and t2.segment == "S1"
    assert S.load_task(str(tmp_path / "missing.json")) is None


def test_acquire_lock(tmp_path):
    lp = str(tmp_path / ".lock")
    assert S.acquire_lock(lp) is True
    assert S.acquire_lock(lp) is False  # 已占用
    S.release_lock(lp)
    assert S.acquire_lock(lp) is True


# ---------------------------------------------------------------------------
# 编排:提交全部 / 费用上限 / 断点续跑 / 崩溃恢复 / 单段失败隔离
# ---------------------------------------------------------------------------
def test_run_submits_all(tmp_path):
    plan = tmp_path / "plan.json"
    _plan(plan, [{"seg": "S1", "type": "mm", "duration": 5},
                 {"seg": "S2", "type": "i2v", "duration": 5, "anchor": "p.png"}])
    clips = tmp_path / "clips"
    state = {"submitted": 0}
    m = RunManifest(max_submits=5)
    summary = S.run(str(plan), str(clips), None, Config(), manifest=m,
                    backends=_fake_backends(state), lock_path=None)
    assert summary["submitted"] == 2 and summary["downloaded"] == 2
    assert os.path.exists(clips / "S1.mp4") and os.path.exists(clips / "S2.mp4")
    assert os.path.exists(clips / "S1.meta.json")
    assert len(m.provenance) == 2


def test_run_cost_cap(tmp_path):
    plan = tmp_path / "plan.json"
    _plan(plan, [{"seg": "S1", "type": "mm", "duration": 5},
                 {"seg": "S2", "type": "i2v", "duration": 5, "anchor": "p.png"}])
    state = {"submitted": 0}
    m = RunManifest(max_submits=1)
    summary = S.run(str(plan), str(tmp_path / "clips"), None, Config(), manifest=m,
                    backends=_fake_backends(state), lock_path=None)
    assert summary["submitted"] == 1
    assert summary["cap_hit"] is True


def test_run_checkpoint_resume(tmp_path):
    plan = tmp_path / "plan.json"
    _plan(plan, [{"seg": "S1", "type": "mm", "duration": 5},
                 {"seg": "S2", "type": "i2v", "duration": 5, "anchor": "p.png"}])
    clips = tmp_path / "clips"
    clips.mkdir()
    (clips / "S1.mp4").write_bytes(b"done")
    state = {"submitted": 0}
    m = RunManifest(max_submits=5)
    summary = S.run(str(plan), str(clips), None, Config(), manifest=m,
                    backends=_fake_backends(state), lock_path=None)
    assert summary["skipped"] == 1 and summary["submitted"] == 1
    assert os.path.exists(clips / "S2.mp4")


def test_run_restore_from_task(tmp_path):
    plan = tmp_path / "plan.json"
    _plan(plan, [{"seg": "S1", "type": "mm", "duration": 5}])
    clips = tmp_path / "clips"
    clips.mkdir()
    # 预置 task 文件(崩溃恢复场景)
    S.save_task(str(clips / "S1.meta.json"),
                GenerationTask(segment="S1", provider=ProviderName("dreamina"),
                               task_id="tid-old", status="polling"))
    state = {"submitted": 0}
    m = RunManifest(max_submits=5)
    summary = S.run(str(plan), str(clips), None, Config(), manifest=m,
                    backends=_fake_backends(state), lock_path=None)
    assert summary["restored"] == 1 and summary["submitted"] == 0
    assert os.path.exists(clips / "S1.mp4")


def test_run_single_seg_failure_isolated(tmp_path):
    plan = tmp_path / "plan.json"
    _plan(plan, [{"seg": "S1", "type": "mm", "duration": 5},
                 {"seg": "S2", "type": "i2v", "duration": 5, "anchor": "p.png"}])
    state = {"submitted": 0}
    m = RunManifest(max_submits=5)
    summary = S.run(str(plan), str(tmp_path / "clips"), None, Config(), manifest=m,
                    backends=_fake_backends(state, fail_seg="S1"), lock_path=None)
    assert summary["failed"] == 1 and summary["submitted"] == 1  # S2 仍成功
    assert os.path.exists(tmp_path / "clips" / "S2.mp4")
