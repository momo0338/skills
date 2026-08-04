# WP0 基线清点 · 原项目 → dy-fanpai 映射

> 配套：`EXECUTION_PLAN.md` v2.2（唯一执行权威）、`archive/DY_FANPAI_DETAILED_REFERENCE.md` v1.2
> 原项目：`/Users/zhugx/src/daihuo-fanpai` · HEAD `ffc22e34cb35477b04967163c3932002ed4f3fed` · tracked 干净 · `.workbuddy/` 未触碰（只读）
> 本文件是 WP0 交付物之一，进入 WP1 冻结门后会据此产出 `DESIGN.md` 与 `pyproject.toml`。

---

## 1. 原项目快照（事实）

- **形态**：21 个平铺 `.py`（全在根目录，无 `__init__.py`，非 Python 包）+ 1 个 `config.py` 配置层。
- **运行模型**：每个脚本可独立 `python3 xxx.py` 执行，靠同目录相对 import 互相引用（如 `plan_segments` 被多处 import）。
- **无**：`pyproject.toml` / `setup.py` / `requirements.txt` / `tests/` / CI / 包结构。
- **定位**：本质上是一个 "agent skill 目录"（README 写装法为 clone 到 `~/.claude/skills/`）。
- **许可证**：MIT · Copyright (c) 2026 wangcanyu（见 §7，重构后须保留并叠加新版权）。
- **文档**：`README.md` / `README.en.md` / `DESIGN.md`（数据契约+设计理由）/ `SKILL.md`（skill 定义+已知坑索引）。
- **样例 fixtures**：`references/` 下有 5 个文件（见 §6）。

---

## 2. 脚本 → 新流程映射表

