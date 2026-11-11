# 站点与接口备忘

站点：`https://www.quarkpanso.com`（夸克盘搜，ReMan v1.11.10）。前端是 SPA，任意不存在路径都会回退成 200 的 HTML，判断接口不能看状态码，要看返回体是不是 JSON。

## 1. 公开只读接口（skill 默认通道）

`GET https://amcmm.com/api/pan-search-v3.php`

| 参数 | 取值 | 说明 |
|---|---|---|
| `q` | 关键词 | 必填，≤60 字 |
| `limit` | 1~5 | 默认 3，超出按 5 处理 |
| `share_time` | `week` `month` `half_year` `year` | 分享时间范围 |
| `page` | ≥1 | 翻页 |

返回：`{ok, keyword, total, count, skipped_unhealthy, from_cache, results:[{title, doc_id, url, status, status_text, files, file_count, share_time, share_user, disk_type}]}`。

- 响应头带 `X-API-Version: quark-only-1`，可用于确认部署的是否为夸克限定版。

- 只查夸克网盘（服务端固定 `type=QUARK`，返回 `disk_type: QUARK`），不支持百度/阿里/迅雷。
- 服务端持有站点 token，调用方不需要任何密钥；返回里不含网盘原始分享链接。
- 同参数 60 秒缓存；按 IP 限流 30 次/分钟，超限返回 429 `RATE_LIMITED`。
- 失败码：`BAD_REQUEST` 400、`SERVER_NOT_CONFIGURED` 500、`RATE_LIMITED` 429、`UPSTREAM` 502、`UPSTREAM_AUTH` 502（站点 token 失效）。

## 2. 搜索页（浏览器兜底）

`GET /search?q={关键词}`

| 参数 | 取值 | 说明 |
|---|---|---|
| `q` | 关键词 | 必填，URL 编码 |
| `order` | `hot` 等 | 排序 |
| `share_time` | `week` `month` `half_year` `year` | 分享时间 |
| `exact` | `1` | 精确模式（实测作用有限） |
| `format` | `[".mp4",".mkv"]` | 格式过滤，需 URL 编码 |
| `page` | 数字 | 翻页 |
| `type` | `QUARK` | 本技能只支持夸克，通常不传（站点绝大多数资源本就是夸克） |

页面顶部回显「为您提供 XXX 搜索结果 N 条」，可判断命中量。结果卡片：标题（即 `/doc/{id}` 链接）→ `file:` / `folder:` 清单 → 标签 → 网盘类型 → 分享日期 → 失效/违规举报。**列表页没有有效性信息。**

```python
rows = bu.read_all("a[href*='/doc/']", fields=["text", "href"], limit=20)
```

## 3. 详情页

`GET /doc/{id}`，字段纵向排列：

```
分享时间    2026-02-24 04:02:33
入库时间    2026-07-03 23:31:18
状态检测    有效
资源类型    夸克网盘
分享用户    端庄*狮子9
资源标签    小说 / 大米 / ...
```

「状态检测」三种取值：`有效` / `可能失效` / `失效`（或提示资源已删除）。`可能失效` 不要混进主结果。

## 4. 已知坑

- **`POST /v1/search/disk` 直连必 412**：`{"code":412,"msg":"系统过载，稍后重试 [timestamp]"}`，加浏览器 UA/Referer 也一样，别试。
- **多词宽松匹配**：空格分隔的词会掺进无关结果（「三体 电视剧」返回一堆别的剧），用核心词最准。
- **SPA 全量回退**：`/v1/user/info`、`/nonexistent` 都返回 200 HTML。
- **接口的 `status` 是入库状态**，不等于分享此刻可打开；要确认只能开详情页看「状态检测」。
- **文件清单偶有缺前缀**：上游个别行不以 `file:` 开头（如「亮剑 第16集.mp4」），非解析错误。
