#!/usr/bin/env bash
# =============================================================================
# run_comfyui_nvidia.sh — Ubuntu + NVIDIA 环境启动 ComfyUI（CUDA 最优参数版）
#
# 适用: Ubuntu + NVIDIA 显卡(消费级 RTX / 数据中心 A100-H100 均适配),CUDA torch。
# 说明: 与 run_comfyui.sh(AMD/双平台通用版)不同,本脚本只面向 NVIDIA:
#   - --fp16-vae 默认开启(VAE 半精度,NVIDIA 上更快更稳;AMD 粉红问题不存在)
#   - --cuda-malloc 开启(显存复用优化,减少分配抖动;新版参数,自动兼容旧版)
#   - --highvram 自动决策: 显存 >= 32GB 自动开(跑 14B 视频模型),否则关(消费卡)
#   - 注意力后端: flash-attn > xformers > split-cross-attention(自动探测)
#   - 崩溃排查注释改为 NVIDIA 语境
#
# ★ Python 环境选择优先级(2026-08-06 调整):
#   1) 系统 python3: 有 torch + CUDA + comfy 依赖 → 直接用系统 python 运行
#      (DSW/预装环境常见,零安装即跑)
#   2) venv(env/ .venv): 系统不满足时切换;venv 满足 → 在 venv 运行
#   3) venv 自动安装: venv 缺 torch/依赖 → 按需安装
#      (CUDA torch + requirements.txt + flash-attn/xformers 可选)后运行
#   4) 都没有 → 明确报错提示
#
# 用法:
#   bash run_comfyui_nvidia.sh [--port 8188] [--workspace /path/to/comfy]
# 环境变量(可用 export 覆盖):
#   COMFY_WORK   : ComfyUI 父目录,默认 $(pwd)/comfy 或 /mnt/workspace/comfy(自动探测)
#   COMFY_PORT   : 监听端口,默认 8188
#   COMFY_ATTN   : auto|flash|xformers|sdpa(默认 auto=自动探测)
#   COMFY_HIGHVRAM: auto|1|0(默认 auto=按显存自动)
#   COMFY_FP16_VAE: 1|0(默认 1=NVIDIA 开启)
#   COMFY_CUDA_MALLOC: 1|0(默认 1=开启)
#   COMFY_CORS    : 1|0(默认 1=开启 --enable-cors-header,允许跨域访问 API)
#   COMFY_CUDA_VERSION: 安装用 CUDA 轮子版本,默认 cu128
#   COMFY_NO_INSTALL: 1=禁用自动安装(仅检查与提示)
# =============================================================================
set -uo pipefail

# ---- 参数解析 ----
COMFY_PORT="${COMFY_PORT:-8188}"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --port)       COMFY_PORT="${2:?--port 需要端口}"; shift 2 ;;
    --port=*)     COMFY_PORT="${1#*=}"; shift ;;
    --workspace)  COMFY_WORK="${2:?--workspace 需要路径}"; shift 2 ;;
    --workspace=*) COMFY_WORK="${1#*=}"; shift ;;
    -h|--help)    sed -n '3,18p' "$0" | sed 's/^# *//'; exit 0 ;;
    *) echo "未知参数: $1 (--port / --workspace / -h)"; exit 1 ;;
  esac
done

# ---- 工作目录探测(默认 /mnt/workspace/comfy,兼容 DSW;可 --workspace 覆盖)----
if [ -z "${COMFY_WORK:-}" ]; then
  for cand in /mnt/workspace/comfy "$HOME/comfy" "$(pwd)/comfy"; do
    if [ -d "$cand/ComfyUI" ]; then COMFY_WORK="$cand"; break; fi
  done
  COMFY_WORK="${COMFY_WORK:-/mnt/workspace/comfy}"
fi
COMFY_DIR="$COMFY_WORK/ComfyUI"
if [ ! -d "$COMFY_DIR" ]; then
  echo "❌ 未找到 ComfyUI: $COMFY_DIR"
  echo "   请先运行: bash install_comfyui_cuda.sh --workspace $COMFY_WORK"
  exit 1
fi

cd "$COMFY_DIR" || exit 1

# ---- Python 环境选择（2026-08-06：系统优先 → venv 回退 → venv 自动安装）----
CUDA_VER="${COMFY_CUDA_VERSION:-cu128}"

