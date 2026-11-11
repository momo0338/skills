---
name: job-poster-write
description: 全文海报/长图类招聘公告转排版技能。后续所有全文海报性质、长图、多卡片、图文招聘推文均使用本技能处理。通过 7 步标准流水线（抓图切段、查重、事实萃取、自动化机检、HTML组版、封面裁切、草稿推送与对账）发布为高质感微信排版。触发词：海报招聘、长图招聘、长图公告、转排版、海报排版、job-poster-write。
version: 1.1.0
---

# job-poster-write · 全文海报招聘公告转排版技能

专门针对**全文海报、长图、多卡片类招聘公告**设计的端到端生产流水线。后续所有全文海报性质的招聘公告统一由本技能承接处理。

> **核心设计哲学**：
> 1. **极简 Token 消耗**：全流程仅在「AI 读图切片 → 填充 `facts.json`」消耗大模型 Token，其余抓取、查重、机检、组版、裁图、推送与对账 100% 自动化零 Token。
> 2. **事实溯源防编造**：所有提炼数据必须附带切片原图证据；中介号强制回源；截止日期未写一律记「公告未披露」，严禁脑补推演。
> 3. **无缝视觉拼合**：单张超长图按 2000px 纵向切段 + 60px 重叠防断字；HTML 段间使用 `-1px` 负边距抵消亚像素缝隙，消除微信客户端中的白线接缝。

---

## 流程概览（标准七步法）

```dot
digraph pipeline {
    rankdir=LR;
    node [shape=box, style="rounded,filled", fillcolor="#f9f9f9"];
    fetch [label="① fetch\n抓图切段/形态判断\n(零Token)", fillcolor="#e1f5fe"];
    preflight [label="② preflight\n数据库查重\n(零Token)", fillcolor="#e1f5fe"];
    facts [label="③ AI 读图\n填 facts.json\n(唯一 Token 步)", fillcolor="#fff9c4"];
    check [label="④ facts-check\n格式/敏感词机检\n(零Token)", fillcolor="#e1f5fe"];
    gen [label="⑤ gen + cover\n组版+封面裁切\n(零Token)", fillcolor="#e1f5fe"];
    push [label="⑥ push\n推送微信草稿箱\n(零Token)", fillcolor="#e1f5fe"];
    post [label="⑦ postprocess\n交付小结+写日志\n(零Token)", fillcolor="#e1f5fe"];

    fetch -> preflight -> facts -> check -> gen -> push -> post;
}
```

> **本技能自足**：开工只需读本文件，⛔ 无需通读项目 `.workbuddy/memory/` 三本分册。分册特有的判重真源、hook 落库自检、三检路径、封面机位已全部并入下文（见 ②/⑤/⑥ 与「环境与解释器」）。

### 单篇收敛序列（2026-11-10 提速版 v2，目标 ≤ 55 轮 / ≤ 9 分钟）

```
fetch → 查重(1次合并) → scan_images 摸底(1次) → 读图(只读 hot 组) → facts_len 批量量字数(1次)
      → facts 一次写对 → gen(自动带折行预检) → cover(目检 1 次) → 三检(1 条命令)
      → preview(只看首屏/表格屏/末屏) → push → draft/get 回读 + thumb_url 目检 → postprocess
```

1. **前置探路合并**：`--help` / `--facts-help` / 历史 `facts.json` 样本 / `REQUIRED` 一次批量取齐，别拆成 8~10 次 Bash。
2. **看图先摸底再精读**（2026-11-10 新增）：`fetch` 后先跑 `python3 scripts/scan_images.py <work_dir> --ocr`，拿到每张图的「行数 + 首行」。它会把纯 slogan/END/关注引导图标为「可跳过」——2026-11-10 中工国际篇 12 张里 3 张属此类，白读了 3 轮（≈30s）。**表格类图 OCR 会串行错乱，仍须 ViewImage 逐字核**，摸底只用来筛掉无信息量的图。
3. **字数一次量完**（2026-11-10 新增）：`title`/`digest` 不要写一版量一版。把所有候选丢给 `python3 scripts/facts_len.py --digest <<'EOF' … EOF`，一次输出每个候选的字数与达标判定，直接挑达标的那个。当天多篇都是「写→量→压→再量」3~4 轮（≈30~40s），这一步可压到 1 轮。
4. **gen 自带折行预检**（2026-11-10 新增）：`gen` 完会自动打印 `[折行预检]`，列出会「单字成行」的格子并给出建议列宽。**看到 ⛔ 就改 widths 再 gen，不要等 preview 逐屏找**。当天 8 篇里 6 篇踩这个坑，每次返工约 4 步往返。
5. **预览只看关键屏**：首屏（划重点+四宫格）、含表格的屏、末屏。中间纯海报原图段只需确认无白线重影，不必逐屏目检。

