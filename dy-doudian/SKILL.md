---
name: dy-doudian
description: |
  抖音小店（抖店）本地化数据工具与 MCP Server。基于抖店开放平台官方 API，提供订单/商品/售后/评价/店铺/物流/飞鸽/直播/流量/营销/类目/账单等经营数据的只读查询，支持 access_token 自动刷新与持久化。
  当用户需要查询抖店订单、商品、评价、直播数据、账单，或让 AI Agent 读取自家店铺经营数据时触发。
  触发词：抖店、抖音小店、doudian、店铺订单、商品管理、经营数据、DOUDIAN。
---

# dy-doudian — 抖音小店本地化数据工具

> 基于抖店开放平台官方 API（`openapi-fxg.jinritemai.com`），把店铺经营数据暴露给 AI Agent。
> 相对 mcp-cn-commerce 的核心增强：**access_token 自动刷新 + 持久化**（上游无此能力）。

## 架构与能力

```
dy-doudian/
├── src/dy_doudian/
│   ├── client.py          # 官方 API 客户端（MD5 签名，与 mcp-cn-commerce 算法一致）
│   ├── token_manager.py   # ★ access_token 自动刷新 + 持久化（核心增强）
│   ├── config.py          # 环境变量 + ~/.dy-doudian/.env 加载
│   ├── cli.py             # 命令行：status / token / query / browser
│   ├── mcp_server.py      # MCP Server（19 个只读工具）
│   └── browser/           # ★ 浏览器自动化运营层（Playwright 控制抖店网页版）
│       ├── base.py        #   登录态持久化 + 通用页面操作
│       ├── shop_client.py #   商品管理（全量读取/批量下架）
│       ├── order_client.py#   订单管理（查询/发货）
│       ├── daily_report.py#   每日巡检日报
│       └── cli.py         #   browser 子命令入口
└── tests/                 # API/浏览器逻辑测试
```

## 双引擎架构（API + 浏览器）

| 层 | 技术 | 能力 | 适用 |
|---|---|---|---|
| **API 层** | 开放平台 REST | 19 个只读查询（订单/商品/售后/店铺/物流/飞鸽/直播/流量/营销/账单） | 结构化数据分析、AI 自动调用 |
| **浏览器层** | Playwright 控制 `fxg.jinritemai.com` | 写操作 + 复杂页面：商品批量上下架、订单发货、每日巡检 | 运营实操（需登录态） |

> 为什么需要两层：开放平台 API 只读且部分数据接口需单独授权；抖店网页版能做写操作（上下架/发货），但需要浏览器自动化。两层互补。

## 浏览器层使用

```bash
# 首次：登录并保存登录态（自动复用）
python -m dy_doudian.cli browser login

# 读取在售商品列表
python -m dy_doudian.cli browser products --max-pages 20

# 批量下架（默认仅定位验证，加 --execute 实际执行）
python -m dy_doudian.cli browser takedown --ids 1234567890123456789,9876543210987654321
python -m dy_doudian.cli browser takedown --ids ... --execute

# 订单操作
python -m dy_doudian.cli browser orders count          # 订单总数
python -m dy_doudian.cli browser orders today          # 今日订单
python -m dy_doudian.cli browser orders ship --ids ... --execute  # 发货（默认 dry-run）

# 每日巡检生成日报
python -m dy_doudian.cli browser report
```

## 安装

```bash
cd /Users/zhugx/src/skills/dy-doudian
uv sync  # 或 pip install -e .
```

## 配置凭据（一次性）

```bash
# 方式一：环境变量
export DOUDIAN_APP_KEY="你的 app_key"
export DOUDIAN_APP_SECRET="你的 app_secret"
export DOUDIAN_SHOP_ID="你的 shop_id"
export DOUDIAN_ACCESS_TOKEN="你的 access_token"
export DOUDIAN_REFRESH_TOKEN="你的 refresh_token"   # 可选，用于自动续期

# 方式二：配置文件（推荐，与 dy-cli 风格一致）
mkdir -p ~/.dy-doudian
cat > ~/.dy-doudian/.env <<'EOF'
DOUDIAN_APP_KEY=...
DOUDIAN_APP_SECRET=...
DOUDIAN_SHOP_ID=...
DOUDIAN_ACCESS_TOKEN=...
DOUDIAN_REFRESH_TOKEN=...
EOF
```