# 环境可用性检查: 有 torch + CUDA 支持 + 可导入 comfy(在 ComfyUI 目录下)
env_ok() {
  local py="$1"
  (cd "$COMFY_DIR" && "$py" -c \
    "import torch; assert torch.version.cuda, 'no-cuda'; import comfy; print('OK')" \
    >/dev/null 2>&1)
}
env_cuda() {  # 有 CUDA torch 但可能缺 comfy 依赖(可安装补齐)
  local py="$1"
  "$py" -c "import torch; assert torch.version.cuda, 'no-cuda'" >/dev/null 2>&1
}

PYTHON_BIN=""
SYS_PY="$(command -v python3 || echo "")"

echo "--------------------------------------------------------------"
echo "==> [1/3] 检查系统 python3"
if [ -n "$SYS_PY" ] && env_ok "$SYS_PY"; then
  echo "    ✅ $SYS_PY 满足(torch+CUDA+comfy),直接用系统 python 运行"
  PYTHON_BIN="$SYS_PY"
elif [ -n "$SYS_PY" ] && env_cuda "$SYS_PY"; then
  echo "    ⚠️  $SYS_PY 有 CUDA torch 但缺 comfy 依赖"
  if [ "${COMFY_NO_INSTALL:-0}" != "1" ]; then
    echo "    → 尝试补齐 comfy 依赖(requirements.txt)"
    (cd "$COMFY_DIR" && "$SYS_PY" -m pip install -r requirements.txt >/dev/null 2>&1 \
      && echo "    ✅ 依赖补齐,系统 python 可用" && PYTHON_BIN="$SYS_PY")
    if [ -z "$PYTHON_BIN" ] && env_ok "$SYS_PY"; then PYTHON_BIN="$SYS_PY"; fi
  fi
else
  echo "    ❌ 系统 python3 不满足(无 CUDA torch 或无 comfy 依赖)"
fi

# ---- 系统不满足 → 切 venv ----
if [ -z "$PYTHON_BIN" ]; then
  VENV_PY=""
  if [ -x "$COMFY_WORK/env/bin/python" ]; then
    VENV_PY="$COMFY_WORK/env/bin/python"; VENV_NAME="env"
  elif [ -x "$COMFY_DIR/.venv/bin/python" ]; then
    VENV_PY="$COMFY_DIR/.venv/bin/python"; VENV_NAME=".venv"
  fi

  echo "--------------------------------------------------------------"
  echo "==> [2/3] 检查 venv(${VENV_NAME:-无})"
  if [ -n "$VENV_PY" ]; then
    if env_ok "$VENV_PY"; then
      echo "    ✅ $VENV_PY 满足,在 venv 环境运行"
      PYTHON_BIN="$VENV_PY"
    elif env_cuda "$VENV_PY"; then
      echo "    ⚠️  venv 有 CUDA torch 但缺 comfy 依赖"
      if [ "${COMFY_NO_INSTALL:-0}" != "1" ]; then
        (cd "$COMFY_DIR" && "$VENV_PY" -m pip install -r requirements.txt >/dev/null 2>&1 \
          && echo "    ✅ 依赖补齐" && PYTHON_BIN="$VENV_PY")
      fi
    else
      echo "    ❌ venv 无 CUDA torch"
    fi
  else
    echo "    ⚠️  未找到 venv(env/ 或 .venv/)"
  fi
fi

