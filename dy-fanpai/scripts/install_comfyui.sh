#!/usr/bin/env bash
# =============================================================================
# install_comfyui.sh — ComfyUI 安装统一入口(自动检测 GPU 厂商并分派)
#
# 根据 GPU 厂商自动选择安装包与安装路线:
#   NVIDIA → install_comfyui_cuda.sh(装 CUDA 版 torch + xformers/flash-attn)
#   AMD    → install_comfyui_rocm.sh(装 ROCm 版 torch,继承全局/裸机双路线)
#   未知   → 打印提示并终止,需手动 COMFY_GPU 指定
#
# 用法:
#   bash install_comfyui.sh [--workspace /path/to/workdir] [--gpu auto|nvidia|amd|cpu]
#   或等价环境变量:
#   COMFY_WORK=/path COMFY_GPU=nvidia bash install_comfyui.sh
#
# 检测口径(与 run_comfyui.sh 完全一致,见 scripts/detect_gpu.sh):
#   1) 系统 python 已装 torch → 按 torch.version.cuda / torch.version.hip 判断
#   2) nvidia-smi(英伟达) / rocm-smi|rocminfo(AMD)
#   3) lspci 硬件枚举兜底
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=detect_gpu.sh
source "$SCRIPT_DIR/detect_gpu.sh"

WORK="${COMFY_WORK:-/mnt/workspace/comfy}"
GPU_ARG="auto"

while [ $# -gt 0 ]; do
  case "$1" in
    --workspace) WORK="${2:?--workspace 需要路径}"; shift 2 ;;
    --workspace=*) WORK="${1#*=}"; shift ;;
    --gpu) GPU_ARG="${2:?--gpu 需要 auto|nvidia|amd|cpu}"; shift 2 ;;
    --gpu=*) GPU_ARG="${1#*=}"; shift ;;
    -h|--help)
      grep -E "^# +(用法|bash|或|COMFY)" "$0" | sed 's/^# *//'; exit 0 ;;
    *) echo "未知参数: $1 (--workspace / --gpu / -h)"; exit 1 ;;
  esac
done

# --gpu 优先级高于 COMFY_GPU,再高于自动探测
if [ "$GPU_ARG" != "auto" ]; then
  COMFY_GPU="$GPU_ARG"
fi
export COMFY_GPU

echo "================================================================"
echo "==> ComfyUI 安装器 · GPU 环境检测"
echo "================================================================"
GPU_TYPE="$(detect_gpu)"
describe_gpu "$GPU_TYPE"

case "$GPU_TYPE" in
  nvidia)
    echo "==> 分派到 NVIDIA/CUDA 安装脚本"
    bash "$SCRIPT_DIR/install_comfyui_cuda.sh" --workspace "$WORK"
    ;;
  amd)
    echo "==> 分派到 AMD/ROCm 安装脚本"
    bash "$SCRIPT_DIR/install_comfyui_rocm.sh" --workspace "$WORK"
    ;;
  cpu)
    echo "⚠️  已按 CPU 模式处理,但 ComfyUI 推理强依赖 GPU,不推荐。"
    echo "   若确实要装,请手动指定: COMFY_GPU=nvidia|amd bash $0 --workspace $WORK"
    exit 1
    ;;
  unknown)
    echo ""
    echo "❌ 无法自动识别 GPU 厂商。可能原因:"
    echo "   - 无 NVIDIA/AMD GPU(纯 CPU 机器 / 云函数 / 容器未透传 GPU)"
    echo "   - 缺少 lspci 且未装驱动工具(nvidia-smi / rocm-smi / rocminfo)"
    echo ""
    echo "   请手动指定后重试:"
    echo "     NVIDIA 机器: COMFY_GPU=nvidia bash $0 --workspace $WORK"
    echo "     AMD 机器:    COMFY_GPU=amd    bash $0 --workspace $WORK"
    exit 1
    ;;
esac
