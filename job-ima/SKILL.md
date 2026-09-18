---
name: job-ima
version: 1.0.0
description: |
  ima 知识库「招聘」专用操作封装。随时浏览、搜索、读取、导出该库素材（2027 届秋招公众号文章为主），
  并可无缝衔接 job-write（码上职业）采写流水线，把选中的招聘素材转成公众号源稿。
  基于 ima-mcp connector（凭证由 connector 托管，已验证可读招聘库），不自带 API 脚本。
  触发词：ima 招聘、招聘库、招聘素材、看招聘知识库、招聘下面、处理招聘库的素材、招聘库里有什么、把招聘素材转公众号、招聘库去重。
metadata:
  agent_created: true
---

# Job-IMA：ima 知识库「招聘」专用操作封装

> 🎯 **单一固定目标**：本技能只操作 ima 知识库 **「招聘」**（ID `7505639995636931`，创建者：朱高校）。
> 已验证可通过 **ima-mcp connector**（`ima-mcp` 当前 connected）完整读写。所有网络操作走 mcp 工具，**不自带 API 脚本**，避免 IMA 凭证错配（仓库内 `~/.config/ima/` 的凭证与 connector 是不同账号，直接用 OpenAPI 会报 `invalid knowledge_base_id`）。

## 一、何时调用

用户说"看看招聘库""招聘下面有什么素材""处理招聘库的素材""招聘库里有什么""把某篇招聘文章转公众号""招聘素材去重"等，
或任何涉及 ima「招聘」知识库的浏览 / 检索 / 导出操作时，直接调用本技能，**无需再走通用 ima-skill 去搜索知识库名称**。

若用户意图是通用知识库 / 笔记操作（非招聘库），改用 `ima-skill`。

## 二、固定知识库

- 名称：**招聘**
- 知识库 ID：`7505639995636931`（已验证；如失效，用 `mcp__ima-mcp__search_knowledge_base` 查 `query:"招聘"` 重新获取）
- 创建者：朱高校
- 当前规模：约 50 篇，全部为公众号文章（2027 届秋招季，含央企/国企、江苏本地、升学体制内三类）

## 三、调用模板（全部走 ima-mcp 工具）

> 首次使用下列 mcp 工具前，若环境未加载其 schema，先用 `ToolSearch` 加载 `mcp__ima-mcp__*` 的 schema，再用 `DeferExecuteTool` 调用。当前会话已加载则直接调用。

### 1) 浏览全部素材（按更新时间倒序）
```
mcp__ima-mcp__get_knowledge_list
  knowledge_base_id: "7505639995636931"
  limit: 50
  cursor: ""
  sort_type: "UPDATE_TS_DESC_SORT_TYPE"
```
`next_cursor` 非空且 `is_end=false` 时继续翻页，直到取全库。

### 2) 库内搜索
```
mcp__ima-mcp__search_knowledge
  query: "南京"            # 关键词
  knowledge_base_id: "7505639995636931"
  cursor: ""
  limit: 20
```

### 3) 读取某篇原文链接
```
mcp__ima-mcp__get_media_info
  media_id: "<media_id>"
```
- `media_type=6`（公众号）：返回 `url_info.url` 即原文链接，用 `mp-save` / WebFetch 取正文。
- `media_type=11`（笔记）：取 `notebook_ext_info.notebook_id` 走 notes 模块。
- `url_info` 为空：提示"请在 ima 客户端查看原文"。

### 4) 库概况（名称 / 创建者 / 总数 / 体积）
```
mcp__ima-mcp__get_knowledge_base_list   # 列全部知识库；或先用 search_knowledge_base 定位后 get_knowledge_base
```

## 四、输出呈现约定（面向用户）

- **隐藏 `media_id`**：只展示 `标题（来源·发布日期）`；内部需要再取 `media_id`。
- `get_knowledge_list` 结果按内容分组展示（参考：央企/全国性、江苏本地、升学体制内），并给总数。
- 公众号文章的**来源**与**发布日期**从条目的 `introduction` 字段解析（`作者:` / `发布时间:`），解析不到留空。
- `time_wording` 是入库时间，展示用 `introduction` 里的真实发布时间。

## 五、与 job-write 衔接

当用户想把某篇 / 某批招聘素材转成公众号图文：

1. `get_media_info` 拿到原文 URL；
2. `mp-save` / WebFetch 取正文；
3. 加载 **job-write** 技能，按其 8 段骨架 + FAQ 长尾块规范产出源稿，推送到「码上职业」（`--profile mashang`）；
4. **不搬运原文、不声明原创、不复制别家二维码；防骗提醒必须留**（job-write 红线）。

## 六、已知坑位

- **重复素材**：库内「江苏省铁路集团」招聘出现两条（来源"看看南京"与"南京人才招聘"），呈现时主动提示去重。
- **凭证**：本技能依赖 `ima-mcp` connector 处于 connected 状态；若断开，提示用户重新连接 ima-mcp，而非改用 `~/.config/ima/` 凭证（该账号无此库权限）。
- **发布时间 ≠ 入库时间**：`time_wording` 是入库时间；展示用 `introduction` 里的真实发布时间。
