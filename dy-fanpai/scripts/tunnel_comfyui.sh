#!/usr/bin/env bash
# =============================================================================
# tunnel_comfyui.sh — 为 ComfyUI 建立 trycloudflare 隧道(供 macOS 本机 dy-fanpai 调用)
#
# 背景: MI308X 服务器与 Mac 不在同一内网,ComfyUI 默认只监听服务器本机;
#       dy-fanpai(generation/comfyui.py)需要可达的 COMFYUI_BASE_URL。
#       trycloudflare 免费隧道无需登录,但每次启动域名都会变 → 本脚本负责:
#         1) 确认 ComfyUI 已在监听(未启动则提示先跑 run_comfyui.sh)
#         2) 起 cloudflared tunnel → 打印新 https://xxx.trycloudflare.com
#         3) 输出可直接在 Mac 侧执行的更新命令(dy-fanpai set-url 或手动写配置)
#
# 用法(在 MI308X 服务器上执行):
#   bash tunnel_comfyui.sh                 # 默认本机 127.0.0.1:8188
#   bash tunnel_comfyui.sh 127.0.0.1:8188  # 指定 ComfyUI 监听地址
#   bash tunnel_comfyui.sh --detach        # 后台常驻,域名写入 ./comfyui_tunnel_url
#
# 依赖: cloudflared(服务器上 pip/apt 安装或直接下二进制)
#   curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o /usr/local/bin/cloudflared && chmod +x /usr/local/bin/cloudflared
#
# Mac 侧收尾(把域名写给 dy-fanpai 配置):
#   printf '%s' 'https://xxx.trycloudflare.com' > ~/.config/dy-fanpai/comfyui_base_url
#   dy-fanpai doctor   # 看到 COMFYUI_BASE_URL 就位即可
# =============================================================================
set -uo pipefail

TARGET="${1:-127.0.0.1:8188}"
MODE="${2:-}"  # --detach

# 0. 预检 ComfyUI 是否在监听
if ! command -v curl >/dev/null 2>&1; then
  echo "❌ 缺少 curl" >&2; exit 1
fi
if ! curl -s -m 3 "http://$TARGET/system_stats" >/dev/null 2>&1; then
  echo "⚠️  $TARGET 无响应 — 请先确认 ComfyUI 已启动(bash run_comfyui.sh)"
  echo "   若已启动但端口不同,传参: bash tunnel_comfyui.sh 127.0.0.1:8188"
  exit 1
fi
echo "==> ComfyUI 在 $TARGET 正常监听"

# 1. cloudflared 可用性
if ! command -v cloudflared >/dev/null 2>&1; then
  echo "❌ 未安装 cloudflared,安装:"
  echo "   curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o /usr/local/bin/cloudflared && chmod +x /usr/local/bin/cloudflared"
  exit 1
fi

# 2. 建隧道
echo "==> 建立 trycloudflare 隧道 → $TARGET"
if [ "${MODE}" = "--detach" ]; then
  nohup cloudflared tunnel --url "http://$TARGET" > /tmp/comfyui_tunnel.log 2>&1 &
  echo "==> 隧道已在后台启动,日志: /tmp/comfyui_tunnel.log"
  echo "    等待域名就绪(约 3~8s)..."
  for i in $(seq 1 12); do
    URL=$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' /tmp/comfyui_tunnel.log 2>/dev/null | head -1)
    [ -n "${URL}" ] && break
    sleep 1
  done
else
  # 前台模式: 域名会直接打到 stdout,脚本持续运行
  cloudflared tunnel --url "http://$TARGET" 2>&1 | tee /tmp/comfyui_tunnel.log
  exit 0
fi

if [ -z "${URL:-}" ]; then
  echo "⚠️ 未捕获到域名(见 /tmp/comfyui_tunnel.log)" >&2
  exit 1
fi

# 3. 输出结果
echo "================================================================"
echo "✅ 隧道域名: $URL"
echo "--------------------------------------------------------------"
echo "在 macOS 本机执行以下命令即可让 dy-fanpai 使用:"
echo "  dy-fanpai set-url comfyui '$URL'   # 等价于写 ~/.config/dy-fanpai/comfyui_base_url"
echo "  dy-fanpai doctor"
echo "================================================================"
echo "$URL" > /tmp/comfyui_tunnel_url
