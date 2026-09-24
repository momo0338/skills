# 信息源策略 · 每日巡检 · 接口逆向

> 本文件是 `job-write` 技能的**扩展参考**，不由 SKILL.md 常驻加载。
> **何时读**：要找公告源、实拉岗位、逆向报名站接口、跑巡检时
> 读完回到 SKILL.md 继续；脚本路径均已写成绝对路径，与当前工作目录无关。
> 返回：`job-write/SKILL.md`

---

## 一、信息源策略

### 1.1 源 A：ima 知识库取公众号原文（批量场景）
```bash
# ① 找目标库（招聘类常是共享库）
#    get_knowledge_base_list(params=[{limit:50,type:"KBT_MINE_KB"}])   → 个人库
#    search_knowledge_base(query="招聘", limit<=20)                    → 共享/订阅库
# ② 列目录（分页：cursor 从 "" 起，sort_type=UPDATE_TS_DESC_SORT_TYPE）
#    get_knowledge_list(knowledge_base_id, limit=20, cursor="",
#      filters=[{filter_type:"MEDIA_TYPE_FILTER_TYPE",media_type_filter:{media_type:["WECHAT_ARTICLE"]}}])
# ③ 逐篇取全文（正文文本 + 微信 CDN 图片直链 mmbiz.qpic.cn）
#    fetch_media_content(media_id)
```
- **关键认知**：ima 公众号条目**不返回原文 `mp.weixin.qq.com` 链接**，只给正文 + 图片直链 → 不能做"链接跳转转载"，必须做**要点提炼型原创汇编**（更安全、更有附加值）。
- **`--source-url` 从哪来**：多数公告正文末尾带**官方公告网址**（政府网 `xxx.gov.cn` / 单位官网 / 招聘平台），那才是该指向的地址，**不要**指来源公众号。已核实示例：栖霞区卫健委 `njqxq.gov.cn`、泰州市直 `rsj.taizhou.gov.cn`、华电 `chd.com.cn`。
- 要插原文链接：① 后台编辑器「超链接 → 查找文章」原生插入（**推荐合规**）；② `mp_search.py account "<号名>"`（需 playwright + 扫码，本机默认未装）。
- ⚠️ **别用搜狗链** `weixin.sogou.com/link?url=...`：有反爬，curl 直接落 antispider 页。

**本项目已定位的库（2026-09-16 实测，31 条）**：
- 共享知识库「招聘」，`knowledge_base_id = 7505639995636931`（`search_knowledge_base(query="招聘")` 可取到；`get_knowledge_base_list` 只列个人库，取不到它）。
- 三个来源号：**「南京人才招聘」**（9 月批次主力，公告型、常带政府网原文地址）、**「江苏橙考事业通」**（8 月批次，海报型、信息含量低需去报名站补）、「看看南京」。
- ⚠️ 该库 2026-09-15 22:00 前后**一次性批量入库**（存量快照）→ 不能假设它自动更新，用前应重新 `get_knowledge_list` 查增量。
- ⚠️ 库里混两类内容，取数后必须先分流：**A 线 2027 届校招**（企业）/ **B 线 事业单位・高校招考**（2026 口径）。B 线时效更紧，但与本专栏定位不同，不要混进校招稿。

### 1.1.1 ⚠️ 来源号信息密度差异（2026-09-16 实测，最省时间的一条经验）

同是转载招聘信息的公众号，信息含量天差地别 —— **先判断类型，再决定要不要逐条实拉**：

| 类型 | 特征 | 处理方式 |
|---|---|---|
| **公告搬运号**（如「南京人才招聘」） | 文本型为主：有连续 `<p>`/`<h>` 正文节点，岗位/条件/截止日/官方公告网址**齐全** | **直接入稿**；仍需留意它也会混图片型（本次 18 条里 8 条是图） |
| **引流号**（如「江苏橙考事业通」） | **全为图片海报型**：正文节点几乎全是 `<image>`，`alt` 极短或整段重复 | **只当线索源**！逐条拉正文是纯浪费（已验证 3 条一致）。拿到"某单位启动校招"的线索后，去官方招聘站补岗位与截止日 |

- **判断口诀**：正文里 `<image>` 占绝对多数 + 文字节点为 `·`/重复口号 → 图片型；有结构化 `<p>` 段落 → 文本型。
- **图片型也别放弃**：长海报的 `img alt` 属性里**常藏完整全文**（简介 + 岗位表 + 投递方式）。本次晨光的 8 个岗位、中车浦镇的专业清单、航发的网申地址都是从 `alt` 里捞出来的 → **提取时必须读 `alt`，别只看正文节点**。
- **截止日常缺失**：实测 27 条校招素材中仅 5 家公告写明截止日。**排期不能只靠台账**，须以各单位官方招聘站为准。

### 1.2 源 B：官方报名站 / 招考系统实拉岗位（最准，强烈推荐）
很多国企/事业单位校招用智联招考 SPA（`xxx.zhaopin.com/zk/#/...`，uni-app）。公告正文只写"岗位详情在报名页查看"，**真实岗位在报名站接口里**——直接逆向接口拉，比从公告猜准得多。详见**附录 A**。

### 1.2b ⭐ B 线专用：**政府网公告附件 .xlsx 直取**（编制岗唯一可信来源，2026-09-17 实证）

**这是 B 线成本最低、收益最高的一步，写稿必做。** 编制类公告正文几乎从不写岗位明细，只写
「具体岗位、数量、资格条件详见附件《岗位信息表》」——**真实岗位在 .xlsx 附件里**，
而所有转载号（含"公告搬运号"）都只抄正文，**附件里那 90% 的信息量它们集体缺失**。