> 凭据获取：抖店开放平台 https://op.jinritemai.com → 应用管理 → 创建应用，完成 OAuth 授权。

## CLI 用法

```bash
# 查看凭据配置状态
python3 -m dy_doudian.cli status

# 查看当前 token（临近过期自动刷新）
python3 -m dy_doudian.cli token

# 查询订单
python3 -m dy_doudian.cli query orders --page 0 --page-size 10

# 查询商品
python3 -m dy_doudian.cli query products --page-size 20

# 查询评价
python3 -m dy_doudian.cli query reviews --page-size 20
```

## MCP 接入（opencode.json）

```jsonc
"doudian": {
  "type": "local",
  "command": ["uvx", "--from", "/Users/zhugx/src/skills/dy-doudian", "dy-doudian-mcp"],
  "environment": {
    "DOUDIAN_APP_KEY": "你的 app_key",
    "DOUDIAN_APP_SECRET": "你的 app_secret",
    "DOUDIAN_SHOP_ID": "你的 shop_id",
    "DOUDIAN_ACCESS_TOKEN": "你的 access_token"
  }
}
```

重启 opencode 后，Agent 可调用以下 19 个只读工具：

| 类别 | 工具 | 说明 |
|---|---|---|
| 订单 | `get_order_list` / `get_order_detail` | 订单列表（时间/状态筛选、分页）、订单详情 |
| 商品 | `get_product_list` / `get_product_detail` | 商品列表、商品详情 |
| 售后 | `get_refund_list` | 售后/退款单（类型筛选） |
| 评价 | `get_review_list` | 商品评价 |
| 店铺 | `get_shop_info` / `get_shop_score` | 店铺信息、店铺评分 |
| 物流 | `get_logistics_tracking` / `list_logistics_companies` | 物流轨迹、物流公司 |
| 飞鸽客服 | `get_feige_messages` | 客服会话消息 |
| 直播 | `get_live_data` / `list_live_rooms` | 直播间数据、直播间列表 |
| 流量 | `get_traffic_data` / `get_short_video_data` | 店铺流量、短视频数据 |
| 营销 | `list_promotions` / `list_coupons` | 营销活动、优惠券 |
| 类目品牌 | `list_categories` / `list_brands` | 商品类目、品牌 |
| 财务 | `get_bill_list` | 账单明细 |

## Token 自动刷新（相对上游的增强）

- 上游 mcp-cn-commerce **无刷新机制**，access_token 过期即报错
- 本项目 `TokenManager`：
  1. 剩余有效期 <10 分钟时自动调用 `/token/refresh/` 换新
  2. 新 token 原子写入 `~/.dy-doudian/tokens.json`
  3. 进程重启后自动从持久化文件恢复
  4. 多线程安全（内部加锁）

## 已知限制

- **API 层只读**：仅查询类 API；写操作走浏览器层
- **浏览器层安全边界**：
  - 只读操作（商品列表/订单数/巡检）可直接执行
  - 写操作（上下架/发货）**默认 dry-run**，必须显式 `--execute` 才实际提交
  - 登录态持久化在 `~/.dy-doudian/browser-state.json`，含敏感 Cookie，注意权限保护
  - 抖店网页版页面结构可能随改版变化，选择器失效时需更新
- token 刷新依赖 `refresh_token`；若无 refresh_token，临近过期会明确报错提示重新授权
- 部分 API 方法名按抖店文档需按实际授权范围调整（如 `comment/list` 以官方文档为准）
- 浏览器层依赖 `playwright`（`pip install -e ".[browser]"`），需先 `playwright install chromium`
