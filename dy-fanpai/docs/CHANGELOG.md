# CHANGELOG · dy-fanpai

本文件记录公共接口冻结与变更（执行方案 §11 WP1 / §12.2）。

## [0.1.0] — 2026-08-06 · Ubuntu + NVIDIA 环境适配（ComfyUI 启动）

### 新增
- `scripts/run_comfyui_nvidia.sh`：**NVIDIA/CUDA 专属启动脚本**（原 run_comfyui.sh
  是 AMD/双平台通用版，参数非 NVIDIA 最优）。差异：
  - `--fp16-vae` 默认开启（NVIDIA 上更快更稳；AMD 粉红问题不存在）
  - `--enable-cuda-malloc` 默认开启（显存复用优化）
  - `--highvram` 自动决策：显存 >= 32GB 自动开（跑 14B 视频模型），消费卡默认关
  - 注意力后端：flash-attn > xformers > sdpa 自动探测
  - 启动前置校验：CUDA torch + nvidia-smi 缺失即明确报错；崩溃排查注释为 NVIDIA 语境
  - **Python 环境三级选择**（2026-08-06 调整，系统优先）：
    ① 系统 python3 有 torch+CUDA+comfy → 直接用系统 python（DSW/预装零安装）；
    ② 系统不满足 → 切 venv（env/.venv），venv 满足则 venv 运行；
    ③ 均不满足 → 自动在 venv 安装 CUDA torch + requirements + flash-attn 后运行；
    `COMFY_NO_INSTALL=1` 可禁止自动安装，`COMFY_CUDA_VERSION` 指定 CUDA 轮子（默认 cu128）
- `scripts/test_comfyui_scripts.sh`：新增 5.8 节（nvidia 脚本帮助/参数断言），
  语法检查清单加入 run_comfyui_nvidia.sh。

### 变更
- `scripts/run_comfyui.sh`：`COMFY_FP16_VAE` 默认值**按 GPU 类型区分**——
  NVIDIA 默认 1（fp16 开），AMD 默认 0（防粉红输出）。此前 AMD 的默认 0 误作用于
  NVIDIA 分支（08-04 粉红修复的副作用，本次修正）。
- `scripts/install_comfyui_cuda.sh`：默认 CUDA 轮子 **cu126 → cu128**（2026 新 torch 主流）。
- `scripts/test_comfyui_scripts.sh`：修正 2 条过时断言——NVIDIA 有 xformers 时
  新版 ComfyUI 自动启用不留 `--xformers` 参数（期望改为无 xformers 参数 + fp16-vae）；
  未知环境保守参数不带 fp16-vae。

### 说明
- 模型侧：Wan2.2 下载脚本强制 umt5 fp16 是 AMD ROCm 兼容决策，NVIDIA 上可换
  fp8 版本更省显存（脚本注释已注明）；MiniMax H3 int8 pruned 权重两平台通用。
- 回归测试 54/54 通过。

## [0.1.0] — 2026-08-06 · 复盘优化：锁回收 / assemble CLI / 轮询脚本 / set-url

### 新增
- `cli.py`：新增 `set-url` 命令（写 `~/.config/dy-fanpai/<key>_base_url`），
  配合 `scripts/tunnel_comfyui.sh` 一键更新隧道域名，替代手写 printf。
