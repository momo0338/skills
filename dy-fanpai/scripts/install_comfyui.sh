#!/usr/bin/env bash
# =============================================================================
# install_comfyui.sh — MI300X(192GB) 上安装 ComfyUI + ROCm 环境
#
# 来源:用户实测方法(2026-08-04 整理)
# 平台:Ubuntu + AMD Instinct MI300X + ROCm 7.2
#
# 用法:
#   bash install_comfyui.sh [--workspace /path/to/workdir]
# 默认工作目录:/workspace
# =============================================================================
set -euo pipefail

WORK="${1:-/workspace}"
COMFY_DIR="$WORK/ComfyUI"
MIRROR_PREFIX="https://ghfast.top/"   # GitHub 加速镜像(国内拉取慢时可去掉)

echo "==> 工作目录: $WORK"
mkdir -p "$WORK"
cd "$WORK"

# -----------------------------------------------------------------------------
# 1. 克隆 ComfyUI(优先走加速镜像;失败则直连)
# -----------------------------------------------------------------------------
if [ ! -d "$COMFY_DIR/.git" ]; then
  echo "==> 克隆 ComfyUI"
  git clone "${MIRROR_PREFIX}https://github.com/comfyanonymous/ComfyUI.git" \
    || git clone https://github.com/comfyanonymous/ComfyUI.git
else
  echo "==> ComfyUI 已存在,跳过克隆"
fi
cd "$COMFY_DIR"

# -----------------------------------------------------------------------------
# 2. 虚拟环境 + PyTorch(ROCm 7.2 版)
# -----------------------------------------------------------------------------
if [ ! -d ".venv" ]; then
  echo "==> 创建 venv"
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
python -V

echo "==> 安装 PyTorch (ROCm 7.2 构建)"
# 注意:MI300X 用 ROCm 版 PyTorch;cu130 那行是 NVIDIA 卡用的,勿在此环境执行
pip install --upgrade pip
pip install torch torchvision torchaudio \
  --index-url https://download.pytorch.org/whl/rocm7.2

echo "==> 安装 ComfyUI 依赖"
pip install -r requirements.txt

echo "✅ 安装完成: $COMFY_DIR"
echo "   下一步: bash run_comfyui.sh"
