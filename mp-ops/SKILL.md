---
name: mp-ops
description: 公众号运营数据一体化：刷新发表记录、量化分析、搜一搜数据、生成 HTML 报告、发布后归档勾稽、单号每日流量复盘口径。触发词：发表记录、文章数据分析、公众号数据复盘、发布后归档、发表记录勾稽、待发布归档、本地与线上对不上、搜一搜、搜索数据、阅读渠道构成、老稿长尾价值、公众号运营数据、跑今天的数据分析、数据日报、流量分析、阅读数据分析、线上已发布累计表、看看昨天那篇多少阅读。
agent_created: true
---

# mp-ops — 公众号运营数据一体化

> 正本 `~/src/skills/mp-ops`（git 仓库），`~/.workbuddy/skills/mp-ops` 是软链接，两处等价。
> **适用于任意公众号**，账号目录由环境变量注入。
> **跑公众号数据一律先调本技能**，不要在账号目录里另起一份分析脚本。

## 一、环境变量

| 变量 | 含义 | 默认 |
|---|---|---|
| `GZH_WORK_DIR` | 公众号工作目录（含 `待发布/`、`发表记录*.csv`） | 当前工作目录 |
| `GZH_VAULT` | Obsidian vault 根（用于 git mv 归档） | `~/codeup/obsidian` |
| `GZH_PUBLISHED_DIRS` | 已发布分区目录，逗号分隔 | `0南京遛娃,1行走中国,3本地生活,4散装江苏,5教育` |

> 前缀 `GZH_*` 是公众号通用缩写，**与技能名 mp-ops 无关**，改名时别连它一起改。

```bash
export GZH_WORK_DIR="/Users/zhugx/codeup/obsidian/03-工作记录/满爸爱生活"
export GZH_VAULT="/Users/zhugx/codeup/obsidian"
PY=/Users/zhugx/.workbuddy/binaries/python/versions/3.13.12/bin/python3
```

---

## 二、脚本（按执行顺序）

> 📌 **单号专属口径**（「码上职业」每日四段日报格式、行动阈值表、落点三处封顶）不在本文件，
> 见 [`references/analytics-mashang.md`](./references/analytics-mashang.md) —— 2026-09-24 从
> `job-write/references/analytics.md` 迁入（数据复盘是运营动作，不属写稿技能职责）。
> 通用机制在下面，单号口径在 references，**两层别各写一份**。

### ① `refresh_publish_records.py` — 刷新发表记录　*需登录态*

```bash
"$PY" scripts/refresh_publish_records.py            # 抓原始 JSON + 生成新日期 CSV
"$PY" scripts/refresh_publish_records.py --no-csv   # 只落原始 JSON
```

- 接口 `GET /cgi-bin/appmsgpublish?sub=list&begin=<0,20,...>&count=20&token=<t>&lang=zh_CN&f=json&ajax=1`
- **两跳解析**：`publish_page`（字符串）→ `publish_list[i].publish_info`（字符串）→ `appmsg_info[]`
- **时间字段分两处**：已通知在 `sent_info.time`；**未通知没有 `sent_info`，时间在
  `appmsg_info[0].line_info.send_time`**（只读前者会让未通知记录全部没日期）
- 指标字段：`read_num` / `like_num` / `share_num` / `old_like_num`(在看) / `comment_num`
- 产出：`~/.cache/weixin/publish_records/<账号>_发表记录_<时间戳>.json`
  + `<GZH_WORK_DIR>/发表记录-<账号>-<日期>.csv`

### ② `publish_records_analysis.py` — 发表记录量化分析　*纯离线*

```bash
"$PY" scripts/publish_records_analysis.py        # 自动取目录下最新 CSV
```

12 个维度：粉丝规模曲线 / 公域放大倍数 / 标题特征 / 合集 / 时段 / 互动结构 /
头部集中度 / 近 90 天 vs 早期 / 已删除 / 阅读 TOP20 / 分享 TOP15 / **★12 稳健性复核**。

### ③ `search_analysis.py` — 搜索长尾价值评估　*纯离线，产推算值*

```bash
"$PY" scripts/search_analysis.py                       # A~G 七段
"$PY" scripts/search_analysis.py --old-days 120        # 改"老稿"门槛
"$PY" scripts/search_analysis.py --channels <search_channels_*.json>   # 【H】回填真数据校验
```

A 意图词覆盖与缺口 / B 搜索友好度打分 / C 常青 vs 时效 / **D 半实证交叉验证** /
E 合集资产价值 / F 行动清单 / **G 真实长尾水位（剔爆款）** / **H 真实渠道数据回填**。