```bash
# ① 从公告页 HTML 里找附件链接（政府网附件路径形如 /qxqrmzf/202609/P020260915601309122009.xlsx）
curl -sL "<公告页 URL>" -H "User-Agent: Mozilla/5.0 ..." | grep -oE 'href="[^"]*\.(xlsx|xls|docx?)"'
# ② 下载时**必须带完整 UA + Referer**，否则政府网返回 HTML 拦截页（`file` 会报非 Excel）
curl -sL -o gangwei.xlsx "<附件 URL>" \
  -H "User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36" \
  -H "Referer: <公告页 URL>"
file gangwei.xlsx   # → "Microsoft Excel 2007+" 才算拿到
# ③ openpyxl(data_only=True) 逐行读；岗位表的列通常在**第 2 行**，第 1 行是表名
```

**能从附件里捞到、而转载号全都没有的增量**（栖霞实例）：
- **年龄放宽的例外岗**（如"取得中级职称放宽至 43 周岁""高层次岗 45 周岁以下"）；
- **直接面试的触发条件**（"报名比 ≤3:1 时面试 100%、成绩即总成绩"）→ 直接决定报考策略；
- **合并招聘 + 依次选岗**（同专业打包招 N 人，录用后按总成绩选点位）→ 影响"值不值得报"；
- 每岗的**执业资格 / 规培证 / 工作年限**硬门槛、**招聘对象**（应届/社会/不限）分布。

> ⚠️ **岗位数 ≠ 人数**：栖霞「17 个岗位 / 20 人」（两岗各 2 人、3 人）。台账与标题里两个数都要写对，
> 别写成"20 个岗位"。落库时把附件本身也存进 `素材/`，日后复核不必重下。

⚠️ **「报名方式」必须回公告正文 §报名办法 逐字核 —— 别信"网络报名"这四个字**（2026-09-17 无锡实证）：无锡梁溪区卫健委公告写「采用网络报名」，实为 **把材料扫描成 PDF 发到招聘单位邮箱、以收到邮件时间为准、根本没有在线报名系统**；
真正的报名入口写在**附件2《各单位联系方式》的"电子邮箱"列**里。若只看转载稿或正文摘要，会写成"在线报名入口"，直接误导读者。
**取数口径**：`附件N《联系方式》` 里的邮箱／报名系统 URL 才是真入口；`--source-url` 优先给最靠前的可访问入口（网申系统 > 报名邮箱所在公告 > 官网栏目页）。
公告页附件链接形如 `/uploadfiles/YYYYMM/DD/<20位数字>.xlsx`，可批量 grep 后循环下载（每个都要带 UA + Referer）。

### 1.2c ⭐ A 线央企「集团招聘官网」核验路径（2026-09-17 华电/华能实测）

电力/军工等 A 线央企的校招多为**集团统一批次**（同一批、同窗口、多家区域公司同开放）。**截止时点以集团招聘官网页为准，不要用转载稿的四舍五入值**（实测官方写 **23:59**，转载普遍写成 **24:00**）。

| 集团 | 官网 | 实测可用性 |
|---|---|---|
| **中国华电** | `https://rencaishichang.chd.com.cn/w3/`（人才市场信息系统） | ✅ **校招公告列表页可直接读出「招聘时间」区间** —— SPA 打不开详情也没关系（见下）。校招栏目路由：`#/w3/notice/main_view?class_item_pk=10000`（社会招聘 10001、实习 10007） |
| **中国华能** | `https://zhaopin.chng.com.cn`（集团统一网申） | ◐ SPA 首页 curl 仅 448B；API root `/app-api/...`（芋道框架，如 `/app-api/recruit/announcement/index`、`/app-api/recruit/public/deptlist`）**需 `Authorization: Basic <clientId:secret>`**，凭据在 bundle 里未找到 → 改走多源交叉 |
| 国家电网 / 南瑞 | `zhaopin.srec.com.cn` 等 | 见各单位条目 |

**列表页文本直读法（推荐，绕开 SPA 详情页）**：用 ego-browser 打开列表页后，直接 `document.body.innerText` 就能拿到每条的**标题 + 招聘时间区间 + 单位 + 城市**，这一屏就足以核定「批次 + 截止时点」。

```js
await openOrReuseTab('https://rencaishichang.chd.com.cn/w3/#/w3/notice/main_view?class_item_pk=10000', { wait: true, timeout: 40 })
await new Promise(r => setTimeout(r, 5000))
const txt = await js(String.raw`(() => document.body.innerText.replace(/\n{2,}/g,'\n').slice(0,6000))()`)
```
华电实测同一批次**所有区域公司共用同一截止时点**（本批全为 `2026-10-18 23:59`）→ 核对一条即可外推，但仍需在该条上确认单位名。

⚠️ **两个 ego-browser 限制（WorkBuddy 环境实测）**：
1. 可用 helper 只有 `useOrCreateTaskSpace / openOrReuseTab / pageInfo / snapshotText / click / js / cliLog / listTaskSpaces / completeTaskSpace` —— **`page` 和 `mouse` 未定义**（`typeof page === 'undefined'`），Playwright 式写法会报 `page is not defined`。
2. **React SPA 的列表项 `el.click()` 常常不触发路由跳转**（React 合成事件 + 未挂 `<a>`），`snapshotText()` 也不给非交互节点 ref → **详情页可能打不开**。此时不要死磕，直接用上面的列表页文本直读法取要点，或换官方公众号/高校就业网镜像交叉。

⚠️ **「分公司校招」常是集团统一网申**：如「华能江苏清洁能源分公司 2027 校招」实际走**中国华能集团统一网申**（9-15 9:00 ~ 10-31 18:00），后续环节是**集团统一综合素质测评**，不是分公司自主笔试。写稿时要把「入口是集团官网」和「测评是集团统一组织」讲清楚，否则读者会去找分公司报名系统。

