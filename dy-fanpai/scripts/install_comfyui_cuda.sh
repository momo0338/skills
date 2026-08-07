#!/usr/bin/env bash
# =============================================================================
# install_comfyui_cuda.sh — NVIDIA(CUDA)平台安装 ComfyUI
#
# 与 install_comfyui_rocm.sh 对称的 NVIDIA 分支:
#   - 装官方 CUDA 版 torch(torchvision/torchaudio),默认 cu128
#   - 可选装 xformers / flash-attn(失败不阻塞启动)
#   - 装完校验 torch.cuda.is_available()
#
# 用法:
#   bash install_comfyui_cuda.sh [--workspace /path/to/workdir]
# 默认工作目录:/mnt/workspace/comfy(与 ROCm 版本保持一致的口径);
#   若该处无 ComfyUI 自动回退 /workspace。N 卡机器请显式指定:
#   bash install_comfyui_cuda.sh --workspace /home/user/comfy
#
# 环境变量:
#   COMFY_CUDA_VERSION : CUDA 轮子版本,默认 cu128(可选 cu121/cu124/cu126)
#   COMFY_GPU          : 强制指定(见 detect_gpu.sh),本脚本不强制
#
# 说明:本脚本可独立运行;通常由 install_comfyui.sh 检测到 NVIDIA GPU 后自动调用,
#       也可用 COMFY_GPU=nvidia bash install_comfyui.sh 强制指定。
# =============================================================================
set -euo pipefail

# 参数解析:兼容位置参数(bash install_comfyui_cuda.sh /path)与 --workspace 风格
WORK="${COMFY_WORK:-/mnt/workspace/comfy}"
if [ $# -gt 0 ] && [[ "${1#--}" == "$1" ]]; then
  WORK="$1"; shift
fi
while [ $# -gt 0 ]; do
  case "$1" in
    --workspace)    WORK="${2:?--workspace 需要路径}"; shift 2 ;;
    --workspace=*)  WORK="${1#*=}"; shift ;;
    -h|--help)      sed -n '2,20p' "$0" | sed 's/^# //' | grep -v '^=='; exit 0 ;;
    *) echo "未知参数: $1(支持 --workspace PATH)"; exit 1 ;;
  esac
done
COMFY_DIR="$WORK/ComfyUI"
MIRROR_PREFIX="https://ghfast.top/"   # GitHub 加速镜像(国内拉取慢时可去掉)
CUDA_VER="${COMFY_CUDA_VERSION:-cu128}"

echo "==> 工作目录: $WORK | CUDA 轮子: $CUDA_VER"
mkdir -p "$WORK"
cd "$WORK"

# -----------------------------------------------------------------------------
# 1. 克隆 ComfyUI(优先走加速镜像;失败则直连)
# -----------------------------------------------------------------------------
export HF_ENDPOINT=https://hf-mirror.com   # 国内 HF 镜像

if [ ! -d "$COMFY_DIR/.git" ]; then
  echo "==> 克隆 ComfyUI"
  git clone "${MIRROR_PREFIX}https://github.com/comfyanonymous/ComfyUI.git" \
    || git clone https://github.com/comfyanonymous/ComfyUI.git
else
  echo "==> ComfyUI 已存在,执行 ff-only 更新(435230: 防前后端版本不一致导致 405)"
  git -C "$COMFY_DIR" fetch origin && git -C "$COMFY_DIR" pull --ff-only
fi
cd "$COMFY_DIR"

# -----------------------------------------------------------------------------
# 2. 建 venv + 安装 CUDA torch(独立 venv,不继承系统 python,
#    避免系统 python 里 ROCm torch / 旧 CUDA 污染)
# -----------------------------------------------------------------------------
if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
python -V
pip install --upgrade pip

echo "==> 安装 CUDA $CUDA_VER torch"
pip install torch torchvision torchaudio \
  --index-url "https://download.pytorch.org/whl/$CUDA_VER"

# -----------------------------------------------------------------------------
# 3. ComfyUI 其余依赖(requirements 里的 torch 行会被上一步的版本满足,无需处理)
# -----------------------------------------------------------------------------
pip install -r requirements.txt

# xformers 可选:装成功则启动脚本可用 --xformers 提速;失败仅提示,不阻塞
if ! python -c "import xformers; print(xformers.__version__)" >/dev/null 2>&1; then
  echo "==> 尝试安装 xformers(可选,失败自动跳过)"
  pip install xformers 2>/dev/null \
    || echo "    (xformers 安装失败,启动时用 flash-attn/sdpa 兜底)"
fi

# flash-attn 可选
if ! python -c "import flash_attn; print(flash_attn.__version__)" >/dev/null 2>&1; then
  echo "==> 尝试安装 flash-attn(可选,失败自动跳过)"
  pip install flash-attn 2>/dev/null \
    || echo "    (flash_attn 安装失败,启动时用 --use-split-cross-attention 兜底)"
fi

# -----------------------------------------------------------------------------
# 4. 安装后校验(cuda 非空 且 is_available 为 True 才正确)
# -----------------------------------------------------------------------------
echo "==> 安装后校验"
python -c "
import torch
print('torch:', torch.__version__, '| cuda:', torch.version.cuda)
print('cuda_available:', torch.cuda.is_available())
assert torch.cuda.is_available(), 'CUDA 不可用!请检查驱动(nvidia-smi)与 CUDA 版本是否匹配'
"

# -----------------------------------------------------------------------------
# 5. 防御性清理(与 ROCm 脚本对称:清理从 AMD 机器拷来的目录里的 AMD 专属残留)
# -----------------------------------------------------------------------------
echo "==> 防御性检查: 清理 AMD/ROCm 专属自定义节点(如存在)"
cd "$COMFY_DIR/custom_nodes" 2>/dev/null || exit 0
for node in comfy-kitchen ComfyUI-AMD-Patcher; do
  [ -d "$node" ] && { echo "   移除 $node"; rm -rf "$node"; }
done

echo "✅ CUDA 安装完成: $COMFY_DIR"
echo "   下一步: bash run_comfyui.sh(自动识别 CUDA 参数)"
