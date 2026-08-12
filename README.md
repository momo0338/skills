# Momo Skills Core Library (AI Agent 技能库)

> 包含 **23 个通用与专项 AI Agent 技能**，覆盖网页正文提取、智能视频看懂抽帧、媒体音视频下载、万站 CLI 操作、抖音专项 CLI、抖音「我的」个人数据整理、抖音带货翻拍、抖音小店经营数据、千川投流决策、研发资源加速、网络代理管理、企业情报深度调研、微信公众号采集及本地视频语音转写等场景。

---

## 📚 技能目录与概览

| 技能名称 | 目录路径 | 核心用途 | 主要依赖 / 接口 |
|---------|---------|---------|----------------|
| **[claude-real-video](./claude-real-video)** | `claude-real-video/` | 智能视频看懂与抽帧（场景检测变动抽帧、去重、3x3网格拼图、Whisper转写） | `claude-real-video`, `ffmpeg` |
| **[whispercpp](./whispercpp)** | `whispercpp/` | 本地视频批量语音转写 + 画面 OCR 融合纠错（ffmpeg 提音频 + whisper.cpp large-v3-turbo GPU 加速，术语提示词、跳过无关文件、时间戳转写稿；tesseract OCR 提取画面文字线索，LLM 交叉修正同音错字；macOS/Windows 双平台原生运行） | `whisper-cpp`(brew/macOS) 或官方预编译包(Windows), `ffmpeg`, `tesseract`(可选), ggml-large-v3-turbo 模型 |
| **[opencli](./opencli)** | `opencli/` | 万站合一 CLI 工具（覆盖抖音、知乎、B站、YouTube、小红书、雪球等 164 站点 + 10 桌面应用） | Node.js, `@jackwener/opencli`, Chrome Extension |
| **[dy-cli](./dy-cli)** | `dy-cli/` | 抖音全功能 CLI 工具（搜索、无水印音视频/图文下载、热榜 Top 50、点赞/评论/收藏互动、发布与数据分析） | Python `dy-cli` |
| **[dy-wode](./dy-wode)** | `dy-wode/` | 抖音「我的」个人数据整理（登录态下采集喜欢/收藏/观看历史/稍后再看/私信视频，批量取点赞/评论/收藏/转发统计，输出 Markdown/CSV/JSON/Excel 表格；逐分类缓存与中断续跑） | Python `dy-cli`, `openpyxl`, ego lite（ego-browser） |
| **[proxy](./proxy)** | `proxy/` | 代理池获取与管理工具（实时同步 `momo0338/proxy` 节点，支持 HTTP/SOCKS5 轮换、延迟测试与环境变量导出） | Python `proxy_manager.py`, GitHub raw |
| **[dev-resource-accelerator](./dev-resource-accelerator)** | `dev-resource-accelerator/` | 公开 GitHub 仓库、Release、Raw 与归档的镜像优先访问、自动回退和安全拦截 | Python, `git`, `curl` |
| **[yt-dlp](./yt-dlp)** | `yt-dlp/` | 全能音视频下载（最高画质/音质、字幕提取、播放列表批处理、Cookie 认证） | `yt-dlp`, `ffmpeg` |
| **[scrapling](./scrapling)** | `scrapling/` | 本地网页正文提取（Fast/Stealth 无头双模式，自动修复懒加载图片 `data-src`） | Python `scrapling`, `html2text`, `browserforge` |
| **[jina-reader](./jina-reader)** | `jina-reader/` | 云端网页转 Markdown 工具（零本地依赖，支持 AI 图片描述与 Token 过滤） | HTTP API (`r.jina.ai`) |
| **[defuddle](./defuddle)** | `defuddle/` | 网页去杂清洁提取 CLI，快速提取纯净 Markdown，大幅节省 Token | Node.js `defuddle` CLI |
| **[crawl4ai](./crawl4ai)** | `crawl4ai/` | LLM 原生网页提取（Playwright 完整渲染 JS/SPA，BM25 主题过滤 Fit Markdown，JSON CSS 结构化字段抽取） | Python `crawl4ai`, Playwright |
| **[lux](./lux)** | `lux/` | 多平台视频下载 CLI（YouTube、Bilibili、抖音、TikTok 等） | Homebrew `lux`, `ffmpeg` |
| **[mptext-api](./mptext-api)** | `mptext-api/` | 微信公众号 API 工具（支持公众号搜索、文章列表获取、多格式/批量下载） | Python `requests`, mptext.top API |
| **[fengniao-search](./fengniao-search)** | `fengniao-search/` | 风鸟企业与风险情报检索（工商信息、司法风险、经营异常、股东背景等） | Node.js `tool.mjs`, 风鸟 API |
| **[zhihu-search](./zhihu-search)** | `zhihu-search/` | 知乎内容搜索工具 | Python `zhihu-search.py`, 知乎 API |
| **[qibook-company-profile](./qibook-company-profile)** | `qibook-company-profile/` | 企书企业/人员组合查询工具 | Python `combined_query.py`, 企书 API |
| **[qibook-company-wiki-deepresearch](./qibook-company-wiki-deepresearch)** | `qibook-company-wiki-deepresearch/` | 企书企业百科深度调研与结构化报告生成工具 | Python `skill_runner.py`, 企书 API |
| **[analyze-viral-commerce-video](./analyze-viral-commerce-video)** | `analyze-viral-commerce-video/` | 带货视频证据化结构拆解（本地视频/链接/截图输入，抽帧+转写+宣称证据矩阵，输出结构化拆解报告） | Python `PIL`, `ffmpeg`, `whisper`(可选) |
| **[videodl](./videodl)** | `videodl/` | 多平台视频下载 CLI（URL 直下，支持指定平台过滤与保存目录） | Python `videodl` |
| **[dy-fanpai](./dy-fanpai)** | `dy-fanpai/` | 抖音带货视频翻拍（参考视频反推、规划人审、即梦/Ark/小云雀生成、音频/装配/质检、字幕与剪映草稿交付，四闸口+费用硬上限） | Python `dy-fanpai`, `ffmpeg`, `ffprobe` |
| **[dy-doudian](./dy-doudian)** | `dy-doudian/` | 抖音小店（抖店）经营数据工具与 MCP Server（订单/商品/评价/直播/账单只读查询，access_token 自动刷新） | Python `mcp`, `httpx`, 抖店开放平台 API |
| **[dy-qianchuan](./dy-qianchuan)** | `dy-qianchuan/` | 巨量千川投流日报与策略调整（真实ROI/保本ROI、素材12维评分+四分类、账号类型诊断、掉量排查、ROI四层漏斗、HTML看板+每日操作清单） | Python `requests`, `pyyaml`, 千川开放平台 API |

