# 场景：旁白

无说话人标签，整段旁白，apply_pron_fix 控制符保护需校验。

## 所需 fixture 输入
- `shotlist.json`：镜头清单 / 台词 / 角色（见 `tests/fixtures/original/` 现有样例结构）。
- `assets.json`：素材清单（图 / 音频 / 商品锚）。
- `original.mp4`（受控 Live 提供，不入库）：原片。
- `segments.golden.json`（可选）：确定性 golden。

## 验收重点（门3 + 关联门）
- 规划：口播段无 A：/B： 标签，整段旁白。
- 音频：apply_pron_fix 参→身 + CAN_WORDS 保护不误伤旁白。
- 交付：SRT/字幕整段呈现正确。