### ④ `search_fetch.py` — 单篇阅读渠道构成　*需登录态*

```bash
"$PY" scripts/search_fetch.py --check              # 检查登录态 + 取 token
"$PY" scripts/search_fetch.py --limit 30           # 抓渠道构成
"$PY" scripts/search_fetch.py --account-summary    # 账号层关注来源
```

### ⑤ `generate_report.py` — 生成 HTML 分析报告　*纯离线*

```bash
"$PY" scripts/generate_report.py                   # 输出到 <GZH_WORK_DIR>/运营/复盘/
"$PY" scripts/generate_report.py --out <路径>
```

八章：增长曲线 / 破圈分布 / **搜一搜真相（实测）** / 标题技巧翻案 / 标题字数 /
集中度 / TOP15 与沉没清单 / 行动建议。图表引擎**内联**于 `assets/echarts.min.js`。

### ⑦ `fetch_published_archive.py` — 抓回线上历史文章存档　*纯离线*

```bash
"$PY" scripts/fetch_published_archive.py            # 全量（幂等，已存档的跳过）
"$PY" scripts/fetch_published_archive.py --limit 5  # 先试几篇
```

用于补 **内容资产缺口**：早期发布后未在本地留档的稿，vault 里没有原件。
从发表记录的 `content_url` 逐篇抓回正文，转 Markdown 存进
`<GZH_WORK_DIR>/已发布存档/<YYYY-MM>/<DD>-<标题>.md`。

- **不需要登录态**（走 mp-save 记录的 curl 通道 + Safari UA）
- **图片只保留链接、不下载文件**（147 篇 × 平均 6 张规模过大，需要时按 URL 取）
- 正文范围 `id="js_content"` → `rich_media_area_extra`，避免混入推荐位
- frontmatter 写入 `album / read / like / share / url`，便于后续检索与复用
- **幂等**：目标文件存在即跳过，可反复运行
- ⚠️ **已删除的文章返回 HTTP 200 + 2.6MB 提示页，不是 404**。必须按提示文本
  （`该内容已被删除` / `已被发布者删除`）判定，否则会被误判成"抓取失败"而反复重试。
  **要确认真实原因就去后台「违规记录」页核对** —— 实测某号 18 篇"已被删除"稿，
  违规记录**为空**，说明是**作者自删**而非平台处置，别凭前端文案瞎推断。

### ⑧ `publish_archive_reconcile.py` — 发布后归档勾稽

```bash
"$PY" scripts/publish_archive_reconcile.py              # dry-run
"$PY" scripts/publish_archive_reconcile.py --apply       # 高置信的 git mv 归档
"$PY" scripts/publish_archive_reconcile.py --report <p>  # 指定报告路径
```

三态清单：`✅ 高置信已发` / `❓ 需人工判断` / `⬜ 线上已发、本地未归档`。
样例见 `references/勾稽报告样例-2026-09-16.md`。

#### ⚠️ 归档是「三件套」：稿 + 排版稿 + 专属图，缺一即断链

`--apply` 与手工归档都容易只搬**稿件 md 本身**。2026-09-22 人工归档 9 篇时查出深层债：
**md 早已在分区目录，但 `-排版.html` 和专属图片仍留在 `待发布/`**，
而 md 里的图片引用写法是 `assets/xxx.jpg`（相对 `待发布/`）——搬进分区后**全部断链**。

归档一篇稿必须同步处理三样，并改引用：

| # | 搬什么 | 说明 |
|---|---|---|
| 1 | `<名>.md`（+ `-封面.jpg`） | 稿件本体 |
| 2 | `<名>-排版.html` | mp-publish 产出的排版稿**一般是 base64 内嵌图**，但**也可能用 `src="assets/..."` 相对路径**（苏超 Tifo 稿即后者），必须一并改 |
| 3 | `待发布/assets/` 里**该稿引用的**图 → `<分区>/<名>__assets/` | 见下方共享池警告 |

**改引用规则**（只替换该稿实际引用的文件名，**不要**用 `assets/` 做泛替换）：
- md：`](assets/<fn>)` → `](<名>__assets/<fn>)`
- html：`src="assets/<fn>"` → `src="<名>__assets/<fn>"`

> **`待发布/assets/` 是多稿共享池**（实测一次 76 个文件分属多篇稿，含未发稿的素材）。
> **绝不能整个目录搬走**，只能按引用逐篇摘。搬完若某未发稿引用了刚被摘走的图，需补一份回去。

