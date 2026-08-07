#!/usr/bin/env bash
# =============================================================================
# run_comfyui.sh — 启动 ComfyUI(自动识别 CUDA / ROCm 环境,选用对应参数)
#
# 安装侧(install_comfyui.sh)已经按 GPU 厂商装好对应 torch,这里以
# 实际激活的 venv 里 torch 类型为准(而非再猜硬件),保证安装/启动口径一致:
#   venv 内 torch.version.hip  非空 → AMD/ROCm 参数(原有 MI308X/MI300X 优化)
#   venv 内 torch.version.cuda 非空 → NVIDIA/CUDA 参数(xformers/flash-attn 优先)
#   两者皆空 → 通用兜底参数
# 可用 COMFY_GPU=nvidia|amd 强制指定(见 scripts/detect_gpu.sh)。
#
# 用法:
#   bash run_comfyui.sh [--port 8188]
# 环境变量(均可在脚本前用 export 覆盖):
#   COMFY_WORK  : 工作目录,默认 /mnt/workspace/comfy(用户实机路径);
#                 若该处无 ComfyUI 自动回退探测 /workspace(软链兼容)
#   COMFY_PORT  : 监听端口,默认 8188
#   COMFY_ATTN  : 注意力后端,auto|sdpa(排查 flash_attn 兼容问题时用 sdpa)
#   COMFY_FP16_VAE: 1/0,控制 --fp16-vae(默认 0=关,AMD ROCm 防粉红输出,08-04 实测)
#   COMFY_HIGHVRAM: 1/0,强制加/去 --highvram(默认: AMD 开,NVIDIA 关)
# =============================================================================
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=detect_gpu.sh
source "$SCRIPT_DIR/detect_gpu.sh"

COMFY_WORK="${COMFY_WORK:-/mnt/workspace/comfy}"
COMFY_PORT="${COMFY_PORT:-8188}"
COMFY_DIR="$COMFY_WORK/ComfyUI"

# 默认路径下没有 ComfyUI 时,回退探测 /workspace(软链/挂载兼容)
if [ ! -d "$COMFY_DIR" ] && [ -d "/workspace/ComfyUI" ]; then
  echo "==> $COMFY_DIR 不存在,回退使用 /workspace/ComfyUI"
  COMFY_DIR="/workspace/ComfyUI"
fi

# 优先用已存在的全局 env(用户环境习惯);否则用 ComfyUI/.venv
if [ -d "$COMFY_WORK/env" ]; then
  echo "==> 激活 $COMFY_WORK/env"
  # shellcheck disable=SC1091
  source "$COMFY_WORK/env/bin/activate"
elif [ -d "$COMFY_DIR/.venv" ]; then
  echo "==> 激活 $COMFY_DIR/.venv"
  # shellcheck disable=SC1091
  source "$COMFY_DIR/.venv/bin/activate"
else
  echo "==> 警告: 未找到 venv,直接用系统 python(需已预装对应 torch)"
fi

cd "$COMFY_DIR" || { echo "❌ 无法进入 $COMFY_DIR,请先运行 install_comfyui.sh"; exit 1; }

# -----------------------------------------------------------------------------
# 0. 运行时平台判定: 以 venv 里实际装的 torch 为准,硬件探测作兜底
#    (COMFY_GPU 手动指定时 detect_gpu 直接返回该值)
# -----------------------------------------------------------------------------
TORCH_HIP=$(python -c "import torch; print(torch.version.hip or '')" 2>/dev/null || echo "")
TORCH_CUDA=$(python -c "import torch; print(torch.version.cuda or '')" 2>/dev/null || echo "")

echo "================================================================"
if [ -n "$TORCH_HIP" ]; then
  GPU_TYPE="amd"
  echo "==> 运行环境: AMD/ROCm (torch hip=$TORCH_HIP)"
elif [ -n "$TORCH_CUDA" ]; then
  GPU_TYPE="nvidia"
  echo "==> 运行环境: NVIDIA/CUDA (torch cuda=$TORCH_CUDA)"
else
  GPU_TYPE="$(detect_gpu)"
  echo "==> venv 内未检测到 torch,按硬件探测结果执行"
  describe_gpu "$GPU_TYPE"
fi
echo "================================================================"

# 国内 HF 镜像(依赖/权重加速;模型主体走 ModelScope 则非必需)
export HF_ENDPOINT=https://hf-mirror.com

