# 抖音 dy-fanpai 精简执行方案

版本：2.2  
日期：2026-08-03  
状态：唯一权威执行方案  

> 本文件可以单独派发给执行 Agent。`archive/DY_FANPAI_DETAILED_REFERENCE.md` 仅供人工查阅，不是执行前置；若内容冲突，以本文件为准。

原项目（只读）：`/Users/zhugx/src/daihuo-fanpai`  
原项目基线：`ffc22e34cb35477b04967163c3932002ed4f3fed`  
新项目：`/Users/zhugx/src/skills/dy-fanpai`

启动前规划文件可以位于独立规划目录。WP0 的第一步必须创建新项目目录，并把本文件原样复制为新仓库根目录的 `EXECUTION_PLAN.md`。校验内容哈希一致后，新仓库内的副本成为唯一权威版本，旧规划目录只读归档，不再双向同步。

---

## 0. 使用方式和开工条件

### 0.1 默认决策

除非项目负责人明确修改，所有 Agent 采用：

```text
新项目路径：/Users/zhugx/src/skills/dy-fanpai
仓库可见性：初期私有
Python：3.12
包管理：uv，同时保证 pip 可安装
CLI：argparse
数据模型：Pydantic v2
HTTP：requests，同步调用
测试：pytest
格式检查：Ruff
类型检查：Pyright，仅检查 src/dy_fanpai
开发和普通成品平台：macOS
剪映草稿验收：指定 Windows/WSL 机器和指定剪映版本
Live 策略：先 MVP，再 Full
```

MVP Live 包含：A 模式、原音、Seed 反推、即梦生成、final 成品。  
Full Live 再覆盖：双反推、产品迁移、B 模式、群戏、TTS/换声、Ark、小云雀和剪映草稿。

WP0 的启动步骤创建新项目目录和本地 Git 仓库，使基线文档与 fixtures 有明确落点；WP1 负责工程骨架。创建远端仓库、推送或设置公开可见性属于额外外部操作，必须由项目负责人明确授权。

首次提交前必须由项目负责人提供 Git `user.name` 和 `user.email`，推荐只配置在新仓库本地，不要求修改全局身份。

负责人可在 WP0 完成前修改默认值；WP1 开始后，技术选择和公共接口变更必须走变更流程。

### 0.2 当前环境事实

截至本方案生成时：

```text
原项目 HEAD：ffc22e34cb35477b04967163c3932002ed4f3fed
ffmpeg/ffprobe：可用
Python 3.12.13：已由 uv 安装，路径 `/Users/zhugx/.local/share/uv/python/cpython-3.12-macos-aarch64-none/bin/python3.12`
即梦 CLI：未安装/未登录
ARK_API_KEY：未配置
Kimi：未配置
小云雀：未配置
CosyVoice：未安装
Seed-VC：未安装
pyJianYingDraft：未安装
Git user.name / user.email：未配置
原项目未跟踪目录：.workbuddy/，保留且不纳入工作
```

WP0 可以在这些外部能力缺失时进行。WP1 使用已安装的 Python 3.12.13 创建项目环境；如果 uv 缓存目录受沙箱权限限制，应使用项目可写缓存或申请窄范围权限，不得静默改用系统 Python 3.14。真实 Live 前必须重新运行 doctor，并准备相应凭证和环境。

### 0.3 开工角色

必须指定一名 Integrator。未另行指定时，发起整个项目的主 Agent 即为 Integrator。

Integrator 负责：

- 维护本方案和新项目 `ACCEPTANCE.md`；
- 冻结公共模型、Provider 接口和工作区 schema；
- 分配工作包和文件所有权；
- 审核各 Agent 的测试证据；
- 合并工作包并运行全量测试；
- 批准或拒绝公共接口变更；
- 只有在最终验收门全部满足时宣布完成。

### 0.4 四个时间点的 Go 条件

