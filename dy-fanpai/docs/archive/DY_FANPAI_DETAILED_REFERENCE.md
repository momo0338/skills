# 抖音 dy-fanpai 详细设计参考（非主执行方案）

> 本文件仅用于查询边界和风险，不直接派发 Agent。实际执行以 `DY_FANPAI_EXECUTION_PLAN.md` v2.2 精简主方案为准；若两者冲突，以主方案为准。

版本：1.2  
日期：2026-08-03  
用途：交给多个模型 Agent 分阶段执行和验收  
原项目：`/Users/zhugx/src/daihuo-fanpai`  
新项目固定路径：`/Users/zhugx/src/skills/dy-fanpai`

### 0.1 v1.2 勘误与执行边界

本文件保留较细的历史设计展开，因此包含 22 个状态节点和 WP0～WP12 共 13 个工作包。它们不能直接作为派发编号；实际执行采用主方案的七阶段、11 个状态值、四个闸口和 WP0～WP6。

以下口径以现场核查和主方案 v2.2 为准：

- Python 3.12.13 已安装，不需要重复安装；
- 评委默认沿用原项目 Ark Seed 后端，不再作为待定设计项；
- 小云雀 CLI 已安装，当前缺少的是凭证和 Live 验收；
- 第一版不使用数据库、远程队列，也不单独创建 `external-prerequisites.json`；外部前置状态写入 doctor 报告和 `run.json`；
- `.env` 不是必需配置层；密钥优先来自进程环境或 `~/.config/dy-fanpai/`；
- Skill 的安装/注册位置由选定宿主的真实机制决定，不硬编码 `~/.workbuddy/skills/`；
- 新项目先建本地 Git，远端创建和推送需要用户另行授权。

本文件中与以上勘误或主方案 v2.2 冲突的旧示例，只能用于理解风险背景，不得照搬实现。

---

## 1. 项目目标

在不修改原项目的前提下，新建一个架构清晰、目录合理、可测试、可恢复、可审计的抖音带货视频复刻系统，项目名统一为 `dy-fanpai`，中文名统一为“抖音翻拍”。

新系统必须达到原项目已经覆盖的全部能力，但不要求兼容原项目的：

- 根目录脚本名称；
- Python 导入路径；
- 命令行参数形式；
- 默认工作目录；
- 内部实现方式；
- 文本日志格式。

新系统必须保持一致的是：

- 业务能力；
- 生成路由和关键约束；
- 输入输出语义；
- 人审闸口；
- 断点续跑能力；
- 失败恢复能力；
- 计费安全边界；
- 成片技术质量；
- 剪映草稿和普通成品交付能力。
- 作为 Agent Skill 被发现、按自然语言触发并在人工/费用闸口正确暂停的能力。

### 1.1 名称与范围边界

- Git 仓库和项目目录：`dy-fanpai`；
- Python 包：`dy_fanpai`；
- 命令行程序：`dy-fanpai`；
- 用户界面中文名：`抖音翻拍`；
- 默认用户配置目录：`~/.config/dy-fanpai/`；
- 环境变量前缀：`DY_FANPAI_`；
- `dy` 表示面向抖音带货内容生产，不表示自动下载、自动发布、自动互动或自动经营抖店；
- 第一版输入仍以用户合法持有的本地视频文件为准，URL 下载不属于原项目能力，也不纳入第一版等价范围。

### 1.2 原项目基线

执行开始时将以下版本视为参考实现：

```text
仓库：https://github.com/wangcanyu/daihuo-fanpai.git
提交：ffc22e34cb35477b04967163c3932002ed4f3fed
短提交：ffc22e3
```

开始执行前必须再次记录原项目 HEAD 和工作区状态。如果 HEAD 已变化，不得静默替换基线，必须生成新的基线记录并说明差异。

### 1.3 非目标

第一版禁止顺带实施以下事项：

- Web 管理后台；
- 数据库和远程任务队列；
- 多机分布式调度；
- 自动发布抖音；
- 自动选择商品卖点；
- 自动绕过平台审核；
- 自动消耗真实模型额度的 CI；
- 重写或“优化”已经验证有效的业务 Prompt；
- 用统一 Provider 抹平不同模型的能力差异。

---

## 2. 总体执行原则

1. 原项目全程只读，禁止改文件、提交、格式化或补测试。
2. 新项目独立建仓，不以运行时方式依赖原项目。
3. 原项目是参考实现和行为 Oracle，不是新项目的依赖库。
4. 先冻结业务契约，再写架构；先离线测试，再接付费能力。
5. 每个阶段必须有可执行验收命令，不能用“代码已完成”代替验收。
6. 默认测试禁止网络、禁止真实提交、禁止消耗积分。
7. 所有付费步骤必须同时满足：人工批准、明确后端、明确段数、明确调用上限。
8. AI 输出具有随机性，一致性以请求语义、路由、约束和验收结果为准，不以视频哈希为准。
9. 确定性产物必须支持逐字段或规范化后的精确比较。
10. 每个 Agent 只修改自己工作包声明的目录，避免并行冲突。
11. 同一工作区必须使用进程锁和提交租约，禁止两个进程对同一段重复付费提交。
12. 所有上传到第三方服务的视频、人脸、声音和商品资料必须经过权利与隐私确认。
13. 新项目必须能从干净环境安装和运行，不能只在开发源码目录内工作。
14. Prompt、模型名、Provider/CLI 版本、ffmpeg 版本和请求指纹必须进入可追溯记录。