### 1.3 信息核验铁律
- 岗位/人数/学历/专业/薪资/报名 URL：以**官方公告或报名站接口**为准，绝不凭印象补。
- 官方咨询电话可保留（便于读者核验）；不搬运联系方式以外的敏感信息。
- ⭐ **银行招聘站抓取可行性分四级（2026-09-20 更新，决定用哪套工具）**：

  | 级别 | 判据 | 取数方式 | 实例 |
  |---|---|---|---|
  | ✅ **接口可取** | SPA 但 XHR 接口无鉴权 | 浏览器**同源 `fetch()`** 打接口 | **徽商** `rczp.hsbank.com.cn`、**杭州** `myjob.hzbank.com.cn`、中行官网公告页、邮储 |
  | ✅ **HTML 可直抓** | 静态页 / 服务端渲染 | `curl` 带 UA 即可 | 恒丰 `career.hfbank.com.cn/xyzp/zwcx/index.shtml` |
  | ⚠️ **legacy TLS** | 报 `UNSAFE_LEGACY_RENEGOTIATION` / SSL 握手失败 | 换 `/usr/bin/curl`（LibreSSL）或 `--ciphers 'DEFAULT:@SECLEVEL=1'` | 农行 `career.abchina.com.cn`、交行 `job.bankcomm.com` |
  | ◐ **纯 SPA / 有盾** | 前端 200 但无内容；或 412/403 | `ego-browser` 渲染后读 DOM 或同源 fetch | 工行 `job.icbc.com.cn`、建行 `job.ccb.com`、南京银行 `job.njcb.com.cn`、江苏银行（412） |

  > **逐家的入口 URL 不写在这里**——每家银行的 `网申入口` 字段存在唯一主档 `ijob/data/jobs.db`（`campaigns.apply_url` / `campaigns.announcement_url`），本技能只记"**怎么取**"。接口逆向见**附录 C**。
- ⛔ **来源黑名单（2026-09-16 实证，银行专题）**：`yinhangzhaopin.com`《国有六大行2027秋招备考时间线》**六大行截止日期 6/6 全错**（中行写 10-10/官方 10-09、交行写 10-12/官方 10-18、邮储写 9-30/官方 10-07、工 10-09/官方 10-08、农 10-09/官方 10-08、建 10-10/官方 10-08）→ 该站一切日期/人数不用，其"6.4 万人缩招"等行业数据引用一律降级为"媒体估算"。上岸鸭/高顿/中公推算页同理，只当线索。
- **银行公告直抓可行性**（09-16 实测）：中行官网公告页 ✅ `boc.cn/aboutboc/bi4/` 可 curl 直抓；邮储官网 ✅；农行 `career.abchina.com.cn` / 交行 `job.bankcomm.com` ❌ SSL 证书链/旧重协商屏障 → 改走"高校就业网镜像 + 官方号长海报 img alt + 多源交叉"钉死（三路原文一致即可升 ✅）。`mp.weixin.qq.com` 官方公告 WebFetch 只出标题（JS 渲染），opencli download 需浏览器扩展在跑，不稳 → 优先搜镜像站。
- ⭐ **银行「分行级公告」的取数链路（2026-09-17 中行江苏实证，最完整的一条）**：总行全球公告 ≠ 分行公告，**真正的岗位矩阵与分行专属填报路径只在分行公告里**，而分行公告**官网上往往没有**。三步打通：
  1. **总行官网公告页**（`boc.cn/aboutboc/bi4/202609/t2026xxxx_xxxxxx.html`）→ 拿统一报名网址、志愿规则（"每人最多 5 个岗位、平行志愿"）、**官方截止时点**（中行原文写 **"10月9日24点"**，即官方自己就用 24 点，别一律改成 23:59）、笔试时间、防骗与官方渠道声明。
  2. **同页附件 PDF**（`href` 里 `pic.bankofchina.com/bocappd/appform/...pdf`，curl 带 Referer 可直下，`pdfplumber` 可读）→ 拿**毕业时间窗口（如 2026-01-01～2027-07-31 且须"毕业后初次就业"、不含定向生委培生）**、亲属回避、各机构岗位条件分层（CET-6/CET-4 两档）。**附件是转载号集体缺失的部分，必下**。
  3. **分行公告靠高校就业网静态转载**（`jyb.<校>.edu.cn` / `career.<校>.edu.cn` / `51uns.bysjy.com.cn`，落款为分行 + 日期），搜「<单位> <届别> 校园招聘公告」即可命中多家。⚠️ **只有正文带真 `<table>` 的那一份能还原"机构 × 岗位"矩阵的列归属**：纯文本转载（含搜索引擎摘要）会把空单元格压掉，只剩一串 `√√√`，**列位置无法判断**（中行江苏实测：江苏省分行本部仅管培、南京分行仅营销+综合服务、管培只在本部+无锡+常州+扬州——这些结论只有解析 `<table>` 才拿得到）。解析口诀：单元格空＝`<br/>`，有＝`√`，逐个 `<td>` 判。
  - 分行公告独有的高价值增量：**分行专属填报路径**（如"ENTER→在招职位→境内分行→江苏省分行→辖属机构→选择岗位→申请职位→填写简历→职位问题选省内意向工作地点→投递简历"）、简历提交后不可修改、6 位报名编号提醒、"辖内可报 1-2 个岗位"。
  - 人数若公告未单列：找**省级官方就业平台**（江苏＝`91job.org.cn`，省高校招生就业指导服务中心主办）+ 高校就业网职位页（"需求人数"字段）两源一致才写，并在稿内注明口径 + "以报名系统为准"。
  - 行 logo 直取：`boc.cn/images/boc2013_logo.png`（写死在 CSS `boc2013_common.css` 里，首页 HTML 不带）；⚠️ 别把 `logo_raw` 之类的旧抓取件直接当图用——**中行那份 `boc_logo_raw.png` 实际是"提示信息"拦截页 HTML**，用前先 `file` 验。
  - ⭐ **先判断"这家分行到底有没有独立窗口"**：① 看总行/集团公告的"招聘机构"清单里有没有它；② 有 → 再找该分行**自己**发的公告；③ 找不到独立公告、且截止日与集团一致 → 判为**"同批次机构"，不单独成稿**。
    **2026-09-20 苏州实证（9 家一次核完）**：工 / 农 / 中 / 建 / 交 / 招 / 中信 / 浦发 / 民生的苏州分行**全部无独立窗口**，截止日与母行完全一致。
    ⚠️ **反向也要认**：标题写"南京与苏州分行"的（广发、光大）是公告本身合并了两地，属**真合并**，不是误判——江苏有南京、苏州两个平行市场，误判会写出"同一家银行两篇重复稿"。

