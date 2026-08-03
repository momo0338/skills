"""WP6 并发与崩溃验收（验收门 6）：并发/崩溃不会静默重复提交。

机制：``generation/service.run`` 用 best-effort 文件锁（acquire_lock）+ 提交前
within_cap 硬上限 + 提交意图先写 task 文件占位，保证：
- 同一工作区同一时刻只有一个 run 在提交（并发锁）；
- 已达 max_submits 立即停止（费用硬上限）；
- 已存在 clip / 已存在 task 的检测保证续跑/重试不重复提交。
"""

from __future__ import annotations

import json
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from dy_fanpai.config import Config
from dy_fanpai.generation import service
from dy_fanpai.models import ProvenanceEntry, ProviderName, RunManifest, Stage


class _MockBackends:
    """可控 Mock：submit 返回唯一 tid；wait 阻塞直到 go 事件，确保并发重叠。"""

    def __init__(self) -> None:
        self.holding = threading.Event()
        self.go = threading.Event()
        self._lock = threading.Lock()
        self._n = 0

    def make(self) -> dict:
        outer = self

        def submit(seg, ad, cfg):  # noqa: ANN001, ANN002, ANN003
            with outer._lock:
                outer._n += 1
                return f"tid-{outer._n}"

        def wait(tid, dst, cfg):  # noqa: ANN001, ANN002, ANN003
            outer.holding.set()
            outer.go.wait()
            Path(dst).write_bytes(b"x")
            return 1

        return {
            "dreamina": {"submit": submit, "wait": wait},
            "ark": {"submit": submit, "wait": wait},
            "xyq": {"submit": submit, "wait": wait},
        }


def _plan(tmp_path: Path) -> str:
    p = tmp_path / "segments.json"
    p.write_text(json.dumps([
        {"seg": "S1", "type": "i2v", "duration": 3, "prompt": "p", "anchor": "a"},
        {"seg": "S2", "type": "i2v", "duration": 3, "prompt": "p", "anchor": "a"},
    ]), encoding="utf-8")
    return str(p)


def test_acquire_lock_excludes_concurrent(tmp_path):
    lp = str(tmp_path / ".l")
    assert service.acquire_lock(lp) is True
    assert service.acquire_lock(lp) is False  # 已被占用
    service.release_lock(lp)
    assert service.acquire_lock(lp) is True


def test_within_cap_enforces_max():
    m = RunManifest(max_submits=1)
    m.provenance.append(ProvenanceEntry(
        stage=Stage.GENERATE, provider=ProviderName.DREAMINA, task_id="t1"))
    assert service.within_cap(m, m.max_submits) is False  # 已 1 次，再提交超上限
    m2 = RunManifest(max_submits=2)
    m2.provenance.append(ProvenanceEntry(
        stage=Stage.GENERATE, provider=ProviderName.DREAMINA, task_id="t1"))
    assert service.within_cap(m2, m2.max_submits) is True


def test_concurrent_run_no_duplicate_submit(tmp_path):
    mb = _MockBackends()
    clips = tmp_path / "clips"
    clips.mkdir()
    (tmp_path / "audio").mkdir()
    plan = _plan(tmp_path)
    lock = str(tmp_path / ".lock")
    cfg = Config.load()
    m = RunManifest(live=True, max_submits=10)

    with ThreadPoolExecutor(max_workers=2) as ex:
        f1 = ex.submit(
            service.run, plan, str(clips), str(tmp_path / "audio"), cfg,
            manifest=m, lock_path=lock, backends=mb.make(),
        )
        # 等 thread1 真正拿到锁并进入 wait（保证并发重叠）
        assert mb.holding.wait(timeout=10)
        f2 = ex.submit(
            service.run, plan, str(clips), str(tmp_path / "audio"), cfg,
            manifest=m, lock_path=lock, backends=mb.make(),
        )
        s2 = f2.result(timeout=10)
        mb.go.set()
        s1 = f1.result(timeout=10)

    # 并发保护：第二个 run 被锁挡住，不提交
    assert s2.get("locked") is True
    # 第一个 run 完成全部提交，无重复
    assert s1["submitted"] == 2
    task_ids = [c.task_id for c in m.cost_ledger if c.task_id]
    assert len(task_ids) == 2
    assert len(set(task_ids)) == 2  # 全部唯一，无重复提交
