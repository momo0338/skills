# LIVE_PREREQUISITES · 受控 Live 前置清单（验收门 3/7/8/9/10）

> 版本：1.0  日期：2026-08-03
> 配套：`EXECUTION_PLAN.md` §0.5（用户外部输入）、§0.6（Live 预算规则）、§11 WP6；
> `ACCEPTANCE.md` 未验 Live 项汇总；`DEGRADATION.md` 降级矩阵。
> 原则：**Live 默认关闭；每次审批只允许一个 Provider、一个段、一次提交；`
> `代码硬执行 max_submits；未批准只能跑 Mock/dry-run。`**

## 0. 为什么需要这份清单

项目代码与 Mock 已全部就绪（204 passed / 1 skipped，离线全绿），剩余 12 个最终验收门中的
**5 个**（门 3 验收记录、门 7 真实 Provider、门 8 剪映真机、门 9 人工审核、门 10 全链路追溯）
以及「四闸口全新会话自然语言暂停」验证，都需要**真实账号、预算、合法素材、特定机器或人工**。
本清单把这些外部前置按「凭证→素材→环境→执行」四层拆开，每项给出：状态、提供方式、对应验收门。

---

## 1. 前置总览（四层）

| 层 | 内容 | 阻塞的验收门 | 能否离线替代 |
|---|---|---|---|
| L1 凭证与预算 | 即梦/Ark/小云雀/Kimi 账号+key+预算 | 门 7 | 否（doctor WARN，可 Mock） |
| L2 素材与授权 | 六类合法视频、产品图/锚图/事实、人脸/声音授权 | 门 3/7/9 | 否（六类 fixture 已有合成版，真验需真实素材） |
| L3 环境 | 剪映 Windows/WSL、pyJianYingDraft、CosyVoice、Seed-VC、libass ffmpeg | 门 8 | 部分（代码已就绪） |
| L4 执行与验收 | 受控 Live Pilot 流程、人工审核清单、追溯回填 | 门 3/9/10 | 否 |

---

## 2. L1 凭证与预算（先决，其余基本都等它）

> 配置位置：进程环境变量 或 `~/.config/dy-fanpai/<name>`（`config.py` `_read`）。
> 密钥不入仓库、不入日志、不入 fixtures。doctor 会 WARN 但不阻塞。

| # | 项目 | 环境变量 / 配置键 | 状态 | 需要提供 |
|---|---|---|---|---|
| L1-1 | 即梦 CLI 登录 | `DY_FANPAI_DREAMINA_BIN`（默认 `~/.local/bin/dreamina`） | 未安装/未登录 | 安装即梦 CLI 并完成登录（网页扫码）；确认积分池额度 |
| L1-2 | Ark（反推 Seed + 评委 + 生成） | `ARK_API_KEY`（生成模型另可 `DY_FANPAI_ARK_GEN_MODEL`） | 未配置 | 火山方舟 API key，开通 Seed 反推模型 `doubao-seed-2-1-pro-260628` 与生成模型 `doubao-seedance-2-0-260128`，确认区域与计费 |
| L1-3 | Kimi K3（双反推腿2） | `KIMI_API_KEY` / `MOONSHOT_API_KEY`、`KIMI_BASE_URL`、`KIMI_K3_MODEL` | 未配置 | Moonshot API key，开通 K3 模型 |
| L1-4 | 小云雀 XYQ（纯产品 i2v） | `XYQ_ACCESS_KEY`、`XYQ_VIDEO_MODEL` | 未配置 | pippit-tool-cli 已装，补 `XYQ_ACCESS_KEY`（credits 池） |
| L1-5 | 预算与审批 | `run.json` 审批记录 + `max_submits` | 未开始 | 每轮 Live 前在 `approve generation` 写明：段数、段 ID、后端、硬上限 |

**验证命令**：`dy-fanpai doctor`（应无 WARN）→ `dy-fanpai new --video <合法视频> --workspace runs/<scene>` → `dy-fanpai status runs/<scene>`。

---

## 3. L2 素材与授权（六类场景真验用）

> 六类 = A（标准口播）、产品迁移、B（无 hero 纯运镜口播）、群戏、旁白、纯产品。
> fixture 合成输入已在 `tests/fixtures/scenarios/<scene>/`，真验需**真实视频+真实产品资料**替换。

| # | 素材 | 用途 | 状态 | 需要提供 |
|---|---|---|---|---|
| L2-1 | 六类合法测试视频（mp4/mov，竖屏） | 反推/切段/质检比对输入 | 缺 | 每类 1 支，须有权使用（自产或授权） |
| L2-2 | 产品图（hero/hero_alt/包装/内包装/单根…） | 即梦/Ark/小云雀锚图 | 缺 | 与视频同品，清晰无遮挡 |
| L2-3 | 主播锚图 + 主播描述 | 口播段跨段一致 | 缺 | 与视频同人，授权肖像使用 |
| L2-4 | 产品事实（价格/活动/赠品/卖点） | 本地化台词、B 模式 | 缺 | 真实可核，禁止编造（方案 §S07） |
| L2-5 | 人脸/声音/视频上传授权 | S01.5 权利闸 | 缺 | 明确允许上传到哪些 Provider，写入 `rights-and-consent` |

**注意**：真实素材一律放 `runs/<scene>/inputs/`，**不入 Git**（`.gitignore` 已忽略 `runs/`、`*.mp4` 等）。

---

## 4. L3 环境（门 8 剪映 + TTS/换声 + 烧字幕）

| # | 环境 | 阻塞的验收门 | 状态 | 需要提供 |
|---|---|---|---|---|
| L3-1 | 剪映 Windows/WSL 验收机 + 目标剪映版本 + 草稿目录 | 门 8（剪映真机打开/编辑/保存） | 缺 | 指定机器、版本、`DY_FANPAI_JY_DRAFTS`、`DY_FANPAI_JY_PYTHON` |
| L3-2 | pyJianYingDraft（剪映草稿引擎） | 门 8 | 未安装 | 在验收机安装兼容版（`pip install pyjianyingdraft`，jianying 可选依赖） |
| L3-3 | CosyVoice（TTS 合成） | 门 7（TTS 路径） | 未安装 | 安装 `~/CosyVoice` + 合法目标音色（U5） |
| L3-4 | Seed-VC（换声） | 门 7（换声路径） | 未安装 | GPU 环境 + `~/seed-vc` + 合法音色（U5） |
| L3-5 | 带 libass 的 ffmpeg（烧字幕） | 门 8（烧字幕成品） | 本机 macOS 缺 libass | Homebrew 装 `ffmpeg`（含 libass）或指定带 libass 的机器；现有兜底=无烧字幕 FINAL+SRT 侧载 |
| L3-6 | Skill 实机宿主（WorkBuddy 等） | 「四闸口自然语言暂停」验证 | 待定 | 选定至少 1 个宿主，按其官方机制安装/注册 `../SKILL.md`，全新会话验证 |

---

## 5. L4 执行与验收（受控 Live Pilot 流程）

> 严格遵循 `EXECUTION_PLAN.md` §0.6：MVP 先（A 模式+原音+Seed 反推+即梦生成+final），
> Full 再覆盖其余。每轮 `approve generation --segments S1 --provider <x> --max-submits 1`。

| 步骤 | 动作 | 输出/验收 |
|---|---|---|
| 1 | `dy-fanpai doctor` 全绿（密钥/工具就位） | 无 WARN |
| 2 | `dy-fanpai new --video <视频> --workspace runs/<scene>` + `confirm-rights` | `run.json` + `rights-and-consent` |
| 3 | `dy-fanpai run` 到计划闸 → `approve plan` | `segments.md` 人工审核通过 |
| 4 | `dy-fanpai approve generation --segments S1 --provider <x> --max-submits 1` | 费用批准记录 |
| 5 | `dy-fanpai run`（生成 S1 → 装配 → 质检） | clip + FULL 母版 |
| 6 | `dy-fanpai qc` → 双视频评委 + 人工审片 | `qc/` 技术报告 + 人工审核记录（门 9） |
| 7 | `dy-fanpai deliver --mode both` | FINAL + SRT + 剪映草稿（门 8） |
| 8 | 回填 `tests/fixtures/scenarios/<scene>/acceptance_record.md` | 门 3 验收记录 |
| 9 | 核对 `run.json` 费用账本/task ID/版本追溯 | 门 10 |

**每轮 Live 必须保留**：task ID、usage、产物哈希、验收结果（方案 §12.7）。测试类 Live 走
`tests/live/`（默认跳过，环境开关 + 人工批准才运行，每 Provider 最多 1 次提交）。

---

## 6. 当前勾选状态（2026-08-03）

- [x] L1-0 代码/Mock 全部就绪（204 passed / 1 skipped，离线全绿）
- [x] L2-0 六类场景合成 fixture + segments golden（`tests/fixtures/scenarios/`）
- [ ] L1-1 即梦 CLI 安装+登录（缺）
- [ ] L1-2 ARK_API_KEY（缺）
- [ ] L1-3 KIMI_API_KEY（缺）
- [ ] L1-4 XYQ_ACCESS_KEY（缺）
- [ ] L1-5 预算与审批流程（待凭证后启动）
- [ ] L2-1~L2-5 六类真实素材与授权（缺）
- [ ] L3-1/L3-2 剪映 Windows/WSL 验收环境（缺）
- [ ] L3-3/L3-4 CosyVoice/Seed-VC + 合法音色（缺，B 模式/换声 Live 前）
- [ ] L3-5 带 libass 的 ffmpeg（缺；现有兜底可先跑无烧字幕 FINAL）
- [ ] L3-6 Skill 实机宿主选定 + 全新会话验证（缺）
- [ ] L4 受控 Live Pilot 首轮（等 L1 凭证）

---

## 7. 建议的首轮 Live（MVP，最小集）

```
后端：即梦（dreamina）     段数：S1（1 段）      素材：A 类真实视频+产品图+主播锚图
max_submits：1              模式：A 模式 + 原音   评委：Ark Seed（默认后端）
```

MVP 通过后依次扩：产品迁移 / B 模式（需千川包 U4）/ 群戏 / 旁白 / 纯产品 / Ark / 小云雀 /
TTS（L3-3）/ 换声（L3-4）/ 剪映草稿（L3-1/2）。
