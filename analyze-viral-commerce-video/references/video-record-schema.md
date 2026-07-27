# 批量视频独立记录

批量比较前，为每条视频建立一条独立记录。没有证据的字段使用 `unknown`，不要从聚合结论反推。

## 身份与快照

| 字段 | 要求 |
|---|---|
| platform | 平台 |
| video_id | 作品 ID |
| canonical_url | 规范链接 |
| observed_at | 指标和榜单观察时间 |
| board_name | 榜单名称 |
| board_rank | 排名或 `unknown` |
| author_type | merchant / creator / unknown |
| author | 作者 |
| product | 商品 |
| price | 价格与时间口径 |
| ad_status | 广告/投流状态或 `unknown` |

## 指标

分别记录播放、3秒完播、完播、商品点击、点击率、点击转化、GMV、点赞、评论、分享和收藏。每个指标至少包含：

```json
{
  "value": null,
  "unit": null,
  "observed_at": null,
  "source": "platform_reported",
  "status": "unknown"
}
```

不要把点赞替代播放、点击、成交或 GMV。

## 证据覆盖

```json
{
  "video": "complete|partial|unavailable|unchecked",
  "audio": "complete_listen|sampled_listen|stream_only|unavailable|unchecked",
  "text": "manual_all|ocr_all_reviewed|ocr_sampled|asr_reviewed|unchecked",
  "platform_breakdown": "complete|partial|unavailable|unchecked",
  "metrics": "complete|partial|unavailable"
}
```

## 创意标签

至少记录：

- 时长；
- 钩子；
- 商品首次出现时间；
- 第一利益点出现时间；
- 证明方式；
- 信任来源；
- 转化装置；
- 场景、主要机位和人物；
- 商家/达人依赖；
- 合规风险；
- 可迁移机制。

## 汇总硬门

- 先完成独立记录，再聚类和计数。
- 每个“有 N 条”结论能追溯到具体作品 ID 或记录编号。
- 保留反例和缺失样本。
- 历史快照不冒充当前榜单。
- 缺作品 ID 或作品级指标的旧基线只能用于定性校准，不能用于精确统计。
