#!/bin/bash
# ============================================================
# transcribe_batch.sh — whisper.cpp 批量转写
# 用法:
#   bash transcribe_batch.sh <音频目录> <输出目录> ["跳过id1 id2"] ["提示词,逗号分隔"]
#
# 示例:
#   bash transcribe_batch.sh ./audio ./transcripts "7670345621838327729 7671846982315421947" \
#     "千川,全域推广,追投,商品卡,千展,冷启动,ROI,GMV,素材,计划,直播间,代投,跑量,抖店"
# ============================================================

set -euo pipefail

SRC="${1:?用法: transcribe_batch.sh <音频目录> <输出目录> [跳过id] [提示词]}"
OUT="${2:?用法: transcribe_batch.sh <音频目录> <输出目录> [跳过id] [提示词]}"
SKIP="${3:-}"
PROMPT="${4:-千川,全域推广,追投,商品卡,千展,冷启动,ROI,GMV,素材,计划,直播间,代投,跑量,抖店}"

MODEL="${WHISPER_MODEL:-$HOME/whisper.cpp/models/ggml-large-v3-turbo.bin}"

# --- 前置检查 ---
command -v whisper-cli >/dev/null 2>&1 || { echo "错误: whisper-cli 未安装 (brew install whisper-cpp)"; exit 1; }
[ -f "$MODEL" ] || { echo "错误: 模型不存在: $MODEL (见 references/model-download.md)"; exit 1; }
mkdir -p "$OUT"

# --- 批量转写 ---
count=0; skip_count=0; fail=0
shopt -s nullglob
for f in "$SRC"/*.wav "$SRC"/*.mp3 "$SRC"/*.flac "$SRC"/*.m4a; do
  [ -e "$f" ] || continue
  id=$(basename "$f")
  id="${id%.*}"

  # 跳过列表
  if [ -n "$SKIP" ]; then
    if echo " $SKIP " | grep -q " $id "; then
      echo "SKIP $id"; skip_count=$((skip_count+1)); continue
    fi
  fi

  # 已存在则跳过（断点续跑）
  if [ -f "$OUT/$id.txt" ] && [ -s "$OUT/$id.txt" ]; then
    echo "EXISTS $id (跳过)"
    count=$((count+1)); continue
  fi

  echo "=== $id ==="
  if whisper-cli -m "$MODEL" -l zh --prompt "$PROMPT" \
      -f "$f" -otxt -of "$OUT/$id" 2>/dev/null; then
    echo "  OK -> $OUT/$id.txt ($(wc -m < "$OUT/$id.txt" 2>/dev/null) 字符)"
    count=$((count+1))
  else
    echo "  FAIL $id"
    fail=$((fail+1))
  fi
done

echo "=================================="
echo "完成: 成功 $count / 跳过 $skip_count / 失败 $fail"
echo "输出目录: $OUT"
[ "$fail" -gt 0 ] && exit 1 || exit 0
