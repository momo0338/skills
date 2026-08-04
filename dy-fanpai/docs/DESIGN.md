# DESIGN.md · dy-fanpai 设计冻结

> 配套：`EXECUTION_PLAN.md` v2.2（唯一执行权威）、`DY_FANPAI_DETAILED_REFERENCE.md` v1.2（仅供人工查阅）、`WP0_BASELINE.md`（原项目基线）。
> 本文件由 **WP1** 产出，记录被冻结的公共接口与对 WP0 §9 冲突点的裁决。任何修改走 `EXECUTION_PLAN.md` §12.2 变更流程。

## 1. 权威与优先级

1. `EXECUTION_PLAN.md` 是唯一执行权威；发生冲突以它为准。
2. `DY_FANPAI_DETAILED_REFERENCE.md` 仅供查询，不覆盖执行方案。
3. `WP0_BASELINE.md` 是事实基线（原项目行为），用于 parity 证据；若与执行方案冲突，以执行方案为新架构依据，但原业务规则（如群戏人数硬约束）必须保留为 parity 项。
4. 事实优先级（执行方案 §0.7）：原项目固定提交代码/样例 > 原项目 DESIGN/SKILL/README > 执行方案 > Agent 推测。

## 2. 命名冻结（执行方案 §1）

```text
仓库/目录：dy-fanpai
Python 包：dy_fanpai        （src/dy_fanpai）
CLI：dy-fanpai
配置目录：~/.config/dy-fanpai/
环境变量前缀：DY_FANPAI_
```

## 3. 七阶段流程（冻结）

| 阶段 | 枚举值 | 说明 |
|---|---|---|
| P0 | `prepare` | 准备：doctor、建工作区、复制源视频、ffprobe、哈希、权利确认 |
| P1 | `reverse` | 反推：Seed 单反推 / Seed+Kimi 双反推 |
| P2 | `plan` | 规划与审核：资产清单、锚图路由、分段、Prompt、完备性、群戏、B 模式、人工审核 |
| P3 | `audio` | 音频：原音切段 / TTS / Seed-VC，统一输出 WAV + timing.json |
| P4 | `generate` | 生成：提交、轮询、下载、坏流重下、断点续跑 |
| P5 | `assemble` | 装配与质检：归一化、拼接 FULL、解码检查、口型证据、双视频评委、人工 QC |
| P6 | `deliver` | 交付与清理：SRT、贴字、烧字幕/BGM、剪映草稿、清理 dry-run |

## 4. 11 个状态值（冻结，唯一状态集合，执行方案 §5）

`created, ready, reversed, planned, approved, audio_ready, generating, assembled, qc_passed, delivered, failed`

- `current_stage`（Stage 枚举）与 `status`（RunStatus 枚举）是 `run.json` 两个独立字段。
- 权利确认 / 计划审核 / 费用批准是 `run.json.approvals` 中的闸口记录，**不**各自变成状态。

## 5. 四个闸口（冻结，执行方案 §6）

| 闸口 | 枚举值 | 触发点 | 拦截语义 |
|---|---|---|---|
| G1 | `rights` | P0 结束 | 确认参考视频/肖像/声音/商品素材可用与上传范围 |
| G2 | `plan` | P2 结束 | 确认分段/动作/锚图/台词/前三秒/包装/合规 |
| G3 | `cost` | P4 开始前 | 确认段 ID / Provider / max_submits |
| G4 | `qc` | P5 结束 | 确认人物/商品/包装/动作/口型，技术通过不可自动越过 |

`dy-fanpai run` 遇任一未批准闸口立即抛 `GateBlocked` 停止；四个闸口不能被 `run` 或 `--force` 绕过（最终验收门 §13(5)）。

## 6. run.json v1 schema（冻结，执行方案 §4）

字段（见 `src/dy_fanpai/models.py::RunManifest`）：

```text
schema_version=1
project_id
current_stage: Stage
status: RunStatus
source_video, source_hash
rights_confirmation: Approval
configuration_snapshot: dict
stage_results: dict
approvals: dict[gate, Approval]
artifacts: list[ArtifactRef]
provenance: list[ProvenanceEntry]
cost_ledger: list[CostEntry]
remote_uploads: list[RemoteUpload]
errors: list[ErrorRecord]
live: bool
max_submits: int
```

单任务状态独立存 `generation/tasks/<SEG>.json`（`GenerationTask`）。锁文件 `.dy-fan-pai.lock`（fcntl 排他锁，防并发写）。

## 7. 工作区目录（冻结，执行方案 §4）

```text
runs/<id>/
├── run.json
├── inputs/{source.mp4, assets.json, assets/}
├── reverse/{seed.json, kimi.json, dossier.md, frames/, shotlist.json}
├── planning/{required-assets.json, segments.json, segments.md}
├── audio/segments/ + timing.json
├── generation/{tasks/, clips/}
├── qc/
└── output/{FULL.mp4, FULL.srt, onscreen-text.md, FINAL.mp4}
```

## 8. Provider 最小接口（冻结）

任何生成后端实现以下协议（`generation/` 包内），不抹平差异、不设万能 Provider：

```python
class Provider(Protocol):
    name: ProviderName
    def submit(self, segment: Segment, prompt: str,
               anchors: list[Path], audio: Path | None = None) -> GenerationTask: ...
    def get_status(self, task: GenerationTask) -> str: ...      # pending|submitted|polling|done|failed
    def download(self, task: GenerationTask, dst: Path) -> Path: ...
```

