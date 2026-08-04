#!/usr/bin/env bash
# =============================================================================
# download_qwen_image_models.sh — Qwen-Image 家族模型下载(ComfyUI 单文件打包版)
#
# 方案(2026-08-04 决策):主力 Z-Image-Turbo 快速出草稿,需高质量终版(尤其带文字/
#   排版的产品图)时切 Qwen-Image-2512 fp8。本脚本按版本下载,支持 4 模型 + 蒸馏版。
#
# 共享三件套(全家族共用,除 Layered 用专用 VAE):
#   - text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors   (~9.4GB, Qwen2.5-VL-7B)
#   - vae/qwen_image_vae.safetensors                        (~0.3GB)
#   - diffusion_models/ 对应版本扩散模型(fp8 ~20.4GB / bf16 ~40.9GB)
#
# 版本与扩散模型(--model):
#   base    : qwen_image_fp8_e4m3fn.safetensors          8月原版, 50步
#   2512    : qwen_image_2512_fp8_e4m3fn.safetensors     12月质量更新, 推荐, 50步
#   edit    : qwen_image_edit_fp8_e4m3fn.safetensors     编辑版, 语义+外观双重编辑
#   layered : qwen_image_layered_bf16.safetensors(40.9G) 图层分解, 专用 VAE
#   distill : qwen_image_distill_full_fp8_e4m3fn.safetensors 蒸馏加速(non_official)
#   all     : 以上全部
#
# 加速 LoRA(--with-lora, 可选, loras/):base 用 8steps, edit/2512 用 4steps
#   来源 lightx2v/Qwen-Image-Lightning(1.7GB fp32, ModelScope 有镜像)
#
# 仓库(ModelScope 均有镜像):Comfy-Org/Qwen-Image_ComfyUI、
#   Comfy-Org/Qwen-Image-Edit_ComfyUI、Comfy-Org/Qwen-Image-Layered_ComfyUI、
#   lightx2v/Qwen-Image-Lightning
#
# 用法:
#   bash download_qwen_image_models.sh [--work-dir DIR] [--comfy-dir DIR]
#       [--model base|2512|edit|layered|distill|all(默认 2512)] [--with-lora 4|8]
# 默认目标 ComfyUI:/mnt/workspace/comfy/ComfyUI;下载后自动 mv 到 models/ 各子目录(mv 省磁盘)
# 依赖:modelscope CLI(按文件粒度下载 + 断点续传)
# =============================================================================
set -euo pipefail

WORK_DIR="$(pwd)/Qwen-Image"
COMFY_DIR="/mnt/workspace/comfy/ComfyUI"
MODEL="2512"
LORA_STEPS=""  # 空=不下载 LoRA; 4|8=下载对应 Lightning LoRA

while [[ $# -gt 0 ]]; do
  case "$1" in
    --work-dir)  WORK_DIR="$2"; shift 2 ;;
    --comfy-dir) COMFY_DIR="$2"; shift 2 ;;
    --model)     MODEL="$2"; shift 2 ;;
    --with-lora) LORA_STEPS="$2"; shift 2 ;;
    *) echo "未知参数: $1"; exit 1 ;;
  esac
done

case "$MODEL" in
  base|2512|edit|layered|distill|all) : ;;
  *) echo "错误: --model 取值 base|2512|edit|layered|distill|all"; exit 1 ;;
esac
if [[ -n "$LORA_STEPS" ]] && [[ "$LORA_STEPS" != "4" && "$LORA_STEPS" != "8" ]]; then
  echo "错误: --with-lora 取值 4|8"; exit 1
fi

# 仓库 -> 短目录名(mv 阶段用)
REPO_T2I="Comfy-Org/Qwen-Image_ComfyUI"
REPO_EDIT="Comfy-Org/Qwen-Image-Edit_ComfyUI"
REPO_LAYERED="Comfy-Org/Qwen-Image-Layered_ComfyUI"
REPO_LORA="lightx2v/Qwen-Image-Lightning"

# 条目格式: 仓库|文件相对路径|目标 models/ 子目录
FILES=(
  "$REPO_T2I|split_files/text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors|text_encoders"
)

