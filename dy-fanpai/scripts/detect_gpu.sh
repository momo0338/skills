#!/usr/bin/env bash
# =============================================================================
# detect_gpu.sh — GPU 厂商检测公共函数库(仅供 source,不可直接执行)
#
# 供 install_comfyui.sh / install_comfyui_cuda.sh / install_comfyui_rocm.sh /
# run_comfyui.sh 共用,保证"检测口径"在安装与启动两端完全一致。
#
# 用法:
#   source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/detect_gpu.sh"
#   GPU_TYPE=$(detect_gpu)              # 输出: nvidia | amd | unknown
#   describe_gpu "$GPU_TYPE"            # 打印人类可读描述(也可不传参自动探测)
#
# 可选: 传入 python 解释器路径,优先用它探测已装 torch(如 venv 内 python):
#   GPU_TYPE=$(detect_gpu /path/to/venv/bin/python)
#
# 检测优先级(由强到弱):
#   1. 指定/系统 python 已装 torch → torch.version.cuda / torch.version.hip(最准)
#   2. 厂商驱动工具 → nvidia-smi(英伟达) / rocm-smi|rocminfo(AMD)
#   3. lspci 硬件枚举兜底(无 lspci 或均未命中 → unknown)
# 检测依据会以 "(检测依据: ...)" 打印到 stderr,不影响 stdout 捕获。
#
# 环境变量 COMFY_GPU 可强制指定(auto|nvidia|amd|cpu),跳过探测;
#   cpu 仅在无可用 GPU 时手动降级使用,安装侧会给出警告。
# =============================================================================

detect_gpu() {
  local py="${1:-python3}" hip="" cuda="" pci=""

  # 0) 手动强制指定(最高优先级,便于 CI / 无 GPU 机器 / 出问题兜底)
  case "${COMFY_GPU:-auto}" in
    nvidia)  echo "nvidia";  echo "    (检测依据: COMFY_GPU 手动指定)" >&2; return 0 ;;
    amd)     echo "amd";     echo "    (检测依据: COMFY_GPU 手动指定)" >&2; return 0 ;;
    cpu)     echo "cpu";     echo "    (检测依据: COMFY_GPU 手动指定)" >&2; return 0 ;;
    auto) : ;;
    *)
      echo "⚠️  COMFY_GPU='$COMFY_GPU' 取值非法(应为 auto|nvidia|amd|cpu),按 auto 探测" >&2
      ;;
  esac

  # 1) 已有 torch 最准:镜像/环境预装什么底层,就用什么路线,绝不与硬件打架
  if command -v "$py" >/dev/null 2>&1; then
    hip=$("$py" -c "import torch; print(torch.version.hip or '')" 2>/dev/null || echo "")
    cuda=$("$py" -c "import torch; print(torch.version.cuda or '')" 2>/dev/null || echo "")
    if [ -n "$hip" ]; then
      echo "amd"
      echo "    (检测依据: $py 已装 torch, hip=$hip)" >&2
      return 0
    fi
    if [ -n "$cuda" ]; then
      echo "nvidia"
      echo "    (检测依据: $py 已装 torch, cuda=$cuda)" >&2
      return 0
    fi
  fi

  # 2) 厂商驱动工具
  if command -v nvidia-smi >/dev/null 2>&1; then
    echo "nvidia"
    echo "    (检测依据: 找到 nvidia-smi)" >&2
    return 0
  fi
  if command -v rocm-smi >/dev/null 2>&1 || command -v rocminfo >/dev/null 2>&1; then
    echo "amd"
    echo "    (检测依据: 找到 rocm-smi/rocminfo)" >&2
    return 0
  fi

  # 3) lspci 硬件枚举兜底
  if command -v lspci >/dev/null 2>&1; then
    pci=$(lspci 2>/dev/null | grep -iE "vga|3d controller" || true)
    if printf '%s' "$pci" | grep -qi "nvidia"; then
      echo "nvidia"
      echo "    (检测依据: lspci 显示 NVIDIA 显卡)" >&2
      return 0
    fi
    if printf '%s' "$pci" | grep -qiE "advanced micro devices|amd"; then
      echo "amd"
      echo "    (检测依据: lspci 显示 AMD 显卡)" >&2
      return 0
    fi
  fi

  echo "unknown"
  echo "    (检测依据: 未探测到 NVIDIA/AMD GPU,可能是 CPU 机器或容器未透传 GPU)" >&2
  return 0
}

# 人类可读描述:在安装/启动脚本开头打印,方便排障
# 传参为已探测结果可避免重复探测(否则内部自动探测一次)
describe_gpu() {
  local v="${1:-}"
  if [ -z "$v" ]; then
    v=$(detect_gpu "$@")
  fi
  case "$v" in
    nvidia) echo "🟢 检测到 NVIDIA GPU → CUDA 路线(装 CUDA torch + xformers)" ;;
    amd)    echo "🟢 检测到 AMD GPU → ROCm 路线(装 ROCm torch + triton>=3.7.1)" ;;
    cpu)    echo "🟡 手动指定 CPU 模式 → 无 GPU 加速" ;;
    *)      echo "🟠 未识别 GPU → 通用兜底,建议手动 COMFY_GPU=nvidia|amd 重试" ;;
  esac
}
