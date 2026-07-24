# claude-real-video Skill

让 AI 智能体 (Claude, ChatGPT, Gemini 等) 拥有高效视频感知能力的智能关键帧提取与语音转写技能。

## 功能亮点

- **场景感知抽帧 (Scene Detection)**：依据画面镜头变动智能截取，避免固定时间抽帧。
- **滑动窗口去重 (Deduplication)**：自动剔除重复出现的镜头与长时间停留的静态 PPT。
- **网格拼图 (--grid)**：将 9 张连续关键帧合成为 1 张 3x3 拼图，降低 90% 图片 Token 消耗。
- **Whisper 语音转写**：自动导出精准时间戳的字幕文本（支持说话人识别 `--speakers`）。
- **完整生态联动**：可与 `yt-dlp`、`dy-cli`、`lux`、`proxy` 无缝配合使用。

## 使用文档

具体使用方法、常用 CLI 参数表、智能体推荐工作流与多 Skill 协同指南请查阅 [SKILL.md](./SKILL.md)。
