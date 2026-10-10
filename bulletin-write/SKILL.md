---
name: bulletin-write
description: 官方公告重排引擎（B 线·机关/事业单位/医院/国企等有正式公告长文的招聘线）。公告原文一字不改只做排版，前后加划重点、三宫格、岗位表、FAQ、CTA。触发词：公告重排、处理这个公告、原文重排、bulletin、招聘公告成稿。
version: 0.2.0
---

# bulletin-write · 官方公告重排引擎

> **定位（朱总裁定）**：凡有正式公告长文的招聘线，弃用 job-write 的 8 段解读骨架，改用
> **「原文重排骨架」**——公告原文一字不改，只做拆段与关键数字加粗；AI 的增值件收缩为四样：
> 划重点、三宫格、岗位表（附件提取）、FAQ。真实成稿样例见 `references/samples/`。

---

## 一、骨架（固定七件，顺序不可换）

| # | 件 | 内容来源 | 纪律 |
|---|---|---|---|
| 1 | **码上君划重点** | 从公告提炼 3-5 条 | 每条一个钩子；编制/用工性质必须有一条如实交代 |
| 2 | **数据三宫格** | 截止 / 性质 / 规模 | 用 layout_kit.quad_grid 传 3 格 |
| 3 | **岗位表** | 官方附件逐行核 | 岗位数、人数加总必须等于公告总数（守恒） |
| 4 | **公告原文全文** | 公告原文照录 | ⛔ 一字不改；只做拆段、关键数字加粗、长条款转小字注脚 |
| 5 | **常见问答** | 从公告提炼 6-8 问 | 完整主谓宾自然问句（对齐搜一搜 Answer Box） |
| 6 | **CTA** | `素材/组件/cta-客服码单码.html` | layout_kit.cta() 自动替换品牌色 |
| 7 | （来源小字） | 原文尾部 | 附件说明＋落款＋原文链接 |

**砍掉不写的**（相对旧 8 段）：单位来头原创段、码上君解读黄底卡（内容并入 FAQ）、
资格禁入重写卡（原文条件节已覆盖）、实操建议。

## 二、流程（十步）

```bash
# ① 拉公告原文：先 WebFetch；被拦(Bad Request/412)→curl 带浏览器 UA 直拉
# ② 查重：emit_briefing --state-audit + ls */待发布/ | grep <单位专名>（按单位专名，禁标题匹配）
# ③ 没写过→补台账：/tmp 备份总表 xlsx → 招聘信息 sheet 加行（单脚本一次读一次写+断言+重读校验）
# ④ 投料单：emit_briefing "<单位>"（[miss] 时按脚本指引走补台账路径）
# ⑤ 附件逐行核（守恒：人数加总=公告总数）——按格式选工具：
#    .xlsx→openpyxl；旧版 .xls→xlrd（openpyxl 不认）；.pdf→pdfplumber；
#    岗位表以「页面图片」内嵌的（正文无附件链接时 grep 页面 <img>）→下载 png 后多模态直接读表；
#    附件直下返回 HTML=防盗链 → curl 加 -e "<公告页URL>" Referer 重下；
#    合并单元格以 extract_text 版面序复原，别漏行
# ⑥ 填 config → 生成排版（内建断言见 §五）：
python3 ~/src/skills/bulletin-write/scripts/gen_bulletin.py <config.py 路径>
# ⑦ 封面：build_cover.py --type 社招；无干净官方 logo → 纯母版不加胶囊（⛔ 不自制底版）
#    （工作目录不在公告页时，--out 用绝对路径）
# ⑧ 推送：wx_pipeline.py --profile mashang --html ... --cover ... --source-url ... --digest "手动摘要≤120字"
#    ⛔ 本骨架的 HTML 无 SEO 摘要块，--digest 必须显式给（gen 结束时会打印 DIGEST），否则落到自动兜底
# ⑨ 回填：emit_briefing --mark "<单位>" --to draft --facts "..."；总表该行 内容状态→draft
#    ⛔ --facts 必须是 KEY=VALUE 分号连接（如「岗位=15岗23人；报名=10-16 17:00截止」），纯叙述文本会被拒；
#      总表检索词用单位全名子串（注意「经开区」匹配不到「经济开发区」这类简称/全称差异）
# ⑩ 排期：按报名截止升序报朱总定夺；窗口冲突时 ⛔ AI 不自作主张砍稿（多稿同窗=人工取舍）
```

## 三、config 编写规范（每篇唯一要写的东西）

复制 `scripts/config_example.py` 填空；真实成稿样例在 `references/samples/`（复用时改 OUT 路径）。

- `TITLE`：≤64 字，前 21 字带钩子（单位+人数/亮点）；
- `DIGEST`：≤120 字单行，含截止时间、硬门槛、入口（域名/地点/电话）；
- `HIGHLIGHT`：dict(sub, intro, items, numbers)；
- `GRID`：3 个 (大字, 小字) 元组；
- `POSITION_TABLE`：dict(title, note, headers, rows, widths, footnote) 或 None；
  - 附件岗位 ≤15 行 → 逐岗位列表；
  - **>15 行 → 分单位汇总表**（岗位数/人数/用人方式/学历构成/报名邮箱）+亮点注脚，明细回指官网附件；
- `ORIGINAL`：list of (节标题或 None, [段…])；段用 `("p", 文本)` / `("note", 小字)` / `("sub", 小节标题)` / `("url", 明文网址卡)`；
  原文文本一律照抄，只许在关键数字外面包 `<strong>`；节标题用原文编号（一、二、三…），不添加自拟后缀；