> ⏱️ **耗时结构（2026-11-10 实测 8 篇）**：墙钟 ≈ 轮次 × 10s，工具执行只占 11%。**提速的唯一杠杆是减轮次，不是优化命令**。当天后半段稳定在 8.6~10.4 分钟/篇。

---

## 环境与解释器（零 Token 环节统一口径）

| 项 | 固定值 | 踩坑 |
|---|---|---|
| 解释器 | **`/usr/local/bin/python3`** | 系统 `python3` 无 PIL，`push`/`preview` 会 `ModuleNotFoundError`；它同时带 bs4 + playwright，两个检测脚本也用它跑 |
| 判重库 | **`/Users/zhugx/src/mashangzhiye/data/内容流水线.db`** | 建议 `export PIPELINE_DB=...` 显式传入；`draft_sync.py` 的 DEFAULT_DB 曾指向已不存在的 `工具/` 目录，导致 hook 长期空转 |
| 账号 | **`--profile mashang`** | `wx_draft.py` 默认是 manba，推错即事故 |
| 三检脚本 | `~/src/skills/mp-html/scripts/wx_dialect_check.py`<br>`~/src/skills/mp-html/scripts/wx_overflow_check.py` | 溢出须 320/360/375/414/677px 五档全过；另查 mmbiz 外链 = 0 |
| 工作目录 | `cd "<工作区根目录>"` 后再跑 `gen`/`cover`/`push` | `line_dir` 写相对路径时以**运行时的 CWD** 为基准，不是技能目录；写绝对路径可免去此约束 |

---

## 命令清单与执行步骤

脚本主入口：`scripts/job_poster_pipeline.py`。`--facts-help` 也用主脚本，⛔ `scripts/wx_article_pipeline.py` 软链已失效（调用会报 `can't open file`）。

### ① 抓取与形态探测（`fetch`）
调用底层 `mp-save` 引擎抓取微信文章、提取高清原图（`/0?` 通道），并对高分辨率长图自动按 2000px 切段（带 60px 重叠防断字）：
```bash
python3 scripts/job_poster_pipeline.py fetch "<微信推文URL>" --dir /tmp/wxwork_<单位名>
```
产出物：
- `meta.json`：原文元数据、发布者、形态判读（`long` / `multi` / `text`）
- `images/`：高清原图
- `images/segs/`：2000px 长图切片（供多模态 AI 读图提取）

### ② 查重校验（`preflight`）
校验单位是否已写过或已发布；支持传入可选 SQLite 数据库（`--db` 参数或 `PIPELINE_DB` 环境变量）查重，未指定时跳过本地库查重：
```bash
python3 scripts/job_poster_pipeline.py preflight "<单位全称或简称>" [--db <path/to.db>]
```

**🔴 判重真源与状态陷阱（2026-11-04 并入，原在分册）**
- **只用 URL 锚定**，⛔ 弃用标题匹配。真源 = db **`drafts` ∪ `articles`**，SQL 直查最可靠（一次查完）：
  ```sql
  -- 微信 URL 与官网 URL 双向查：同一公告常有两个锚点，只查一个会漏判
  select id,title,source_url,status from drafts   where source_url like '%<锚点>%';
  select id,published_title,source_url from articles where source_url like '%<锚点>%';
  ```
  注意 `articles` 用 `published_title`（无 `title` 列）。同时补一次 `%单位名%` LIKE 作兜底，但**命中必须逐条打开看 `unit_name` 是否同一法人**：2026-11-04 徽商集团篇，「徽商银行2027全球校招」是银行主体，与集团不同法人 ⇒ 典型关键词假阳性，不判死。
- **同单位可有分批/分级公告**（分行 vs 总行、子公司 vs 集团），⛔ 别因「写过这家」判死，按 URL + 公告版本锚定。
- 🔴 **`status` 不可信**：`published` 可能是 reconcile 误标（判真发表只认 `articles.published_title`）；`draft` 也可能是已被外部删除的僵尸行。判活一律 `wx_draft.py --profile mashang get --media-id <ID>` ＋ 翻完草稿箱；报 40007 且全箱无此文 = 真删，走接替 SOP（推新稿 → 旧行 `discarded` → 写 `audit_log`）。
- **判重命中后必须回读草稿存活**，同址 + db 有记录 ≠ 草稿还在。

### ③ AI 读图并填充 `facts.json`
AI 读取切片图片（`images/segs/*.png`），提取硬核事实并写入工作目录下的 `facts.json`（字段模板详见下文）。

### ④ 自动化机检断言（`facts-check`）
零 Token 校验必填字段、字数长度限制、极限词溯源断言及回源纪律：
```bash
python3 scripts/job_poster_pipeline.py facts-check /tmp/wxwork_<单位名>/facts.json
```
- **标题**：`title` 长度必须 ≤ 64 字符
- **摘要**：`digest` 长度必须 ≤ 120 字符
- **词汇核验**：出现“正式编制/直签/第一/最高/落户”等词汇必须在 `raw_evidence` 中附带证据
- **回源纪律**：非官方系账号（聚合号/中介号）推文严禁作为源，必须指回官网公告