---

### 1.4 招聘公告的五个固定结构（**写稿前先认形状**，2026-09-20 银行线归纳）

> 公告的坑不在信息缺失，而在**结构决定文章角度**。以下五种几乎每篇都遇到，**认出来就不会写偏**。银行最典型，国企/事业编同样适用。

1. **门槛分两档（总行岗 vs 分行岗）** —— 最常见形态是「总行科技岗专业限定 + 分行岗专业不限」，而分行内部常再分一档：**「培训生」要硕士，「营销/运营/柜员」本科起**。
   - 徽商：总行金融科技岗（限定计算机/软件/AI/数据科学等）vs 分行管培/客户经理/定向柜员（专业不限）。
   - 杭州：南京分行培训生（**硕士及以上**）vs 营销/运营培训生（**本科及以上、专业不限**）。
   > **写稿口径**：「是不是本科」往往不决定「能不能报这家」，而决定「**能报哪一档**」——这比单纯写"本科可投"信息量大得多。

2. **双截止时点（科技岗/提前批先关）** —— 主批次一个时点，**总行信息技术岗常单独提前截止**，差近一个月。
   - 杭州：报名截止 **10-25 24:00**，但**总行信息技术培训生 09-30 24:00**。
   - 徽商：徽航计划主批 10-08，**徽银理财 2027 校招同窗口并行**（另一条通道，别漏）。
   > ⚠️ **两个时点必须分开写**。投科技岗的人按主批次日期算会误事。

3. **定向岗的服务年限（城商行/农商行特色）** —— 「定向柜员 / 定向综合柜员」常写死服务期，是**选岗第一道筛子**。
   - 徽商：定向柜员岗**柜面服务期限不少于 5 年**。
   - 紫金农商行：定向岗**服务满 3 年**。
   > 这是**硬条件**（不是"原则上"），**必须原文引用，不能软化**。

4. **志愿规则的三态（能投几个 × 能不能改）** —— 直接决定投递策略，各家差异极大：

   | 形态 | 实例 |
   |---|---|
   | 限投 **1** 岗、选定即锁 | 恒丰银行 |
   | 限投 **2** 志愿、**投递后不可修改** | 杭州银行 |
   | 第一 + 第二志愿 + 是否接受调剂 + 调剂分行 | 徽商银行 |
   | 可投 **3** 岗 | 民生银行南京 |
   | 可报 **6** 岗 | 交通银行江苏 |
   | 13 家机构 **35 岗**矩阵 | 中信银行江苏辖区 |
   > **「能不能改」比「能投几个」更重要**——不可修改意味着必须在提交前把顺序定死，值得单独成段讲。

5. **亲属回避 + 明示加分项（几乎家家都有，别漏）** ——
   - **亲属回避**基本是标配（"配偶/直系血亲/三代以内旁系血亲及近姻亲在本行及全资子公司工作的属回避对象"），稿里应提一句。
   - **加分项常被明示**，且很直白，是能直接换排序分的部分：徽商（法考 / CPA / CFA / 精算师，或校级以上奖励）;杭州（优秀团干 / 优秀团员 / 三好学生 / 优秀学生干部;零售金融方向另列基金从业 / 证券从业 / 银行从业 / CFA / FRM / AFP / CFP）。

---


---

## 二、信息源清单与每日巡检（引擎在 `ijob` 仓库：`/Users/zhugx/src/ijob/patrol/recruit_scan.py`）

招聘是**强时效**品类，靠人工想起来去搜必然漏。本技能配一个**零依赖巡检脚本**，每天自动回答"今天新出了哪些招聘信息"。

> 2026-09-24 起巡检引擎与去重/健康缓存**收进 ijob 仓库**（本技能目录不再存副本）。
> **日常请优先跑总控** `python3 /Users/zhugx/src/ijob/patrol/run.py --daily`，它会串起届别同步 + 探活 + 双通道抓取。
> 缓存落点：`/Users/zhugx/src/ijob/data/patrol_state/`。

### 2.1 双通道设计（都是免登录）

| 通道 | 手段 | 覆盖 | 速度 |
|---|---|---|---|
| `--mode wx` | **HTTP 直抓搜狗微信搜索页**并解析结果块（`--wx-engine sogou`，默认） | 全网公众号里的招聘文章，**能发现知识库里没有的新公告** | 秒级（4 组关键词约 15s） |
| `--mode wx`（备选） | `--wx-engine opencli` 调 `opencli weixin search`（浏览器） | 同上 | 首次 ~60s；⚠️ **第 2 次起必被搜狗限流超时**，仅作备用 |
| `--mode web` | **三层管线**（源取自 `jobs.db:patrol_sources`）：①列表扫描（政府专栏/企业招聘站/hotjob，当前 enabled ~177 个）→ ②招考适配器（zkapi 直拉**岗位数组**）→ ③哨兵（SPA hash 变更告警，当前 enabled 15 个） | 官方一手公告 + 岗位级增量 + SPA 变更探测 | 随源数而定 |

