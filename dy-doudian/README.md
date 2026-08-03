# dy-doudian

抖音小店（抖店）本地化数据工具与 MCP Server —— 订单/商品/售后/评价/店铺/物流/飞鸽/直播/流量/营销/类目/账单 19 个只读工具 + 浏览器自动化运营，access_token 自动刷新。

基于抖店开放平台官方 API（`openapi-fxg.jinritemai.com`），MD5 签名算法与 [mcp-cn-commerce](https://github.com/TonyWang-hub/mcp-cn-commerce) 兼容。

## 特性

- **官方 API**：非逆向，合规稳定
- **Token 自动刷新**：临近过期自动换新并持久化（`~/.dy-doudian/tokens.json`）
- **双引擎**：API 层（19 只读工具）+ 浏览器层（Playwright 控制抖店网页版：商品上下架/订单发货/每日巡检）
- **写操作安全**：浏览器写操作默认 dry-run，需显式 `--execute`
- **双入口**：CLI（`dy-doudian`）+ MCP Server（`dy-doudian-mcp`）
- **极简依赖**：mcp + httpx + python-dotenv（浏览器层可选 playwright）

## 快速开始

```bash
uv sync
export DOUDIAN_APP_KEY=... DOUDIAN_APP_SECRET=... DOUDIAN_SHOP_ID=... DOUDIAN_ACCESS_TOKEN=...
python -m dy_doudian.cli status
python -m dy_doudian.cli query orders --page-size 5
```

详见 [SKILL.md](./SKILL.md)。

## 测试

```bash
python -m pytest tests/ -v
```

## 项目结构

```
src/dy_doudian/
├── client.py          # API 客户端（MD5 签名）
├── token_manager.py   # token 生命周期（刷新+持久化）
├── config.py          # 配置加载（环境变量/.env）
├── cli.py             # 命令行入口
└── mcp_server.py      # MCP Server 入口
```

## License

MIT