---

## 3. 已冻结技术栈

- Python：已安装的 3.12.13，不以系统 Python 3.14 作为生产基线；
- 包管理：`pyproject.toml` + `uv`，同时保留标准 `pip` 安装能力；
- CLI：标准库 `argparse`；
- 数据模型：Pydantic v2；
- HTTP：`requests`，同步串行；
- 测试：pytest；
- Mock：pytest 内置 `monkeypatch` + `responses`；
- 媒体：系统 `ffmpeg`、`ffprobe`；
- 格式与静态检查：Ruff；
- 类型检查：Pyright，仅检查 `src/dy_fanpai`；
- JSON：UTF-8、`ensure_ascii=False`；
- 运行状态：本地 JSON 文件，不引入数据库。
- 分发：源码克隆后可作为 Skill 使用，同时必须能构建 wheel 并在干净虚拟环境安装；
- 资源打包：公开 Prompt、schema 和示例进入 wheel，私有音色、私有方法论和真实用户素材不得进入 wheel。

依赖必须分层：

```text
core       基础运行依赖
dev        测试和静态检查
jianying   剪映草稿可选依赖
```

CosyVoice、Seed-VC、即梦 CLI、小云雀 CLI、ffmpeg 不作为普通 Python 必装依赖，由 doctor 检查。

---

## 4. 目标目录结构

```text
dy-fanpai/
├── pyproject.toml
├── README.md
├── SKILL.md
├── AGENTS.md
├── LICENSE
├── .gitignore
├── docs/
│   ├── architecture.md
│   ├── workflows.md
│   ├── contracts.md
│   ├── providers.md
│   ├── artifacts.md
│   ├── acceptance.md
│   └── decisions/
│       ├── 0001-python-version.md
│       ├── 0002-state-storage.md
│       ├── 0003-provider-boundaries.md
│       └── 0004-cost-gates.md
├── src/
│   └── dy_fanpai/
│       ├── __init__.py
│       ├── cli.py
│       ├── domain/
│       │   ├── models.py
│       │   ├── enums.py
│       │   ├── contracts.py
│       │   └── errors.py
│       ├── application/
│       │   ├── pipeline.py
│       │   ├── stages.py
│       │   ├── state_machine.py
│       │   ├── run_context.py
│       │   └── gates.py
│       ├── reverse/
│       │   ├── seed.py
│       │   ├── kimi.py
│       │   ├── merge.py
│       │   └── prompts.py
│       ├── planning/
│       │   ├── planner.py
│       │   ├── grouping.py
│       │   ├── routing.py
│       │   ├── prompts.py
│       │   ├── completeness.py
│       │   ├── asset_requirements.py
│       │   ├── localization.py
│       │   └── cast.py
│       ├── audio/
│       │   ├── source_audio.py
│       │   ├── tts.py
│       │   ├── voice_conversion.py
│       │   ├── timing.py
│       │   └── pronunciation.py
│       ├── generation/
│       │   ├── service.py
│       │   ├── routing.py
│       │   ├── recovery.py
│       │   └── providers/
│       │       ├── base.py
│       │       ├── dreamina.py
│       │       ├── ark.py
│       │       └── xyq.py
│       ├── media/
│       │   ├── ffmpeg.py
│       │   ├── probe.py
│       │   ├── normalize.py
│       │   ├── download.py
│       │   └── frames.py
│       ├── quality/
│       │   ├── decode.py
│       │   ├── lipsync.py
│       │   ├── judge.py
│       │   └── report.py
│       ├── delivery/
│       │   ├── subtitles.py
│       │   ├── final_video.py
│       │   └── jianying.py
│       └── infrastructure/
│           ├── config.py
│           ├── filesystem.py
│           ├── process.py
│           ├── http.py
│           └── logging.py
├── resources/
│   ├── prompts/
│   ├── schemas/
│   └── examples/
├── tests/
│   ├── fixtures/
│   ├── unit/
│   ├── contract/
│   ├── integration/
│   ├── parity/
│   └── live/
└── scripts/
    ├── capture_original_baseline.py
    ├── compare_artifacts.py
    └── verify_release.py
```

---

## 5. 核心数据模型

不得直接用任意 `dict` 在阶段之间传递。至少建立以下模型：

### 5.1 Shotlist

- `VideoInfo`
- `OverallAnalysis`
- `Shot`
- `Shotlist`

`Shot` 至少包含：

```text
shot_id
start
end
is_opening_3s
shot_size
camera
subject
action
scene
lighting
person
product_in_frame
product_role
onscreen_text
dialogue
key_colors
```

### 5.2 产品素材

- `ProductAssets`
- `ProductForm`
- `CastMember`
- `CastProfile`

必须保留：主播锚图、主播描述、产品描述、多种产品形态、形态别名、产品动作词。

### 5.3 生成计划

- `Segment`
- `SegmentPlan`
- `CompletenessWarning`
- `GenerationRoute`