- `scripts/poll_comfyui_tasks.py`：正式版 ComfyUI 任务轮询下载工具
  （读 clips/*.meta.json → 按间隔查 /history → 出片自动下载；断点续传；
  双 id 兜底查队列实际执行 id；正确遍历 outputs.images 列表）。
- `pipeline.py`：ASSEMBLE 阶段由"跳过"改为真实执行（新增 `_exec_assemble`
  调 media.ffmpeg.assemble → output/FULL.mp4），`run --stage assemble` 可用。
- `tests/unit/test_generation_service.py`：锁回收 4 个新用例。

### 变更
- `generation/service.py` `acquire_lock`：增加**陈旧锁回收**——锁文件持有者
  PID 已死（kill -9/沙盒超时残留）时自动回收加锁，不再永久"被占用"需手工删；
  损坏/空锁文件同样视为陈旧。活锁仍拒绝（并发保护）。
- `scripts/tunnel_comfyui.sh`：输出改用 `dy-fanpai set-url comfyui <url>` 提示。

### 说明
- 46s vs 41.4s 成片时差为**设计行为**（planner 把短段归并为整数秒段，
  duration 字段即归并后时长），非 bug，未改。
- jianying-editor 技能侧：新增 `scripts/utils/__init__.py` 根治 users.pth
  硬编码 GPT-SoVITS 路径劫持 namespace utils 包的问题（技能仓库外部修改）。

## [0.1.0] — 2026-08-05 · 全 H3 路线工程债修复（Live 实测暴露）

### 新增
- `cli.py`：`approve` 增加 `--live`（批准时开启 run.live）与 `--max-submits N`
  （设置提交硬上限），不再需要手工改 run.json。
- `cli.py`：`run` / `retry` 增加 `--i2v-backend`（选择 i2v/无主播 mm 段生成后端），
  README 已声明但 CLI 此前未接线。
- `pipeline.py`：`execute_stage` 的 GENERATE 分支由"跳过"改为真实执行
  （新增 `_exec_generate` 调 generation.service.run）；`run_flow` 透传 `i2v_backend`。
- `scripts/tunnel_comfyui.sh`：MI308X 侧一键建 trycloudflare 隧道 + 打印 Mac 侧
  更新命令（解决隧道域名漂移）。
- `docs/ANCHOR_ASSET_STANDARD.md`：产品锚图素材规范（禁止带营销文字的宣传图
  作 H3/即梦锚图；1501# 仅 `sku/*（合并）.png` 可用）。
- `tests/unit/test_voicebox_client.py`：find_profile_id 5 个确定性用例。

### 变更
- `generation/service.py` `route_backend`：**放宽 mm 段硬规则**——无真人出镜
  （shots 全 `host_on_camera=False`）的 mm 段允许走 alt 后端（如 comfyui_h3），
  有主播出镜仍必须走即梦（口型驱动）。`service.run` 提交前把 segments 相对
  anchor 路径基于 planning/ 解析为绝对路径（此前 FileNotFoundError）。
- `audio/voicebox_client.py` `find_profile_id`：未配置 `voicebox_profile_id` 时
  回退按 `voicebox_profile_name` 查找已有 profile（此前每段重复 create_profile
  → S2 起 HTTP 400）。
- `media/ffmpeg.py` `normalize_args`：新增 `seg_dur` 参数，assemble 按段目标
  时长 `-t` 裁剪 clip（兼容 H3 帧数网格导致 4s 段出 5s clip 的时长错位）。
- `models.py`：`ProviderName` 补 `minimax` / `comfyui` / `comfyui_h3` /
  `comfyui_h3_t2v` / `comfyui_h3_r2v` 枚举成员。

### 说明
- 无主播 mm 段走 H3 时用 `submit_h3_i2v`（纯视觉，seg["anchor"] 驱动），
  配音在 assemble 阶段混流——符合无主播画外音形态，无需 LatentSync。

## [0.1.0] — 2026-08-05 · ComfyUI 直连 H3 三能力(T2V/I2V/R2V)

### 新增
- `comfyui.py`：`submit()` 支持**扁平模板**（顶层即 `{node_id: {class_type, inputs}}`，
  graph nodes/links 自动识别转换）；新增 `submit_h3_t2v` / `submit_h3_r2v`；
  占位符 `__ASPECT__`（H3 ResolutionSelector 8 档比例）+ `__SEED__`（随机种子）；
  `aspect_ratio_for` / `prune_r2v_single`（单参考图裁剪）。
- `service.py`：后端注册 `comfyui_h3_t2v` / `comfyui_h3_r2v`。
- `config.py`：`comfyui_workflow_h3_t2v` / `comfyui_workflow_h3_r2v`
  （`COMFYUI_WORKFLOW_H3_T2V` / `COMFYUI_WORKFLOW_H3_R2V`）。
- `resources/workflows/`：`comfyui_h3_t2v.json`（17 节点）/ `comfyui_h3_r2v.json`
  （19 节点）扁平模板，从 `scripts/h3_video_*.js` 抽取；README 补模板清单与占位符表。

### 说明
- 三能力（文生/图生/参考生视频）现在 CLI 直连 ComfyUI 可用，无需无限画布。
- r2v 单参考图自动裁剪；双参考图保留两个 LoadImage。

## [0.1.0] — 2026-08-05 · 环境变量命名统一(COMFYUI_*)

### 变更
- ComfyUI 相关环境变量由混合大小写 `COMfyUI_*` 统一为全大写 `COMFYUI_*`：
  `COMFYUI_BASE_URL` / `COMFYUI_WORKFLOW_I2V` / `COMFYUI_WORKFLOW_H3_I2V` /
  `COMFYUI_WORKFLOW_MM`（config.py 读取键、doctor 展示键同步更新）。
- 旧名 `COMfyUI_*` 不再识别；已配置旧名的用户环境需同步改名（项目内无历史配置残留）。

## [0.1.0] — 2026-08-03 · WP1 冻结

WP1（骨架与核心）完成，以下公共接口冻结，后续修改须走变更流程：

### 新增
- 包结构 `src/dy_fanpai/`（顶层 models/config/workspace/workflow/cli + 子包 reverse/planning/audio/generation/media/quality/delivery）。
- `pyproject.toml`：Python ≥3.12，core=pydantic≥2+requests，dev=pytest/responses/ruff/pyright，CLI=argparse，jianying 可选独立环境。
- `models.py` 冻结：7 阶段 `Stage`、11 状态 `RunStatus`、4 闸口 `Gate`、Provider 枚举、`RunManifest` v1、`GenerationTask`、Segment/Shot。
- `config.py` 冻结：env→`~/.config/dy-fanpai/`→默认 三级读取；全部密钥/二进制路径集中（含新增 `DY_FANPAI_DREAMINA_BIN`/`DY_FANPAI_TTS_DRAMA`/`DY_FANPAI_ARK_GEN_MODEL`）。
- `workspace.py` 冻结：工作区布局、run.json 读写、fcntl 排他锁、产物登记。
- `workflow.py` 冻结：状态机、四闸口（GateBlocked）、`max_submits` 硬上限、费用账本。
- `cli.py` 骨架：8 命令组（doctor/new/status/run/approve/retry/deliver/clean），new/status/doctor 可用，其余接口冻结、业务待 WP2–WP5。
- `DESIGN.md`：权威声明 + 全部冻结项 + WP0 §9 十个冲突点裁决。
- `LICENSE`：MIT，保留 wangcanyu 并叠加 momo0338。

### 裁决（详见 DESIGN.md §12）
- 2 秒闸：`pad = max(2.0, 实际音频时长)`，不垫到计划段时长。
- 时长：统一 `SEGMENT_MAX_DURATION=15` / `SEGMENT_TARGET_DURATION=12`。
- `detect_cuts` 默认阈值冻结为 0.15。
- Ark 生成模型收归 `DY_FANPAI_ARK_GEN_MODEL`。
- 内置音色不随仓库分发；路径转换仅 Windows/WSL 草稿模式触发。
- config 双重标准消除；多处无重试统一补重试/降级。

## [0.1.0] — 2026-08-03 · WP2 反推与规划

WP2（业务包第 1 个）完成：忠实复刻原 `daihuo-fanpai` 的反推与规划算法，确定性逻辑
与网络调用解耦，离线可单测。

### 新增
- `reverse/seed.py`：反推腿 1（Ark Seed 2.1 Pro）。`detect_cuts`(默认 0.15) / `video_info`
  / `make_upload_clip` / `build_prompt` / `ark_reverse` / `extract_json` / `reverse`；
  国内 Ark endpoint 强制 `NO_PROXY`、thinking 关、流式。
- `reverse/kimi.py`：反推腿 2（Kimi K3）。同 ffmpeg 硬切 + 第 8 条实体纪律；连接抖动重试 3 次。
- `reverse/merge.py`：双反推合并证据准备。`build_merged`（纯函数,离线可测）产出
  Seed 实体基底 + `__alt_*` 候选运镜时序；含静音闸 / 性别信号 / 分歧信号灯 / 抽帧点。
- `planning/planner.py`：规划器。`split_long_shots`(≤15) / `group_shots`(≤12, ≤3 切) /
  `seg_role` / `merged_form_map` / `pick_product_anchors` / `build_*_prompt` /
  `completeness_check` / `plan` → segments.json + .md。逐字节复刻原算法（golden 校验）。
- `planning/localization.py`：B 模式本地化。`apply_edits_dict`（离线,同步口播段 `台词{...}`）
  / `rewrite`（喂千川弹药包,需 Ark key）。
- 测试：`tests/fixtures/original/`（sample_shotlist+sample_assets + 当前算法 golden）；
  `tests/parity/test_planner_parity.py`（planner 精确 parity + 结构化断言，9 例）；
  `tests/unit/test_merge.py` / `test_seed.py` / `test_localization.py`（离线单测，共 18 例）。

### 校验
- planner 对 golden **逐字节相等**；reverse.merge 静音闸/性别信号/抽帧离线断言通过。
- ruff 全绿、pytest 35 例全绿、pyright 0 错误。
- `config.py`：`_read` 返回类型收为 `str`（消除 `str|None` 赋值告警）；`pyproject.toml`
  为 prompt/SCHEMA 长字符串文件豁免 E501、为 pyright 配置 venv。

### 注意（parity 实测发现,非新冻结）
- planner 输出每段 `shots` 为镜引用列表（字符串/整数混合,如 `['1a']`/`['1b',2]`）,非 dict。
- i2v 段不含 `images`/`anchor_labels` 键；mm 段含且锚标数 ≤ 图数。
- 段 `duration` 是目标生成时长,不要求等于 `end-start`（实际镜跨度）。

## [0.1.0] — 2026-08-03 · WP3 音频与媒体

WP3（业务包第 2 个，与 WP4 并行）完成：忠实复刻原 `daihuo-fanpai` 的音频切段、TTS/换声适配器、ffmpeg 装配与下载体检，确定性逻辑与 ffmpeg/网络 IO 解耦，离线单测 + T3 合成媒体真跑。

### 新增
- `audio/service.py`：原音切段主入口 `cut_original_audio`；复刻 `cut_audio.py`。`pad_for_upload`（2 秒闸 `max(2.0,span)`，只垫到上传下限）、`segment_cut_args`（`-ss/-to` + `-vn -ac 1 -ar 24000 -af apad=whole_dur`）、`shot_in_segment`、`build_timing`（镜级字幕轴，相对段起点偏移）。
- `audio/voice.py`：复刻 `tts_segments.py` + `vc_segments.py`。`apply_pron_fix`（参→身 + CAN_WORDS 17 词控制符保护/还原，可关 haishen）、`parse_speakers`（A：/B：/甲： 标签切分）、`resolve_target`（wav/内置名/默认，缺失抛 ValueError）、`seedvc_status`、`cosyvoice_status`；重 IO `synth`（CosyVoice + tts-drama 子进程）、`convert`（Seed-VC GPU 子进程）。
- `media/ffmpeg.py`：复刻 `assemble.py`。`dur`（ffprobe）、`normalize_args`（720x1280 + setsar + yuv420p + libx264 crf20）、`pad_audio_args`/`silence_args`（段配音 pad 到视频时长 / 无配音填静音）、`concat_args`/`mux_args`、`decode_ok`（只认 `Invalid NAL`/`Invalid data` 坏流标记）、`assemble`（归一化→pad→concat→mux）。
- `media/download.py`：复刻 `gen_segments.py` 下载体检。`MIN_BYTES=10240`；`proxy_for_attempt`（显式代理常走 / 前两试直连 / 之后回退 None）、`robust_download`（重试 + 大小校验 + 可选解码体检复用 `decode_ok`）。
- 测试：`tests/unit/test_audio_service.py`（8）、`test_voice.py`（16）、`test_ffmpeg.py`（11）、`test_download.py`（4）；`tests/integration/test_media_t3.py`（4）：合成小视频真跑 `dur`/`decode_ok`/`normalize_args`/`assemble`/`cut_original_audio`，含 2 秒闸与静音段分支。
- `__init__.py`：`audio`/`media` 导出新子模块；`pyproject.toml` 为 8 个新文件豁免 E501。

### 校验
- WP3 验收（§11「合成媒体离线全通过」）：T3 用合成小视频真实调用 ffmpeg/ffprobe（无网络、无付费 API）跑通切段/归一化/装配/解码体检；2 秒闸实测生效（1.0s 跨度→2.0s 产物）；静音段不崩溃。
- ruff 全绿、pytest 全仓 **113 例**全绿、pyright 0 错误。

### 注意（复刻铁律，非新冻结）
- 段配音 pad 到【视频时长】对齐口型，绝不垫到规划段时长（与 WP1 2 秒闸裁决一致，只作用于上传下限）。
- 解码体检只认坏流标记，大小正常但字节流损坏（07-25 大鹅4 S2 实翻车）仍判坏。

## [0.1.0] — 2026-08-03 · WP4 视频生成

WP4（业务包第 3 个，与 WP3 并行）完成：忠实复刻原 `daihuo-fanpai` 的即梦/Dreamina、Ark、小云雀三后端提交/轮询/下载编排，确定性请求构造与网络 IO 解耦，全部 Mock 先行、未经审批不 Live。

### 新增
- `generation/dreamina.py`：复刻 `gen_segments.py`。`wav_dur`、`fitted_duration`（wav 长则抬段时长，cap 15s，tol 0.25）、`fit_duration_to_audio`、`build_submit_cmd`（mm 走 `multimodal2video` 带图+音频，i2v 走 `image2video`）、`parse_submit_out`（11 段 UUID 解析）、`is_fatal`、`submit`（重试 3× 退避）、`parse_query_out`、`wait_download`（轮询 40× gap15）。`MULTIMODAL_MODEL="seedance2.0_vip"`、`RATIO="9:16"`、`RESOLUTION="720p"`。
- `generation/ark.py`：复刻 `ark_gen.py`。`submit_i2v/mm/t2v`（data-uri 内联图/音频，role `reference_image`/`reference_audio`），`wait_download`；国内 endpoint 强制 `NO_PROXY`，`# pyright: ignore[reportArgumentType]`；`Model doubao-seedance-2-0-260128`。
- `generation/xyq.py`：复刻 `xyq_gen.py`。`AUDIO_GUARD="无人声,无背景音乐。"`（i2v 默认带 guard），`submit_i2v/mm/t2v` 经 `pippit-tool-cli generate-video`，`wait_download`（60× gap10）；tid=`thread_id/run_id`。
- `generation/service.py`：生成编排。 `route_backend`（mm→即梦恒，i2v→alt 或即梦）、`submits_so_far`、`within_cap`（用 `manifest.max_submits` 硬上限）、`load_task`/`save_task`、`acquire_lock`/`release_lock`（最佳努力排他）、`run`（DI 友好：`backends=` 注入 Mock；支持 `only`/`dry`/断点续跑/从 task 恢复/单段失败隔离/`cap_hit` 早停/锁冲突）。
- 测试：`tests/unit/test_dreamina.py`（13）、`test_ark.py`（4）、`test_xyq.py`（9）、`test_generation_service.py`（10）：覆盖 2 秒闸无关的请求构造、UUID 解析、i2v 后端路由、成本硬上限、检查点续跑、task 恢复、单段失败隔离——全部 Mock，无付费调用。
- `__init__.py`：`generation` 导出 ark/dreamina/service/xyq。

### 校验
- WP4 验收（§11「先完成全部 Mock；未经审批不得 Live」）：`generation/service.py.run()` 全程 `backends=` Mock 注入，10 例编排测试零真实 API；成本硬上限 `manifest.max_submits` 生效；未设置任何 Live 提交。
- ruff 全绿、pytest 全仓 113 例全绿、pyright 0 错误。

### 未验的 Live / 实机项（标记「实现完成，外部验收未完成」）
- 即梦/Dreamina、Ark、小云雀的真实提交/轮询/下载需对应账号与预算，未跑受控 Live。
- CosyVoice（TTS）、Seed-VC（换声）需合法环境与音色，未跑受控 Live；`synth`/`convert` 仅离线接口与状态函数单测。
- 剪映草稿（WP5/质量交付）本包未涉及。

## [0.1.0] — 2026-08-03 · WP5 质检与交付

WP5（业务包第 4 个、收尾交付）完成：忠实复刻原 `export_subs.py` 字幕基础并补齐 FULL→FINAL
母版、剪映草稿、技术 QC、双视频结构评委、dry-run 清理。确定性逻辑与 ffmpeg/ffprobe IO 解耦；
字幕/SRT/评委/FINAL拷贝 离线可单测，质检/混BGM/FINAL 由 T3 合成媒体真跑。

### 新增
- `delivery/final.py`：复刻 `export_subs.py` 1:1（字幕铁律：FULL 永不带字幕/BGM，FINAL 才叠加）。
  `fmt_ts`（HH:MM:SS,mmm 逐字节一致）/ `sentences`（剥 A：/B： 说话人标签）/ `build_srt_entries`
  （段内按字数占比摊句、段间时钟归零累加）/ `render_srt`/`write_srt`/`export_srt`/`export_onscreen`
  （屏上贴字清单 .md，跳过「无」/「none」）/ `subtitle_filter`（确定性 force_style，路径 `:` 转义 `\:`）/
  `burn_subtitles`（ffmpeg subtitles filter，需 libass）/ `mux_bgm`（BGM 压低混原声）/ `build_final`
  （FULL 只读 → FINAL，无 srt/bgm 直接拷贝，铁律不修改 FULL）。
- `delivery/jianying.py`：5 轨剪映草稿规格（视频+原声+字幕+贴纸+BGM）+ 离线 JSON 引擎。
  `_ts_to_sec`/`parse_srt`/`build_draft_spec`/`draft_json`/`write_draft`（engine="json" 默认拒绝覆盖、
  需 force；engine="pyjianying" 抛 RuntimeError 标明外部验收）。
- `delivery/cleanup.py`：dry-run 清理 + 受保护安全网。`PROTECTED_PREFIXES`/`PROTECTED_NAMES`
  （run.json/FULL.mp4/FINAL.mp4）/`PROTECTED_ROOT_SUFFIXES`/`TEMP_*`；`plan_cleanup(run_dir, dry_run=True)`
  默认只报告候选、不删；`dry_run=False` 仅删临时，受保护项永不动。
- `quality/qc.py`：技术 QC。`probe`（ffprobe 流/分辨率/时长）/ `qc_video`（流/分辨率/解码/
  时长体检，聚合 ok+issues）/ `mouth_evidence`（生成段时长覆盖配音时长，容差 0.05）/
  `qc_report`（多文件聚合）。
- `quality/judge.py`：双视频结构评委（确定性）。`judge_pair`（双方解码 + 分辨率命中 + 时长比
  0.5~2.0 = structural_pass；模型级语义评委不在此实现，属外部验收）/ `judge_summary`。
- `cli.py`：`deliver`/`clean` 接线（WP1 冻结接口落地）。`deliver [--mode final|jianying|both]
  [--bgm <path>]`：从 `planning/segments.json` 造 SRT，FINAL 烧字幕失败（libass 缺失）时
  try/except 回退无烧字幕 FINAL 并登记产物；`clean [--yes]`：默认 dry-run 报告。
- 测试：`tests/unit/test_delivery_final.py`（10）/ `test_delivery_jianying.py`（7）/
  `test_delivery_cleanup.py`（4）/ `test_quality.py`（12：qc 7 + judge 5）/ `tests/integration/
  test_delivery_t3.py`（5：真 ffmpeg 跑 qc_video/mux_bgm/build_final 拷贝/非烧字幕；burn_subtitles
  因本机无 libass 自动 skip）。
- `__init__.py`：`delivery` 导出 `cleanup`/`final`/`jianying`；`quality` 导出 `judge`/`qc`；
  `pyproject.toml` 为 5 个新文件豁免 E501。

### 校验
- WP5 验收（§11「技术状态与人工状态分离；剪映真实打开一次」）：
  - 技术状态（qc/judge/字幕/SRT/FINAL拷贝/混BGM）离线 + T3 合成媒体全跑通；
  - 人工状态（烧字幕观感、剪映真机打开）属外部验收，CLI 已做 libass 缺失兜底（回退无烧字幕 FINAL）。
- ruff 全绿、pytest 全仓 **152 passed, 1 skipped**（skip = 本机缺 libass 的烧字幕用例）、
  pyright 0 错误。

### 未验的 Live / 实机项（标记「实现完成，外部验收未完成」）
- 烧字幕（ffmpeg subtitles filter）：本机 macOS ffmpeg 8.1.2 构建缺 libass，FINAL 回退「无烧字幕
  + SRT 侧载」；真机烧字幕需带 libass 的 ffmpeg。
- 剪映草稿真机写入（pyJianYingDraft）：需 Windows/WSL + 已装包 + 剪映版本/草稿目录；本包仅产出
  可被照抄的 JSON 规格（engine="json"），真机打开验证为外部验收。
- 双视频模型级语义评委（Ark 等）：本包只交付确定性结构评委（解码/分辨率/时长比），语义比对属外部验收。

## [0.1.0] — 2026-08-03 · WP6 集成与发布

WP6（收尾集成与发布）完成：把 WP1–WP5 的全部业务包通过 `pipeline.py` 串成可被 CLI 驱动
的单次运行/分阶段执行流，四闸口在 run 路径上强制执行且不可被 `--force` 绕过，无重复提交
由排他锁 + 费用硬上限 + 提交意图保证；`../SKILL.md` 已是完整技能说明；干净环境安装（验收门 2）
已验证。这是唯一可宣布「替代原项目」的工作包。

### 新增
- `src/dy_fanpai/pipeline.py`：`STAGE_GATE` 映射（reverse/plan→RIGHTS、audio→PLAN、
  generate/assemble→COST、deliver→QC、prepare→无闸）+ `_STAGE_ORDER` + `required_gate` +
  `_skip_offline` + `_exec_plan` / `_exec_deliver` + `execute_stage`（先 `workflow.require_gate`
  再离线安全执行，完成标记 `mark_stage_done` 并 `ws.save`）+ `run_flow`（按当前阶段→目标阶段
  顺序推进）。确定性执行顺序与 IO 解耦，DI 友好（`backends=` 注入 Mock）。
- `cli.py` 重写 `run`/`approve`/`retry`/`deliver`：`_approve` 调 `workflow.approve_gate`；
  `_run` 调 `pipeline.execute_stage` 或 `run_flow`，捕获 `workflow.GateBlocked` → 返回 1；
  `_retry` 非 live 直接离线提示返回 0，live 则 `require_gate(COST)` 后 `G.run(lock_path=...)`；
  `_deliver` 委托 `pipeline.execute_stage(DELIVER, ...)`。三命令不再 `_not_implemented`，
  且无 `--force` 绕过闸口的入口（argparse 不提供该 flag，硬解析失败即 `SystemExit`）。
- `../SKILL.md`：完整技能说明（8 条命令 + 四闸口纪律 + 「不得用 --force 绕过」+ 外部资源降级
  说明），满足 WP6「完整 Skill」要求。
- 测试（WP6 新增 14 例）：
  - `tests/unit/test_gate_enforcement.py`（7，验收门 5）：`require_gate` 未审批抛 `GateBlocked`、
    `approve` 记录并解锁、`approve` CLI 记录、`run deliver` 无 QC→rc1 不产 FINAL、`run deliver`
    有 QC→rc0 产 FINAL/SRT/draft 并登记产物、全链路无 RIGHTS→rc1、`--force` 触发 `SystemExit`。
  - `tests/unit/test_no_duplicate_submit.py`（3，验收门 6）：`acquire_lock` 互斥、`within_cap`
    硬上限、`ThreadPoolExecutor(2)` 并发跑 `G.run` 无静默重复提交（thread2 返回 `locked`，
    thread1 仅交 2 个唯一 tid）。
  - `tests/integration/test_pipeline_e2e.py`（4）：`new` 建工作区、`run --stage plan` 离线产
    segments.json、`run deliver` 离线+QC 产 FINAL、`run deliver` 无 QC 被拦。

### 校验
- WP6 验收（§11「完整 CLI + Skill」「五类测试」「干净环境安装」）：
  - 四闸口在 run 路径强制执行：**不可绕过**（验收门 5，test_gate_enforcement 覆盖；`--force`
    入口不存在）。
  - 并发/崩溃无静默重复提交（验收门 6，test_no_duplicate_submit 覆盖：排他锁 + 费用硬上限 +
    提交意图）。
  - 干净环境安装（验收门 2）：在全新 Python 3.13.12 venv（`/tmp/wp6clean`）从源码 `pip install`
    成功，`dy-fanpai --help` / `doctor` / `status` 均可用（doctor 对缺失 ARK_API_KEY 等给 WARN，
    rc=0）。
- ruff 全绿、pytest 全仓 **166 passed, 1 skipped**（skip = 本机缺 libass 的烧字幕用例；
  WP5 152 → WP6 166 = +14 例）、pyright 0 错误。
- `pyproject.toml`：为 `src/dy_fanpai/pipeline.py` 与 3 个新测试文件豁免 E501。

### 未验的 Live / 实机项（标记「实现完成，外部验收未完成」）
- 受控 Live Pilot：真实 API 提交（即梦/Ark/小云雀）需账号与预算，未跑受控 Live（仍受
  §11「未经审批不得 Live」约束）。
- 剪映草稿真机打开一次：pyJianYingDraft 真机写 + 剪映真实打开（Windows/WSL + 已装包）属外部验收。
- 六类场景 fixture / 验收记录（验收门 3）：需补 6 类输入 fixture 与对应验收记录。
- 四闸口在全新会话自然语言触发暂停（验收门 4）：需端到端自然语言会话验证，未跑。
- 人物/商品/口型/合规人工审核（验收门 9）：属人工审核项。
- 费用/任务 ID/版本可追溯（验收门 10）：run.json 已含账本与 task 字段，全链路串联真跑后验收。
- 原项目未修改确认（验收门 1）：`daihuo-fanpai/` 始终只读未触碰，待最终发布审计复核。

## 验收收尾 · 文档补全（WP6 之后，未改冻结接口）

在「实现完成」定论下，补齐可离线推进的验收门证据文档（无新代码、不改冻结接口）：

### 新增文档
- `DEGRADATION.md`：验收门 11 降级矩阵，15 项外部缺口逐条声明降级路径，证明「未虚报完整」。
- `PARITY.md`：验收门 4 确定性产物比对现状（WP2 planner golden 逐字节；WP3/WP4 参数级 1:1；
  统一 parity fixture 建设中）。
- `tests/fixtures/scenarios/`：验收门 3 六类场景（A / 产品迁移 / B / 群戏 / 旁白 / 纯产品）
  fixture 输入说明 + `acceptance_record.md` 模板；验收记录待受控 Live 回填。

### 复核
- 验收门 1：原项目 `daihuo-fanpai` 复核纯净——清理工具链遗留的 `.workbuddy/` 未跟踪目录，
  `git status` 干净，HEAD 仍为基线 `ffc22e34`。
- `ACCEPTANCE.md`：修正 §13 十二门映射（曾误将「四闸口自然语言暂停」标为门 4，已更正为
  「确定性产物无差异」），刷新门 1/3/4/7/8/9/10/11 状态。

### 仍 🟡（需真实账号/预算/特定机器/人工）
受控 Live Pilot（门 7）、剪映真机打开（门 8 部分）、人工审核（门 9）、全链路追溯真跑（门 10）、
四闸口自然语言会话暂停（详细参考验证项）。任一未完成只能维持「实现完成，外部验收未完成」。

## [0.1.0] — 2026-08-03 · Parity Golden 补齐（验收门 3/4 离线推进）

### 新增
- `tests/parity/fixtures/`：6 份当前算法 golden —— `wp3_ffmpeg_args` / `wp3_timing` /
  `wp4_dreamina` / `wp4_ark` / `wp4_xyq` / `wp4_download`（装配 args、切段 timing、三后端
  提交命令/请求体、轮询输出解析、下载代理策略）。
- `tests/parity/test_media_parity.py`（8 例）：WP3 装配/切段 golden 逐字段断言 + 业务铁律
  （2 秒闸、720x1280、单声道 24k、apad 只垫下限、解码标记）。
- `tests/parity/test_generation_parity.py`（15 例）：WP4 三后端 golden 逐字段断言 + 路由/铁律
  （mm 带音频、i2v 不带音频、AUDIO_GUARD 仅非口播段、Ark NO_PROXY、时长上调封顶 15s）。
- `tests/parity/test_scenarios_parity.py`（24 例）：六类场景（A/产品迁移/B/群戏/旁白/纯产品）
  合成输入 `shotlist.json`+`assets.json` → `segments.golden.json` 逐字段相等 + 路由特征断言。
- `pyproject.toml`：parity 测试文件豁免 E501（含 golden 长字符串比对，与 src 业务文件同理）。

### 变更
- `PARITY.md`：「待补」三项全部完成，新增 golden 说明与 `build_timing` 行为记录。
- `ACCEPTANCE.md`：验收门 3/4 离线部分推进为 ✅（fixture/统一 golden 已就位；验收记录与
  受控 Live 仍标 🟡）。

### 验证
- pytest 全仓 **204 passed, 1 skipped**（WP6 166 → 204 = +38 例）、ruff 全绿、pyright 0。

## [0.1.0] — 2026-08-03 · Qwen 反推腿3（experimental）

### 新增
- `reverse/qwen.py`：通义千问 Qwen 单反推腿（与 seed/kimi 同契约），阿里云百炼
  OpenAI 兼容接口（compatible-mode/v1），视频以 base64 data URI 经 `video_url` 直传；
  prompt 复用 seed SCHEMA + 实体纪律；未实机验收标 experimental。
- `config.py`：新增 `dashscope_api_key`（`DASHSCOPE_API_KEY`）、`qwen_model`
  （`QWEN_MODEL`，默认 `qwen3.7-plus`）、`qwen_base_url`（`QWEN_BASE_URL`）；doctor
  `key_status` 增加 `DASHSCOPE_API_KEY` 检查。
- `tests/unit/test_qwen.py`（8 例）：prompt 硬切/铁律、请求体 data URI、Mock 请求
  （URL/密钥/NO_PROXY/超时）、无 key 抛错、extract_json 围栏、离线编排落盘。
- `LIVE_RUNBOOK.md` 第 3.5 步：Qwen 配置指南；`DEGRADATION.md` 4b 降级项。

### 验证
- pytest 全仓 **212 passed, 1 skipped**（204 → 212 = +8 例）、ruff 全绿、pyright 0。
- 依据：阿里云百炼官方文档 2026-08 核实 qwen3.7-plus 原生支持文本/图像/视频输入
  （2 小时/2GB/64 个视频，结构化 JSON 输出）。

## [0.1.0] — 2026-08-03 · Qwen 反推实测冒烟通过

### 实测记录
- 2026-08-03 用 12s 合成视频（testsrc2 + sine 音频，720x1280）真实调用百炼
  `qwen3.7-plus` 反推：返回 637 字 / 16.7s，输出 1 镜 shotlist。
- 质量核对：`scene`（电视测试卡）、`action`（线条移动/色块闪烁/时间码）、
  `key_colors`、`host_on_camera=false`、`product_role=none`、`dialogue=""` 均正确。
- 状态：从 experimental 转为「已实测冒烟」；真实带货视频完整验收待合法素材（U6）。

### 变更
- `reverse/qwen.py` / `__init__.py` / `DEGRADATION.md` 4b / `LIVE_RUNBOOK.md` 3.5 步
  同步移除 experimental 标注，改为实测记录。

## [0.1.0] — 2026-08-03 · reverse 阶段接入 run 流程(反推腿一体化)

### 变更
- `pipeline.py`：新增 `_exec_reverse`（live 模式真调反推腿 seed/kimi/qwen，
  产物写 `reverse/shotlist.json`；离线正确跳过不虚报）；`execute_stage`/`run_flow`
  透传 `leg` 参数；plan 阶段自动消费 `reverse/shotlist.json`（无需手动复制到 planning/）。
- `cli.py`：`run` 新增 `--leg {seed,kimi,qwen}`（默认 seed，仅 live reverse 生效）。
- `tests/integration/test_reverse_stage.py`（4 例）：live+leg qwen 真调落盘、
  离线跳过、非法 leg 被 argparse 拒绝、plan 自动带入 reverse 产物。

### 实测
- `dy-fanpai run --stage reverse --leg qwen`（真实百炼 key）→ 8s 视频反推 690字/18.4s
  → `--stage plan` 自动带入 → 产出 segments.json + segments.md。CLI 一体化链路首次跑通。

### 验证
- pytest 全仓 **216 passed, 1 skipped**（212 → 216 = +4 例）、ruff 全绿、pyright 0。

## [0.1.0] — 2026-08-03 · Ark(Seed)实测:账号未开通 Seed 模型

### 实测记录
- 用户提供 ARK_API_KEY → doctor `[OK]`（key 有效，账号 2103053097 可连 Ark）。
- `run --stage reverse --leg seed`（CLI 一体化）→ 压缩视频成功，但调用抛
  `ModelNotOpen`：`doubao-seed-2-1-pro-260628` 未开通。
- 探测：`doubao-seed-2-0-pro` / `doubao-seed-2-1-turbo` / `doubao-seedance-2-0` 均
  `ModelNotOpen`；`doubao-seed-1-8` 返回 NotFound。**账号未开通任何 Seed 系列模型**。
- 结论：非配置问题，需在火山方舟控制台开通「Seed 2.1 Pro（反推）」与
  「Seedance 2.0（生成）」模型服务后才能用；当前反推腿 1（seed）不可用，
  反推可用腿为 qwen（已实测通过）。

## [0.1.0] — 2026-08-03 · Ark(Seed)反推实测通过

### 实测记录
- 用户在火山方舟控制台开通 Seed 2.1 Pro 后重测：`doubao-seed-2-1-pro-260628`
  文本探测 HTTP 200；`run --stage reverse --leg seed`（CLI 一体化）真实反推 8s 视频
  返回 1639 字 / 27.1s，1 镜 shotlist。
- 质量核对：scene（电视测试卡）、action（带时间轴的线条/粒子运动细节）、
  key_colors、host_on_camera=false、product_role=none、dialogue="" 均正确。
- plan 自动带入 → 产出 segments.json + segments.md。反推腿 1（seed）实测通过。
- 至此两条反推腿可用：seed（本记录）+ qwen（此前记录）；Kimi 腿仍缺 K3 权限。

## [0.1.0] — 2026-08-03 · Qwen vs Seed 真实视频反推对比

### 对比记录(146.7s 青少年内裤带货视频,1080x1920)
- 硬切同源:两边均检出 87 切点 → 88 镜(硬切纪律成立)。
- 台词:全文归一化后**长度完全一致(731=731)**,唯一差异为「底档/底裆」一个同音字;
  Qwen 按句切为 76 片段,Seed 合并为 61 片段(切句粒度差异,内容等价)。
- 出镜判断一致:均为「仅露手」产品操作特写,host_on_camera=false。
- 差异:product_role 分布 Qwen {hero_real:75,dynamic:10,package_text:2} vs
  Seed {hero_real:67,dynamic:17,package_text:4};动作描述粒度不同(Seed 更细带时间轴,
  Qwen 更平实)。overall.product 双方均正确识别内裤/纯棉/多色/腰头字样。
- merge 双反推合并:88 镜、0 静音警告、264 抽帧点,__alt_* 候选字段就位,双向均可。

### 结论
- 反推质量两者同档:台词转写等价、实体识别正确;差异在切句粒度与描述详略,
  恰为 merge 双反推合并的价值所在(Seed 基底+alt 细句 或 反之,人工按卷宗裁决)。

## [0.1.0] — 2026-08-03 · audio 阶段接入 run 流程(原音切段一体化)

### 变更
- `pipeline.py`：新增 `_exec_audio`（live 模式原音切段，产物 `audio/segments/{seg}.wav`
  + `audio/timing.json`；离线正确跳过）；`_load_segs` 兼容 segments.json 为 list 的形态。
- `tests/integration/test_reverse_stage.py` +2 例：live 原音切段落盘与规范位置、
  离线跳过。

### 实测(146.7s 内裤带货视频全链路)
- reverse(Qwen, 88镜) → plan(30段: 18口播+12纯产品, 0 完备性警告) → approve plan
  → audio 原音切段(30 段 wav, 均 ≥2s 上传闸, timing.json 83 句镜级字幕轴)。
- 至此 CLI 一体化已覆盖 prepare→reverse→plan→audio;generate/assemble 仍离线跳过。

### 验证
- pytest 全仓 **218 passed, 1 skipped**（216 → 218 = +2 例）、ruff 全绿、pyright 0。

## [0.1.0] — 2026-08-03 · MiniMax H3 生成后端接入(第四后端)

### 新增
- `generation/minimax.py`：MiniMax H3（`POST {base}/v2/video_generation` +
  `GET /v2/query/video_generation/{task_id}`），多模态 content 数组（text/image_url/
  audio_url），媒体 base64 data URI 直传；支持文生/图生(首帧)/多模态参考(reference_image
  + reference_audio)三场景；`submit_i2v/submit_mm/submit_t2v` + `wait_download` 与
  dreamina/ark/xyq 同契约；参数级错误(400/401/402/422)不重试。
- `config.py`：`MINIMAX_API_KEY`/`MINIMAX_MODEL`(默认 MiniMax-H3)/`MINIMAX_BASE_URL`
  (默认 https://api.minimaxi.com)；doctor `key_status` 增加该键。
- `generation/service.py`：`_default_backends` 注册 `minimax`；`--i2v-backend minimax`
  可路由纯产品段。
- `tests/unit/test_minimax.py`（11 例）：请求体三场景构造、解析、Mock 提交/轮询、
  无 key 抛错、参数级错误不重试、后端已注册。

### 说明
- mm 段默认仍走即梦（口型验证过）；MiniMax reference_audio 口型能力未实测，
  mm 段切换需实测通过后显式放开（experimental）。

### 验证
- pytest 全仓 **229 passed, 1 skipped**（218 → 229 = +11 例）、ruff 全绿、pyright 0。

## [0.1.0] — 2026-08-03 · ComfyUI 生成后端接入(自建 GPU 部署,替代即梦)

### 新增
- `generation/comfyui.py`：自建 ComfyUI（ROCm 容器 0.18.2 + 原生 HTTP API）后端。
  流程：上传素材（/upload/image、/upload/audio）→ 注入工作流模板占位符 →
  POST /prompt 提交 → GET /history 轮询 → /view 下载（robust_download）。
  占位符：__PROMPT__/__IMAGE__/__IMAGE2__/__AUDIO__/__DURATION__/__WIDTH__/__HEIGHT__/__RESOLUTION__。
  与 dreamina/ark/xyq/minimax 同契约（submit_i2v/mm/t2v + wait_download，默认 240×10s 轮询）。
- `config.py`：`COMfyUI_BASE_URL` / `COMfyUI_WORKFLOW_I2V` / `COMfyUI_WORKFLOW_MM`
  （模板路径）；doctor `key_status` 增加 COMfyUI_BASE_URL 检查。
- `generation/service.py`：`_default_backends` 注册 `comfyui`（`--i2v-backend comfyui`）。
- `../resources/workflows/README.md`：模板 JSON 与占位符约定说明。
- `tests/unit/test_comfyui.py`（10 例）：占位符注入/解析/Mock 上传提交轮询下载/缺模板抛错/后端注册。

### 说明
- mm 段默认仍走即梦；ComfyUI LatentSync 口型工作流需实测通过后切换（experimental）。
- 模板 JSON 需用户在自有机器搭好后导出（Wan2.1 i2v + LatentSync 两套）。

### 验证
- pytest 全仓 **239 passed, 1 skipped**（229 → 239 = +10 例）、ruff 全绿、pyright 0。
