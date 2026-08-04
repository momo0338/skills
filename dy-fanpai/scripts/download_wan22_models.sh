#!/usr/bin/env bash
# =============================================================================
# download_wan22_models.sh — 下载 Wan2.2 14B I2V 模型(modelscope,方案 A)
#
# 场景:纯产品图生视频(i2v)工作流,对应 ComfyUI 官方 Wan2.2 14B I2V 模板
# 来源:Comfy-Org/Wan_2.2_ComfyUI_Repackaged(官方教程文档核实 2026-08)
#
# 用法:
#   bash download_wan22_models.sh [--work-dir DIR] [--comfy-dir DIR]
# 选项:
#   --work-dir DIR   下载缓存目录,默认 ./Wan2.2
#   --comfy-dir DIR  ComfyUI 根目录;指定后自动把模型拷进 models/(可选)
# 依赖:modelscope CLI(modelscope download)
# =============================================================================
set -euo pipefail

WORK_DIR="$(pwd)/Wan2.2"
COMFY_DIR=""
MODEL_REPO="Comfy-Org/Wan_2.2_ComfyUI_Repackaged"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --work-dir)  WORK_DIR="$2";  shift 2 ;;
    --comfy-dir) COMFY_DIR="$2"; shift 2 ;;
    --only)      ONLY="$2";      shift 2 ;;   # i2v | t2v | both(默认 both)
    *) echo "未知参数: $1"; exit 1 ;;
  esac
done
ONLY="${ONLY:-both}"

# 公共文件:CLIP + VAE(两套工作流共用,只下一份)
COMMON_FILES=(
  "split_files/vae/wan_2.1_vae.safetensors"
  "split_files/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors"
)

# I2V 图生视频(方案 A,纯产品段主力,192GB 满配 fp16;各 26.6GB)
I2V_FILES=(
  "split_files/diffusion_models/wan2.2_i2v_high_noise_14B_fp16.safetensors"
  "split_files/diffusion_models/wan2.2_i2v_low_noise_14B_fp16.safetensors"
)

# T2V 文生视频(fp8;各 13.3GB,CLIP/VAE 与 I2V 共用)
T2V_FILES=(
  "split_files/diffusion_models/wan2.2_t2v_high_noise_14B_fp8_scaled.safetensors"
  "split_files/diffusion_models/wan2.2_t2v_low_noise_14B_fp8_scaled.safetensors"
)

FILES=("${COMMON_FILES[@]}")
case "$ONLY" in
  i2v)  FILES+=("${I2V_FILES[@]}") ;;
  t2v)  FILES+=("${T2V_FILES[@]}") ;;
  both) FILES+=("${I2V_FILES[@]}" "${T2V_FILES[@]}") ;;
  *) echo "错误: --only 取值 i2v|t2v|both"; exit 1 ;;
esac

echo "==> 下载目录: $WORK_DIR | 模式: $ONLY"
mkdir -p "$WORK_DIR"

# 下载每个文件(可断点续传;modelscope 按文件粒度,重复跑跳过已存在)
for f in "${FILES[@]}"; do
  echo "==> 下载 $f"
  modelscope download --model "$MODEL_REPO" --local_dir "$WORK_DIR" "$f"
done

echo ""
echo "✅ 下载完成,共 ${#FILES[@]} 个文件"
ls -lhR "$WORK_DIR/split_files" 2>/dev/null | head -30 || true

# -----------------------------------------------------------------------------
# 可选:自动拷贝到 ComfyUI models/ 目录
# -----------------------------------------------------------------------------
if [ -n "$COMFY_DIR" ]; then
  echo ""
  echo "==> 拷贝到 $COMFY_DIR/models/"
  mkdir -p "$COMFY_DIR"/models/{diffusion_models,text_encoders,vae}
  cp "$WORK_DIR"/split_files/diffusion_models/*.safetensors "$COMFY_DIR"/models/diffusion_models/
  cp "$WORK_DIR"/split_files/vae/*.safetensors               "$COMFY_DIR"/models/vae/
  cp "$WORK_DIR"/split_files/text_encoders/*.safetensors     "$COMFY_DIR"/models/text_encoders/
  echo "✅ 已拷贝。工作流加载时按类型选择:"
  echo "   I2V 工作流(图生视频):"
  echo "     Load Diffusion Model 1: wan2.2_i2v_high_noise_14B_fp16.safetensors"
  echo "     Load Diffusion Model 2: wan2.2_i2v_low_noise_14B_fp16.safetensors"
  echo "   T2V 工作流(文生视频):"
  echo "     Load Diffusion Model 1: wan2.2_t2v_high_noise_14B_fp8_scaled.safetensors"
  echo "     Load Diffusion Model 2: wan2.2_t2v_low_noise_14B_fp8_scaled.safetensors"
  echo "   共用: Load CLIP = umt5_xxl_fp8_e4m3fn_scaled.safetensors | Load VAE = wan_2.1_vae.safetensors"
else
  echo ""
  echo "提示:未指定 --comfy-dir,模型在 $WORK_DIR;"
  echo "     后续手动拷贝或重跑加 --comfy-dir /path/to/ComfyUI"
fi