```bash
# 日常首选：总控（届别同步 + 探活 + 双通道抓取，源取自 ijob/jobs.db 的 patrol_sources 表）
python3 /Users/zhugx/src/ijob/patrol/run.py --daily

# 只跑引擎（--state 缺省即 ijob/data/patrol_state/.scan-state.json，可不传）
python3 /Users/zhugx/src/ijob/patrol/recruit_scan.py --mode both --wx-days 30 \
  --state "/Users/zhugx/src/ijob/data/patrol_state/.scan-state.json" \
  --out   "<vault>/码上职业/巡检记录/$(date +%F)-新增招聘.md"
# 分线扫 / 回退内置源 / 站点批量探活
python3 /Users/zhugx/src/ijob/patrol/recruit_scan.py --mode web --line B   # 或 --line A
python3 /Users/zhugx/src/ijob/patrol/recruit_scan.py --mode web --no-sources
python3 /Users/zhugx/src/ijob/patrol/run.py --probe
```

- **去重靠状态文件**：见过的标题集合存在 `--state` 里（留最近 4000 条），只报**首次出现**的 → 每天跑、隔天跑都不重复刷屏。
- **时效过滤 `--wx-days`（默认 30 天）必开**：⚠️ 搜狗按**相关度**排序，不加过滤会把 2016–2024 的陈旧文章当成新信息（实测「南京 校招」10 条命中里时效内 0 条，全是旧文）。
- **首次建库**用 `--all` 忽略状态输出全部命中。
- 搜狗结果里的链接是 `link?url=...` **跳转链**（有时效/反爬，正文解析不可靠）→ 只作"发现"，原文链接另行溯源。

### 2.2 选源原则（配置驱动，源数据在 jobs.db 不在代码）

- **源清单唯一真源 = `/Users/zhugx/src/ijob/data/jobs.db` 的 `patrol_sources` 表**（ijob 工程中枢；2026-09-21 起废弃 `sources.yaml`）：字段 `id/name/company_id/probe_url/kind/line(A|B)/tier/enabled/http_code/is_alive/consecutive_fail`；**加源 = 插一行 + 重跑探活**，不改代码。
- **kind 分流**：`gov_list|gov_bm|self_list|hotjob|company_site` → 列表扫描；`zhaokao` → `recruit_adapters.scan_zhaokao`（智联招考三步法拉岗位数组）；`self_spa` → 哨兵；其余（beisen/moka/job51/chinahr/zhaopin_gen/zhaopin_fix）→ 停用或待适配（脚本会**逐条列名**，不静默跳过）。
- **要"招聘专栏列表页"，不要网站首页**；HIT/NOISE 正则过滤 + 排除栏目导航链接（同前）。
- **源健康告警**：`sources-health.json` 记 last_ok_at / consecutive_fail / last_code；**连续失败 ≥3 在报告顶部列「🚨 源告警」**——防止"源坏了但报告显示无新增"的静默失效（最危险）。
- **平台族结论（2026-09-17 实测，勿再走弯路）**：①**北森 `*.zhiye.com` 22 家大半已死**（Not Found/重定向他司，按届租用站点过期即漂）→ 只能靠公众号首发；②智联子站分三型：**招考型**（zkapi 通，附录 A）、**企业型**（前端 200 但 SPA → 哨兵）、**按届 403**（公告期人工核）；③银行站 legacy TLS 用 `/usr/bin/curl`（LibreSSL）可过。
- 巡检只做「**发现 + 登记**」，不自动写稿、不自动推送；岗位明细：招考型已直拉，其余进站取（`--source-url` 用官方源）。

### 2.3 分拣方法（2026-09-16 首巡 43 条实测，报告出来的下一步怎么做）

**① 号族分三档，决定它能给你什么**：

| 档 | 特征 | 用途 | 例（江苏） |
|---|---|---|---|
| **矩阵号族** | 同日发布、命名套路一致（"XX省/市+国企招聘"） | 批量线索源，专发集中招聘，**一稿吃多家** | 江苏考聊国企招聘 / 江苏省国企招聘 / 江苏南京国企招聘 / 江苏国企招聘鹿 / 江苏校园招聘 |
| **地方·行业垂号** | 区级、医疗、教师等细分 | 发现库内没有的单位 | 南京招聘号、徐州招聘号（跨市转载）、栖霞视点、南京医聘猫、医服猫江苏、江苏教师招聘牛 |
| **考试培训引流号** ⚠️ | 标题堆大数字 + "附岗位表可直接下载" | **只能当"某事发生了"的信号，数字严禁引用** | 笔试信号阁、同学小翠的小瞬间、现在启程、依欣上岸、柳爱学习3273啊、锡才上岸 |

> **硬证据**：同一件"江苏省事业编下半年统考"，6 个培训号标题分别写 **2944 / 2964 / 3176 人** —— 互相矛盾，说明全是自媒体加工值。看到多号密集转同一事件，**结论只能是"此事真实存在、数字必须回官方核"**，而不是挑一个写。

**② 四类必判为「其他」，不要入库**：
- **录用公示 / 拟聘公示 / 体检公示**（`XX公开招聘人员公示`）→ 这是招聘流程的**结束环节**，投不了。已加进 NOISE（`招聘.{0,8}公示`）。
- **取消公告**（`关于取消…部分岗位的公告`）→ 变更环节，不是招聘公告（已加 `取消.*公告`）。
- 招聘会/就业活动**新闻**（"逛夜市拿offer"、"秋季校园招聘亮相"）→ 政务动态，无岗位。
- 已收录单位的**重复转载** → 不新增行，但**要抠增量信息**（见 ④）。