| # | 原文件 | 角色 | 新流程映射 | 输入 | 输出 | 关键依赖 | 失败/恢复 |
|---|---|---|---|---|---|---|---|
| 1 | `config.py` | 纯库 | → 新 `config` 模块（密钥/路径集中层） | 环境变量 + `~/.config/daihuo-fanpai/*` | 模块常量+函数 | 无 | 无 key → `raise`；`*_status()` 捕获供 doctor |
| 2 | `seed_reverse.py` | 入口+库 | 反推腿1（Ark Seed） | video + `ARK_API_KEY` | `shotlist.json` | ffmpeg/ffprobe, requests | **无重试无断点**；HTTP≠200 直抛 |
| 3 | `k3_reverse.py` | 入口 | 反推腿2（Kimi K3） | video + `KIMI_API_KEY` | `shotlist_k3.json` | 复用 seed 的 4 函数 | 3 次连接抖动重试（仅 ConnectionError） |
| 4 | `merge_reverse.py` | 入口 | 双反推合并（证据准备，不终审） | seed+alt json, video | `dossier.md`, `merged_draft.json`, frames | ffmpeg(silencedetect) | 帧幂等；无其它重试 |
| 5 | `needed_assets.py` | 入口 | 产品图清单 | `shotlist.json` | `assets.skeleton.json` | `plan_segments.FORM_MAP` | 无 |
| 6 | `plan_segments.py` | 入口+库 | **流水线大脑**：分段/路由/提示词/完备性关卡 | `shotlist`,`assets` | `segments.json`+`.md` | **纯标准库** | 无重试；坏方案靠 `warns`+人审兜底 |
| 7 | `patch_cast.py` | 入口 | 群戏多人补丁 | `segments.json`,`cast.json` | **原地覆写** segments.json | 纯标准库 | 正则剥离旧声明，**重复执行有风险** |
| 8 | `localize_seed.py` | 入口 | B 模式台词初稿（Ark） | shotlist, `facts.json`, `qianchuan/` | `script.txt` | Ark | 弹药包缺失静默跳过；无重试 |
| 9 | `localize_apply.py` | 入口 | 台词回写 segments | `edits.json` | 覆写 segments | 纯标准库 | 字数偏差>8 告警；未知段名告警 |
| 10 | `cut_audio.py` | 入口 | 原音复用切段 + **2 秒闸** + timing | `segments.json`, video, shotlist | `<seg>.wav`+`timing.json` | ffmpeg | `check=True`，任一段失败整体崩 |
| 11 | `tts_segments.py` | 入口 | CosyVoice 配音 | `segments.json` | `<seg>.wav`+`timing.json`+`_tts_manifest` | CosyVoice venv + **外部 tts-drama skill** | 子进程失败 `return` 不抛；缺段静默 |
| 12 | `vc_segments.py` | 入口+库 | Seed-VC 换声 | `audio_dir` | `<seg>.wav` | `~/seed-vc` venv | 单段失败进 fails 继续；无断点续跑 |
| 13 | `gen_segments.py` | 入口 | **生成调度**（提交/轮询/下载/断点） | `segments.json` | `clips/<seg>.mp4`+`.meta.json` | 即梦 CLI / ark_gen / xyq_gen / ffmpeg | **三层重试+解码探针+断点续跑**（最成熟） |
| 14 | `ark_gen.py` | 入口+库 | 火山 Ark 后端（i2v/mm/t2v） | 图片/音频/prompt | 视频文件 | requests | urlretrieve 4 次；**无解码探针** |
| 15 | `xyq_gen.py` | 入口+库 | 小云雀后端（pippit-tool-cli） | prompt/图片/音频 | 视频文件 | subprocess CLI | 脆弱输出解析；**无解码探针** |
| 16 | `assemble.py` | 入口 | 归一化拼接 + 铺配音轨 | segments+clips+audio | `FULL.mp4` | ffmpeg | `check=True` 失败即崩；缺片跳过 |
| 17 | `qc_lipsync.py` | 入口 | 帧级口型质检 harness（只产证据） | segments, video, clips | `qc_frames/` | ffmpeg 抽帧 | `check=False` 容错 |
| 18 | `judge.py` | 入口 | 三看漏斗 90 分评委（Ark 双视频对比） | video, target | `<video>.judge.json` | Ark | 主打分无重试；保真度对比 try 包裹 |
| 19 | `export_subs.py` | 入口+库 | SRT + 贴字清单 | segments | `.srt` | 纯标准库 | 无 |
| 20 | `deliver.py` | 入口+库 | 交付：剪映草稿 / 烧字幕成品 | segments, clips, audio | 草稿目录 / 成品 mp4 | pyJianYingDraft | 缺 FULL.mp4 直接 `sys.exit` |
| 21 | `doctor.py` | 入口 | 环境体检（聚合入口） | 无 | 体检报告 | 各 CLI/API 探针 | 非 core 项一律 WARN 不挡开工 |

**内部耦合（重构必须保留或显式打断）**
- `config.py` 被 9 个模块引用（密钥/路径单一来源，必须保留）。
- `seed_reverse` ⇄ `k3_reverse`：共享 `detect_cuts / video_info / make_upload_clip / extract_json / SCHEMA`——**双反推同源切点是"可比较"前提**，不可破坏。
- `gen_segments` 运行期**动态 import** `ark_gen` / `xyq_gen`（唯一插件式后端加载点，是 Provider 抽象的良好雏形）。
- `export_subs.sentences/fmt_ts` 被 `deliver` 复用；`vc_segments.seedvc_status` / `deliver.to_wsl` 被 `doctor` 复用。

---

## 3. 流水线核心规则（逐条代码定位）

### 3.1 硬切（hard-cut）
- **唯一实现** `seed_reverse.py:58-63` `detect_cuts()`：`ffmpeg select='gt(scene,thresh)'` 抽场景切换时间戳。
- **阈值双标（待裁决）**：函数签名默认 `0.3`，但两个调用方都传 **0.15**（`reverse(scene_thresh=0.15)`、CLI `--scene-thresh` 默认 0.15）。CLI help 注"0.15 抓同机位跳剪，0.3 漏检"。
- **首帧噪声**：丢弃 `t <= 0.3` 的切点。
- **切点→镜头**：`ark_reverse()` L92-94 把 cuts 转闭区间写进 prompt，强制 "shots 严格对应 N 段，start/end 用给定值"——**切分由 ffmpeg 确定性完成，VLM 只填描述不决定边界**。
- **下游不重切**：`plan_segments` 只做归并(`group_shots`)+拆超长(`split_long_shots`)。
- **内部硬切上限** `MAX_CUTS = 3`（≈2 个内部硬切，即梦侧 5 崩）。