`Segment` 必须覆盖：

```text
seg
type: mm | i2v
images
anchor
anchor_labels
prompt
dialogue
shots
start
end
duration
opening_3s
warns
```

### 5.4 音频与时间轴

- `AudioSegment`
- `SentenceTiming`
- `TimingManifest`
- `VoiceProfile`

### 5.5 外部任务与恢复

- `ProviderTask`
- `GenerationAttempt`
- `ClipArtifact`

每次提交至少保存：

```text
segment_id
provider
provider_task_id
submitted_at
request_fingerprint
attempt
status
usage
output_path
last_error
```

### 5.6 项目状态

- `ProjectManifest`
- `StageRecord`
- `ApprovalRecord`
- `ArtifactRecord`
- `ProvenanceRecord`
- `RightsAndConsentRecord`

所有模型都必须支持 schema 版本，但第一版内部使用，不要求兼容原项目 JSON。

`ProvenanceRecord` 至少记录：Git 提交、Python 版本、ffmpeg/ffprobe 版本、外部 CLI 版本、Provider、模型名、Prompt 版本、请求指纹、输入哈希和生成时间。无法取得版本时必须明确写 `unknown`，不能留空。

---

## 6. 工作区和产物布局

每个视频任务必须自包含：

```text
runs/<project-id>/
├── project.json
├── state.json
├── lock.json
├── rights-and-consent.json
├── provenance.json
├── cost-ledger.json
├── remote-assets.json
├── inputs/
│   ├── source.mp4
│   ├── product-assets.json
│   └── assets/
├── reverse/
│   ├── seed.json
│   ├── kimi.json
│   ├── merged-draft.json
│   ├── dossier.md
│   ├── frames/
│   └── shotlist.json
├── planning/
│   ├── required-assets.json
│   ├── segments.json
│   ├── segments.md
│   └── approval.json
├── localization/
│   ├── facts.json
│   ├── draft.txt
│   └── edits.json
├── audio/
│   ├── segments/
│   ├── timing.json
│   └── manifest.json
├── generation/
│   ├── tasks/
│   ├── clips/
│   └── attempts/
├── qc/
│   ├── decode-report.json
│   ├── lipsync/
│   └── judge.json
├── output/
│   ├── FULL.mp4
│   ├── FULL.srt
│   ├── onscreen-text.md
│   └── FINAL.mp4
├── delivery/
│   └── jianying/
└── logs/
```

大文件不得进入 Git。

---

## 7. 状态机

```text
CREATED
→ DIAGNOSED
→ SOURCE_READY
→ RIGHTS_CONFIRMED
→ REVERSED
→ RECONCILIATION_REQUIRED | RECONCILED
→ ASSETS_REQUIRED
→ ASSETS_READY
→ PLANNED
→ PLAN_REVIEW_REQUIRED
→ PLAN_APPROVED
→ LOCALIZATION_REQUIRED | SCRIPT_READY
→ AUDIO_READY
→ GENERATION_APPROVAL_REQUIRED
→ GENERATING
→ CLIPS_READY
→ ASSEMBLED
→ QC_REQUIRED
→ QC_PASSED
→ DELIVERED
```

### 7.1 状态规则

- 每次状态变化必须写 `state.json`；
- 必须记录时间、触发命令、输入指纹和产物；
- 阶段失败不得覆盖上一个成功状态；
- 失败详情写入阶段记录；
- 允许重新执行当前阶段；
- 上游输入变化后，下游阶段必须标记 stale；
- 不允许跳过人审状态直接进入真实生成；
- `--force` 不能绕过费用批准和安全闸口。
- 同一工作区只能有一个有效写锁；锁包含进程、主机、开始时间和租约期限；
- 过期锁只能通过显式恢复命令接管，并保存原锁证据；
- Provider 提交前必须先原子写入提交意图，提交成功后补写 task ID，缩小崩溃导致重复扣费的窗口；
- schema 版本不认识时必须停止并提示迁移，禁止猜测读取。

---

## 8. 阶段契约

### S00 Doctor

输入：配置和本机环境。  
输出：`doctor-report.json` 和终端摘要。  
检查：ffmpeg、ffprobe、即梦 CLI、Ark、Kimi、小云雀、CosyVoice、Seed-VC、剪映草稿能力、代理状态。  
要求：不得打印密钥；必须区分 blocker、optional、warning；支持 `--strict`。

### S01 Source Ingest

输入：参考视频路径。  
输出：工作区内源视频、SHA-256、ffprobe 信息。  
要求：默认复制或硬链接策略必须写入 ADR；不得静默覆盖。

### S01.5 Rights, Consent and Privacy Gate

输入：源视频、人物/声音/商品素材、拟使用的第三方 Provider。  
输出：`rights-and-consent.json`。  
必须由用户确认：

- 对参考视频具有合法使用权限，或使用方式满足适用法律和平台规则；
- 对人物肖像、声音克隆和主播锚图具有授权；
- 商品图、品牌标识、价格、活动、赠品和宣传主张真实且可使用；
- 知道哪些素材会上传到 Ark、Kimi、即梦或小云雀；
- 接受相应 Provider 的数据处理与保存规则。

