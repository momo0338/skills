---
name: mp-publish
description: 微信公众号内容中台（草稿 · 发布 · 数据分析 三模块一站式）。既支持排版稿（HTML + base64 内嵌图）一键直推草稿箱——图片自动转存微信 CDN、微信原生方言合规校验（section 替 div、禁 position、样式实体规范化）、长尾 SEO 摘要、服务端 draft/get 回读验收；也覆盖草稿增删改查与备份回滚、发布提交与状态跟踪、用户/图文/消息/接口四大类数据分析（21 个 datacube 接口，日期跨度自动分段）。触发词：公众号草稿、推草稿、draft、发布文章、freepublish、公众号数据分析、datacube、阅读量、涨粉数据、mp-publish。
---

# 技能-微信公众号内容中台（草稿 · 发布 · 数据分析 · HTML 直推）

**沉淀时间**: 2026-09-04（HTML 直推全链路打通）｜ 2026-09-16 扩展为三模块内容中台
**适用场景**: 两条主线——
① **排版稿直推草稿箱**：把 vault 里排版好的单文件 HTML 文章（base64 内嵌图 + `<style>` 类样式）直接推送进微信公众号草稿箱，无需手工粘贴排版；
② **服务端接口作业**：草稿箱增删改查（draft/*）、发布提交与状态跟踪（freepublish/*）、用户/图文/消息/接口四类数据分析（datacube/*）。

> ⚡ **先读 §十三「能力总览与权限现实」**：本账号（个人订阅号）的接口权限实测结论与脚本入口一览。
> 一句话版：**草稿模块全部可用；发布模块与数据统计模块因账号类型限制全部不可用** ——
> 别在这两块白花力气，§十三 已给出各自的替代路径。

---

## 一、凭据与前置


- **凭据**：AppID/AppSecret **禁止明文写入本仓库**。运行前通过环境变量 `WX_APPID` / `WX_APPSECRET` 注入，或在 `~/.config/weixin/` 下放置 `appid` / `appsecret` 文件（与 IMA 凭证 `~/.config/ima/` 同款约定）；脚本启动时两者皆缺会退出报错。
- **IP 白名单**：微信 `cgi-bin/token` 强校验出口 IP（40164 报错会带 `invalid ip x.x.x.x`）。家宽 IP 会变，变动后需在公众号后台「设置与开发 → 基本配置 → IP白名单」手动添加。**注意：沙箱内 curl 的出口 IP 就是白名单校验对象**。
- **依赖**：`bs4`、`PIL`（均在 `~/.workbuddy/binaries/python/envs/default` venv 内已装）。
- **access_token 获取（2026-09-16 升级）**：新脚本统一走 [`scripts/wx_common.py`](./scripts/wx_common.py) 的 `get_token()` ——
  **优先用官方推荐的 `cgi-bin/stable_token`**（不经 `cgi-bin/token`，不会被其它系统把 token 顶掉），失败自动回退旧接口；
  同时带**本地磁盘缓存**（`~/.cache/weixin/token_<appid 后8位>.json`，有效期扣 300s 安全边距），
  避免高频调 token 接口触发频次限制。旧脚本（`wx_push_draft.py` / `wx_pipeline.py`）逻辑未动，行为不变。
- **错误翻译**：`wx_common.py` 内置 `ERRCODE_HINTS`，把微信 errcode 译成「人话 + 处置建议」，
  40164 会直接把「需添加的 IP」打出来。常见码见 §十四.1 的错误码对照表。

## 二、微信排版原生方言规范（强制遵循）

**所有排版稿件的编写 → prep → push 全链路必须遵循 [`微信排版原生方言规范.md`](../mp-html/SKILL.md)**。要点：
- 块级容器**只用 `<section>`，不要用 `<div>`**（div 含块级子元素会被微信溶解并丢失大量样式）
- 样式属性**不能用 `position:relative/absolute/fixed/sticky`**（微信静默剥除）
- style 值里**不要写 `&#39;` 等 HTML 实体**（整个 style 会被清空）。**区分来源**：这条禁的是作者自己在源码里写实体；微信存储时**自己**把裸 `'` 规范化成 `&#39;`（发生在 `font-family` 上）属无害，别误判——判定方法见 §四「存回内容里的 `&#39;` 是微信自己的编码」
  - ⚠️ **由此推出的回写铁律**：如果你把 `draft/get` 读回的正文**原样**丢回 `draft/update`，就把微信自己编码的 `&#39;` 当成了"作者写的实体"，微信会立刻把那个 style 整段清空成 `style=""`（2026-09-14 流感文实测：外层 `font-family/color/line-height` 全丢）。**回写前必须把真实 `style="…"` 属性内的 `&#39; → '`、`&quot;/&#34; → "`、`&amp; → &` 解码回裸字符**。判别式：`style=""` 计数必须为 0，且 `style=` 总数与发送前相等。
- **不要用 `<a href>`**（href 被剥光），需要链接用文字或文末列出
- **列表小圆点别自绘**（2026-09-11 实测）：`ul li{position:relative}` + `ul li::before{position:absolute;...}` 这种写法会被方言校验判 `position:relative` 违例（阻断推送），而且**伪元素在微信正文里根本不渲染**——手机端上圆点会整个消失。正确做法是往每个 `<li>` 里插一个**真实字符标记**：`<li><span class="m">•</span>正文</li>`，配 `ul li .m{color:#1a73e8;font-size:1.05em;font-weight:700;margin-right:8px;}`，零 position 依赖。用 `·`(U+00B7) 视觉偏细，用 `•`(U+2022) 更饱满。
- **导语/钩子 ≠ 概括信息（2026-09-11 朱总反馈）**：文章开头不要写成"本文分两部分/先看两个前提"这类摘要式清单，读者点进来是想读文章。开篇应当是**导语**：先给一个具体场景（"九月初，你拖着行李箱出站，录取通知书还塞在包侧兜里"）→ 亮出核心利益 → 埋紧迫感（截止日期）→ 一句必须记住的前提。硬信息（分类表、截止时间、适用人群）下沉到正文小节，不要堆在开头。
- **编号列表不要依赖 `<ol>` 自动编号**（2026-09-11）：`<ol><li>` 的序号由编辑器渲染，微信规范化时可能被丢掉（与伪元素同理）。要点数就用**显式字符**：`<span class="m">①</span>`（或 1./①/•），零渲染依赖。
- **给读者外链只能走两条路**：正文里的 `<a href>` 会被剥光，所以①用**公众号后台的「原文链接」**（`draft/add` 的 `content_source_url` 字段，本次实测场景：把活动页地址设为原文链接）②**把二维码图片贴进正文**让读者长按识别。**照抄别人文案里的"点文末阅读原文"是常见错**——那是别人账号自己的入口，你的文章里没有，必须改文案。
- 验收用 [`scripts/wx_dialect_check.py`](./scripts/wx_dialect_check.py) 跑：禁 `position:*`、`style=""` 空属性、`<div>` 含块级子、`<a href>` 等；通过才能 push
- 凡需重新确认微信支持/不支持某项，写一个最小样本用 [`scripts/wx_dialect_test.py`](./scripts/wx_dialect_test.py) 跑一次 draft/add→draft/get，看读回里的属性值
- **对话气泡卡片组件（2026-09-11 吸收）**：多人/亲子对话可视化优先用交替色气泡卡片（薄荷绿/奶油黄/淡粉，左置黄色引号图标 + 栏目名标题栏 + 📍）。完整合规 HTML 见 [`微信排版原生方言规范.md §九`](../mp-html/SKILL.md)：纯 flex、零 `position`、零 `<div>` 块级、引号用 `&#x201C;`，直接过 `wx_dialect_check.py`；写作端纪律见文风规范第 12 条。
- **引言框 / 导语卡片（2026-09-11 吸收）**：文章开篇导语区优先用竖条纹背景 + 右上角装饰标签样式。完整合规 HTML + 4 个主题色变量见 [`微信排版原生方言规范.md §十`](../mp-html/SKILL.md)：`repeating-linear-gradient` 竖条纹、标签用 `margin-left:auto` 推右（零 position）、换配色只改 4 个变量。
- **数据列表卡片（2026-09-11 吸收）**：结构化信息（活动清单/对比表/福利汇总）优先用主题色卡片 + 斑马纹 `<table>` 样式。完整合规 HTML + 5 个主题色变量见 [`微信排版原生方言规范.md §十一`](../mp-html/SKILL.md)：`<table>` 全属性微信保留、手动斑马纹（不用伪类）、换配色全局替换 5 个色值即可。
- **横向滑动图组（2026-09-14 实测吸收）**：同一处看点有多张实拍（多角度/全景局部）时，用**横向滑动图组**一次展示——`overflow-x:auto` + `white-space:nowrap` + `display:inline-block` + `scroll-snap-type:x mandatory`，每张 **78% 宽**（右侧露下一张边缘作"可滑"提示），图注必须写"**左右滑动看更多**"。已做属性级 draft/add→get 往返实测，上述 CSS **全部保留**（仅 `-webkit-overflow-scrolling` 被剥，不影响）。详见 [`微信排版原生方言规范.md §十二`](../mp-html/SKILL.md)。

## 三、极速推荐：单命令一键直推流水线（Single-Call Pipeline，10~15秒完成）

将预处理、封面提取、方言校验、查重匹配、图片上传、草稿增量更新与服务端回读验收**全量收敛为单次命令执行**，杜绝多轮模型往返延迟：

```bash
python3 /Users/zhugx/src/skills/mp-publish/scripts/wx_pipeline.py \
    --html "待发布/xxx-排版.html" \
    --update-auto
```

**流水线在底层 15 秒内自动闭环完成以下 7 步**：
1. **元数据全自动萃取**：自动从 HTML `<title>` 与同级 `*.md` 提取标题和 ≤120 字 SEO 摘要，自动寻找匹配同级 `*-封面.jpg`；
2. **HTML 预处理 (wx_prep_content.py)**：抽离 Base64 原图并分配占位符、CSS 全内联；
3. **封面规范裁切**：对匹配封面自动按 900×383（2.35:1）居中裁切并覆盖缓存；
4. **原生方言合规拦截 (wx_dialect_check.py)**：强校验 0 position、0 div 块级嵌套、0 a[href]、0 空样式，不过不推；
5. **草稿箱智能查重与就地更新 (draft/update)**：自动检测草稿箱中同名/同主题已有草稿，匹配到即原地增量更新，杜绝生成同名废稿；
6. **素材上传与正文拼装 (wx_push_draft.py)**：正文图并发上传腾讯 CDN 换取 mmbiz URL，封面上传永久素材；
7. **服务端全量闭环验收 (draft/get)**：自动回读微信服务端最新存储内容，核验标签数、图片数与样式存活，断言 `style="": 0`。

---

### 三.1 底层分步调试流水线（备查）

```bash
PY=/Users/zhugx/.workbuddy/binaries/python/envs/default/bin/python3
SCRIPTS="/Users/zhugx/src/skills/mp-publish/scripts"

# ① 预处理：抽图 + CSS 全内联 + 伪元素转真实节点 + 裁封面（输出到 /tmp/wx_*）
$PY $SCRIPTS/wx_prep_content.py "待发布/xxx-排版.html"

# ② 推送：token → uploadimg(正文图) → add_material(封面) → draft/add
$PY $SCRIPTS/wx_push_draft.py

# ②' 就地更新已有草稿（不新增草稿、不删旧稿）——优先用这条
$PY $SCRIPTS/wx_push_draft.py --update-media-id "m9YR9nbv...已有草稿media_id"
```

`wx_push_draft.py` 里的 `TITLE / AUTHOR / DIGEST` 每篇文章要改（脚本头部常量，3670 字节，直接改文件或让我现场改）。

### ②'' 就地更新（draft/update）回写铁律（2026-09-14 实测，踩过坑）

**场景**：只想改封面 / 微调少量字段，正文一个字不动 → 用 `draft/get` 拉回 `news_item[0]`，改字段后 `draft/update` 写回。这样不新增草稿、不删旧稿。

**必须在回写前做的归一化**：`draft/get` 读回的正文里，微信已把 `font-family` 引号规范化成 `&#39;`。**原样回写 = 把实体当作者输入 → 微信清空该 style → `style=""`**。所以先解码：

```python
import re
def decode_style(m):
    v = m.group(1)
    for a, b in [("&#39;", "'"), ("&#34;", '"'), ("&quot;", '"'), ("&amp;", "&")]:
        v = v.replace(a, b)
    return 'style="' + v + '"'
content = re.sub(r'style="([^"]*)"', decode_style, content)   # 只动真实 style 属性，data- 里 JSON 化的 &quot;style&quot; 不会命中
```

**payload 结构**（易错点）：`{"media_id":…, "index":0, "articles": <对象>}` —— **`articles` 是对象不是数组**（与 `draft/add` 相反）。成功判 `errcode==0`。

**回写后必做的三条断言**：① `style=""` 计数 == 0；② 各标签计数（section/p/img/table/tr/td/th/h3/strong）+ `style=` 总数与发送前逐项相等；③ 去标签纯文本完全一致。三条全过才算成功（本次首推后就是靠 ② 里 `style=""` 由 0 变 1 抓到了回归）。

**只换封面更省事的做法**：`draft/get` → 仅替换 `thumb_media_id` → 按上述规则回写。不必重跑 `wx_prep_content.py`（免去正文图重传与新 URL）。

### ① wx_prep_content.py 做了什么
1. 抽取全部 `data:image/*;base64` → `/tmp/wx_img_N.jpg`，原位替换为 `{{IMGn}}` 占位符
2. 解析 `<style>` CSS（剥离注释、展开 `var(--x)`），按特异性排序后**全部内联**到 `style` 属性——**微信正文会过滤 `<style>` 标签，类样式全靠内联存活**
3. 时间轴 `.t-item::before` 竖线伪元素 → 注入真实 `<span>`（伪元素在微信里不渲染）
4. 删除编辑器注入的 `data-page-node-id`（每条约 40 字符，全文省 ~10KB）
5. `@media (max-width:480px)` 规则当移动端值用（微信读者全是手机，正好）
6. 选**最宽横图**居中裁 900×383（2.35:1 封面比例）→ `/tmp/wx_cover.jpg`
7. 产出：`/tmp/wx_wechat_content.html`（带占位符）+ `/tmp/wx_imgmap.json` + `/tmp/wx_img_*.jpg` + `/tmp/wx_cover.jpg`

### ② wx_push_draft.py 做了什么
1. `cgi-bin/token` 取 access_token
2. 每张图 `cgi-bin/media/uploadimg`（**正文图必须走这个接口**，返回 mmbiz.qpic.cn URL）→ 回填占位符
3. 去掉 `class` 属性 + 压缩标签间空白（微信忽略 class，纯减体积）
4. 封面 `cgi-bin/material/add_material?type=image` → `thumb_media_id`
5. `cgi-bin/draft/add` 推 JSON → 返回 `media_id` 即成功，后台「草稿箱」可见

**就地更新（`--update-media-id`，2026-09-14 新增，优先用）**：传了该参数就走 `draft/update` 而不是 `draft/add`——**同一个 media_id 原地改，草稿箱不会多出一份、也不需要删任何旧稿**。这是"修订已推草稿"的默认姿势（配合 2026-09-14 立规：能 update 就不 delete+add）。
- 请求体结构与 add 不同：`{"media_id": "...", "index": 0, "articles": {…}}` —— **注意 `articles` 是单个对象，不是数组**（add 里才是 `[article]`）；`index` 是图文消息内序号，单图文固定 0。
- 返回体没有 `media_id`（不是新增），判成功看 **`errcode == 0`**。
- 副作用提醒：`/tmp/wx_draft_payload.json` 的顶层结构会变成 update 形状（`articles` 为 dict），凡按 `["articles"][0]` 读"发送前内容"做验收的脚本要相应兼容。
- **改用户手改过的草稿前先 `draft/get` 拉档对比**（见 §⑧ 铁律），update 也一样会覆盖用户的手工改动。

**摘要（digest）自动处理**：`--digest` 显式传则直接使用（超 120 自动截断）；**不传则自动从正文纯文本开头提炼**（保底不空白，会打印醒目提示）。命令示例：
```bash
python wx_push_draft.py --title "..." --author "满爸爱生活" --digest "SEO摘要…" [--content-file …] [--imgmap …] [--cover …]
```

**无图文章分支**（源 HTML 无 base64 内嵌图，如方孝孺墓文字稿）：
- prep 会自动跳过封面（打印提示并 exit 0，正文产物已保留）；
- 需要自备封面：`wx_push_draft.py --cover <文字封面.jpg>`——可用 PIL 生成 900×383 文字封面（柔蓝渐变 + 标题两行 + 实用标签 + 署名，STHeiti Medium/Light 字体，样例代码见 2026-09-05 日志）；
- 正文的图片占位建议先替换为一行小字提示"（实拍图整理中，发布前补充）"再推，避免灰占位盒进草稿。

### 三.2 摘要（digest）规范（每篇文章强制必做）

> 规则来源：朱总 2026-09-04 指示——**所有生成的公众号文章必须同时产出摘要；推送草稿自动带摘要**。

1. **字符上限 120**（微信卡片展示上限；推送脚本已断言，手动摘要超限自动截断）
2. **不复述标题**——摘要补标题没说的信息，标题+摘要一起才是完整卖点
3. **长尾关键词密度**：每个独立名词=一个搜索入口。模板骨架：
   `地域/交通 → 核心场馆名 → 免费/费用 → 差异化看点×2-3（含"国内首创/禁止出境/百年旧址"这类稀缺标签） → 实用价值点（亲测动线/避坑提醒/盖章点/周边）`
4. **具体数字**（`216件展品`、`8月23日亲测`）比形容词可搜、可信
5. **无 emoji、无夸张词**（"天花板/保姆级/最强"一票否决）——与账号真人风格一致
6. 摘要自动生成的兜底只在没手写时生效，**投稿前人工检查**摘要是否有卖点

## 四、实测数据与坑位（2026-09-04 镇江文）

| 项 | 实测值 |
|---|---|
| draft/add content 体积 | **26843 字符成功**（传闻 2 万上限未触发，别太担心，但别超太多） |
| base64 图 | 10 张 JPEG 全部 uploadimg 成功，单张 ~100-300KB 无压力 |
| 封面 | 源图 618×1100 竖图裁 900×383 可用但画质一般；有横图优先横图 |
| 40164 | IP 白名单问题，报错信息里直接给出当前出口 IP，照抄添加即可 |
| 43002 | uploadimg 报 require POST = curl 少了 `-F`，检查脚本 |
| 微信API对内容体积无强限 | 26843 字符直接接受（传闻 2 万上限未触发），draft/add content 字段原样存富文本；**draft/get 读回的 content 字段就是真实存储（用于 API 端验证）** |
| draft/get 与 draft/delete 必须用 JSON body | `-d '{"media_id":"..."}' -H 'Content-Type: application/json'`（表单 47001 data format error） |

**img src 占位符大坑（2026-09-04 第二次推送发现的根因）**：上一版推送"排版全部丢失"的真凶——base64 替换函数返回 `src="{{IMG0}}"` 这种带前缀的字符串，覆盖到 `<img src="data:...">` 后变成 `<img src="src="{{IMG0}}""...`、BeautifulSoup 再序列化时出现 `src="src="`、`"=""` 等畸形属性。**正确做法：占位符替换时只返回 `{{IMGn}}`，原位保留 `src=""` 外壳**。结果就是 10 张图全部畸形 → 微信拿到坏 HTML 后排版整体崩。

**微信正文方言 = section/p/span（2026-09-04 第三次推送定位的终极根因）**：微信草稿存储层会把正文重新序列化成编辑器母语。**`<div>` 会被全部溶解成 p/span 并丢弃一半以上的内联样式**（实测 107 div → 0，style 235 → 126：卡片背景/边框/圆角全丢，用户视角就是"排版全没了"，但 img/h2/h3/ul 都还在）。**必须全量用 `<section>` 写块级卡片**（flex/背景/圆角在 section 上 100% 保留，往返测试 11/11）。`wx_prep_content.py` 已内置 div→section 转换 + assert 防残留。

**推送后验收 = draft/get 全量对比，不是子串检查**：比较 发送 vs 存储 的 ①各标签计数 ②style 属性计数 ③img 数。三者完全相等才算过关（本次 235→235、108 section 全等）。子串检查（"含 <h2"）会漏掉 div 溶解这类结构性损失。

**存回内容里的 `&#39;` 是微信自己的编码，不是违例（2026-09-12 澄清，别误判）**：流感疫苗稿 `draft/get` 读回后 `&#39;` 从 0 变 6，一度像是踩了"style 里写实体"的红线。定位后发现**全部落在 `font-family` 的引号上**——我们发的源码是 `font-family:-apple-system,BlinkMacSystemFont,'PingFang SC','Hiragino Sans GB','Microsoft YaHei',sans-serif`，微信存储时把裸 `'` 规范化成了 `&#39;`。**判定"样式有没有被清空"不能数 `&#39;`，要看：**
- `style=""` 空属性数 = 0（被清空的样式会退化成空属性）
- `style=` 总数与发送前**相等**（本次 236 = 236）
- 抽查 `style` 值里关键属性还在（本次 `font-size` 109 个、`border-radius` 36 个、`display:flex` 18 个全部存活）
- 纯文本 md5 完全一致（标签外文字不丢）

红线仍然成立且区分明确：**作者自己往源码 style 里写 `&#39;` 会被清空**；微信存储时**自己生成**的 `&#39;` 无害（浏览器解析属性时 `&#39;` 会解码回 `'`）。`wx_dialect_check.py` 查的是源码，所以两类不会混淆。

**最硬的验收 = 把 draft/get 读回的 content 直接渲染出来看（2026-09-12 新增）**：计数相等只能证明"没被系统溶解"，证明不了"渲染出来是对的"。做法：把 `news_item[0].content` 套进 `body{margin:0}.page{max-width:677px}` 外壳落盘 → Chrome 无头 `--no-sandbox` 截图 → PIL 切片目检。本次该法一次确认了速览卡斑马纹、PART 01 色块、剂次表、价格表全部正常。**注意：`mmbiz.qpic.cn` 有防盗链**，本地无 Referer 渲染时图片会显示成 alt 文字、高度塌陷，**这是本地假象不是坏图**；要确认图真能出，另外带 `Referer: https://mp.weixin.qq.com/` 请求 img src 看是否 `200` 且体积接近原图（本次 118927/93590/34534 字节全 200）。

**竖版手机截图不能当封面（2026-09-12）**：源 HTML 里的实拍图全是竖版手机截图（720×1501 / 720×780）时，prep 会打印"无横图候选，跳过封面生成"——这正是我们要的结果，别去强行让它裁。此时自备 900×383 文字封面（见 §十 与 2026-09-12 日志），push 时 `--cover` 传绝对路径。**封面文件同时存一份到文章同级目录**（命名 `<文章名>-封面.jpg`），便于回溯与重推。

**作者在编辑器里删内容会留"空壳"，接手前必须查（2026-09-14 实战）**：朱总用 HTML 编辑器删掉一段内容后，**外层卡片和表格行壳子会留在文件里**，肉眼在浏览器里常常看不出来。两类典型：
1. **幽灵卡片**：内容删光了，但外层 `<section style="background:#1a73e8;…">` + 内层白底 `<table>` 还在（表内只剩 6 个空 `<tr>`）。Chrome 会把空表格塌成 0 高度、看不见；但**换一个渲染器（微信后端编辑器/某些 webview）只要给空 `<tr>` 一点最小高度，就会露出一条蓝白相间的色带**。→ 整块删掉。
2. **表格斑马纹错位**：删掉数据行后留下空 `<tr>`，把 `background` 的交替节奏推错一格，出现**相邻两行同色**（本次「华兰 88元」和「上海生物 78元」两行同为 `#E3F2FD`）。空行本身不渲染，所以肉眼很容易漏。→ 删掉空 `<tr>`，并按设计意图重排（表头 `#0d47a1` 之后第一行用 `#fff`，然后 `#E3F2FD` / `#fff` 交替，末行说明用 `#F7F8FA`）。

**自查脚本**（接手用户改过的排版稿时先跑一遍）：
```python
import re
s = open(F, encoding="utf-8").read()
print("空 <tr>:", len(re.findall(r'<tr[^>]*>\s*</tr>', s)))       # 期望 0
print("空 <td>:", len(re.findall(r'<td[^>]*>\s*</td>', s)))       # 期望 0
print("空 style=:", s.count('style=""'))                          # 期望 0
```
**定位表要按内容找，不要按 CSS 属性找**：本次第一版修复脚本用 `<table[^>]*font-size:13\.5px` 定位价格表，结果**先命中了同字号的「剂次表」**、误改了它的末行配色。正确做法是遍历所有 `<table>` 区块、挑**表内文本含特征词**（如「适用年龄」）的那一张——顺便，**回滚能力比一次改对更重要**：动手前先 `cp` 一份到 `/tmp`，改错立刻还原重来。

**改完必须做像素级复检**：斑马纹这类配色问题**看缩略图会看错**（本次肉眼以为"白/蓝/白"是对的，实测像素才发现是"蓝/蓝/白"）。用 PIL 逐行采样表格右侧留白处的颜色、打印连续色带区间与高度，与预期的 `#fff` / `#E3F2FD` 序列逐段对齐才算过：
```python
prev = start = None
for y in range(y0, y1):
    c = tuple(int(v) for v in arr[y, x_blank])
    if c != prev:
        if prev is not None and y - start >= 6:
            print(f"y{start}-{y} 高{y-start} rgb{prev}")
        prev, start = c, y
```

**40164 IP 白名单判断铁律（2026-09-05 实测）**：判断"该加哪个 IP"只能以**微信 40164 报错里的 IP 为准**——`curl api.ipify.org / ifconfig.me` 走的是 WorkBuddy 沙箱代理出口（本次 20.9.176.2），与 python requests 直连 api.weixin.qq.com 的出口（58.213.75.90）不是同一个，别信 curl。家宽/代理出口会变，白名单建议保留多条历史 IP。

**封面目检（2026-09-05 阳山稿教训）**：wx_prep_content.py 自动选"loss 最小接近 2.35"的图作封面，可能不是文章主形象图（阳山稿它选了戏楼广场，主题表达弱；而父子碑身仰视图才是主形象）。**push 前必须 Read /tmp/zj_cover.jpg 目检**；不对就手动 PIL 裁（scale=max(900/w,383/h) 等比放大→居中裁 900×383，边缘 6px 自检无黑）覆盖后 --cover 传。

**图内实物文字须放大核对（2026-09-05 明文化村教训）**：AI 看缩略图/接触表会把实物文字认错（"通行大红"实为"大明通行宝钞"）。凡图注涉及照片上可见的文字，必须 Read 单张原图放大核对。

**API 往返验证是排版正确性的金标准**：先 draft/add 一个带内联样式的小样本 → draft/get 读回 → 确认 tags/样式/images URL 全部存活再推真稿。push 后再 draft/get 一次作为成稿验收。验证用过的草稿立即 draft/delete 清理（JSON body）。

**编辑器注入坑**：WorkBuddy HTML 编辑器会给所有标签注入 `data-page-node-id`，导致精确字符串 `Edit` 匹配失败——处理这类 HTML 一律用 Python 脚本改，别用逐字符串替换。

**WorkBuddy 沙箱 Edit 偶发不落盘**：本次会话多次 Edit 报成功但文件未变（grep 验证发现）。**改完脚本必须 grep/重跑验证落盘**；批量修改优先用 Write 整文件重写或 Python 字符串替换补丁。

**不要忘记"备选标题"编辑块**：HTML 排版稿里经常残留 `# 标题选项（5选1）` 或 `<div class="titles">` 这种编辑工作区备注，推送前要在源 HTML + MD 里同步删掉（项目约定 MD/HTML 同步）。

## 五、流程定位

在「探店/遛娃标准流程」中，本步骤位于 **Chrome 截图验收之后、发布之前**：
实拍 → MD初稿 → HTML排版稿 → 小红书/公众号调研 → 事实核查 → 断言同步 → 截图验收 → **草稿直推（本技能）** → 人工在后台预览确认 → 群发。

相关：`[[技能-图文创作与内容调研工具链]]`

## 六、故障排查决策树（排版丢失 / 渲染不对时按序查）

复盘自 2026-09-04 镇江文三次"排版丢失"与一次"没拉满"的完整排查（**每一步都有对应的实证样本**）。

```
用户说"排版丢了/不对"
 │
 ├─1 先看 draft/get 读回的【存储内容】≠ 我们【发送的内容】
 │    （不要只看后台编辑器/手机预览，先看存储层是否已经被改）
 │    └ 全量对比: 各标签计数 | style属性计数 | img数 → 不等 → 微信改了存储
 │        ├─ div 消失(被溶成 p/span) → 块级容器没用 section（方言规范§1）
 │        ├─ style 数骤减 → 大多也是 div 溶解附带丢样式（方言规范§1）
 │        ├─ img 还在但 src 变 data-src → 正常（微信懒加载格式，不要慌）
 │        └─ 出现 style="" → 输入端 style 里写了 &#39; 实体（方言规范§2输入坑）
 │            └ 若你走的是 draft/update 回写：几乎一定是**把 draft/get 读回的 &#39; 原样丢回去了**
 │               → 回写前先解码真实 style 属性内实体（§三''）；最容易漏的一条
 │
 ├─2 存储与发送一致，但用户还说不对
 │    ├─ position:relative/absolute 在 style 值里被剥（属性数不减、值被改）
 │    │    └ 对比存储文本里有没有 "position" 关键字（方言规范§2 禁用表）
 │    ├─ 卡片/文字看起来"没拉满/多出大段留白" → 检查嵌套容器水平 padding
 │    │    └ 外层排版 wrapper + 源 .page 两层都带 padding = 双重内边距
 │    │       prep 已归一化（方言规范§五.5）；目视用像素测量（见下）
 │    └─ 颜色/圆角等"看起来没生效" → 先怀疑微信存储时值被剥（第1、2步）
 │
 ├─3 本地复现不了微信的改动
 │    └ 渲染【存储内容】(data-src→src 替换后) 再看，别渲染发送内容
 │
 └─4 拿不准某项语法微信保不保 → 写最小样本跑 scripts/wx_dialect_test.py
      （一次一个 feature，draft/add→draft/get 看读回，测完即删）
```

**排版像素级验收（"拉满/留白/对齐"量化）**：
- Chrome 无头截图 → PIL/numpy：先放一个贴左 200px 红色块标定截图无偏移；
- 按目标颜色（如卡片底色）做"同色连续段 ≥250px 才算卡片行"，取首卡左右缘测留白；
- 陷阱：① 根容器纯白背景会让"内容边界"检测失效（要测卡片色不是背景）；② 照片像素会污染颜色匹配（用连续段长度过滤，别用单像素）；③ body 自带 margin 先清零。
- 案例数据：旧版（双重 padding 34px）卡片 x∈[45,413]；修复后 x∈[3,413] 真拉满。

相关：`[[微信排版原生方言规范]]`

---

## 七、重排既有草稿 → 另推新草稿（2026-09-10 五小终稿实操沉淀）

**场景**：用户已在草稿箱手改好文字（称"终稿"），只要求**换排版/配色**、**一个字都不改**，另推一篇新草稿，原稿（终稿＋原有草稿）全部保留。

**流程**
1. `draft/batchget`（`no_content:1`）列草稿、按标题定位；`draft/get` 取回正文存 `/tmp/draft_*.html`。
2. 重排脚本**按"角色"重写内联样式**（只动 `style`，不碰文本节点）：
   - 小标题 → 主题色 + 左色条；正文 → 白底黑字；提示卡 → 浅底 + 左色条；表格 → 细边框 + 浅表头；图注 → 灰色居中
   - **图片**：`data-src`（微信懒加载）还原为真实 URL；若重新上传，用本地原图映射 `{{IMGn}}` 占位交给 push
   - 清编辑器注入：`data-*`、`class`、`leaf`、`textstyle`；清 `&#39;` 实体（改写字面引号）
3. **文本零变化断言（铁律）**：变换前后各取 `BeautifulSoup(...).get_text()` 去空白比对，不等即 `sys.exit(1)`——保证"一字不改"。
4. `wx_dialect_check.py` 校验 → Chrome 无头截图目检 → 常规 `wx_prep/push` 推送**新草稿**。
5. `draft/get` 复查：**存储文本 == 终稿文本**（证明未改字）；`batchget` 复查原草稿 `update_time` 未变（证明未动原稿）。

**坑位**
- **`text-align:center` 传染**：判"图片居中容器"必须看**直接子元素**是否含 `<img>`（`any(getattr(c,'name',None)=='img' for c in el.children)`）；用 `el.find('img')` 会把包裹全篇的大容器误判成图片容器 → 全篇居中错位。
- **分享卡标题 64 字节上限**：长标题（>21 汉字）会被分享卡截断，长版留给文内 H1，另起短版作 `--title`。
- **`draft/get` 的 `title`/`digest` 属元数据**：重排按"不改"原则原样沿用最稳。

---

## 八、查询"已发布"内容：API 查不到，只能走后台网页（2026-09-11 实测）

**结论：AppID/AppSecret 无法枚举已发布文章。**

| 接口 | 结果 | 说明 |
|---|---|---|
| `cgi-bin/freepublish/batchget` | **48001 api unauthorized** | 本账号（个人订阅号）无"发布能力/发表记录"接口权限 |
| `cgi-bin/material/get_materialcount` | `news_count: 0` | 群发图文**不会**自动进永久素材库，无从枚举 |
| `cgi-bin/draft/batchget` | ✅ 正常（本次 60 篇） | 只能拿到**草稿**，不是已发布 |

即：**"写"的能力齐全（token / uploadimg / draft/add / add_material），"读已发布"的能力缺失。**

**正确姿势 —— 后台网页「内容与互动 → 发表记录」+ ego-browser 扫码**：

```bash
launchctl asuser 501 ego-browser nodejs <<'EOF'   # Bash 工具需 dangerouslyDisableSandbox=true
const task = await useOrCreateTaskSpace('公众号发表记录_时间戳')
await openOrReuseTab('https://mp.weixin.qq.com/', { wait: true, timeout: 40 })
// 展开扫码登录（首页若记住过微信号会默认显示"微信快捷登录"，两种都要用户手机在场）
await js(String.raw`(() => { const a=[...document.querySelectorAll('a')].find(e=>(e.textContent||'').trim()==='扫码登录'); if(a){a.click(); return 'ok';} return 'nf'; })()`)
// 同源 fetch 拿二维码原图（472×472），落地给用户扫
const b64 = await js(String.raw`(async () => {
  const img=document.querySelector('img.login__type__container__scan__qrcode');
  const r=await fetch(img.src,{credentials:'include'}); const b=await r.blob();
  return await new Promise(res=>{const fr=new FileReader();fr.onload=()=>res(fr.result);fr.readAsDataURL(b);});
})()`)
cliLog(b64)
EOF
```

**坑位**
- **`cliLog` 写到 stderr**：重定向时别只接 stdout，否则 base64 会"消失"。
- **二维码数分钟即过期**：必须"先把图给用户、让用户立刻扫"，隔轮再给基本等于白给。
- 「微信快捷登录」按钮在 iframe 内，必须用 `click('@ref')` 的 ref 方式点，按坐标点会落空（getBoundingClientRect 返回 0）。
- 落地 base64 用 `re.search(r"data:image/\w+;base64,...")` 解码成 PNG 再 `present_files` 展示；校验真伪可看灰度唯一值数（真二维码=2 个值）。

---

## 九、从别人文章里搬"二维码/海报"进自己正文（2026-09-11 实测）

**场景**：原文写着"长按海报扫描二维码"，要把那张海报（含二维码）搬进自己的文章。

**① 抓原图 URL（关键坑：data-src 是转义形式）**
抓 `mp.weixin.qq.com/s/xxx` 的 HTML 后，图片真实地址在 `data-src` 里，但**正文 HTML 被 `\xNN` 转义过**（`\x3cimg`= `<img`、`\x22`= `"`），直接用 `data-src="` 正则会漏掉正文区。先反转义再解析：

```python
u = re.sub(r'\\x([0-9a-fA-F]{2})', lambda m: chr(int(m.group(1),16)), html)
seg = u[u.find("礼品领取操作指南") : u.find("第二弹")]      # 用上下文文本定位区间
urls = re.findall(r'data-src="([^"]+)"', seg)
```

取原图：把 URL 尾部 `/640?wx_fmt=jpeg` 换成 `/0?wx_fmt=jpeg`（必须带 `Referer: https://mp.weixin.qq.com/`）。

**② 定位并验证二维码可扫（别只靠肉眼）**
用 `cv2.QRCodeDetector().detectAndDecodeMulti(img)` 拿到框 + 解码文本。**解码成功 = 读者一定扫得动**；顺手把结果记下来（本次解出活动页 `https://h.zjsnews.cn/2026/09/draw/`）。注意一张图常含**多个码**：活动海报上的码进活动页，操作指南步骤图上的码是"关注公众号"（`weixin.qq.com/r/...`），别搬错。

**③ 嵌入方式**
用占位符 `{{POSTER_B64}}` 写进 HTML，再用 Python 注入 `base64`——**不要直接把几百 KB base64 塞进 Write/Edit**。`wx_prep_content.py` 会自动抽成 `/tmp/zj_img_N.jpg` 并在 push 时走 `uploadimg`，所以 base64 不会进 `draft/add`。

**④ 纯海报是竖图，不会自动当封面**
prep 的封面貌似只挑横图，竖版海报会提示"无横图候选，跳过封面生成"——仍需自备 `--cover`。

---

## 十、排版稿自检：无头渲染探针（2026-09-12 新）

**问题**：内嵌 base64 图后，光看 `img` 计数=3 不能证明图片**真的渲染出来了**（目录错、`data:` 前缀写坏、alt 与文件不符都会计数正常但显示裂图）。而 Chrome 截图 + 切片目检依赖 Read 看图，某些环境下会被"不支持图片"过滤掉，目检不可靠。

**解法**：让浏览器自己报出每张图的布局盒。做法是**复制一份临时 HTML 注入探针脚本**（绝不改交付稿），再用 `--dump-dom` 读出脚本写进 DOM 的结果：

```bash
# 1) 复制交付稿 -> /tmp/probe.html，在 </body> 前插入探针
#    探针脚本（vanilla JS）：
#    window.addEventListener('load', function(){
#      var out=[];
#      document.querySelectorAll('img').forEach(function(el){
#        var r=el.getBoundingClientRect();
#        out.push('IMG '+el.getAttribute('alt')+' y='+Math.round(r.y+scrollY)
#                 +' w='+Math.round(r.width)+' h='+Math.round(r.height)
#                 +' nat='+el.naturalWidth+'x'+el.naturalHeight+' ok='+el.complete);
#      });
#      out.push('BODY_H='+document.body.scrollHeight);
#      document.getElementById('__probe').textContent = out.join('\n');
#    });
# 2) 跑无头并 grep 探针输出
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --headless=new --no-sandbox --disable-gpu --virtual-time-budget=4000 \
  --window-size=677,1000 --dump-dom "file:///tmp/probe.html" 2>/dev/null \
  | python3 -c "import sys,re,html;d=sys.stdin.read();m=re.search(r'<pre id=\"__probe\"[^>]*>(.*?)</pre>',d,re.S);print(html.unescape(m.group(1)))"
```

**判读标准**：`ok=true` 且 `nat=720x1501` 这类真实像素（而不是 `nat=0x0`）→ 图加载成功；`w/h` 是实际占位尺寸，顺带验两图并排是否各占 48.5%、单图是否满宽。

**顺带**：`BODY_H` 直接给出整页高度，用来判断某张图是否"占了一屏半"——本次就是靠它发现全宽竖图 1411px 太高，裁剪到 733px，整页从 9345px 降到 8667px。

**渲染失败排查补充**：本机 Chrome 无头必须加 `--no-sandbox`（否则 `sandbox initialization failed` + GPU 进程退出，截不出图）。

**手机竖图入正文前先裁**：手机截图原始比例常是 1080×2400（约 1:2.2），整张塞进 677px 宽的正文会被放大成 1400px+ 的巨幅。按信息区裁掉导航栏、空白与底部按钮（本次 1501→780px，`crop` 后 `resize(720, LANCZOS)` + `quality=88` 约 43KB），图注写"××截图 · 日期"。

**手机实拍竖图的裁剪基线（2026-09-13 S3号线稿实测）**：手机原片 1599×2844（1:1.78）整张入正文高约 1200px，占一屏半。经验基线：
- **常规叙事图裁到宽高比 0.72-0.83**（头图裁掉顶部 26% 天空、孩子趴窗图裁顶部 22%），全宽 677px 下高度落在 810-940px；
- **本身呈横条状的图直接裁成横图更好**（站台线路带、横排招牌、长队）：本次站台线路图裁成 1.39:1，高度 488px，整页 `BODY_H` 从 5429px 降到 5044px；
- 裁完用探针/截图测 `BODY_H` 复核；图注一律"主体（关键补充）· 日期实拍"。

---

## 十一、配图全流程：Wikimedia Commons CC 实拍（2026-09-12 江苏文旅口号两篇实测）

> 适用：文章无实拍图时，用 Commons 上 CC0/CC BY/CC BY-SA 的地标实拍（合法可商用，图注带「作者+许可证」署名）。API 免 key。

**① 检索**：`commons.wikimedia.org/w/api.php`，`action=query&list=search&srnamespace=6`（File 命名空间）。**连续请求会被限流**（返回空或非 JSON）：每次间隔 1.5~2s + 失败重试 3~4 次；`srsearch` 支持中文关键词（"花果山""项王故里""高淳老街"均命中），冷门县区命中率低，按"能找到才配"取舍。

**② 取信息与下载**：`prop=imageinfo&iiprop=url|extmetadata|size&iiurlwidth=1100` → `thumburl`（1100px 缩略图，正文够用）+ `extmetadata.LicenseShortName/Artist`（Artist 是 HTML，须去标签）。**含撇号/特殊字符的文件名**（如 `Père David's Deer`）单独重试，首次下载失败常见。

**③ 接触表目检（强制）**：PIL 拼 3×4 缩略网格一次 Read。实测淘汰两类：NASA 卫星遥感图（搜 "Taihu" 第一条是卫星图）、主体不可见图（麋鹿缩略图里看不到麋鹿）。换图重下再目检。

**④ 署名图注**：`图：{caption}（Wikimedia Commons · {artist} · {license}）`，11px 灰色，放图片正下方。CC0/PD 可只写 "Wikimedia Commons · Public domain"。

**⑤ 生成器模式**：大 HTML 用 Python 脚本 + imgmap.json（{地区: {file, credit, caption}}）拼装 base64，勿手写。**`%` 转义坑**：参与 `%` 格式化的字符串里写 `%%`，**不参与格式化的字符串里写单个 `%`**——本次 gradient `0%%` 原样输出成非法 CSS（白底白字），img `width:100%%` 反而必须写 `%%`。生成后 grep `linear-gradient(.*%%)` 自查。

**⑥ 截图验收的 Chrome 500px 坑（重要）**：macOS Chrome headless **最小窗宽≈500px**，`--window-size=414` 会被钳制到 500 渲染、截图却按 414 裁 → 出现"右侧文字被裁"假象（注入 JS 读 `clientWidth` 可证实 VW=500）。**验证手机宽度：`body` 设 `width:390px; overflow:hidden` + `--window-size=500`**，裁左侧 390 目检。必须 `--headless=new --no-sandbox`（无 --no-sandbox 截不出图）。

**⑦ 推送链路补充坑**：
- `wx_prep_content.py` 已修：无 `<style>` 块的全内联稿不再崩溃（判空）。
- **prep 会自动重裁封面并覆盖 `/tmp/zj_cover.jpg`**——自备封面必须在 prep **之后**再写入（prep 优先选最宽横图，常非文章主形象）。
- 标题（--title）走分享卡 64 字节上限：>21 汉字被截断，完整标题留文内 H1，短版作 --title（如"江苏13市文旅口号大PK，你家乡排第几？"≈53 字节）。
- draft/get 验收读回的 `&#39;` 若全部位于 font-family 值内 = 微信对字面引号的正常归一化（§三），非致命；致命场景是**发送前** style 里就有实体。
- 本文两篇产物生成器：`/tmp/js_slogan/build_html.py`、`build_county.py`（会话级临时，模式照 §六 即可复刻）。

**⑧ 红线：删除/替换草稿前必须先存档，严禁擅自 `draft/delete`（2026-09-14 事故）**

- 事故：用户说"重推草稿"，直接 `draft/delete` 旧稿 + `draft/add` 新稿 → **用户在该草稿上做过的人工修改全部丢失**。微信官方明确"草稿删除后不可恢复、无回收站"；被删 media_id 再 `draft/get` 返回 `40007 invalid media_id`；素材库也查不到手工上传的图。
- **增量更新 SOP（一律禁止"直接删旧稿 + 重推"）**：
  1. **先拉档**：动任何已有草稿之前，先 `draft/get` 把**平台当前版本**完整存到本地（`title/digest/content/content_source_url/thumb_media_id` → `/tmp/draft_backup_<media_id>_<ts>.json`）。
  2. **再对比**：平台版 vs 本地待推版逐项 diff，**识别出用户在平台上的手工改动**（本地稿不会有——这是丢稿的根因）。
  3. **合并增量**：把平台版的改动**并入**新稿（= 本地新内容 + 用户手工改动，二者都不能丢）。
  4. **最后才删 + 推**：合并确认无误、且经用户同意后，才 `draft/delete` 旧稿 + `draft/add` 新稿；**能 `draft/update` 就地增量更新的，优先 update、不删稿**（`{media_id, index:0, articles:{...}}`，保留草稿本体与平台"历史版本"）。
  5. 局部改动（换封面、改摘要、补一段）一律 `draft/update`，**不要 delete+add**；验收若发现平台版与本地版不一致（标题/图片数对不上），先怀疑"用户在平台上改过"，**停下来问，绝不覆盖**。

---

## 十二、本地渲染目检与长截图切片（可选前置验收）

在执行直推前，如需对长篇 HTML 排版稿进行全景视觉目检：

```bash
# 1. 调用系统 Chrome Headless 渲染超长页面
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless   --screenshot=/tmp/verify_full.png --window-size=900,28000 --hide-scrollbars   "file:///绝对路径/文章-排版.html"

# 2. 调用托管 Python PIL 切片逐屏目检
python3 -c "
from PIL import Image
im = Image.open('/tmp/verify_full.png')
w, h = im.size
slice_h = h // 12
for i in range(12):
    box = (0, i * slice_h, w, min((i + 1) * slice_h, h))
    im.crop(box).save(f'/tmp/slice_{i+1:02d}.png')
print('12 slices saved to /tmp/slice_*.png')
"
```

---

## 十三、能力总览与权限现实（2026-09-16 实测）

本技能已从「HTML 直推草稿」单点工具，扩展为**草稿 / 发布 / 数据分析三模块内容中台**。
新增三个 CLI + 一个共享底座，**原有 HTML 直推链路（`wx_prep_content.py` → `wx_dialect_check.py` → `wx_push_draft.py` → `wx_pipeline.py`）完全保留、逻辑未动**。

### 13.1 脚本清单

| 脚本 | 角色 | 覆盖能力 |
|---|---|---|
| [`scripts/wx_common.py`](./scripts/wx_common.py) | **共享底座**（新） | 凭据解析、`stable_token` 优先 + 磁盘缓存的 token、统一 HTTP、errcode 中文翻译、JSON/CSV 落盘 |
| [`scripts/wx_draft.py`](./scripts/wx_draft.py) | **草稿模块 CLI**（新） | `list` `count` `get` `add` `update` `delete` `restore` `diff` `backup` `switch` `product-card` `selftest` |
| [`scripts/wx_publish.py`](./scripts/wx_publish.py) | **发布模块 CLI**（新） | `submit` `status` `list` `getarticle` `delete` `selftest` |
| [`scripts/wx_stats.py`](./scripts/wx_stats.py) | **数据分析 CLI**（新） | 21 个 datacube 接口 + `users` `daily` `list` `webplan` `selftest` |
| `scripts/wx_prep_content.py` | 原有流水线 | HTML 预处理（抽图/CSS 内联/裁封面） |
| `scripts/wx_dialect_check.py` | 原有流水线 | 微信原生方言合规校验 |
| `scripts/wx_push_draft.py` | 原有流水线 | 上传图片/封面 → `draft/add` 或 `draft/update` |
| `scripts/wx_pipeline.py` | 原有流水线 | 单命令一键直推（7 步闭环） |
| `scripts/wx_dialect_test.py` | 原有工具 | 最小样本跑微信往返属性测试 |

#### 13.1.1 新脚本的统一 CLI 约定

三个新脚本（`wx_draft.py` / `wx_publish.py` / `wx_stats.py`）接口风格一致，记住这五条即可：

- **`--json <path>`**：把原始返回写入 JSON 文件。**位置随意** —— 写在子命令前（`--json a.json list`）
  或子命令后（`list --json a.json`）都行。`--json -` 表示打印到标准输出（排查时用）。
  **不给 `--json` 时输出是全安静的**：命令只打印人类可读摘要，不会喷出大块原始 JSON。
- **`--csv <path>`**（仅 `wx_stats.py`）：写 CSV，嵌套字段自动扁平化（`detail.read_user` → `read_user`，
  `read_user_source[]` 序列化为 JSON 字符串）。用 `utf-8-sig` 编码，Excel 直接打开不乱码。
- **`selftest`**：三个脚本都有。**养成"先探权限再干活"的习惯**，省去在无权限接口上试错的时间。
- **所有 `delete` 类子命令默认只演练**（只备份 + 打印目标），必须显式 `--yes` 才真正执行。
- **退出码约定**：`0` 成功 ｜ `1` 接口报错（会打印 errcode 中文解释）｜ `2` 凭据缺失 ｜ `130` 用户中断。

### 13.2 权限实测表（关键结论，别踩空）

本仓库主用账号为**个人订阅号**（AppID `wxa8f9****924f`）。2026-09-16 用 `selftest` 逐个实测：

| 模块 | 接口 | 实测结果 | 说明 |
|---|---|---|---|
| **草稿** | `draft/count`、`draft/batchget`、`draft/get`、`draft/add`、`draft/update`、`draft/delete` | ✅ **可用**（实测草稿总数 49 篇） | 草稿箱能力不受账号类型限制，是当前最可靠的接口面 |
| 草稿·商品卡片 | `/channels/ec/service/product/getcardinfo` | ❌ `-1 system error` | 需先开通带货/电商能力；本账号未开通 |
| 草稿·开关 | `draft/switch` | ⚠️ 官方已废弃 | 草稿箱与发布功能已全量开放，无需设置开关。脚本保留只读探测 |
| **发布** | `freepublish/batchget`（权限集 7 整体） | ❌ **48001 未授权** | 官方明确：2025 年 7 月起，个人主体账号、企业主体未认证账号被**回收发布接口权限** |
| **数据** | 全部 21 个 `datacube/*` | ❌ **48001 未授权**（可用 0 / 未授权 21） | 数据接口「向所有**认证**公众号开发者开放」，个人订阅号无法认证 |

**由此推出的作业原则**：
1. **写文章 → 推草稿 → 后台人工群发**，这是当前唯一可全自动跑通的链路；
2. **发布（freepublish）与数据（datacube）两步走接口**，在本账号上**必须**改走后台网页（用 ego-browser 携登录态，姿势沿用 §八）；
3. 脚本层面能力已写全，**等账号类型变化（认证/企业主体）即可直接启用**，无需改代码。

### 13.3 任务 → 命令 决策树

```
我要做什么？
 ├─ 把排版好的 HTML 推进草稿箱 ────────→ wx_pipeline.py --html xxx-排版.html --update-auto   （§三）
 ├─ 看草稿箱里有什么 ─────────────────→ wx_draft.py list / count
 ├─ 取回某篇草稿正文 ─────────────────→ wx_draft.py get --media-id <ID>      （自动落备份+HTML）
 ├─ 只改标题/摘要/封面，正文不动 ──────→ wx_draft.py update --media-id <ID> --digest "…"
 ├─ 删草稿 ──────────────────────────→ wx_draft.py delete --media-id <ID>     （默认演练，--yes 才删）
 ├─ 本地版和平台版对不上，想知道差在哪 → wx_draft.py diff --media-id <ID> --vs xxx-排版.html
 ├─ 误删了想恢复 ────────────────────→ wx_draft.py restore --backup <备份JSON>
 ├─ 发布/查看已发布列表 ─────────────→ wx_publish.py selftest（先探权限）；无权限走 §八 后台网页
 ├─ 拉阅读/涨粉等数据 ───────────────→ wx_stats.py selftest（先探权限）；无权限走 wx_stats.py webplan
 └─ 查某个接口的跨度上限/是否停维护 ──→ wx_stats.py list
```

---

## 十四、草稿模块全能力手册（draft/*）

### 14.1 接口矩阵（官方草稿管理 7 个 + 商品卡片 1 个）

| 接口 | 路径 | 备注 |
|---|---|---|
| 新增草稿 | `POST /cgi-bin/draft/add` | body `{"articles":[article]}` —— **articles 是数组** |
| 更新草稿 | `POST /cgi-bin/draft/update` | body `{"media_id","index","articles":{…}}` —— **articles 是对象**（与 add 相反，易错点） |
| 获取草稿详情 | `POST /cgi-bin/draft/get` | body `{"media_id"}`；返回 `news_item[]` |
| 获取草稿列表 | `POST /cgi-bin/draft/batchget` | body `{"offset","count"(1-20),"no_content"(0/1)}` |
| 获取草稿总数 | `GET /cgi-bin/draft/count` | 返回 `total_count`，只计数不返回内容 |
| 删除草稿 | `POST /cgi-bin/draft/delete` | body `{"media_id"}`；**不可撤销、无回收站** |
| 草稿箱开关 | `POST /cgi-bin/draft/switch` | **已废弃**；`&checkonly=1` 为只查状态 |
| 商品卡片 DOM | `POST /channels/ec/service/product/getcardinfo` | body `{"product_id","article_type","card_type"}`；返回 `product_key` 或 `DOM` |

**article 字段限制（本地已前置校验，见 `wx_draft.py::validate_article`）**：
`title` ≤32 字 ｜ `author` ≤16 字 ｜ `digest` ≤120 字 ｜ `content` <2 万字符且 <1M（⚠️ 实测 26843 字符可通过，故超限只告警不阻断）
`article_type` 为 `news`（图文消息）时 `thumb_media_id` 必填；为 `newspic`（图片消息）时用 `image_info.image_list[].image_media_id`（≤20 张，首张即封面），且正文只支持纯文本与商品标签（商品 ≤50 个）。
`cover_info.crop_percent_list[].ratio`：图文消息仅支持 `2.35_1`/`1_1`；图片消息支持 `1_1`/`16_9`/`2.35_1`。

**高频错误码**：`40007` media_id 无效（草稿已被删）｜`40114` index 越界｜`41039` content_source_url 不合法｜`45166` content 不合法｜`47001` 格式错误（必须 JSON body）｜`53404/53405/53406` 带货相关。

### 14.2 CLI 用法

```bash
PY=/Users/zhugx/.workbuddy/binaries/python/envs/default/bin/python3
D=/Users/zhugx/src/skills/mp-publish/scripts/wx_draft.py

$PY $D selftest                                  # 能力自检（草稿数 / 权限）
$PY $D count                                     # 草稿总数
$PY $D list --count 20                           # 草稿列表（默认 no_content=1，快）
$PY $D list --count 20 --with-content --json /tmp/drafts.json
$PY $D get --media-id M9xxx                      # 详情 + 自动备份（JSON 与 HTML 双落盘）
$PY $D backup --media-id M9xxx                   # 只拉档，不做任何写操作

# 新增：从文件 / 参数 / 克隆已有草稿
$PY $D add --title "标题" --content-file /tmp/wx_wechat_content.html \
           --thumb-media-id <永久素材ID> --digest "≤120字摘要"
$PY $D add --article-file /tmp/article.json --dry-run      # 先看 payload 再决定
$PY $D add --from-draft M9xxx --index 0                    # 克隆为新草稿

# 更新：默认「字段级合并」，只改你点名的字段，其余沿用平台当前版本
$PY $D update --media-id M9xxx --digest "新的SEO摘要"
$PY $D update --media-id M9xxx --thumb-media-id NEW_THUMB   # 只换封面
$PY $D update --media-id M9xxx --title "新标题" --dry-run    # 先预览再执行

# 删除 / 恢复 / 对比
$PY $D delete --media-id M9xxx            # 演练：只备份，不删
$PY $D delete --media-id M9xxx --yes      # 真删（先自动备份）
$PY $D restore --backup ~/.cache/weixin/draft_backups/pre-delete_M9xxx_*.json
$PY $D diff --media-id M9xxx --vs "待发布/xxx-排版.html"
```

**备份落在哪**：`~/.cache/weixin/draft_backups/`，命名 `<用途>_<media_id>_<时间戳>.json|_idxN.html`。
用途标签：`get` / `manual` / `dryrun` / `pre-delete` / `pre-update` / `post-update`。

### 14.3 三条安全护栏（对应 §十一⑧ 的历史事故，已工程化）

1. **删除不可逆 → 默认演练**：`delete` 不带 `--yes` 只做备份并打印目标，不执行删除。
   微信官方明确「草稿删除后不可恢复、无回收站」，被删的 media_id 再 `draft/get` 返回 `40007`。
2. **回写丢手改 → 字段级合并**：`update` 默认行为是「先 `draft/get` 拉平台版 → 只覆盖你显式指定的字段 → 回写」，
   因此**用户在后台的手工改动不会丢**。整篇覆盖必须显式加 `--replace-all`，否则脚本直接拒绝执行。
   写前自动备份（`pre-update`），写后自动回读验收（`post-update` + 打印 `style=`/空 style 计数）。
3. **回写被清空样式 → 自动解码实体**：`draft/get` 读回的内容里，微信会把裸 `'` 规范化成 `&#39;`；
   原样回写会让微信把该 `style` 整段清空成 `style=""`（§三'' 的铁律）。脚本在**所有写路径**
   （`add` / `update` / `restore`）统一调用 `decode_style_entities()`，把真实 `style="…"` 属性内的
   `&#39;` `&#34;` `&quot;` `&amp;` 解码回裸字符后再提交。

### 14.4 商品卡片（带货账号才可用）

```bash
$PY $D product-card --product-id 1000000000 --article-type news --card-type 0 --save-dom /tmp/card.html
```
- 卡片类型：`0` 大卡 ｜ `1` 小卡 ｜ `2` 文字链接 ｜ `3` 条卡
- **支持范围**：图文消息（news）支持大卡/小卡/文字链接；图片消息（newspic）支持小卡/文字链接/条卡
- 用法：图文消息拿到的 `DOM` **贴进 content 即插入卡片**；图片消息等类型用 `product_key`，
  写到 article 的 `product_info.footer_product_info.product_key`（文末插入商品）
- 本账号实测 `-1 system error`：**未开通带货能力**，需先在后台开通电商/带货

---

## 十五、发布模块全能力手册（freepublish/*）

### 15.1 接口矩阵与状态机

| 接口 | 路径 | 关键点 |
|---|---|---|
| 发布草稿 | `POST /cgi-bin/freepublish/submit` | body `{"media_id"}`；返回 `publish_id`、`msg_data_id` |
| 发布状态查询 | `POST /cgi-bin/freepublish/get` | body `{"publish_id"}`；返回 `publish_status`、`article_id`、`article_detail` |
| 获取已发布列表 | `POST /cgi-bin/freepublish/batchget` | body `{"offset","count"(1-20),"no_content"}`；返回 `article_id` 与 `news_item[]` |
| 获取已发布图文 | `POST /cgi-bin/freepublish/getarticle` | body `{"article_id"}`；返回 `news_item[]`（含正文、`thumb_url`、`is_deleted`） |
| 删除已发布文章 | `POST /cgi-bin/freepublish/delete` | body `{"article_id","index"}`；`index` 不填/填 0 = **删全部文章**，**不可逆** |

**`publish_status` 状态机（`wx_publish.py status` 会译成中文）**：

| 值 | 含义 | 该做什么 |
|---|---|---|
| 0 | 成功 | 记下 `article_detail.item[].article_url`（永久链接） |
| 1 | 发布中 | 用 `--wait` 轮询到终态，别急着下结论 |
| 2 | 原创失败 | 看 `fail_idx`，到后台处理该篇原创声明后重发 |
| 3 | 常规失败 | 同上 |
| 4 | 平台审核不通过 | 看 `fail_idx`，内容整改后重发 |
| 5 | 成功后用户删除所有文章 | 已发布内容被删 |
| 6 | 成功后系统封禁所有文章 | 内容被平台封禁 |

**易错点**：`submit` 返回 `errcode=0` **只代表任务提交成功**，不代表已发布完成 —— 仍可能因原创声明失败、
平台审核不通过而最终失败。官方还会向后台配置的开发者 URL 推送 `PUBLISHJOBFINISH` 事件
（XML，含 `publish_id`/`publish_status`/`article_id`/`fail_idx`），可用于异步回调，不必死轮询。
`submit` 的常见报错：`53503` 草稿未通过发布检查 ｜ `53504` 需前往公众平台官网使用草稿 ｜ `53505` 请手动保存成功后再发表。

### 15.2 CLI 用法

```bash
P=/Users/zhugx/src/skills/mp-publish/scripts/wx_publish.py

$PY $P selftest                                   # 先探权限（本账号会得到 48001）
$PY $P submit --media-id M9xxx                    # 提交发布，拿到 publish_id
$PY $P status --publish-id 100000001 --wait       # 轮询到终态（默认 5s 间隔、最长 120s）
$PY $P list --count 20                            # 已发布列表
$PY $P list --count 20 --search 遛娃              # 关键词本地过滤
$PY $P getarticle --article-id ARTICLE_ID --save-html
$PY $P delete --article-id ARTICLE_ID             # 演练（只备份）
$PY $P delete --article-id ARTICLE_ID --yes       # 真删
```
备份落在 `~/.cache/weixin/publish_backups/`。

### 15.3 本账号无权限时的替代路径

本账号 `freepublish/batchget` 实测 **48001**，意味着 `submit/status/getarticle/delete` 一并不通（权限集 7 整体授予）。
**发布与"查已发布"改走后台网页**，姿势见 §八（ego-browser 扫码 + 同源 fetch）。
另外注意 §八 已实测的两条补充：`cgi-bin/material/get_materialcount` 的 `news_count` 为 0（群发图文**不会**自动进永久素材库），
所以「枚举已发布文章」只能靠后台「内容与互动 → 发表记录」。

---

## 十六、数据分析模块全能力手册（datacube/*）

### 16.1 21 个接口与跨度上限

**用户数据（2）** —— 属「用户管理」权限
| 接口 | 路径 | 跨度 | 关键返回字段 |
|---|---|---|---|
| `getusersummary` | `/datacube/getusersummary` | ≤7 天 | `ref_date` `user_source`(渠道) `new_user` `cancel_user` |
| `getusercumulate` | `/datacube/getusercumulate` | ≤7 天 | `ref_date` `cumulate_user` |

`user_source` 渠道取值：`0` 其他合计 ｜`1` 公众号搜索 ｜`17` 名片分享 ｜`30` 扫描二维码 ｜`57` 文章内账号名称 ｜`100` 微信广告 ｜`161` 他人转载 ｜`149` 小程序关注 ｜`200` 视频号 ｜`201` 直播。

**图文数据（10）** —— 属「群发与通知」权限。★ = 官方已停止维护
| 接口 | 路径 | 跨度 | 备注 |
|---|---|---|---|
| ★`getarticlesummary` | `/datacube/getarticlesummary` | 1 天 | 某天被阅读过的**群发**文章当日数据 |
| ★`getuserread` | `/datacube/getuserread` | 1 天 | 含 `user_source` 区分渠道与全部；原文页阅读/收藏只给「全部」 |
| ★`getuserreadhour` | `/datacube/getuserreadhour` | 1 天 | 带 `ref_hour` |
| ★`getusershare` | `/datacube/getusershare` | 1 天 | `share_scene`：1 好友转发 / 2 朋友圈 / 255 其他 |
| ★`getusersharehour` | `/datacube/getusersharehour` | 1 天 | 带 `ref_hour` |
| ★`getarticletotal` | `/datacube/getarticletotal` | 1 天 | 群发日起**累计**总量，最多统计发表后 7 天；`details[]` 按 `stat_date` 展开 |
| `getarticleread` | `/datacube/getarticleread` | 1 天 | 发表内容每日阅读；`detail.read_user_source[]` 含场景（全部/公众号消息/聊天会话/朋友圈/公众号主页/其他/推荐/搜一搜） |
| `getarticleshare` | `/datacube/getarticleshare` | 1 天 | 发表内容每日分享；`detail.share_user` |
| `getbizsummary` | `/datacube/getbizsummary` | **≤30 天** | 汇总概览：阅读/分享/爱心赞/拇指赞/留言/收藏/跳转原文/发布篇数 |
| `getarticletotaldetail` | `/datacube/getarticletotaldetail` | 1 天 | 逐篇详情：含**赞赏金额、阅读后关注、阅读送达率、阅读完成率、平均阅读时长、跳出位置分布** |

**消息数据（7）** —— 属「消息管理」权限
| 接口 | 路径 | 跨度 |
|---|---|---|
| `getupstreammsg` | `/datacube/getupstreammsg` | <7 天 |
| `getupstreammsgweek` | `/datacube/getupstreammsgweek` | **必须同一天** |
| `getupstreammsgmonth` | `/datacube/getupstreammsgmonth` | **必须同一天** |
| `getupstreammsghour` | `/datacube/getupstreammsghour` | 1 天 |
| `getupstreammsgdist` | `/datacube/getupstreammsgdist` | ≤15 天 |
| `getupstreammsgdistweek` | `/datacube/getupstreammsgdistweek` | ≤15 天 |
| `getupstreammsgdistmonth` | `/datacube/getupstreammsgdistmonth` | ≤15 天 |

`msg_type`：1 文字 / 2 图片 / 3 语音 / 4 视频 / 6 第三方应用消息（链接消息）。
`count_interval`（发送量分布）：0 =「0」/ 1 =「1-5」/ 2 =「6-10」/ 3 =「10 次以上」。
周/月数据的 `ref_date` 是**周期首日**（当月 1 日或周一），且**必须在该周期结束后**才能取到。

**接口数据（2）** —— 属对应权限集（被动回复相关）
| 接口 | 路径 | 跨度 | 关键字段 |
|---|---|---|---|
| `getinterfacesummary` | `/datacube/getinterfacesummary` | ≤30 天 | `callback_count` `fail_count` `total_time_cost` `max_time_cost` |
| `getinterfacesummaryhour` | `/datacube/getinterfacesummaryhour` | 1 天 | 同上 + `ref_hour` |

**广告分析**：官方独立说明页（`…/analysis_data/ad/Ad_Analysis`），无独立接口清单，按需查阅。

### 16.2 CLI 用法

```bash
S=/Users/zhugx/src/skills/mp-publish/scripts/wx_stats.py

$PY $S list                                       # 21 个接口 × 跨度 × 维护状态总览
$PY $S selftest                                   # 逐接口权限自检（本账号：21 个全 48001）
$PY $S webplan                                    # 无权限时的后台网页替代路径

$PY $S fetch getusersummary --days 7              # 最近 7 天用户增减（自动按 7 天分段）
$PY $S fetch getbizsummary --begin 2026-09-01 --end 2026-09-15    # ≤30 天
$PY $S fetch getuserread --date 2026-09-15 --csv /tmp/read.csv
$PY $S fetch getarticletotaldetail --date 2026-09-15 --json /tmp/d.json
$PY $S users --days 30                            # 用户增减+累计联合报表（含净增）
$PY $S daily                                      # 昨日核心指标一览（用户+发表内容+消息）
```

**自动分段与自适应降级**：脚本按注册表里的跨度上限自动切段逐段拉取并合并；
若仍收到 `61501`/`61500`（跨度超限），会把分段跨度**自动减半重试**（打印「[降级]」提示），无需人工干预。
`--span N` 可手动指定分段跨度。

### 16.3 官方注意事项（务必内化）

1. 数据仅存 **2014-12-01 之后**；更早日期即使有值也是不可信脏数据。
2. **每天 8 点后**查询前一天数据才是完整的（否则 `61503 data not ready`）。
3. **阅读量总和 < 3 的图文不会被统计** —— 小号数据为空是正常现象，不是脚本 bug。
4. 「发表内容」新接口族（`getarticleread`/`getarticleshare`/`getbizsummary`/`getarticletotaldetail`）数据**起始 2025-11-01**，更早日期无效。
5. 数据可能延迟，返回体的 **`is_delay=false` 才表示已是最新**。
6. 官方要求开发者**自行落库缓存**（既提速也降低微信侧接口损耗）—— 建议把 `--json/--csv` 产物归档。
7. `getarticletotal` 的 `details[]` 里，每天对应的是**到该日为止的累计量**，不是当日增量。
8. `getarticlesummary`（当日增量）与 `getarticletotal`（发表起累计，最多 7 天）语义不同，别混用。

### 16.4 本账号无权限时的替代路径

21 个接口实测全部 `48001`（数据接口「向所有**认证**公众号开发者开放」，个人订阅号无法认证）。
**数据并非拿不到，只是入口换成后台网页**：

- 用户数据 → 后台「数据 → 用户分析 → 用户增长 / 用户属性」
- 图文数据 → 后台「数据 → 内容分析 → 单篇图文数据 / 内容汇总」
- 消息数据 → 后台「数据 → 消息分析」（部分账号无此模块）
- 接口数据 → 后台「数据 → 接口分析」（需先配置服务器地址）

抓取姿势沿用 §八：ego-browser 扫码登录 → 进「数据」板块选区间 → 同源 fetch 后台自身 JSON 或读 DOM 表格 → 落盘 JSON/CSV。
`wx_stats.py webplan` 会把这套对照表直接打印出来（含菜单导航语义，后台菜单以账号实际可见项为准）。

---

## 十七、三模块作业安全规程（红线汇总）

引用并覆盖 §十一⑧ 的立规，扩展为三模块通用：

1. **动任何已有草稿之前，先拉档**：`wx_draft.py get/backup` 会存 JSON + HTML；写操作（`update`/`delete`）自动加备份。
2. **能 `update` 就不 `delete`+`add`**：`delete` 不可逆、无回收站，且会丢掉用户在后台的手工改动。
3. **删除类操作一律两步走**：`wx_draft.py delete`、`wx_publish.py delete` 默认只演练；必须显式 `--yes` 才执行。
4. **平台版 ≠ 本地版时，先怀疑"用户在后台改过"**：用 `wx_draft.py diff` 定位差异，**停下来问，绝不覆盖**。
5. **推送前必过方言校验**：`wx_dialect_check.py` 不通过不推（`wx_pipeline.py` 已内置硬拦截）。
6. **推送后必做服务端回读验收**：`draft/get` 比对 ①各标签计数 ②`style=` 总数 ③纯文本一致性，并断言 `style=""` 计数为 0。
7. **发布（freepublish/submit）是面向全部关注者的动作**：即便某天接口权限恢复，也必须先人工在后台预览确认，
   绝不把 `submit` 放进无人值守的流水线。
8. **凭据永不入库**：只用环境变量或 `~/.config/weixin/`；`wx_common.py` 打印凭据来源时只显示 AppID 前 6 后 4 位。

