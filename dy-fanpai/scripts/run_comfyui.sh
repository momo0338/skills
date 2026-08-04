#!/usr/bin/env bash
# =============================================================================
# run_comfyui.sh — MI300X(192GB) 启动 ComfyUI(AMD ROCm 加速 + 防崩溃参数)
#
# 来源:用户实测方法(2026-08-04 整理)
# 平台:Ubuntu + AMD Instinct MI300X + ROCm 7.2
#
# 用法:
#   bash run_comfyui.sh [--port 8188]
# 环境变量(均可在脚本前用 export 覆盖):
#   COMFY_WORK  : 工作目录,默认 /workspace
#   COMFY_PORT  : 监听端口,默认 8188
# =============================================================================
set -uo pipefail

COMFY_WORK="${COMFY_WORK:-/workspace}"
COMFY_PORT="${COMFY_PORT:-8188}"
COMFY_DIR="$COMFY_WORK/ComfyUI"

# 优先用已存在的全局 env(用户环境习惯);否则用 ComfyUI/.venv
if [ -d "$COMFY_WORK/env" ]; then
  echo "==> 激活 $COMFY_WORK/env"
  # shellcheck disable=SC1091
  source "$COMFY_WORK/env/bin/activate"
else
  echo "==> 激活 $COMFY_DIR/.venv"
  # shellcheck disable=SC1091
  source "$COMFY_DIR/.venv/bin/activate"
fi

cd "$COMFY_DIR"

# -----------------------------------------------------------------------------
# AMD 专属加速与防崩溃环境变量(核心!)
# -----------------------------------------------------------------------------
export FLASH_ATTENTION_TRITON_AMD_ENABLE="TRUE"      # AMD FlashAttention 加速
export TORCH_ROCM_AOTRITON_ENABLE_EXPERIMENTAL=1     # AOTriton 实验加速
export HSA_OVERRIDE_GFX_VERSION=11.0.0               # 覆盖 gfx 版本(RX7900 系需;MI300X 可留空试)
# 解决显存碎片化导致跑图中断的终极杀招
export PYTORCH_HIP_ALLOC_CONF="garbage_collection_threshold:0.8,expandable_segments:True"

echo "==> 启动 ComfyUI: 端口 $COMFY_PORT"
# --disable-xformers:          切断任何企图加载 N 卡库的插件
# --use-flash-attention:       AMD 环境最有效注意力机制打底
# --fp16-vae:                  VAE 半精度,省显存
# --listen 0.0.0.0:            允许远程访问(供本机 dy-fanpai 调用)
python main.py --listen 0.0.0.0 --port "$COMFY_PORT" \
  --disable-xformers \
  --use-flash-attention \
  --fp16-vae
