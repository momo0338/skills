---
name: whispercpp
description: 使用 whisper.cpp（whisper-cli + ggml-large-v3-turbo，GPU 加速）对本地视频/音频批量提取并转写内容，产出带时间戳的转写稿，用于后续内容分析、知识提炼、方案整理。macOS（Metal）与 Windows（官方预编译包，CUDA/CPU）均可原生运行，不依赖 WSL2。当用户要求"提取/分析这批视频的内容"、"把视频转成文字"、"整理视频里的干货/方法论/方案"时使用。支持电商术语提示词（千川、投流等）、自动跳过无关文件、中文口播优先。
agent_created: true
---

# whisper.cpp 视频转写与分析

## Overview

用 whisper.cpp（whisper-cli + ggml-large-v3-turbo 模型）把一批本地视频批量转成中文转写稿，供后续做内容提炼（方法论、方案、SOP 等）。

**双平台支持**：

- **macOS**：brew 安装 `whisper-cpp`，Apple Silicon 走 Metal GPU 加速
- **Windows**：下载官方 Releases 预编译包 `whisper-bin-x64.zip`（含 `whisper-cli.exe`，解压即用，无需编译、不依赖 WSL2）；NVIDIA 显卡可用 CUDA 版 `whisper-cublas-12.4.0-bin-x64.zip` 加速
- 模型文件（`ggml-large-v3-turbo.bin`）两平台通用，同一个文件直接复用

## 前置条件检查（先做这 3 项）

1. **whisper-cli 已安装**
   - macOS：`which whisper-cli`（brew 装：`brew install whisper-cpp`；新版命令名是 `whisper-cli`，不是 `whisper-cpp`/`main`）
   - Windows：`where whisper-cli` 或直接指定 `WHISPER_CLI` 环境变量为 `whisper-cli.exe` 完整路径（预编译包解压后加入 PATH 即可）
2. **模型已存在**（两平台同一文件，路径默认如下，可用 `WHISPER_MODEL` 环境变量覆盖）
   - macOS/Linux：`ls "$HOME/whisper.cpp/models/ggml-large-v3-turbo.bin"`
   - Windows：`Test-Path "$env:USERPROFILE\whisper.cpp\models\ggml-large-v3-turbo.bin"`
   - 1.5GB，sha256 校验：`1fc70f774d38eb169993ac391eea357ef47c88757ef72ee5943879b7e8e2bc69`
   - 缺模型 → 见 `references/model-download.md`（网络受限时需按本机代理配置访问 HuggingFace，或改用国内镜像）
3. **ffmpeg 可用**：macOS `which ffmpeg`；Windows `where ffmpeg`（无则安装 ffmpeg Windows 版并加入 PATH）

## 工作流程（Workflow Decision Tree）

```
用户给视频目录
├─ 第一步：盘点视频（列出 .mp4，读同名 .metadata.json 判断主题）
├─ 第二步：提取音频（ffmpeg → 16kHz 单声道 wav）
├─ 第三步：批量转写（whisper-cli，可加术语提示词，跳过无关文件）
├─ 第四步：质量抽查（读转写稿首尾，检查术语是否识别正确）
└─ 第五步：内容提炼（按主题归档 → 交叉去重 → 产出方案/总结）
```

> 可选增强：**第六步：画面 OCR + LLM 融合纠错**（有画面文字线索时，见下方专节）

### 第一步：盘点视频

```bash
ls -la "<视频目录>/" && ls "<视频目录>"/*.metadata.json 2>/dev/null
```
- 有 `.metadata.json` 时读取，可获知标题/标签/作者/时长/数据，用于**预分类**（哪些与目标主题相关、哪些无关）
- 判断哪些视频跳过（无关主题的），转写前先和用户确认或按明显无关直接跳过

### 第二步：提取音频

```bash
mkdir -p "<输出目录>/audio"
for f in <视频目录>/*.mp4; do
  id=$(basename "$f" | sed 's/_.*//')   # 取文件名前缀作 id
  ffmpeg -y -loglevel error -i "$f" -vn -ac 1 -ar 16000 "<输出目录>/audio/${id}.wav"
done
```
- 16kHz 单声道是 whisper 标准输入，压缩后转写最快
- 文件名前缀做 id，保持与视频对应关系（如抖音 aweme_id）

### 第三步：批量转写（核心）

运行批量脚本（已封装，含术语提示词 + 跳过列表 + 断点续跑）：

```bash
# macOS / Linux（bash）
bash scripts/transcribe_batch.sh <音频目录> <输出目录> "<跳过id列表(空格分隔)>" "<提示词,逗号分隔>"
```

```powershell
# Windows / macOS（PowerShell，两平台通用）
powershell -ExecutionPolicy Bypass -File scripts\transcribe_batch.ps1 <音频目录> <输出目录> "<跳过id列表(空格分隔)>" "<提示词,逗号分隔>"
```

等价手动命令（单文件）：
```bash
whisper-cli -m "${WHISPER_MODEL:-$HOME/whisper.cpp/models/ggml-large-v3-turbo.bin}" \
  -l zh --prompt "千川,全域推广,追投,商品卡,千展,冷启动,ROI,GMV,素材,计划,直播间,代投,跑量,抖店" \
  -f <音频.wav> -otxt -of <输出路径前缀>
```

