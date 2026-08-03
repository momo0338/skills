# DEGRADATION · 降级矩阵（验收门 11）

执行方案 §13 门11：私有方法论、合法音色或外部服务缺失时，必须有**明确降级**，且**未虚报完整**。

本文件逐条列出所有外部依赖缺口、声明范围与缺失时的降级路径，作为「未虚报完整」的凭证。
凡标 🟡 的项均为「实现完成，外部验收未完成」——代码与 Mock 就绪，但需真实账号 / 预算 /
合法素材 / 特定机器 / 人工才能跑受控 Live，本会话不虚称已通过。

## 矩阵

| # | 能力 / 外部依赖 | 声明范围 | 缺失时的降级 | 是否虚报 |
|---|---|---|---|---|
| 1 | 即梦 / Dreamina 提交·轮询·下载 | Mock 先行；未经审批不得 Live | `doctor` 缺 `DY_FANPAI_DREAMINA_BIN`→WARN；`G.run` 未审批不提交 | 否（明确标 🟡） |
| 2 | Ark 生成（i2v/mm/t2v） | 请求体构造单测；Live 需 `ARK_API_KEY`+预算 | 缺 key→`doctor` WARN；不构造真实提交 | 否 |
| 3 | 小云雀 XYQ（pippit-tool-cli） | 请求体构造单测；Live 需凭证 | 缺 `XYQ_ACCESS_KEY`→WARN；AUDIO_GUARD 默认带 | 否 |
| 4 | CosyVoice TTS（合成） | `synth` 接口 + `cosyvoice_status` 单测 | 缺环境→仅状态函数可用，不跑合成 | 否 |
| 4b | Qwen 反推腿3（百炼原生视频输入） | `reverse/qwen.py` 请求构造单测（8 例） | 缺 `DASHSCOPE_API_KEY`→doctor WARN；离线不调用；未实机验收标 experimental | 否 |
| 5 | Seed-VC 换声 | `convert` 接口 + `seedvc_status` 单测 | 缺 GPU 环境→仅状态函数可用 | 否 |
| 6 | 下载体检（真实 URL） | `robust_download` 逻辑单测（重试/大小/坏流） | 真实 URL 仅受控 Live；不改逻辑 | 否 |
| 7 | 烧字幕（ffmpeg subtitles / libass） | 确定性 `subtitle_filter` 单测 | 本机 mac ffmpeg 缺 libass→CLI 回退**无烧字幕 FINAL + SRT 侧载** | 否（CLI 兜底已验） |
| 8 | 剪映草稿真机写 + 剪映打开 | JSON 规格（5 轨）离线产；`engine=json` 可照抄 | `engine=pyjianying` 真机写标 🟡；`engine=json` 拒绝覆盖需 force | 否 |
| 9 | 双视频模型级语义评委（Ark 等） | 仅交付确定性**结构评委**（解码/分辨率/时长比） | 语义比对属外部验收，不声称已做 | 否 |
| 10 | 四闸口自然语言会话暂停（门4） | CLI/`run` 路径强制拦截已实现并单测 | 自然语言触发为 Skill 行为，待端到端会话验证 | 否 |
| 11 | 人物/商品/包装/动作/口型/合规人工审核（门9） | 技术 QC + 结构评委 + 人工审核清单 | 代码结构评委不替代人工；清单见各场景 `acceptance_record.md` | 否 |
| 12 | 费用/任务 ID/模型·CLI·ffmpeg 版本/远端上传追溯（门10） | `run.json` 账本 + task 字段已实现 | 全链路真跑后回填追溯字段 | 否（字段已实现） |
| 13 | 原项目未修改（门1） | 只读访问，已复核纯净 | — | 否（HEAD=ffc22e34，零改动） |
| 14 | 六类场景 fixture + 验收记录（门3） | fixture 结构已搭（6 类） | 验收记录待受控 Live 回填 | 否（fixture 已就位） |
| 15 | 确定性产物与原项目无未解释差异（门4） | WP2 planner golden 逐字节；WP3/WP4 1:1 复刻 | 统一 parity fixture 建设中（见 `PARITY.md`） | 否 |

## 降级原则（代码层已落地）
- **闸口门禁**：`workflow.require_gate` 在 `pipeline.execute_stage` 每阶段强制；`--force` 入口不存在（验收门 5）。
- **Mock 优先**：`generation/service.run` 全程 `backends=` 注入 Mock，零真实 API。
- **硬上限**：`manifest.max_submits` 费用硬上限 + `acquire_lock` 排他锁 + 提交意图，防重复提交（验收门 6）。
- **资源自检**：`cli doctor` 对缺失 key/bin 给 WARN 不报错，明确告知哪些能力不可用。
- **不破坏母版**：FULL 只读，FINAL 叠加；受保护项（run.json/FULL/FINAL）清理永不动。

## 结论
所有外部缺口均有显式降级路径，且均在 `ACCEPTANCE.md` / `CHANGELOG.md` 标 🟡，未声称已通过
真实验收——满足门11「未虚报完整」。