派发 WP0：原项目路径和基线可读，确认只读，不调用真实 API。  
开始 WP1：WP0 交付完整，Python 3.12 项目环境可创建，默认决策已确认，Integrator 已冻结公共接口。  
开始 Live：凭证、合法测试素材、预算、Provider Mock、并发/崩溃恢复测试全部就绪。  
宣布替代：第 13 节十二组最终验收全部通过。

### 0.5 用户需要提供或确认的外部输入

这些内容不要求在 WP0 前全部提供，但必须在对应 Live 验收前齐全：

- 六类合法测试视频：A、产品迁移、B、群戏、旁白、纯产品；
- 对应产品图、人物锚图和真实产品事实；
- 人脸、声音和参考视频的使用授权；
- Ark、Kimi、即梦、小云雀的可用账号和预算；
- 合法目标音色，以及 CosyVoice/Seed-VC 环境；
- 私有千川方法论包，若要求完整验收原作者 B 模式方法论；
- Windows/WSL 剪映验收机器、剪映版本和草稿目录。

缺少某项时可以继续开发和 Mock，但相应功能只能标记“实现完成，外部验收未完成”。

### 0.6 Live 预算规则

未给出具体金额时，默认规则为：

- 所有 Live 默认关闭；
- 每次审批只允许一个 Provider、一个段、一次提交；
- 评委每轮最多一次；
- 扩大段数或重试必须重新审批；
- 代码硬执行 `max_submits`；
- 所有 usage 和任务 ID 写入 `run.json`。

项目负责人可以在 `ACCEPTANCE.md` 中填写更严格的总预算，但 Agent 不得自行扩大。

### 0.7 事实来源和许可证

执行时的事实优先级：

1. 原项目固定提交中的实际代码和样例，用于判断既有行为；
2. 原项目 `DESIGN.md`、`SKILL.md`、`README.md`，用于理解业务理由和操作边界；
3. 本文件，用于决定新架构、工作包、流程和验收；
4. Agent 推测只能作为待验证假设，不能覆盖以上事实。

新项目独立运行，但不是脱离原项目凭空重写。Agent 必须读取对应原实现并建立 parity 证据。

原项目采用 MIT License。若复用代码、Prompt 或样例，必须保留原许可证和必要的版权/来源说明；私有音色、私有千川资料和用户素材不得因为代码许可证而被视为可公开分发。

### 0.8 配置和依赖契约

配置读取顺序：进程环境变量 → `~/.config/dy-fanpai/` 用户配置 → 项目非敏感配置 → 默认值。第一版不强制加载 `.env`；若以后支持，必须默认忽略且不得把真实密钥写进仓库。

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

Live 开关和批准记录进入 `run.json`，不依赖一个可被误设的全局环境变量。日志必须脱敏；测试必须清除真实密钥并使用假值。

依赖保持最小：

```text
core：pydantic>=2、requests
dev：pytest、responses、ruff、pyright
CLI：标准库 argparse，不安装 click/typer
HTTP：requests，不同时引入 httpx/respx
jianying：可选独立环境，不进入 core
```

pytest 自带 `monkeypatch` fixture，不增加名为 `pytest-monkeypatch` 的依赖。外部工具和私有资源状态写入 doctor 报告及 `run.json`，不再单独引入 `external-prerequisites.json`，避免与单清单设计冲突。

---

## 1. 目标

新建一个独立的抖音带货视频翻拍项目：

- 不修改、不依赖原项目运行；
- 架构和目录清晰；
- 覆盖原项目全部已实现能力；
- 支持 Agent Skill 和 CLI；
- 支持人审、费用控制、断点续跑和失败恢复；
- 支持中性母版、字幕成品和剪映草稿交付；
- 用测试和真实 Pilot 证明效果，不以“代码完成”代替验收。

不要求兼容原项目脚本名、导入路径、CLI 参数和默认目录。

项目命名统一为：

