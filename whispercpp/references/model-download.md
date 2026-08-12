# 模型与工具获取指南

> macOS（Apple Silicon）与 Windows 双平台安装说明，网络部分给出通用方案 + 示例环境实测记录（2026-08）。

## 1. 安装 whisper-cpp

### macOS（brew，Apple Silicon Metal 加速）

```bash
brew install whisper-cpp
```

- 新版命令名是 **`whisper-cli`**（不是 `whisper-cpp`，也不是旧版 `main`）
- 附带工具：whisper-quantize（量化）、whisper-server 等
- 验证 Metal 加速：`whisper-cli --help` 输出中应看到 `ggml_metal_device_init` 与 GPU 名

### Windows（官方 Releases 预编译包，原生运行、无需 WSL2）

1. 打开 whisper.cpp 官方 GitHub Releases 页面：`https://github.com/ggml-org/whisper.cpp/releases`
2. 下载 **`whisper-bin-x64.zip`**（标准 x64 版，含 `whisper-cli.exe`，无需编译）
   - NVIDIA 显卡用户可下载 **`whisper-cublas-12.4.0-bin-x64.zip`**（CUDA 加速版，需已安装 NVIDIA 驱动）
   - 无独显时用标准 x64 版走 CPU 即可
3. 解压到任意目录（如 `C:\whisper.cpp\`），把解压目录加入系统 PATH，或设置 `WHISPER_CLI` 环境变量指向 `whisper-cli.exe` 完整路径
4. 验证：`where whisper-cli` 能找到，或 `whisper-cli.exe --help` 可运行

- 预编译包是官方发布产物，不需要 Visual Studio、不需要 WSL2、不需要编译
- 模型文件与 macOS 完全通用，同一份 `ggml-large-v3-turbo.bin` 直接拷贝即可

## 2. 下载模型（ggml-large-v3-turbo.bin，1.5GB）

### 网络策略（通用）

模型托管在 HuggingFace。若直连超时/失败，按顺序尝试：

1. **配置本机代理**：先确认本机实际代理端口（如 Clash 类工具常见混合端口），再导出环境变量：
   ```bash
   export https_proxy=http://127.0.0.1:<你的代理端口> http_proxy=http://127.0.0.1:<你的代理端口>
   ```
   - 代理证书为自签名时，curl 需加 `-k`
2. **国内镜像 hf-mirror.com**：直连（不走代理）通常可达：
   ```bash
   curl -sL --retry 3 -o <模型保存路径>/ggml-large-v3-turbo.bin \
     "https://hf-mirror.com/ggerganov/whisper.cpp/resolve/main/ggml-large-v3-turbo.bin"
   ```
3. 上述均不通时，从其他社区镜像或团队共享存储获取，再校验 sha256。

### 示例环境实测记录（仅供参考，不同网络环境结果不同）

| 源 | 结果 | 原因 |
|---|---|---|
| huggingface.co 直连 | ❌ 超时 | 需要代理 |
| Clash 代理（127.0.0.1:7897）| ✅ 通，~1-3 MB/s | 示例：Clash Verge 混合端口 |
| hf-mirror.com（走代理）| ❌ 502 | 代理隧道对国内镜像异常 |
| hf-mirror.com（直连）| ❌ 超时 | 直连 160.16.86.14 不通 |
| ggml.ggerganov.com | ❌ 404 | 旧路径已废弃 |
| azureedge（OpenAI 官方 .pt）| ✅ 通，~3.5 MB/s | 与 HF 无关，走代理可下 |

### 下载命令

```bash
# 走代理下载 ggml 格式（whisper.cpp 专用）
export https_proxy=http://127.0.0.1:<你的代理端口> http_proxy=http://127.0.0.1:<你的代理端口>
mkdir -p "$HOME/whisper.cpp/models"
curl -k -sL --retry 3 -o "$HOME/whisper.cpp/models/ggml-large-v3-turbo.bin" \
  "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3-turbo.bin"