# -----------------------------------------------------------------------------
# AMD / ROCm 分支(原有 MI308X/MI300X 优化,逐项保留注释)
# -----------------------------------------------------------------------------
if [ "$GPU_TYPE" = "amd" ]; then

  # AMD FlashAttention 加速(435354)
  export FLASH_ATTENTION_TRITON_AMD_ENABLE="TRUE"

  # AOTriton 实验加速(435354/434324)
  export TORCH_ROCM_AOTRITON_ENABLE_EXPERIMENTAL=1

  # 注意:MI300X/MI308X 是 gfx942,ROCm 7.2 原生支持,不需要 HSA_OVERRIDE_GFX_VERSION!
  # (旧值 11.0.0 是 RX7900/gfx1100 的,设了反而可能触发 Illegal opcode)
  # 若启动报架构错误再试: export HSA_OVERRIDE_GFX_VERSION=9.4.2

  # 解决显存碎片化导致跑图中断的终极杀招(434324)
  export PYTORCH_HIP_ALLOC_CONF="garbage_collection_threshold:0.8,expandable_segments:True"

  # 可选加速(434324):算子自整定,第一次跑图编译慢,之后起飞
  # export PYTORCH_TUNABLEOP_ENABLED=1
  # export HIP_FORCE_DEV_KERN_ARG=1
  # export MIOPEN_FIND_MODE=FAST

  # 注意力后端: auto=有 flash_attn 用 flash 否则 sdpa;可强制 sdpa 排查 flash_attn 兼容问题
  #   (08-04 实机: flash_attn 2.8.3 已装;若出现 hipErrorLaunchFailure 且怀疑 flash_attn,设 COMFY_ATTN=sdpa)
  if [[ "${COMFY_ATTN:-auto}" == "sdpa" ]]; then
    ATTN_ARGS="--use-pytorch-cross-attention"
    echo "==> 强制 sdpa 注意力(--use-pytorch-cross-attention,COMFY_ATTN=sdpa)"
  elif python -c "import flash_attn" >/dev/null 2>&1; then
    echo "==> 检测到 flash_attn,使用 --use-flash-attention(435354 实测)"
    ATTN_ARGS="--use-flash-attention"
  else
    echo "==> 未检测到 flash_attn,回退 --use-pytorch-cross-attention(435230 稳定兜底)"
    ATTN_ARGS="--use-pytorch-cross-attention"
  fi

  # --enable-triton-backend 需 triton>=3.7.1;3.6.0 已知触发 Illegal opcode/崩溃(08-04 实机诊断)
  TRITON_VER=$(python -c "import triton;v=triton.__version__.split('.');print(f'{v[0]}.{v[1]}')" 2>/dev/null || echo "0.0")
  if [[ "$TRITON_VER" =~ ^[0-9]+\.[0-9]+$ ]] && [[ "$(printf '%s\n' "$TRITON_VER" "3.7" | sort -V | head -1)" == "3.7" ]]; then
    TRITON_ARGS="--enable-triton-backend"
    echo "==> triton $TRITON_VER.x >= 3.7,启用 --enable-triton-backend"
  else
    TRITON_ARGS=""
    echo "==> triton $TRITON_VER(需 >=3.7.1,3.6.0 已知崩溃),跳过 --enable-triton-backend;升级: pip install -U triton"
  fi

  # AMD 服务器大显存(192GB)默认常驻 GPU
  VRAM_ARGS="--highvram --disable-async-offload --disable-pinned-memory --disable-smart-memory"
  # 切断任何企图加载 N 卡库的插件(434324)
  EXTRA_ARGS="--disable-xformers"

# -----------------------------------------------------------------------------
# NVIDIA / CUDA 分支(消费级卡默认不 --highvram,可用 COMFY_HIGHVRAM=1 强制)
# -----------------------------------------------------------------------------
elif [ "$GPU_TYPE" = "nvidia" ]; then

  # CUDA 显存分配: 分段可扩展,缓解碎片化(等价 AMD 的 expandable_segments 杀招)
  export PYTORCH_CUDA_ALLOC_CONF="expandable_segments:True"

  # 注意力后端: xformers > flash-attn > split-cross-attention(sdpa)
  # 注意: 新版 ComfyUI 不再接受 --xformers 参数(08-04 实机启动报 unrecognized arguments),
  #       xformers 在 venv 内已装时由 ComfyUI 自动启用,无需手动传参;
  #       仅 --disable-xformers(关)保留。故检测到 xformers 时 ATTN_ARGS 留空即可。
  if [[ "${COMFY_ATTN:-auto}" == "sdpa" ]]; then
    ATTN_ARGS="--use-split-cross-attention"
    echo "==> 强制 sdpa 注意力(--use-split-cross-attention,COMFY_ATTN=sdpa)"
  elif python -c "import xformers" >/dev/null 2>&1; then
    echo "==> 检测到 xformers,自动启用(新版 ComfyUI 无需 --xformers 参数)"
    ATTN_ARGS=""
  elif python -c "import flash_attn" >/dev/null 2>&1; then
    echo "==> 未找到 xformers,检测到 flash_attn,使用 --use-flash-attention"
    ATTN_ARGS="--use-flash-attention"
  else
    echo "==> 未找到 xformers/flash_attn,回退 --use-split-cross-attention(稳定兜底)"
    ATTN_ARGS="--use-split-cross-attention"
  fi

  # NVIDIA 侧无 triton 后端开关(该参数是 ROCm 专属)
  TRITON_ARGS=""
  VRAM_ARGS=""
  EXTRA_ARGS=""
  if [[ "${COMFY_HIGHVRAM:-0}" == "1" ]]; then
    VRAM_ARGS="--highvram --disable-async-offload"
    echo "==> COMFY_HIGHVRAM=1,启用 --highvram"
  fi