没有确认不得上传素材。该记录只保存确认事实和时间，不保存身份证件等额外敏感信息。

### S02 Reverse

输入：源视频。  
输出：Seed shotlist；可选 Kimi shotlist。  
关键规则：硬切时间同源；Seed 关闭 thinking 并流式；国内端点直连；不得让静音贴字进入台词。

上传型 Provider 必须记录远端文件 ID、上传时间、用途、清理能力和清理结果；支持删除的临时远端文件应在阶段完成后删除，失败则进入待清理清单。

### S03 Reconcile

输入：Seed、Kimi、源视频。  
输出：dossier、差异帧、merged draft、最终 shotlist。  
规则：实体以 Seed 和原片帧为基础，运镜时序参考 Kimi，互斥信息必须看帧；最终数据不得残留候选字段。

### S04 Asset Requirements

输入：最终 shotlist。  
输出：需要的产品形态清单和待填产品档案。  
规则：按产品形态、包装、剖面、裸品分别列出，不允许笼统只要一张产品图。

### S05 Planning

输入：shotlist、产品档案、可选角色档案。  
输出：segments JSON、人工审核 Markdown。  
关键规则：按硬切分组；动作原样进入 Prompt；产品动词完备性检查；口播、hero、package 正确路由；单段时长限制；前三秒标记；群戏人数硬约束。

### S06 Plan Review

输入：segments。  
输出：approval record。  
必须人工检查：动作、产品锚图、包装、人物一致性、台词、前三秒、合规、所有 warning。  
只允许显式命令批准。

### S07 Localization

输入：segments、产品事实、可选方法论资料。  
输出：本地化台词和修改记录。  
规则：只改台词和对应口播 Prompt；字数变化告警；不得编造价格、活动、疗效、背书。

### S08 Audio

支持三条路径：

1. 原片切音频；
2. TTS；
3. Seed-VC 换声。

输出统一为逐段 WAV 和句级 timing。  
规则：即梦音频 2 秒下限；不能把音频垫满计划时长；TTS 台词必须与口播 Prompt 一致；Seed-VC 参考音频需信噪比检查。

### S09 Generation Approval

输入：计划、后端、待生成段。  
输出：费用批准记录。  
必须记录：段数、段 ID、后端、是否人物镜头、预计调用次数、硬上限。  
默认建议只批准 S1 Pilot。

代码必须硬性执行 `max-submits`，不能只把它写进审批记录。每次提交和 usage 都追加到 `cost-ledger.json`；达到上限后即使仍有缺失段也必须停止并重新审批。

### S10 Generate

路由规则：

- 人物口播和对口型：即梦；
- 纯产品 i2v：即梦、Ark 或小云雀；
- 含人脸参考图不得路由到 Ark；
- 默认串行；
- 已完成且通过解码检查的段跳过；
- 有任务 ID 但未下载的段优先恢复，禁止直接重复提交；
- 同一段存在有效提交租约时，第二个进程必须拒绝提交；
- 下载后必须执行 ffmpeg 解码探针；
- 单段失败不带崩整批，但最终状态必须准确反映部分失败。

### S11 Assemble

输入：全部通过检查的 clips、逐段音频。  
输出：中性母版 `FULL.mp4`。  
规则：逐段归一化到 720×1280；统一 SAR、编码和音频参数；缺音频补静音；配音对齐段起点；FULL 不烧字幕、不加 BGM。

### S12 QC

包含：

- 全片解码检查；
- 音视频轨检查；
- 时长与段顺序检查；
- 帧级口型证据包；
- 原片和成片双视频评委；
- 人工产品身份、包装、动作和口型审核。

技术检查通过不能替代人工审核。

QC 报告必须分别给出：技术状态、人物/商品身份状态、包装文字状态、动作完整性、口型状态和内容合规状态，不允许压成一个含糊的 `passed`。

### S13 Deliver

支持：

- SRT；
- 屏上贴字清单；
- 烧字幕成品；
- 可选 BGM；
- 剪映草稿。

剪映草稿必须保持：视频、配音、字幕、贴字参考、空 BGM 五轨；素材自包含；支持 Windows/WSL 路径；默认禁止覆盖同名草稿。

### S14 Retention and Cleanup

输入：已交付工作区和保留策略。  
输出：清理计划或清理报告。  
要求：默认只做 `--dry-run`；禁止删除源视频、最终成品、状态、任务 ID、费用记录和验收报告；临时上传压缩片、抽帧缓存和归一化中间文件可按策略清理；清理前后记录文件清单与释放空间。

同时检查 `remote-assets.json`，报告仍滞留在第三方服务的临时文件；没有可靠删除 API 时必须在报告中明确说明，不能假装已经清理。

---

## 9. CLI 设计

第一版建议命令：