```text
仓库/目录：dy-fanpai
Python 包：dy_fanpai
CLI：dy-fanpai
中文名：抖音翻拍
配置目录：~/.config/dy-fanpai/
项目环境变量前缀：DY_FANPAI_
```

`dy` 只表示面向抖音带货内容生产。第一版不包含视频下载、自动发布、自动互动或抖店经营操作。

---

## 2. 不能精简掉的五条底线

1. 反推中的主体、动作和关键颜色必须完整进入生成提示词。
2. 计划必须人工审核后才能生成。
3. 真实提交必须有段 ID、后端和最大提交次数审批。
4. 已有远端任务必须优先恢复，不能直接重复提交扣费。
5. 技术检查通过不能替代人物、商品、包装、动作和口型人工审核。

此外：

- 人脸、声音、视频和商品素材上传第三方前必须确认权利与隐私；
- 人物口播走即梦，纯产品 i2v 才允许 Ark/小云雀；
- `FULL.mp4` 始终保持无字幕、无 BGM；
- 全部付费 Live 测试默认关闭。

---

## 3. 精简后的目录

目标控制在约 20～25 个主要 Python 文件，不为每个小概念单建模块。

```text
dy-fanpai/
├── README.md
├── SKILL.md
├── pyproject.toml
├── LICENSE
├── .gitignore
├── docs/
│   ├── EXECUTION_PLAN.md
│   ├── DESIGN.md
│   ├── ACCEPTANCE.md
│   ├── CHANGELOG.md
│   └── ...
├── src/
│   └── dy_fanpai/
│       ├── __init__.py
│       ├── cli.py
│       ├── models.py
│       ├── config.py
│       ├── workspace.py
│       ├── workflow.py
│       ├── reverse/
│       │   ├── seed.py
│       │   ├── kimi.py
│       │   └── merge.py
│       ├── planning/
│       │   ├── planner.py
│       │   └── localization.py
│       ├── audio/
│       │   ├── service.py
│       │   └── voice.py
│       ├── generation/
│       │   ├── service.py
│       │   ├── dreamina.py
│       │   ├── ark.py
│       │   └── xyq.py
│       ├── media/
│       │   ├── ffmpeg.py
│       │   └── download.py
│       ├── quality/
│       │   ├── qc.py
│       │   └── judge.py
│       └── delivery/
│           ├── final.py
│           └── jianying.py
├── resources/
│   ├── prompts/
│   ├── schemas/
│   └── examples/
└── tests/
    ├── fixtures/
    ├── unit/
    ├── integration/
    ├── parity/
    └── live/
```

### 合并原则

- 数据模型集中在 `models.py`，暂不拆成多个 domain 文件；
- 状态、闸口和流程集中在 `workflow.py`；
- 路径、锁、产物登记集中在 `workspace.py`；
- 产品素材清单、分段、路由、Prompt 和群戏规则集中在 `planner.py`；
- 原音、TTS、timing 集中在 `audio/service.py`；
- 媒体探测、切分、抽帧、归一化和拼接集中在 `media/ffmpeg.py`；
- 字幕和烧字幕成品集中在 `delivery/final.py`；
- 不设置万能 Provider，不抹平不同后端能力。

当单个文件超过约 500 行或出现两个独立变化原因时再拆分，不提前设计深层目录。

---

## 4. 一个运行清单代替多份状态文件

每个任务使用一个主清单 `run.json`，集中保存：

```text
schema_version
project_id
current_stage
source video and hash
rights confirmation
configuration snapshot
stage results
approvals
artifacts
provenance
cost ledger
remote uploads
errors
```

生成任务数量较多，单独保存：

```text
generation/tasks/S1.json
generation/tasks/S2.json
```

锁文件为临时运行文件：

```text
.dy-fanpai.lock
```

这样不再分别维护 state、rights、provenance、cost、artifact 等多份容易不一致的 JSON。

### 工作区布局