### 3.2 时长处理
| 约束 | 值 | 出处 |
|---|---|---|
| 单段目标上限 `MAX_DUR` | 12 | `plan_segments.py:24`（注释 mm 硬上限 15，留余量） |
| 单段最多镜头 `MAX_CUTS` | 3 | `plan_segments.py:25` |
| 拆镜触发阈值 `max_dur` | 15 | `split_long_shots(shots, max_dur=15)` |
| 拆分份数 | `ceil(dur/12)` | `plan_segments.py:50` |
| 段时长最终值 | `max(4, min(15, ceil(end-start)))` | `plan_segments.py:241` |
| 生成时长自动上调上限 | 15s | `gen_segments.py:43` |
| 逼近上限告警线 | 14.5s | `gen_segments.py:46` |

- **双标（待裁决）**：`split_long_shots` 用 **15** 作触发阈值，却用 **12**(`MAX_DUR`) 算份数。13s 镜不拆，16s 镜拆成 2 段各 8s。
- **配音驱动时长自适应** `gen_segments.py:32-47`：仅 `type=="mm"`；`ad > duration + 0.25` 才上调（`+0.25` 容差防静音垫尾误触发）；`ad > 14.5` 告警。
- **总时长约束：代码里不存在**，成片总长 = 各 clip 实际时长累加。
- **对齐口径**：`assemble` 配音 `apad -t 视频时长`，无配音 `anullsrc` 等长静音——**以视频为准，音频服从**。

### 3.3 Prompt 固定句（不可变模板，重构必须逐字保留）
- **全局尾巴** `plan_segments.py:23`：`"电影质感,真实生活感。保持无字幕,不要生成BGM或背景音乐,不要生成Logo,不要生成水印。"`
- **口播段模板** `build_kou_prompt()` L151-171：主播声明（有/无 `host_desc` 二选一）+ 逐产品图声明（`@图片{i+2}是{prod_desc}的{label}(以此图为准,不要改产品外观和包装文字)`）+ `{body}。台词{{{dialogue}}}@音频1,主播嘴巴跟随音频节奏自然说话,口型同步。{TAIL}`。
- **hero 段** L198-203、**package 段** L206-208：纯产品质感描述，禁 Logo/水印。
- **★群戏人数硬约束**（patch_cast.py:73）：`"画面中自始至终只有{names}这{len}个角色,不要出现任何其他人物。"` 插入 `"竖屏9:16。"` 之后。**SKILL.md 记载此句是"群戏生命线，永不删"**（07-12 不加会幻觉人物；07-23 无此句口型错乱率 28%，回植后降到 6%）。
- **小云雀防自生语音** `xyq_gen.py:71`：`AUDIO_GUARD = "无人声,无背景音乐。"`（i2v/t2v 自动追加）。
- **反推 SCHEMA + 7 条硬规** `seed_reverse.py:26-51`：第 6 条最关键——"静音字幕残留只进 onscreen_text，严禁写进 dialogue/full_transcript"（治幻听）。
- **K3 第 8 条实体纪律** `k3_reverse.py:72-73`：性别/人数逐人核对，背景物件不脑补，屏上文字逐字抄。
- **评委 RUBRIC** `judge.py:31-34`；**保真度对比** `judge.py:88-91`（旧版只传成片，"保真度"是模型编的，已修）。

