#!/usr/bin/env bash
# =============================================================================
# test_comfyui_scripts.sh — ComfyUI 安装/启动脚本回归测试
#
# 无需 GPU、无需网络即可安全运行(所有外部命令均被 mock/拦截)。
# 用法:  bash test_comfyui_scripts.sh [--verbose]
# 退出码: 0=全部通过  1=存在失败(输出 FAIL 明细)
#
# 覆盖范围:
#   1. bash -n 语法 + shellcheck(如已安装)
#   2. detect_gpu 判定矩阵(裸环境/驱动工具/lspci/torch/手动指定/非法值)
#   3. install_comfyui.sh 入口(帮助/未知参数/--gpu 分派到对应子脚本)
#   4. 子脚本参数解析(位置参数/--workspace/--workspace=/缺值/未知参数)
#   5. run_comfyui.sh 启动参数分支(NVIDIA×4 / AMD×2 / 未知×1)
# =============================================================================
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR" || exit 1
VERBOSE="${1:-}"
PASS=0; FAIL=0

say()  { echo "$*"; }
note() { [ -n "$VERBOSE" ] && echo "      · $*"; }

check() { # $1=描述  $2=实际输出  $3=grep 期望模式(扩展正则)
  if printf '%s' "$2" | grep -qE -- "$3"; then
    PASS=$((PASS+1)); echo "  ✅ $1"
  else
    FAIL=$((FAIL+1)); echo "  ❌ $1"
    echo "      实际输出: $(printf '%s' "$2" | head -4 | tr '\n' '│')"
    echo "      期望匹配: $3"
  fi
}

check_rc() { # $1=描述  $2=实际rc  $3=期望rc
  if [ "$2" -eq "$3" ]; then
    PASS=$((PASS+1)); echo "  ✅ $1 (rc=$2)"
  else
    FAIL=$((FAIL+1)); echo "  ❌ $1 (实际 rc=$2,期望 rc=$3)"
  fi
}

T=$(mktemp -d)
trap 'rm -rf "$T"' EXIT

# ---------------------------------------------------------------------------
say "== 1. 语法与静态检查 =="
for f in detect_gpu.sh install_comfyui.sh install_comfyui_cuda.sh \
         install_comfyui_rocm.sh run_comfyui.sh run_comfyui_nvidia.sh test_comfyui_scripts.sh; do
  if bash -n "$f" 2>/dev/null; then
    PASS=$((PASS+1)); echo "  ✅ bash -n: $f"
  else
    FAIL=$((FAIL+1)); echo "  ❌ bash -n: $f"
  fi
done
if command -v shellcheck >/dev/null 2>&1; then
  if shellcheck -S warning detect_gpu.sh install_comfyui.sh install_comfyui_cuda.sh \
                        install_comfyui_rocm.sh run_comfyui.sh run_comfyui_nvidia.sh; then
    PASS=$((PASS+1)); echo "  ✅ shellcheck: 全部通过"
  else
    FAIL=$((FAIL+1)); echo "  ❌ shellcheck 有告警(见上)"
  fi
else
  echo "  ⏭  shellcheck 未安装,跳过"
fi

# ---------------------------------------------------------------------------
# mock 工具:假驱动工具 / 假 lspci / 假 torch python3
# ---------------------------------------------------------------------------
mk_mock() { # $1=目标目录  $2=文件名  $3=内容
  mkdir -p "$1"
  printf '%s\n' "$3" > "$1/$2"
  chmod +x "$1/$2"
}

say ""
say "== 2. detect_gpu 判定矩阵 =="
OUT=$(bash -c 'source ./detect_gpu.sh; detect_gpu')
check "裸环境(无 GPU 工具)→ unknown" "$OUT" '^unknown$'

OUT=$(COMFY_GPU=nvidia bash -c 'source ./detect_gpu.sh; detect_gpu')
check "COMFY_GPU=nvidia 强制" "$OUT" '^nvidia$'
OUT=$(COMFY_GPU=amd bash -c 'source ./detect_gpu.sh; detect_gpu')
check "COMFY_GPU=amd 强制" "$OUT" '^amd$'
OUT=$(COMFY_GPU=cpu bash -c 'source ./detect_gpu.sh; detect_gpu')
check "COMFY_GPU=cpu 强制" "$OUT" '^cpu$'
OUT=$(COMFY_GPU=xxx bash -c 'source ./detect_gpu.sh; detect_gpu' 2>/dev/null)
check "COMFY_GPU 非法值 → 按 auto 探测(unknown)" "$OUT" '^unknown$'

