---
name: mp-html
version: 1.0.0
description: 微信公众号排版原生方言规范与合规组件库。定义微信草稿正文 100% 渲染保真的 HTML+CSS 语法集（强制使用 section 容器、严禁 position 定位、真字符列表符号、安全样式实体解码），并提供原生对话气泡、引言框导语、斑马纹表格等高保真组件模板。
homepage: https://github.com/zhugx/skills
metadata: {"openclaw":{"emoji":"🎨"}}
---

# 微信排版原生方言规范（2026-09-04 实证沉淀）

**目的**：定义"微信草稿正文能够 100% 保留的 HTML+CSS 语法集"。后续所有排版（任何文章、任何技能）都必须以本规范为母语编写，避开一切微信会转换或丢弃的写法。

**实证方法**：所有结论来自 `draft/add` → `draft/get` 真实往返测试（3 轮标签矩阵 + 35 项 CSS 属性 + 嵌套/属性测试 + 25KB div 阈值测试），每条断言都有可复现的 sample。本规范的"禁止项"均代表 **微信存储时会被改写或丢失，会导致用户在微信里看到的渲染与排版稿不一致**。

---

## 一、HTML 标签 — 全量支持表

### ✅ 原样保留（推荐使用）

| 标签 | 备注 |
|---|---|
| `<section>` | **块级容器的母语**，所有卡片用 section |
| `<p>` | 段落（section 自动渲染为段落时也是 p） |
| `<span>` | 行内 |
| `<h1>`–`<h6>` | 标题（h1 慎用：太大），h2/h3/h4 常用 |
| `<strong>` / `<b>` | 加粗 |
| `<em>` / `<i>` | 斜体 |
| `<u>` `<s>` `<del>` | 下划线/删除线 |
| `<blockquote>` | 引用（自动左侧色条样式不会被生成，需自己用 border-left） |
| `<ul>` / `<ol>` / `<li>` | 列表（ol 的 `start` 属性保留） |
| `<table>` `<thead>` `<tbody>` `<tr>` `<td>` `<th>` | 表格（border / colspan / rowspan 属性保留） |
| `<figure>` `<figcaption>` | 图组+图注 |
| `<header>` `<footer>` `<aside>` `<article>` `<nav>` `<main>` | 语义块（不强制使用） |
| `<mark>` | 高亮 |
| `<small>` / `<sub>` / `<sup>` | 小字/上下标 |
| `<q>` / `<abbr>` `<center>` | 短引用/缩写/居中 |
| `<font color="...">` | 旧字体标签（仅 color 属性保留） |
| `<big>` | 大字号 |
| `<br>` `<hr>` | 换行/分割线（微信规范化为 `<br  />` / `<hr  />`） |
| `<img>` | 图片（**`src` 会被微信改写为 `data-src` 并归一化 URL 到 `/640` 宽度**） |

### ⚠️ 行为受限（知道再使用）

| 标签 | 行为 |
|---|---|
| `<a href="...">` | **`href` 被剥光，只剩文字**——正文里加超链接行不通。如需外链，列出 URL 文本或公众号编辑器里人工加链 |
| `<iframe>` `<video>` | 标签留下但 `src` 被剥（空壳），**不要用**——直接插图片或外链 |
| `<input>` `<form>` `<label>` | **全部被删** |
| `<div>` | 仅当只含行内内容（文本、span）时原样保留；**含块级子元素（p/h\*/img/ul/嵌套div）时会被微信溶解成 p/span 并丢弃大量内联样式**（实测：107 div → 0，style 235 → 126）。**块级容器一律用 `<section>`，不要用 div** |

---

## 二、CSS 属性 — 全量支持表（35 项实测）

### ✅ 原样保留（放心使用）

布局 / 盒模型：
`display:flex` / `display:inline-block` / `display:block` / `display:none` · `align-items` · `justify-content` · `gap` · `flex` · `float` · `position:static` · `box-sizing` · `padding` · `margin` · `width` · `height` · `max-width` · `min-height` · `vertical-align` · `z-index`

边框与背景：
`border` / `border-radius` / `box-shadow` · `background` 纯色 · `background:linear-gradient(...)` · `background-image:url(...)`（URL 会被微信改写为 /640 宽度）· `background-size` · `outline`

文字与排版：
`font-family`（带 `'PingFang SC'` 字面引号，**不要写 `&#39;` 实体**）· `font-size` · `font-weight` · `color` · `line-height` · `letter-spacing` · `text-align` · `text-indent` · `text-decoration` · `word-break` · `white-space` · `min-height`

视觉：
`opacity` · `transform:rotate/scale/translate(...)` · `cursor`

标记：
`!important`（保留）

### ❌ 会被微信静默剥除

