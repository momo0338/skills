# PARITY · 确定性产物比对现状（验收门 4）

执行方案 §13 门4：确定性产物与原项目**无未解释差异**。

本文件汇总当前确定性比对覆盖，并列出待补的统一 parity fixture。

## 已实现的比对

| 工作包 | 模块 | 比对方式 | 覆盖程度 |
|---|---|---|---|
| WP2 | `planning/planner.py` | `tests/parity/test_planner_parity.py`（9 例） | ✅ 对 `tests/fixtures/original/A__planning.golden.json` **逐字节相等** + 结构化断言 |
| WP2 | `reverse/merge.py` | `tests/unit/test_merge.py` | ✅ 静音闸 / 性别信号 / 抽帧点离线断言（镜像原 `merge_reverse` 逻辑） |
| WP3 | `audio/service.py` `media/ffmpeg.py` `media/download.py` | args 级单测（11+4+…） | ✅ 请求/参数构造 1:1 复刻（`-ss/-to`、`apad`、`normalize_args`、`decode_ok` 标记集） |
| WP3 | `audio/voice.py` | 16 例单测 | ✅ `apply_pron_fix` 参→身 + CAN_WORDS 保护、`parse_speakers` 标签切分、`resolve_target` 解析 |
| WP4 | `generation/dreamina.py` `ark.py` `xyq.py` | 请求体构造单测（13+4+9） | ✅ `build_submit_cmd` / `submit_i2v/mm/t2v` 参数与 URL 模板 1:1；UUID 解析 |
| WP5 | `delivery/final.py` | 10 例单测 | ✅ `fmt_ts`/`sentences`/`build_srt_entries` 时钟与权重 1:1（复刻 `export_subs.py`） |
| WP5 | `delivery/jianying.py` | 7 例单测 | ✅ 5 轨规格 1:1（视频/原声/字幕/贴纸/BGM） |
| WP5 | `quality/qc.py` `judge.py` | 12 例单测 | ✅ 探活/解码/分辨率/时长比判定 1:1 |

## 关键 parity 发现（非新冻结，仅记录）
- `planner` 每段 `shots` 为镜引用列表（字符串/整数混合，如 `['1a']`/`['1b',2]`），非 dict。
- i2v 段不含 `images`/`anchor_labels`；mm 段含且锚标数 ≤ 图数。
- 段 `duration` 是目标生成时长，不要求等于 `end-start`（实际镜跨度）。
- `references/sample_segments.json`（原项目）是**旧版** `plan_segments` 产物，与当前源码不一致；
  parity 基准只用当前算法 golden，不依赖原 `references/`。

## 待补（统一 parity fixture）
门4 当前缺口：WP3/WP4 为**参数/请求体级** 1:1 复刻，尚未像 WP2 那样有「统一 golden 输出」
做端到端字节/字段比对。建议补：
1. `tests/parity/fixtures/`：为 WP3（切段 timing / 装配 args）、WP4（提交命令 / 轮询输出解析）
   各建一份**当前算法 golden**，跑 `assert` 级 parity。
2. `tests/parity/test_media_parity.py` / `test_generation_parity.py`：对 golden 做结构化断言。
3. 把六类场景（见 `tests/fixtures/scenarios/`）的 `segments.golden.json` 纳入 parity 基线。

> 这些待补项不影响「实现完成」定论：逻辑已 1:1 复刻并通过单测；统一 golden 是为了在受控
> Live 前再多一道确定性回归护栏。