### 3.4 「2 秒音频闸」（2-second audio gate）
- **含义**：即梦 `multimodal2video --audio` 要求音频 2–15s；快切段音频常 <2s 被拒（`out of allowed range`）。
- **唯一实现** `cut_audio.py:26-32`：`pad = max(2.0, span)`，ffmpeg `-ac 1 -ar 24000 -af apad=whole_dur={pad}`（单声道 24kHz 匹配即梦上传）。
- **★文档/代码矛盾（必须裁决）**：行内注释与 SKILL.md 都说"只垫到 2s 下限，别垫满规划时长"，但代码 `pad = max(2.0, span)` 在 `span>2` 时**恰垫满规划时长**。实测当前无害（因 `gen` 触发条件是 `ad > duration+0.25`，垫满不会误触发），但语义与注释冲突，WP1 冻结时需二选一明确。

### 3.5 下载与解码
- **稳健下载** `gen_segments.robust_download()` L80-107：**4 次重试**；代理三段策略（`i<2` 强制直连屏蔽环境代理，`i>=2` 回退环境代理，设 `DOWNLOAD_PROXY` 则全程走它）；`size > 10240` 校验；**ffmpeg 解码探针** `ffmpeg -v error -i {dst} -t 2 -f null -` 检出 `Invalid NAL/Invalid data` 即判坏流重下。
- **ark 腿缺解码探针**（xyq 腿也缺）——WP1 应统一补到所有后端。
- **轮询**：即梦 `wait_download()` 40×15s=最长 10 分钟；正则兼容有无空格两种 JSON；`fail`→`"FAIL:..."`；超时→`None`(pending)。

### 3.6 拼接与字幕
- **拼接** `assemble.py`：逐段归一化（`scale=720:1280:force_original_aspect_ratio=decrease,pad=...,setsar=1` + `libx264 -crf 20`）→ `concat` 视频轨 → `concat` 配音轨 → mux（`-c:v copy -c:a aac -b:a 192k`）。`tempfile.mkdtemp` **不清理**；任一段 `check=True` 失败即崩；缺片只打印跳过。
- **字幕时间轴** `deliver.build_entries()`：优先吃 `tts_segments` 的 `audio/seg/timing.json`（逐句真实时长，精确），缺失退化为"按字数占比摊"（粗对齐）。段起点按 clips 实际时长累加（与 assemble 一致）。
- **剪映草稿** `deliver_draft()`：五轨（主视频/配音/BGM空轨/字幕/贴字参考）；素材 `shutil.copy` 进 `<draft>/materials/` 自包含；字幕 `import_srt`；贴字参考轨放原片 `onscreen_text`。**强 WSL 假设**：`to_wsl()` 把 `D:\x` → `/mnt/d/x`，`fix_json_paths()` 反向改写回 `X:/`。
- **烧字幕成品** `deliver_final()`：ffmpeg `subtitles=...:force_style=...`，可选 BGM `amix`。
- **解释器自举** `deliver._ensure_jy()`：当前解释器缺 `pyJianYingDraft` 时 `os.execv(config.JY_PYTHON, ...)` 换解释器重跑自己。

---

## 4. `run.json` v1 草案（冻结稿，待 WP1 注入权威枚举）

> 原项目**没有 run.json**；唯一持久化状态是 `gen_segments` 的 `clips/<seg>.meta.json`（存 submit_id/task）。v1 草案设计为全局运行状态机，承接执行方案的 7 阶段 / 11 状态值 / 4 闸口。

```json
{
  "schema_version": "1",
  "run_id": "RUN-<timestamp>",
  "created_at": "<ISO8601>",
  "live": false,
  "max_submits": 0,
  "source_video": "<path>",
  "assets": {
    "product_images": [], "host_image": null,
    "cast": null, "facts": null, "qianchuan": null
  },
  "stages": {
    "reverse":   {"status": "pending", "seed": null, "k3": null},
    "merge":     {"status": "pending", "dossier": null},
    "plan":      {"status": "pending", "segments": null},
    "localize":  {"status": "pending"},
    "audio":     {"status": "pending", "cut": null, "tts": null, "vc": null},
    "generate":  {"status": "pending", "clips": {}},
    "deliver":   {"status": "pending", "draft": null, "final": null}
  },
  "providers": {
    "reverse": "ark", "judge": "ark",
    "i2v": "jimeng", "tts": "cosyvoice", "vc": "seedvc"
  },
  "cost_ledger": []
}
```