| 属性 | 后果 | 替代方案 |
|---|---|---|
| **`position:relative`** | 整段 `position:relative` 被从 style 值中删除（left/top 留下无意义） | 用 flex 列 + border-left 自绘连线；或放弃连线 |
| **`position:absolute`** | 同上，剥除 | 同上；用 flex / inline-block 实现相对位置 |
| **`position:fixed/sticky`** | 一定剥除 | 微信里没有固定/吸附概念 |
| **`top/left/right/bottom`（在没保留 position 的元素上）** | 留下但无定位效果 | — |

> ⚠️ 注意：style **属性计数**仍为 1（属性没消失），但**值里关键字被剥**。所以验收不能只看 style=数量，**必须做属性级 diff**（详见五·验收）。

### ⚠️ 输入格式坑

| 输入 | 结果 |
|---|---|
| `style="font-family:'PingFang SC'"`（字面引号） | ✅ 保留（微信会再归一化成 `&#39;` 实体） |
| `style="font-family:&#39;PingFang SC&#39;"`（HTML 实体） | ❌ **整个 style 属性被清空为 `style=""`**——上次推送 root section 变空就是这个原因 |
| `style="  font-size:16px;  color:red  "`（多空格） | ✅ 保留 |
| `style=""`（空） | ✅ 保留（空） |
| 多个分号、错乱顺序 | ✅ 保留 |

---

## 三、属性（attributes）

| 属性 | 行为 |
|---|---|
| `class="..."` | ✅ 保留（微信不解析，只透传存储） |
| `id="..."` | ❌ **被删**——别用 id 做锚点定位 |
| `data-*` | ✅ 保留（WeChat 自身就用 `data-src` 改写 img） |
| `title="..."` | ✅ 保留 |
| `alt="..."` | ✅ 保留 |
| `align="center"` | ✅ 保留（块级居中兼容） |
| `width="100%"` `height="..."` | ✅ 保留 |
| `start="3"`（ol） | ✅ 保留 |

---

## 四、设计适配清单（重要的"微信里做不到"）

| 你想做的 | 为什么不行 / 怎么替代 |
|---|---|
| 时间轴节点之间的**竖向连线** | position:absolute 被剥；用 flex 容器 + 每个 item 左侧 border + 第一个 item 的 border-top 上色 / 或每个 item 加 left-border、最后一个去掉 border-bottom |
| **正文中嵌入超链接** | `<a href>` 整个 href 被剥，文字留着但无链。替代：正文中用"链接见文末"，文末加 `<p>📎 参考链接：https://...</p>`（URL 文本字面写出，微信扫一扫会自动识别）；或推送后到后台编辑器里手工插入超链接 |
| `position:absolute` 实现**图片角标 / 浮标** | position 被剥；用 inline-flex 包裹 + 浮标放在 inline 元素里，或放弃角标 |
| `<iframe>` 嵌入视频 | src 被剥；改用图片（封面图）+ 文字提示"点击下方链接观看" + 公众号编辑器里手动插视频 |
| 在卡片右上角加 **"NEW" / "置顶"** 小标 | 别用 position:absolute；用 flex 布局，标和标题并排 |
| 列表项前的**彩色圆点** | ✅ 用 flex + 圆形 div 圆点（不用 `<ul> marker`，用 flex 容器自己绘圆点 circle） |
| 段落首行缩进 2 字符 | ✅ `text-indent:2em` 支持 |
| 两端对齐 | ✅ `text-align:justify` 支持 |

---

## 五、推送验收标准（每次必做）

**前置**：每篇文章推送后立即 `draft/get` 读回存储内容，**做属性级 diff**（不是只看计数）：

```python
import json, subprocess, re

# sent = 实际发送的 content 字符串
# stored = draft/get news_item[0]['content']

assert stored.count("<section") == sent.count("<section")     # 块级结构一致
assert stored.count("<p>")       == sent.count("<p>")         # 段落一致
assert stored.count("<img")      == sent.count("<img")        # 图片一致
assert stored.count("style=\"") == sent.count("style=\"")    # style 属性数一致
assert sent.count("<a href")     == stored.count("<a href")   # 链接数（必须是 0，a href 被剥）
# ⚠️ 属性级逐项检查：position:relative/absolute 必须为 0
assert "position:relative" not in stored
assert "position:absolute" not in stored
# ⚠️ 实体诱因：搜索任何 style 属性值里出现 &#39;
assert "&#39;" not in stored or all occurrences are inside <h*>...（仅正文实体）
# ⚠️ div 残留：存储里 <div 应该是 0（块级容器都被我们转成 section）
assert stored.count("<div") == 0
```

**任何一项不过** → 删除该草稿（`draft/delete` 用 JSON body）→ 修源码 → 重跑 prep → 重传。

---