```text
runs/demo/
├── run.json
├── inputs/
│   ├── source.mp4
│   ├── assets.json
│   └── assets/
├── reverse/
│   ├── seed.json
│   ├── kimi.json
│   ├── dossier.md
│   ├── frames/
│   └── shotlist.json
├── planning/
│   ├── required-assets.json
│   ├── segments.json
│   └── segments.md
├── audio/
│   ├── segments/
│   └── timing.json
├── generation/
│   ├── tasks/
│   └── clips/
├── qc/
└── output/
    ├── FULL.mp4
    ├── FULL.srt
    ├── onscreen-text.md
    └── FINAL.mp4
```

---

## 5. 七阶段流程

状态只保留：

```text
created
ready
reversed
planned
approved
audio_ready
generating
assembled
qc_passed
delivered
failed
```

权利确认、计划审核和费用批准是 `run.json` 中的闸口记录，不再各自变成状态。

### P0 准备

包含：doctor、创建工作区、复制源视频、ffprobe、哈希、磁盘空间检查、权利与隐私确认。

输出：`run.json`、`inputs/source.mp4`。

停止条件：

- ffmpeg/ffprobe 缺失；
- 没有 Ark 反推能力；
- 用户未确认参考视频、人脸、声音和商品素材的使用权限；
- 磁盘空间明显不足。

### P1 反推

默认 Seed 单反推，可选 Seed + Kimi 双反推。

输出：最终 `reverse/shotlist.json`。双反推还输出 dossier 和差异帧。

保留规则：

- 两条腿使用同一组硬切；
- Seed 负责实体基底，Kimi 主要补充时序和运镜；
- 互斥信息看原片帧；
- 静音贴字不能进入台词；
- Kimi 上传文件能删除时必须删除并记录。

### P2 规划与审核

一次完成：

- 产品素材需求清单；
- 产品锚图路由；
- 硬切分段；
- Prompt；
- 动作完备性检查；
- 群戏角色和人数约束；
- 可选 B 模式台词修改；
- `segments.md` 人工审核稿。

只有显式执行计划批准后才能进入下一阶段。

### P3 音频

三选一：

- 原片切音频；
- TTS；
- Seed-VC 换声。

统一输出逐段 WAV 和 `timing.json`。

保留规则：

- 即梦音频不得短于 2 秒；
- 只垫到 2 秒，不垫满计划时长；
- TTS 台词与口播 Prompt 必须逐字一致；
- 换声前检查参考音频质量和授权。

### P4 生成

生成前审批内容：

```text
segments
provider
max_submits
```

规则：

- `max_submits` 由代码硬执行；
- 默认先批 S1 一段；
- 人物和口播走即梦；
- 纯产品 i2v 可选即梦、Ark、小云雀；
- 同一工作区加锁；
- 每段提交前写提交意图；
- 有 task ID 优先查询和下载；
- 下载后做 ffmpeg 解码检查；
- 单段失败不带崩整批，但状态必须显示部分失败；
- usage 和费用写入 `run.json`。

### P5 装配与质检

一次完成：

- 逐段归一化；
- 拼接 `FULL.mp4`；
- 完整解码检查；
- 分辨率、音轨、时长和顺序检查；
- 口型证据包；
- 原片与成片双视频评委；
- 人工审核记录。

人工审核分开记录：人物、商品、包装文字、动作、口型、内容合规。

双视频评委默认沿用原项目的 Ark Responses API 和 `ARK_SEED_MODEL`，一次输入原片与成片，关闭 thinking 并使用流式输出。WP0 必须冻结原评委 Prompt、上传预算和压缩逻辑；更换评委后端属于显式设计变更，不是未定义缺口。

### P6 交付与清理

支持：

- SRT；
- 屏上贴字清单；
- 烧字幕和可选 BGM 成品；
- 剪映五轨草稿；
- 临时文件清理 dry-run。

