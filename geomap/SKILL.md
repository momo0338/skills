---
name: geomap
description: 制作与渲染高转化自媒体地图图说海报（如省市地铁/城轨、高校分布、品牌门店、经济对比等）。基于标准 GeoJSON、D3-geo 投影与现代 HTML/CSS 矢量卡片，自动生成 1080×2160 竖屏印刷级信息图。
---

# geomap — 自媒体地图图说海报生成技能

专为微信公众号、小红书、抖音等移动端竖屏图文设计的高转化地图信息图（Infographic）生成工具。

- **标准画幅**：1080 × 2160 竖屏比例（完美占满手机屏）。
- **专业美工系统**：
  - 经典晴空蓝/渐变背景与微投影多边形底图；
  - 顶部高对比荧光黄胶囊主标与大字重副标；
  - 城市中心悬浮“双拼色块徽章”（上半指标数、下半城市名）；
  - 底部毛玻璃亚克力 Logo 墙与作者品牌专属印章；
  - 省域散落式微型半透明防盗水印网。
- **稳健技术栈**：基于 Python + D3.js + 无头 Chromium（Playwright），彻底解决国内官方 GeoJSON 反向环序（Winding Order）导致的全球翻转问题，秒级批量出图。

---

## 快速使用

> **解释器**：必须用带 playwright 的隔离环境
> `/Users/zhugx/.workbuddy/binaries/python/envs/default/bin/python3`（系统 `python3` 缺 playwright）。
> **技能根目录**：`$HOME/.workbuddy/skills/geomap`（下文记作 `$SKILL`；该目录与 `~/src/skills/geomap` 互为同一实体，两条路径都可用）。

### 1. 命令行单次渲染

```bash
SKILL="$HOME/.workbuddy/skills/geomap"
PY="/Users/zhugx/.workbuddy/binaries/python/envs/default/bin/python3"

# 使用已有配置生成海报 (默认输出到当前目录下的 <config_name>_poster.png)
"$PY" "$SKILL/scripts/render_poster.py" --config "$SKILL/examples/jiangsu_metro.json"

# 指定输出路径与清晰度 (scale 2 = 2160x4320 4K 印刷级超清)
"$PY" "$SKILL/scripts/render_poster.py" \
  --config "$SKILL/examples/jiangsu_metro.json" \
  --output ./jiangsu_poster.png \
  --scale 2
```

### 2. 生成可视化编辑器（给非技术使用者改图）

把「模板 + GeoJSON + d3 + 某份配置」打包成**自包含编辑器 HTML**：左侧表单改标题/副标题/各市指标/颜色/偏移/排行卡/Logo，右侧 iframe 实时预览；可导出 PNG（foreignObject 栅格化，2160×4320）、下载 standalone HTML、下载/复制 JSON；改动自动存 localStorage，一键恢复默认。

```bash
"$PY" "$SKILL/scripts/build_editor.py" --config "$SKILL/examples/jiangsu_metro_onmap.json" \
  --output ./图说-编辑器.html
```

适用场景：把成图交给运营/同事自己微调文案，不再来回找 AI 改。**注意**：编辑器只内置当前省份的 GeoJSON，换省份要重新生成；导出的 PNG 是浏览器栅格化，正式发布仍以 `render_poster.py` 出图为准。

### 3. 预先下载/刷新省份地理底图

底图基于阿里云 DataV 官方高德区划边界数据（覆盖全国所有省份与直辖市），首次渲染时会自动下载并持久化缓存到 `data/` 目录中：

```bash
"$PY" "$SKILL/scripts/fetch_geojson.py" 江苏
"$PY" "$SKILL/scripts/fetch_geojson.py" 410000 --force
```

---

## 配置文件规范 (JSON Schema)

编写一个自定义专栏主题只需准备一个简单的 JSON 配置文件：

```json
{
  "province": "江苏省",
  "pill_text": "江苏省",
  "pill_bg": "#DDF32E",
  "pill_color": "#0859A1",
  "title": "已开通地铁的城市",
  "subtitle": "编号对应下方排行榜 · 淮安为有轨电车 | 截至2026年9月",
  "label_mode": "chip",
  "source_note": "数据来源：交通运输部月度运营数据速报 + 各市轨道交通运营方公开数据",
  "rank_title": "运营里程排行",
  "rank_sub": "单位：公里（含市域线）",
  "watermark_text": "满爸爱生活",
  "brand_stamp": "满爸爱生活",
  "highlights": [
    { "name": "南京市", "metric": "579km · 14条", "color": "red",    "offset": [0, 0] },
    { "name": "苏州市", "color": "orange", "offset": [12, 8] }
  ],
  "ranking": [
    { "name": "南京市", "value": 579, "value_text": "579 km", "color": "red" },
    { "name": "淮安市", "value": 20,  "value_text": "20 km",  "color": "blue", "tag": "有轨电车" }
  ],
  "logos": [
    { "name": "南京地铁", "sub": "NANJING METRO", "icon": "" }
  ]
}
```

