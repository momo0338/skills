---
name: yt-dlp
description: |
  使用 yt-dlp 从 YouTube、Bilibili、Twitter/X、TikTok、Vimeo 等数千个视频/音频网站下载音视频内容。
  支持画质选择（1080p/4K/8K）、音频提取（MP3/M4A/FLAC）、字幕下载（自动生成/多语言字幕）、播放列表/频道批量下载、Cookie 登录态绕过限权、SponsorBlock 自动跳过广告段落等功能。
  适用于视频下载、音频提取、字幕抓取、播客保存、批量音视频备份等场景。
  触发词：yt-dlp、下载视频、下载音频、提取MP3、下载字幕、下载播放列表、YouTube下载、B站视频下载、TikTok视频下载。
version: 1.0.0
---

# yt-dlp — 全能音视频下载 Skill

> 强大的命令行音视频下载工具，基于 youtube-dl 开发，支持数千个主流与小众网站。

## Overview

[yt-dlp](https://github.com/yt-dlp/yt-dlp) 是功能最丰富、更新最频繁的音视频下载命令行工具。支持选择画质/音质、下载字幕/封面、提取音频、播放列表批处理、自动合并分段、使用浏览器 Cookie 绕过登录限制等。

## 安装指南 / Installation

### 安装方式

```bash
# macOS (推荐 Homebrew)
brew install yt-dlp ffmpeg

# Python pip 安装
python3 -m pip install -U "yt-dlp[default]"

# 独立二进制文件 (macOS)
curl -L https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp_macos -o /usr/local/bin/yt-dlp
chmod +x /usr/local/bin/yt-dlp
```

> **注意**：强力推荐同时安装 `ffmpeg`，用于合并视频轨与音频轨以及转换文件格式。

### 检查与更新

```bash
# 查看版本
yt-dlp --version

# 更新到最新 nightly 版本 (推荐)
yt-dlp --update-to nightly
```

## When to Use

- 用户提供视频/音频链接（如 YouTube、Bilibili、TikTok、Twitter、Vimeo 等）并要求下载
- 用户需要提取视频中的音频（如转换为 MP3、M4A）
- 用户需要下载字幕文件（SRT、VTT 等）
- 用户要求批量下载整个播放列表（Playlist）或频道（Channel）
- 用户需要下载特定画质（4K、1080p 60fps 等）

## 常用参数速查

| 参数 | 全称 | 说明 | 示例 |
|------|------|------|------|
| `-f` | `--format` | 指定视频/音频格式 | `-f "bestvideo[height<=1080]+bestaudio/best"` |
| `-F` | `--list-formats` | 列出可用画质/音质列表 | `yt-dlp -F <URL>` |
| `-x` | `--extract-audio` | 提取音频 | `yt-dlp -x <URL>` |
| `--audio-format` | `--audio-format` | 指定提取的音频格式 | `--audio-format mp3` |
| `-o` | `--output` | 自定义文件名输出模板 | `-o "%(title)s.%(ext)s"` |
| `--write-subs` | `--write-subs` | 下载字幕 | `--write-subs --sub-lang zh-Hans,en` |
| `--write-auto-subs` | `--write-auto-subs` | 下载自动生成的字幕 | `--write-auto-subs` |
| `--embed-subs` | `--embed-subs` | 将字幕嵌入视频文件 | `--embed-subs` |
| `--embed-thumbnail` | `--embed-thumbnail` | 将封面图嵌入视频/音频 | `--embed-thumbnail` |
| `--cookies-from-browser` | `--cookies-from-browser` | 读取浏览器 Cookie 绕过登录 | `--cookies-from-browser chrome` |
| `-I` | `--playlist-items` | 下载播放列表中的指定项 | `-I 1-5,10` |
| `--sponsorblock-remove` | `--sponsorblock-remove` | 自动剪掉视频赞助商广告段落 | `--sponsorblock-remove sponsor` |

## 常用场景与命令行示例

### 1. 基础下载

```bash
# 自动下载最佳质量（视频+音频自动合并）
yt-dlp "https://www.youtube.com/watch?v=xxx"

# 下载并保存到指定目录与文件名
yt-dlp -o "~/Downloads/%(title)s.%(ext)s" "https://www.youtube.com/watch?v=xxx"
```

### 2. 挑选画质 (Format Selection)

```bash
# 查看所有可用画质与 Format ID
yt-dlp -F "https://www.youtube.com/watch?v=xxx"

# 指定最高 1080p 分辨率下载
yt-dlp -f "bestvideo[height<=1080]+bestaudio/best" "https://www.youtube.com/watch?v=xxx"

# 指定 Format ID 下载（例如 137 为 1080p 视频，140 为 AAC 音频）
yt-dlp -f 137+140 "https://www.youtube.com/watch?v=xxx"
```

### 3. 仅提取音频 (Audio Only)

```bash
# 提取为最佳品质 MP3 并嵌入封面与元数据
yt-dlp -x --audio-format mp3 --audio-quality 0 --embed-thumbnail --add-metadata "https://www.youtube.com/watch?v=xxx"

# 提取为 M4A 音频（无损重封装）
yt-dlp -x --audio-format m4a "https://www.youtube.com/watch?v=xxx"
```

### 4. 下载字幕 (Subtitles)

```bash
# 查看所有可用字幕
yt-dlp --list-subs "https://www.youtube.com/watch?v=xxx"

# 下载中英文字幕并转换为 srt 格式
yt-dlp --write-subs --write-auto-subs --sub-lang "zh-Hans,zh-CN,en" --convert-subs srt --skip-download "https://www.youtube.com/watch?v=xxx"

# 下载视频并将字幕硬嵌入/软嵌入视频中
yt-dlp -f "bestvideo+bestaudio" --write-subs --embed-subs "https://www.youtube.com/watch?v=xxx"
```

### 5. 播放列表与频道批处理 (Playlists)

```bash
# 下载整个播放列表（前 10 个视频）
yt-dlp -I 1-10 "https://www.youtube.com/playlist?list=xxx"

# 按序号编号保存播放列表
yt-dlp -o "%(playlist_index)s - %(title)s.%(ext)s" "https://www.youtube.com/playlist?list=xxx"
```

### 6. 使用 Cookie 绕过年龄/登录限制 (Authentication)

```bash
# 直接从本地 Chrome / Firefox / Edge 获取 Cookie
yt-dlp --cookies-from-browser chrome "https://www.youtube.com/watch?v=xxx"

# 使用已导出的 cookies.txt 文件
yt-dlp --cookies cookies.txt "https://www.youtube.com/watch?v=xxx"
```

### 7. 自动裁剪赞助商广告 (SponsorBlock)

```bash
# 自动去除视频中的赞助广告、片头片尾
yt-dlp --sponsorblock-remove sponsor,intro,outro "https://www.youtube.com/watch?v=xxx"
```

## 输出文件名模板变量 (%())s

- `%(title)s`: 视频标题
- `%(ext)s`: 文件扩展名
- `%(id)s`: 视频 ID
- `%(uploader)s`: 上传者名称
- `%(upload_date)s`: 上传日期 (YYYYMMDD)
- `%(playlist_title)s`: 播放列表名称
- `%(playlist_index)s`: 在播放列表中的序号

## 故障排除 / Troubleshooting

| 现象 / 报错 | 原因 | 解决方法 |
|------------|------|----------|
| `FFmpeg not found` | 未安装 FFmpeg 导致无法合并音视频或转换格式 | 运行 `brew install ffmpeg` |
| `Sign in to confirm you’re not a bot` | 触发了网站的防爬/验证码 | 增加 `--cookies-from-browser chrome` |
| `Requested format is not available` | 指定的 `-f` 画质 ID 不存在 | 先运行 `yt-dlp -F <URL>` 查询可用格式 |
| 视频下载非常缓慢 | 平台服务端限制速率 | 使用 `--update-to nightly` 更新到最新修复版 |
| `HTTP Error 403: Forbidden` | 访问凭证过期或规则变动 | 更新 yt-dlp: `yt-dlp -U` 并尝试配合 Cookie |