### ⑤ 组版与封面制作（`gen` + `cover`）
```bash
# 生成排版 HTML（自动应用品牌色、三宫格与负边距切片拼合）
python3 scripts/job_poster_pipeline.py gen /tmp/wxwork_<单位名>/facts.json

# 裁剪长图顶部（默认 0~460px）并缩放到 900x383 标准微信大图封面
# 推荐用法：直接传入 facts.json，自动从 facts 提取源图、slug 与落点目录，杜绝路径分裂
python3 scripts/job_poster_pipeline.py cover /tmp/wxwork_<单位名>/facts.json

# ⭐ 竖排/单行大标题海报首选：--auto 自动定位标题块（2026-11-04 新增）
# 原理：macOS Vision OCR 探测顶部 1600px，按「行间距断档」找标题块底部，
#      装得下就直裁，装不下就「完整标题 + 高斯模糊拉伸铺底 + 居中实图」合成
python3 scripts/job_poster_pipeline.py cover /tmp/wxwork_<单位名>/facts.json --auto

# 也支持指定单张图片与自定义裁剪范围（--auto 与 --top/--bottom 互斥）：
# python3 scripts/job_poster_pipeline.py cover /tmp/wxwork_<单位名>/images/img_01.png --slug "<slug>" [--line-dir "待发布目录"] [--top 0 --bottom 460]
```

**🔴 `--auto` 适用边界（2026-11-04 徽商集团篇实测打回，务必先判形态）**

| 海报顶部形态 | 用什么 | 原因 |
|---|---|---|
| 竖排大标题 / 单行横标题，标题块连续 | `cover --auto` | 行间距断档判定准，一次成型（林氏家居篇 H=747 零切字） |
| **顶部有 logo 行 + 大面积插画 + 双行横排大标题** | **手工严格 2.35:1 横窗直裁** | OCR 会把 **logo 行误判成标题块**（徽商篇判 H=260 → 直裁 →「徽聚英才」刚露头被切断） |

横窗直裁做法（一次到位，别生成 5 个候选再目检）：
```python
from PIL import Image
im = Image.open('/tmp/wxwork_<单位名>/images/img_02.png').convert('RGB')
# 750 宽 → 严格 2.35:1 取高 319；窗口须含完整双行大标题 + 单位/届别横条
c = im.crop((0, 181, 750, 500))          # 本篇实测值，换稿按实际 y 调整
assert c.size == (750, 319)
c.resize((900, 383), Image.LANCZOS).save('<交付目录>/<date_tag>-<slug>-长图转排版-封面.png')
```
- 备选方案都更差：**高斯模糊铺底**有贴图感、**按行边缘中位色延展**有明显色块断层；只有无拼接的横窗直裁零切字、零变形、零痕迹。
- **不管用哪种方式，封面必须目检 1 次**（一次 ViewImage，别省）；`thumb_media_id` 是临时素材，`get_material` 取不到，本地文件不作验收依据。
- 封面验收只认服务端 `draft/get` 五项硬校验；`/tmp/wxrun_<profile>/zj_cover.jpg` 是全 profile 共享路径，并行推稿会互相覆盖。

### ⑤-b 排版预览（`preview`，2026-11-04 新增）
一条命令渲染 HTML 并按 2400px 等分成若干张图，替代「临时写 playwright 脚本 + 反复截图」：
```bash
python3 scripts/job_poster_pipeline.py preview "2027年校园招聘/待发布/xxx-长图转排版.html" [--step 2400] [--outdir /tmp] [--width 375]
# 实测：4.5s 出 7 张（全页 7369px），之前手写脚本每次 25~40s × 多轮
```

### ⑤-c 本地 OCR 预抽（`vision_ocr.swift`）
macOS Vision 框架零 token OCR，带 bbox（归一化、原点左下）与置信度：
```bash
swift scripts/vision_ocr.swift <图片> [--json]     # 2000px 切片约 0.2-0.3s/段
```
⚠️ **定位是「辅助」不是「替代」**：对正文段落识别近乎逐字正确，但**海报表格/图形化排版会串行错乱**
（实测 5 段 103 行中，四阶段成长路径被拆成「子ン阶段」「（打滕专V实力」这类碎片）。
⇒ 可用于「判重/是否过期/有无截止日期」的粗筛，以及 `cover --auto` 的标题定位；
⛔ 不可用 OCR 文本直接填 `facts.json` 的表格类硬信息，仍须 AI 读图定版。
⚠️ 整张 9000px+ 长图直接 OCR 会被降采样严重漏检（9149px 只出 28 行），**必须先按 2000px 切段**。