## 五.5、容器内边距：水平归零（2026-09-04 朱总"没拉满"反馈修正）

微信阅读页正文容器自身带平台内边距，所以**我们自己不要再加水平 padding**，否则"双重内边距"让内容比普通公众号明显内收。
- 实测坑：外层排版 section（prep 加的 `padding:28px 20px 48px`）与源文档 `.page`（移动端 `padding:20px 14px 36px`）**两层叠加 ≈ 左右各 34px**，用户视角"没有左右对齐拉满"。
- 规则：外层只放排版属性（font/size/color/line-height），**不设水平 padding**；`.page` 容器水平方向清零（保留纵向呼吸，prep 已自动归一化为 `padding:8px 0 40px`，卡片贴边仅留自身 border）。
- 此条已写进 `wx_prep_content.py`（写文件前归一化 .page），并配套方言校验器无需额外规则。

## 六、Prep 流水线（`wx_prep_content.py`）必做

1. **CSS 剥注释 + 展 `var(--x)` + 按特异性内联**（避免 class 依赖）
2. **`::before/::after` 伪元素转真实节点**（微信不渲染伪元素）
3. **删 `data-page-node-id` 编辑器注入**（每个标签都注入，省 10KB）
4. **`<style>` 块必须删**（微信会过滤，且所有样式都已内联）
5. **`<div>` → `<section>` 全量转换**（div→section 之前已被证据表明"块级容器必须用 section"——避免块级溶解丢样式；含断言防残留）
6. **删除 `class="..."`**（保留也行，体积影响小）
7. **img 占位符只返回 `{{IMGn}}` 不带 `src="` 前缀**（否则 src="src=" 畸形）
8. **不用 `<a href>`**（要链放到正文末尾文字）
9. **不要在 style 值里写 `&#39;`**（要字面引号；推送前最好用 grep 扫一遍 `style=.*&#39;`）

---

## 七、参考数据点（实测）

| 项 | 值 |
|---|---|
| draft/add content 字符上限（宽松版） | **实测 27428 字符直接接受**（传闻 2 万上限未触发）。2026-09-14 再测：**39347 字符**（19 图长文，走 `draft/update`）**同样成功** —— 上限比传闻宽得多，长文不必为字符数牺牲内容 |
| `<div>` 溶解触发 | **结构触发**——div 含块级子元素即溶，与 size 无关（25KB 全文本 div 也全保） |
| `<img>` src → data-src | URL 自动改写为 `/640` 宽度（即原图原 URL 在，但公众号 CDN 截到 640px） |
| ad_count | 与长度无关，**4KB 内容也会插 2 条广告**（账号开启文中广告） |
| 访问频控 | 单 access_token 每分钟调用 1000 次，无 token 时 40001 |

---

## 八、版本与变更

- **v1.0** 2026-09-04 首次实证（4 轮 draft/add ↔ draft/get 测试；标签矩阵 + 35 CSS 项 + 嵌套属性 + div 阈值）

---

## 九、合规组件范例：对话气泡卡片（多人对话可视化，2026-09-11 吸收）

> 来源：朱总指定的「少年有话」对话样式。纯 flex 布局、零 `position:*`、零 `<div>` 含块级子元素、零伪元素、引号用 `&#x201C;`（在 `style=""` 之外安全），`wx_dialect_check.py` 应全绿。

**视觉规格**

| 要素 | 值 |
|---|---|
| 外层卡片 | 背景 `#FFFBF0`（浅米），内卡白底，圆角 `16px`，阴影 `0 2px 12px rgba(0,0,0,0.06)` |
| 左右竖线 | `#7CB342`（草绿），宽 `3px`，距边缘 `12px` |
| 标题栏 | ☀️ + 绿色药丸 `background:#7CB342;color:#fff;border-radius:20px;padding:4px 18px` + 📍 |
| 气泡圆角 | `12px`，内边距 `14px 16px` |
| 引号图标 | 黄色 `#F9A825`，`font-size:22px` |
| 三色气泡 | A `#E8F5E9`（薄荷绿）/ B `#FFF8E1`（奶油黄）/ C `#FCE4EC`（淡粉），A→B→C→A 循环 |

**合规 HTML 模板（直接复制改文字）**

