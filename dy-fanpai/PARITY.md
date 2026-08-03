# PARITY · 确定性产物比对现状（验收门 4）

执行方案 §13 门4：确定性产物与原项目**无未解释差异**。

本文件汇总当前确定性比对覆盖，并列出待补的统一 parity fixture。

## 已实现的比对

| 工作包 | 模块 | 比对方式 | 覆盖程度 |
|---|---|---|---|
| WP2 | `planning/planner.py` | `tests/parity/test_planner_parity.py`（9 例） | ✅ 对 `tests/fixtures/original/A__planning.golden.json` **逐字节相等** + 结构化断言 |
| WP2 | `reverse/merge.py` | `tests/unit/test_merge.py` | ✅ 静音闸 / 性别信号 / 抽帧点离线断言（镜像原 `merge_reverse` 逻辑） |
| WP3 | `audio/service.py` `media/ffmpeg.py` | `tests/parity/test_media_parity.py`（8 例）+ args 级单测 | ✅ 对 `tests/parity/fixtures/wp3_ffmpeg_args.golden.json` / `wp3_timing.golden.json` **逐字段相等** + 业务铁律断言（2s 闸、720x1280、单声道 24k、apad 只垫下限） |
| WP3 | `audio/voice.py` | 16 例单测 | ✅ `apply_pron_fix` 参→身 + CAN_WORDS 保护、`parse_speakers` 标签切分、`resolve_target` 解析 |
| WP4 | `generation/dreamina.py` `ark.py` `xyq.py` + `media/download.py` | `tests/parity/test_generation_parity.py`（15 例）+ 请求体单测 | ✅ 对 `tests/parity/fixtures/wp4_dreamina/ark/xyq/download.golden.json` **逐字段相等** + 路由/铁律断言（mm 带音频、AUDIO_GUARD、NO_PROXY、时长上调封顶 15s） |
| WP5 | `delivery/final.py` | 10 例单测 | ✅ `fmt_ts`/`sentences`/`build_srt_entries` 时钟与权重 1:1（复刻 `export_subs.py`） |
| WP5 | `delivery/jianying.py` | 7 例单测 | ✅ 5 轨规格 1:1（视频/原声/字幕/贴纸/BGM） |
| WP5 | `quality/qc.py` `judge.py` | 12 例单测 | ✅ 探活/解码/分辨率/时长比判定 1:1 |
| 六类场景 | `planning/planner.py` | `tests/parity/test_scenarios_parity.py`（24 例） | ✅ 六类场景（A/产品迁移/B/群戏/旁白/纯产品）`shotlist+assets` 合成输入 → `segments.golden.json` **逐字段相等** + 路由特征断言（旁白/纯产品=全 i2v、口播类含 mm 等） |

## 关键 parity 发现（非新冻结，仅记录）
- `planner` 每段 `shots` 为镜引用列表（字符串/整数混合，如 `['1a']`/`['1b',2]`），非 dict。
- i2v 段不含 `images`/`anchor_labels`；mm 段含且锚标数 ≤ 图数。
- 段 `duration` 是目标生成时长，不要求等于 `end-start`（实际镜跨度）。
- `references/sample_segments.json`（原项目）是**旧版** `plan_segments` 产物，与当前源码不一致；
  parity 基准只用当前算法 golden，不依赖原 `references/`。
- `build_timing` 使用**原始（未拆分）shotlist**：跨段长镜的台词不落入任何段的 timing
  （如 A 场景 S1 的 timing 为空），此为当前算法真实行为，已被 golden 固化。

## 统一 golden 已补齐（2026-08-03）
原「待补」三项已全部完成，作为受控 Live 前的确定性回归护栏：
1. `tests/parity/fixtures/wp3_ffmpeg_args.golden.json` / `wp3_timing.golden.json`：
   装配 args 与切段 timing 的当前算法 golden。
2. `tests/parity/fixtures/wp4_dreamina.golden.json` / `wp4_ark.golden.json` /
   `wp4_xyq.golden.json` / `wp4_download.golden.json`：三后端提交命令/请求体、
   轮询输出解析、下载代理策略的当前算法 golden。
3. 六类场景（A/产品迁移/B/群戏/旁白/纯产品）均建 `shotlist.json` + `assets.json`
   合成输入与 `segments.golden.json`，纳入 `test_scenarios_parity.py` 基线。

> 以上为「当前算法 golden」回归护栏：任何后续改动若改变确定性输出，parity 测试即失败，
> 需人工审查 diff。受控 Live 仍待真实账号/预算（见 `ACCEPTANCE.md` 门 4 状态）。