### 参数字段说明

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- | :--- |
| `province` | string | 是 | 无 | 省份名称（如 `安徽省`、`河南省`）或行政区划代码（如 `340000`） |
| `title` | string | 是 | 无 | 主标题（如 `已开通地铁的城市`、`本科大学分布图`） |
| `pill_text` | string | 否 | `province` | 顶部胶囊内重点文本 |
| `pill_bg` | string | 否 | `#DDF32E` | 胶囊背景色（荧光柠檬黄） |
| `pill_color` | string | 否 | `#0859A1` | 胶囊文字色（深深蓝） |
| `subtitle` | string | 否 | `""` | 主标下方副标题；留空则整行隐藏 |
| `label_mode` | string | 否 | `badge` | 城市标记样式。`badge`＝数据徽章 + 引线；`chip`＝58px 编号圆点（编号 = 该市在 `ranking` 中的名次，地图零遮挡）；`onmap`＝城市名 + 指标直接标在色块内（白字深描边，零浮层，信息最全） |
| `source_note` | string | 否 | `""` | 底部 Dock 栏与品牌印章之间的数据来源注脚（小号半透明白字） |
| `ranking` | array | 否 | `[]` | 地图下方「运营里程/数量排行」亚克力卡片；留空则整卡隐藏 |
| `ranking[].name` | string | 是 | 无 | 城市名（可含未上图的城市，如仅有轨电车的城市） |
| `ranking[].value` | number | 是 | 无 | 用于计算条形长度的数值（同一口径，单位统一） |
| `ranking[].value_text` | string | 是 | 无 | 右侧显示的数值文本（如 `579 km`） |
| `ranking[].color` | string | 否 | `red` | 条形色，同 highlights 色板 |
| `ranking[].tag` | string | 否 | `""` | 名称后的小标签（如 `有轨电车`），用于标注口径差异 |
| `rank_title` / `rank_sub` | string | 否 | `运营里程排行` / `""` | 排行卡主标题与右侧单位说明 |
| `highlights` | array | 是 | `[]` | 需要高亮标记的城市列表 |
| `highlights[].name` | string | 是 | 无 | 地级市完整全称（必须与 GeoJSON 一致，如 `南京市`） |
| `highlights[].metric` | string | 否 | `""` | 徽章上半部指标文字；**越短越好**（如 `579km · 14条`，加「运营」二字会让徽章宽出一大截，苏南密集区必挤） |
| `highlights[].color` | string | 否 | `red` | 颜色标识：`red` / `orange` / `green` / `yellow` / `blue` 或自定义十六进制 Hex |
| `highlights[].offset` | [dx, dy] | 否 | `[0, 0]` | 徽章相对城市中心的像素偏移微调，解决临近城市重叠 |
| `logos` | array | 否 | `[]` | 底部亚克力 Dock 栏徽标列表 |
| `logos[].name` | string | 是 | 无 | 机构/地铁名称（如 `南京地铁`） |
| `logos[].sub` | string | 否 | `""` | 英文小标（如 `NANJING METRO`） |
| `logos[].icon` | string | 否 | `""` | 图标路径或 base64 DataURL |
| `watermark_text` | string | 否 | `""` | 地图背景散落的半透明防盗水印 |
| `brand_stamp` | string | 否 | `满爸爱生活` | 底部正中央的作者专属品牌印章 |

---

## 专栏选题与色彩规范建议

1. **层级色彩建议**：
   - 省会/核心极值点：用 `red`（`#E5251E`）
   - 第二梯队/次中心：用 `orange`（`#F37021`）
   - 普通上榜城市/跨市互联：用 `green`（`#6DB935`）
   - 未上榜城市：系统自动填充纯白底色（`#FFFFFF`）与浅灰边界
2. **专栏高频选题模板**：
   - 交通基建类：《XX省已开通高铁/地铁/单轨的城市》
   - 高教教育类：《XX省双一流/本科大学各市分布图》
   - 商业与消费：《XX省山姆会员店/盒马鲜生门店分布》、《各市万象城与顶级商场》
   - 区域经济类：《XX省各市GDP体量与千亿县分布》

---

## 城市标记排版：先量后调，禁止盲试

几十个地级市里高亮 5–7 个时，**数据徽章（约 150–180 × 83 px）远大于地级市色块的宽度**（江苏最小的地级市色块只有 140px 宽）。靠截图肉眼反复试调 offset 必然出现三种事故：徽章压在隔壁市身上、徽章飘在省外蓝底、徽章盖住别市的文字标签。正确流程是先量后调：

```bash
PY="/Users/zhugx/.workbuddy/binaries/python/envs/default/bin/python3"
"$PY" "$SKILL/scripts/measure_layout.py" --config "$SKILL/examples/jiangsu_metro.json"
"$PY" "$SKILL/scripts/measure_layout.py" --config "$SKILL/examples/jiangsu_metro.json" --json   # 程序化反算 offset
```

脚本会把页面渲染出来，一次性读出每个城市多边形的 `getBBox()`、每个标记的 `getBoundingClientRect()`、引线锚点与画板/排行卡/标题区的真实占位，并自动验收：

