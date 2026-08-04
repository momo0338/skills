#!/usr/bin/env bash
# =============================================================================
# download_z_image_models.sh — Z-Image-Turbo 模型下载(ComfyUI 单文件打包版)
#
# 方案(2026-08-04 决策):先用 Z-Image-Turbo 跑通 ComfyUI 验证,后续要微调再切 Base。
# 官方 ComfyUI 教程(z-image-turbo)基础文生图工作流仅需 3 个文件:
#   - text_encoders/qwen_3_4b.safetensors            (文本编码器 Qwen3-4B,~8.0GB)
#   - diffusion_models/z_image_turbo_bf16.safetensors(扩散模型 6B bf16,~12.3GB)
#   - vae/ae.safetensors                             (Flux1 VAE,~335MB)
#   合计 ≈ 20.7GB。生成参数:8 步(最少 4 步),CFG=0.0,无需负提示词。
#
# 仓库:Comfy-Org/z_image_turbo(HF 与 ModelScope 双镜像,文件结构一致:
#       split_files/{text_encoders,diffusion_models,vae}/)
# 可选量化版(小显存机器):
#   --diffusion int8(6.2G)/nvfp4(4.5G);--te fp8(5.6G)/fp4(3.5G)
#   本机 MI308X 205GB 显存,默认全用 bf16 即可。
# 可选蒸馏 patch LoRA(z_image_turbo_distill_patch_lora_bf16,151MB)官方基础
#   工作流不需要,本脚本不下载。
#
# 用法:
#   bash download_z_image_models.sh [--work-dir DIR] [--comfy-dir DIR]
#       [--diffusion bf16|int8|nvfp4] [--te bf16|fp8|fp4]
# 默认目标 ComfyUI:/mnt/workspace/comfy/ComfyUI;下载后自动 mv 到 models/ 各子目录(mv 省磁盘)
# 依赖:modelscope CLI(支持按文件粒度下载 + 断点续传)
# =============================================================================
set -euo pipefail

WORK_DIR="$(pwd)/Z-Image-Turbo"
COMFY_DIR="/mnt/workspace/comfy/ComfyUI"
DIFFUSION="bf16"
TE="bf16"
MODEL_REPO="Comfy-Org/z_image_turbo"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --work-dir)   WORK_DIR="$2"; shift 2 ;;
    --comfy-dir)  COMFY_DIR="$2"; shift 2 ;;
    --diffusion)  DIFFUSION="$2"; shift 2 ;;
    --te)         TE="$2"; shift 2 ;;
    *) echo "未知参数: $1"; exit 1 ;;
  esac
done

case "$DIFFUSION" in
  bf16)  DM_FILE="split_files/diffusion_models/z_image_turbo_bf16.safetensors" ;;
  int8)  DM_FILE="split_files/diffusion_models/z_image_turbo_int8_convrot.safetensors" ;;
  nvfp4) DM_FILE="split_files/diffusion_models/z_image_turbo_nvfp4.safetensors" ;;
  *) echo "错误: --diffusion 取值 bf16|int8|nvfp4"; exit 1 ;;
esac

case "$TE" in
  bf16) TE_FILE="split_files/text_encoders/qwen_3_4b.safetensors" ;;
  fp8)  TE_FILE="split_files/text_encoders/qwen_3_4b_fp8_mixed.safetensors" ;;
  fp4)  TE_FILE="split_files/text_encoders/qwen_3_4b_fp4_mixed.safetensors" ;;
  *) echo "错误: --te 取值 bf16|fp8|fp4"; exit 1 ;;
esac

# 源相对路径(含 split_files/) -> 目标 models/ 子目录
FILES=(
  "$TE_FILE|text_encoders"
  "$DM_FILE|diffusion_models"
  "split_files/vae/ae.safetensors|vae"
)

echo "==> 下载目录: $WORK_DIR | diffusion=$DIFFUSION | te=$TE"
echo "==> 目标 ComfyUI: $COMFY_DIR"
mkdir -p "$WORK_DIR"

# -----------------------------------------------------------------------------
# 逐个下载(目标文件已存在则跳过)
# -----------------------------------------------------------------------------
echo ""
echo "==> 下载 ${#FILES[@]} 个文件"
for entry in "${FILES[@]}"; do
  rel="${entry%%|*}"
  local_file="$WORK_DIR/$rel"
  if [ -f "$local_file" ] && [ -s "$local_file" ]; then
    echo "    跳过(已存在): $rel"
    continue
  fi
  echo "    -> $rel"
  modelscope download --model "$MODEL_REPO" --local_dir "$WORK_DIR" "$rel"
done

echo ""
echo "✅ 下载完成。"

# -----------------------------------------------------------------------------
# 自动 mv 到 ComfyUI models/ 各子目录(mv 省磁盘;目标已存在则跳过)
# -----------------------------------------------------------------------------
if [ -d "$COMFY_DIR" ]; then
  echo ""
  echo "==> mv 到 $COMFY_DIR/models/"
  mkdir -p "$COMFY_DIR"/models/{diffusion_models,text_encoders,vae}

  for entry in "${FILES[@]}"; do
    rel="${entry%%|*}"; sub="${entry##*|}"
    src="$WORK_DIR/$rel"; dst="$COMFY_DIR/models/$sub/$(basename "$rel")"
    if [ ! -f "$src" ]; then
      echo "    ⚠ 未找到源文件: $src"
      continue
    fi
    if [ -e "$dst" ]; then echo "    跳过(已存在): $dst"; else mv "$src" "$dst"; echo "    mv → $dst"; fi
  done

  echo ""
  echo "✅ 已就位。Z-Image-Turbo 文生图工作流加载:"
  echo "   UNETLoader      : $(basename "${DM_FILE##*/}")"
  echo "   CLIPLoader      : $(basename "${TE_FILE##*/}") (type=z_image)"
  echo "   VAELoader       : ae.safetensors"
  echo "   采样参数        : steps=8(最少4), cfg=0.0, 负提示词留空"
else
  echo ""
  echo "⚠ 未找到 $COMFY_DIR(下载文件仍在 $WORK_DIR/split_files/ 下)"
  echo "   部署 ComfyUI 后重跑本脚本,或手动 mv 到 models/ 各子目录"
fi