### ⑤-d 发布切片重切（`reslice`，发布前必跑 ⚠️）
`fetch` 的 `images/segs/*.png` 是**给 AI 读图用的**，每段尾部多带 60px 重叠（防整行切断）。直接塞进 `stack_b64_imgs` 发布，接缝会**重复约 22px 内容**（375px 视图），表现为文字重影/断层。发布前一律重切：
```bash
python3 scripts/job_poster_pipeline.py reslice /tmp/wxwork_<单位名> --facts /tmp/wxwork_<单位名>/facts.json
# 产出 images/publish/seg_01..N.jpg（严格 step 无重叠 + JPEG q86），并自动回写 facts 的 stack_b64_imgs
# 只丢弃旧切片（images/segs、images/publish），二维码卡片等附加图会保留
```
自检口径：`preview` 出来的全页高度，重切后应比用 fetch 原始段**矮约 22px × 接缝数**。

### ⑤-e 推稿前三检（必跑，2026-11-04 并入）
```bash
H="<交付目录>/<date_tag>-<slug>-长图转排版.html"
/usr/local/bin/python3 ~/src/skills/mp-html/scripts/wx_dialect_check.py "$H"     # 方言：section/p/img/style 统计，禁空 span 色块
/usr/local/bin/python3 ~/src/skills/mp-html/scripts/wx_overflow_check.py "$H"    # 320/360/375/414/677px 五档零溢出
# 第三检：mmbiz 外链 = 0（正文图一律 base64；长图走 stack_b64_imgs 天然无此坑）
python3 -c "import re;s=open('$H',encoding='utf-8').read();print('外链',len(re.findall(r'(?:src|href)=[\"\']https?://',s)),'| mmbiz',s.count('mmbiz.qpic'))"
```
其余口径：表格 `widths` 传**纯数字** `[21,15,19,45]`（写 `"24%"` 会渲染成 `24%%` 被微信清掉列宽）；三宫格每格小字 ≤7 字；`preview` 目检接缝连续、末尾收尾完整、CTA 与来源小字齐全。

### ⑤-f 扫码投递卡（`qr_card`，2026-11-05 朱总定标准 🔴）

**规则：原文提供二维码投递渠道的，必须把二维码从海报里「拎出来」，单独渲染成一张卡片，放进投递信息所在小节**；⛔ 不许只让二维码躺在文末长图里让读者自己找。

- 用 `Layout.qr_card()`（`mp-html/scripts/layout_kit.py`），已内建、不用再手写 HTML。
- 卡片结构：`标题（粗）+ 副题 + 二维码 + 脚注1（加粗）+ 脚注2（浅灰）`，浅底圆角、居中、`max-width:270px`（保证 320px 视口零溢出）。
- 二维码必须以 **base64 data URI** 内联（外链会被防盗链吞掉，且违反「外链=0」）。
- 原文长图/卡片流**照旧完整保留**在下方，卡片只是把关键入口前置，⛔ 不得因此裁掉原图里的二维码。
- 位置：写在 facts 的 `sections[]` 里任一小节内（如「投递通道」），该小节末尾按序渲染；也可作为顶层 `qr_card` 兜底渲染在 sections 之后。

```jsonc
// 写在某个 section 内部：
{
  "title": "投递通道",
  "paras": ["PC端：https://xxx", "手机端：扫描下方二维码投递。"],
  "qr_card": {
    "title": "扫码一键投递",                 // 卡内主标题
    "sub": "某某集团2027校园招聘",            // 卡内副题（可空）
    "img": "/tmp/wxwork_<单位名>/images/qr_apply.png",  // 本地路径，gen 自动转 base64
    "foot1": "报名 即日起至 11月22日 24:00 截止",        // 加粗脚注（截止/关键信息）
    "foot2": "更多信息：campus.51job.com/xxx",           // 浅灰脚注（网址/补充，可空）
    "qr_size": 176                                        // 可选，默认 176
  }
}
```

**二维码提取口径**（别截图、别整张塞）：定位海报里的二维码区域 → 裁到二维码白边为止 → `NEAREST` 放大 3 倍（保持模块锐利，别用 LANCZOS 磨边）→ 存 PNG。自动化做法是扫「近白像素行/列」求 bbox（见本轮 `天津农商银行` 实例：375×312 的卡片里 QR bbox = x125–326 / y6–206，裁出 202×200，放大 3 倍到 606×603）。裁完**必须目检**：三个定位角完整、无紫底/文字残留。

`facts-check` 已加软提示：正文出现「扫码／二维码」但 `facts` 里没有 `qr_card` 时打印 ⚠️ 提醒（不 FATAL，兼容存量稿）。

### ⑤-g 两张速查表（2026-11-10 实测校准，省掉最常见的两类返工）

#### 表一：表格列宽速查（375px 视口）

参数取自 `layout_kit.py` 实测：`font-size:12.5px`、`td padding:5px 4px`、`table-layout:fixed`、**容器可用宽 345px**（375 视口减正文左右各 15px）。用 9 篇的真实边界反验，全部吻合。

