# ============================================================
# transcribe_batch.ps1 — whisper.cpp 批量转写（Windows / macOS 通用 PowerShell 版）
# 用法:
#   powershell -ExecutionPolicy Bypass -File transcribe_batch.ps1 <音频目录> <输出目录> ["跳过id1 id2"] ["提示词,逗号分隔"]
#
# 示例:
#   powershell -ExecutionPolicy Bypass -File transcribe_batch.ps1 .\audio .\transcripts `
#     "7670345621838327729 7671846982315421947" `
#     "千川,全域推广,追投,商品卡,千展,冷启动,ROI,GMV,素材,计划,直播间,代投,跑量,抖店"
#
# 环境变量:
#   WHISPER_MODEL — 模型完整路径（默认 %USERPROFILE%\whisper.cpp\models\ggml-large-v3-turbo.bin）
#   WHISPER_CLI   — whisper-cli 可执行文件（默认 whisper-cli，Windows 未加入 PATH 时指定 whisper-cli.exe 完整路径）
# ============================================================

param(
    [Parameter(Mandatory = $true)][string]$Src,
    [Parameter(Mandatory = $true)][string]$Out,
    [string]$Skip = "",
    [string]$Prompt = "千川,全域推广,追投,商品卡,千展,冷启动,ROI,GMV,素材,计划,直播间,代投,跑量,抖店"
)

$ErrorActionPreference = "Stop"

# --- 可执行文件与模型路径 ---
$Cli = if ($env:WHISPER_CLI) { $env:WHISPER_CLI } else { "whisper-cli" }
$DefaultModel = Join-Path $env:USERPROFILE "whisper.cpp\models\ggml-large-v3-turbo.bin"
$Model = if ($env:WHISPER_MODEL) { $env:WHISPER_MODEL } else { $DefaultModel }

# --- 前置检查 ---
if (-not (Get-Command $Cli -ErrorAction SilentlyContinue)) {
    Write-Host "错误: 找不到 whisper-cli ($Cli)。macOS: brew install whisper-cpp; Windows: 下载官方 Releases whisper-bin-x64.zip 解压后加入 PATH，或用 WHISPER_CLI 指定 whisper-cli.exe 完整路径。" -ForegroundColor Red
    exit 1
}
if (-not (Test-Path $Model)) {
    Write-Host "错误: 模型不存在: $Model (见 references/model-download.md)" -ForegroundColor Red
    exit 1
}
New-Item -ItemType Directory -Force -Path $Out | Out-Null

# --- 批量转写 ---
$count = 0; $skipCount = 0; $fail = 0
$audioFiles = Get-ChildItem -Path $Src -File | Where-Object { $_.Extension -in ".wav", ".mp3", ".flac", ".m4a" }

foreach ($f in $audioFiles) {
    $id = $f.BaseName
    $txtPath = Join-Path $Out "$id.txt"

    # 跳过列表
    if ($Skip) {
        $skipIds = $Skip -split "\s+"
        if ($skipIds -contains $id) {
            Write-Host "SKIP $id"
            $skipCount++
            continue
        }
    }

    # 已存在则跳过（断点续跑）
    if ((Test-Path $txtPath) -and ((Get-Item $txtPath).Length -gt 0)) {
        Write-Host "EXISTS $id (跳过)"
        $count++
        continue
    }

    Write-Host "=== $id ==="
    & $Cli -m $Model -l zh --prompt $Prompt -f $f.FullName -otxt -of (Join-Path $Out $id) 2>$null
    if ($LASTEXITCODE -eq 0) {
        $chars = if (Test-Path $txtPath) { [System.IO.File]::ReadAllText($txtPath).Length } else { 0 }
        Write-Host "  OK -> $txtPath ($chars 字符)"
        $count++
    }
    else {
        Write-Host "  FAIL $id"
        $fail++
    }
}

Write-Host "=================================="
Write-Host "完成: 成功 $count / 跳过 $skipCount / 失败 $fail"
Write-Host "输出目录: $Out"
if ($fail -gt 0) { exit 1 }
