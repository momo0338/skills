#!/usr/bin/env bash
# =============================================================================
# download_wan22_models.sh — ComfyUI 最终模型下载(方案:只用 I2V,替代即梦)
#
# 结论(2026-08-04 核实):翻拍管线只需「图生视频 I2V」,不需要 T2V(文生)。
#   - i2v 段(纯产品):Wan2.2 14B I2V fp16(真实产品图 → 视频)
#   - mm 段(口播):Wan2.2 I2V 生成画面 + LatentSync 音频口型(可选,Part 2)
#
# 用法:
#   bash download_wan22_models.sh                    # 下到 ./Wan2.2
#   bash download_wan22_models.sh --latentsync       # 额外下载口型模型
# 默认目标 ComfyUI:/workspace/ComfyUI(可用 --comfy-dir 覆盖)
# 下载完成后自动 mv 到 ComfyUI/models/ 各子目录(mv 不复制,省磁盘)
# 依赖:modelscope CLI(modelscope download)
# =============================================================================
set -euo pipefail

WORK_DIR="$(pwd)/Wan2.2"
COMFY_DIR="/mnt/workspace/comfy/ComfyUI"  # 用户实机路径(默认);可用 --comfy-dir 覆盖
DO_LATENTSYNC=0
MODEL_REPO="Comfy-Org/Wan_2.2_ComfyUI_Repackaged"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --work-dir)    WORK_DIR="$2"; shift 2 ;;
    --comfy-dir)   COMFY_DIR="$2"; shift 2 ;;
    --latentsync)  DO_LATENTSYNC=1; shift ;;
    *) echo "未知参数: $1"; exit 1 ;;
  esac
done

echo "==> 下载目录: $WORK_DIR"
echo "==> 目标 ComfyUI: $COMFY_DIR"
mkdir -p "$WORK_DIR"

# -----------------------------------------------------------------------------
# Part 1: Wan2.2 14B I2V(纯产品段主力;fp16 最高质量,192GB 显存满配)
#         6 个文件 ≈ 59.7GB(全部必需,缺一不可)
# -----------------------------------------------------------------------------
I2V_FILES=(
  "split_files/diffusion_models/wan2.2_i2v_high_noise_14B_fp16.safetensors"
  "split_files/diffusion_models/wan2.2_i2v_low_noise_14B_fp16.safetensors"
  "split_files/vae/wan_2.1_vae.safetensors"
  "split_files/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors"
  "split_files/loras/wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise.safetensors"
  "split_files/loras/wan2.2_i2v_lightx2v_4steps_lora_v1_low_noise.safetensors"
)

echo ""
echo "==> [Part 1] 下载 Wan2.2 14B I2V(6 文件 ≈ 59.7GB)"
for f in "${I2V_FILES[@]}"; do
  echo "    -> $f"
  modelscope download --model "$MODEL_REPO" --local_dir "$WORK_DIR" "$f"
done

# -----------------------------------------------------------------------------
# Part 2(可选): LatentSync 1.6 口型模型(mm 段口播用)
#         文件在 HuggingFace(部分需仓库访问权;Enhanced 版标准路径如下)
# -----------------------------------------------------------------------------
if [ "$DO_LATENTSYNC" = "1" ]; then
  echo ""
  echo "==> [Part 2] 下载 LatentSync 1.6 口型模型"
  LS_DIR="$COMFY_DIR/models/checkpoints/LatentSync-1.6"
  mkdir -p "$LS_DIR"/{whisper,vae}
  if command -v huggingface-cli >/dev/null 2>&1; then
    huggingface-cli download ByteDance/LatentSync-1.6 \
      latentsync_unet.pt \
      whisper/tiny.pt \
      vae/config.json \
      vae/diffusion_pytorch_model.safetensors \
      --local-dir "$LS_DIR" || echo "⚠ LatentSync 仓库可能需访问权限,请手动下载(见下方提示)"
  else
    echo "⚠ 未安装 huggingface-cli,请手动下载:"
    echo "   https://huggingface.co/ByteDance/LatentSync-1.6"
    echo "   放到 $LS_DIR/ (latentsync_unet.pt + whisper/tiny.pt + vae/)"
  fi
fi

echo ""
echo "✅ 下载完成。"

# -----------------------------------------------------------------------------
# 自动 mv 到 ComfyUI models/ 各子目录(mv 省磁盘;目标已存在则跳过并提示)
# -----------------------------------------------------------------------------
if [ -d "$COMFY_DIR" ]; then
  echo ""
  echo "==> mv 到 $COMFY_DIR/models/"
  mkdir -p "$COMFY_DIR"/models/{diffusion_models,text_encoders,vae,loras}

  for f in "$WORK_DIR"/split_files/diffusion_models/*.safetensors; do
    [ -e "$f" ] || continue
    dst="$COMFY_DIR/models/diffusion_models/$(basename "$f")"
    if [ -e "$dst" ]; then echo "    跳过(已存在): $dst"; else mv "$f" "$dst"; echo "    mv → $dst"; fi
  done
  for f in "$WORK_DIR"/split_files/text_encoders/*.safetensors; do
    [ -e "$f" ] || continue
    dst="$COMFY_DIR/models/text_encoders/$(basename "$f")"
    if [ -e "$dst" ]; then echo "    跳过(已存在): $dst"; else mv "$f" "$dst"; echo "    mv → $dst"; fi
  done
  for f in "$WORK_DIR"/split_files/vae/*.safetensors; do
    [ -e "$f" ] || continue
    dst="$COMFY_DIR/models/vae/$(basename "$f")"
    if [ -e "$dst" ]; then echo "    跳过(已存在): $dst"; else mv "$f" "$dst"; echo "    mv → $dst"; fi
  done
  for f in "$WORK_DIR"/split_files/loras/*.safetensors; do
    [ -e "$f" ] || continue
    dst="$COMFY_DIR/models/loras/$(basename "$f")"
    if [ -e "$dst" ]; then echo "    跳过(已存在): $dst"; else mv "$f" "$dst"; echo "    mv → $dst"; fi
  done

  echo "✅ 已就位。I2V 工作流加载:"
  echo "   - UNETLoader high: wan2.2_i2v_high_noise_14B_fp16.safetensors"
  echo "   - UNETLoader low : wan2.2_i2v_low_noise_14B_fp16.safetensors"
  echo "   - CLIPLoader     : umt5_xxl_fp8_e4m3fn_scaled.safetensors (type=wan)"
  echo "   - VAELoader      : wan_2.1_vae.safetensors"
  echo "   - LoRA(4步)      : wan2.2_i2v_lightx2v_4steps_lora_v1_*"
else
  echo ""
  echo "⚠ 未找到 $COMFY_DIR(下载文件仍在 $WORK_DIR/split_files/ 下)"
  echo "   部署 ComfyUI 后重跑本脚本,或手动 mv 到 models/ 各子目录"
fi
