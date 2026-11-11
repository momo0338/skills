---
name: quarkpanso
description: "在夸克盘搜（QuarkPanSo.com）搜索夸克网盘资源，返回 3 条结果（标题、文件预览、分享时间、详情页链接）。用户要找电影、剧集、动漫、综艺、电子书、软件、教程、资料、音乐等夸克网盘分享时使用；只支持夸克网盘，不支持百度/阿里/迅雷。免配置即可用，一次请求秒回。"
---

# 夸克盘搜资源搜索

在 QuarkPanSo.com 上搜索**夸克网盘**资源，默认返回 3 条，只返回状态正常的资源。只支持夸克网盘，不支持百度/阿里/迅雷。

## 数据通道

1. **公开只读接口（首选）**：`scripts/search.py` 默认指向 `https://amcmm.com/api/pan-search-v3.php`，一次 GET 秒回，无需任何配置。
2. **浏览器兜底**：接口不可用时，用页面搜索（慢，但一定能用）。

```bash
python3 scripts/search.py "武林外传"        # 走公开接口
python3 scripts/search.py "武林外传" --raw   # 接口返回原始内容，排查用
```

脚本输出 `channel` 字段：`endpoint` 表示走了接口；返回 `ENDPOINT_UNAVAILABLE` 时按「浏览器模式」继续。

## 接口模式

```bash
python3 scripts/search.py "武林外传"                       # 默认 3 条
python3 scripts/search.py "武林外传" --limit 5
python3 scripts/search.py "三体" --share-time month
```

| 参数 | 说明 |
|---|---|
| `--limit N` | 返回条数，默认 3，服务端最多 5 |
| `--share-time month` | `week` / `month` / `half_year` / `year` |
| `--page N` | 翻页，默认 1 |
| `--endpoint URL` | 换接口地址（默认 `https://amcmm.com/api/pan-search-v3.php`） |

输出：

```json
{"ok": true, "keyword": "武林外传", "total": 55, "count": 3, "channel": "endpoint",
 "results": [{"title": "武林外传", "doc_id": "cmm...", "url": "https://www.quarkpanso.com/doc/cmm...",
              "status": 0, "status_text": "有效", "files": ["file:武林外传59.mp4"],
              "file_count": 7, "share_time": "2026-02-27 10:57:03", "share_user": "街头*梦",
              "disk_type": "QUARK"}]}
```

- `title` / `files` 已去掉站点返回的 `<em>` 高亮标签。
- `total` 是命中总数，可用于「一共 55 条，先给 3 条」。
- `files` 是前 3 项预览，`file_count` 是完整数量；个别条目可能缺 `file:` 前缀（上游原始数据如此），照原样展示即可。
- 结果固定为夸克网盘（`disk_type: QUARK`），接口与站点侧都只查这一类。

## 浏览器模式（接口不可用时）

1. 拼 URL：`https://www.quarkpanso.com/search?q={URL编码后的关键词}`，筛选参数见 [references/site-notes.md](references/site-notes.md)。
2. 取候选：`rows = bu.read_all("a[href*='/doc/']", fields=["text", "href"], limit=20)`，多取 2~3 倍。
3. 逐条验证：打开详情页读「状态检测」——`有效` 收下、`可能失效` 默认不收、`失效` 跳过、字段缺失重试一次。
4. 收够 3 条即停。

## 回复用户

```
为你找到以下 3 条【武林外传】资源（共 55 条）：

1. **武林外传**
   - 文件：武林外传59.mp4、资源汇总.txt、武林外传2.mp4（共 7 项）
   - 分享时间：2026-02-27
   - 详情页：https://www.quarkpanso.com/doc/cmm4ufsc504c7bovr58z5vgvr

2. ...
3. ...
```

只要名字和链接时，压成「标题 + 详情页链接」两行。

## 错误与边界

| 情况 | 怎么做 |
|---|---|
| `ENDPOINT_UNAVAILABLE` | 切浏览器模式，不要向用户报错 |
| 接口 429 | 请求太频繁，等 10~20 秒重试一次，仍失败切浏览器 |
| 条数不足 / 零结果 | 如实说找到几条；建议换关键词（原名/别名/加年份/去副标题） |
| 结果跑偏 | 站点对空格分隔的多词按宽松匹配处理（「三体 电视剧」会掺进别的剧），只用核心词最准 |
| 页面提示系统繁忙/412/验证码 | 等 10~20 秒重试一次，不要连续请求 |
| 用户要百度/阿里/迅雷链接 | 明确说明本技能只支持夸克网盘，不要硬搜或改用其他站点 |

## 硬性约束

- 只给站点详情页链接（`/doc/{doc_id}`），**不输出** `pan.quark.cn` / `pan.baidu.com` 等原始分享链接。
- `status` 是入库状态（0 正常 / 1 被举报 / 2 已处理 / 3 相似资源 / 4 可能失效），不等于此刻 100% 可打开；用户要求「必须确认能打开」时用浏览器逐条核验「状态检测」。
- 不要绕开接口直打 `/v1/search/disk`：外部请求恒定 `{"code":412,"msg":"系统过载，稍后重试 [timestamp]"}`。