**③ 「批量集中招聘」类是最高优先选题**：一条公告含 N 家单位 + 总人数（实测见"49 家市属国企 228 人免笔试"、"51 家省属国企 323 人第二批"）→ 天然汇编稿，且"免笔试""第二批"是强钩子。**遇到就单独标记，别混在单位线索里。**

**④ 重复公告要抠增量**（这是零成本的信息增量来源）：已收录单位的他号转载版常带原文没有的角度 —— 转载标题里的「五险两金 + 提供住宿」「全国 8971 人」「含职位表和报名入口」「带编！五险二金」，都是可直接用于标题/卖点的素材，但仍需回官方源核实后才写进稿子。

**⑤ 登记动作**：在报告里把「待分拣」改写成**分拣结果表**（归属/条目/登记位置）+ 本次新发现的规律；A/B 线条目在对应台账**末尾追加**小节，每条只写"标题+来源号+发布时间+初步判断+待核项"，**不碰台账已有表格**。

### 2.4 巡检链路的踩坑（换环境先看）

| 现象 | 原因 | 解决 |
|---|---|---|
| `opencli: command not found` | 沙箱 PATH 无 opencli | 用**全路径** `/usr/local/bin/opencli` |
| opencli 报 `unknown option '--timeout'` | 无此选项 | 用环境变量 `OPENCLI_BROWSER_COMMAND_TIMEOUT=240` |
| opencli 第 2 次起 `Browser exec command timed out after 120s` | 搜狗对连续自动化检索限流 | **改 HTTP 直抓搜索页**（默认 `--wx-engine sogou`） |
| 巡检报告混进 2016–2024 旧招聘文 | 搜狗按相关度排序，老文权重高 | 时效过滤 `--wx-days 30` |
| 报告混进「录用公示」「取消公告」 | 这些是招聘流程的**结束/变更环节**，不是可投公告 | NOISE 加 `招聘.{0,8}公示`、`取消.*公告`（官网通道噪音 15+ → 11） |
| `mp-search account` 报 `Page.goto: Page crashed` | Playwright **自带 Chromium** 在沙箱下渲染 mp.weixin.qq.com 必崩（浏览器本身能开 example.com，只微信站点崩，`--no-sandbox` 也无效） | 走系统 Chrome：`launch(channel="chrome")`，按 [系统 Chrome → 自带 Chromium] 顺序探测 |
| urllib 抓政府网 `CERTIFICATE_VERIFY_FAILED` | 沙箱代理证书链问题（curl 正常） | 放宽 SSL 校验（只读公开页，`--verify-ssl` 可切回严格） |
| `mp-search account` 要扫码 | 需**公众号管理员**扫码，无法无人值守 | 日常别用它；每周人工补一次号内全量列表 |
| urllib 抓银行/企业站报 `UNSAFE_LEGACY_RENEGOTIATION` / `SSL_ERROR_SYSCALL` | TLS 指纹/旧重协商被拒（本机代理节点也会掐 TLS） | `fetch()` 已内置 **`/usr/bin/curl`（LibreSSL）兜底**；仍失败的源在本机关代理复核 `ijob/patrol/run.py --probe` |
| `-w "%CURLCODE%{http_code}"` 解析恒为 0 | curl 把 `%CURLCODE%` 输出成 `%CURLCODE200`（**无尾 %**） | rfind 标记不要带尾 `%`（探活脚本已修） |
| 智联按届子站（`{品牌}{年份}.zhaopin.com`）403 | 届次站带反爬且过期即废 | 勿硬爬：公告首发看「江苏国资」公众号，拿到新址更新 `patrol_sources` |

### 2.5 落地位置（本项目）

- **源配置（唯一真源）**：`/Users/zhugx/src/ijob/data/jobs.db` 的 `patrol_sources` 表 ｜ 探活：`python3 /Users/zhugx/src/ijob/patrol/run.py --probe`
- 巡检脚本：`/Users/zhugx/src/ijob/patrol/recruit_scan.py`（源读 DB；`--db` 可换库）
- 巡检报告：`码上职业/巡检记录/YYYY-MM-DD-新增招聘.md`（探活报告同目录）
- 去重状态：`/Users/zhugx/src/ijob/data/patrol_state/.scan-state.json` ｜ 源健康：同目录 `sources-health.json` ｜ 北森：同目录 `beisen-state.json`（2026-09-24 从 vault 迁入，换机务必整体迁移，否则历史公告会重复入库）
- ⛔ 旧入口 `00-信息源清单与每日巡检.md` / `01-官方站点源总表.md` 与 `工具/sources.yaml`、`工具/probe_sources.py` **已于 2026-09-21 废弃删除**，功能迁入 ijob（`patrol_sources` 表 + `patrol/run.py`）。
- ⚠️ 当前**无** WorkBuddy 定时任务跑本巡检（唯一定时任务是 09:40「每日公众号数据分析」）→ 巡检按需手动触发。

---


---

## 三、取数类坑位速查

