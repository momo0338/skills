# 抖音小店（抖店）数据本地化接入指南

> 基于 [mcp-cn-commerce](https://github.com/TonyWang-hub/mcp-cn-commerce) 的抖店 MCP Server 本地化方案。
> 分析日期：2026-08-03 ｜ 项目版本：mcp-cn-commerce 0.1.5

---

## 一、背景与结论

mcp-cn-commerce 是 8 个中国电商平台的 MCP Server 套件（Monorepo），其中 `mcp-cn-doudian` 是抖店（抖音小店）的商家经营数据 MCP。

**核心结论**：
- 抖店模块走的是**官方开放平台 API**（`openapi-fxg.jinritemai.com`），非逆向破解，合规、稳定。
- 唯一门槛是 **4 个凭据**（app_key / app_secret / shop_id / access_token），需要真实抖店商家 + 开放平台开发者资质。
- 依赖极轻（仅 `mcp` + `httpx`），本机 `uv/uvx` 已就绪，可直接运行。

---

## 二、本地化方案 A：直接接入 mcp-cn-doudian（推荐，5 分钟）

### 1. 前置条件

- 抖音小店开放平台账号：https://op.jinritemai.com
- 已创建应用并获取 `App Key` / `App Secret`
- 已完成 OAuth 授权拿到 `Access Token`（有效期通常 2 小时~24 小时，视授权类型）

### 2. 验证凭据可调用（不经过 MCP，直接 curl）

```bash
# 抖店开放平台文档：https://op.jinritemai.com/docs/api-docs
# 用官方文档的「在线调试」先确认凭据有效，再接入 MCP
```

### 3. 配置 opencode.json

编辑 `~/.config/opencode/opencode.json`，在 `mcp` 节点追加：

```jsonc
"doudian": {
  "type": "local",
  "command": ["uvx", "mcp-cn-doudian"],
  "environment": {
    "DOUDIAN_APP_KEY": "你的 app_key",
    "DOUDIAN_APP_SECRET": "你的 app_secret",
    "DOUDIAN_SHOP_ID": "你的 shop_id",
    "DOUDIAN_ACCESS_TOKEN": "你的 access_token"
  }
}
```

重启 opencode 后，Agent 即可调用抖店的 19 个只读工具。

### 4. 抖店 MCP 提供的能力（19 个工具，全部只读）

| 类别 | 工具 | 用途 |
|---|---|---|
| 订单 | `get_order_list` / `get_order_detail` | 订单列表（状态/时间筛选、分页）、订单详情 |
| 商品 | `get_product_list` / `list_categories` / `list_brands` | 商品列表、类目、品牌 |
| 售后 | `get_refund_list` | 退款/售后单 |
| 店铺 | `get_shop_info` / `get_shop_score` | 店铺信息、店铺评分 |
| 物流 | `get_logistics_tracking` / `list_logistics_companies` | 物流轨迹、物流公司 |
| 评价 | `get_review_list` / `get_review_detail` | 商品评价 |
| 飞鸽 | `get_feige_messages` | 飞鸽客服会话 |
| 直播 | `get_live_data` / `list_live_rooms` | 直播数据、直播间列表 |
| 流量 | `get_traffic_data` / `get_short_video_data` | 店铺流量、短视频数据 |
| 营销 | `list_promotions` / `list_coupons` | 活动、优惠券 |
| 财务 | `get_bill_list` | 账单明细 |

### 5. 已知局限（接入前必读）

| 局限 | 影响 | 对策 |
|---|---|---|
| **Access Token 会过期**（通常 24h） | 过期后工具报错 | 本项目**无自动刷新**，需定时手动换 token 或自建刷新脚本 |
| 只读 | 不能改价/发货/回复 | 符合"分析"定位；如需写入走官方其他 API |
| 分页上限 | 部分工具 page_size 最大 100 | 分析大数据量时注意分页聚合 |

---

## 三、本地化方案 B：新建 dy-doudian 项目（适合需要私有化增强时）

### 触发条件

- 有开放平台凭据，但需要补**token 自动刷新**、私有工具、定时任务等能力
- 想与你的 dy-cli 技能体系（`~/.opencode/skills/dy-cli`）风格统一

### 项目结构设计

```
dy-doudian/
├── README.md / SKILL.md          # 与 dy-cli 技能风格一致，含触发词
├── pyproject.toml                # 依赖: mcp + httpx（与上游一致）
├── src/dy_doudian/
│   ├── __init__.py
│   ├── client.py                 # 官方 API 客户端（复用上游 MD5 签名算法）
│   ├── config.py                 # 配置加载（环境变量 + .env 文件）
│   ├── token_manager.py          # ★ 核心增强：access_token 自动刷新 + 持久化
│   ├── tools/                    # ★ 私有工具（按需裁剪上游 19 个 + 新增）
│   │   ├── orders.py             # 订单
│   │   ├── products.py           # 商品
│   │   ├── reviews.py            # 评价
│   │   └── ...
│   └── mcp_server.py             # MCP 入口（uvx / python -m 两用）
├── scripts/
│   ├── refresh_token.py          # 定时刷新 token 的独立脚本（配合 launchd/cron）
│   └── oauth_login.py            # 首次 OAuth 授权向导
└── tests/
    ├── test_client.py            # 签名正确性测试（对齐上游测试用例）
    └── test_token_manager.py
```

### 关键增强点（相对上游）

1. **token_manager.py** — 上游最大短板：
   - 记录 `access_token` + `expires_at`
   - 调用前检查剩余有效期，<10 分钟自动用 `refresh_token` 换新
   - 换新后原子写入持久化存储（`~/.dy-doudian/tokens.json`）
   - 全流程串行加锁，避免并发重复刷新

2. **config.py** — 支持 `.env` 文件 + 环境变量，与 dy-cli 的 `dy config` 模式一致

3. **tools 裁剪** — 按实际店铺需要保留子集，减少 MCP 工具噪音

### 落地顺序建议

```
1. 确认有 openai 开放平台凭据（方案 A 的硬前提）
2. 方案 A 先跑通（uvx 直接接入，验证数据可用）
3. 如果 token 过期频繁 → 升级方案 B，先实现 token_manager
4. 如果工具噪音大 → 裁剪 tools，只留常用
```

---

## 四、决策树

```
有抖店开放平台 app_key/access_token？
├── 有 → 方案 A：uvx 直接接入（5 分钟，先验证数据）
│        └── token 过期是痛点？→ 是 → 方案 B 的 token_manager
├── 无 → 先解决凭据：
│        ├── 是真实抖店商家 → 申请开放平台开发者资质
│        └── 非商家 → 该 MCP 不适合；转向「内容侧」能力（dy-cli 已覆盖）
```

---

## 四·五、⚠️ 重要发现：本机已有抖店本地化基础（2026-08-03 复核）

分析过程中发现 `/Users/zhugx/src/doudian/` 已存在**抖店桌面 GUI 自动化路线**，这会改变对 mcp-cn-commerce 的取舍：

| 维度 | 已有路线（`/Users/zhugx/src/doudian/`） | mcp-cn-doudian（开放平台 API） |
|---|---|---|
| 技术 | macOS 抖店工作台 App 桌面操作 | 官方开放平台 REST API |
| 凭据 | 仅需已登录的桌面 App | 需 app_key/secret/token（开发者资质） |
| 能力 | **读写全量**：商品/订单/售后/发货/营销/账户全操作 | **只读**：查询/统计/导出 |
| 覆盖 | 订单导出、打单发货、售后审核、上下架、发布、投放 | 订单/商品/评价/直播/流量/账单查询 |
| 适合 | 日常运营实操（改价/发货/审核） | 结构化数据分析（AI 只读调用） |

**结论修正**：
- 若目标是用 AI 做**日常运营实操**（发货/审核/上下架）→ 已有桌面路线已覆盖，mcp-cn-commerce 无用武之地。
- 若目标是用 AI 做**结构化数据洞察**（订单统计、流量分析、直播复盘，需程序化读取）→ mcp-cn-doudian 是补充，但前提仍是开放平台凭据。
- `.skill-staging/` 中已有 `analyze-viral-commerce-video(-cn/-v2)` 技能（爆款带货视频结构化拆解，含 doudian-baseline 校准基线）——这是**抖店后台数据 + 视频分析**的既有成果，与本仓库的 `analyze-viral-commerce-video`（已发布版本）存在演进关系，注意版本同步。

---

## 五、本地验证记录（2026-08-03）

- `git clone` 成功，位于 `/Users/zhugx/src/mcp-cn-commerce`
- venv 安装 `mcp-cn-commerce 0.1.5` 成功（Python 3.14，依赖 mcp 1.29.0 + httpx）
- `mcp-cn-doudian` MCP 握手（initialize）成功，serverInfo: `mcp-cn-doudian v1.29.0`
- `uvx mcp-cn-doudian` 启动成功（uv 0.11.6 本机可用）
- 工具列表因 stdio 测试脚手架时序问题未在自动化中列出，源码确认 19 个 `@server.tool()`
- **凭据未配置**：缺 `DOUDIAN_APP_KEY` 等 4 个环境变量时 server 会报 ConfigError（符合预期）
