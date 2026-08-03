# dy-fanpai 新项目启动准备：差距清单（Gap List）与待办事项（To-Do Checklist）

> 文档版本：v2.0（2026-08-03 刷新）
> 依据文件（均已更新）：`DY_FANPAI_EXECUTION_PLAN.md` v2.2、`DY_FANPAI_PREFLIGHT_CHECKLIST.md` v1.1、`DY_FANPAI_DETAILED_REFERENCE.md` v1.2
> v1.0→v2.0 主要变化：方案更新后，原清单中多处「缺口」已被新版方案明确消化（详见 §0）。

---

## 0. 本次刷新结论（相对 v1.0）

上一轮我列出的多项缺口，已被方案 v2.2 / 清单 v1.1 / 详细参考 v1.2 **直接更正或消化**。新版清单甚至专门写了「更正原差距清单中的错误」。结论：

- **现在唯一会近期阻断提交的硬性事项 = Git 提交身份（user.name / user.email）**（清单 U1）。
- 其余外部事项（Skill 宿主、剪映环境、千川包、音色、真实凭证、远端仓库）**全部可延后到对应 Live / 发布节点**，不阻塞 WP0 / WP1 与离线开发。
- 我上一轮误判/夸大之处已在本文件 §1 逐条订正。

---

## 1. 对我上一轮判断的订正（避免沿用错误结论）

| 上一轮判断 | 新版方案事实 | 处置 |
|---|---|---|
| Python 3.12 未安装 | 已装 `3.12.13`（uv，路径 `/Users/zhugx/.local/share/uv/python/cpython-3.12-macos-aarch64-none/bin/python3.12`） | 缺口关闭；改用 3.12.13，禁用系统 3.14 |
| 评委后端未定义 | 默认沿用原项目 **Ark Responses API + `ARK_SEED_MODEL`**，关闭 thinking、流式；换后端属显式设计变更 | 缺口关闭 |
| Skill 分发方式未定义 | 仓库即 Skill 源；WP6 选真实宿主并验证；**不得硬编码** `~/.workbuddy/skills/` | 缺口关闭，转为 U2（选宿主） |
| 应建 `external-prerequisites.json` | 明确**不单独建**，外部前置状态写入 doctor 报告 + `run.json` | 缺口关闭 |
| 路径不一致（规划目录 vs 新项目路径） | 规划文件可留在独立目录；WP0 把方案复制进仓库根为 `EXECUTION_PLAN.md` 并校验哈希，旧目录只读归档 | 缺口关闭（流程已规定） |
| 详细参考 = WP0–WP12 共 14 个工作包 | 实为 **13 个**（WP0–WP12） | 计数订正 |
| 执行版 = 7 状态 | 实为 **7 阶段 / 11 状态值 / 4 闸口** | 表述订正 |
| 小云雀 CLI 未安装 | `pippit-tool-cli` 已安装，缺的是 **XYQ_ACCESS_KEY 与真实验收** | 细化 |
| 数据库缺连接/凭据 | 第一版**按设计不需要** DB / 远程队列 / `.env` | 维持：非缺口 |
| git 身份为空 = 设计风险 | 方案已规定「首次提交前由负责人提供，仅写仓库本地配置」 | 转为唯一近期阻塞项 U1 |

---

## 2. 当前真实差距清单（Gap List，v2.0）

> 区分三类：**P（近期阻塞）**、**D（延后到 Live/发布）**、**B（由计划本身产出，非外部前置）**。

### P. 近期阻塞项（必须开工前/首次提交前解决）

| 编号 | 缺口 | 必须动作 | 依据 |
|---|---|---|---|
| P1 | **Git 提交身份未配置** | 首次提交前提供 `user.name` / `user.email`，仅写新仓库本地配置（`git config user.name ...` 不带 `--global`） | 清单 U1 / 执行方案 §0.1 |
| P2 | 新项目目录 `/Users/zhugx/src/skills/dy-fanpai` 尚未创建 | WP0 第一步 `mkdir` + `git init` + 复制方案为 `EXECUTION_PLAN.md` 并校验哈希 | 执行方案 §0（开头新增段落）、§11 WP0 |