---

## 🤖 自动配置全平台 AI 助手技能

内置自动化脚本，可自动扫描本机已安装的 AI 工具（OpenCode、WorkBuddy、Trae、Claude Code、Gemini/Antigravity、OpenAI Codex、Cursor、Windsurf 等），并将本仓库中的全量技能自动软链接/配置到各个 AI 助手中：

```bash
# 自动检测本机已安装的 AI 助手并一键挂载全量技能
python3 scripts/auto_config_ai.py

# 预览拟配置的 AI 助手与路径 (不实际写文件)
python3 scripts/auto_config_ai.py --dry-run
```

### 支持与已配置的 AI 助手路径

- **OpenCode Agent** (`~/.opencode/skills/`)
- **WorkBuddy AI** (`~/.workbuddy/skills/`)
- **Trae CN / Trae IDE** (`~/.trae-cn/skills/`)
- **Claude Code / Claude Agent** (`~/.claude/skills/`)
- **Google Gemini / Antigravity Agent** (`~/.gemini/config/skills.json` 与 `~/.gemini/config/skills/`)
- **OpenAI Codex Agent** (`~/.codex/skills/`)
- **Cursor IDE** (`~/.cursor/skills/`)
- **Windsurf IDE** (`~/.codeium/windsurf/skills/`)
- **OpenClaw / Cline / Roo Code / OpenHands**

---

## 🛠️ 基础系统依赖安装

我们推荐您使用内置的自动配置脚本来一键安装所有需要的依赖（脚本内置了国内加速镜像）：

```bash
# 自动检测本机缺失的依赖并安装（推荐）
python3 scripts/auto_config_ai.py --install
```

如果您希望手动安装，或者需要查看所有依赖的官方及镜像下载地址，请查阅详细的 **[依赖项下载与安装指南 (DEPENDENCIES.md)](./DEPENDENCIES.md)**。

*(以下是手动安装的基础参考命令)*
```bash
# macOS (Homebrew)
brew install node ffmpeg yt-dlp lux

# Python 全局依赖包 (可加上 -i https://pypi.tuna.tsinghua.edu.cn/simple 提速)
pip install --break-system-packages scrapling html2text browserforge requests yt-dlp dy-cli

# npm 全局工具 (可加上 --registry=https://registry.npmmirror.com 提速)
npm install -g defuddle @jackwener/opencli
```

---

## 🔗 远程仓库与同步

- **GitHub 仓库**：[https://github.com/momo0338/skills.git](https://github.com/momo0338/skills.git)
- **默认分支**：`main`

---

## 🧰 开发与维护

### 开发环境基线

仓库离线测试统一以 Python 3.12 为基线。建议使用项目虚拟环境，避免全局 Python
及其依赖版本污染测试结果：

```bash
uv venv --python 3.12
source .venv/bin/activate
```

CI 会运行技能同步检查、依赖解析回归测试，以及四个含测试套件的技能项目；真实账号、
浏览器写操作和付费 Provider 调用不进入自动 CI。

### 新增技能时（必须同步三处，否则检查失败）

新增一个技能 = 在仓库根目录新建 `<skill-name>/SKILL.md`，然后：

1. **磁盘**：`<skill-name>/` 目录（含 `SKILL.md`）
2. **README**：在「技能目录与概览」表格追加一行，并把开头 `包含 **N 个**` 改为新数量
3. **注册表**：在 `scripts/auto_config_ai.py` 的 `SKILL_DEPS` 中声明依赖与安装命令

### 防漂移检查（三重保障）

`scripts/check_skill_sync.py` 验证磁盘技能目录、README 表格、`SKILL_DEPS` 注册表三方一致：

```bash
# 1. 本地手动检查
python3 scripts/check_skill_sync.py

# 2. 完整依赖自检（含 sync 检查，作为 test_deps 的第 1b 节）
python3 scripts/test_deps.py
```

三重保障：
- **本地 pre-commit 钩子**：安装后每次 `git commit` 自动拦截漂移提交（`scripts/git-pre-commit`）
- **GitHub Actions**：`.github/workflows/skill-sync.yml` 在 push/PR 时自动检查

安装/更新本地钩子：

```bash
cp scripts/git-pre-commit .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit
```
