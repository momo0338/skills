# 场景：A（标准 A 类）

最典型的带货翻拍：hero 图 + 口播，单人物主播出镜。

## 所需 fixture 输入
- `shotlist.json`：镜头清单 / 台词 / 角色（见 `tests/fixtures/original/` 现有样例结构）。
- `assets.json`：素材清单（图 / 音频 / 商品锚）。
- `original.mp4`（受控 Live 提供，不入库）：原片。
- `segments.golden.json`（可选）：确定性 golden。

## 验收重点（门3 + 关联门）
- 规划：hero 图锚定 + 口播段台词同步（localization.apply_edits_dict）。
- 生成：i2v/mm 路由到即梦；口型覆盖配音时长（mouth_evidence 容差0.05）。
- 交付：FULL 无字幕/BGM，FINAL 叠加；SRT + 剪映草稿。
