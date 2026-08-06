"""dy_fanpai 数据模型（WP1 冻结）。

本文件定义 run.json v1 schema、七阶段、11 状态值、四闸口、Provider 枚举与
公共数据模型。WP1 冻结后，任何对这些模型的修改必须走 EXECUTION_PLAN §12.2
变更流程，不得自行复制或新增第二套状态文件。
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# 七阶段流程（EXECUTION_PLAN §5）
# ---------------------------------------------------------------------------
class Stage(StrEnum):
    PREPARE = "prepare"  # P0 准备
    REVERSE = "reverse"  # P1 反推
    PLAN = "plan"  # P2 规划与审核
    AUDIO = "audio"  # P3 音频
    GENERATE = "generate"  # P4 生成
    ASSEMBLE = "assemble"  # P5 装配与质检
    DELIVER = "deliver"  # P6 交付与清理


# ---------------------------------------------------------------------------
# 11 个状态值（EXECUTION_PLAN §5，唯一保留的状态集合）
# ---------------------------------------------------------------------------
class RunStatus(StrEnum):
    CREATED = "created"
    READY = "ready"
    REVERSED = "reversed"
    PLANNED = "planned"
    APPROVED = "approved"
    AUDIO_READY = "audio_ready"
    GENERATING = "generating"
    ASSEMBLED = "assembled"
    QC_PASSED = "qc_passed"
    DELIVERED = "delivered"
    FAILED = "failed"


# ---------------------------------------------------------------------------
# 四个明确闸口（EXECUTION_PLAN §6）
# ---------------------------------------------------------------------------
class Gate(StrEnum):
    RIGHTS = "rights"  # G1 权利与隐私
    PLAN = "plan"  # G2 计划审核
    COST = "cost"  # G3 费用审批
    QC = "qc"  # G4 最终人工 QC


# ---------------------------------------------------------------------------
# Provider 枚举（能力矩阵见 WP0_BASELINE §5）
# ---------------------------------------------------------------------------
class ProviderName(StrEnum):
    ARK = "ark"  # 火山方舟：反推腿1 / 评委 / 生成
    KIMI = "kimi"  # Kimi K3：反推腿2
    DREAMINA = "dreamina"  # 即梦：人物口播 / 纯产品 i2v
    XYQ = "xyq"  # 小云雀
    MINIMAX = "minimax"  # MiniMax H3（API 直连）
    COMFYUI = "comfyui"  # 自建 ComfyUI：Wan2.x i2v
    COMFYUI_H3 = "comfyui_h3"  # 自建 ComfyUI：MiniMax H3(FL2VA/ref2va)
    COMFYUI_H3_T2V = "comfyui_h3_t2v"  # 自建 ComfyUI：H3 文生视频
    COMFYUI_H3_R2V = "comfyui_h3_r2v"  # 自建 ComfyUI：H3 参考生视频
    COSYVOICE = "cosyvoice"  # CosyVoice TTS
    SEEDVC = "seedvc"  # Seed-VC 换声
    JIANYING = "jianying"  # 剪映草稿交付


# ---------------------------------------------------------------------------
# 公共记录结构
# ---------------------------------------------------------------------------
class CostEntry(BaseModel):
    timestamp: str = Field(default_factory=lambda: _now())
    provider: ProviderName
    task_id: str | None = None
    amount: float = 0.0
    currency: str = "CNY"
    note: str = ""


class Approval(BaseModel):
    gate: Gate
    approved: bool = False
    approved_at: str | None = None
    approved_by: str | None = None
    note: str = ""


class ArtifactRef(BaseModel):
    kind: str  # e.g. "shotlist", "segments", "full", "final"
    path: str
    stage: Stage | None = None
    created_at: str = Field(default_factory=lambda: _now())


class ProvenanceEntry(BaseModel):
    stage: Stage
    provider: ProviderName | None = None
    task_id: str | None = None
    source_sha: str | None = None


class RemoteUpload(BaseModel):
    provider: ProviderName
    uri: str
    uploaded_at: str = Field(default_factory=lambda: _now())


class ErrorRecord(BaseModel):
    stage: Stage | None = None
    message: str
    recovered: bool = False
    at: str = Field(default_factory=lambda: _now())


# ---------------------------------------------------------------------------
# run.json v1 主清单（EXECUTION_PLAN §4）
# ---------------------------------------------------------------------------
class RunManifest(BaseModel):
    schema_version: int = 1
    project_id: str = ""
    current_stage: Stage = Stage.PREPARE
    status: RunStatus = RunStatus.CREATED

    source_video: str | None = None
    source_hash: str | None = None

    rights_confirmation: Approval | None = None
    configuration_snapshot: dict[str, Any] = Field(default_factory=dict)
    stage_results: dict[str, Any] = Field(default_factory=dict)
    approvals: dict[str, Approval] = Field(default_factory=dict)
    artifacts: list[ArtifactRef] = Field(default_factory=list)
    provenance: list[ProvenanceEntry] = Field(default_factory=list)
    cost_ledger: list[CostEntry] = Field(default_factory=list)
    remote_uploads: list[RemoteUpload] = Field(default_factory=list)
    errors: list[ErrorRecord] = Field(default_factory=list)

    live: bool = False
    max_submits: int = 0


# ---------------------------------------------------------------------------
# 单个生成任务（generation/tasks/S1.json，EXECUTION_PLAN §4）
# ---------------------------------------------------------------------------
class GenerationTask(BaseModel):
    segment: str
    provider: ProviderName
    task_id: str | None = None
    status: str = "pending"  # pending | submitted | polling | done | failed
    submit_id: str | None = None
    submitted_at: str | None = None
    meta: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# 规划层数据模型（WP2 填充逻辑，WP1 仅冻结字段）
# ---------------------------------------------------------------------------
class Shot(BaseModel):
    start: float
    end: float
    person: str = ""
    action: str = ""
    subject: str = ""
    onscreen_text: str = ""
    dialogue: str = ""


class Segment(BaseModel):
    seg: str
    shots: list[Shot] = Field(default_factory=list)
    type: str = "kou"  # kou | hero | package | dynamic
    dialogue: str = ""
    duration: float = 0.0
    product_anchors: list[str] = Field(default_factory=list)
    prompt: str = ""


def _now() -> str:
    return datetime.now(UTC).isoformat()