```html
<!-- 对话卡片外层：浅米背景 + 白内卡 + 左右绿线 -->
<section style="background:#FFFBF0;border-radius:16px;padding:3px 12px;box-sizing:border-box;">
  <section style="display:flex;background:#fff;border-radius:14px;overflow:hidden;">
    <section style="width:3px;background:#7CB342;flex-shrink:0;"></section>
    <section style="flex:1;padding:24px 20px 20px;">

      <!-- 标题栏 -->
      <section style="display:flex;align-items:center;justify-content:center;gap:10px;margin-bottom:20px;">
        <span style="font-size:20px;">☀️</span>
        <span style="background:#7CB342;color:#fff;border-radius:20px;padding:4px 18px;font-size:15px;font-weight:700;">少年有话</span>
        <span style="font-size:18px;">📍</span>
      </section>

      <!-- 气泡 A（薄荷绿） -->
      <section style="background:#E8F5E9;border-radius:12px;padding:14px 16px;margin-bottom:14px;display:flex;align-items:flex-start;gap:10px;">
        <span style="color:#F9A825;font-size:22px;line-height:1.3;flex-shrink:0;">&#x201C;</span>
        <section style="flex:1;"><span style="font-weight:700;">刘昕雨：</span>最早的时候车上是有售票员的，现在都是<strong>“无人售票车”</strong>了，刷卡或投币都可以乘车。</section>
      </section>

      <!-- 气泡 B（奶油黄） -->
      <section style="background:#FFF8E1;border-radius:12px;padding:14px 16px;margin-bottom:0;display:flex;align-items:flex-start;gap:10px;">
        <span style="color:#F9A825;font-size:22px;line-height:1.3;flex-shrink:0;">&#x201C;</span>
        <section style="flex:1;"><span style="font-weight:700;">刘晏泽：</span><strong>“菜篮子公交”</strong>是给买菜的老年人提供的，现在的南京公交让每个人都有车坐了！</section>
      </section>

    </section>
    <section style="width:3px;background:#7CB342;flex-shrink:0;"></section>
  </section>
</section>
```

**使用注意**
1. 最后一个气泡 `margin-bottom:0`，避免底部多余留白。
2. 加粗只给关键词（人名/术语/数字结论），每条气泡内 ≤2 处。
3. 气泡数量不限，A→B→C→A 循环；满爸爱生活通常 3-5 条（一问一答 + 追问）。
4. 对话必须「满宝：xxx」「满爸：xxx」直给式（见文风规范第 3、23 条）。
5. `wx_prep_content.py` 已原生 compliant，应零改动通过；`wx_dialect_check.py` 校验：无 position、无 div 块级、无 `&#39;`、无 `a href`。

---

## 十、合规组件范例：引言框 / 导语卡片（纯色微卡片 vs 竖条纹版，2026-09-15 优化沉淀）

> 来源：面向导语与编者按区域。原右上角标签布局易产生较大空白占幅，现优化推荐**纯色微卡片**（浅纯色底 + 左侧主题重色条 + 行内紧凑微标签），大幅压缩垂直无效留白，整体紧凑精致；原条纹版作为备选保留。

### 推荐版：纯色紧凑微卡片（纯色底 + 左强调条 + 行内小标，首选推荐）

#### 视觉规格
- **外层卡片**：纯色极浅底（如科技蓝 `#f0f7ff` 或浅绿 `#f1f8e9`），边框 `1px solid #dbeafe`，左侧加粗强调条 `4px solid #2563eb`，圆角 `12px`，内边距 `16px 18px`
- **顶部微标签**：行内圆点 + 强调色小标题（`font-size:13.5px;font-weight:700`），紧凑居左，完全不占右侧整行空白
- **正文**：字号 `15px`，行高 `1.85`，段间距 `10px`，末段 `margin:0`

#### 合规 HTML 模板
```html
<!-- ===== 导语卡片：纯色紧凑微卡片（首选推荐：零垂直留白挤占） ===== -->
<section style="padding:0 14px;margin-bottom:24px;">
  <section style="background:#f0f7ff;border:1px solid #dbeafe;border-left:4px solid #2563eb;border-radius:12px;padding:16px 18px;box-shadow:0 1px 3px rgba(37,99,235,0.04);">
    
    <!-- 紧凑顶标：行内小标，不占用整行垂直高度 -->
    <section style="display:flex;align-items:center;gap:8px;margin-bottom:10px;">
      <span style="display:inline-block;width:6px;height:6px;background:#2563eb;border-radius:50%;"></span>
      <span style="font-size:13.5px;font-weight:700;color:#2563eb;letter-spacing:0.5px;">开源导读</span>
    </section>

    <!-- 导语正文 -->
    <p style="margin:0 0 10px;font-size:15px;line-height:1.85;color:#1e293b;">
      第一段导语内容，直击核心痛点与背景。
    </p>
    <p style="margin:0;font-size:15px;line-height:1.85;color:#1e293b;">
      第二段导语内容，引出本文重点介绍的工具或解决方案。
    </p>
  </section>
</section>
```

---

### 备选版：双层竖条纹框（适合特定节日/文旅专题场景）

> 来源：朱总指定的「开学倒计时」引言样式。纯 `repeating-linear-gradient` 实现竖条纹、flex 绝对定位右上角标签（**零 `position:*`**，用 `margin-left:auto` 推到右侧）、`wx_dialect_check.py` 全绿。

