# 场景：群戏

多人物群戏，需人物一致性与口型一致性人工审核（门9）。

## 所需 fixture 输入
- `shotlist.json`：镜头清单 / 台词 / 角色（见 `tests/fixtures/original/` 现有样例结构）。
- `assets.json`：素材清单（图 / 音频 / 商品锚）。
- `original.mp4`（受控 Live 提供，不入库）：原片。
- `segments.golden.json`（可选）：确定性 golden。

## 验收重点（门3 + 关联门）
- 规划：seg_role 多角色分配。
- 生成：多人物段口型覆盖（mouth_evidence）。
- 交付/审核：人物一致性、口型同步需人工审核（门9 🟡）。