```

- `-k`：代理证书为自签名时使用（无代理可去掉）
- `-L`：HF resolve 会 302 跳转到 Xet CDN，必须跟随
- `--retry 3`：大文件下载容错

### 校验完整性

```bash
shasum -a 256 "$HOME/whisper.cpp/models/ggml-large-v3-turbo.bin"
# 期望: 1fc70f774d38eb169993ac391eea357ef47c88757ef72ee5943879b7e8e2bc69
```

### 备选：openai-whisper（Python）的 .pt 模型

如走 openai-whisper 路径（不推荐，MPS 慢），从 azureedge 下 .pt：
```bash
export https_proxy=http://127.0.0.1:<你的代理端口> http_proxy=http://127.0.0.1:<你的代理端口>
curl -k -L -o ~/.cache/whisper/large-v3-turbo.pt \
  "https://openaipublic.azureedge.net/main/whisper/models/aff26ae408abcba5fbf8813c21e62b0941638c5f6eebfb145be0c9839262a19a/large-v3-turbo.pt"
```

### 量化版（可选，体积小 3 倍）

```bash
# Q5 量化 547MB（精度损失 <0.5%）
curl -k -sL -o "$HOME/whisper.cpp/models/ggml-large-v3-turbo-q5_0.bin" \
  "https://huggingface.co/BricksDisplay/whisper-ggml/resolve/main/ggml-large-v3-turbo-q5_0.bin"
# Q8 量化 834MB
# .../BricksDisplay/whisper-ggml/resolve/main/ggml-large-v3-turbo-q8_0.bin
```

> 模型路径约定：默认 `$HOME/whisper.cpp/models/`，可用环境变量 `WHISPER_MODEL` 覆盖（批量脚本会读取）。

> Windows 路径约定：默认 `%USERPROFILE%\whisper.cpp\models\`（即 `$env:USERPROFILE\whisper.cpp\models\`），同样可用 `WHISPER_MODEL` 覆盖；批量脚本 `transcribe_batch.ps1` 自动读取该默认值。

### 下载命令（PowerShell，Windows）

```powershell
# 走代理下载（端口按本机实际代理填写）
$env:https_proxy = "http://127.0.0.1:<你的代理端口>"
$env:http_proxy  = "http://127.0.0.1:<你的代理端口>"
New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\whisper.cpp\models" | Out-Null
curl.exe -k -sL --retry 3 -o "$env:USERPROFILE\whisper.cpp\models\ggml-large-v3-turbo.bin" `
  "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3-turbo.bin"
```

校验（PowerShell）：
```powershell
Get-FileHash "$env:USERPROFILE\whisper.cpp\models\ggml-large-v3-turbo.bin" -Algorithm SHA256
# 期望: 1fc70f774d38eb169993ac391eea357ef47c88757ef72ee5943879b7e8e2bc69
```

## 3. 音频准备（ffmpeg）

```bash
# 视频 → 16kHz 单声道 wav（whisper 标准输入）
ffmpeg -y -loglevel error -i input.mp4 -vn -ac 1 -ar 16000 output.wav
```

> Windows 需安装 ffmpeg Windows 版（如 `winget install ffmpeg` 或下载 gyan.dev 预编译版）并加入 PATH；命令本身两平台一致。

## 3.5 可选依赖：tesseract（画面 OCR 纠错用）

第六步画面 OCR 需要 tesseract + 简体中文语言包：

```bash
# macOS
brew install tesseract tesseract-lang

# Windows（winget）
winget install UB-Mannheim.TesseractOCR   # 安装时勾选 Chinese (Simplified) 语言包
```

验证：
```bash
tesseract --list-langs   # 应包含 chi_sim
```

未安装时跳过第六步即可，不影响转写主流程。

## 4. 性能参考（Apple Silicon 实测，2026-08）

- 263s 视频（large-v3-turbo + Metal）：约 26-30s 转完（~9x 实时）
- Windows CUDA（NVIDIA GPU）加速效果与 Metal 同级，具体随机型而异
- **纯 CPU（-ng）会 OOM 被杀**——不要加 `-ng`
- 批量 11 个视频（共 ~45 分钟音频）：约 5 分钟跑完

> 具体耗时随机型、模型、音频时长变化，仅供参考。

## 5. 常见问题

- `whisper-cli: command not found` → 检查 brew 是否装好，命令名是 whisper-cli
- Windows `where whisper-cli` 找不到 → 检查预编译包是否解压并加入 PATH，或设置 `WHISPER_CLI` 指向 whisper-cli.exe
- 模型下载 0 字节 → 检查代理配置是否正确 + `-L` 跟随重定向
- 转写全英文/乱码 → 确认 `-l zh`
- 术语识别差 → 确认 `--prompt` 传了术语词（见 qianchuan-terminology.md）
