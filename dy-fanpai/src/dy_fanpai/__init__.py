"""dy_fanpai — 抖音带货视频翻拍。

WP1 冻结核心：models / config / workspace / workflow / cli。业务逻辑由
WP2–WP5 在各子包内实现。
"""

__version__ = "0.1.0"

from .models import (
    Approval,
    ArtifactRef,
    CostEntry,
    ErrorRecord,
    Gate,
    GenerationTask,
    ProvenanceEntry,
    ProviderName,
    RemoteUpload,
    RunManifest,
    RunStatus,
    Segment,
    Shot,
    Stage,
)
from .workflow import (
    GateBlocked,
    MaxSubmitsExceeded,
    add_cost,
    approve_gate,
    enforce_max_submits,
    mark_stage_done,
    require_gate,
    set_stage,
    set_status,
)
from .workspace import Workspace, WorkspaceError

__all__ = [
    "__version__",
    "RunManifest",
    "RunStatus",
    "Stage",
    "Gate",
    "ProviderName",
    "Segment",
    "Shot",
    "GenerationTask",
    "Approval",
    "ArtifactRef",
    "CostEntry",
    "ErrorRecord",
    "ProvenanceEntry",
    "RemoteUpload",
    "Workspace",
    "WorkspaceError",
    "GateBlocked",
    "MaxSubmitsExceeded",
    "set_stage",
    "set_status",
    "mark_stage_done",
    "require_gate",
    "approve_gate",
    "enforce_max_submits",
    "add_cost",
]
