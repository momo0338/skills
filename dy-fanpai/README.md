# dy-fanpai · 抖音翻拍

独立重建的抖音带货视频翻拍项目：中性母版、字幕成品与剪映草稿交付。
不修改、不依赖原项目 `daihuo-fanpai`（只读基线，MIT · wangcanyu）。

## 设计权威

- `docs/EXECUTION_PLAN.md` — **唯一执行权威**（v2.2）
- `docs/DESIGN.md` — 冻结的公共接口与冲突裁决（WP1）
- `docs/WP0_BASELINE.md` — 原项目行为基线（parity 证据）
- `docs/archive/DY_FANPAI_DETAILED_REFERENCE.md` — 仅供人工查阅

## 安装（开发）

要求 Python ≥3.12；仓库开发与 CI 统一使用 Python 3.12，并推荐用 uv 创建独立环境：

```bash
uv venv --python 3.12.13
uv pip install -e ".[dev]"
```

剪映草稿（可选，独立环境）：

```bash
uv pip install -e ".[jianying]"
```

## 配置

密钥读取优先级：进程环境变量 → `~/.config/dy-fanpai/<name>` → 默认值。
必须支持的变量见 `docs/EXECUTION_PLAN.md §0.8`（ARK_API_KEY、KIMI_API_KEY、
XYQ_ACCESS_KEY、ARK_SEED_MODEL、COSYVOICE_HOME、DY_FANPAI_SEEDVC_HOME、
DY_FANPAI_JY_DRAFTS、DY_FANPAI_JY_PYTHON、DY_FANPAI_DOWNLOAD_PROXY 等）。
密钥绝不进仓库；测试用假值。

## 工作区（运行产物）

每个任务一个工作区，**放仓库外**（如 `~/dy_fp/runs/<id>`），绝不在代码仓内产生过程产物：

```bash
dy-fanpai doctor
dy-fanpai new --video target.mp4 --workspace ~/dy_fp/runs/demo
dy-fanpai status ~/dy_fp/runs/demo
dy-fanpai run ~/dy_fp/runs/demo --stage reverse --leg qwen     # 反推腿: seed|kimi|qwen
dy-fanpai approve ~/dy_fp/runs/demo plan
dy-fanpai run ~/dy_fp/runs/demo --stage audio --tts-backend voicebox   # 配音: voxcpm|voicebox
dy-fanpai approve ~/dy_fp/runs/demo generation --segments S1 --provider dreamina --max-submits 1
dy-fanpai run ~/dy_fp/runs/demo --stage generate --i2v-backend comfyui  # 生成: dreamina|ark|xyq|minimax|comfyui|comfyui_h3
dy-fanpai tts --backend voxcpm --only S1    # 独立配音(不依赖 run 流水线)
dy-fanpai retry ~/dy_fp/runs/demo
dy-fanpai deliver ~/dy_fp/runs/demo --mode final|jianying|both
dy-fanpai clean ~/dy_fp/runs/demo --dry-run
```

`runs/`（及全部视频/音频产物）已在 `.gitignore` 忽略；即使误建在仓库内也不会被提交。

## 测试

```bash
pytest                 # 五类：unit / original-parity / media-integration / provider-mock / live(skip)
ruff check src tests
pyright
```

## 状态

**WP0–WP6 已全部完成**（见 docs/CHANGELOG.md）：七阶段流水线 + 四闸口集成就绪，
可插拔后端矩阵——反推 3 腿（seed/kimi/qwen）、生成 6 后端（dreamina 默认 /
ark / xyq / minimax / comfyui / comfyui_h3）、TTS 配音 2 后端（voxcpm 在线 /
voicebox 本地 Qwen3-TTS）。

仍未宣布「替代原项目」：Live 全链路验收与发布审计未完成（即梦 CLI 登录、
剪映实机验收、私有千川包等外部依赖未验收）。缺合法素材/音色/剪映实机时，
对应功能标记「实现完成，外部验收未完成」，不得宣称全部完成。