```bash
dy-fanpai doctor
dy-fanpai version
dy-fanpai new --video target.mp4 --workspace runs/demo
dy-fanpai status runs/demo
dy-fanpai confirm-rights runs/demo
dy-fanpai reverse runs/demo [--dual]
dy-fanpai assets runs/demo
dy-fanpai plan runs/demo
dy-fanpai approve-plan runs/demo
dy-fanpai localize runs/demo --facts facts.json
dy-fanpai audio runs/demo --mode source|tts|voice-convert
dy-fanpai approve-generation runs/demo --segments S1 --backend dreamina --max-submits 1
dy-fanpai generate runs/demo --segments S1
dy-fanpai assemble runs/demo
dy-fanpai qc runs/demo
dy-fanpai deliver runs/demo --mode final|jianying|both
dy-fanpai clean runs/demo --dry-run
dy-fanpai run-next runs/demo
```

`run-next` 只能执行到下一个人审或费用闸口，不能自动越过。

### 9.1 Agent Skill 入口

根目录 `SKILL.md` 必须定义：

- “抖音翻拍、复刻带货视频、用我的产品重做”等触发语义；
- 需要向用户索取的输入；
- Doctor、权利确认、计划人审和费用审批四类暂停点；
- 不自动安装重型依赖、不自动读取真实密钥做测试、不自动提交付费任务；
- A 模式、产品迁移、B 模式、群戏模式的路由；
- 状态恢复和 `status` 命令用法。

必须在全新 Agent 会话中验证 Skill 能被发现，且自然语言请求只推进到下一个闸口，不得仅验证 CLI。

---

## 10. Provider 边界

不要定义一个万能 `generate()`。

建议最小接口：

```text
ReverseProvider.reverse(video, cuts, options) -> Shotlist

I2VProvider.submit_i2v(image, prompt, duration, resolution, ratio) -> ProviderTask
I2VProvider.poll(task) -> TaskStatus
I2VProvider.download(task, destination) -> DownloadResult

LipSyncProvider.submit_mm(images, audio, prompt, duration, resolution, ratio) -> ProviderTask
LipSyncProvider.poll(task) -> TaskStatus
LipSyncProvider.download(task, destination) -> DownloadResult
```

能力矩阵必须显式配置：

| Provider | 反推 | 纯产品 i2v | 人物口播 | 音频口型 | 人脸参考 |
|---|---:|---:|---:|---:|---:|
| Seed Ark | 是 | 否 | 否 | 否 | 不适用 |
| Kimi | 是 | 否 | 否 | 否 | 不适用 |
| Dreamina | 否 | 是 | 是 | 是 | 支持但可能审核 |
| Ark Video | 否 | 是 | 不作为主路 | 未验 | 拦截风险高 |
| XYQ | 否 | 是 | 不作为主路 | 未验 | 按实际能力 |

未实测能力必须标记 `experimental`，不能通过类型设计假装已经支持。

---

## 11. 配置与密钥

配置优先级：

1. 当前进程环境变量；
2. 用户配置目录；
3. 项目非敏感配置；
4. 默认值。

必须支持：

```text
ARK_API_KEY
ARK_SEED_MODEL
KIMI_API_KEY / MOONSHOT_API_KEY
KIMI_BASE_URL
KIMI_K3_MODEL
XYQ_ACCESS_KEY
XYQ_VIDEO_MODEL
COSYVOICE_HOME
DY_FANPAI_SEEDVC_HOME
DY_FANPAI_JY_DRAFTS
DY_FANPAI_JY_PYTHON
DY_FANPAI_DOWNLOAD_PROXY
```

用户配置目录固定为 `~/.config/dy-fanpai/`。API Provider 的通用密钥名保持官方惯例；项目自身路径和行为开关使用 `DY_FANPAI_` 前缀。

要求：

- 不提交密钥；
- 日志不显示完整密钥；
- 生成请求日志必须脱敏；
- 国内端点默认直连；
- 只有下载故障时才允许显式下载代理；
- 测试中清空真实环境变量，使用假密钥。

### 11.1 外部前置条件登记

新项目通过 doctor 报告和 `run.json` 逐项登记，不创建单独的 `external-prerequisites.json`：

- 即梦 CLI 的已验证版本、登录状态和积分池；
- Ark、Kimi、小云雀的账户、模型可用性和区域；
- CosyVoice、Seed-VC 的安装路径和已验证提交；
- pyJianYingDraft 与目标剪映版本；
- 私有 `qianchuan` 方法论包是否存在；
- 私有/用户提供音色是否存在及授权状态。

缺少私有方法论包时，可以完成 A 模式和基于事实的普通台词替换，但不得宣称已经复现原作者的完整 B 模式方法论。缺少合法音色时，不得用未授权声音替代并宣称换声功能完成。

---

## 12. 测试体系

### 12.1 Unit

覆盖：分组、路由、产品形态匹配、动作完备性、台词切句、读音修正、时长计算、状态转换、路径转换、配置优先级。

### 12.2 Contract

覆盖：全部 Pydantic 模型、JSON round-trip、Provider 请求和响应、Artifact manifest、状态文件。

### 12.3 Golden

从原项目样例生成并冻结：

- required assets；
- segments；
- segments review markdown；
- subtitles；
- onscreen text list；
- timing；
- localization apply 结果。

Fixtures 不能只有海参单主播案例，至少增加：

- A 模式原产品原台词；
- 产品迁移；
- B 模式事实包和台词修改；
- 三角色群戏；
- 全片旁白、人物不说话；
- 纯产品无人物；
- 包装文字和多种产品形态；
- 短于 2 秒音频；
- 缺锚图、缺音频、坏视频流和已有未完成 task 的负向案例。