| 坑位现象 | 根本原因 | 标准解决方案 |
|---|---|---|
| 岗位数据编错 / 缺失 | 只看了公告概述，没去报名站 | 走附录 A 实拉 `selectJobList`，用真实岗位表 |
| ⚠️ **公告写"网络报名"、实为邮箱报名** | 政府网公告的「网络报名」是宽泛表述，不等于在线系统 | 回正文 §报名办法 逐字核；真入口在**附件《联系方式》的电子邮箱**列。正文必须写明"无在线系统 + 以收到邮件时间为准"，并提示提前 2–3 天发送（2026-09-17 无锡梁溪实证） |
| ⚠️ **政府类主体主色/logo 取不到** | 政府网首页常只有国徽图，无独立 logo | logo 多藏在静态路径（如 `wxlx.gov.cn/static2022/images/logo.png`），curl 带 Referer 可直取；主色取 logo 众数色再**压深**（梁溪 `#E40900`→`#C60800`，白字对比 6.11:1），与栖霞同法 |
| ⚠️ **央企截止时点写成 24:00** | 转载稿把官方 `23:59` 四舍五入成 `24:00` | **回集团招聘官网核**（华电 `rencaishichang.chd.com.cn` 列表页可直读「招聘时间」）。2026-09-17 华电江苏实测官方为 **10-18 23:59** |
| ⚠️ **分行公告的「机构×岗位」矩阵抄错列** | 分行公告只在高校就业网转载，**纯文本版会把空单元格压掉**，只剩一串 `√√√`，列归属丢失（搜索摘要亦如此） | 只信**带真 `<table>` 的那份转载**（如 `51uns.bysjy.com.cn`），逐个 `<td>` 判（空=`<br/>`、有=`√`）。2026-09-17 中行江苏实测：本部仅管培、南京仅营销+综合服务、管培只在本部/无锡/常州/扬州 |
| ⚠️ **官方截止时点被"惯例"改错** | 见过 23:59 的案例后，把 **官方原文的 24 点**也改成 23:59 | **以该公告原文为准**：中行 2027 全球校招官方就写「北京时间 2026 年 10 月 9 日 **24 点**」→ 照抄 24 点（别机械化套用华电 23:59） |
| ima 取目录报 code:51 | `search_knowledge_base` limit>20 | limit 必须 ≤20，靠 next_cursor 翻页 |

---

## 附录 A1：智联招考报名站接口逆向（实拉岗位，如 jsrg.zhaopin.com）

> 很多国企/事业单位校招用智联招考 SPA（`xxx.zhaopin.com/zk/#/...`，uni-app）。公告只写"岗位详情在报名页查看"，真实岗位在报名站接口里。直接拉接口，段 5 用真实岗位表，一文看懂。

**接口基址**：`https://zkapi.zhaopin.com/zhaokao/api/zhaokao/h5`（必须是 `/zhaokao/h5` 段，否则 404 `接口不存在`）。
**必带请求头**：`Content-Type: application/json`、`Source-Channel: 6`、`x-zp-device-sn: <任意uuid 或空>`、`Referer: https://<站点域名>/`。缺头报 `code:490 非法请求`。

**取数三步**：
1. `GET /cms-menu/list-portal` → 菜单树（公告 / 在线报名 / 我的报名），拿公告 menuId。
2. `GET /cms-menu/listArticleByMenuId?menuId=<公告id>` → 公告正文 HTML（只含概述，不嵌岗位表）。
3. `GET /job-info/selectJobList`（可不带参）→ **全部岗位数组**，字段：`id` / `jobName` / `enrollmentUnit`(用人单位) / `enrollmentPlaces`(招聘人数) / `eduRecord`(学历) / `jobSalary` / `jobDescription`(部门+岗位职责+任职条件) / `jobGroupName`。岗位名带 `-校招` / `-社招` 后缀，据此切分校招/社招。

**踩坑**：`dept-job-list/list`、`job-group-list` 在 JS 里是**页面路由**不是 API，直接打会 404；真实岗位接口是 `/job-info/selectJobList`。`siteId` 可从公告接口 `detail.siteId` 取到，但 `selectJobList` 不传 siteId 也按当前站点返回全部。

**落表建议**：段 5 放「校招岗位清单」斑马纹表（# / 岗位名称 / 用人单位**全称** / 人数 / 学历 / 专业方向简要）；专业方向标签云从 `jobDescription` 真实任职专业提炼，不拍脑袋。完整 JD 引导读者去报名站（即「阅读原文」指向的官方站）。

---


---

## 附录 A2：银行自建招聘站接口逆向（杭州银行实例，2026-09-20 完整打通）

> 银行自建招聘站多为 Vue/React SPA，**公告只写"岗位详见官网"**，真实岗位与学历/专业口径在 XHR 接口里。下面是**一条完整打通的链路**，同类自建站（徽商、南京银行等）可照搬思路。

**站点**：`https://myjob.hzbank.com.cn/hzzp-apply-web/static/index.html#/index`
**前端路由**：`/employ/school`（校招）· `/employ/social`（社招）· `/employ/ungraduate`（实习）· `/employDesc/:id`（岗位详情）
**API 基址**：`window.location.origin + "/hzzp-apply"` —— ⚠️ **不是** `/hzzp-apply-web`（前者是静态资源目录，后者才是接口根）

| 用途 | 接口 |
|---|---|
| 职位列表 | `GET /hzzp-apply/employInfo/queryEmployInfosList?page=0&size=300&positionName=&positionType=01&organNo=&batchNos=&positionCategorys=` |
| 在招批次 | `GET /hzzp-apply/employInfo/queryActiveBatchList?positionType=01` |
| 公告列表 | `GET /hzzp-apply/systemNotice/show?positionType=01` |
| 公告正文 | `GET /hzzp-apply/systemNotice/findById?id=<noticeId>` |

- `positionType`：**01 = 校园招聘，02 = 社会招聘**（不传则两者混返，别被社招岗带偏）。
- 响应包是 `{errorCode, errorMessage, result:{content:[...], totalElements}}` —— **正文在 `result.content`，不在顶层 `content`**（第一次读空就是栽在这）。
- 列表字段：`positionName` / `organizationName`（招录单位，用来筛"南京分行"）/ `workSpace`（工作地点）/ `recruitNum`（**0 = 未披露人数，不要写成"招 0 人"**）/ `startTime` / `endTime` / `jobDesc` / `jobRequire`（**学历与专业口径逐字取自这里**）/ `batchNo`。
- 公告正文是 HTML 富文本；**岗位明细不在公告里**，必须另打职位列表。