### 主题色变量（换配色只改这 4 个值）

| 变量 | 含义 | 默认值（绿主题） | 备选（蓝主题） |
|---|---|---|---|
| `--card-bg` | 条纹底色 A（浅） | `#F1F8E9` | `#E3F2FD` |
| `--card-stripe` | 条纹底色 B（深） | `#E8F5E9` | `#BBDEFB` |
| `--card-border` | 边框 + 标签文字 | `#7CB342` | `#1a73e8` |
| `--label-bg` | 右上角标签底 | `rgba(124,179,66,0.12)` | `rgba(26,115,232,0.10)` |

### 视觉规格

| 要素 | 值 |
|---|---|
| 外层卡 | 白底，圆角 `16px`，阴影 `0 2px 12px rgba(0,0,0,0.06)` |
| 内框 | 竖条纹 `repeating-linear-gradient(90deg, A 0px, A 24px, B 24px, B 48px)`，圆角 `12px`，边框 `1.5px solid` 主题色 |
| 内边距 | `24px 28px` |
| 正文 | 字号 `15px`，行高 `1.85`，颜色 `#333`，段间距 `12px` |
| 右上角标签 | 圆角 `20px`，padding `4px 14px`，字号 `13px`，颜色主题色，底色半透明；下方波浪线用 `border-bottom:1.5px dashed` 模拟 |

### 合规 HTML 模板

```html
<!-- ===== 引言框：竖条纹背景 + 右上角装饰标签 ===== -->
<section style="background:#fff;border-radius:16px;padding:20px;box-shadow:0 2px 12px rgba(0,0,0,0.06);">

  <!-- 内框：竖条纹 + 绿边 + 相对定位容器 -->
  <section style="background:repeating-linear-gradient(90deg,#F1F8E9 0px,#F1F8E9 24px,#E8F5E9 24px,#E8F5E9 48px);border:1.5px solid #7CB342;border-radius:12px;padding:24px 28px;position:relative;">

    <!-- 右上角标签（margin-left:auto 推右，零 position） -->
    <section style="display:flex;justify-content:flex-end;margin-bottom:16px;">
      <section style="background:rgba(124,179,66,0.12);color:#7CB342;border-radius:20px;padding:4px 14px;font-size:13px;font-weight:700;border-bottom:1.5px dashed #7CB342;text-align:center;">
        开学倒计时
      </section>
    </section>

    <!-- 正文段落 -->
    <p style="font-size:15px;line-height:1.85;color:#333;margin:0 0 12px;">暑期接近尾声，开学的脚步声越来越近咯！</p>
    <p style="font-size:15px;line-height:1.85;color:#333;margin:0 0 12px;">对于南京的中小学生们来说，有一张出行<strong>“神卡”</strong>要赶紧安排上，不仅乘车享半价优惠，卡面还<strong>越来越可爱</strong>！</p>
    <p style="font-size:15px;line-height:1.85;color:#333;margin:0;">今天给大家带来一份超全的学生卡种类及办理攻略，各种卡面、线上线下渠道一目了然，<strong>赶紧收藏转发</strong>哦！</p>

  </section>
</section>
```

### 使用注意
1. **条纹宽度固定 48px 周期**（A 24px + B 24px），在不同屏幕宽度下视觉一致；不要改周期否则稀疏不均。
2. **右上角标签用 `justify-content:flex-end` 推右**，不用 `position:absolute`（微信会剥除）；内框需 `position:relative` 仅作视觉参考——**实际推送前 prep 会把 position:relative 剥掉**，但 flex 布局不受影响（标签已在正常流中靠右）。
3. **若文章整体是蓝主题**，把 4 个变量批量替换为蓝主题值即可；条纹周期和圆角/阴影不变。
4. 正文段落数不限，最后一段 `margin:0`。
5. 标签文字建议 2-6 字（"开学倒计时""满爸划重点""本期亮点"等），超长会挤占正文空间。

---

## 十一、合规组件范例：数据列表卡片（主题色卡片 + 斑马纹表格，2026-09-11 吸收）

> 来源：朱总指定的「南京教师节福利指南」列表样式。纯 `<table>` + 主题色卡片头、斑马纹行、零 `position:*`、`wx_dialect_check.py` 全绿。

### 主题色变量（换配色只改这 5 个值）