比较前只允许规范化绝对路径、时间戳和随机任务 ID。

### 12.4 Media Integration

使用程序生成的小型无版权测试视频，覆盖：切段、2 秒垫尾、抽帧、归一化、拼接、静音补轨、字幕烧入、BGM 混音、完整解码。

### 12.5 Provider Mock

验证：模型名、URL、直连策略、图片顺序、音频 role、Prompt、分辨率、时长、比例、重试、轮询、任务保存、恢复下载。

### 12.6 Parity

相同样例同时运行原项目确定性环节和新项目，对比规范化产物。原项目只读。

### 12.7 Live

默认跳过。必须通过环境开关和人工批准才运行。第一轮每个 Provider 最多 1 次提交；必须保存 task ID、usage、产物哈希和验收结果。

### 12.8 Packaging and Skill

必须构建 wheel 和 sdist，在干净虚拟环境安装后运行 `dy-fanpai --help`、doctor 和离线样例。检查公开资源已打包、私有资源未打包。另在全新 Agent 会话验证 `SKILL.md` 的发现、触发、暂停和恢复行为。

### 12.9 Concurrency and Crash Recovery

用两个进程竞争同一工作区，验证写锁、租约、提交意图和 task ID 恢复。模拟在“提交前、提交后未写 task ID、写 task ID 后未下载、下载一半”四个位置崩溃，证明不会无提示重复扣费。

### 12.10 Retention and Disk Pressure

验证磁盘空间预检、清理 dry-run、保留列表和实际清理报告。磁盘不足必须在生成或装配前停止，不能等写到一半才破坏工作区。

---

## 13. 功能验收矩阵

每一行必须有测试或人工证据，不能只填“已实现”。

| 能力 | 离线 | Mock | Live | 人审 | 状态 |
|---|---:|---:|---:|---:|---|
| Doctor 分级 | 必须 | - | 可选 | - | 待完成 |
| Skill 发现与自然语言闸口 | 必须 | - | 必须 | 必须 | 待完成 |
| 权利、声音和隐私确认 | 必须 | - | - | 必须 | 待完成 |
| Seed 单反推 | Schema | 必须 | 必须 | 必须 | 待完成 |
| Kimi 双反推 | Schema | 必须 | 必须 | 必须 | 待完成 |
| 分歧帧与 dossier | 必须 | - | - | 必须 | 待完成 |
| 产品素材清单 | 必须 | - | - | 必须 | 待完成 |
| 规划与完备性 | 必须 | - | - | 必须 | 待完成 |
| 群戏锚定和人数约束 | 必须 | - | Pilot | 必须 | 待完成 |
| 本地化台词 | 必须 | Mock | 可选 | 必须 | 待完成 |
| 原音切段 | 必须 | - | - | 抽听 | 待完成 |
| TTS | Manifest | 必须 | Pilot | 抽听 | 待完成 |
| Seed-VC | 检查 | Mock process | Pilot | 抽听 | 待完成 |
| 即梦人物口播 | Request | 必须 | 必须 | 必须 | 待完成 |
| 即梦纯产品 | Request | 必须 | 必须 | 必须 | 待完成 |
| Ark 纯产品 | Request | 必须 | 必须 | 必须 | 待完成 |
| 小云雀纯产品 | Request | 必须 | 必须 | 必须 | 待完成 |
| 任务恢复和断点续跑 | 必须 | 必须 | Pilot | - | 待完成 |
| 并发防重复提交 | 必须 | 必须 | 不并发付费 | - | 待完成 |
| 坏流自动重下 | 必须 | 必须 | 可选 | - | 待完成 |
| 装配 | 必须 | - | - | 抽看 | 待完成 |
| 口型 QC 证据包 | 必须 | - | Pilot | 必须 | 待完成 |
| 双视频评委 | Request | 必须 | 必须 | 复核 | 待完成 |
| SRT/贴字 | 必须 | - | - | 必须 | 待完成 |
| 最终成品 | 必须 | - | - | 必须 | 待完成 |
| 剪映草稿 | 结构 | Mock/本机 | 必须 | 必须 | 待完成 |
| 干净环境安装与资源打包 | 必须 | - | - | - | 待完成 |
| 产物追溯与版本记录 | 必须 | 必须 | 必须 | 复核 | 待完成 |
| 费用硬上限和 cost ledger | 必须 | 必须 | Pilot | 复核 | 待完成 |
| 远端临时素材登记与清理 | 必须 | 必须 | Pilot | 复核 | 待完成 |
| 磁盘预检和安全清理 | 必须 | - | - | 复核 | 待完成 |

---

## 14. Agent 工作包

### WP0：基线与需求清点

负责人：Baseline Agent  
依赖：无  
只读原项目：是

任务：

- 记录原项目提交、环境和文件清单；
- 建立 21 个脚本到新能力的映射；
- 列出全部 CLI、环境变量、输入输出、失败恢复行为；
- 运行不计费样例，保存确定性基线；
- 编写 `docs/acceptance.md` 初稿。

交付：

```text
docs/original-baseline.md
docs/feature-inventory.md
tests/fixtures/original/
```