**三个坑**：
1. **别直接 curl 静态 chunk**：webpack 的 `f.p="../"`，chunk 真实路径是 `/hzzp-apply-web/static/js/<序号>.<hash>.js`（**带序号前缀**）。漏了序号会落到 SPA 兜底页（固定约 1038 字节的 HTML），**看起来"下载成功"其实是假的**。
2. **接口要用同源 fetch**：用 `ego-browser` 打开站点后在页内 `fetch("/hzzp-apply/...")`（带 `Accept: application/json`），避免跨域与鉴权问题。
3. **筛选靠参数不靠点 UI**：页面上的"工作机构"筛选项不是叶子节点，`el.click()` 常点不动；直接用 `organNo` / `positionName` 参数筛更稳（本次用 `positionName=南京` 一次拿到 6 条）。

**同类入口形态（已核实）**：徽商 `https://rczp.hsbank.com.cn/pc/`（职位详情 `/pc/#/InternshipDetails?id=<id>&type=1&channelCode=<code>`）;恒丰 `https://career.hfbank.com.cn/xyzp/zwcx/index.shtml`（静态页，curl 可直抓）;南京银行 `job.njcb.com.cn`（Vue SPA → 抓 `static/js/app.*.js` 拿 `API_ROOT`）。
- 两者共用：`mp-html`（排版方言）、`mp-publish`（推草稿）、`mp-search`（如需对标同类招聘号热度）。


---

## 附录 A3：北森招聘门户（`*.zhiye.com`，2026-09-21 南瑞继保实证）

**识别特征**：页面约 36KB、正文几乎空、`Powered by Beisen` → 北森 SPA。**curl 只能拿到外壳，必须走 ego-browser 渲染**。

**第 1 步 · 从外壳里挖配置**（省掉一半瞎猜）：页面内嵌 `var BSGlobal = {...}`（约 34KB 的一段 JSON）。用**花括号配平**把它抠出来再 `json.loads`，可得：

- `tenantInfo.Id`（tenantId）、`tenantInfo.Domain`、`tenantInfo.Abbreviation`、`tenantInfo.SystemVersion`
- `PortalId`、`Pages[]`（`Code` 取值含 `home` / `login` / `jobs` / `Campus` / `CampusList` / `CampusDetail`）、`Navigations[]`

**第 2 步 · 路由别猜，读 `<a href>`**：`document.querySelectorAll('a')` 逐个打印 `textContent + href`。南瑞继保的**职位列表 = `/campus/jobs`**。
⛔ 别用 `el.click()` 去点「搜索职位」——它不跳转；**直接 `openOrReuseTab('https://<domain>.zhiye.com/campus/jobs')`**。

**第 3 步 · 列表页一次拿全量岗位**（读 `innerText` 即可）：`全部职位（共 N 个）`，每条 = 岗位名 / 招聘类型 / 全职 / 工作地点 / **归属部门**。

**第 4 步 · 岗位详情：⚠️ 手风琴陷阱（本次最大的坑）**
职位详情是**手风琴**——**一次只能展开一个**，但**已折叠的面板仍留在 DOM 里**（`innerText` 照样读得到）。
⇒ 用 `body.innerText.indexOf('任职资格')` 会**永远命中列表里第一个岗位**，从而得出「所有岗位要求完全相同」的**假结论**（本次初判即如此，差点写错）。
✅ **正解**：① 每个岗位**重新加载页面**（加 `?rnd=N` 强制刷新），只展开目标岗位；② 只读**可见**容器 —— `querySelectorAll('*')` 过滤 `offsetParent !== null` 且 `innerText` 含「专业要求」、长度 80~1400，**按长度降序取第一个**。

**字段**：`工作职责` / `任职资格`（内含 `学历要求` 与 `专业要求`）。⚠️ **学历逐岗位不同**（南瑞继保：研发/国内销售 硕士+、国际销售 硕士、技术支持/试验/信息技术 本科可报），**务必逐岗位取，不要按企业统一口径写**。

**首页 `/campus` 别漏的三样**（都在 `innerText` 里，无需调 API）：
1. **校招流程时间线**：网申投递 / 在线测评 / 宣讲会 / 面试 / 录用签约 各段起止日期 ← **报名截止就在这里**（南瑞继保 = 08-25 ~ 10-30，比某聚合站写的 10-24 准确）
2. **「加入公司的 N 个理由」**：科研实力、成长机制（如脱产培训 + 师徒帮带）、福利清单 ← 「单位来头」与「码上君解读」段的直接素材
3. **校招问答 FAQ**：**官方自己写的 FAQ 就是最好的长尾素材**（含「最多投几个岗位」「应届生毕业时间范围」等），点题目即展开答案

**四个坑**：
1. **`grep -a "@@@"` 会截断多行输出** —— 只有含 `@@@` 的那一行被打印，多行 `cliLog`（如 pretty-print 的 JSON）**全部丢失**，会让你误判「接口/资源不存在」。**调试时把输出压成单行**（`JSON.stringify(x)` 不加缩进参数）。
2. `performance.getEntriesByType('resource')` 在这类门户上**拿不到业务接口**（条数很少）→ **别在这上面耗时间，直接读 DOM**。
3. 候选 REST 路径（`/api/portal/job/list` 等）会**返回 SPA 外壳**（状态 200、内容 = index.html）—— **200 不代表接口存在**，用「返回长度 ≈ 外壳长度」当判据。
4. 同类入口（ATS 已核实为北森）：南瑞继保 `nrec.zhiye.com/campus`；中核华兴 `cnecc.zhiye.com`、中国核电 `cnnc.zhiye.com`（见 `jobs.db:patrol_sources` 的 `beisen` 类源）。