禁止默认覆盖剪映草稿；禁止清理源视频、最终成品、任务 ID、费用和验收记录。

---

## 6. 四个明确闸口

只保留真正需要用户决策的四处暂停：

### G1 权利与隐私

确认参考视频、人物肖像、声音、商品素材可使用，并知道素材会上传哪些 Provider。

### G2 计划审核

确认分段、动作、锚图、台词、前三秒、包装和合规信息。

### G3 费用审批

确认段 ID、Provider 和最大提交次数。

### G4 最终人工 QC

确认人物、商品身份、包装、动作和口型，技术通过不能自动越过。

`dy-fanpai run` 遇到任一闸口立即停止。

---

## 7. CLI 精简为八组命令

```bash
dy-fanpai doctor
dy-fanpai new --video target.mp4 --workspace runs/demo
dy-fanpai status runs/demo
dy-fanpai run runs/demo
dy-fanpai approve runs/demo rights
dy-fanpai approve runs/demo plan
dy-fanpai approve runs/demo generation --segments S1 --provider dreamina --max-submits 1
dy-fanpai approve runs/demo qc
dy-fanpai retry runs/demo [--segments S1,S2]
dy-fanpai deliver runs/demo --mode final|jianying|both
dy-fanpai clean runs/demo --dry-run
```

这里按“命令组”计为八类：doctor、new、status、run、approve、retry、deliver、clean。

高级调试不再为每个阶段增加顶层命令，统一使用：

```bash
dy-fanpai run runs/demo --stage reverse
dy-fanpai run runs/demo --stage planning
```

---

## 8. Agent Skill

根目录 `SKILL.md` 负责：

- 识别“抖音翻拍、带货视频复刻、用我的产品重做”等请求；
- 收集参考视频和产品素材；
- 运行 `status` 和 `run`；
- 在四个闸口暂停；
- 不自动安装重型依赖；
- 不自动使用真实密钥做测试；
- 不自动扩大生成段数和费用上限；
- 恢复已有任务时先查询 task ID。

Skill 只调用 CLI，不复制 Python 业务逻辑。

项目仓库是 Skill 源。不得未经确认把安装路径硬编码为 WorkBuddy、Codex 或 Claude Code 的用户目录。WP6 由 Integrator 选择至少一个实际目标宿主，记录其安装/注册方式，并在全新会话验证：发现、触发、暂停、批准后恢复。其他宿主未实测时只提供通用 `SKILL.md`，不宣称已验证。

---

## 9. 功能范围

必须覆盖：

- A 模式原产品原台词；
- 产品迁移；
- B 模式事实包台词改写；
- 多人群戏；
- 全片旁白；
- 纯产品视频；
- Seed 单反推；
- Seed + Kimi 双反推；
- 原音、TTS、Seed-VC；
- 即梦人物口播；
- 即梦、Ark、小云雀纯产品 i2v；
- 单段 Pilot、批量生成、断点续跑；
- 坏流重下；
- 装配、字幕、BGM、评委、口型 QC；
- 最终成品和剪映草稿。

外部限制：

- 没有私有千川资料时，只能验收普通事实型台词改写，不能宣称完整复现原作者 B 模式方法论；
- 没有合法音色和 Seed-VC/CosyVoice 环境时，不能宣称换声/TTS Live 验收完成；
- Provider、模型和剪映版本必须实机验证。

---

## 10. 测试只分五类

### T1 单元与契约

模型、配置、状态、锁、路由、分段、动作完备性、字幕、timing、路径和 Provider 请求。

### T2 原项目对照

对确定性产物做规范化后比较：素材清单、segments、Prompt 关键约束、本地化结果、字幕和 timing。

### T3 媒体集成

使用合成小视频验证：切音频、2 秒闸、抽帧、归一化、拼接、补静音、烧字幕、BGM 和完整解码。

### T4 Provider Mock 与恢复

