---
name: job-ima
version: 1.1.0
description: |
  ima 知识库「招聘」专用操作封装。随时浏览、搜索、读取、导出该库素材（2027 届秋招公众号文章为主），
  并可无缝衔接 job-write（码上职业）采写流水线，把选中的招聘素材转成公众号源稿。
  双通道：优先 ima-mcp connector；connector 不可用时回退 ima OpenAPI（~/.config/ima/ 凭证，已验证可读招聘库）。
  触发词：ima 招聘、招聘库、招聘素材、看招聘知识库、招聘下面、处理招聘库的素材、招聘库里有什么、把招聘素材转公众号、招聘库去重。
metadata:
  agent_created: true
---

# Job-IMA：ima 知识库「招聘」专用操作封装

> 🎯 **单一固定目标**：本技能只操作 ima 知识库 **「招聘」**（创建者：朱高校）。
> 🚨 **两套 ID 不是一回事，用错必报错**：
> - `ima-mcp` connector 通道：`knowledge_base_id = 7505639995636931`
> - **ima OpenAPI 通道**：`kb_id = WLHLqUjhy6b8nt84Y5Hjg8KOKQGfMINKJ1rPvAF35Zg=`（base64 形态；把数字 ID 传给 OpenAPI 会返回 `code 220004 invalid knowledge_base_id`）
>
> **双通道，任一可用即可**（2026-09-18 15:40 实测）：
> | 通道 | 何时用 | 凭证/入口 |
> |---|---|---|
> | `ima-mcp` connector | 默认优先（字段更全，带 `introduction`＝来源+发布时间） | mcp 工具，无需本地凭证 |
> | **ima OpenAPI** | connector 工具在会话里不可见 / 报 not found 时的**兜底** | `~/.config/ima/{client_id,api_key}` + `~/.workbuddy/skills/ima-skill/ima_api.cjs`（见 §三.5） |

## 一、何时调用

用户说"看看招聘库""招聘下面有什么素材""处理招聘库的素材""招聘库里有什么""把某篇招聘文章转公众号""招聘素材去重"等，
或任何涉及 ima「招聘」知识库的浏览 / 检索 / 导出操作时，直接调用本技能，**无需再走通用 ima-skill 去搜索知识库名称**。

若用户意图是通用知识库 / 笔记操作（非招聘库），改用 `ima-skill`。

## 二、固定知识库

- 名称：**招聘**
- 知识库 ID（mcp）：`7505639995636931`
- 知识库 ID（OpenAPI）：`WLHLqUjhy6b8nt84Y5Hjg8KOKQGfMINKJ1rPvAF35Zg=`
- 创建者：朱高校
- 当前规模：**53 篇**（2026-09-18 15:40 复核），全部为公众号文章（2027 届秋招季，含央企/国企、江苏本地、升学体制内三类）
- 校验/重新定位：`search_knowledge_base` 查 `query:"招聘"` → `data.info_list[0].kb_id` / `kb_name` / `content_count` / `creator`

## 三、调用模板（全部走 ima-mcp 工具）

> 首次使用下列 mcp 工具前，若环境未加载其 schema，先用 `ToolSearch` 加载 `mcp__ima-mcp__*` 的 schema，再用 `DeferExecuteTool` 调用。当前会话已加载则直接调用。
> ⚠️ 若 `ToolSearch` / `DeferExecuteTool` 报 **tool not found in the deferred tools index** → connector 在本会话未建连，**立刻转 §三.5 的 OpenAPI 兜底**，不要空手回报用户。

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

### 5) 🆘 OpenAPI 兜底通道（connector 不可用时，2026-09-18 实测全通）

脚本：`~/.workbuddy/skills/ima-skill/ima_api.cjs`（读 `~/.config/ima/` 凭证，`POST https://ima.qq.com/<apiPath>`）。
运行（**用 managed node 全路径**）：

```bash
NODE=/Users/zhugx/.workbuddy/binaries/node/versions/22.22.2-3/bin/node
KB="WLHLqUjhy6b8nt84Y5Hjg8KOKQGfMINKJ1rPvAF35Zg="

# ① 定位/校验知识库（也用于确认最新条数 content_count）
$NODE ~/.workbuddy/skills/ima-skill/ima_api.cjs openapi/wiki/v1/search_knowledge_base \
  '{"query":"招聘","cursor":"","limit":20}'

# ② 全量列条目（翻页：用返回的 next_cursor；is_end=true 即结束。limit 上限实测 50）
$NODE ~/.workbuddy/skills/ima-skill/ima_api.cjs openapi/wiki/v1/get_knowledge_list \
  "{\"knowledge_base_id\":\"$KB\",\"cursor\":\"\",\"limit\":50}"

# ③ 取原文链接
$NODE ~/.workbuddy/skills/ima-skill/ima_api.cjs openapi/wiki/v1/get_media_info \
  '{"media_id":"<media_id>"}'

# ④ 库内搜索
$NODE ~/.workbuddy/skills/ima-skill/ima_api.cjs openapi/wiki/v1/search_knowledge \
  "{\"query\":\"南京\",\"knowledge_base_id\":\"$KB\",\"cursor\":\"\",\"limit\":20}"
```

**OpenAPI 与 mcp 的字段差异（重要）**：
- 列表项放在 `data.knowledge_list`（**不是** `info_list`），字段只有 `media_id` / `title` / `parent_folder_id` / `tags` / `media_type`——
  **没有 `introduction`、没有 `time_wording`**。→ 想拿「来源号 + 发布时间」，要去取原文页：
  `curl -sL -A "<桌面 UA>" "<url>"` 后从 HTML 抓 `var nickname = "..."`（来源号）与 `var create_time = "<unix秒>"`（发布时间，用 `date -r <ts>` 转）。
- 搜索接口 `search_knowledge` 返回的条目字段与 mcp 一致，可先用它拿带 `introduction` 的富条目。

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
- **凭证 / 通道**（2026-09-18 更正旧结论）：~~本地 `~/.config/ima/` 凭证无此库权限~~ **错**。实测该凭证走 OpenAPI **可正常读取招聘库全部 53 条**，此前报 `invalid knowledge_base_id` 的真实原因是**把 mcp 的数字 ID 传给了 OpenAPI**；OpenAPI 必须用 §二 的 base64 `kb_id`。
  所以：connector 不可用**不是死路**，直接切 §三.5，不要因为"避免凭证错配"就空手回报。
- **发布时间 ≠ 入库时间**：mcp 的 `time_wording` 是入库时间，展示用 `introduction` 里的真实发布时间；OpenAPI 无 `introduction`，改从原文页 `create_time` 取。
- **列表排序**：OpenAPI `get_knowledge_list` 不传 `sort_type` 时按**入库（更新）时间倒序** → **列表头部即最新入库**，做增量比对时先看前 N 条即可。
- **正文层级**：转载号（如"金陵人才"）常是**纯图片海报型**，正文节点只有免责声明，`img` 无 `alt` → 该条只能当**线索**，硬信息必须回官方源（沿用台账 §二 结论）。
- **增量比对惯例**：拉完新快照后，与 `../巡检记录/ima-招聘素材清单-<日期>.md` 做标题 diff，**只把真增量（新主体/新公告）登记为 A 线候选**，方法论文章与已入库条目的转载变体不入选题池。