> ⚠️ **`--apply` 只搬单个文件，`list_md()` 也只扫 `.md`** —— 有两类稿它天然看不见、也搬不动：
> ① **只在 `待发布/` 剩 `-排版.html` 的**（md 已先归档，实测漏掉《五小比赛》《学平险》两篇已发稿）；
> ② **带 `__assets/` 的**（图不会跟着走 → 归档即断链）。
> **存量核对除了跑勾稽，还要单独扫一遍"没有同名 `.md` 的孤儿 `-排版.html`"**，逐个判断是否已发。

**验收（脚本断言，不靠肉眼）**：归档后遍历该稿 md 的每个本地图引用做 `os.path.exists`，
断链数必须为 0；html 的 `src="..."` 本地引用同理。

**从 base64 恢复丢失的图**：md 断链但 `-排版.html` 是 base64 内嵌时，可提取 base64 还原成图。
**定序不能凭顺序猜** —— 取每张 base64 图**前 400–500 字的去标签文本**，与 md 中对应引用的
**前文**做子串匹配，一一对上再命名（S3 号线 3 张图即用此法定位 `s3-01/04/03`，注意**顺序与 md 不同**）。

### ⑨ `search_center_fetch.py` — 搜一搜数据中心全量抓取　*需登录态*

```bash
"$PY" scripts/search_center_fetch.py --check             # 探登录态 + 目标 profile/appid
"$PY" scripts/search_center_fetch.py                    # 默认 mashang 近 30 天
"$PY" scripts/search_center_fetch.py --days 1           # 仅昨天（12:00 后跑）
"$PY" scripts/search_center_fetch.py --days 7
"$PY" scripts/search_center_fetch.py --profile manba    # 换已登记账号
"$PY" scripts/search_center_fetch.py --out <路径>       # 指定落盘位置
```

打通 `wsad.weixin.qq.com` 三个接口（`get-search-channel` / `get-hot-passage-list` /
`get-hot-query-list`），落盘 `search_center_raw_<日期>.json` + 结构化 `search_center_<日期>.json`。

⛔ **账号纪律（写错号＝数据污染）**：默认 `--profile mashang`，appid **不写死**，运行时从
`mp-publish/scripts/wx_account.py env <profile>` 读（账号表是唯一真源）。当前登录账号与
目标 profile 不符 → **exit 2 硬停**，不允许「A 号登录态 + B 号 appid」取数。
换号后先 `--check` 看清账号再跑。

> 导航三跳、接口族、Vue SPA 资源漂移等逆向细节全在脚本 docstring 里，别在本文档重复一份。

---

## 三、数据源与后台入口

### 后台主站 `mp.weixin.qq.com`

| 用途 | 入口 |
|---|---|
| 登录（唯一正道） | **首页 `https://mp.weixin.qq.com/`** |
| 发表记录 | `/cgi-bin/appmsgpublish?sub=list` |
| 内容分析（列表，可取 msgid） | `/misc/appmsganalysis?action=report&type=daily_v2` |
| 单篇明细（渠道构成/完读率/画像） | `/misc/appmsganalysis?action=detailpage&msgid=<ID>&publish_date=<日期>&type=int&pageVersion=1` |
| 用户分析（关注来源） | `/misc/useranalysis` |

个人订阅号 **datacube 21 个接口全部 48001 无权限**（`mp-publish/wx_stats.py selftest` 可复验），
只能走网页。

### ★「微信搜一搜」数据中心 `wsad.weixin.qq.com`

后台左侧导航**最底部**的「微信搜一搜」（`/misc/pluginloginpage?pluginuin=10071`）把内容装在
**iframe** 里，真实域名是 **`wsad.weixin.qq.com`**，`plugin_id=searchzone`。

| 模块 | 内容 |
|---|---|
| 关键数据 | 搜索后阅读 / 搜索后关注（昨天 · 最近7天 · 最近30天） |
| 粉丝来源 | 按版块（公众号 / 文章）的 展示 · 点击 · 曝光点击率 · 转化粉丝 |
| 热门文章 | 展示 · 点击 · CTR · **平均排序位置** · 命中的搜索词 |
| 热门搜索词 | 展示 · 点击 · CTR · **相关搜索词**（可翻页） |

取数：**已脚本化** → `scripts/search_center_fetch.py`（2026-09-24 打通，见 §二·⑨）。
**数据每日 12:00 更新前一日，仅保留 30 日** —— 必须及时落盘
（`~/.cache/weixin/publish_records/search_center_<日期>.json`）。

