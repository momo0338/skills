#!/usr/bin/env bash
# =============================================================================
# install_comfyui_rocm.sh — AMD(ROCm)平台安装 ComfyUI
#
# 来源:ModelScope 文章 434324(继承全局防覆盖)+ 435354(triton 3.7.1)融合
# 平台:Ubuntu 22.04 + AMD Instinct MI308X(gfx942) + ROCm 7.2.3(DSW 预装环境)
#
# 用法:
#   bash install_comfyui_rocm.sh [--workspace /path/to/workdir]
# 默认工作目录:/mnt/workspace/comfy(用户实机路径);若该处无 ComfyUI 自动回退 /workspace
#
# 说明:本脚本可独立运行;通常由 install_comfyui.sh 检测到 AMD GPU 后自动调用,
#       也可用 COMFY_GPU=amd bash install_comfyui.sh 强制指定。
# =============================================================================
set -euo pipefail

# 参数解析:兼容位置参数(bash install_comfyui_rocm.sh /path)与 --workspace 风格
WORK="${COMFY_WORK:-/mnt/workspace/comfy}"
if [ $# -gt 0 ] && [[ "${1#--}" == "$1" ]]; then
  WORK="$1"; shift
fi
while [ $# -gt 0 ]; do
  case "$1" in
    --workspace)    WORK="${2:?--workspace 需要路径}"; shift 2 ;;
    --workspace=*)  WORK="${1#*=}"; shift ;;
    -h|--help)      sed -n '2,14p' "$0" | sed 's/^# //' | grep -v '^=='; exit 0 ;;
    *) echo "未知参数: $1(支持 --workspace PATH)"; exit 1 ;;
  esac
done
# 默认路径下没有 ComfyUI 时,回退探测 /workspace(软链/挂载兼容)
if [ ! -d "$WORK/ComfyUI" ] && [ -d "/workspace/ComfyUI" ]; then
  echo "==> $WORK/ComfyUI 不存在,回退使用 /workspace"
  WORK="/workspace"
fi
COMFY_DIR="$WORK/ComfyUI"
MIRROR_PREFIX="https://ghfast.top/"   # GitHub 加速镜像(国内拉取慢时可去掉)

echo "==> 工作目录: $WORK"
mkdir -p "$WORK"
cd "$WORK"

# -----------------------------------------------------------------------------
# 1. 克隆 ComfyUI(优先走加速镜像;失败则直连)
# -----------------------------------------------------------------------------
export HF_ENDPOINT=https://hf-mirror.com   # 国内 HF 镜像(435354)

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
# 2. 检测系统 Python 是否已预装 ROCm torch(关键决策!)
#    DSW/魔搭镜像通常已装好: torch ROCm + flash_attn 2.8.3
#    若 hip 非空 → 走"继承全局"路线,绝不重复装 torch(防覆盖,434324 血泪)
#    若 hip 为空 → 裸机路线,装官方 ROCm whl
# -----------------------------------------------------------------------------
SYS_HIP=$(python3 -c "import torch; print(torch.version.hip or '')" 2>/dev/null || echo "")

if [ -n "$SYS_HIP" ]; then
  echo "==> 检测到系统预装 ROCm torch (hip=$SYS_HIP) → 走继承全局路线"
  if [ ! -d ".venv" ]; then
    python3 -m venv .venv --system-site-packages
  fi
  # shellcheck disable=SC1091
  source .venv/bin/activate
  python -V
  # 阉割 requirements 中的 torch 行,防止覆盖系统 ROCm torch
  sed -i.bak '/^torch/d' requirements.txt
  echo "==> 安装 ComfyUI 其余依赖"
  pip install --upgrade pip
  pip install -r requirements.txt
else
  echo "==> 未检测到系统 ROCm torch → 裸机路线,装官方 ROCm 7.2 whl"
  if [ ! -d ".venv" ]; then
    python3 -m venv .venv
  fi
  # shellcheck disable=SC1091
  source .venv/bin/activate
  python -V
  pip install --upgrade pip
  pip install torch torchvision torchaudio \
    --index-url https://download.pytorch.org/whl/rocm7.2
  pip install -r requirements.txt
fi

# -----------------------------------------------------------------------------
# 3. triton 必须 >= 3.7.1(3.6.0 在 ROCm 下 int8 内核因 libdevice 缺 rint 会崩)
#    (435354 实测:升级后 comfy-kitchen triton 后端才启用,INT8 提速 ~30%)
# -----------------------------------------------------------------------------
echo "==> 升级 triton 到 3.7.1(ROCm int8 内核必需)"
pip install "triton>=3.7.1"

# 系统已有 flash_attn 2.8.3 则继承即可;裸机环境补装
if ! python -c "import flash_attn; print(flash_attn.__version__)" >/dev/null 2>&1; then
  echo "==> 未发现 flash_attn,尝试安装 ROCm 适配版(失败可跳过,不影响启动)"
  pip install flash-attn 2>/dev/null || echo "    (flash_attn 安装失败,改用 --use-pytorch-cross-attention 兜底)"
fi

echo "==> 安装后校验(hip 非空才正确)"
python -c "import torch; print('torch:', torch.__version__, '| hip:', torch.version.hip)"
python -c "import triton; print('triton:', triton.__version__)" | grep -E "^triton: (3\.7|3\.8|3\.9|4\.)" \
  || echo "⚠️ 警告: triton 版本可能 <3.7.1(ROCm int8 内核会崩,435354),请确认上面的输出"

# -----------------------------------------------------------------------------
# 4. 防御性清理(434324: 若 ComfyUI 目录是从 N 卡机器拷来的旧目录)
#    全新克隆可跳过;迁移场景需清理 N 卡专属库与监控插件
# -----------------------------------------------------------------------------
echo "==> 防御性检查: 卸载 N 卡专属底层库(如存在)"
pip uninstall -y xformers bitsandbytes 2>/dev/null || true
echo "==> 防御性检查: 清理 N 卡监控类自定义节点(如存在)"
cd "$COMFY_DIR/custom_nodes" 2>/dev/null || exit 0
for node in Crystools ComfyUI-XPUSYS-Monitor rgthree-comfy ComfyUI-Custom-Scripts; do
  [ -d "$node" ] && { echo "   移除 $node"; rm -rf "$node"; }
done

echo "✅ ROCm 安装完成: $COMFY_DIR"
echo "   下一步: bash run_comfyui.sh(自动识别 ROCm 参数)"