| 首列要装 N 个汉字 | 最小列宽 | 常见踩坑 |
|---|---|---|
| 5 字 | 19% | 16% 会折出单字（「本科及以上」→「上」） |
| 7 字 | 27% | 26% 边界、24% 必折 |
| 8 字 | 30% | 28% 会折出单字（「城市更新与运营类」→「类」） |
| 9 字 | 34% | 30% 折 |
| ≥10 字 | 建议改 3 列或拆词 | — |

⚠️ **全角斜杠/顿号比汉字略宽**：「线上笔试／测试」7 字在 26% 会折出「试」，30% 才稳；「六险一金、落户落档、人才引进补贴、带薪年假」21 字在 76% 会折出「假」，78% 才够。**含全角标点的格子按「字数 +1」估算**。

经验值：**内容列约 20 字/行**（76% 宽）。超过就折行，**若折完末行只剩 1 个字，宁可重新归类也不要硬塞**（当天薪酬表 22 字 → 折出「贴」，改成 5 行分类后全单行）。

⛔ **4 列在 375px 下极挤**：当天的「岗位｜学历｜地点｜专业」4 列方案，学历列 16% 直接折出「上」。正确做法是合并成「学历 · 地点」一列改 3 列（`[34,20,46]`）。

`gen` 已内置预检，会直接打印：
```
[折行预检] 375px 视口 | 检查 108 格 | 孤字 0 | 待确认 1 | 折行 0
  ⚠️ [中国中元岗位] 第10行第2列 "…安全科学与工程类、" 列宽50% 末行约1.0字（边缘值…以 preview 为准）
```
- `⛔ 孤字` = 确定会掉出一个字，**必须改**
- `⚠️ 待确认` = 边缘值（估算误差 ±0.5 字），preview 时留意一眼
- 加 `--all` 可看全部普通折行；加 `--strict` 有孤字则 exit 1

#### 表二：二维码裁切策略（按底色选方法，别反复试）

| 海报底色 | 定位方法 | 代码要点 |
|---|---|---|
| 浅底 / 白底 | 暗像素 bbox | `g<80` 求 `ys.min/max`，取 bbox 后外扩 12~14% 白静区 |
| **深底**（深蓝/黑） | **亮框连通域** | 暗像素会把整块背景算进去（当天的 260×260 全区域）；改用 `g>185` + `connectedComponentsWithStats` 找宽高 >100 的亮块，得到真实码区 |
| 彩色艺术码 / 中心带 logo | 先 Vision 后 cv2 | `swift scripts/vision_barcode.swift <img>` 输出 `VAL=… CONF=…`，双码会逐行列出 |

**顺序建议**：先 `cv2.QRCodeDetector().detectAndDecodeMulti`（快），空结果再上 Vision。当天 6 篇里 2 篇 cv2 解不出（内蒙古能源的蓝色点阵码、中工国际的左码），Vision 均 1.0 置信度解出。

裁完**必须目检**：三定位角完整、四周纯白静区、无底色残留。解码复核也必做（`vision_barcode.swift` 或 cv2 再解一次）。

### ⑥ 推送到公众号草稿箱（`push`）
内置自动前置触发 `facts-check` 机检，调用 `mp-publish` 推送至微信公众号草稿箱：
```bash
python3 scripts/job_poster_pipeline.py push /tmp/wxwork_<单位名>/facts.json [--profile mashang]

# ♻️ 改错/重排不新增草稿：原位更新指定历史草稿（2026-11-04 新增透传）
python3 scripts/job_poster_pipeline.py push /tmp/wxwork_<单位名>/facts.json --update-media-id <旧 media_id>
```

**🔴 推送后必查两件事（判重真源靠它，2026-11-04 并入）**
1. 输出里有没有 **`[hook] draft_ctl: ...成功`**。没有就说明 hook 空转，`drafts` 表不会自动登记 —— 手工补：
   ```sql
   insert or replace into drafts(media_id,title,source_url,temp_url,status,synced_at)
   values('<media_id>','<标题>','<源URL>','<临时链接>','draft',datetime('now'));
   ```
   （`media_id` 是唯一键，幂等。）`content_ctl` 报「未匹配到流水线稿件，跳过」属正常，不必处理。
2. `select id,title,status from drafts where media_id='<media_id>'` 有 1 行，且 `audit_log` 有 `hook_insert` 记录。

**服务端回读验收（唯一准绳）**：
```bash
python3 ~/.dsh/skills/mp-publish/scripts/wx_draft.py get --profile mashang --media-id <media_id>
```
核对五项：标题 / 摘要长度 / 正文字符数与 `img` 数 / `section` 容器数 / **空 style=0**，并确认 `content_source_url` 与 `thumb_media_id` 正确。本地封面 PNG 不作依据。

