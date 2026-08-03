# 场景：产品迁移

换品/商品迁移场景：商品锚定图替换，保持原镜头节奏。

## 所需 fixture 输入
- `shotlist.json`：镜头清单 / 台词 / 角色（见 `tests/fixtures/original/` 现有样例结构）。
- `assets.json`：素材清单（图 / 音频 / 商品锚）。
- `original.mp4`（受控 Live 提供，不入库）：原片。
- `segments.golden.json`（可选）：确定性 golden。

## 验收重点（门3 + 关联门）
- 规划：pick_product_anchors 商品锚替换验证。
- 生成：锚图随段传入（mm 走 multimodal2video 带图）。
- 交付：商品图在 FINAL/剪映草稿可见且未串味。