case "$MODEL" in
  base)
    FILES+=(
      "$REPO_T2I|split_files/diffusion_models/qwen_image_fp8_e4m3fn.safetensors|diffusion_models"
      "$REPO_T2I|split_files/vae/qwen_image_vae.safetensors|vae"
    ) ;;
  2512)
    FILES+=(
      "$REPO_T2I|split_files/diffusion_models/qwen_image_2512_fp8_e4m3fn.safetensors|diffusion_models"
      "$REPO_T2I|split_files/vae/qwen_image_vae.safetensors|vae"
    ) ;;
  edit)
    FILES+=(
      "$REPO_EDIT|split_files/diffusion_models/qwen_image_edit_fp8_e4m3fn.safetensors|diffusion_models"
      "$REPO_T2I|split_files/vae/qwen_image_vae.safetensors|vae"
    ) ;;
  layered)
    FILES+=(
      "$REPO_LAYERED|split_files/diffusion_models/qwen_image_layered_bf16.safetensors|diffusion_models"
      "$REPO_LAYERED|split_files/vae/qwen_image_layered_vae.safetensors|vae"
    ) ;;
  distill)
    FILES+=(
      "$REPO_T2I|non_official/diffusion_models/qwen_image_distill_full_fp8_e4m3fn.safetensors|diffusion_models"
      "$REPO_T2I|split_files/vae/qwen_image_vae.safetensors|vae"
    ) ;;
  all)
    FILES+=(
      "$REPO_T2I|split_files/diffusion_models/qwen_image_fp8_e4m3fn.safetensors|diffusion_models"
      "$REPO_T2I|split_files/diffusion_models/qwen_image_2512_fp8_e4m3fn.safetensors|diffusion_models"
      "$REPO_T2I|non_official/diffusion_models/qwen_image_distill_full_fp8_e4m3fn.safetensors|diffusion_models"
      "$REPO_EDIT|split_files/diffusion_models/qwen_image_edit_fp8_e4m3fn.safetensors|diffusion_models"
      "$REPO_LAYERED|split_files/diffusion_models/qwen_image_layered_bf16.safetensors|diffusion_models"
      "$REPO_LAYERED|split_files/vae/qwen_image_layered_vae.safetensors|vae"
      "$REPO_T2I|split_files/vae/qwen_image_vae.safetensors|vae"
    ) ;;
esac

if [[ -n "$LORA_STEPS" ]]; then
  LORA_NAME="Qwen-Image-Lightning-${LORA_STEPS}steps-V1.0.safetensors"
  FILES+=("$REPO_LORA|$LORA_NAME|loras")
fi

echo "==> 下载目录: $WORK_DIR | 模型: $MODEL | LoRA: ${LORA_STEPS:-无}"
echo "==> 目标 ComfyUI: $COMFY_DIR"
mkdir -p "$WORK_DIR"

# -----------------------------------------------------------------------------
# 逐个下载(目标文件已存在且非空则跳过)
# -----------------------------------------------------------------------------
echo ""
echo "==> 下载 ${#FILES[@]} 个文件"
for entry in "${FILES[@]}"; do
  repo="${entry%%|*}"; rest="${entry#*|}"; rel="${rest%%|*}"
  local_file="$WORK_DIR/$rel"
  if [ -f "$local_file" ] && [ -s "$local_file" ]; then
    echo "    跳过(已存在): $rel"
    continue
  fi
  echo "    -> [$repo] $rel"
  modelscope download --model "$repo" --local_dir "$WORK_DIR" "$rel"
done

echo ""
echo "✅ 下载完成。"

# -----------------------------------------------------------------------------
# 自动 mv 到 ComfyUI models/ 各子目录(mv 省磁盘;目标已存在则跳过)
# -----------------------------------------------------------------------------
if [ -d "$COMFY_DIR" ]; then
  echo ""
  echo "==> mv 到 $COMFY_DIR/models/"
  mkdir -p "$COMFY_DIR"/models/{diffusion_models,text_encoders,vae,loras}

  for entry in "${FILES[@]}"; do
    repo="${entry%%|*}"; rest="${entry#*|}"; rel="${rest%%|*}"; sub="${rest##*|}"
    src="$WORK_DIR/$rel"; dst="$COMFY_DIR/models/$sub/$(basename "$rel")"
    if [ ! -f "$src" ]; then
      echo "    ⚠ 未找到源文件: $src"
      continue
    fi
    if [ -e "$dst" ]; then echo "    跳过(已存在): $dst"; else mv "$src" "$dst"; echo "    mv → $dst"; fi
  done

  echo ""
  echo "✅ 已就位。Qwen-Image 工作流加载:"
  echo "   UNETLoader  : 对应版本扩散模型(qwen_image_*_fp8_e4m3fn.safetensors)"
  echo "   CLIPLoader  : qwen_2.5_vl_7b_fp8_scaled.safetensors"
  echo "   VAELoader   : qwen_image_vae.safetensors"
  if [[ -n "$LORA_STEPS" ]]; then
    echo "   采样参数    : steps=$LORA_STEPS(加速), 原版 50 步为佳"
  else
    echo "   采样参数    : steps=50, cfg 默认"
  fi
else
  echo ""
  echo "⚠ 未找到 $COMFY_DIR(下载文件仍在 $WORK_DIR/ 下)"
  echo "   部署 ComfyUI 后重跑本脚本,或手动 mv 到 models/ 各子目录"
fi
