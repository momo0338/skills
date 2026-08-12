# dy-wode 分类页面与接口参考

## 分类页面（PC Web，需登录）

| 分类 | 键 | 页面 URL（`https://www.douyin.com` 前缀） |
|------|----|------|
| 喜欢 | like | `/user/self?from_tab_name=main&showTab=like` |
| 收藏 | favorite | `/user/self?from_tab_name=main&showTab=favorite_collection` |
| 观看历史 | record | `/user/self?from_tab_name=main&showTab=record` |
| 稍后再看 | watch_later | `/user/self?from_tab_name=main&showTab=watch_later` |
| 消息/私信 | message | 首页点「消息」→ 会话列表（脚本 `im_videos.py` 处理） |

个人中心页顶部有一行入口：收藏 / 观看历史 / 稍后再看 / 我的预约，点击后 URL 的 `showTab` 变化。
`https://www.douyin.com/history`、`/collection`、`/watch_later` 等直链不存在（返回“页面不见啦”），不要用。

## DOM 结构

- 视频/图文卡片是 `<a href="/video/{aweme_id}">` 或 `<a href="//www.douyin.com/note/{aweme_id}">`。
- 卡片文本 = 点赞数 + 标题（如 `4.5万梁圣买芯片 #deepseek...`），观看历史/稍后再看还会带 `已看xx%` / `已看完` 前缀。
- 列表是**虚拟列表**：滚动会回收 DOM 节点，因此必须边滚边按 ID 合并，不能只在滚动后读一次。
- 滚动容器：包含第一张卡片的最小可滚动祖先（`scrollHeight > clientHeight + 200`）。
- 页面加载是渐进式的，新开页面约 5–10 秒才渲染出卡片；脚本用轮询等待卡片出现。

## 接口

- 个人中心分类页的数据以 SSR + 前端列表形式渲染，没有简单的一次性列表接口可直接调用；
  采集以 DOM 卡片链接为准。
- 详情统计：`GET https://www.douyin.com/aweme/v1/web/multi/aweme/detail/`，
  参数 `aweme_ids=[id1,id2,...]`（方括号、逗号、**不带引号**，需 URL 编码）。
  实测**带登录 Cookie 即可，无需 a_bogus 签名**（早期版本用过 Playwright 签名，会挂死，已移除）。
  响应 `aweme_details[]`，字段：`desc`（视频名称）、`author.nickname`、`create_time`、
  `statistics.{digg_count, comment_count, collect_count, share_count}`。
- 个人中心列表分页接口（页面自身调用，脚本未依赖）：喜欢 `https://www-hj.douyin.com/aweme/v1/web/aweme/favorite/`
  （带 `sec_user_id`、`max_cursor`、`count=18` 等参数，需页面内签名的 a_bogus；数据也可以直接从网格 DOM 采集）。
- 单条回退：`/aweme/v1/web/aweme/detail/?aweme_id=...`（dy-cli `DouyinAPIClient.get_video_detail` 已封装，
  失败时自动走 iesdouyin share API）。
- 私信：打开会话时页面自动请求 `multi/aweme/detail` 批量接口；脚本直接抓请求 URL 里的 `aweme_ids`。
  消息接口 `imapi.douyin.com` 系列（get_by_conversation / get_info_list 等）签名复杂，不走。

## 故障排查

| 现象 | 处理 |
|------|------|
| 采集到 0 条 | 抖音 A/B 换界面或页面未渲染完；重跑一次，或用 `--list-only` 观察采集数 |
| 网格一直不渲染（0 条 + 警告） | 多为验证码/风控：立即停止，冷却数小时再跑；检查页面是否出现滑块/验证码 |
| 统计全 0 | dy-cli 未登录或 Cookie 过期：先 `dy status` / `dy login` |
| 会话打不开 | 用 `--list-convs` 看会话名，再用 `--index N` 指定；注意页面等待 6 秒以上再点消息 |
| 批量详情失败 | 自动回退单条 detail；仍失败多为风控限速，稍等重跑 |
| 浏览器报错 | 确认 ego lite 已安装、`EGO_BROWSER` 路径正确、抖音网页登录态有效 |

## 规模与性能实测（2026-08）

- 收藏 205 条、观看历史 203 条、稍后再看 27 条为小列表，采集约 1–3 分钟；喜欢列表实测 **4500+ 条仍在增长**，
  完整采集需要 `--max-steps 3000 --tab-timeout 3600` 级别的预算（滚轮模式约 15–30 分钟）。
- 连续多次采集/探测会触发验证码，页面网格不再渲染；必须冷却（小时级）后再跑。
- 批量详情接口 `multi/aweme/detail` 偶尔返回部分缺失（如 40 个返回 38–39 个），脚本会自动回退单条详情；
  仍失败的通常是已删除/仅自己可见的视频，备注会标注。
- 远期优化方向：喜欢等列表的分页接口 `https://www-hj.douyin.com/aweme/v1/web/aweme/favorite/`
  （带 `sec_user_id`/`max_cursor`/`count=18` 参数）目前需要页面内签名的 `a_bogus`，带 Cookie 直调返回空列表；
  若后续破解签名，可直接分页取全量，替代慢速滚动。