- **重叠**：任意两标记相交面积 = 0（擦边几 px 也要推开）
- **越界**：标记横向落在页面安全区、纵向不压排行卡、不顶到标题区
- **引线健全**：每条引线的锚点在标记之外；长度 ≤ 320px；不穿过别的标记矩形
- **归属**（信息项）：标记与自身色块的相交面积占比，chip 模式应为 ~100%

### 三种标记模式的取舍

| 模式 | 配置 | 适用 | 代价 |
| :--- | :--- | :--- | :--- |
| `badge`（默认） | 数据徽章 + `offset` 外置 + 引线 | 只有 2–4 个高亮市、或省份南北狭长有足够空白 | 密集城市群（如江苏苏南）无论怎么排都会压住邻市，只能靠引线兜底 |
| `chip` | 58px 编号圆点压在市中心，编号 = `ranking` 名次 | **密集城市群首选**，地图零遮挡 | 地图上只剩编号，数字要靠下方排行卡读 |
| `onmap` | 城市名 + `metric` 直标在色块内（白字 + 深蓝描边） | **密集城市群且想让地图一眼可读**；色块宽度 ≥ 文字宽度时用 | 文字必须全部装进自家色块，窄小色块（<130px 宽）装不下，需逐市 `offset` 微调 |

- **onmap 模式**是最"图说"的一种：地图自身就带全部数据，不依赖读者来回对照排行卡。常州/无锡/苏州这种紧邻市，把文字分别推到各自色块的不同部位（如常州偏西南、无锡偏北、苏州偏东南）即可完全错开。`offset` 此时指**文字块中心**的偏移。
- **onmap 验收口径**（用 `measure_layout.py` 或临时脚本量 `.onmap-labels text` 的 `getBBox()`）：①每条文字与**自家色块 bbox** 的归属 ≥99%；②任意两条文字不相交；③不遮压白色城市的 `city-label`；④不出自家色块 bbox（超出即说明色块太窄，改用 chip）。
- **onmap 的 metric 写法**：用 `579km·14条` 这种紧凑形式，**不要加空格和「运营」前缀**——文字宽度直接决定能不能装进色块。
- **chip 模式**下 `ranking` 就是图例：把行号与地图编号对齐（`rank_no` 已经是 1..n），`rank_sub` 写一句"地图编号 = 排行名次"即可。没有地图对应点的城市（如只有有轨电车的淮安）留在排行里、用 `tag` 标注，读者自然理解"它没有编号"。
- **chip 模式同样吃 `offset`**：无锡/常州/苏州这类紧邻城市，编号圆点会互相贴边，需要几像素 offset 错开。
- **badge 模式的引线**由模板自动绘制：城市锚点（未加 offset 的真实中心）→ 徽章中心，白色描边 7px + 城市色内线 3.2px 双层，保证在深蓝底和白色色块上都读得清；锚点画白色底圆 + 城市色实心圆。**锚点若落在徽章矩形内则自动跳过引线**，避免出现孤立圆点。

### 版面纵向预算（1080×2160，模板已按此调好）

标题区约到 y=427 → 地图带 `top:500 / height:880`（wrapper 实际 1000×800）→ 排行卡 `top:1342` → 页脚 Dock + 来源注脚 + 印章。

- **地图顶部必须留足 90px 以上**再放地图：江苏最北端（连云港尖角）很靠上，`map-wrapper.top` 若小于 500px 就会顶到副标题，出现"上面字体被遮挡"。
- **东西宽、南北扁的省份**投影后地图只占约 830px 高，页面中下部必然大片死白 → 必须用 `ranking` 排行卡填充，否则版面松散。

---

## 数据口径红线

图说是要被读者当真、被同行挑刺的内容，数字必须先核后写：

- **同图只用一套口径**。各省市轨道交通"运营里程"至少有三种数：运营方口径（含市域线）、交通运输部月度速报口径（对县级市/跨省段按所在城市拆分，如昆山、句容单列）、自媒体二次加工口径。**混用会出现"苏州 346km（运营方）＋ 无锡 110km（部委）"这种自相矛盾**。选一套，并在 `source_note` 里写明。
- **县级市/跨省段单独计数要交代**：交通运输部会把「昆山」「句容」当独立城市列（苏州 11 号线昆山段、上海 11 号线昆山段、宁句线句容段），地级市口径里它们已含在苏州/南京内，不要重复计。
- **线路条数极易过时**：新线开通前后，官方客服口径、"交通部月报"、百科词条会互不一致。凡涉"X 条线"，必须查最近一条**开通公告/地方国资委通稿**，不确定就在文案里退一步用"约"。
- **有轨电车 / SRT 虚拟轨道 ≠ 地铁**：不要混进"已开通地铁的城市"。若要收进来，用 `ranking[].tag` 明确标注（如 `有轨电车`），或单独一行说明。
- 每条硬数据至少两个独立来源（优先运营方官网 / 地方政府 / 交通运输部）交叉，冲突未决就降级为"约"。**宁可少写一个数字，不可写一个没核过的数字。**