| 变量 | 含义 | 默认值（橙主题） | 备选（绿主题） | 备选（蓝主题） |
|---|---|---|---|---|
| `--theme` | 卡片底色 / 表头底色 | `#F57C00`（暖橙） | `#7CB342`（草绿） | `#1a73e8`（蓝） |
| `--theme-light` | 表格偶数行 / 卡片内部区 | `#FFF3E0`（浅橙） | `#F1F8E9`（浅绿） | `#E3F2FD`（浅蓝） |
| `--theme-dark` | 表头文字 / 强调文字 | `#E65100`（深橙） | `#558B2F`（深绿） | `#0d47a1`（深蓝） |
| `--text-on-theme` | 主题色上的文字 | `#FFFFFF` | `#FFFFFF` | `#FFFFFF` |
| `--text-body` | 正文文字 | `#333333` | `#333333` | `#333333` |

### 视觉规格

| 要素 | 值 |
|---|---|
| 外层卡片 | 主题色底，圆角 `16px`，`overflow:hidden` |
| 头部区 | 左侧插图（emoji 或 img 占位）+ 主标题（白/大/粗）+ 副标题（白/小/透明度 0.9） |
| 表格 | 宽 `100%`，`border-collapse:collapse`，无外边框线 |
| 表头行 | 主题色稍深底色，白色文字，`font-weight:700`，`padding:10px 12px` |
| 数据行奇数 | 白色 `#fff` 或极浅底 |
| 数据行偶数 | `--theme-light` 浅色 |
| 单元格 | `padding:10px 12px`，`vertical-align:top`，`border-bottom:1px solid rgba(0,0,0,0.06)` |
| 底部注 | 小字 `12px`，灰色 `#999`，左右分栏（左注释 / 右来源） |

### 合规 HTML 模板

```html
<!-- ===== 数据列表卡片：主题色头 + 斑马纹表格 ===== -->
<section style="background:#F57C00;border-radius:16px;overflow:hidden;">

  <!-- 头部区：插图 + 标题 + 副标题 -->
  <section style="display:flex;align-items:center;gap:14px;padding:22px 24px 16px;">
    <span style="font-size:42px;line-height:1;flex-shrink:0;">👩‍🏫</span>
    <section>
      <p style="color:#fff;font-size:22px;font-weight:700;margin:0 0 4px;line-height:1.3;">南京教师节福利指南</p>
      <p style="color:rgba(255,255,255,0.9);font-size:14px;margin:0;line-height:1.4;">（2026年版 —— 南京刘班班®）</p>
    </section>
  </section>

  <!-- 表格区 -->
  <section style="background:#fff;">
    <table style="width:100%;border-collapse:collapse;font-size:14px;color:#333;">

      <!-- 表头 -->
      <tr style="background:#E65100;color:#fff;">
        <th style="padding:10px 12px;font-weight:700;text-align:left;width:50px;">序号</th>
        <th style="padding:10px 12px;font-weight:700;text-align:left;">景区名称</th>
        <th style="padding:10px 12px;font-weight:700;text-align:left;width:120px;">活动时间</th>
        <th style="padding:10px 12px;font-weight:700;text-align:left;">活动内容</th>
      </tr>

      <!-- 数据行：奇数白底 -->
      <tr style="background:#fff;">
        <td style="padding:10px 12px;vertical-align:top;">1</td>
        <td style="padding:10px 12px;vertical-align:top;">南京欢乐谷</td>
        <td style="padding:10px 12px;vertical-align:top;">8.22–9.20</td>
        <td style="padding:10px 12px;vertical-align:top;">教师免费<br/>同行人员130元</td>
      </tr>

      <!-- 数据行：偶数浅色 -->
      <tr style="background:#FFF3E0;">
        <td style="padding:10px 12px;vertical-align:top;">2</td>
        <td style="padding:10px 12px;vertical-align:top;">心印中华门</td>
        <td style="padding:10px 12px;vertical-align:top;">9.5–9.13</td>
        <td style="padding:10px 12px;vertical-align:top;">教师免费（夜场）</td>
      </tr>

      <!-- 更多行照此模式追加 ... -->

      <!-- 合并备注行 -->
      <tr style="background:#FFF3E0;">
        <td colspan="4" style="padding:10px 12px;text-align:center;color:#E65100;font-size:13px;">
          2026年部分活动暂未公布，持续更新中 ……
        </td>
      </tr>

    </table>
  </section>

  <!-- 底部注 -->
  <section style="display:flex;justify-content:space-between;padding:10px 24px 14px;font-size:12px;color:#999;">
    <span>注：信息仅供参考，详情请查看各景区官方公告</span>
    <span>内容由 @南京刘班班 整理</span>
  </section>

</section>
```

