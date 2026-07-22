# yt-dlp — 全能音视频下载 Skill

> **中文** · [English below](#english)

使用 [yt-dlp](https://github.com/yt-dlp/yt-dlp) 命令行工具从 YouTube、Bilibili、TikTok、Twitter、Vimeo 等数千个平台高速下载音视频，支持最高画质选择、音频提取（MP3/M4A）、字幕抓取、播放列表批处理、SponsorBlock 广告跳过与 Cookie 登录态绕过。

> Command-line audio/video downloader supporting YouTube, Bilibili, TikTok, Twitter, and thousands of other sites. Features format selection, audio extraction, subtitles, playlists, and SponsorBlock.

---

## 这是什么 / What is this

一个让 AI 助手具备专业音视频下载能力的 Skill。当用户提供视频/音频链接或表达下载、音视频提取、字幕保存等需求时，AI 将自动使用 `yt-dlp` 完成任务。

### 核心亮点 / Highlights

- **千站支持**：支持 YouTube、Bilibili、TikTok、Twitter/X、Facebook、Vimeo、SoundCloud 等数千个音视频网站
- **最高画质/音质**：自动探测并下载最高分辨率（4K/8K 60fps）及高码率音频
- **音频独立提取**：一键提取 MP3 / M4A / FLAC / WAV，并支持自动嵌入专辑封面与元数据
- **字幕自动捕获**：支持多语言字幕、自动生成字幕提取与硬嵌入/软嵌入视频
- **Cookie 登录态绑定**：轻松读取浏览器 Cookie 绕过年龄限制、会员限制与防爬防火墙
- **智能广告切除**：集成 SponsorBlock 插件，自动识别并裁剪视频赞助商广告与无用片头片尾

---

## 快速开始 / Quick Start

### 1. 安装依赖

```bash
# 安装 yt-dlp 与 ffmpeg (推荐 Homebrew)
brew install yt-dlp ffmpeg
```

### 2. 检查安装状态

```bash
yt-dlp --version
```

### 3. 基础使用命令

```bash
# 1. 基础视频下载
yt-dlp "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

# 2. 提取 MP3 音频 (含封面)
yt-dlp -x --audio-format mp3 --embed-thumbnail "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

# 3. 查看可用分辨率/格式
yt-dlp -F "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

# 4. 指定 1080p 画质下载
yt-dlp -f "bestvideo[height<=1080]+bestaudio/best" "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

# 5. 读取 Chrome Cookie 下载需要登录的视频
yt-dlp --cookies-from-browser chrome "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
```

---

## 参数速查表 / Option Reference

| 参数 | 全称 | 说明 |
|------|------|------|
| `-f` | `--format` | 指定格式/分辨率，如 `bestvideo+bestaudio` |
| `-F` | `--list-formats` | 列出视频所有可用的视频与音频格式 ID |
| `-x` | `--extract-audio` | 仅提取音频轨 |
| `--audio-format` | `--audio-format` | 指定提取音频格式 (mp3/m4a/flac/wav 等) |
| `-o` | `--output` | 文件保存路径与名称模板 |
| `--write-subs` | `--write-subs` | 下载视频字幕文件 |
| `--write-auto-subs` | `--write-auto-subs` | 下载自动生成的字幕 (Auto-caption) |
| `--embed-subs` | `--embed-subs` | 将字幕软嵌入视频文件中 |
| `--embed-thumbnail` | `--embed-thumbnail` | 将封面图片嵌入 MP3/MP4 中 |
| `--cookies-from-browser` | `--cookies-from-browser` | 从本地浏览器 (chrome/firefox/edge) 读取 Cookie |
| `-I` | `--playlist-items` | 指定播放列表下载范围（如 `1-5,10`） |
| `--sponsorblock-remove` | `--sponsorblock-remove` | 自动裁剪 SponsorBlock 标注的段落 (sponsor/intro/outro) |

---

## 常见问题与解答 / FAQ

**Q: 为什么下载提示需要 FFmpeg？**
yt-dlp 通常分别下载最高质量的视频轨（无声）和音频轨（无图），然后调用 `ffmpeg` 自动合并为一个完整的 MP4/MKV 文件。未安装 FFmpeg 只能下载较低质量的混合流。

**Q: 遇到需要登录才能看的视频怎么办？**
在命令行中加上 `--cookies-from-browser chrome`（或 `firefox`/`edge`），yt-dlp 会直接使用浏览器中已登录的 Cookie 状态。

**Q: 视频下载速度变慢或出现 403 报错？**
视频网站会频繁更新防爬策略，请保持 yt-dlp 为最新版本：
```bash
yt-dlp --update-to nightly
```

---

## 相关文档 / Related Docs

- **SKILL.md** — 完整技能指令与使用规范
- **[yt-dlp GitHub](https://github.com/yt-dlp/yt-dlp)** — 官方项目与完整文档

---

<a name="english"></a>

# yt-dlp — Video & Audio Downloader Skill — English

> Feature-rich command-line audio/video downloader supporting YouTube, Bilibili, TikTok, Twitter, and thousands of other sites.

## What is this

A skill that gives AI assistants professional video and audio downloading capabilities. Provides full support for quality selection, audio extraction, subtitles, playlist batching, and browser cookies.

## Quick Start

1. Install: `brew install yt-dlp ffmpeg`
2. Download video: `yt-dlp "https://www.youtube.com/watch?v=xxx"`
3. Extract MP3: `yt-dlp -x --audio-format mp3 --embed-thumbnail "https://www.youtube.com/watch?v=xxx"`
4. Use browser cookies: `yt-dlp --cookies-from-browser chrome "https://www.youtube.com/watch?v=xxx"`

## Dependencies

- [yt-dlp](https://github.com/yt-dlp/yt-dlp)
- [FFmpeg](https://ffmpeg.org/) (recommended for merging audio/video streams)