- `stages.*.status` 取值、`stages` 命名、`providers` 可选值、4 个闸口的触发条件——**全部以 `EXECUTION_PLAN.md` v2.2 为权威，WP1 冻结时回填，不在本文件臆造**。
- 状态文件位置：建议 `<workspace>/run.json`；密钥绝不进此文件（仅存 task id / submit id / cost 计数）。

---

## 5. Provider 能力矩阵（Mock / Live / experimental）

| Provider | 用途 | 凭证/配置 | 当前状态 | 缺口 |
|---|---|---|---|---|
| **Ark（火山方舟）** | 反推腿1、评委（默认 Seed）、生成(i2v/mm/t2v via `ark_gen`) | `ARK_API_KEY`；反推/评委模型 `ARK_SEED_MODEL`(默认 `doubao-seed-2-1-pro-260628`)；生成模型 **硬编码** `doubao-seedance-2-0-260128`(ark_gen.py:15) | **Live 可用** | 生成模型未走环境变量；无解码探针 |
| **Kimi（K3）** | 反推腿2 | `KIMI_API_KEY`/`MOONSHOT_API_KEY`；`KIMI_BASE_URL`/`KIMI_K3_MODEL` | **Live 可用**（3 次连接重试） | 仅连接抖动重试，HTTP 错误不重试 |
| **即梦（dreamina CLI）** | 生成 i2v/mm（jimeng 后端） | `~/.local/bin/dreamina` 已装+登录；`--model_version seedance2.0_vip` | **Live 可用**（最成熟：三层重试+解码探针+断点续跑+2s 闸处理） | 路径硬编码绕过 config；登录态缺 |
| **小云雀（pippit-tool-cli / `xyq_gen`）** | 生成 i2v/mm/t2v | `XYQ_ACCESS_KEY`；`XYQ_VIDEO_MODEL`(默认 `Seedance_2.0_mini_lite`) | **Live 可用，submit_mm 实验性未验证** | 输出解析脆弱；无解码探针；AUDIO_GUARD 仅 i2v/t2v |
| **CosyVoice（TTS）** | 配音 | `COSYVOICE_HOME`(默认 `~/CosyVoice`)；**外部 `tts-drama` skill** 路径硬编码 `~/.claude/skills/tts-drama/scripts/cosy_drama.py` | **Live 需环境** | 指向仓库外另一 skill；路径绕过 config |
| **Seed-VC（换声）** | 换声不换演 | `DAIHUO_SEEDVC_HOME`(默认 `~/seed-vc`)；内置音色 `voices/` **被 .gitignore 排除，新克隆缺失** | **Live 需环境** | 群戏说话人分离未实现；内置音色缺失 |
| **pyJianYingDraft（剪映）** | 草稿交付 | `DAIHUO_JY_PYTHON`(默认 `~/.venv-jianying/bin/python`)；`DAIHUO_JY_DRAFTS` | **Live 需 Windows/WSL 实机** | 强 WSL 路径假设；10.7 加密兼容随升级可能失效 |

> **Mock 策略**（WP0/WP1 离线开发用）：每个 Provider 实现统一最小接口（`submit()` / `wait_download()` / `status()`）；`live=false` 时返回确定性桩数据，媒体集成测试全绿后再切真后端。评委默认沿用原项目 Ark Seed，变更评委属显式设计变更。

---

## 6. fixtures 盘点（公开样例，可作 parity 基线）

`references/` 下（均随仓库公开，无密钥/私有素材）：
- `sample_shotlist.json`（19KB）— 反推结果样例（golden 输入候选）
- `sample_segments.json`（10KB）/ `sample_segments.md`（6.7KB）— 规划结果样例
- `sample_assets.json`（620B）— 资产骨架样例
- `xyq_notes.md` / `xyq_web_manual.txt` — 小云雀用法笔记（非代码）