### 使用注意
1. **表头 `<th>` 必须在 `<thead>` 或直接 `<tr>` 里**，微信保留 `<th>` 的加粗语义；不要用 `<td>` + 手动 `font-weight:700` 代替（功能一样但语义不清）。
2. **斑马纹用 `background` 交替**，不用 `:nth-child` 伪类（微信不渲染伪类选择器）。手动给偶数行写 `style="background:--theme-light;"`。
3. **单元格内多行内容用 `<br/>`**（微信保留），不要用 `<p>`（会增加意外 margin）。
4. **头部插图**可用 emoji（如 👩‍🏫🎫🏛️🚌）或 `<img>`（base64 图走 uploadimg）；插图区 `flex-shrink:0` 防止被压缩。
5. **列宽控制**：序号列 `width:50px` 固定窄，时间列 `width:120px` 半固定，其余自适应。超过 5 列时建议改横向滚动或拆分表格。
6. **底部注的来源文字**格式为 `@账号名`，与公众号互导引流一致。
7. **换主题**：全局搜索替换 5 个色值即可（`#F57C00`→新主题色、`#FFF3E0`→新浅色、`#E65100`→新深色），其余结构/圆角/间距不变。
8. **`<table>` 在微信中 100% 保留**：`border` / `colspan` / `rowspan` / `cellpadding` 全部存活（方言规范 §一 已实证）。

---

## 十二、合规组件范例：横向滑动图组（同主题多图，2026-09-14 实测通过）

> 场景：同一处看点有多张实拍（正立面／侧立面、全景／局部、多角度），想一次展示又不想纵向堆成一条长龙。**微信正文会保留横向滚动相关 CSS**，可以做出"手指左右滑动看图"的效果——2026-09-14 先做属性级 `draft/add` → `draft/get` 往返实测，**随后在正式长文（19 图）里端到端复验：6 组滑动组 CSS 一条没丢**（`overflow-x:auto`×6、`white-space:nowrap`×6、`scroll-snap-type`×6、`scroll-snap-align`×13、`display:inline-block`×13），可用。

### 实测结论（属性级，非"看着像"）

| 属性 | 结果 |
|---|---|
| `overflow-x:auto` / `overflow-x:scroll` / `overflow:auto` | ✅ 原样保留 |
| `white-space:nowrap` | ✅ 保留 |
| `scroll-snap-type:x mandatory` / `scroll-snap-align:center` | ✅ 保留（可做"一张一张吸附"） |
| `scrollbar-width:none` | ✅ 保留 |
| `display:inline-block` | ✅ 保留 |
| `-webkit-overflow-scrolling:touch` | ❌ 被剥（无妨：现代 iOS 默认就有惯性滚动） |

### 合规 HTML 模板（2 张示例，可续加）

```html
<!-- ===== 横向滑动图组 ===== -->
<section style="margin:18px 0 4px;">
  <section style="overflow-x:auto;white-space:nowrap;width:100%;scroll-snap-type:x mandatory;scrollbar-width:none;">
    <section style="display:inline-block;width:78%;vertical-align:top;scroll-snap-align:center;">
      <img src="..." style="width:100%;border-radius:12px;display:block;"/>
    </section>
    <section style="display:inline-block;width:78%;vertical-align:top;scroll-snap-align:center;margin-left:8px;">
      <img src="..." style="width:100%;border-radius:12px;display:block;"/>
    </section>
  </section>
  <p style="font-size:12.5px;color:#9a9a9a;text-align:center;margin:9px 0 0;line-height:1.6;">图注 · 日期实拍 ｜ 左右滑动看更多</p>
</section>
```

### 使用注意

1. **每张图 78% 宽，绝不要 100%**——右侧露出下一张的边缘，是唯一的"可滑动"视觉提示；用 100% 读者会以为只有一张，滑动功能等于白做。
2. **图注必须写"左右滑动看更多"**，否则大多数读者不会去滑。二者要配套使用。
3. **不用 `position`**，靠 `overflow-x` + `inline-block` 实现，天然规避方言红线；`wx_dialect_check.py` 全绿。
4. 一组 **2–3 张**为宜；超过 4 张读者划不动，也不记得看到哪张。
5. 竖图放进滑动组（78% 宽 ≈ 528px 显示宽）比单独用 100% 宽省一半纵向空间，长文尤其值得这么做。
6. 首图的 `margin` 由外层 section 承担，内层不要加水平 padding，避免与微信正文容器双重内缩（同 §五.5）。

---

**附**：实测脚本 `/tmp/wx_dialect_test.py` + 全部测试样本 `/tmp/wx_t{1,2,3}_*.html` 可复跑；改动 prep 时照本规范重测一遍。

---

## 十三、合规组件范例：GitHub 专栏「科技卡片 UI」（2026-09-15 规范沉淀）

> 来源：面向「满宝看未来」专栏 Markdown 草稿中纯语义的「项目名片」标准三列表格，在 HTML 排版阶段自动升级为高转化、移动端友好的高保真科技卡片。纯 flex 布局、零 `position:*`、零 `<div>` 块级、`wx_dialect_check.py` 全绿。

