# ijob 公共只读契约

## 通用响应

```json
{
  "schema_version": "1.0.0",
  "contract": "ijob.public",
  "operation": "status",
  "generated_at": "2026-09-25T20:00:00+08:00",
  "data": {},
  "meta": {
    "read_only": true,
    "source": "ijob",
    "campaign_semantics_version": 3
  },
  "warnings": []
}
```

失败时保留同一外壳，`data=null`，追加 `error`：

```json
{
  "code": "campaign_not_found",
  "message": "未找到招聘批次: 999",
  "retryable": false,
  "details": {"campaign_id": 999}
}
```

退出码：0 成功；2 请求或契约错误；3 业务对象不存在；4 未知内部错误；5 技能执行超时。

## 版本兼容

- 契约采用**同 major 兼容**：`schema_version` 为 `1.x` 且 `>=1.0.0` 均可接受，不精确钉死某一个 patch。
- 跨 major（如 `2.0.0`）必须显式升级技能后才可使用。
- `meta.campaign_semantics_version` 固定为 `3`，表示招聘业务语义配置正本
  （截止日哨兵、导航占位判据、紧急窗口）的 schema 版本。
- 技能侧自身错误使用 `ijob.skill` 外壳，`meta.source` 为 `ijob.skill`，
  同样带 `read_only=true` 与 `campaign_semantics_version`。

## 错误码

| code | 含义 | retryable |
|---|---|---|
| `invalid_request` | 参数或用法不合法 | false |
| `campaign_not_found` | 按 id 或关键词未找到批次 | false |
| `query_ambiguous` | 关键词命中超过 100 个批次 | false |
| `semantics_incompatible` | 语义配置缺失/损坏/版本不兼容 | false |
| `contract_incompatible` | 契约跨 major 或低于技能下限 | false |
| `contract_invalid` / `contract_schema_invalid` | 契约文件与实现不一致 | false |
| `database_locked` | 主库被其他进程占用 | **true** |
| `database_corrupt` | 主库文件真实损坏 | false |
| `database_unreadable` | 其他只读打开失败 | false |
| `cycle_config_missing` / `cycle_config_invalid` | 当前届别配置问题 | false |
| `internal_error` | 未归类的内部失败 | false |

`database_locked` 允许重试；`database_corrupt` 不允许，两者不可混用。

## 操作语义

只读操作共 **9 个**：`discover`、`health`、`status`、`backlog`、`inbox`、
`next`、`brief`、`info`、`cycle-status`。

### discover

验证契约与 schema 文件，返回契约版本、只读能力列表、主库存在性。不需要主库可读。
会自检 `public_contract.schema.json` 确实是描述本外壳的对象 schema，伪 schema 被拒绝。

### health

返回 `ok`、SQLite `quick_check`、必要表是否存在、当前届别、库体积。若必要表缺失或 quick_check 失败，仍返回成功外壳并在 `warnings` 报告；`data.ok=false`。

### status

返回 `data.counts`，字段均使用稳定英文键。数字是动态值，不在文档中写死。

### backlog

- 定义：有至少一个启用巡检源，且不存在被识别为当前届校招批次的公司。
- 语义：信息覆盖待核队列，不等于写稿队列。
- 分页：`limit` 1–500，`offset>=0`；排序带唯一 tiebreaker，分页稳定。

### inbox

只返回状态为“待分拣”的线索，支持分页。字段 `tier/found_channel/announcement_url` 描述发现渠道，不等于已核实。

### next

返回未过期在招批次，按真实截止日升序，历史哨兵日置后。`urgency` 可能为 `critical/urgent/normal/unverified`；`content_state` 只表示库内内容状态。

### brief

- 返回所有未标为已截止的批次业务对象，供内容技能组装投料单与草稿箱对账。
- 支持 `limit` / `offset` 分页，**`limit` 上限 100**（`data.limit_max=100`）。
- 包含 `content_state` 与受限的 `article_search_text`，**每条最多 20000 字符**（`data.article_search_text_limit=20000`），仅用于把本地草稿标题映射到批次，不等于官方证据。
- 不返回数据库路径、表名或原始 SQLite schema。

### info

`--campaign-id` 精确返回一条；`--query` 只收**一个**完整关键词，不按整串拆词，OR 匹配单位简称、全称和批次标题。关键词命中多条时返回 `items`，不会自动挑一个。命中超过 100 条返回 `query_ambiguous`。

纯数字关键词（如 `2027`）仍然按关键词处理，**不会**被静默改义成 `campaign_id`；要按 id 查必须用 `--campaign-id`。

### cycle-status

- `stored_distribution`：数据库当前保存的巡检源状态。
- `derived_distribution`：从当前届批次反推的状态。
- `drift_count`：两者不同的启用源数量。
- `sync_performed=false`：保证没有回写。

## 兼容规则

1. 同一 major 版本只允许新增可选字段。
2. 删除字段、改变字段类型或改变业务含义必须提升 major。
3. 技能接受 1.x 且不低于 1.0.0；2.x 必须显式升级技能。
4. 旧 ijob CLI、中文输出和 SQLite schema 均不属于公共契约。

## 当前未开放

- `promote` / `ignore`
- `sync-cycle` / `cycle-advance`
- `probe` / `daily`
- `reconcile-articles`
- 工商画像写回

以上操作需等 ijob 侧提供带备份、确认、SHA-256 和写后完整性检查的正式写契约。
本技能**不执行任何写操作**，不得对外宣称写操作已开放。
