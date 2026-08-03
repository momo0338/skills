# COMPYUI_DEPLOY · 自建 ComfyUI 视频生成部署操作单(替代即梦)

> 版本:1.0  日期:2026-08-03
> 目的:在自有机器部署 ComfyUI + Wan2.1(纯产品 i2v)+ LatentSync(口播口型),
> 产出与即梦同契约的视频生成后端,接回 dy-fanpai 管线。
> 配套:`generation/comfyui.py`(后端代码,部署完成后启用)。
> 纪律:按硬件选模型档位,勿强上高配模型(显存不足→OOM/极慢);先单段验证再批量。

---

## 0. 硬件决策表(先选档位)

| 你的 GPU | 显存 | i2v 模型 | 口型方案 | 预期:5s 视频 |
|---|---|---|---|---|
| RTX 3060/4060 | 8~12GB | Wan2.1-1.3B(FP16) | LatentSync-1.5 | 5~15 分钟 |
| RTX 3090/4090 | 24GB | **Wan2.1-14B(FP8/GGUF Q5)** | **LatentSync-1.6** | 2~6 分钟 |
| A100/H100 | 40~80GB | Wan2.1-14B(FP16) | LatentSync-1.6 | <2 分钟 |

> ⚠ **若显存 ≥ 24GB 且 NVIDIA 卡,直接按"推荐档"走**(最省事、质量最好)。
> Mac/AMD 卡不适用本操作单(NVIDIA 专属算子问题),若有 Apple Silicon 机器请用云方案。

---

## 1. 环境准备(Linux + NVIDIA)

```bash
# 1) 确认驱动与 CUDA
nvidia-smi                 # 期望:驱动正常、看到显存大小
python3 --version          # ≥3.10
git --version

# 2) 装 miniconda(若没有)
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
bash Miniconda3-latest-Linux-x86_64.sh

# 3) 建 ComfyUI 环境
conda create -n comfy python=3.11 -y && conda activate comfy
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```

---

## 2. 安装 ComfyUI + 关键节点

```bash
git clone https://github.com/comfyanonymous/ComfyUI.git
cd ComfyUI
pip install -r requirements.txt

# 必需自定义节点
cd custom_nodes
git clone https://github.com/comfyanonymous/ComfyUI-Manager.git        # 节点管理器
git clone https://github.com/kijai/ComfyUI-WanVideoWrapper.git          # Wan2.1 视频
git clone https://github.com/byteDance/LatentSync.git ComfyUI-LatentSync # 口型同步
cd ..

# 确认能启动(先不下载模型)
python main.py --listen 0.0.0.0 --port 8188
# 浏览器打开 http://<机器IP>:8188 看到画布 = 成功
```

---

## 3. 下载模型(按档位)

```bash
cd models
# Wan2.1 i2v(纯产品段)
#   推荐档(24GB+):
mkdir -p wan && cd wan
#   Wan2.1-14B-720P i2v FP8: https://huggingface.co/Wan-AI/Wan2.1-I2V-14B-720P  (约 27GB)
#   或 GGUF Q5 量化版(ComfyUI-Org 提供,约 13GB)
wget <对应模型链接>

# LatentSync 口型模型(口播段)
cd ../latentsync
#   下载 LatentSync-1.6 权重(官方 GitHub releases 提供,约 2-5GB)

# 可选:Whisper(口型工作流音频嵌入)
#   由 LatentSync 节点自动下载或手动放 models/whisper
```

> 模型下载源:国内可用 hf-mirror.com 加速:`export HF_ENDPOINT=https://hf-mirror.com`。

---

## 4. 工作流搭建(两套,一次搭好反复用)

### 4.1 纯产品 i2v 工作流(Wan2.1)
节点链:LoadImage(锚图)→ WanVideo i2v → VHS_VideoCombine(存 mp4)
- 输入参数:图片、prompt、时长(秒)、分辨率(720×1280 或按源视频)
- 输出:`output/wan_i2v_<ts>.mp4`

### 4.2 口播口型工作流(Wan2.1 InfiniteTalk / LatentSync)
节点链:LoadImage(参考图)→ LoadAudio(段配音)→ 口型生成 → VideoCombine
- 输入参数:参考图、音频(wav)、prompt、时长
- 输出:口型对上的 mp4

> 参考官方模板库(comfy.org/templates):
> - 「Audio-Driven Character Lip Sync Video」(Wan2.1 InfiniteTalk)
> - 「LatentSync」工作流(ByteDance 官方)

---

## 5. 启用 API 模式(供 dy-fanpai 调用)

ComfyUI 原生支持 HTTP API(`/prompt` 提交,`/history/{id}` 查结果),无需额外插件:

```bash
# 保持服务运行
python main.py --listen 0.0.0.0 --port 8188 --disable-auto-launch
```

dy-fanpai 侧(`generation/comfyui.py`,我写好等你)将:
1. `POST http://<IP>:8188/prompt` 提交工作流(带图/音频/参数) → 拿 prompt_id;
2. `GET /history/{prompt_id}` 轮询 → 取输出文件 → 下载到 `generation/clips/Sxx.mp4`。

> 防火墙需放行 8188 端口;或用 SSH 隧道:`ssh -L 8188:localhost:8188 <机器>` 本机直连。

---

## 6. 验证与接入 dy-fanpai

```bash
# 1) 手动跑通一段:网页上载入 i2v 工作流,传一张产品图 + prompt,生成成功
# 2) 口型工作流:传参考图 + S3.wav,生成成功,肉眼确认口型对得上
# 3) 告诉我:机器 IP/端口、两套工作流 JSON(或 API 参数格式)、模型档位
# 4) 我启用 generation/comfyui.py,配置 COMfyUI_BASE_URL,跑 dy-fanpai 全链路
```

---

## 7. 常见问题

| 症状 | 原因 | 解法 |
|---|---|---|
| OOM 崩溃 | 模型超过显存 | 换小档位模型/GGUF 量化/降分辨率 |
| 口型不对 | LatentSync 版本/参数 | 用官方工作流默认参数,lips_expression 1.5~2.5 |
| 视频抖动 | 采样步数低 | 步数 ≥25,CFG 6~8 |
| 慢 | 显存不足换页 | 换 24GB+ 卡,或降分辨率 |
| API 连不上 | 端口未放行 | 放行 8188 / SSH 隧道 |

---

## 8. 成本对比(供决策)

| 方案 | 30 段耗时 | 成本 |
|---|---|---|
| 自有 GPU(≥24GB) | 2~6 小时 | 电费≈¥几元 |
| 云 GPU 4090(¥6~8/h) | 2~4 小时 | ¥15~30 |
| 即梦页面手动 | 30~60 分钟操作 | 积分(已有账号) |

**自有机器的最大价值:口播口型(LatentSync)与纯产品 i2v(Wan2.1)全部自控、无限量。**
