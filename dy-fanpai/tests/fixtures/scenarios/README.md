# 六类场景 Fixture 与验收记录（验收门 3）

执行方案 §13 门3 要求：六类合法测试视频**都有 fixture 和验收记录**。
六类定义见执行方案 §0.4/§13 上下文：**A、产品迁移、B、群戏、旁白、纯产品**。

本目录为每类准备了 fixture 输入说明 + `acceptance_record.md` 模板（占位，待受控 Live 填写）。
fixture 结构已就绪；**验收记录需在真实账号/预算/特定机器上跑受控 Live 后回填**，
属外部验收项，不影响「实现完成」定论。

## 目录
| 场景 | 目录 | 典型特征 |
|---|---|---|
| A（标准 A 类） | `A/` | hero 图 + 口播，最典型带货翻拍 |
| 产品迁移 | `product_migration/` | 商品锚定图替换/换品 |
| B（B 类） | `B/` | 无 hero 图，纯运镜 + 口播 |
| 群戏 | `group/` | 多人物，需人物/口型一致性审核 |
| 旁白 | `narration/` | 无说话人标签，整段旁白 |
| 纯产品 | `pure_product/` | 无人物，纯商品特写 |

## 每类 fixture 的最小输入约定
- `shotlist.json`：规划输入（镜头清单 / 台词 / 角色）。
- `assets.json`：素材清单（图 / 音频 / 商品锚）。
- `original.mp4`（可选）：原片，用于反推/切段/质检比对（受控 Live 提供，不入库大文件）。
- `segments.golden.json`：若该类有确定性 golden，放此处做 parity。

## 回填验收记录的步骤
1. 在干净工作区 `dy-fanpai new <scenario>` → `run` 分阶段执行（按闸口审批）。
2. 跑完后在对应 `acceptance_record.md` 填：日期、run id、四闸口审批人、产出物清单、
   技术 QC（qc_report/judge_summary）结论、人工审核（门9）结论、追溯字段（门10）。
3. 判定 ✅/🟡，提交进仓库作为该类验收证据。
