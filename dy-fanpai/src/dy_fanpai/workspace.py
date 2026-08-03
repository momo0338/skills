"""dy_fanpai 工作区（WP1 冻结）。

管理 run.json 读写、工作区目录布局（EXECUTION_PLAN §4）、文件锁与产物登记。
所有路径集中在此，避免原项目分散写盘的反模式。
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

from .models import ArtifactRef, RunManifest, Stage

WORKSPACE_FILE = "run.json"
LOCK_FILE = ".dy-fan-pai.lock"


class WorkspaceError(RuntimeError):
    """工作区初始化或读写失败。"""


class Workspace:
    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.run_path = self.root / WORKSPACE_FILE
        self.lock_path = self.root / LOCK_FILE
        self._lock_fd: int | None = None

    # ---- 布局 ----
    @property
    def inputs(self) -> Path:
        return self.root / "inputs"

    @property
    def reverse(self) -> Path:
        return self.root / "reverse"

    @property
    def planning(self) -> Path:
        return self.root / "planning"

    @property
    def audio(self) -> Path:
        return self.root / "audio" / "segments"

    @property
    def generation(self) -> Path:
        return self.root / "generation"

    @property
    def tasks(self) -> Path:
        return self.generation / "tasks"

    @property
    def clips(self) -> Path:
        return self.generation / "clips"

    @property
    def qc(self) -> Path:
        return self.root / "qc"

    @property
    def output(self) -> Path:
        return self.root / "output"

    # ---- run.json ----
    def load(self) -> RunManifest:
        if not self.run_path.exists():
            raise WorkspaceError(f"工作区缺少 {WORKSPACE_FILE}：{self.run_path}")
        data = json.loads(self.run_path.read_text(encoding="utf-8"))
        return RunManifest.model_validate(data)

    def save(self, run: RunManifest) -> None:
        self.run_path.write_text(run.model_dump_json(indent=2), encoding="utf-8")

    def register_artifact(
        self, run: RunManifest, kind: str, path: str, stage: Stage | None = None
    ) -> None:
        run.artifacts.append(ArtifactRef(kind=kind, path=str(path), stage=stage))
        self.save(run)

    # ---- 初始化 ----
    @classmethod
    def create(cls, root: str | Path, source_video: str | Path, project_id: str = "") -> Workspace:
        root = Path(root)
        if root.exists() and any(root.iterdir()):
            raise WorkspaceError(f"目标目录非空：{root}")
        for d in (
            root / "inputs",
            root / "reverse",
            root / "planning",
            root / "audio" / "segments",
            root / "generation" / "tasks",
            root / "generation" / "clips",
            root / "qc",
            root / "output",
        ):
            d.mkdir(parents=True, exist_ok=True)

        src = Path(source_video)
        if not src.exists():
            raise WorkspaceError(f"源视频不存在：{src}")
        dst = root / "inputs" / src.name
        shutil.copy(src, dst)

        sha = _sha256(dst)
        run = RunManifest(
            project_id=project_id or root.name,
            source_video=str(dst),
            source_hash=sha,
            current_stage=Stage.PREPARE,
            status=RunManifest().status,
        )
        ws = cls(root)
        ws.save(run)
        return ws

    # ---- 文件锁 ----
    def acquire_lock(self) -> None:
        self._lock_fd = os.open(self.lock_path, os.O_CREAT | os.O_RDWR, 0o644)
        try:
            fcntl.flock(self._lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            os.close(self._lock_fd)
            self._lock_fd = None
            raise WorkspaceError("另一实例已持有工作区锁，禁止并发写入")

    def release_lock(self) -> None:
        if self._lock_fd is not None:
            fcntl.flock(self._lock_fd, fcntl.LOCK_UN)
            os.close(self._lock_fd)
            self._lock_fd = None


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def probe_duration(path: str) -> float:
    out = subprocess.check_output(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", path]
    ).strip()
    return float(out)
