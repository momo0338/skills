---
name: dy-fanpai
description: 抖音带货视频翻拍——用用户的产品/素材复刻参考视频，产出中性母版、字幕成品或剪映草稿。识别「抖音翻拍、带货视频复刻、用我的产品重做、把这条视频改成我的货」等请求。
version: 0.1.0
type: workflow
---

# dy-fanpai · 抖音翻拍 Agent Skill

本 Skill 只调用 CLI（`dy-fanpai`），不复制 Python 业务逻辑。仓库即 Skill 源；
安装路径以目标 Agent 宿主的官方机制与现场探测为准，不硬编码 WorkBuddy / Codex / Claude Code 目录。

## 触发

- 用户要「翻拍/复刻/二创」一条抖音带货视频
- 用户要用自己的产品替换原视频里的商品
- 用户要产出剪映可精剪草稿、带字幕成品或中性母版

## 标准流程

1. 收集参考视频与产品素材（图、人物锚图、事实、授权）。
2. `dy-fanpai doctor` 体检环境与密钥。
3. `dy-fanpai new --video <ref> --workspace runs/<id>` 建工作区。
4. `dy-fanpai run` 逐阶段推进；在四个闸口暂停等待人工批准。
5. `dy-fanpai deliver --mode final|jianying|both` 交付。

## 必须遵守（执行方案 §2 / §8）

- **四个闸口必须暂停**：G1 权利隐私、G2 计划审核、G3 费用审批、G4 最终人工 QC。
  `run` 遇未批准闸口立即停止，不得用 `--force` 绕过。
- **不自动安装重型依赖**（CosyVoice / Seed-VC / pyJianYingDraft）。
- **不自动使用真实密钥做测试**；Live 默认关闭。
- **不自动扩大生成段数或费用上限**；一次只批一个 Provider、一段、一次提交。
- **恢复已有任务时先按 task ID 查询**，不重复提交扣费。
- 人物口播走即梦；纯产品 i2v 才允许 Ark / 小云雀。
- `FULL.mp4` 始终保持无字幕、无 BGM。

## 外部资源缺失时

缺合法素材/音色/剪映实机/私有千川包时，对应功能标记「实现完成，外部验收未完成」，
不得宣称全部完成。