> P1 只阻塞「首次提交」，不阻塞 WP0 的目录初始化与只读基线分析。P2 是 WP0 自身动作，不算外部缺失。

### D. 延后项（明确不阻塞 WP0/WP1 与离线开发，到对应节点再解决）

| 编号 | 缺口 | 何时需要 | 依据 |
|---|---|---|---|
| D1 | **Skill 实机宿主未选定** | WP6 验收前 | 清单 U2 |
| D2 | **剪映实机环境**（Windows/WSL + 版本 + 草稿目录 + `pyJianYingDraft` 兼容版） | Full Live 前 | 清单 U3 |
| D3 | **私有千川方法论包**（完整 B 模式 parity 必需） | 若要求完整 B 模式 | 清单 U4 |
| D4 | **合法目标音色 + CosyVoice / Seed-VC 隔离环境**（TTS/换声 Live 必需） | TTS/换声 Live 前 | 清单 U5 |
| D5 | **真实服务凭证与素材授权与预算**：Ark / Kimi / 即梦 / 小云雀账号与 key、模型/区域/额度、六类合法视频、产品图/锚图/事实、人脸声音授权、本轮预算 | 各自 Live Pilot 前逐项提供 | 清单 U6 |
| D6 | **远端仓库创建与可见性**（GitHub/GitLab） | 仅当需要协作/发布时，须用户明确授权 | 清单 U7 |

### B. 由计划本身产出的交付物（不是「缺失的外部前置」，而是 WP 要建的东西）

归于此类的，是我上一轮误列为「缺失组件」的工程内容，现明确它们是**项目目标产出**，不属于「开工前必须预先准备的事项」：

- 全部业务代码 `src/dy_fanpai/`（WP1–WP5 建）
- 工程文件：`pyproject.toml`、`.gitignore`、`README.md`、`SKILL.md`、`DESIGN.md`、`ACCEPTANCE.md`、`CHANGELOG.md`、`LICENSE`（WP1 建）
- `run.json` v1 schema、工作区布局、Provider 最小接口（WP0 冻结草案，WP1 落地）
- 依赖与包管理：core/dev/jianying 分层；`uv` 已装 ✓；pytest + `responses`；Ruff + Pyright（WP1）
- 配置加载与密钥安全：config 读取顺序（进程环境 → `~/.config/dy-fanpai/` → 项目配置 → 默认）；日志脱敏；测试清真实变量（WP1 实现）
- 测试 fixtures 与六类场景（WP0 起建）
- wheel/sdist 干净安装（WP6）

### 仍然确认的「非缺口」项

- **数据库 / 远程任务队列 / `.env`**：第一版设计明确排除（执行方案 §1.3 非目标、§0.8；详细参考 §3、§11.1）。**无需数据库连接与凭据**。
- **原项目（只读参考）**：真实存在，HEAD=`ffc22e34…` 与基线一致，可读 ✅。

---

## 3. 待办准备事项（To-Do Checklist，v2.0）

### 阶段 0：唯一近期阻塞（P 类）
- [ ] **P1** 提供 Git `user.name` / `user.email`（仓库本地配置，不碰全局）。
- [ ] **P2** WP0 创建 `/Users/zhugx/src/skills/dy-fanpai`、`git init`、复制方案为根 `EXECUTION_PLAN.md` 并校验哈希。

### 阶段 1：WP0 可立即启动（无需等待 D 类）
- [ ] 原项目 HEAD 仍为 `ffc22e34…`、只读、不碰 `.workbuddy/`（已满足 ✓）。
- [ ] 不调用真实 API、不装重型依赖（默认 ✓）。
- [ ] 默认决策已冻结：路径、技术选型（Python 3.12.13 / uv / argparse / Pydantic v2 / requests / pytest+responses / Ruff+Pyright）、Integrator=主 Agent、MVP→Full Live（默认生效，无需逐项确认 ✓）。
- [ ] 产出 `original-baseline.md`、`feature-inventory.md`、`artifacts.md`、`behavior-baseline.md`、`provider-matrix.md`、六类 fixtures、`ACCEPTANCE.md` 初稿。