mk_mock "$T/bin/nvidia" "nvidia-smi" '#!/usr/bin/env bash
echo mock'
OUT=$(PATH="$T/bin/nvidia:$PATH" bash -c 'source ./detect_gpu.sh; detect_gpu')
check "nvidia-smi → nvidia" "$OUT" '^nvidia$'

mk_mock "$T/bin/amd" "rocm-smi" '#!/usr/bin/env bash
echo mock'
OUT=$(PATH="$T/bin/amd:$PATH" bash -c 'source ./detect_gpu.sh; detect_gpu')
check "rocm-smi → amd" "$OUT" '^amd$'

mk_mock "$T/bin/lspcin" "lspci" '#!/usr/bin/env bash
echo "01:00.0 VGA compatible controller: NVIDIA Corporation GA102 [GeForce RTX 3080]"'
OUT=$(PATH="$T/bin/lspcin:$PATH" bash -c 'source ./detect_gpu.sh; detect_gpu')
check "lspci 显示 NVIDIA → nvidia" "$OUT" '^nvidia$'

mk_mock "$T/bin/lspcia" "lspci" '#!/usr/bin/env bash
echo "03:00.0 Display controller: Advanced Micro Devices, Inc. [AMD/ATI] MI300X [Instinct MI300X]"
echo "04:00.0 3D controller: NVIDIA Corporation"'
OUT=$(PATH="$T/bin/lspcia:$PATH" bash -c 'source ./detect_gpu.sh; detect_gpu')
check "lspci 双卡混合 → nvidia 优先(双卡机器建议手动 COMFY_GPU)" "$OUT" '^nvidia$'

# 假 torch:注意 HIP 分支先于 CUDA 判断
mk_mock "$T/bin/pyhip"  "python3" '#!/usr/bin/env bash
case "$*" in
  *"torch.version.hip"*) echo "6.2";;
  *"torch.version.cuda"*) echo "";;
  *) exit 1;;
esac'
OUT=$(PATH="$T/bin/pyhip:$PATH" bash -c 'source ./detect_gpu.sh; detect_gpu')
check "系统 python 已装 torch(hip=6.2)→ amd" "$OUT" '^amd$'

mk_mock "$T/bin/pycuda" "python3" '#!/usr/bin/env bash
case "$*" in
  *"torch.version.hip"*) echo "";;
  *"torch.version.cuda"*) echo "12.4";;
  *) exit 1;;
esac'
OUT=$(PATH="$T/bin/pycuda:$PATH" bash -c 'source ./detect_gpu.sh; detect_gpu')
check "系统 python 已装 torch(cuda=12.4)→ nvidia" "$OUT" '^nvidia$'

# 指定 python 解释器参数
OUT=$(PATH="$T/bin/pyhip:$PATH" bash -c 'source ./detect_gpu.sh; detect_gpu python3')
check "detect_gpu python3 显式传解释器" "$OUT" '^amd$'

# ---------------------------------------------------------------------------
say ""
say "== 3. install_comfyui.sh 入口 =="
OUT=$(bash install_comfyui.sh -h 2>&1)
check "-h 打印帮助(含 --gpu)" "$OUT" '--gpu'
check "-h 打印帮助(含 --workspace)" "$OUT" '--workspace'
OUT=$(bash install_comfyui.sh --bogus 2>&1); RC=$?
check "未知参数报错" "$OUT" '未知参数'
check_rc "未知参数退出码=1" "$RC" 1