> ✅ **本模块已于 2026-09-24 落地脚本**（此前只有本文档、必须人工翻 iframe）：
> ```bash
> "$PY" scripts/search_center_fetch.py --check              # 探登录态 + 目标 appid
> "$PY" scripts/search_center_fetch.py                     # 默认 mashang 近 30 天
> "$PY" scripts/search_center_fetch.py --days 1            # 仅昨天（12:00 后跑）
> "$PY" scripts/search_center_fetch.py --profile manba     # 换账号
> ```
> ⛔ **写错号＝数据污染**：脚本默认 `--profile mashang`，appid 从 `mp-publish` 账号表
> 运行时读取（不写死）；**当前登录账号与目标 profile 不符时直接 exit 2 硬停**。
> 2026-09-24 首跑即靠这条抓出「登录态是满爸爱生活、appid 却是满爸号」的问题 ——
> 换号后请先跑 `--check` 看清楚账号再取数。
> ⚠️ `scripts/search_fetch.py` 仍在，但取的是**单篇阅读渠道构成**，与本模块两个口径，勿混。

> ⚠️ **先翻导航再下结论**：不要只从「内容分析 → 单篇渠道构成」拿几篇就说"数据就这么多"。

---

## 四、⚠️ 口径纪律（结论性的，违反会得出错误结论）

1. **`sent_succ` ≈ 粉丝数，不是打开基数**。read/sent 常 >100%，它是**公域放大倍数**
   （>1 = 突破粉丝池吃到推荐流量）。**别拿它冒充打开率**（微信不对外提供真实打开率）。
2. **发布不足 7 天的稿仍在发酵**，混排会把好稿误判成差稿。对比类统计用 `mat`，别用 `live`。
3. **篇均（mean）极易被爆款拉高，必须同时看中位数**：
   均值高 + 中位≈1 = 少数爆款抬高天花板，**不能指望复现**；
   均值低 + 中位高 = 地板资产，不出爆款但每篇不掉链子，**别砍**。
4. **判断标题特征必须用维度【12】**（分层 + 剔极端值），维度【3】只看分布不下结论。
   历史教训：未剔极端值得出过"长标题更好""最/第一/唯一有效""稀缺词拉分享"，复核后**全部反向或无效**。
5. 分层阈值取粉丝数 60% 分位；换阈值个别判定会漂移，但**方向稳定**。
6. **两个"阅读"口径别混**：detailpage 是区间口径且页面滞后（更新至 T-1），
   `appmsgpublish` 的 `read_num` 是累计 live 值。**比大小一律用后者**。
7. **推算值必须标注**。`search_analysis.py` 的打分是推算，不是后台实测搜索量。
8. 脚本给的是**相关性不是因果**。

---

## 五、已知坑（实测，别重踩）

**登录与抓取**
- 登录入口**必须用首页**；`/cgi-bin/home` 在失效时是"登录超时，请重新登录"**死页，没有二维码**。
- 判定登录态**不能只用"扫码"黑名单**：后台首页有运营文案"推荐带来6.5万阅读量，**微信扫码**查看
  你的一周创作总结"，会把**已登录误判成未登录**。以 URL 带 `token=` 且位于 `cgi-bin/(home|appmsg|masssend)` 为准。
- 「微信快捷登录」按钮是 `<div>` 包 `<a class="login__type__container__link_text">`，
  要取**最内层**元素点击，点外层容器无效。
- **msgid 有两个**：真实 id 是 `appmsgid_序号`（`2247488280_1`，只能从 report 页「详情」href 取）；
  发表记录 CSV 里的 `msgid` 是**批次号**（`1000000172`），拿去请求返回「系统错误(200002)」。

**渠道构成解析**
- innerText 里**数值在前（7 个 xx.x%）、渠道名在后，两者都按数值降序**，
  必须**按位置 zip 配对**；渠道名之后还有 `0/25/50/75/100/125%` 坐标轴刻度，要丢弃，
  做法是在 `End of interactive chart` 处截断。
  （`mp-publish` 文档早期写的"固定图例顺序硬取"会把「搜一搜」和「推荐」**配反**，已更正。）
- **detailpage 只统计发表后 30 天内**，老文章拿到的是冻结在第 30 天的快照，样本天然偏近期。

**报告生成**
- ECharts 必须**内联**，改回 CDN 在预览端加载不到会整页空白。
- `const mk=(id,o)=>...` 是双参数；写成柯里化 `mk=id=>o=>...` 时 `mk('c1',option)`
  只会取第一个参数、闭包被丢弃，`setOption` 从不执行 —— 图表全空且不报错。
- 生成后用 node 模拟 DOM 跑最后一个 `<script>`，断言 `setOption` 次数 == 图表数；
  肉眼刷新证明不了图表已挂载。