### 阶段 2：WP1 编码前冻结门
- [ ] WP0 验收通过。
- [ ] 冻结 `run.json` v1、7 阶段 / 11 状态值 / 4 闸口、Provider 接口、公共错误、fixture 命名、文件所有权。
- [ ] `pyproject.toml` 遵守最小依赖合同（core: pydantic>=2, requests；dev: pytest, responses, ruff, pyright；CLI: 标准库 argparse；不引 httpx/respx/click/typer）。
- [ ] `DESIGN.md` 声明「执行方案优先，详细参考仅供查询」（消除历史 22 态/13 WP 与执行版的分歧风险）。
- [ ] 仓库本地 Git 身份已配置（对应 P1）。

### 阶段 3：对应 Live 前逐项补齐（D 类，按需）
- [ ] **D5** 该 Provider 的 key/模型/区域已配（即梦登录、ARK_API_KEY、KIMI_*、XYQ_ACCESS_KEY）。
- [ ] **D5** 合法素材 + 人脸声音授权 + 预算 + `max_submits` 已批准；Live 默认关、Mock/媒体集成全绿。
- [ ] **D5** 工作区锁/重复提交/崩溃恢复/费用台账测试通过；密钥仅来自进程环境或 `~/.config/dy-fanpai/`，不进日志/仓库/fixtures。
- [ ] **D4** 合法音色 + CosyVoice/Seed-VC 就位（换声/TTS Live）。
- [ ] **D2** `pyJianYingDraft` 安装，剪映实机环境就绪。
- [ ] **D3** 私有千川包就位（完整 B 模式）。

### 阶段 4：发布/替代前
- [ ] **D1** Skill 在选定宿主新会话完成触发/暂停/恢复。
- [ ] **D6** 如需远端仓库，由用户授权创建并选可见性。
- [ ] 六类场景均有 fixture 与验收；parity 无未解释差异；Seed/即梦/至少一纯产品 i2v 完成受控 Live；FULL/FINAL 可解码；剪映草稿实机打开/编辑/保存；wheel/sdist 干净安装；私有资源未泄漏；费用/版本/模型/Prompt/task ID 可追溯。

---

## 4. 一句话结论（刷新版）

新版方案已把上一轮我指出的**路径、Python 版本、评委后端、Skill 分发、external-prerequisites.json、规格计数**等缺口全部消化或订正。**现在真正「开工前必须准备」的只剩一件事：提供 Git 提交身份（user.name / user.email，仅仓库本地）**。其余外部账号、素材、私有资源、远端仓库全部可延后到对应 Live / 发布节点，不阻塞 WP0。数据库按设计本就不需要。

---

## 附录 A：环境核查（2026-08-03，与方案声称核对）

```text
原项目 /Users/zhugx/src/daihuo-fanpai:
  git HEAD = ffc22e34cb35477b04967163c3932002ed4f3fed  ← 与基线一致 ✓
  含真实源码（ark_gen.py, assemble.py, config.py, judge.py, k3_reverse.py ...）

新目标 /Users/zhugx/src/skills/dy-fanpai: 尚未创建（WP0 将创建）

工具链:
  ffmpeg / ffprobe : 8.1.2  ✓
  uv                : 已装 ✓
  Python 3.12.13    : 已由 uv 安装 ✓  （方案声称一致）
  pippit-tool-cli   : 已装（小云雀 CLI），XYQ_ACCESS_KEY 未配置
  即梦 CLI          : 未安装/未登录
  Ark / Kimi / XYQ 凭证 : 未配置
  CosyVoice / Seed-VC / pyJianYingDraft : 未安装
  Git user.name/email : 均未配置 ← 唯一近期阻塞项
```

## 附录 B：方案对「原差距清单」的官方更正（引自清单 v1.1 §1）

- Python 3.12 已安装，不需要再次安装；
- 原项目评委后端并非未定义，默认使用 Ark Seed；
- 小云雀 CLI 已安装，缺少的是凭证和真实验收；
- 详细参考实际是 WP0～WP12，共 13 个工作包，不是 14 个；
- 执行方案是 7 个流程阶段、11 个状态值和 4 个闸口，不能简写为“7 状态”；
- `.env`、数据库、远程队列和单独的 `external-prerequisites.json` 都不是第一版必需项；
- Skill 安装路径尚未由真实宿主验证，不固定写成 `~/.workbuddy/skills/`。