验收：原项目零修改；功能清单无未归类脚本；样例可重复生成。

### WP1：项目骨架与工程门禁

负责人：Foundation Agent  
依赖：WP0 的技术决策输入

任务：创建新仓库、pyproject、基础包、Ruff、类型检查、pytest、CI、README、SKILL.md、AGENTS.md、许可证、忽略规则、wheel/sdist 构建和干净环境安装测试。

验收命令：

```bash
pytest
ruff check .
pyright
dy-fanpai --help
```

不得接真实 Provider。

### WP2：领域模型和工作区

负责人：Domain Agent  
依赖：WP1

所有权：`domain/`、`application/run_context.py`、`infrastructure/filesystem.py`、contract tests。

任务：实现数据模型、工作区、Artifact manifest、输入指纹、Provenance、磁盘空间预检、进程锁、提交租约和原子状态写入。

验收：模型 round-trip；路径不越出工作区；已有文件不被静默覆盖。

### WP3：状态机和费用/人审闸口

负责人：Workflow Agent  
依赖：WP2

所有权：`application/`。

任务：实现状态转换、stale 传播、失败记录、权利与隐私确认、plan approval、generation approval、run-next 和清理审批边界。

验收：非法跳转被拒绝；修改上游后下游变 stale；不能绕过费用批准。

### WP4：媒体基础设施

负责人：Media Agent  
依赖：WP1

所有权：`media/`、media integration tests。

任务：ffprobe、抽帧、切音频、2 秒垫尾、归一化、拼接、解码探针、下载校验、字幕烧入基础函数。

验收：只用合成媒体；无网络；所有输出可完整解码。

### WP5：规划与产品素材

负责人：Planning Agent  
依赖：WP2、WP0 基线

所有权：`planning/`。

任务：产品素材清单、硬切分组、路由、Prompt、动作完备性、产品形态别名、群戏补丁、本地化应用。

验收：与原样例规范化结果一致；关键动作和人数约束不得丢失。

### WP6：反推与双反推

负责人：Reverse Agent  
依赖：WP2、WP4

所有权：`reverse/`。

任务：Seed、Kimi Provider、同源切点、视频压缩、流式解析、静音闸、merge、差异帧和 dossier。

验收：先完成 Mock；真实 API 只在 Live Gate 后执行。

### WP7：音频

负责人：Audio Agent  
依赖：WP2、WP4

所有权：`audio/`。

任务：原音复用、TTS adapter、说话人解析、读音修正、timing、Seed-VC adapter 和参考音质检查。

验收：原音路径完全离线通过；TTS/Seed-VC 先 Mock，后 Pilot。

### WP8：视频生成和恢复

负责人：Generation Agent  
依赖：WP2、WP3、WP4

所有权：`generation/`。

任务：路由、Dreamina、Ark、XYQ、任务记录、轮询、恢复下载、重试、usage、解码后落成。

验收：Mock 覆盖所有路径；同一未完成 task 不得重复提交；人物不得错误路由 Ark。

### WP9：装配、质检和评委

负责人：Quality Agent  
依赖：WP4、WP7、WP8

所有权：`quality/` 和装配 service。

任务：FULL 母版、技术报告、帧级口型证据包、双视频评委请求、人工 QC 状态。

验收：技术通过不能自动标记人工通过；FULL 无字幕无 BGM。

### WP10：交付

负责人：Delivery Agent  
依赖：WP4、WP9

所有权：`delivery/`。

任务：SRT、贴字清单、烧字幕、BGM、剪映五轨草稿、素材自包含、Windows/WSL 路径。

验收：final 模式跨平台；剪映模式在指定版本真实打开、编辑、保存一次。

### WP11：CLI 集成

负责人：CLI Agent  
依赖：WP2-WP10 的稳定服务接口

所有权：`cli.py`、README 使用说明、CLI tests。

任务：实现完整命令组、统一错误呈现、status、version、confirm-rights、clean；完善 SKILL.md 的自然语言路由和暂停规则。CLI 和 Skill 只编排 service，不复制业务逻辑。

验收：从 new 到离线 deliver 的无网络演示可完成；所有闸口有效；在全新 Agent 会话中自然语言触发成功并停在正确闸口。

### WP12：全功能对照和发布审计

负责人：Release Agent  
依赖：全部

任务：运行静态检查、全测试、parity、干净环境安装、Skill 新会话测试、并发崩溃恢复、受控 Live Pilot、剪映实机测试，逐行填功能矩阵。

交付：

```text
docs/release-audit.md
docs/known-limitations.md
release-manifest.json
```

只有 WP12 可以给出“可替代原项目”的结论。

---

## 15. 并行执行建议

```text
WP0 ─┬→ WP1 → WP2 → WP3 ───────────────┐
     │          ├→ WP5                 │
     │          ├→ WP6                 │
     │          ├→ WP7                 ├→ WP11 → WP12
     │          └→ WP8                 │
     └────────→ WP4 → WP9 → WP10 ─────┘
```

推荐批次：

1. 第一批：WP0；
2. 第二批：WP1；
3. 第三批并行：WP2、WP4；
4. 第四批并行：WP3、WP5、WP6、WP7；
5. 第五批：WP8；
6. 第六批并行：WP9、WP10；
7. 第七批：WP11；
8. 第八批：WP12。

