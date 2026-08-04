# ACCEPTANCE · dy-fanpai

原能力 → 新能力逐项映射与验收方式（EXECUTION_PLAN §12.3 集成检查点、§13 最终验收门）。

状态图例：
- ✅ 离线/确定性已验：单元测试 +（媒体类）T3 合成媒体真跑，无网络、无付费 API。
- 🟡 实现完成，外部验收未完成：代码与 Mock 就绪，但需真实账号/预算/合法素材/特定机器才能跑受控 Live。
- ⬜ 尚未实现（属后续工作包）。

## WP3 音频与媒体

| 原脚本 / 能力 | 新模块 / 函数 | 离线单测 | T3 媒体集成 | Live/实机验收 | 状态 |
|---|---|---|---|---|---|
| `cut_audio.py` 原音切段 + 2 秒闸 + timing | `audio/service.py` `cut_original_audio` / `pad_for_upload` / `build_timing` | ✅ 8 例 | ✅ `test_cut_original_audio_real`（2 秒闸实测） | — | ✅ 离线全通过 |
| `tts_segments.py` 发音修正 `apply_pron_fix`（参→身 + CAN_WORDS 保护） | `audio/voice.py` `apply_pron_fix` | ✅ 多例 | — | 🟡 CosyVoice 环境未跑 | 🟡 离线逻辑已验，Live 未验 |
| `tts_segments.py` 多说话人 `parse_speakers` | `audio/voice.py` `parse_speakers` | ✅ | — | — | ✅ 离线已验 |
| `tts_segments.py` TTS 合成 `synth`（CosyVoice 子进程） | `audio/voice.py` `synth` / `cosyvoice_status` | 🟡 仅状态函数单测 | — | 🟡 需 CosyVoice 环境 | 🟡 实现完成，外部验收未完成 |
| `vc_segments.py` 换声 `convert`（Seed-VC） | `audio/voice.py` `convert` / `resolve_target` / `seedvc_status` | 🟡 状态+解析单测 | — | 🟡 需 Seed-VC GPU 环境 | 🟡 实现完成，外部验收未完成 |
| `assemble.py` 归一化 / 拼接 / 补静音 / 解码体检 | `media/ffmpeg.py` `assemble` / `normalize_args` / `pad_audio_args` / `silence_args` / `concat_args` / `mux_args` / `decode_ok` | ✅ 11 例（args 级） | ✅ `test_normalize_real` / `test_assemble_real` | — | ✅ 离线全通过（合成媒体真跑） |
| `gen_segments.py` 下载体检（大小 + 坏流） | `media/download.py` `robust_download` / `proxy_for_attempt` | ✅ 4 例 | — | 🟡 需真实 URL 受控 Live | 🟡 离线逻辑已验，Live 未验 |
| `export_subs.py` 字幕基础（`fmt_ts`/`sentences`/`export`） | `delivery/`（WP5 范围，本包未建模块） | ⬜ | ⬜ | ⬜ | ⬜ 属 WP5 |

## WP5 质检与交付