```powershell
# Windows：模型路径用 %USERPROFILE%\whisper.cpp\models\...，或用 WHISPER_MODEL 指定
whisper-cli -m "$env:WHISPER_MODEL" -l zh --prompt "千川,全域推广,追投,商品卡,千展,冷启动,ROI,GMV,素材,计划,直播间,代投,跑量,抖店" `
  -f <音频.wav> -otxt -of <输出路径前缀>
```

**关键参数**：
- `-l zh`：中文模式
- `--prompt`：术语提示词（initial prompt），**对电商/专业术语识别至关重要**，按内容主题定制
- `-otxt`：输出 txt；需要时间戳可加 `-oj`（JSON）或 `-osrt`（字幕）
- GPU 加速：macOS 默认 Metal（Apple Silicon 实测约 9x 实时，具体因机型而异）；Windows 用 CUDA 版预编译包自动走 NVIDIA GPU，无独显时用 CPU
- **不要加 `-ng`**（强制纯 CPU，大模型很慢）

### 第四步：质量抽查

```bash
head -30 <转写稿>.txt && tail -10 <转写稿>.txt
```
```powershell
# Windows
Get-Content <转写稿>.txt -TotalCount 30
Get-Content <转写稿>.txt -Tail 10
```
- 检查核心术语是否识别正确（如"千川/全域推/追投/ROI"）
- 少量同音错字（"保本线"→"宝本线"、"三步"→"商部"）不影响理解，在提炼时纠正即可
- 若术语大面积错误：确认 --prompt 是否传了术语词

### 第五步：内容提炼（分析师角色）

逐份读转写稿 → 每份提炼【核心观点/操作步骤/具体参数/避坑】→ 多视频同主题**交叉去重**（冲突观点标注并存）→ 按模块归档 → 产出交付物：
- 方案文档（Markdown）
- 可视化看板（HTML，参照千川投流方案看板风格：深色 header + 模块导航 + 表格 + 决策树）

## 第六步（可选增强）：画面 OCR + LLM 融合纠错

**适用场景**：whisper 转写存在同音错字，尤其专有名词（人名/地名/项目名）听错时。画面里的标题、字幕、水印、角标是权威文字线索，可交叉验证转写稿。

**流程**（三个输入 → LLM 融合 → 修正稿 + 改动清单）：

1. **画面 OCR 提取文字线索**：
   ```bash
   python3 scripts/ocr_subtitles.py <视频.mp4> <输出目录> --fps 1 --region full
   ```
   - `--region full`：大字覆盖式字幕（新闻/访谈剪辑），提取标题、人名、水印、角标
   - `--region bottom`：标准底部字幕条（裁剪下部 28%），逐句字幕质量更好；**尚未实测，遇到此类视频再验证**
   - 输出 `<输出目录>/subtitles.txt`（`[MM:SS-MM:SS] 文本`），帧缓存可复用
2. **LLM 融合纠错**：把 whisper 转写稿 + OCR 文字线索 + 视频标题/简介一起交给 LLM，要求输出：
   - 修正稿全文
   - 改动清单（原词 → 修正词 + 依据：语音语境 / OCR 画面文字）
3. **人工复核改动清单**（LLM 修正也可能错，改动必须可追溯到依据）

**实测边界（2026-08，两个新闻/访谈视频）**：

- 大字覆盖式字幕：OCR 提取专有名词、日期、水印、核心短语可靠（如"进士园"、"8月19日"、"推动企业向善发展"），逐句字幕不可靠（tesseract 对描边大字识别弱）
- 同音错字规律：常见词（急难愁盼、淡季、弦绷紧）靠语音语境可纠；专有名词（进士园/吉安中国进士文化园）必须靠画面文字
- 定制 `--prompt` 提示词能修正高频领域词，但对低频专有名词无效（prompt 只能引导不能强制）
- 对话内 LLM 即够用：不需要额外 LLM API，当前对话直接做融合纠错，零凭证零成本

## 引擎选型备注

- **首选 whisper.cpp large-v3-turbo**：术语准、带标点、GPU 快（已实测优于 FunASR SenseVoice 的术语识别）
- **备选 FunASR SenseVoice**（`references/engine-comparison.md` 有完整 A/B 实测）：仅当需要情感标签/说话人分离/粤语时
- **不要用 openai-whisper Python 版**（MPS 慢）与云端 API（数据出境、要注册）

## Resources

### scripts/
- `transcribe_batch.sh` — 批量转写脚本（macOS/Linux bash 版：遍历 wav → whisper-cli → txt，支持跳过列表、术语提示词、断点续跑）
- `transcribe_batch.ps1` — 批量转写脚本（Windows/macOS PowerShell 版，功能与 bash 版一致）
- `ocr_subtitles.py` — 抽帧 + tesseract OCR 字幕线索提取（大字覆盖式用 `--region full`，标准字幕条用 `--region bottom`）

### references/
- `model-download.md` — 模型与工具获取全流程（macOS brew / Windows 官方预编译包、HF 下载与代理/国内镜像方案、sha256 校验）
- `engine-comparison.md` — whisper.cpp vs FunASR SenseVoice 实测对比（数据 + 结论），选型依据
- `qianchuan-terminology.md` — 千川/电商投流术语表（提示词模板 + 常见同音错字对照），供内容提炼时纠错