验证请求参数、直连、重试、任务保存、崩溃恢复、并发锁、`max_submits` 和坏流重下。

### T5 受控 Live 与实机

默认跳过。按一段一个 Provider 的方式验证反推、生成、评委和剪映草稿。

Fixtures 至少覆盖：

- A、产品迁移、B、群戏、旁白、纯产品；
- 短音频、缺锚图、坏流、已有未完成 task。

---

## 11. 七个 Agent 工作包

### WP0 基线

启动步骤：创建 `/Users/zhugx/src/skills/dy-fanpai`、执行本地 `git init`、复制本文件为根目录 `EXECUTION_PLAN.md` 并校验哈希；首次提交前等待项目负责人提供 repo-local Git 身份。随后只读原项目，产出：

- `original-baseline.md`：提交、tracked diff、未跟踪项、Python/ffmpeg 环境；
- `feature-inventory.md`：每个原脚本/函数对应的能力、输入、输出、外部依赖、失败和恢复行为；
- `artifacts.md`：shotlist、segments、timing、task/meta、dossier、QC、judge、字幕、FULL、FINAL、剪映草稿；
- `behavior-baseline.md`：硬切、时长、Prompt 固定约束、路由、2秒闸、重试、解码、拼接和字幕优先级；
- `provider-matrix.md`：模型、端点、政策限制、最后验证日期和 experimental 项；
- `tests/fixtures/original/`：公开样例、确定性黄金结果和负向样例；
- `ACCEPTANCE.md` 初稿：原能力到新能力的逐项映射和验收方式。

WP0 还必须从原实现提取具体阈值：输出比例/分辨率、帧率处理、编码、允许时长误差、音频下限、单段时长上限、硬切数量和解码通过条件。不能让后续 Agent 自己猜。

不得写新业务代码。

WP0 验收标准：21 个原脚本无未归类项；所有隐藏产物已登记；确定性样例可以重复生成；没有复制密钥、私有音色或付费资料。

### WP1 骨架与核心

负责：

- pyproject、README、SKILL、DESIGN、LICENSE、CHANGELOG 和忽略规则；
- `models.py`、`config.py`、`workspace.py`、`workflow.py`；
- `run.json`、锁、闸口、费用上限；
- CLI 骨架；
- 干净虚拟环境安装。

WP1 完成后冻结公共模型和服务接口。

冻结项至少包括：`run.json` v1 schema、工作区目录、七阶段流程、四个闸口、Provider 最小接口、公共错误类型、fixture 命名和文件所有权。冻结结果写入 `DESIGN.md` 和 `CHANGELOG.md`。

### WP2 反推与规划

负责：

- Seed、Kimi、双反推合并；
- 素材需求；
- 分段、路由、Prompt、完备性；
- 群戏；
- 本地化。

验收：原项目确定性样例 parity，无关键动作丢失。

### WP3 音频与媒体

负责：

- ffmpeg/ffprobe 基础能力；
- 原音切段、2 秒闸、timing；
- TTS 和 Seed-VC adapter；
- 归一化、拼接、解码检查、字幕基础。

验收：合成媒体离线全通过。

### WP4 视频生成

负责：

- 即梦、Ark、小云雀；
- 人物/产品路由；
- task 文件、查询、恢复、下载；
- 重试、坏流重下；
- 锁、提交意图、费用硬上限。

验收：先完成全部 Mock；未经审批不得 Live。

### WP5 质检与交付

负责：

- FULL 母版；
- 技术 QC、口型证据、双视频评委；
- SRT、贴字、烧字幕、BGM；
- 剪映草稿；
- 清理 dry-run。

验收：技术状态与人工状态分离；剪映真实打开一次。

### WP6 集成与发布

负责：

- 完整 CLI 和 Skill；
- 五类测试；
- 六类场景验收；
- 受控 Live Pilot；
- 干净环境安装；
- 最终发布审计。

只有 WP6 可以宣布可替代原项目。