### 视觉规格与要素

| 要素 | 规格与实现 |
|---|---|
| 外层卡片 | 浅灰蓝底 `#f8fafc`，边框 `1px solid #e2e8f0`，圆角 `14px`，轻微阴影 `box-shadow:0 1px 3px rgba(0,0,0,0.03)` |
| 仓库抬头 | GitHub 黑色 SVG 图标 + 仓库全名 (`font-size:17px;font-weight:800;color:#0f172a`) + 右侧协议小标签 |
| 开源地址栏 | 白底内卡 (`#ffffff`)，浅灰微框，**明文展示 URL (`color:#2563eb;word-break:break-all;font-family:monospace`)**，读者长按即可直接复制 |
| 数据三宫格 | 三等分 flex 白底微卡：社区热度 (Stars/Forks)、开源协议 (强调色突出)、核心语言 (TS/Vue/Rust 等) |
| 架构与版本 | 底层架构技术栈 (如 Electron + PixiJS + 原生后端) 与最新发布版本及时间 |
| 核心定位 | 底部虚线分隔，单句精炼提炼工具的核心业务定位 |

### 合规 HTML 模板

```html
<!-- ===== GitHub 项目名片：高保真科技卡片 UI ===== -->
<section style="padding:0 14px;margin-bottom:28px;">
  <section style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:14px;padding:18px 16px;box-shadow:0 1px 3px rgba(0,0,0,0.03);">
    
    <!-- 仓库抬头 -->
    <section style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px;">
      <section style="font-size:17px;font-weight:800;color:#0f172a;display:flex;align-items:center;gap:6px;">
        <svg style="width:20px;height:20px;fill:#1e293b;" viewBox="0 0 16 16"><path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"></path></svg>
        owner / repo
      </section>
      <span style="font-size:12px;background:#e2e8f0;color:#334155;padding:2px 8px;border-radius:12px;font-weight:700;">AGPL-3.0</span>
    </section>

    <!-- 独立开源地址复制栏（明文 URL） -->
    <section style="background:#ffffff;border:1px solid #e2e8f0;border-radius:8px;padding:10px 12px;margin-bottom:14px;">
      <section style="font-size:11px;color:#64748b;margin-bottom:3px;font-weight:600;">🌐 项目开源地址（长按直接复制）：</section>
      <section style="font-size:13.5px;color:#2563eb;font-family:ui-monospace,Menlo,Consolas,monospace;word-break:break-all;font-weight:700;line-height:1.4;">
        https://github.com/owner/repo
      </section>
    </section>

    <!-- 数据三宫格 -->
    <section style="display:flex;gap:8px;margin-bottom:14px;">
      <section style="flex:1;background:#ffffff;border:1px solid #e2e8f0;border-radius:8px;padding:10px 4px;text-align:center;">
        <section style="font-size:11.5px;color:#64748b;">社区热度</section>
        <section style="font-size:15px;font-weight:800;color:#0f172a;margin-top:2px;">⭐ 28.8k</section>
        <section style="font-size:10.5px;color:#94a3b8;margin-top:1px;">2,196 🍴</section>
      </section>
      <section style="flex:1;background:#ffffff;border:1px solid #e2e8f0;border-radius:8px;padding:10px 4px;text-align:center;">
        <section style="font-size:11.5px;color:#64748b;">开源协议</section>
        <section style="font-size:15px;font-weight:800;color:#2563eb;margin-top:2px;">AGPL-3.0</section>
        <section style="font-size:10.5px;color:#10b981;margin-top:1px;">代码完全公开</section>
      </section>
      <section style="flex:1;background:#ffffff;border:1px solid #e2e8f0;border-radius:8px;padding:10px 4px;text-align:center;">
        <section style="font-size:11.5px;color:#64748b;">核心语言</section>
        <section style="font-size:15px;font-weight:800;color:#0f172a;margin-top:2px;">TS 83%</section>
        <section style="font-size:10.5px;color:#94a3b8;margin-top:1px;">C++ · CUDA</section>
      </section>
    </section>

    <!-- 架构与版本说明 -->
    <section style="font-size:13.5px;color:#334155;line-height:1.8;margin-bottom:8px;">
      <section>🛠️ <strong>架构底座</strong>：核心框架与底层依赖说明</section>
      <section>🚀 <strong>最新版本</strong>：v1.4.0 (2026-09-08 ｜ 发布特性说明)</section>
    </section>

    <!-- 核心定位 -->
    <section style="border-top:1px dashed #cbd5e1;padding-top:10px;margin-top:8px;font-size:12.5px;color:#64748b;line-height:1.6;">
      💡 <strong>核心定位</strong>：一句话说明项目核心价值定位与主要解决的痛点
    </section>
  </section>
</section>
```