# -----------------------------------------------------------------------------
# 未知环境: 最保守的通用参数
# -----------------------------------------------------------------------------
else
  ATTN_ARGS="--use-split-cross-attention"
  TRITON_ARGS=""
  VRAM_ARGS=""
  EXTRA_ARGS=""
  echo "==> 未知 GPU 环境,使用保守参数(仅 CPU 可用时请确认 torch 为 CPU 版)"
fi

# VAE 精度默认值按 GPU 类型区分(2026-08-06 修复:此前 NVIDIA 分支误吃 AMD 默认):
#   - AMD/ROCm: fp16 VAE 内核不稳定(08-04 实测 MI308X 全输出粉红/噪点),默认 0=关闭
#   - NVIDIA/CUDA: fp16 VAE 更快更稳,默认 1=开启
# 均可用 COMFY_FP16_VAE=1|0 显式覆盖。
if [[ "$GPU_TYPE" == "nvidia" ]]; then
  COMFY_FP16_VAE="${COMFY_FP16_VAE:-1}"
else
  COMFY_FP16_VAE="${COMFY_FP16_VAE:-0}"
fi
if [[ "$COMFY_FP16_VAE" == "1" ]]; then
  VAE_ARGS="--fp16-vae"
  echo "==> VAE 使用 fp16(NVIDIA 默认;AMD 若需排查粉红请 COMFY_FP16_VAE=0)"
else
  VAE_ARGS=""
  echo "==> VAE 使用 fp32(--fp16-vae 已关,AMD ROCm 默认,防粉红输出)"
fi

echo "==> 启动 ComfyUI: 端口 $COMFY_PORT"
# --disable-auto-launch:  无浏览器环境,禁止自动拉起浏览器
# $VRAM_ARGS:             AMD 默认 --highvram 系;NVIDIA 默认无,COMFY_HIGHVRAM=1 开启
# $EXTRA_ARGS:            AMD 加 --disable-xformers;NVIDIA 无
# $ATTN_ARGS:             NVIDIA 侧 xformers 自动启用(留空);flash-attention/sdpa 按需显式传参
# $TRITON_ARGS:           ROCm 且 triton>=3.7.1 才启用 --enable-triton-backend
# $VAE_ARGS:              COMFY_FP16_VAE=0 关闭 --fp16-vae
# --listen 0.0.0.0:       允许远程访问(供 dy-fanpai 调用)
#
# ── 崩溃排查(08-04: hipErrorLaunchFailure,错误可能异步报告到别的调用点)────────
#   1) 先复位 GPU: pkill -9 python → 重启 DSW 容器/内核(硬崩溃后设备常卡死)
#   2) 最小参数复测定位真正失败的内核:
#        AMD: AMD_SERIALIZE_KERNEL=3 COMFY_FP16_VAE=0 COMFY_ATTN=sdpa bash run_comfyui.sh
#   3) 通过后逐个恢复: 先 triton(升级 >=3.7.1),再 flash_attn,最后 fp16-vae
# ── 现象2: 生成视频全粉红/紫噪点(08-04 实机)───────────────────────────────
#   症状: 不同输入图+不同 prompt 输出均粉红/白粉渐变,无产品主体。
#   根因: AMD ROCm 上 --fp16-vae 内核不稳定 → VAE 解码数值爆炸。
#   处置: 确认脚本默认 COMFY_FP16_VAE=0(f16→fp32)后重启即可;无需改工作流/prompt。
python main.py --listen 0.0.0.0 --port "$COMFY_PORT" \
  --disable-auto-launch \
  $VRAM_ARGS $EXTRA_ARGS $ATTN_ARGS $TRITON_ARGS $VAE_ARGS