### 执行顺序

```text
WP0 → WP1 → ┬→ WP2 ─┐
            ├→ WP3 ─┼→ WP5 → WP6
            └→ WP4 ─┘
```

WP2、WP3、WP4 可以并行，但必须在 WP1 冻结接口之后开始。

---

## 12. Agent 通用指令

```text
你正在执行《抖音 dy-fanpai 精简执行方案》的 <工作包>。

原项目 /Users/zhugx/src/daihuo-fanpai 只读。
新项目 /Users/zhugx/src/skills/dy-fanpai 独立实现。

要求：
1. 只修改本工作包拥有的文件。
2. 不真实调用付费 API，除非任务明确包含已批准 Live Pilot。
3. 不删除原项目已经验证有效的业务规则。
4. 每个确定性行为必须有测试。
5. 不用“测试通过”之外的完成声明代替证据。
6. 完成时报告修改文件、测试命令、结果、未覆盖项、风险和下一接口。
7. 遇到公共接口不够用，先提出变更，不自行复制另一工作包逻辑。
```

### 12.1 工作包完成报告

每个 Agent 必须按以下格式交付：

```text
工作包：WPx
状态：完成 | 部分完成 | 阻塞
修改文件：
实现能力：
执行测试：
测试结果：
未运行的测试及原因：
是否调用真实服务及费用：
已知限制：
公共接口变化：
下一工作包需要的输入：
```

“部分完成”和“外部验收未完成”不得写成完成。

### 12.2 公共接口变更

WP1 冻结后，任何 Agent 若要修改 `models.py`、`run.json` schema、Provider 接口、工作区路径或 CLI 顶层语义，必须先提交：

```text
变更原因
受影响工作包
旧行为
新行为
迁移或 fixture 更新
Integrator 决定
```

未经批准不得各自复制模型或增加第二套状态文件。

### 12.3 集成检查点

每个工作包合并前必须：

- 查看原项目 tracked diff，确保未修改；
- 运行本工作包测试；
- 运行已有全量默认测试；
- 更新 `ACCEPTANCE.md` 对应行；
- 记录未验的 Live/实机项；
- 由 Integrator 判断是否允许进入下一阶段。

---

## 13. 最终验收门

只保留十二组必须通过的结果：

1. 原项目工作区未修改；
2. wheel/sdist 在干净环境安装，CLI 和 Skill 可用；
3. 六类场景都有 fixture 和验收记录；
4. 确定性产物与原项目无未解释差异；
5. 四个闸口不能被 `run` 或 `--force` 绕过；
6. 并发和崩溃测试证明不会静默重复提交；
7. 反推、三种视频后端、音频路径按声明范围完成 Mock 和 Live；
8. FULL 母版、字幕成品和剪映草稿通过技术检查；
9. 人物、商品、包装、动作、口型和合规完成人工审核；
10. 费用、任务 ID、模型/CLI/ffmpeg 版本和远端上传可追溯；
11. 私有方法论、合法音色或外部服务缺失时有明确降级，未虚报完整；
12. `ACCEPTANCE.md` 没有无说明的空白功能项。

全部通过后，可以认定新项目达到预期并替代原项目；任一 Live 或实机项未完成，只能标记“实现完成，外部验收未完成”。

---

## 14. 第一条派发指令

```text
请执行《抖音 dy-fanpai 精简执行方案》WP0：基线。
原项目 /Users/zhugx/src/daihuo-fanpai 只读。
新项目目标路径 /Users/zhugx/src/skills/dy-fanpai。
本阶段不写新业务代码、不接 API、不消耗额度。
按本方案 WP0 要求产出 original-baseline.md、feature-inventory.md、artifacts.md、behavior-baseline.md、provider-matrix.md、确定性 fixtures 和 ACCEPTANCE.md 初稿，并提供逐项验证证据。
```

WP0 验收通过后再派发 WP1。