### ⑦ 交付小结与日志（`postprocess`）
输出最终交付卡片与概要信息，在 facts 目录下持久化 `pipeline_summary.json`，并支持可选追加到指定日志文件：
```bash
python3 scripts/job_poster_pipeline.py postprocess /tmp/wxwork_<单位名>/facts.json [--log <path/to.log>]
```

> ℹ️ **本技能的 `postprocess` 是精简版**：只产出 `pipeline_summary.json` ＋可选日志追加，**不写单位总表、不做对账同步**。
> 🛑 **2026-11-04 朱总裁定：`单位与招聘信息总表.xlsx` 及「总表回填／`units` 写入／报备环境缺口」整套要求已完全废弃。** 本技能不回填、不报备；判重只认 db `drafts` ∪ `articles`。
> （旧版此处称「总表正本缺失、仅存 10-15 备份」并要求向朱总报备，系只查工作区根目录造成的误判——正本一直在 `/Users/zhugx/src/mashang/单位与招聘信息总表.xlsx`。该 xlsx 现已废弃。该条已删除，勿再恢复。）

---

## `facts.json` 规范字典

运行 `python3 scripts/job_poster_pipeline.py --facts-help` 可查看完整定义：

```json
{
  "source_url": "https://xiaozhao.eebbk.com/",
  "source_kind": "official_account",
  "publisher": "发布方公众号名称（转发号也如实填）",
  "title_official": "官方原标题",
  "publish_date": "2026-11-04",
  "company": "单位简称（标题用）",
  "company_full": "单位全称（可空）",
  "line_dir": "/Users/zhugx/codeup/obsidian/03-工作记录/码上职业/2027年校园招聘/待发布",
  "brand": "#f26722",
  "brand_dark": "#d4541a",
  "date_tag": "2026-11-04",
  "slug": "单位简称-校招",
  "deadline": "2026-11-30 或 公告未披露（二选一，严禁招满即止/日期推演）",
  "audience": "2027届国内外应届毕业生",
  "positions": "研发工程师、管培生等若干岗",
  "locations": "南京、北京、上海",
  "apply": "网申链接或指定投递方式",
  "title": "推文标题（≤64字）",
  "digest": "推文摘要（目标 115~119 字，硬上限 120）",

  "highlight_sub": "划重点卡副题【必填！gen 读 f['highlight_sub']，缺则 KeyError】",
  "highlight_items": ["提炼要点1", "提炼要点2", "提炼要点3", "提炼要点4"],

  "grid": [
    ["2027届", "本硕博应届"],
    ["11类", "热招工程师"],
    ["东莞", "研发制造双园区"],
    ["招满即止", "即日起投递"]
  ],

  "work_dir": "/tmp/wxwork_<单位名>【必填！gen 读 f['work_dir'] 取 meta.json/图片，缺则 KeyError】",
  "body_imgs": [2, 3, 4],

  "stack_b64_imgs": ["/tmp/wxwork_<单位名>/images/publish/seg_01.jpg"],
  "raw_evidence": "长图原文关键句摘抄...",
  "source_note": "信息来源：…官方网申平台；原推文由…转发，码上职业仅作排版整理，具体以官方页面为准。"
}
```

> ⚠️ **2026-11-04 修正（本篇小天才稿实测打回）——以下必须与脚本一致，否则 gen/facts-check 反复报错：**
>
> | 字段 | 正确格式 | 脚本依据 | 常见错误 |
> |---|---|---|---|
> | `grid` | **`[["大字","小字"], ...]` 元组数组**（脚本 `quad_grid([tuple(g) for g in grid])`） | gen L274 | 写成 `[{label,value}]` dict 数组 → 报错 |
> | `highlight_sub` | 必填字符串 | gen L272 `f['highlight_sub']` | 漏填 → KeyError |
> | `work_dir` | 必填，= fetch 的 `--dir` 工作目录绝对路径 | gen L286 `f['work_dir']` | 漏填 → KeyError |
> | `body_imgs` | **图片 idx 整数列表**（对应 meta.json `images[].idx`），非路径 | gen L288-292 `url_by_idx[n]` | 填路径 → KeyError |
> | `deadline` | 只能是含年份日期（如 `2026-11-13`）或 `"公告未披露"` | facts-check L247 | 填「招满即止」→ FATAL |
> | `source_url` | 转发号必须回源到官方平台 URL，并配 `source_kind` | facts-check L223+ | 直接用转发推文链接 → FATAL 回源纪律 |
> | `line_dir` | **绝对路径，或在工作区根目录运行时写相对路径**（脚本 `CWD=os.getcwd()`，相对基准是运行时目录，非 skill 目录） | gen L321 | 在 skill 目录里跑 + 写相对路径 → 落到错误位置 |

---

### 出稿前 facts 自检清单（进入 `facts-check` 前逐项核对，可省 80% 来回试错）