- `FAQ`：[(问, 答)] 6-8 条；
- `SOURCE_NOTE`：附件+落款+原文链接小字；
- 可选：`BRAND`/`BRAND_DARK`（品牌色覆盖）、`ALLOWLIST`（指纹豁免）、`SOURCE_MD`（同步产出源稿）、`DATE`/`SOURCE_URL`。

## 四、硬纪律（红线，违者打回）

1. **原文一字不改**：只拆段、加粗、长条款转小字。改写=回退到解读稿模式，⛔；
2. **硬信息只认公告原文与官方附件**：人数加总守恒；缺口写「公告未披露」；
   **编制属性原文没写就写「公告未披露/签订劳动合同」**，严禁脑补「进编」（原文写了「劳动合同或派遣」就直说无编制）；
3. **岗位表必须守恒**：行数×人数加总=公告总数，不符=停笔查附件；
4. **来源声明**：划重点 intro 末尾必须带「码上职业仅做排版整理，未改动原文表述」；
5. 出口固定 `--profile mashang`；`wx_draft.py` 默认 manba，漏写=事故；
6. **三件套质检口径**：`job-write/scripts/verify_draft.py` 按 8 段骨架指纹校验，**不适用于本骨架**——
   质量门禁＝`gen_bulletin.py` 内建断言（原文守恒/指纹/比较级/自证句/section 配平/空 span）
   ＋推送链路的 `wx_dialect_check`＋draft/get 五项验收；
7. **写划重点/摘要禁用「最多/最高…之一」类词**——有原文依据也换成数值区间表述（机检会拦）；
8. **同系列多批次隔离**：每条划重点、FAQ 答案必须回**本批次**公告 find 溯源，严禁凭上一批记忆搬。

## 五、机检与坑位

**gen_bulletin.py 内建断言**（写盘前逐条过，命中即失败）：
原文守恒（ORIGINAL 原样出现在成品）／编造话术指纹（指纹词命中 TITLE+DIGEST+划重点+三宫格+岗位表+FAQ
但不在 ORIGINAL 原文）／A 类自证句／无据比较级／section 配平／禁空 span·div·th·position／`<title>` 在位／DIGEST ≤120。

| 坑 | 症状 | 防御 |
|---|---|---|
| `layout_kit.table` headers 传元组列表 | 表头渲染成 `('序号','8%')` 字面量 | headers 传纯文本列表，widths 单独传（其 docstring 写反了，以实现为准） |
| `layout_kit.doc_open` 参数不带 `<title>` 标签 | 流水线报「未能提取到文章标题」 | doc_open('`<title>`…`</title>`') |
| quad_grid 外层 td 无 border:0 | 微信渲染出矩形框线套住圆角卡 | layout_kit 已修（border-collapse:collapse＋td border:0） |
| 本骨架 HTML 无 SEO 摘要块 | 摘要落「自动(正文开头兜底)」 | 推送必带 `--digest` |
| gov 附件下载回 HTML | openpyxl BadZipFile | curl 加 `-e <公告页URL>` Referer |
| 机关线巡检报告投料单 [miss] | parse_patrol_report 列序与机关线报告不符（待修） | 按「补台账→重跑投料单」路径绕过 |
| 岗位表以页面图片内嵌 | 附件列表里找不到简介表 → 误判「无岗位明细」 | 正文无附件链接时 grep 页面 `<img>`，下载 png 后多模态直读 |
| 旧版 .xls | openpyxl BadZipFile | `xlrd`（venv 已装） |
| `--facts` 非 KEY=VALUE | `--mark` 报 facts_invalid，状态没回填 | facts 用「岗位=…；报名=…」分号连接格式 |

## 六、验收清单（推送后）

1. `[VERIFY] ✅ draft/get` 五项绿（标题/正文/容器/空样式/图片URL）；
2. `wx_draft.py get --media-id ... --json` 回读 `digest` 非「自动兜底」；
3. `--profile mashang` 日志首行确认；
4. **`wx_draft.py list` 确认同名稿只有 1 篇**（`--update-auto` 查重失败会**静默造重复稿**）；
5. 状态回填：`内容状态.json`＋总表行 → draft；
6. 群发后当天归档（git mv 进 `已发布/`）＋台账/状态推 published。

## 七、写作纪律（填 config 时的人工检查项）

| 纪律 | 要点 |
|---|---|
| **B 类无据推测** | FAQ 答案只写公告说的；后果类判断（「逾期视为放弃」）必须能在原文 find 到 |
| **C 类官腔套话** | 划重点提炼时跳过文化理念/薪酬口号，只留可核实事实 |
| **「引号必溯源」** | 「」引用的内容须在本单位公告原文 find 得到 |
| **加粗密度 ≤5.5 处/屏** | 原文重排只加粗关键数字天然低密度；删加粗只能逐条白名单，禁按字数阈值批量删 |
| **主色取主体 logo 众数色** | config `BRAND/BRAND_DARK` 覆盖；拿不到 logo 用默认 B 线蓝，禁沿用上一篇色板 |
| **「公告未披露」是信息还是填充** | FAQ 若连续几问答完读者行动不变 → 删问；但编制/薪酬缺口**必须**如实写「公告未披露」 |
| **推送前自检** | title≤64 前 21 字钩子／明文 URL break-all／页脚四无（来源行/免责/预告/防骗）／封面 RGB PNG／source-url 指官方源 |

> ❌ **明确不在本技能范围**：招聘站 SPA/接口抓取（智联/51job/银行招聘站）——那是 job-write 管 A 线的武器；
> 本线是政府官网静态公告页。