> 缺口：原项目**无 tests/、无负例（negative-case）fixtures**。WP0 应补充：① 静音字幕残留视频（验证第 6 条硬规）；② 群戏多人视频（验证人数硬约束）；③ <2s 段音频（验证 2 秒闸）；④ 即梦坏流样本（验证解码探针）。

---

## 7. 许可证与可复用来源

- **许可证**：MIT · Copyright (c) 2026 wangcanyu。新项目须 **保留原 MIT 声明 + 叠加新版权**（如 `Copyright (c) 2026 <you>`），不得删除原作者归属。
- **仓库内原创**：21 个 `.py` + 文档。
- **外部依赖（需保留署名/遵守各自许可）**：
  - **Seed-VC**、**CosyVoice**：换声/TTS 引擎（本机 venv，非仓库内）。
  - **pyJianYingDraft**：剪映草稿生成（独立 pip 包，轻量纯 py）。
  - **即梦 `dreamina` CLI**、**小云雀 `pippit-tool-cli`**：第三方 CLI 工具。
  - **外部 `tts-drama` skill**（路径 `~/.claude/skills/tts-drama/`）：CosyVoice 调用封装，**不在本仓库、需另行授权/获取**。
- **不得进入新仓库**：真实密钥、私有音色、私有千川弹药包（`qianchuan/`）、未授权素材。

---

## 8. 可逐项勾选的 parity 基线（WP1 冻结前验收）

- [ ] 双反推同源切点（ffmpeg `detect_cuts`，seed/k3 共用 bounds）
- [ ] 静音字幕残留只进 `onscreen_text`，不进 `dialogue`/`full_transcript`（第 6 条硬规）
- [ ] 群戏人数硬约束句存在于每个群戏段 prompt（"自始至终只有 N 个角色"）
- [ ] 2 秒音频闸：<2s 段音频可提交即梦 mm 不报错
- [ ] 时长：段时长 `max(4,min(15,ceil(end-start)))`；mm 段配音超长自适应上调（仅 mm）
- [ ] 拼接：720×1280 归一化 + setsar=1；配音以视频时长为准；缺片不崩仅告警
- [ ] 字幕：优先 `timing.json` 精确轴，缺失退化为字数占比
- [ ] 剪映草稿五轨 + 素材自包含 + 贴字参考轨
- [ ] 评委双视频真对比（成片 vs 原片）
- [ ] 生成三层重试 + 解码探针 + 断点续跑（submit_id 持久化）
- [ ] 密钥仅来自环境变量 / `~/.config/dy-fanpai/`，不进日志/仓库/fixtures
- [ ] Provider 最小接口统一（submit/wait_download/status），`live=false` 可离线跑通

---

## 9. 重构必须裁决的冲突点（WP1 冻结门输入）

1. **config 双重标准**：`config.py` 有完整环境变量优先级，但 `gen_segments.py:19`(`DREAMINA`)、`tts_segments.py:20`(`COSY_DRAMA`)**硬编码绕过 config**——新项目须全部收归 config。
2. **2 秒闸语义冲突**：注释"只垫 2s 下限" vs 代码 `pad=max(2.0,span)` 垫满——二选一明确。
3. **时长双标**：`split_long_shots` 触发 15 vs 计算 12——统一语义。
4. **detect_cuts 默认 0.3 vs 实际 0.15**——统一到 0.15。
5. **Ark 生成模型硬编码** `doubao-seedance-2-0-260128` 未走 `ARK_SEED_MODEL` 环境变量——收归配置。
6. **vc_segments 内置音色** `voices/` 被 gitignore 排除，新克隆缺失——明确音色 sourcing 策略（合法音色由 U5 提供）。
7. **needed_assets 只用默认 FORM_MAP**，换品类无法读用户 forms——重构为读 `merged_form_map`。
8. **patch_cast 原地覆写 segments.json 无备份**——改为写新文件或先备份。
9. **无全局重试/断点** 于 seed_reverse/localize/judge 主打分/assemble/deliver——按 gen_segments 范式补齐或显式声明"不重试"。
10. **强 WSL 假设**（deliver 路径转换）——新项目需支持 macOS 本机或明确 Windows 实机（U3）。