| 原脚本 / 能力 | 新模块 / 函数 | 离线单测 | T3 媒体集成 | Live/实机验收 | 状态 |
|---|---|---|---|---|---|
| `export_subs.py` `fmt_ts`/`sentences`/`export`（SRT + 贴字清单） | `delivery/final.py` `fmt_ts`/`sentences`/`build_srt_entries`/`render_srt`/`write_srt`/`export_srt`/`export_onscreen` | ✅ 10 例（时钟/权重/说话人剥离/贴字跳过「无」） | — | — | ✅ 离线全通过（1:1 复刻） |
| `export_subs.py` 烧字幕 filter + FINAL 母版 | `delivery/final.py` `subtitle_filter`/`burn_subtitles`/`build_final` | ✅ `subtitle_filter` 确定性单测 | 🟡 `test_build_final_copy`/`test_build_final_with_bgm_no_burn` 真跑；`test_burn_subtitles_requires_libass` 因缺 libass 跳过 | 🟡 真机烧字幕需带 libass 的 ffmpeg | 🟡 实现完成，烧字幕外部验收未完成（CLI 已兜底回退） |
| `export_subs.py` BGM 混音 | `delivery/final.py` `mux_bgm` | — | ✅ `test_mux_bgm_real`（真 ffmpeg 混音，原声时长保留） | — | ✅ 离线全通过（合成媒体真跑） |
| 剪映草稿（5 轨：视频/原声/字幕/贴纸/BGM） | `delivery/jianying.py` `build_draft_spec`/`write_draft`(engine="json") | ✅ 7 例（5 轨/最小 2 轨/JSON 有效/拒绝覆盖/force） | — | 🟡 pyJianYingDraft 真机写 + 剪映真实打开 | 🟡 实现完成，真机打开外部验收未完成 |
| 技术 QC：ffprobe 探活 + 解码体检 + 分辨率/时长 | `quality/qc.py` `probe`/`qc_video`/`mouth_evidence`/`qc_report` | ✅ 12 例（mock IO：分辨率/缺音频/probe失败/口型容差/聚合） | ✅ `test_qc_video_real_ok`（真 ffmpeg） | — | ✅ 离线+真跑全通过 |
| 双视频评委（结构版） | `quality/judge.py` `judge_pair`/`judge_summary` | ✅ 5 例（解码/分辨率/时长比 0.5~2.0） | — | 🟡 模型级语义评委（Ark 等） | 🟡 结构评委已验，语义评委外部验收 |
| 交付清理（dry-run + 受保护安全网） | `delivery/cleanup.py` `plan_cleanup` | ✅ 4 例（dry-run 只报/不删、真实只删临时、受保护存活） | — | — | ✅ 离线全通过 |
| CLI 交付/清理接线 | `cli.py` `deliver`/`clean`（WP1 冻结接口落地） | — | ✅ 真跑 deliver(final/jianying) + clean dry-run 烟测 | — | ✅ 接线可用；烧字幕/剪映真机为 🟡 |

**WP5 验收结论（§11）：** 技术状态（字幕/SRT/FINAL拷贝/混BGM/QC/结构评委/清理）离线 + T3 合成媒体全跑通 ✅；人工状态（烧字幕观感、剪映真机打开）属外部验收 🟡，CLI 已对 libass 缺失做无烧字幕 FINAL 兜底。全仓 152 passed / 1 skipped（skip = 本机缺 libass 烧字幕用例）、pyright 0。

**WP3 验收结论（§11）：** 合成媒体离线全通过 ✅（T3 真实 ffmpeg 跑通切段/归一化/装配/解码体检，ffmpeg 8.1.2 在场）。TTS/换声/下载的真机与 Live 项标记 🟡。

## WP4 视频生成

| 原脚本 / 能力 | 新模块 / 函数 | Mock 单测 | Live/实机验收 | 状态 |
|---|---|---|---|---|
| `gen_segments.py` 即梦/Dreamina 提交/轮询/下载 | `generation/dreamina.py` + `service.py` `route_backend` | ✅ 13+10 例（全部 Mock） | 🟡 需即梦账号/预算 | 🟡 实现完成，外部验收未完成 |
| `ark_gen.py` Ark i2v/mm/t2v | `generation/ark.py` `submit_i2v/mm/t2v` / `wait_download` | ✅ 4 例（请求体构造） | 🟡 需 Ark key + 预算 | 🟡 实现完成，外部验收未完成 |
| `xyq_gen.py` 小云雀 XYQ i2v/mm/t2v | `generation/xyq.py` `submit_i2v/mm/t2v` / `wait_download` | ✅ 9 例（含 AUDIO_GUARD） | 🟡 需 XYQ CLI 凭证 | 🟡 实现完成，外部验收未完成 |
| 生成编排：人/物路由、task 写盘/恢复/下载、重试/坏流重下、锁/提交意图/费用硬上限 | `generation/service.py` `run` | ✅ 10 例（DI `backends=` Mock） | — | ✅ Mock 全通过；Live 受 §11「未经审批不得 Live」约束 |

**WP4 验收结论（§11）：** 先完成全部 Mock ✅（`run()` 全程 Mock 注入，零真实 API）；未经审批不得 Live ✅（未设置任何 Live 提交，费用硬上限 `manifest.max_submits` 生效）。三后端真实提交/轮询/下载标记 🟡。

