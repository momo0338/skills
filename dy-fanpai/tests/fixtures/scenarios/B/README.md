# 场景：B（B 类）

无 hero 图，纯运镜 + 口播，依赖运镜时序候选（__alt_*）。

## 所需 fixture 输入
- `shotlist.json`：镜头清单 / 台词 / 角色（见 `tests/fixtures/original/` 现有样例结构）。
- `assets.json`：素材清单（图 / 音频 / 商品锚）。
- `original.mp4`（受控 Live 提供，不入库）：原片。
- `segments.golden.json`（可选）：确定性 golden。

## 验收重点（门3 + 关联门）
- 规划：merge.build_merged 的 __alt_* 运镜候选生效。
- 生成：i2v 默认带 AUDIO_GUARD（小云雀）或即梦。
- 交付：无 hero 图分支不崩溃，字幕/口播同步。