# ---- venv 无 CUDA torch → 自动安装（建 venv + CUDA torch + 依赖）----
if [ -z "$PYTHON_BIN" ]; then
  echo "--------------------------------------------------------------"
  echo "==> [3/3] 准备 venv 环境并安装 CUDA torch"
  if [ "${COMFY_NO_INSTALL:-0}" == "1" ]; then
    echo "❌ COMFY_NO_INSTALL=1 禁止安装,且无可运行环境。请手动安装后重试。"
    exit 1
  fi
  # 优先用现有 venv; 没有则新建
  if [ -n "$VENV_PY" ]; then
    VENV_PYTHON="$VENV_PY"
    echo "    复用 venv: ${VENV_PYTHON}"
  else
    # 系统有 venv 模块就新建 ComfyUI/.venv
    if [ -n "$SYS_PY" ] && "$SYS_PY" -m venv --help >/dev/null 2>&1; then
      VENV_PYTHON="$COMFY_DIR/.venv/bin/python"
      "$SYS_PY" -m venv "$COMFY_DIR/.venv" 2>/dev/null \
        && echo "    新建 venv: $COMFY_DIR/.venv" || { echo "❌ 建 venv 失败"; exit 1; }
    else
      echo "❌ 系统 python3 无 venv 模块,无法建 venv。请手动安装 CUDA torch:"
      echo "   pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/$CUDA_VER"
      exit 1
    fi
  fi
  echo "    安装 CUDA $CUDA_VER torch…"
  "$VENV_PYTHON" -m pip install --upgrade pip >/dev/null 2>&1
  "$VENV_PYTHON" -m pip install torch torchvision torchaudio \
    --index-url "https://download.pytorch.org/whl/$CUDA_VER" || {
      echo "❌ torch 安装失败。检查网络/驱动后重试,或手动:";
      echo "   pip install torch --index-url https://download.pytorch.org/whl/$CUDA_VER"; exit 1; }
  echo "    安装 ComfyUI 依赖…"
  (cd "$COMFY_DIR" && "$VENV_PYTHON" -m pip install -r requirements.txt) >/dev/null 2>&1 \
    || echo "    ⚠️ requirements 部分失败(继续,启动时可能报缺依赖)"
  # 可选加速
  "$VENV_PYTHON" -m pip install flash-attn >/dev/null 2>&1 \
    && echo "    ✅ flash-attn 已装" || echo "    (flash-attn 可选,跳过)"
  if env_ok "$VENV_PYTHON"; then
    echo "    ✅ venv 环境就绪"
    PYTHON_BIN="$VENV_PYTHON"
  else
    echo "❌ venv 安装后仍不满足(torch/CUDA/comfy)。请人工检查:"
    echo "   $VENV_PYTHON -c \"import torch; print(torch.__version__, torch.version.cuda)\""
    exit 1
  fi
fi

echo "--------------------------------------------------------------"
echo "==> 使用环境: $PYTHON_BIN"

# ---- 前置校验: CUDA torch + nvidia-smi ----
TORCH_CUDA=$("$PYTHON_BIN" -c "import torch; print(torch.version.cuda or '')" 2>/dev/null || echo "")
if [ -z "$TORCH_CUDA" ]; then
  echo "❌ $PYTHON_BIN 内 torch 无 CUDA 支持(torch.version.cuda 为空)。"
  echo "   请确认用 CUDA 版 torch: pip install torch --index-url https://download.pytorch.org/whl/$CUDA_VER"
  exit 1
fi
if ! command -v nvidia-smi >/dev/null 2>&1; then
  echo "❌ 未找到 nvidia-smi。确认 NVIDIA 驱动已装: nvidia-smi"
  exit 1
fi
echo "==> torch.cuda=$TORCH_CUDA"

# 显存探测(GB,取第一块卡;多卡环境取最大可用)
VRAM_GB=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits 2>/dev/null \
  | sort -n | tail -1 | awk '{print int($1/1024)}')
echo "==> GPU 显存(最大卡): ${VRAM_GB}GB"

# 国内 HF 镜像
export HF_ENDPOINT=https://hf-mirror.com

# ---- CUDA 显存分配: 分段可扩展 + cuda-malloc(默认开)----
export PYTORCH_CUDA_ALLOC_CONF="expandable_segments:True"
CUDA_MALLOC=""
if [[ "${COMFY_CUDA_MALLOC:-1}" == "1" ]]; then
  # 参数名版本差异: 新版 ComfyUI 用 --cuda-malloc,旧版用 --enable-cuda-malloc
  # (2026-08-06 A10 实机: 0.30 版报 unrecognized --enable-cuda-malloc → 用新版名)
  if "$PYTHON_BIN" main.py --help 2>&1 | grep -q -- "--cuda-malloc"; then
    CUDA_MALLOC="--cuda-malloc"
    echo "==> 启用 --cuda-malloc(新版参数,显存复用)"
  else
    CUDA_MALLOC="--enable-cuda-malloc"
    echo "==> 启用 --enable-cuda-malloc(旧版参数,显存复用)"
  fi
