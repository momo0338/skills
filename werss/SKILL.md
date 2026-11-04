---
name: werss
description: Manage and automate WeChat Official Accounts RSS feeds via WeRSS API (https://rss.mmdai.top). Use when user provides a WeChat article URL to subscribe, wants to manage subscriptions, fetch latest articles, trigger sync, or export OPML/RSS feeds.
---

# WeRSS 微信公众号 RSS 订阅与控制技能

## 概述

**WeRSS**（微信公众号订阅助手）是一个面向自托管场景的微信公众号聚合、解析与 RSS/Atom 转换系统。
本技能封装了基于 **AK/SK 鉴权**（`Authorization: AK-SK <AccessKey>:<SecretKey>`）的完整操作能力，核心支持**“提供任意微信公众号文章链接，秒级自动识别公众号并订阅”**，并提供即时抓取更新、文章查询、RSS 订阅源导出与订阅生命周期管理。

- **WeRSS API 文档**：`https://rss.mmdai.top/api/docs`
- **默认服务节点**：`https://rss.mmdai.top`
- **CLI 工具路径**：`/Users/zhugx/src/skills/werss/werss_cli.py`（零第三方依赖，基于 Python 3 标准库）
- **配置文件路径**：`/Users/zhugx/src/skills/werss/config.json`

---

## 适用场景 (When to Use)

1. **丢链接一键订阅**：用户提供了一个微信公众号文章链接（形如 `https://mp.weixin.qq.com/s/...`），希望订阅该公众号并获取 RSS 源。
2. **查询订阅列表**：用户想要查看当前订阅了哪些微信公众号、更新状态或获取某个公众号的 RSS / Atom / JSON Feed 链接。
3. **即时同步更新**：用户想要立即抓取某个公众号的最新文章。
4. **文章检索与阅读**：用户想要搜索已抓取的公众号文章历史。
5. **OPML 批量导出**：用户需要导出全部订阅源到 NetNewsWire、Feedly、Follow、FreshRSS 等 RSS 阅读器。
6. **在线搜索与订阅**：根据公众号名称关键词进行微信全网搜索并添加。

---

## 核心工作流与 CLI 命令

### 1. 丢一个文章链接，一键添加公众号订阅（核心功能）
自动下载文章、提取公众号元数据（名称、ID、Biz、头像）、自动入库并返回专属 RSS/Atom 链接：

```bash
python3 /Users/zhugx/src/skills/werss/werss_cli.py subscribe --url "https://mp.weixin.qq.com/s/oJt-TI3D8EU-Yj8mZeWqKQ"
```

输出示例：
```text
[✓] 订阅成功！
==================================================
  公众号名称: 国资小新
  内部识别码: MP_WXS_2390216734
  解析来源文: 【校招】中国储备粮管理集团有限公司2027年度校园招聘公告
  微信 Biz ID: MjM5MDIxNjczNA==
  头像链接: https://mmbiz.qpic.cn/...
--------------------------------------------------
  RSS 订阅源:
  • RSS 2.0:  https://rss.mmdai.top/feed/MP_WXS_2390216734.xml
  • Atom:     https://rss.mmdai.top/feed/MP_WXS_2390216734.atom
  • JSON:     https://rss.mmdai.top/feed/MP_WXS_2390216734.json
==================================================
```

### 2. 查看已订阅公众号列表
列出当前所有公众号及其 ID、状态、专属 Feed 链接：

```bash
# 标准表格展示
python3 /Users/zhugx/src/skills/werss/werss_cli.py list

# 按关键词筛选
python3 /Users/zhugx/src/skills/werss/werss_cli.py list --keyword "国资"

# 输出完整 JSON 格式
python3 /Users/zhugx/src/skills/werss/werss_cli.py list --json
```

### 3. 获取公众号的 Feed 链接
```bash
# 获取单个公众号的三种订阅格式（RSS 2.0, Atom, JSON）
python3 /Users/zhugx/src/skills/werss/werss_cli.py feed --id MP_WXS_2390216734

# 获取全局聚合 RSS（所有已订阅公众号文章合集）
python3 /Users/zhugx/src/skills/werss/werss_cli.py feed
# -> https://rss.mmdai.top/feed/all.xml
```

### 4. 即时触发更新同步（抓取新文章）
当用户希望立即刷新某个公众号的文章时调用：

```bash
python3 /Users/zhugx/src/skills/werss/werss_cli.py sync MP_WXS_2390216734
```

### 5. 查询公众号历史文章
```bash
# 查询指定公众号最新文章
python3 /Users/zhugx/src/skills/werss/werss_cli.py articles --mp-id MP_WXS_2390216734 --limit 5

# 按文章标题关键词检索
python3 /Users/zhugx/src/skills/werss/werss_cli.py articles --keyword "招聘" --limit 10
```

### 6. 在线全网搜索公众号
如果用户只记得公众号名字而没有具体文章链接：

```bash
python3 /Users/zhugx/src/skills/werss/werss_cli.py search "机器之心"
```

### 7. 导出 OPML 订阅文件
导出标准 OPML 2.0 文件，可直接导入至任意第三方 RSS 阅读器：

```bash
python3 /Users/zhugx/src/skills/werss/werss_cli.py export-opml -o /path/to/my_subscriptions.opml
```

### 8. 标签管理与标签聚合 Feed
对公众号进行分类管理，并生成该分类标签专属的聚合 RSS / Atom 订阅源：

```bash
# 查看所有标签及其公众号数量和专属 Feed URL
python3 /Users/zhugx/src/skills/werss/werss_cli.py tags

# 创建新标签
python3 /Users/zhugx/src/skills/werss/werss_cli.py tags create --name "大学就业中心" --intro "高校就业指导中心"

# 为指定标签追加公众号
python3 /Users/zhugx/src/skills/werss/werss_cli.py tags add --tag "大学就业中心" --mp-ids MP_WXS_3086031217 MP_WXS_3522786087
```

### 9. 删除公众号订阅
```bash
python3 /Users/zhugx/src/skills/werss/werss_cli.py delete MP_WXS_2390216734
```

---

## 认证与底层 API 规范

若需要在脚本、代码或外部 HTTP 客户端中直接调用 WeRSS API：

### 请求头规范
```http
Authorization: AK-SK WKbxzdFTgKekXKwE6lZjxQwmP6neaTJFnJ:SKQQmC_nOlGqLzP56M4hXhbuGZr9aOc7Vc
Content-Type: application/json
```

### 常用核心端点清单

| 操作 | HTTP 方法 | API 路径 | 参数说明 |
| :--- | :--- | :--- | :--- |
| **文章链接订阅** | `POST` | `/api/v1/wx/mps/by_article` | Query 参数: `url=<文章完整URL>` |
| **公众号列表** | `GET` | `/api/v1/wx/mps` | Query 参数: `page=1&size=20&keyword=...` |
| **手动添加** | `POST` | `/api/v1/wx/mps` | JSON Body: `{"mp_name": "名称"}` |
| **更新抓取** | `GET` | `/api/v1/wx/mps/update/{mp_id}` | Query 参数: `start_page=0&end_page=1` |
| **搜索公众号** | `GET` | `/api/v1/wx/mps/search/{kw}` | 路径参数为 URL 编码的搜索词 |
| **文章列表** | `GET` | `/api/v1/wx/articles` | Query 参数: `mp_id=...&keyword=...&limit=20` |
| **导出 OPML** | `GET` | `/api/v1/wx/export/mps/opml` | 返回 XML 格式的 OPML 文件 |
| **删除订阅** | `DELETE` | `/api/v1/wx/mps/{mp_id}` | 路径参数为公众号唯一 ID |

---

## 凭证保护与环境变量覆盖

本技能在 `/Users/zhugx/src/skills/werss/config.json` 中配置了预设凭证，同时支持以下环境变量覆盖：

```bash
export WERSS_BASE_URL="https://rss.mmdai.top"
export WERSS_ACCESS_KEY="WKbxzdFTgKekXKwE6lZjxQwmP6neaTJFnJ"
export WERSS_SECRET_KEY="SKQQmC_nOlGqLzP56M4hXhbuGZr9aOc7Vc"
```
优先级：CLI 命令行参数（`--ak` / `--sk`） > 环境变量 > `config.json`。
