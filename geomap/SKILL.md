---
name: geomap
description: 制作与渲染高转化自媒体地图图说海报（如省市地铁/城轨、高校分布、品牌门店、经济对比等）。基于标准 GeoJSON、D3-geo 投影与现代 HTML/CSS 矢量卡片，自动生成 1080×2160 / 1080×1920 竖屏印刷级信息图及动态短视频。
---

# geomap — 自媒体地图图说海报与短视频生成技能

专为微信公众号、小红书、抖音等移动端竖屏图文与短视频设计的高转化地图信息图（Infographic）与动效生成工具。

- **多画幅与多模版支持**：
  - **经典长海报**（1080 × 2160，1:2）：经典晴空蓝、胶囊主标、运营里程排行榜与亚克力 Logo 墙；
  - **自媒体短视频黄牌风**（1080 × 1920，9:16）：明黄黑框告示板、暗渐变底色、全彩满幅地图、纯白字黑粗描边浮标；
  - **城市夜景大片风**（1080 × 2160，1:2）：真实城市高空航拍夜景向上羽化融合底图、顶部三组 KPI 数据胶囊、全覆盖三档色阶（万亿红/青绿/紫红）、蓝底药丸城市标与黄白特粗大字；
  - **市辖区县级细分风**（1080 × 1920，9:16）：地级市下钻至区县级细分、米白纸质感底色、区县名+数值+增速三行错落排版。
- **全行政层级下钻**：支持全国 34 省级行政区、各省下辖地级市、以及各地级市下辖区县级（如扬州市、南京市、合肥市等）官方高德 GeoJSON 自动下载与持久化缓存。
- **一键动效短视频（--video）**：自动调用 ffmpeg 生成 7 秒、30fps、带缓慢呼吸推近（Ken Burns）效果的无水印超清自媒体短视频。

---

## 快速使用

> **解释器**：必须用带 playwright 的隔离环境
> `/Users/zhugx/.workbuddy/binaries/python/envs/default/bin/python3`（系统 `python3` 缺 playwright）。
> **技能根目录**：`$HOME/.codex/skills/geomap` 或 `~/src/skills/geomap`。

### 1. 命令行渲染海报与短视频

```bash
SKILL="$HOME/.codex/skills/geomap"
PY="/Users/zhugx/.workbuddy/binaries/python/envs/default/bin/python3"

# 1. 生成经典长海报
"$PY" "$SKILL/scripts/render_poster.py" --config "$SKILL/examples/jiangsu_metro.json"

# 2. 生成自媒体短视频黄牌风 (1080x1920) + 一键生成 7秒 MP4 短视频
"$PY" "$SKILL/scripts/render_poster.py" \
  --config "$SKILL/examples/anhui_metro_shortvideo.json" \
  --output ./anhui_metro.png \
  --scale 2 \
  --video

# 3. 生成城市夜景大片风 (1080x2160)
"$PY" "$SKILL/scripts/render_poster.py" \
  --config "$SKILL/examples/jiangsu_gdp_night.json" \
  --output ./jiangsu_gdp.png \
  --scale 2 \
  --video

# 4. 生成地级市辖区县经济图 (1080x1920)
"$PY" "$SKILL/scripts/render_poster.py" \
  --config "$SKILL/examples/yangzhou_district_gdp.json" \
  --output ./yangzhou_district.png \
  --scale 2 \
  --video
```

### 2. 预先下载/刷新各级行政区划地理底图

支持全国、省份、地级市名称或 6 位标准行政代码：

```bash
"$PY" "$SKILL/scripts/fetch_geojson.py" 全国
"$PY" "$SKILL/scripts/fetch_geojson.py" 江苏省
"$PY" "$SKILL/scripts/fetch_geojson.py" 扬州市
"$PY" "$SKILL/scripts/fetch_geojson.py" 320100 --force
```

---

## 主题与配置文件规范

通过在 JSON 顶层设置 `theme` 字段自动路由对应模板：

