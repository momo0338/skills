# Lux — 多平台视频下载 Skill

> **中文** · [English below](#english)

使用 [lux](https://github.com/iawia002/lux) 命令行工具下载 YouTube、Bilibili、抖音、TikTok 等 40+ 平台的视频，支持画质选择、播放列表、多线程加速等功能。

> Download videos from 40+ platforms (YouTube, Bilibili, Douyin, TikTok, etc.) via [lux](https://github.com/iawia002/lux) CLI. Supports quality selection, playlists, multi-threading, and more.

---

## 这是什么 / What is this

一个让 AI 助手具备视频下载能力的 Skill。用户提供视频 URL，AI 自动调用 lux 完成下载，支持画质选择、仅音频提取、批量下载等高级功能。

### 核心亮点 / Highlights

- **40+ 平台支持**：YouTube、Bilibili、抖音、TikTok、优酷、爱奇艺、腾讯视频等
- **最高画质默认**：自动选择最高可用画质，也可手动指定
- **多线程加速**：`-m` 参数开启多线程，显著提升下载速度
- **仅音频模式**：`--audio-only` 提取音频（适合音乐/播客）
- **播放列表下载**：一键下载整个播放列表
- **批量下载**：从文件读取 URL 列表批量处理
- **零配置启动**：通过 Homebrew 安装即用，无需 API 密钥

---

## 安装信息 / Installation

| 项目 | 详情 |
|------|------|
| **安装路径** | `/opt/homebrew/bin/lux` |
| **当前版本** | 0.24.1 |
| **安装方式** | `brew install lux` |
| **依赖** | FFmpeg（视频合并） |

### 安装命令

```bash
# 安装 lux
brew install lux

# 安装 FFmpeg（合并音视频流需要）
brew install ffmpeg
```

### 验证安装

```bash
lux --version
```

---

## 支持平台 / Supported Platforms

| 平台 | 域名 | 状态 |
|------|------|:----:|
| YouTube | youtube.com, youtu.be | ✅ |
| Bilibili | bilibili.com | ✅ |
| 抖音 | douyin.com | ✅ |
| TikTok | tiktok.com | ✅ |
| 优酷 | youku.com | ✅ |
| 爱奇艺 | iqiyi.com | ✅ |
| 腾讯视频 | v.qq.com | ✅ |
| Vimeo | vimeo.com | ✅ |
| Twitter/X | twitter.com, x.com | ✅ |
| Facebook | facebook.com | ✅ |
| Instagram | instagram.com | ✅ |
| 芒果TV | mgtv.com | ✅ |
| 西瓜视频 | ixigua.com | ✅ |

> 完整平台列表见 [lux 官方文档](https://github.com/iawia002/lux#supported-sites)

---

## 快速开始 / Quick Start

### 1. 下载视频（默认最高画质）

```bash
lux "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
```

### 2. 先查看视频信息

```bash
lux -i "https://www.bilibili.com/video/BV1xx411c7mD"
```

### 3. 指定画质下载

```bash
# 查看可用画质
lux -i <URL>

# 选择指定画质
lux -f <格式ID> <URL>
```

---

## 使用示例 / Examples

### 基础下载

```bash
# YouTube
lux "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

# Bilibili
lux "https://www.bilibili.com/video/BV1xx411c7mD"

# 抖音
lux "https://www.douyin.com/video/1234567890"

# TikTok
lux "https://www.tiktok.com/@user/video/1234567890"
```

### 高级用法

```bash
# 多线程加速下载
lux -m "https://www.youtube.com/watch?v=xxxxx"

# 仅下载音频
lux --audio-only "https://www.youtube.com/watch?v=xxxxx"

# 指定输出目录
lux -o ~/Downloads/videos <URL>

# 自定义文件名
lux -O "我的视频" <URL>

# 下载整个播放列表
lux -p "https://www.youtube.com/playlist?list=PLxxxxx"

# 使用 Cookie（下载需登录的内容）
lux -c cookies.txt <URL>

# 输出 JSON 格式信息
lux -j <URL>
```

### 批量下载

创建 `urls.txt`，每行一个 URL：

```
https://www.youtube.com/watch?v=xxxxx
https://www.bilibili.com/video/BVxxxxxx
https://v.qq.com/x/cover/xxxxx.html
```

执行：

```bash
lux -F urls.txt
```

---

## 参数速查 / Parameter Reference

| 参数 | 全称 | 说明 |
|------|------|------|
| `-i` | `--info` | 仅显示视频信息，不下载 |
| `-f` | `--stream-format` | 指定画质格式 ID |
| `-o` | `--output-path` | 输出目录 |
| `-O` | `--output-name` | 输出文件名 |
| `-p` | `--playlist` | 下载整个播放列表 |
| `-m` | `--multi-thread` | 启用多线程下载 |
| `-ao` | `--audio-only` | 仅下载音频 |
| `-c` | `--cookie` | 指定 Cookie 文件 |
| `-F` | `--file` | 从文件读取 URL 列表 |
| `-j` | `--json` | 以 JSON 格式输出信息 |
| `-s` | `--silent` | 静默模式 |
| `-d` | `--debug` | 调试模式（排错用） |

---

## 故障排除 / Troubleshooting

| 问题 | 原因 | 解决方案 |
|------|------|---------|
| 下载失败 | URL 无效或网络问题 | `lux -d <URL>` 启用调试查看详情 |
| 需要登录才能观看 | 受限内容 | 导出浏览器 Cookie：`lux -c cookies.txt <URL>` |
| 画质不理想 | 默认格式不匹配 | `lux -i <URL>` 查看可用画质后 `-f` 指定 |
| `Library not loaded: libx265` | FFmpeg 依赖损坏 | `brew reinstall ffmpeg x265` |
| `developer cannot be verified` | macOS 安全限制 | `xattr -d com.apple.quarantine /opt/homebrew/bin/lux` |
| 地区限制无法下载 | 平台地区屏蔽 | 需配置代理：`lux -x http://proxy:port <URL>` |
| 音视频未合并 | 缺少 FFmpeg | `brew install ffmpeg` |

---

## 常见问题 / FAQ

**Q: 免费吗？**
完全免费开源（[Apache-2.0 License](https://github.com/iawia002/lux/blob/master/LICENSE)），无使用限制。

**Q: 支持下载 4K/8K 视频吗？**
取决于平台提供的画质。用 `lux -i <URL>` 查看可用画质列表，选择最高分辨率下载。

**Q: Bilibili 需要大会员视频怎么下？**
需要导出已登录大会员账号的 Cookie 文件，通过 `-c cookies.txt` 参数使用。

**Q: 下载速度慢怎么办？**
1. 添加 `-m` 启用多线程
2. 检查网络连接和代理配置
3. 部分平台有服务端限速，无法突破

**Q: 可以只提取音频吗？**
可以。使用 `--audio-only` 参数，适用于音乐、播客等场景。

---

## 依赖 / Dependencies

- [lux](https://github.com/iawia002/lux) ≥ 0.24.1（Homebrew 安装）
- [FFmpeg](https://ffmpeg.org/)（音视频流合并，Homebrew 安装）
- [x265](https://www.videolan.org/developers/x265.html)（HEVC 编解码，随 FFmpeg 安装）

---

## 相关文档 / Related Docs

- **SKILL.md** — 技能触发规则与完整命令参考
- **[lux GitHub](https://github.com/iawia002/lux)** — 官方文档与最新版本
- **[FFmpeg 文档](https://ffmpeg.org/documentation.html)** — 音视频处理参考

---

<a name="english"></a>

# Lux — Multi-platform Video Downloader Skill — English

> Download videos from 40+ platforms via lux CLI. Supports quality selection, playlists, multi-threading, audio-only mode, and batch downloading.

## What is this

A skill that gives AI assistants video downloading capabilities. Provide a video URL, and the AI handles download with optimal quality, format selection, and output management.

## Highlights

- **40+ platforms**: YouTube, Bilibili, Douyin, TikTok, Vimeo, Twitter, and more
- **Best quality by default**: Auto-selects highest available quality
- **Multi-threaded**: `-m` flag for significantly faster downloads
- **Audio-only**: `--audio-only` for music/podcast extraction
- **Playlist support**: Download entire playlists with `-p`
- **Batch processing**: Read URL lists from file with `-F`

## Quick Start

1. Install: `brew install lux && brew install ffmpeg`
2. Download: `lux "https://www.youtube.com/watch?v=xxxxx"`
3. Check info first: `lux -i <URL>`

## FAQ

**Q: Is it free?** Yes, fully open source (Apache-2.0), no usage limits.

**Q: 4K/8K support?** Depends on platform. Use `lux -i <URL>` to see available qualities.

**Q: Slow downloads?** Use `-m` for multi-threading. Some platforms enforce rate limits.

**Q: Audio only?** Use `--audio-only` flag.

## Dependencies

- [lux](https://github.com/iawia002/lux) ≥ 0.24.1 (via Homebrew)
- [FFmpeg](https://ffmpeg.org/) (for stream merging)