1. [ ] `digest` 长度 **115~119** —— 用 `python3 scripts/facts_len.py --digest <<'EOF' … EOF` 一次量完所有候选（别写一版量一版）
2. [ ] `grid` 是 **`[大字,小字]` 元组 ×3~4**，不是 dict
3. [ ] `highlight_sub` 已填
4. [ ] `work_dir` 已填（= fetch 的 `--dir`）
5. [ ] `body_imgs` 是 **idx 整数列表**（不是路径）
6. [ ] `deadline` 是日期或 `公告未披露`（无「招满即止」）
7. [ ] `source_url` 已回源到官方平台 + `source_kind` 正确
8. [ ] **原文有二维码投递渠道 ⇒ 已在投递小节内配 `qr_card`（图已提取、目检干净）；⛔ 不许只留在文末原图里**（2026-11-05 朱总定）
9. [ ] **`source_note` ≤50 字**、不含完整 URL、不含回源过程（2026-11-10 定，铁律 8）
10. [ ] `line_dir` 用绝对路径，或确保 `gen`/`cover`/`push` 都在**工作区根目录**执行（相对路径基准 = 运行时 CWD）
11. [ ] `gen` 输出的 `[折行预检]` **没有 ⛔ 孤字**（有就先改 widths 再 gen，别等 preview）

---

## 铁律与避坑指南

1. **接缝白线问题**：
   长图切片在移动端拼接时，由于屏幕缩放亚像素计算容易出现细微白线。脚本已固化：同一 section 容纳所有切片，段间应用 `-1px` 负边距，且必须清除行高（`line-height:0; font-size:0;`），**严禁加圆角 `border-radius`**（圆角会在接缝处露底）。
2. **防切断文字**：
   切片步长 2000px，必须附加 60px 垂直重叠（overlap），确保没有文字刚好被整行切断而丢失信息。
3. **回源纪律**：
   中介转载号（如求职汇等）严禁作为 source_url；必须核查官方公众号、官网或官方网申平台，溯源真实链接。
4. **截止时间严禁推演**：
   `deadline` 字段**只能是**含年份的日期（如 `2026-11-13`）或 **`公告未披露`**，绝不能主观臆测。
   ⚠️ 若海报原文写的是「招满即止 / 长期有效」这类**无固定日期**的表述：
   - `deadline` 字段填 **`公告未披露`**（通过 facts-check；填 `招满即止` 会被硬校验 **FATAL**）；
   - 「招满即止」作为**原文事实**写进 `sections` / `raw_evidence` / `digest`（原文确有依据，不冲突）；
   - ⛔ 切勿把 `招满即止` 塞进 `deadline` 字段。
5. **⛔ 正文不许出现「元描述」（2026-11-04 朱总打回）**：
   「海报给出的五个数字」「海报原文表述」「原文（长图，共 N 段）」「长图已按 2000px 分段并保留重叠」这类描述**载体与制作过程**的句子，一律不进正文——读者只关心信息本身，不关心它印在海报上还是被切成了几段。
   正确写法：小节标题写「关于林氏家居：五个关键数字」；表头写「原文表述」「历练内容」；`original_title` 只写「招聘海报原文」；`original_note` 只写「以下为…海报原文，原样收录、未作改动，长图较长可点击放大逐段查看」。
   规则边界：缺口仍按纪律写「公告未披露」，但**不要再挂一句「海报未标注」**；开头 `intro` 只留 gen 自动生成的「依据：…原文，码上职业仅做排版整理，未改动原文表述」，转载/回源披露统一放文末 `source_note`，别在开头再念一遍。
6. **摘要要写满，别浪费展示位（SEO）**：
   `digest` 目标 **115~119 字**（硬上限 120）。四必含（截止/门槛/入口/差异）之外，再塞：公司量级（亚洲500强、连续 N 年行业 NO.1）、培养机制（18 个月四阶段）、工作地、岗位大类关键词。⚠️ 80 字以下属于浪费——本篇初稿 87 字被朱总指出「应该写满」。
   自检：`facts-check` 会打印 digest 长度，落在 115~119 才算过关（不要卡 120，留一个字的余地）。
7. **有二维码投递渠道 ⇒ 必须独立成卡（2026-11-05 朱总定，不再逐篇自由发挥）**：
   原文给了扫码投递入口的，一律按 ⑤-f 用 `Layout.qr_card()` 渲染「扫码投递卡」放进投递小节，二维码 base64 内联、裁干净、目检过。⛔ 不许只把二维码留在文末长图里。
   历史教训：`layout_kit` 早期**没有**二维码卡片组件，导致同样是有码的公告，有的稿子手工做了卡、有的直接没做（湖北港口做了、山东港口没做），完全取决于当次是否临时手写——这是「为什么有的这样有的不这样」的根因。组件现已内建，别再手搓，也别再漏。
