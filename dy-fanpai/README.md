# dy-fanpai · 抖音翻拍

独立重建的抖音带货视频翻拍项目：中性母版、字幕成品与剪映草稿交付。
不修改、不依赖原项目 `daihuo-fanpai`（只读基线，MIT · wangcanyu）。

## 设计权威

- `docs/EXECUTION_PLAN.md` — **唯一执行权威**（v2.2）
- `docs/DESIGN.md` — 冻结的公共接口与冲突裁决（WP1）
- `docs/WP0_BASELINE.md` — 原项目行为基线（parity 证据）
- `docs/archive/DY_FANPAI_DETAILED_REFERENCE.md` — 仅供人工查阅

## 安装（开发）

要求 Python 3.12（推荐用 uv）：

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

## CLI

```bash
dy-fanpai doctor
dy-fanpai new --video target.mp4 --workspace runs/demo
dy-fanpai status runs/demo
dy-fanpai run runs/demo --stage reverse
dy-fanpai approve runs/demo plan
dy-fanpai approve runs/demo generation --segments S1 --provider dreamina --max-submits 1
dy-fanpai retry runs/demo
dy-fanpai deliver runs/demo --mode final|jianying|both
dy-fanpai clean runs/demo --dry-run
```

## 测试

```bash
pytest                 # 五类：unit / original-parity / media-integration / provider-mock / live(skip)
ruff check src tests
pyright
```

## 状态

当前处于 **WP1（骨架与核心）完成、接口冻结** 阶段。业务实现由 WP2–WP5
在各自子包内完成，WP6 集成与发布后方可宣布替代原项目。
