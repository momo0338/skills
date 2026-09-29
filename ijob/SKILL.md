---
name: ijob
version: 0.1.0
description: ijob 独立招聘数据中枢的稳定只读访问层。用于查询全局盘点、待补当前届批次、待分拣线索、内容生产队列、单批次硬信息与届别状态漂移；触发词包括 ijob、招聘中台、待补批次、待分拣线索、今天写谁、招聘主数据、届别状态。需要采集工商画像、巡检、线索转正或回写数据库时，本技能只负责入口发现和风险提示，不自动执行写操作。
license: Proprietary
metadata:
  agent_created: true
---

# ijob 招聘数据访问技能

## 定位

把 `ijob` 当作独立项目，通过版本化 JSON 契约消费数据。禁止在调用方直接打开 ijob 数据库、拼接 SQLite SQL、解析旧 CLI 中文输出，或依赖 ijob 的绝对安装路径。

只读侧开放 9 个操作。**写操作已于 2026-09-25 通过受控网关开放**（`write --write-op ...`），
仅限「线索分拣 / 巡检运行 / 稿件回传 / 届别同步」四类业务场景，白名单外一律拒绝。
其余一次性迁移、建库、高危治理类写脚本仍不开放，必须回 ijob 项目内按其交接规则执行。
不得对外宣称「所有写操作都已开放」。

## 标准入口

统一运行：

```bash
python3 <本技能目录>/scripts/ijob.py <operation> [options]
```

需要固定运行时时，优先使用用户配置的 `IJOB_PYTHON`；未配置则使用当前 `python3`。

首次接入或路径迁移后先执行：

```bash
python3 <本技能目录>/scripts/ijob.py health
```

## 运行时发现顺序

`scripts/ijob.py` 按以下顺序定位 ijob：

1. 命令参数 `--ijob-home`；
2. 环境变量 `IJOB_HOME`；
3. 用户配置 `~/.config/ijob/config.json` 的 `ijob_home`；
4. 常见安装目录发现。

候选目录必须同时具备：

- `api/contract.py`
- `api/public_contract.json`
- `api/public_contract.schema.json`

**显式 `--ijob-home` 或 `IJOB_HOME` 是硬约束**：一旦给出，校验不通过就返回
`ijob_home_invalid` 错误并停止，**禁止静默回退**到其他候选路径。定位失败必须返回结构化错误并提示设置 `IJOB_HOME`。

## 只读操作

共 9 个：

| 操作 | 用途 | 关键参数 |
|---|---|---|
| `discover` | 返回契约版本、能力和主库存在性 | 无 |
| `health` | 只读健康检查、必要表、当前届别 | `--cycle-config`（仅诊断） |
| `status` | 全局动态盘点 | 无 |
| `backlog` | 当前届信息覆盖待核公司 | `--limit` `--offset` |
| `inbox` | 待分拣线索，支持分页 | `--limit` `--offset` |
| `next` | 内容生产队列 | `--recruit-type 校招` `--include-written` `--limit` `--offset` |
| `brief` | 写稿投料单与草稿箱对账所需业务对象；分页返回 | `--limit`（上限 100） `--offset` |
| `info` | 单批次或关键词查询 | `--campaign-id 3` 或 `--query 国网江苏` |
| `cycle-status` | 对比已存状态和批次反推状态 | `--limit` |

载荷上限：`brief` 的 `limit` 最大 100，`article_search_text` 每条最多 20000 字符。

完整参数与返回结构见 `references/contract.md`。

## 响应外壳

- 顶层 `schema_version` 采用**同 major 兼容**：接受 `1.x` 且 `>=1.0.0`，不精确钉死某个版本；跨 major 必须先升级技能。
- `meta.campaign_semantics_version=3` 表示招聘业务语义正本版本。
- 技能自身错误使用 `ijob.skill` 外壳（`meta.source="ijob.skill"`），同样带 `read_only=true` 与 `generated_at`。
- argparse 参数错误也输出 JSON 错误外壳，不向 stderr 吐 usage。

## 调用纪律

1. 先检查 JSON 顶层 `schema_version` 与 `contract`；不兼容就停止，不猜字段。
2. `error` 存在时先按 `code` 处理：`database_locked` 可稍后重试，`campaign_not_found` 不得当作空数据，`semantics_incompatible` 必须停止并报出语义版本。
3. `cycle-status` 永远是只读；`drift_count > 0` 只报告，不触发同步。
4. `backlog` 表示“信息覆盖待核公司”，不是“851 篇待写稿”。真正写稿队列看 `next`。
5. `info --query` 只收一个完整关键词，不拆词；纯数字（如 `2027`）仍按关键词，不会被当成 `campaign_id`。
6. `content_state=written` 只证明库内存在成稿，不证明已推微信草稿箱或已经发布。
7. 不把 `data` 原样当核实结论；人数、截止日、岗位和条件仍须按官方公告或网申系统核验。
8. 不把数据库文件路径、SQLite 表名或内部巡检文件路径写入用户交付物；需要解释口径时只描述业务定义。

## 日常用法（实测可用）

先设个别名，少打长路径：

```bash
export IJOB=~/.workbuddy/skills/ijob/scripts/ijob.py
```

### 早上开工：先看全局，再看最大的活

```bash
python3 $IJOB status            # 全局盘点（数字随时间变，别用文档里的旧值）
python3 $IJOB backlog --limit 30   # 851 家待补当前届批次的公司 = 当前最大 backlog
```

`status` 常用口径（2026-09-25 实测，务必以当次输出为准）：

