#!/usr/bin/env bash
# =============================================================================
# download_minimax_h3.sh — MiniMax H3 本地模型下载(I2V + R2V 双套)
#
# 方案(2026-08-04 决策):MiniMax H3 本地替代即梦,与 Wan2.2 对比后二选一。
#   - I2V(图生/首尾帧):MiniMaxH3ImageToVideo 节点(fl2va 模型)
#   - R2V(参考生,含音频参考驱动):MiniMaxH3ReferenceToVideo 节点(ref2va 模型)
#     —— R2V 支持参考音频驱动(口播段 mm 的正解,原生立体声)
#   - 文本编码器/VAE 三工作流共用
#
# 用法:
#   bash download_minimax_h3.sh [--work-dir DIR] [--comfy-dir DIR]
#   --only i2v|r2v|both(默认 both)
# 默认目标 ComfyUI:/workspace/ComfyUI;下载后自动 mv 到 models/ 各子目录(mv 省磁盘)
# 依赖:modelscope CLI
# =============================================================================
set -euo pipefail

WORK_DIR="$(pwd)/MiniMax-H3"
COMFY_DIR="/mnt/workspace/comfy/ComfyUI"  # 用户实机路径
ONLY="both"
MODEL_REPO="Comfy-Org/MiniMax-H3"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --work-dir)  WORK_DIR="$2"; shift 2 ;;
    --comfy-dir) COMFY_DIR="$2"; shift 2 ;;
    --only)      ONLY="$2"; shift 2 ;;
    *) echo "未知参数: $1"; exit 1 ;;
  esac
done

echo "==> 下载目录: $WORK_DIR | 模式: $ONLY"
echo "==> 目标 ComfyUI: $COMFY_DIR"
mkdir -p "$WORK_DIR"

# 公共文件:文本编码器 + 双 VAE(三个工作流共用,只下一份)
COMMON_FILES=(
  "text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors"
  "vae/minimax_h3_video_vae_fp16.safetensors"
  "vae/minimax_h3_audio_vae_fp32.safetensors"
)

# I2V/T2V: fl2va 扩散模型(首尾帧图生;19.53GB)
I2V_FILES=(
  "diffusion_models/minimax_h3_fl2va_pruned_int8_convrot.safetensors"
)

# R2V: ref2va 扩散模型(参考图/视频/音频驱动;19.53GB)
R2V_FILES=(
  "diffusion_models/minimax_h3_ref2va_pruned_int8_convrot.safetensors"
)

FILES=("${COMMON_FILES[@]}")
case "$ONLY" in
  i2v)  FILES+=("${I2V_FILES[@]}") ;;
  r2v)  FILES+=("${R2V_FILES[@]}") ;;
  both) FILES+=("${I2V_FILES[@]}" "${R2V_FILES[@]}") ;;
  *) echo "错误: --only 取值 i2v|r2v|both"; exit 1 ;;
esac

echo ""
echo "==> 下载 ${#FILES[@]} 个文件"
for f in "${FILES[@]}"; do
  echo "    -> $f"
  modelscope download --model "$MODEL_REPO" --local_dir "$WORK_DIR" "$f"
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

  for f in "$WORK_DIR"/diffusion_models/*.safetensors; do
    [ -e "$f" ] || continue
    dst="$COMFY_DIR/models/diffusion_models/$(basename "$f")"
    if [ -e "$dst" ]; then echo "    跳过(已存在): $dst"; else mv "$f" "$dst"; echo "    mv → $dst"; fi
  done
  for f in "$WORK_DIR"/text_encoders/*.safetensors; do
    [ -e "$f" ] || continue
    dst="$COMFY_DIR/models/text_encoders/$(basename "$f")"
    if [ -e "$dst" ]; then echo "    跳过(已存在): $dst"; else mv "$f" "$dst"; echo "    mv → $dst"; fi
  done
  for f in "$WORK_DIR"/vae/*.safetensors; do
    [ -e "$f" ] || continue
    dst="$COMFY_DIR/models/vae/$(basename "$f")"
    if [ -e "$dst" ]; then echo "    跳过(已存在): $dst"; else mv "$f" "$dst"; echo "    mv → $dst"; fi
  done

  echo "✅ 已就位。MiniMax H3 工作流加载:"
  echo "   I2V/T2V: diffusion = minimax_h3_fl2va_pruned_int8_convrot.safetensors"
  echo "   R2V    : diffusion = minimax_h3_ref2va_pruned_int8_convrot.safetensors"
  echo "   共用   : qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors + 双 VAE"
else
  echo ""
  echo "⚠ 未找到 $COMFY_DIR(下载文件仍在 $WORK_DIR/ 下)"
  echo "   部署 ComfyUI 后重跑本脚本,或手动 mv 到 models/ 各子目录"
fi