### 1. 短视频黄牌主题 (`"theme": "short_video"`)
```json
{
  "theme": "short_video",
  "region": "安徽省",
  "header_lines": [
    "2026年",
    "安徽省已开通",
    "轨道交通的城市"
  ],
  "bg_style": "linear-gradient(135deg, #362955 0%, #463467 35%, #5e365b 70%, #75414d 100%)",
  "default_city_color": "#1EA0E6",
  "highlights": [
    { "name": "合肥市", "metric": "运营275.5公里", "color": "#E51818", "offset": [15, 30] },
    { "name": "滁州市", "metric": "运营44.86公里", "color": "#DF21B7", "offset": [30, -10] }
  ],
  "watermark_text": "@满爸爱生活"
}
```

### 2. 城市夜景大片主题 (`"theme": "city_night"`)
```json
{
  "theme": "city_night",
  "region": "江苏省",
  "title": "2025江苏十三太保GDP",
  "subtitle": "一张图看懂江苏实力！苏大强是真强！",
  "kpis": [
    { "label": "GDP总额", "value": "14.24万亿" },
    { "label": "常住人口", "value": "8518万" },
    { "label": "人均GDP", "value": "16.7万元" }
  ],
  "tiers": {
    "tier1": { "color": "#E5161C", "valClass": "yellow" },
    "tier2": { "color": "#199889", "valClass": "white" },
    "tier3": { "color": "#922761", "valClass": "white" }
  },
  "cities": [
    { "name": "苏州市", "tier": "tier1", "value": "27695亿", "offset": [85, 20] },
    { "name": "南京市", "tier": "tier1", "value": "19428亿", "offset": [-70, -20] },
    { "name": "常州市", "tier": "tier1", "value": "11158亿", "isHorizontal": true, "offset": [-30, -35] }
  ],
  "watermark_text": "@满爸爱生活"
}
```

### 4. 官方出版级标准行政地图主题 ()
基于自然资源厅/局官方标准地图制图规范开发，适用于高公信力、严肃出版物或政区地理科普。
- **制图四要素**：标准双层外图廓框、竖排黑体图名、左下角图例与比例尺方框、底部正规审图号与监制单位；
- **温润莫兰迪五色相间**：淡米黄 ()、淡粉杏 ()、淡薄荷青 ()、淡丁香粉 ()、淡天青蓝 ()；
- **铅灰外晕 (Halo)**：省界/市界外侧施加 14px 柔和立体晕渲；
- **行政中心注记**：自动为各设区市或区县标绘官方同心双圆 () 行政中心符号。



### 3. 市辖区县经济主题 (`"theme": "district"`)
```json
{
  "theme": "district",
  "region": "扬州市",
  "title": "2026年上半年扬州市\n各区县GDP",
  "subtitle": "单位:亿元",
  "source_note": "注:采用初对初、名义增速和行政区划口径。",
  "districts": [
    { "name": "邗江区", "value": "1160.01", "rate": "4.36%", "color": "#7B0D18", "offset": [0, 0] },
    { "name": "江都区", "value": "732.52", "rate": "4.08%", "color": "#E0111E", "offset": [0, 0] }
  ]
}
```



### 4. 全国省级分布模版 (`"theme": "national"`)
国家标准中国 Albers 等面积圆锥投影，支持全国 34 省级行政区分布、右下角标准《南海诸岛》附图插框与蓝白经典配色。

### 5. 官方出版级标准行政地图 (`"theme": "official_standard"`)
基于自然资源厅/局官方标准地图制图规范开发，适用于政区科普与严肃出版物：
- 标准双层外图廓线框与右上角竖排黑体图名；
- 左下角官方图例框（设区市行政中心双圆符号、省级界、设区市界、比例尺）；
- 自然资源厅标准低饱和莫兰迪五色相间：淡米黄 (`#FFFDDC`)、淡粉杏 (`#FDECD2`)、淡薄荷青 (`#E2F0E3`)、淡丁香粉 (`#FCE7F0`)、淡天青蓝 (`#E2F0FA`)；
- 省界外侧 14px 柔和铅灰立体外晕渲 (Halo)。