# 影子目录分派测试:复制入口+检测库,子脚本替换为假实现
SHADOW="$T/shadow"
mkdir -p "$SHADOW"
cp install_comfyui.sh detect_gpu.sh "$SHADOW/"
printf '#!/usr/bin/env bash\necho "CALLED:cuda $*"\n' > "$SHADOW/install_comfyui_cuda.sh"
printf '#!/usr/bin/env bash\necho "CALLED:rocm $*"\n' > "$SHADOW/install_comfyui_rocm.sh"
chmod +x "$SHADOW"/*.sh

OUT=$(COMFY_GPU=nvidia bash "$SHADOW/install_comfyui.sh" --workspace /tmp/w 2>&1)
check "COMFY_GPU=nvidia → 分派到 cuda 脚本" "$OUT" 'CALLED:cuda'
check "分派时 --workspace 正确传递" "$OUT" 'CALLED:cuda --workspace /tmp/w'

OUT=$(COMFY_GPU=amd bash "$SHADOW/install_comfyui.sh" --workspace /tmp/w 2>&1)
check "COMFY_GPU=amd → 分派到 rocm 脚本" "$OUT" 'CALLED:rocm'
check "AMD 分派传递 --workspace" "$OUT" 'CALLED:rocm --workspace /tmp/w'

OUT=$(COMFY_GPU=amd bash "$SHADOW/install_comfyui.sh" --gpu=nvidia --workspace /tmp/w 2>&1)
check "--gpu=nvidia 覆盖 COMFY_GPU=amd" "$OUT" 'CALLED:cuda'

OUT=$(bash "$SHADOW/install_comfyui.sh" --workspace /tmp/w 2>&1); RC=$?
if printf '%s' "$OUT" | grep -q '无法自动识别' && [ "$RC" -ne 0 ]; then
  PASS=$((PASS+1)); echo "  ✅ 裸环境 → 提示无法识别并退出(rc=$RC)"
else
  FAIL=$((FAIL+1)); echo "  ❌ 裸环境应提示无法识别并非零退出;实际 rc=$RC: $(printf '%s' "$OUT" | head -2 | tr '\n' '│')"
fi

# ---------------------------------------------------------------------------
say ""
say "== 4. 子脚本参数解析(假 git 拦截,仅验证首行 WORK 解析) =="
mk_mock "$T/bin/fakegit" "git" '#!/usr/bin/env bash
echo "FAKE_GIT: $*"
exit 1'

parse_cuda() { # $@=传给 cuda 脚本的参数;输出首行
  PATH="$T/bin/fakegit:$PATH" bash install_comfyui_cuda.sh "$@" 2>&1 | head -1
}
parse_rocm() { # $@=传给 rocm 脚本的参数;输出首行
  PATH="$T/bin/fakegit:$PATH" bash install_comfyui_rocm.sh "$@" 2>&1 | head -1
}

OUT=$(parse_cuda --workspace /tmp/ws_a)
check "cuda --workspace PATH 解析" "$OUT" '工作目录: /tmp/ws_a'
OUT=$(parse_cuda --workspace=/tmp/ws_b)
check "cuda --workspace=PATH 解析" "$OUT" '工作目录: /tmp/ws_b'
OUT=$(parse_cuda /tmp/ws_c)
check "cuda 位置参数解析" "$OUT" '工作目录: /tmp/ws_c'
OUT=$(PATH="$T/bin/fakegit:$PATH" bash install_comfyui_cuda.sh --workspace 2>&1 | head -1)
check "cuda --workspace 缺值报错" "$OUT" '需要路径'
OUT=$(PATH="$T/bin/fakegit:$PATH" bash install_comfyui_cuda.sh --bogus 2>&1 | head -1)
check "cuda 未知参数报错" "$OUT" '未知参数'

OUT=$(parse_rocm --workspace /tmp/ws_d)
check "rocm --workspace PATH 解析" "$OUT" '工作目录: /tmp/ws_d'
OUT=$(parse_rocm /tmp/ws_e)
check "rocm 位置参数解析" "$OUT" '工作目录: /tmp/ws_e'
OUT=$(PATH="$T/bin/fakegit:$PATH" bash install_comfyui_rocm.sh --workspace 2>&1 | head -1)
check "rocm --workspace 缺值报错" "$OUT" '需要路径'
OUT=$(PATH="$T/bin/fakegit:$PATH" bash install_comfyui_rocm.sh --bogus 2>&1 | head -1)
check "rocm 未知参数报错" "$OUT" '未知参数'

# ---------------------------------------------------------------------------
say ""
say "== 5. run_comfyui.sh 启动参数分支(mock venv) =="
# 假 venv python:torch 版本查询 / 加速库查询 / 启动参数打印
mk_fake_venv() { # $1=ComfyUI 目录  $2=hip  $3=cuda  $4=是否已装 xformers  $5=是否已装 flash_attn
  local d="$1/ComfyUI/.venv/bin"
  mkdir -p "$d"
  printf '#!/usr/bin/env bash\ncase "$*" in\n  *"torch.version.hip"*) echo "%s";;\n  *"torch.version.cuda"*) echo "%s";;\n  *"import triton"*) echo "3.8";;\n  *"import flash_attn"*) exit %s;;\n  *"import xformers"*) exit %s;;\n  *) echo "ARGS>>> $*";;\nesac\n' \
    "$2" "$3" "$([ "$5" = "yes" ] && echo 0 || echo 1)" "$([ "$4" = "yes" ] && echo 0 || echo 1)" > "$d/python"
  chmod +x "$d/python"
  touch "$1/ComfyUI/.venv/bin/activate"
}
run_with_venv() { # $1=ComfyUI 根目录  $2=额外 COMFY_* 环境变量(形如 "COMFY_PORT=8199 COMFY_ATTN=sdpa")
  # shellcheck disable=SC2086
  env PATH="$1/ComfyUI/.venv/bin:$PATH" COMFY_WORK="$1" $2 bash run_comfyui.sh 2>&1
}

# 5.1 NVIDIA: 无加速库
D="$T/run_cuda_none"; mk_fake_venv "$D" "" "12.4" no no
OUT=$(run_with_venv "$D" "")
check "NVIDIA 识别" "$OUT" '运行环境: NVIDIA/CUDA \(torch cuda=12.4\)'
check "NVIDIA 无加速库 → split-cross-attention(且不带 --highvram/--disable-xformers)" \
  "$OUT" 'ARGS>>> main.py --listen 0.0.0.0 --port 8188 --disable-auto-launch --use-split-cross-attention --fp16-vae$'

# 5.2 NVIDIA: 有 xformers(新版 ComfyUI 自动启用,无需 --xformers 参数)
D="$T/run_cuda_xf"; mk_fake_venv "$D" "" "12.4" yes no
OUT=$(run_with_venv "$D" "")
check "NVIDIA 有 xformers → 自动启用(无 --xformers 参数,带默认 fp16-vae)" "$OUT" 'ARGS>>> main.py --listen 0.0.0.0 --port 8188 --disable-auto-launch --fp16-vae$'

# 5.3 NVIDIA: COMFY_ATTN=sdpa
D="$T/run_cuda_sdpa"; mk_fake_venv "$D" "" "12.4" yes no
OUT=$(run_with_venv "$D" "COMFY_ATTN=sdpa")
check "NVIDIA COMFY_ATTN=sdpa → 强制 split-cross-attention" "$OUT" 'ARGS>>>.*--use-split-cross-attention --fp16-vae$'

# 5.4 NVIDIA: COMFY_HIGHVRAM=1
D="$T/run_cuda_hvram"; mk_fake_venv "$D" "" "12.4" no no
OUT=$(run_with_venv "$D" "COMFY_HIGHVRAM=1")
check "NVIDIA COMFY_HIGHVRAM=1 → 加 --highvram" "$OUT" 'ARGS>>>.*--highvram --disable-async-offload.*--use-split-cross-attention'

# 5.5 AMD: 默认(triton 3.8,无 flash_attn)
D="$T/run_hip"; mk_fake_venv "$D" "6.2" "" no no
OUT=$(run_with_venv "$D" "")
check "AMD 识别" "$OUT" '运行环境: AMD/ROCm \(torch hip=6.2\)'
check "AMD triton≥3.7 → --enable-triton-backend" "$OUT" 'ARGS>>>.*--enable-triton-backend'
check "AMD 默认 --highvram 系列" "$OUT" 'ARGS>>>.*--highvram --disable-async-offload --disable-pinned-memory --disable-smart-memory'
check "AMD 默认 --disable-xformers" "$OUT" 'ARGS>>>.*--disable-xformers'
check "AMD 无 flash_attn → pytorch-cross-attention" "$OUT" 'ARGS>>>.*--use-pytorch-cross-attention'

# 5.6 AMD: COMFY_FP16_VAE=0
D="$T/run_hip_fp32"; mk_fake_venv "$D" "6.2" "" no no
OUT=$(run_with_venv "$D" "COMFY_FP16_VAE=0")
check "AMD COMFY_FP16_VAE=0 → 无 --fp16-vae" "$OUT" 'ARGS>>>.*--enable-triton-backend$'

# 5.7 未知环境(无 torch、无硬件工具):保守参数,无 --highvram 且无 --fp16-vae(非 nvidia 默认关)
D="$T/run_unknown"
mk_fake_venv "$D" "" "" no no
OUT=$(run_with_venv "$D" "")
check "未知环境 → 保守参数" "$OUT" 'ARGS>>> main.py --listen 0.0.0.0 --port 8188 --disable-auto-launch --use-split-cross-attention$'

# 5.8 run_comfyui_nvidia.sh: NVIDIA 专属脚本帮助与强制参数
say ""
say "== 5.8 run_comfyui_nvidia.sh(仅 NVIDIA 的启动脚本) =="
OUT=$(bash run_comfyui_nvidia.sh -h 2>&1)
check "nvidia 脚本 -h 帮助可读" "$OUT" 'Ubuntu \+ NVIDIA 环境启动 ComfyUI'
check "nvidia 脚本帮助含 fp16-vae 说明" "$OUT" 'fp16-vae'
check "nvidia 脚本帮助含 cuda-malloc 说明" "$OUT" 'cuda-malloc'

# ---------------------------------------------------------------------------
say ""
say "== 结果汇总 =="
say "  PASS=$PASS  FAIL=$FAIL"
[ "$FAIL" -eq 0 ] && say "  🎉 全部通过" || say "  ❌ 存在失败"
[ "$FAIL" -eq 0 ]
