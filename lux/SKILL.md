---
name: lux-video-downloader
description: 使用 lux 下载各平台视频的工具
version: 1.0.0
---

# lux 视频下载 Skill

使用 [lux](https://github.com/iawia002/lux) 下载各平台视频。

## 安装状态

lux 已安装：`/opt/homebrew/bin/lux`，版本 0.24.1

## 支持平台

| 平台 | 域名 | 状态 |
|------|------|------|
| YouTube | youtube.com, youtu.be | ✅ |
| Bilibili | bilibili.com | ✅ |
| 优酷 | youku.com | ✅ |
| 爱奇艺 | iqiyi.com | ✅ |
| 腾讯视频 | v.qq.com | ✅ |
| 抖音 | douyin.com | ✅ |
| Vimeo | vimeo.com | ✅ |
| Twitter | twitter.com | ✅ |
| Facebook | facebook.com | ✅ |
| Instagram | instagram.com | ✅ |
| TikTok | tiktok.com | ✅ |

以及更多平台...

## 常用命令

### 1. 查看视频信息（不下载）

```bash
lux -i <URL>
```

### 2. 下载视频（默认最高画质）

```bash
lux <URL>
```

### 3. 选择画质下载

```bash
# 先查看可用画质
lux -i <URL>

# 指定画质下载
lux -f <格式ID> <URL>
```

### 4. 下载音频

```bash
lux --audio-only <URL>
```

### 5. 指定输出路径

```bash
lux -o /path/to/save <URL>
```

### 6. 指定文件名

```bash
lux -O "自定义文件名" <URL>
```

### 7. 下载播放列表

```bash
lux -p <播放列表URL>
```

### 8. 多线程下载（更快）

```bash
lux -m <URL>
```

### 9. 使用 Cookie 下载（需要登录的内容）

```bash
lux -c cookie.txt <URL>
```

### 10. 从文件批量下载

```bash
lux -F urls.txt
```

## 参数说明

| 参数 | 说明 |
|------|------|
| `-i, --info` | 仅显示视频信息，不下载 |
| `-f, --stream-format` | 指定画质格式 ID |
| `-o, --output-path` | 输出目录 |
| `-O, --output-name` | 输出文件名 |
| `-p, --playlist` | 下载整个播放列表 |
| `-m, --multi-thread` | 多线程下载 |
| `-ao, --audio-only` | 仅下载音频 |
| `-c, --cookie` | Cookie 文件 |
| `-F, --file` | URL 列表文件 |
| `-j, --json` | 输出 JSON 格式信息 |
| `-s, --silent` | 静默模式 |

## 使用示例

### 下载 YouTube 视频

```bash
lux "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
```

### 下载 Bilibili 视频

```bash
lux "https://www.bilibili.com/video/BV1xx411c7mD"
```

### 下载 Bilibili 播放列表

```bash
lux -p "https://www.bilibili.com/video/BV1xx411c7mD?t=1"
```

### 下载抖音视频

```bash
lux "https://www.douyin.com/video/1234567890"
```

### 下载 TikTok 视频

```bash
lux "https://www.tiktok.com/@user/video/1234567890"
```

### 查看视频信息（JSON 格式）

```bash
lux -j "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
```

### 下载到指定目录

```bash
lux -o ~/Downloads/videos "https://www.bilibili.com/video/BV1xx411c7mD"
```

### 仅下载音频（MP3）

```bash
lux --audio-only "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
```

## 批量下载

创建 `urls.txt` 文件，每行一个 URL：

```
https://www.youtube.com/watch?v=xxxxx
https://www.bilibili.com/video/BVxxxxxx
https://v.qq.com/x/cover/xxxxx.html
```

然后：

```bash
lux -F urls.txt
```

## 注意事项

1. **需要登录的内容**：某些视频需要 Cookie，可使用浏览器插件导出 Cookie 文件
2. **地区限制**：部分内容可能有地区限制，可能需要代理
3. **画质选择**：使用 `-i` 查看可用画质，再用 `-f` 指定
4. **下载速度**：默认单线程，添加 `-m` 可启用多线程加速

## 故障排除

### 下载失败

```bash
# 检查 URL 是否正确
lux -i <URL>

# 启用调试模式
lux -d <URL>
```

### 需要登录

```bash
# 导出 Cookie 后使用
lux -c cookies.txt <URL>
```

### 画质不好

```bash
# 查看可用画质
lux -i <URL>

# 选择最高画质
lux -f <最高画质ID> <URL>
```

### FFmpeg 合并错误

如果遇到 `Library not loaded: libx265` 错误：

```bash
# 重新安装 ffmpeg 和 x265
brew reinstall ffmpeg x265
```

### macOS 安全限制

如果遇到 `cannot be opened because the developer cannot be verified`：

```bash
# 移除隔离属性
xattr -d com.apple.quarantine /opt/homebrew/bin/lux
```