8. **来源小字必须一次写短（2026-11-10 定，单篇最大时间黑洞）**：
   `source_note` 目标 **≤50 字**，硬上限 60。写法固定为「码上职业仅作排版整理，以官方页面为准。来源：<官方平台简称>，<发布号>发布。」或「…来源：<官方>。「<转发号>」转发。」
   ⛔ 不许塞完整 URL（长网址在 375px 必然断词）；⛔ 不许写回源过程（`pcs_token`／`chksm`／「解码得」这类）。
   **教训**：2026-11-10 中济通篇 `source_note` 被改了 **12 次**（`gen` 跑 14 次、`preview` 14 次），连出「转／发」「整／理」「准。」「码上／职业」「官网公／告」六七处折词，单篇吃掉 31 分钟——当天其他篇只要 9 分钟。根因就是一次只删一两个字，把孤字推到下一行，来回打转。
   **正确姿势**：一次压到 50 字内，品牌名（码上职业）与专有名词（转发号全称）**放在句首**，让它们整体占行首，不在中间被折断。
   `facts-check` 现已对 >60 字、含长 URL 两种情况打印 ⚠️ 提醒。

---

## 修订记录

| 日期 | 版本 | 内容 |
|---|---|---|
| 2026-11-10 | 1.3.0 | **按「单篇 10 分钟」实测复盘做的四项提速**（当天 8 篇：墙钟 123.9 分钟、628 轮、看图 194 次；工具执行仅占 11%，**瓶颈是往返轮次 ≈10s/轮**）：① 新增 `scripts/wx_cell_wrap_check.py` 表格折行预检（参数从 `layout_kit.py` 的 12.5px/4px/table-layout:fixed 反推，并用当天四组实测边界校验；`gen` 后自动跑，直接报「哪格会掉单字 + 建议列宽」。回归验证：把中工国际篇还原成当时的 4 列 16% 错误版，能精确报出「本科及以上→上」）；② 新增 `scripts/facts_len.py` 批量量字数（标题/摘要候选一次量完，省 3~4 轮）；③ 新增 `scripts/scan_images.py` 图片摸底（OCR 筛掉 slogan/END/引导图，中工国际篇 12 张里筛出 3 张不必读）；④ `scripts/vision_barcode.swift` 从 `/tmp` 收编进技能（cv2 解不出的彩色艺术码/Vision 一次成功，当天 2 篇用到）；⑤ `facts-check` 新增 `source_note` >60 字、含长 URL 两条 ⚠️；⑥ 新增 ⑤-g「两张速查表」（表格列宽 + 二维码按底色选裁法）、铁律第 8 条「来源小字必须一次写短」、自检清单补至 11 项；⑦ 顺手修自检清单重复的「8.」编号。**根因数据**：中济通篇 `source_note` 改 12 次、`gen` 跑 14 次，单篇 31 分钟（其他篇 9 分钟）。 |
| 2026-11-05 | 1.2.0 | **扫码投递卡标准化（朱总对数发现「有的做卡、有的不做」）**：① `mp-html/scripts/layout_kit.py` 新增 `Layout.qr_card()` 组件（浅底圆角、居中、`max-width:270px` 保证 320px 零溢出）；② `gen` 支持 `sections[].qr_card` / 顶层 `qr_card`，图片自动转 base64 内联，无需再手写卡片 HTML；③ `facts-check` 加软提示（正文含「扫码/二维码」但无 `qr_card` ⇒ ⚠️）；④ 新增 ⑤-f 章节写明提取口径（近白像素求 bbox → NEAREST 3× → 目检定位角）；⑤ 铁律第 7 条与出稿自检第 8 项固化该要求。根因：组件此前不存在，各篇靠临时手搓，故湖北港口有卡、山东港口无卡。 |
| 2026-11-04 | 1.1.0 | **技能自足化（朱总指出「应该只用技能就行了」）**：把原需查三本项目分册的 4 条并入本文件 —— ① 判重真源＝`drafts`∪`articles` URL 锚定、`status` 陷阱、关键词排伪（②）；② 三检脚本路径与五档溢出、`/usr/local/bin/python3`（「环境与解释器」＋⑤-e）；③ push 后 hook 落库自检与服务端回读五项（⑥）；④ 封面 `--auto` 适用边界与 2.35:1 横窗直裁（⑤）。另加「单篇收敛序列」提速（目标 ≤20 次工具调用）、`postprocess` 精简版与总表正本缺失说明、硬数字放大核对。顺手修两处文档 bug：`--facts-help` 原指向已失效的 `wx_article_pipeline.py`；`line_dir` 原误写「必须绝对路径／脚本 CWD 在 skill 目录」。 |
| 2026-11-04 | 1.1.1 | **清理已废弃的总表要求（朱总裁定）**：⑦ 删除「总表正本缺失／不擅写 `units`／向朱总报备环境缺口」整条。该条源于徽商篇只查工作区根目录造成的误判，正本实际在 `/Users/zhugx/src/mashang/单位与招聘信息总表.xlsx`；总表回填、回填核实与缺口报备均已完全废弃，`postprocess` 不再涉及，判重只认 db `drafts` ∪ `articles`。 |