统一约束（执行方案 §5 P4）：
- 每段提交前写提交意图；有 task ID 优先查询下载（不断重复提交）。
- 下载后做 ffmpeg 解码检查（`ffmpeg -v error -i dst -t 2 -f null -`），坏流重下。
- 单段失败不崩整批，但 `status` 显示部分失败。
- `usage` / 费用写入 `run.json.cost_ledger`。

评委（P5）默认沿用原项目 Ark Responses API + `ARK_SEED_MODEL`，一次输入原片与成片、关 thinking、流式。更换评委=显式设计变更。

## 9. 公共错误类型（冻结）

| 异常 | 含义 | 抛出点 |
|---|---|---|
| `ConfigError` | 配置缺失/非法 | `config` |
| `WorkspaceError` | 工作区读写/锁失败 | `workspace` |
| `GateBlocked` | 闸口未通过，必须停止 | `workflow.require_gate` |
| `MaxSubmitsExceeded` | 超过 `max_submits` 硬上限 | `workflow.enforce_max_submits` |
| `ProviderError` | Provider 通用错误 | `generation.*` |
| `DownloadError` | 解码探针失败/坏流 | `generation/download` |

## 10. fixture 命名（冻结，执行方案 §10）

```text
tests/fixtures/original/<scenario>__<variant>.json
```

- 六类场景 scenario：`A` / `migration` / `B` / `group` / `narration` / `product`
- 负例 variant：`short_audio` / `missing_anchor` / `bad_stream` / `pending_task`
- 黄金结果命名：同基名 `+ .golden.json`；负例同基名 `+ .expected.json`

WP0 已带入 `references/` 下公开样例（sample_shotlist / sample_segments / sample_assets），迁移为 `tests/fixtures/original/` 初版。

## 11. 文件所有权（冻结）

| 文件 / 目录 | owner | 说明 |
|---|---|---|
| `models.py` `config.py` `workspace.py` `workflow.py` `cli.py` | WP1 | 冻结后变更走 §12.2 |
| `reverse/` | WP2 | Seed/Kimi/merge |
| `planning/` | WP2 | planner + localization |
| `audio/` `media/` | WP3 | 切音频/2秒闸/TTS/换声/ffmpeg |
| `generation/` | WP4 | 即梦/Ark/小云雀 + 任务/锁/费用 |
| `quality/` `delivery/` | WP5 | QC/评委/字幕/剪映 |
| `tests/` | 各 WP + WP6 | 与实现同包提交 |
| `EXECUTION_PLAN.md` `DESIGN.md` `ACCEPTANCE.md` `CHANGELOG.md` | Integrator | 仅 Integrator 改 |

## 12. WP0 §9 冲突点裁决（WP1 冻结）

| # | 冲突 | 裁决 |
|---|---|---|
| 1 | `config` 双重标准（dreamina/tts-drama 硬编码绕过） | 全部二进制路径收归 `config.py`：`DY_FANPAI_DREAMINA_BIN`、`DY_FANPAI_TTS_DRAMA`、`DY_FANPAI_ARK_GEN_MODEL`，env 可覆盖，默认已知位置 |
| 2 | 2 秒闸注释 vs 代码矛盾 | 冻结规则：垫到 **≥2s 下限，绝不垫到计划段时长**。`pad = max(2.0, 实际音频时长)`；当实际时长≥2s 不延长（执行方案 §5 P3「只垫到2秒，不垫满计划时长」） |
| 3 | 时长双标（15 触发 / 12 计算） | 单值：`SEGMENT_MAX_DURATION=15`（触发拆分与硬上限），`SEGMENT_TARGET_DURATION=12`（拆分目标份数）。两者语义统一 |
| 4 | `detect_cuts` 默认 0.3 vs 实际 0.15 | 默认阈值冻结为 **0.15**（经验证抓同机位跳剪） |
| 5 | Ark 生成模型硬编码未走 env | 收归 `DY_FANPAI_ARK_GEN_MODEL`，默认 `doubao-seedance-2-0-260128` |
| 6 | `vc_segments` 内置音色被 gitignore 排除 | 内置音色**不随仓库分发**；音色来源走 U5（合法音色）。缺 `--target` 且无合法音色时明确报错，不静默退出 |
| 7 | `needed_assets` 只读默认 FORM_MAP | planner 优先读 `merged_form_map(cfg)`（用户 assets 存在时），默认 FORM_MAP 仅作回退 |
| 8 | `patch_cast` 原地覆写 segments.json 无备份 | 所有变更写新文件（如 `segments.next.json`）或先备份；禁止无 `--force` 原地破坏性覆写 |
| 9 | 多处无重试（seed/localize/judge/assemble/deliver） | 统一重试工具；seed_reverse/judge 主打分加重试；assemble/deliver 失败不崩整批（跳过+记录）；gen 既有三层重试保留 |
| 10 | 强 WSL 假设（deliver 路径转换） | `deliver` 支持 `platform` 设置；macOS 可跑 `final`（烧字幕，无需 WSL）；`jianying` 草稿模式仅当目标为 Windows/WSL 时才做路径转换，且需 U3 实机 |

## 13. 五条底线（执行方案 §2，不可精简）

1. 反推的主体/动作/关键颜色必须进生成提示词。
2. 计划必须人工审核后才生成。
3. 真实提交必须有段 ID / 后端 / max_submits 审批。
4. 已有远端任务优先恢复，不重复提交扣费。
5. 技术检查通过不能替代人物/商品/包装/动作/口型人工审核。