同一批并行前必须由集成负责人冻结公共接口。禁止多个 Agent 同时编辑 `domain/models.py`、`cli.py` 或 `pyproject.toml`。

---

## 16. Agent 通用任务模板

将下面内容附加到每个 Agent 的具体工作包：

```text
你正在实现抖音 dy-fanpai 的 <工作包编号>。

约束：
1. 原项目 /Users/zhugx/src/daihuo-fanpai 只读，禁止修改。
2. 只修改本工作包声明的目录。
3. 不调用真实付费 API，除非任务明确属于已批准的 Live Gate。
4. 先读执行方案、架构文档和对应原实现，再编码。
5. 不把原代码机械复制成新的平铺脚本；业务规则必须保留。
6. 新增或修改的确定性行为必须有测试。
7. 不以测试通过之外的模型自述作为完成证据。
8. 完成时报告：修改文件、测试命令、测试结果、未覆盖项、风险和下一工作包接口。

验收：
- 所有声明测试通过；
- 无原项目改动；
- 无真实额度消耗；
- 无越权修改；
- 交付物完整。
```

---

## 17. 禁止事项

- 禁止修改原项目以方便新项目测试；
- 禁止把原脚本作为 subprocess 永久调用；
- 禁止默认读取用户真实密钥进行测试；
- 禁止在没有 approval record 时真实生成；
- 禁止在没有 rights-and-consent record 时上传视频、人脸或声音；
- 禁止发现已有 task ID 后直接重新提交；
- 禁止绕过工作区锁并发提交同一段；
- 禁止把技术 QC 通过等同于商品身份和内容通过；
- 禁止省略 `segments.md` 人审；
- 禁止把人物段路由给 Ark 作为默认降级；
- 禁止自动覆盖剪映草稿；
- 禁止把私有音色和千川资料提交 Git；
- 禁止缺少私有方法论或合法音色时宣称相应能力已经完整验收；
- 禁止清理命令默认删除文件或删除源视频、最终成品、任务 ID 和验收证据；
- 禁止为了抽象统一而删除 Provider 特有能力和限制；
- 禁止一次性合并超大重写而无阶段验收证据。

---

## 18. 最终发布门

只有同时满足以下条件，才可认定新项目功能达成：

1. Ruff、类型检查和全部默认测试通过；
2. 原项目确定性样例和新项目 parity 通过；
3. 三种视频生成后端 Mock 契约通过；
4. Seed 和 Kimi Mock 契约通过；
5. 至少完成一次受控 Seed 反推 Pilot；
6. 至少完成一次即梦人物口播 Pilot；
7. 至少完成一次纯产品 i2v Pilot；
8. Ark 和小云雀的真实能力分别验证，未验证项明确标 experimental；
9. 原音、TTS 或换声三路径按声明范围完成验收；
10. 断点续跑和已有 task 恢复通过；
11. 坏流解码检查和重下机制通过；
12. FULL 母版无字幕无 BGM；
13. 最终成品可完整解码，音视频参数合格；
14. 剪映草稿在目标剪映版本真实打开、编辑、保存；
15. 功能矩阵没有无说明的空白项；
16. `release-audit.md` 明确列出限制、实测证据和费用；
17. 原项目工作区仍保持未修改；
18. wheel 和 sdist 在干净虚拟环境安装通过，公开资源齐全且私有资源未泄漏；
19. 新 Agent 会话能发现 Skill、自然语言触发并在权利、人审和费用闸口暂停；
20. 工作区锁和崩溃恢复测试证明不会静默重复付费提交；
21. rights-and-consent、provenance、模型/CLI/ffmpeg 版本和费用记录完整；
22. 磁盘空间预检和安全清理通过；
23. B 模式方法论和换声功能的外部资源前置条件已满足，或明确降级且不得宣称完整等价；
24. A、产品迁移、B、群戏、旁白、纯产品六类场景都有 fixture 和验收记录；
25. `max-submits` 在代码层硬执行，cost ledger 与 Provider usage 对得上；
26. 远端临时上传素材均有登记，能删除的已删除，不能删除的有明确保留说明；
27. 确定性产物 parity 无未解释差异，媒体技术指标全部达标，Live Pilot 的人物、商品、包装、动作和口型均完成人工审片。

若某个原功能因外部服务、凭证或平台政策无法实测，应标记“实现完成但外部验收未完成”，不得写成“完全完成”。

---

## 19. 建议的第一条执行指令

先只派发 WP0，不要让多个 Agent 立即开始写代码：

```text
请执行《抖音 dy-fanpai 全新实现执行方案》的 WP0：基线与需求清点。
原项目路径为 /Users/zhugx/src/daihuo-fanpai，只读。
目标新项目路径为 /Users/zhugx/src/skills/dy-fanpai。
本阶段不接 API、不消耗额度、不修改原项目、不实现新业务代码。
请产出 original-baseline.md、feature-inventory.md、确定性 fixtures 和 acceptance.md 初稿，并提供逐项验证证据。
```

WP0 验收通过以后，再批准 WP1。