- 全文会残留 `___EC__COMPONENT__CONTAINER___`，那是 **ECharts 库内部**占位符，不是漏替换。

**其他**
- 分析脚本早期在【4】合集维度会因 `st.mean([])` 抛 `StatisticsError` 中断整份报告，已加 `safe_mean()`。
- CSV 文件名**不要写死**：刷新后会生成新日期的 CSV，写死会静默跑旧数据。一律"取目录下最新"。

---

## 六、与其他技能的分工

| 环节 | 用哪个 |
|---|---|
| 写稿 / 选题 | 各账号 vault 与运营文档；招聘类走 `job-write` |
| 排版（微信原生方言） | `mp-html` |
| 发布到草稿箱 / 群发 | `mp-publish` |
| **跑数 / 搜一搜 / 报告 / 归档** | **本技能 `mp-ops`** |
| 单号每日复盘口径（「码上职业」四段日报 + 阈值） | 本技能 `references/analytics-mashang.md` |
| ⛔ 写稿技能里的数据分析内容 | **已迁出**（2026-09-24 原 `job-write/references/analytics.md`） |

---

## 七、为什么归档勾稽不能用标题精确匹配

公众号为打开率会把标题**彻底改写**，本地工作标题 ≠ 发布标题。脚本用
「最长公共子串 + 泛词剥离」，对每篇待发布稿输出**最相似的 3 篇**让人肉眼判，
只有达阈值才标「高置信」可自动归档。

> **绝不要改成精确匹配**，那会直接误归档。

### ⚠️ 「高置信」也不能盲信 —— 2026-09-22 实测误判

一次 dry-run 报「高置信 3 篇」，逐条核对后发现 **1 篇是错的**：

| 待发布稿 | 脚本匹配到的线上稿 | 实情 |
|---|---|---|
| 中国地铁第一省，为什么是"散装"江苏 | 中国地铁第一省，不是广东…（75,391） | ✅ 同一篇 |
| 南师大标本馆 9月只剩19日 | 同名稿（2,228） | ✅ 同一篇 |
| **江苏13太保6城通地铁，全国地铁城市最多的省** | **中国地铁第一省**（75,391） | ❌ **不同稿件**，仅"全国地铁城市最多的省"措辞撞车 |

**误判率 1/3。** 结论：
- `--apply` **必须先跑 dry-run 并逐条看「命中片段」**，确认所指是同一篇稿；
- 宁可手动 `mv` 这两三篇，也不要一键 `--apply` 把没发的稿移走；
- 同题材系列稿（"第一省"系列）**最容易被互相误配**，看到同系列标题就要格外警惕。

### 关于「线上已发、本地未归档」

这个数字（满爸号一度报 129 篇）**不等于"本地有稿没归档"**——多数是**本地压根没有这些稿的存档**
（早期发布后未留档）。两件事要分开看：
- **本地有稿 + 线上已发** → 该归档，用本脚本三态清单处理；
- **线上已发 + 本地无稿** → 属内容资产缺失，用 `fetch_published_archive.py` 抓回正文存档，
  抓完后本脚本会把它算作"本地已有"（`已发布存档/` 已纳入识别范围），归档率才反映真实情况。

### 执行归档时的环境坑

- **`git mv` 可能被 stale 锁挡住**：报 `Unable to create .git/index.lock`。
  先确认无活跃 git 进程、且锁文件大小/时间戳长时间不变（真 stale）再删；
  若仓库挂着 Obsidian Git 之类的外部进程，**不要反复抢锁**，改用普通 `mv` 移动文件，
  之后 `git add -A <路径>` —— git 的 rename detection 通常仍能识别为 `R`（重命名），历史连续。
- 沙箱内**没有 `.git` 写权限**，git 操作需完整权限执行。
- **`git status` 会在沙箱下残留 0 字节 `.git/index.lock`**（报
  `unable to unlink '.git/index.lock': Operation not permitted`），此后所有 `git add` 都会
  报"另一个 git 进程在运行"。**每次 `git add` 前先 `rm -f .git/index.lock`**（0 字节可安全删）。
- **归档只 stage 相关路径**：`git add -A <分区目录> <待发布目录>`，**不要**全仓库 `git add -A` ——
  vault 常同时有别的 session 在写（实测一次 131 条待提交变更，多数与本任务无关）。
- **Python 不能往"本次进程刚建的目录"里搬文件**：`os.makedirs(新目录)` 后紧接 `shutil.move()`
  会报 `PermissionError: ENOENT ... rename`（沙箱 broker 不认这个新目录）。
  **先用 shell `mkdir -p` 把目标目录建好，再移文件**。