| 字段 | 含义 |
|---|---|
| `active_unwritten` | 在招且未成稿 = **写稿队列真实规模** |
| `urgent_unwritten` | 7 天内截止且未成稿 = **今天该干的** |
| `unverified_deadline_unwritten` | 截止日未核实的未成稿（动笔前须回官方钉死） |
| `written_campaigns` | 库内已成稿数（≠ 已推草稿箱 ≠ 线上已发布） |
| `pending_inbox` | 待分拣线索 |
| `enabled_sources_alerting` | 巡检源告警数（源坏了但报告显示无新增，最危险） |

### 选活与出稿

```bash
python3 $IJOB next --limit 10                 # 今天写谁（含 days_remaining / urgency）
python3 $IJOB info --query "中信银行南京分行"    # 查某批次底细
python3 $IJOB next --recruit-type 社招          # 只看社招
python3 $IJOB next --include-written            # 连已写过的也列出来
```

### 写稿：出投料单（走 job-write，自动消费 brief 契约）

```bash
python3 ~/.workbuddy/skills/job-write/scripts/emit_briefing.py "中信银行南京分行"
python3 ~/.workbuddy/skills/job-write/scripts/emit_briefing.py "中信银行南京分行" --gap-only  # 只看缺口
python3 ~/.workbuddy/skills/job-write/scripts/emit_briefing.py --ready                        # 全库：必填齐且未动笔的单位
```

投料单会标出每条硬信息的**可信度**与**缺口清单**；`--ready` 还会自动对账微信草稿箱，输出「疑似已在草稿箱」。

### 届别与线索

```bash
python3 $IJOB cycle-status        # 三态分布 + drift_count（只读，永不触发同步）
python3 $IJOB inbox --limit 20    # 待分拣线索（promote/ignore 是写操作，回 ijob 项目做）
```

### 输出是 JSON：两种看法

```bash
python3 $IJOB status --pretty          # 美化缩进，仍是 JSON
python3 $IJOB status | python3 -c "import json,sys; d=json.load(sys.stdin)['data']['counts']; [print(f'{k:34} {v}') for k,v in d.items()]"
```

⚠️ **登录态失效时 `--ready` 只降级告警、名单不可采信**——草稿箱对账依赖微信登录态。

### 写操作不在这里

`promote` / `ignore` / `sync-cycle` / `probe` / `daily` / `reconcile-articles` 均**未开放**。
其中稿件对账回填的真实入口是：

```bash
python3 /Users/zhugx/src/ijob/scripts/reconcile_articles.py           # 默认 dry-run，只读
python3 /Users/zhugx/src/ijob/scripts/reconcile_articles.py --apply   # 写库（备份+SHA-256+单事务+写后终验）
```

旧入口 `job-write/scripts/sync_articles_to_db.py` 已是留痕薄壳，执行即退出码 2 并打印新位置。

### 写操作：`write` 子命令（2026-09-25 新增）

写操作**已包含进来**，但走受控网关：白名单 + 强制备份 + SHA-256 校验。
按**业务场景**开放，不按脚本数量：

| 场景 | 写操作 | 用途 |
|---|---|---|
| **线索分拣** | `promote` / `ignore` | 巡检线索转正入库 / 标记忽略 |
| **巡检运行** | `probe` / `daily` | 巡检源探活 / 每日巡检 |
| **稿件回传** | `reconcile-articles` | 本地成稿回写主档 |
| 届别同步 | `sync-cycle` | 回写巡检源调度状态 |

```bash
# 预演（默认，不写库也不备份）
python3 $IJOB write --write-op reconcile-articles

# 真写（自动备份到 /tmp/ijob-writegate-*.db 并打印 SHA-256 与回滚命令）
python3 $IJOB write --write-op reconcile-articles --apply

# 带参数（--write-arg 可重复）
python3 $IJOB write --write-op promote \
  --write-arg 2879 --write-arg 2026-12-31 \
  --write-arg --apply-url --write-arg https://example.com/x \
  --apply

# 看有哪些可写、哪些被拒及原因
python3 /Users/zhugx/src/ijob/api/writegate.py list
```

**门禁保证**：

1. 白名单外一律拒绝，**不做临时放行**；被拒操作会说明原因（如「会 DELETE companies，最高危」）。
2. 每次写库前强制备份并逐字节校验 SHA-256，不一致即拒绝执行。
3. 不加 `--apply` 就是 dry-run：不备份、不写库。
4. 子脚本非零退出即视为整体失败，回滚以备份为准（返回 `rollback_hint`）。
5. 只读操作携带 `--apply` / `--write-op` 会**直接报错**，不静默忽略。

**不开放的写操作**（一次性迁移/建库/高危治理类，共 12 项）：
`link-merge-entities`、`dedup-duplicates`、`migrate-schema`、`migrate-ids`、
`import-central-enterprises`、`setup-org-hierarchy`、`normalize-tags`、
`remediate-nature-tags`、`sync-recruit-url`、`enrich-company-tags`、
`cycle-advance`、`process-inbox-bulk`

## 迁移状态

本版已完成 ijob 侧 `ijob.public` 1.x 只读契约（当前实现版本 1.0.0，业务语义 schema 3），
并已由用户级 `ijob` 技能承接运行时发现、契约校验与只读调用。`job-write` 的投料单与草稿箱对账
已切换为消费 `brief` 契约，不再直连数据库。写操作经 `ijob.write` 网关按业务场景开放
（线索分拣 / 巡检 / 稿件回传 / 届别同步），白名单外 12 项仍须回 ijob 项目执行。

## 自检

执行：

```bash
python3 <本技能目录>/scripts/self_test.py
```

测试只使用临时数据库与临时配置，不读写真实 ijob 主库。