fi

# ---- VAE: NVIDIA 上 fp16 默认开(更快更稳)----
FP16_VAE=""
if [[ "${COMFY_FP16_VAE:-1}" == "1" ]]; then
  FP16_VAE="--fp16-vae"
  echo "==> 启用 --fp16-vae(NVIDIA 半精度 VAE)"
fi

# ---- 注意力后端: flash-attn > xformers > sdpa ----
ATTN_ARGS=""
case "${COMFY_ATTN:-auto}" in
  flash) ATTN_ARGS="--use-flash-attention"; echo "==> 强制 --use-flash-attention" ;;
  xformers) ATTN_ARGS="--use-split-cross-attention"; echo "==> 强制 sdpa(xformers 新版自动启用)" ;;
  sdpa)  ATTN_ARGS="--use-split-cross-attention"; echo "==> 强制 sdpa(--use-split-cross-attention)" ;;
  auto)
    if "$PYTHON_BIN" -c "import flash_attn" >/dev/null 2>&1; then
      ATTN_ARGS="--use-flash-attention"
      echo "==> 检测到 flash_attn,启用 --use-flash-attention(最快)"
    elif "$PYTHON_BIN" -c "import xformers" >/dev/null 2>&1; then
      ATTN_ARGS=""  # 新版 ComfyUI 自动启用 xformers,无需传参
      echo "==> 检测到 xformers,自动启用"
    else
      ATTN_ARGS="--use-split-cross-attention"
      echo "==> 未找到 flash_attn/xformers,回退 sdpa"
    fi
    ;;
esac

# ---- 显存模式: 大显存自动 --highvram(14B 视频模型需要),消费卡默认关 ----
VRAM_ARGS=""
case "${COMFY_HIGHVRAM:-auto}" in
  1) VRAM_ARGS="--highvram --disable-async-offload"; echo "==> 强制 --highvram" ;;
  0) VRAM_ARGS=""; echo "==> 强制关闭 --highvram" ;;
  auto)
    if [ "${VRAM_GB:-0}" -ge 32 ]; then
      VRAM_ARGS="--highvram --disable-async-offload"
      echo "==> 显存>=32GB,启用 --highvram(14B 模型常驻)"
    else
      VRAM_ARGS=""
      echo "==> 显存<32GB,默认关闭 --highvram(按需加载)"
    fi
    ;;
esac

echo "================================================================"
echo "==> 启动 ComfyUI: 端口 $COMFY_PORT | CUDA $TORCH_CUDA | 显存 ${VRAM_GB}GB"
echo "================================================================"

# --disable-auto-launch: 无浏览器环境,禁止自动拉起浏览器
# --listen 0.0.0.0:      允许远程访问(供 dy-fanpai 调用)
# --enable-cors-header:  允许浏览器/API 跨域访问(COMFY_CORS=0 可关)
CORS_ARGS=""
if [[ "${COMFY_CORS:-1}" == "1" ]]; then
  CORS_ARGS="--enable-cors-header"
  echo "==> 启用 --enable-cors-header(允许跨域访问 API)"
fi
"$PYTHON_BIN" main.py --listen 0.0.0.0 --port "$COMFY_PORT" \
  --disable-auto-launch \
  $VRAM_ARGS $ATTN_ARGS $FP16_VAE $CUDA_MALLOC $CORS_ARGS

# ── NVIDIA 崩溃排查速查 ─────────────────────────────────────────────
# 1) CUDA OOM / 显存不足:
#      → 关闭 --highvram(COMFY_HIGHVRAM=0),或换 fp8 权重(int8 H3 已省显存)
# 2) "CUDA error: out of memory" 持续:
#      → COMFY_CUDA_MALLOC=0 bash run_comfyui_nvidia.sh 关掉 cuda-malloc 再试
# 3) 驱动与 torch 版本不匹配(启动即崩):
#      → nvidia-smi 看驱动版本; 按 CUDA 版本重装 torch:
#        pip install torch --index-url https://download.pytorch.org/whl/cu128
# 4) 画面粉红/噪点(罕见,NVIDIA 上多为显存不足静默降精度):
#      → COMFY_FP16_VAE=0 关闭 fp16-vae 排查