## WP6 集成与发布

| 原脚本 / 能力 | 新模块 / 函数 | 离线单测 | 集成/烟测 | Live/实机验收 | 状态 |
|---|---|---|---|---|---|
| 全流程编排（分阶段 + 闸口拦截） | `pipeline.py` `run_flow` / `execute_stage` / `STAGE_GATE` / `required_gate` | ✅（gate 单测见下） | ✅ `test_pipeline_e2e.py`（`new`/`run --stage plan`/`run deliver` 离线跑通） | — | ✅ 离线全通过 |
| CLI `run`/`approve`/`retry`/`deliver` 接线（原 `_not_implemented` 落地） | `cli.py` `_run`/`_approve`/`_retry`/`_deliver` | ✅ 7 例（gate 5 拦截 + 解锁 + 全链路） | ✅ 真跑 `run deliver` 离线产 FINAL/SRT/draft | — | ✅ 接线可用；闸口约束见验收门 5 |
| 四闸口不可被 `run`/`--force` 绕过（验收门 5） | `workflow.py` `require_gate` / `GateBlocked` | ✅ 7 例（`test_gate_enforcement.py`：未审批抛 `GateBlocked`、`--force` 触发 `SystemExit`） | — | — | ✅ 已验，入口不存在 `--force` |
| 并发/崩溃无静默重复提交（验收门 6） | `workspace.acquire_lock` / `generation/service.run` `within_cap` + 提交意图 | ✅ 3 例（`test_no_duplicate_submit.py`：`acquire_lock` 互斥/`within_cap` 硬上限/`ThreadPoolExecutor(2)` 并发无重复） | — | 🟡 真机崩溃恢复待 Live 复核 | ✅ 实现+单测已验 |
| 完整 Skill 文档 | `SKILL.md`（8 命令 + 四闸口纪律 + 降级说明） | — | ✅ 内容审阅完整 | — | ✅ 完整 |
| 干净环境安装（验收门 2） | `pyproject.toml`（hatchling wheel/sdist）+ CLI | — | ✅ 全新 Py3.13.12 venv `pip install` 成功，`--help`/`doctor`/`status` 可用 | — | ✅ 已验 |

**WP6 验收结论（§11）：** 完整 CLI + Skill ✅（8 命令全部接线，Skill 文档完整）；五类测试 ✅（gate 5 / gate 6 / e2e / 既有单测 / 集成）；干净环境安装 ✅（验收门 2，全新 venv 安装 + CLI/Skill 可用）；三绿维持（ruff 全绿 / pytest 166 passed, 1 skipped / pyright 0）。受控 Live Pilot、剪映真机打开、六类场景 fixture、全新会话自然语言暂停、人工审核、费用/任务 ID 可追溯、原项目未修改复核标记 🟡。

## 跨工作包通用验收项（§13）

