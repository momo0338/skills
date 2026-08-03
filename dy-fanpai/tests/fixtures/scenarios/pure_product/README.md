# 场景：纯产品

无人物，纯商品特写，纯 i2v/产品运镜。

## 所需 fixture 输入
- `shotlist.json`：镜头清单 / 台词 / 角色（见 `tests/fixtures/original/` 现有样例结构）。
- `assets.json`：素材清单（图 / 音频 / 商品锚）。
- `original.mp4`（受控 Live 提供，不入库）：原片。
- `segments.golden.json`（可选）：确定性 golden。

## 验收重点（门3 + 关联门）
- 规划：无人物角色，纯产品镜头。
- 生成：纯 i2v 产品运镜，无口型约束。
- 交付：FULL 干净，FINAL 叠加 BGM/字幕（若有）。