| # | 验收门 | 本包状态 |
|---|---|---|
| 1 | 原项目工作区未修改 | ✅ 已复核：`daihuo-fanpai` HEAD=`ffc22e34` 零受跟踪改动（清理了工具链遗留 `.workbuddy`） |
| 2 | 干净环境安装（wheel/sdist + CLI/Skill 可用） | ✅ 全新 Py3.13.12 venv `pip install` 成功，`dy-fanpai --help`/`doctor`/`status`/`SKILL.md` 均可用 |
| 3 | 六类场景 fixture + 验收记录 | ✅ fixture 已搭（`tests/fixtures/scenarios/` 6 类均有 `shotlist.json`+`assets.json`+`segments.golden.json` 合成输入）；验收记录待受控 Live 回填（🟡） |
| 4 | 确定性产物与原项目无未解释差异 | ✅ WP2 planner golden 逐字节；WP3 装配 args/timing、WP4 三后端命令/请求体/解析均有统一 golden 逐字段断言（`tests/parity/fixtures/`，38 例新增）；六类场景 segments golden 已纳入基线（见 `PARITY.md`） |
| 5 | 四闸口不可被 `run`/`--force` 绕过 | ✅ `test_gate_enforcement.py` 7 例：未审批 `GateBlocked`、`--force` 入口不存在（`SystemExit`） |
| 6 | 并发/崩溃无静默重复提交 | ✅ `test_no_duplicate_submit.py` 3 例：排他锁 + 费用硬上限 + 提交意图；真机崩溃恢复待 Live 复核 |
| 7 | 反推/三视频后端/音频 按声明完成 Mock + Live | 🟡 Mock 全完成；Live 待账号+预算（降级见 `DEGRADATION.md`，未虚报） |
| 8 | FULL 母版/字幕成品/剪映草稿 技术检查 | ✅ qc/judge/delivery 技术检查全过；剪映真机打开 🟡 |
| 9 | 人物/商品/包装/动作/口型/合规 人工审核 | 🟡 人工审核项，清单见各场景 `acceptance_record.md` |
| 10 | 费用/任务 ID/模型·CLI·ffmpeg 版本/远端上传 追溯 | 🟡 `run.json` 账本 + task 字段已实现，全链路真跑后验收 |
| 11 | 缺失时明确降级，未虚报完整 | ✅ `DEGRADATION.md` 15 项降级矩阵，全部标 🟡 不虚报 |
| 12 | `ACCEPTANCE.md` 无无说明空白功能项 | ✅ 逐项说明，🟡/⬜ 均标注 |

## 未验 Live / 实机项汇总（§12.3 记录）

- 即梦/Dreamina、Ark、小云雀：真实提交/轮询/下载未跑受控 Live（需账号+预算）。
- CosyVoice（TTS）、Seed-VC（换声）：需合法环境与音色，未跑受控 Live。
- 烧字幕（ffmpeg subtitles filter / libass）：本机 macOS ffmpeg 8.1.2 缺 libass，FINAL 已兜底回退无烧字幕 + SRT 侧载；真机烧字幕需带 libass 的 ffmpeg。
- 剪映草稿真机写入（pyJianYingDraft）+ 剪映真实打开一次：需 Windows/WSL 机器 + 已装包 + 对应剪映版本/草稿目录，本包仅产出可照抄 JSON 规格。
- 双视频模型级语义评委（Ark 等）：本包只交付确定性结构评委，语义比对属后续外部验收。
- 四闸口绕过防护：✅ WP6 已集成验证（`test_gate_enforcement.py` 覆盖未审批 `GateBlocked` 与 `--force` 入口不存在；`workflow.require_gate` 在 `pipeline.execute_stage` 每阶段强制调用）。
- 原项目未修改（验收门 1）：✅ 已复核 `daihuo-fanpai` HEAD=`ffc22e34` 零受跟踪改动（清理了工具链遗留的 `.workbuddy/` 自动生成目录）。
- 六类场景 fixture（验收门 3）：✅ fixture 已搭（`tests/fixtures/scenarios/` 6 类目录 + `acceptance_record.md` 模板）；验收记录待受控 Live 回填。
- 确定性 parity（验收门 4）：✅ WP2 planner golden 逐字节；WP3/WP4 统一 golden（`tests/parity/fixtures/`）逐字段断言 + 六类场景 segments golden 已纳入基线（见 `PARITY.md`）。
- 受控 Live Pilot（即梦/Ark/小云雀真实提交，验收门 7）：待账号+预算受控 Live，仍受 §11「未经审批不得 Live」约束。
- 剪映草稿真机打开一次（验收门 8 部分）：pyJianYingDraft 真机写 + 剪映真实打开（Windows/WSL + 已装包）属外部验收。
- 人物/商品/包装/动作/口型/合规人工审核（验收门 9）：属人工审核项，清单见各场景 `acceptance_record.md`。
- 费用/任务 ID/版本追溯（验收门 10）：run.json 已含账本与 task 字段，全链路串联真跑后验收。
- 降级与「未虚报完整」（验收门 11）：✅ `DEGRADATION.md` 15 项降级矩阵，所有外部缺口显式降级且标 🟡，未虚称已通过。
- 四闸口在全新会话自然语言触发暂停（详细参考验证项，非 §13 门）：需端到端自然语言会话验证，未跑；CLI/`run` 路径强制拦截已实现并单测。
