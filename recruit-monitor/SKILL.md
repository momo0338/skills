---
name: recruit-monitor
description: 政府机关/电力电网/铁路/银行等招聘官网巡检脚本的架构、扩线方法与实测坑位。当用户要「新增一条巡检线」「把某行业加进巡检」「巡检报告数字对不上」「巡检抓不到条目」「SPA 空壳源」「分层加总≠主口径」「栏目页被当公告」「改巡检脚本」时使用。关键词：巡检、监测、快照 diff、四层收敛、有效性深检、守恒自检、待核、存疑、招聘公告抓取。
agent_created: true
---

# 招聘官网巡检脚本 · 架构与扩线 SOP

> 实战来源：`码上职业/巡检记录/`（7 脚本 5895 行，四条线：机关 / 电力电网 / 铁路 / 银行）。
> ⛔ 本技能只讲**巡检脚本工程**；内容成稿走 `job-write` / `school-write` / `hospital-write`。

## 〇、开工前必读

| 项 | 说明 |
|---|---|
| 唯一数据源 | `单位与招聘信息总表.xlsx`，**只读**。该文件 **git 未跟踪 ⇒ 改前 `/tmp` 全文件备份是唯一回滚路径** |
| Python | 必须 `/Users/zhugx/.workbuddy/binaries/python/envs/default/bin/python3`（macOS 系统 python3 是 LibreSSL 且无 openpyxl） |
| 改脚本纪律 | `/tmp` 备份 → **隔离回归法**（见 §五）→ 改后**全量重跑 + 核对守恒自检行** |

---

## 一、标准架构（六步流水线）

所有巡检线共用同一套口径，**新增线必须照抄这个骨架**：

```
1. 加载 xlsx → 清洗 URL → 归一化去重 → 映射回全部关联单位
2. 抓列表页 → 解析条目（标题 + URL + 日期 + 来源）
3. 四层收敛：open 真·开启 / proc 流程后续 / event 活动 / nav 栏目入口
   ＋ 噪音剔除（遴选/政策/采购/物资）
4. 快照 diff（新增 / 滚出）→ snapshots/<线>/<域名>_<md5前8>.json
5. 有效性深检：仅对 open 抓文章页（URL 去重、8 并发）
   ① 完整标题重分层（列表标题被截断的，按文章页完整标题改判）
   ② 子句级报名截止提取
6. 四层分层输出：有效 / 长期 / 已过期 / 待核（＋存疑/新近兜底）
```

**报告章节固定序**（gov/power/rail/bank 已统一）：
`一、概览` → `一之二 抓取失败源分类`（银行线） → `二、源状态明细` →
`三、当前在架（仅有效/长期）` → `三之二 流程后续` → `三之三 活动` →
`三之四 栏目入口` → `三之五 已过期/待核` → `四、本次新增` → `五、下次运行`

---

## 一之二、🔴 母本没有的层就别硬加（`adj` 伪设计教训）

2026-09-29 银行线自带一栏「职业资格·相邻 `adj`」，跑出来**恒为 0**。
根因不是词表写错，而是**母本 gov 的 `tier()` 只返回 `noise/proc/event/open/None` 四值**，
`adj` 那个分支在任何标题上都不可能命中。

🔴 **加层前先证明它能产出条目**：把判据函数写好后，拿全量快照跑一遍
`Counter(tier(i["title"]) for 快照里所有条目)` —— 产出 0 条的层是伪设计，删掉比留着好。
留着更糟：报告里一个恒 0 的栏位会被下一个人当成「功能已实现只是今天没数据」。

**真正该补的是 `nav`（栏目入口层）**，银行线实测数据给的答案：
46 条命中招聘词根的标题里，**12 条是裸栏目名**（校园招聘/社会招聘/实习生招聘/内部招聘/
专项招聘/人才招聘/诚聘英才/招贤纳士/招聘公告/招聘职位/汇丰环球招聘官方网站），
URL 指向 `/socialJob`、`/p1.html`、`/aboutboc/bi4/` 这类子栏目入口，不是公告。
它们全部混进 `open`，把主口径**虚增近一倍**（58 → 实为 33）。

```python
NAV_TITLE_SITE_RE = re.compile(r"(官网|官方网站|网站|首页|入口|导航)")
NAV_TITLE_ABBR    = re.compile(r"^(社招|校招|招人|招才|诚聘|纳新)$")
NAV_TITLE_REAL_RE = re.compile(r"(20\d{2}|第[一二三四五六七八九十\d]+[批轮]|批次|届|"
                               r"分行|支行|总行|总部|中心|分公司|事业部|部门|学院|校区)")

def is_nav_title(t):
    if NAV_TITLE_SITE_RE.search(t) or NAV_TITLE_ABBR.search(t): return True
    # 短标题豁免：带年份/届次/批次/机构词的短标题是真公告（如「2025秋季招聘」）
    return len(t) <= 8 and not NAV_TITLE_REAL_RE.search(t)
```

> 🔴 **短标题规则必须带豁免**，否则「2025秋季招聘」这种真公告会被误杀。
> 双向回归：① 裸栏目名全判 nav ② 带真公告信号的短标题全判 open —— 两条都得过。

### 🔴🔴 SPA 的 `innerText` 会在词之间插空格，关键词匹配前必须去空白

抽查 ego 补回的条目时抓到实测样本（农行招聘站顶部导航）：

```
首 页校园招聘社会招聘专项招聘帮 助
```

**两条判据同时失效**：① 16 字 > ≤8 规则 ② `innerText` 保留排版空格，
「首页」「帮助」都被劈开，`NAV_TITLE_SITE_RE` 匹配不上 ⇒ 混进主口径。

```python
if NAV_TITLE_SITE_RE.search(re.sub(r"\s+", "", t)):   # ← 关键：去空白后再匹配一次
    return True
```

🔴 这是 **SPA 抽条通用坑**，不只 nav 层：凡是用 `js()` 取回的 `innerText` 做
关键词判断（`is_noise` / `tier` / 标题清洗），都要先归一化空白。

---

## 二、🔴 词表复用铁律（不要复制）

**永远 `import` 主线脚本的词表，不要复制粘贴**——复制必然口径漂移。

```python
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gov_recruit_monitor as G      # 机关线是词表母本

REC_KW = re.compile("(?:" + G.REC_KW.pattern + ")|(?:" + 本线额外词根 + ")")
def is_noise(t):  return G.is_noise(t) or bool(本线噪音_RE.search(t))
def tier(t):
    if not REC_KW.search(t): return None
    if is_noise(t):        return "noise"
    if G.REC_PROC.search(t):   return "proc"
    if G.REC_EVENT.search(t):  return "event"
    return "open"
```

深检也直接复用：`G.check_item_validity()` / `G.extract_deadline()` /
`G.article_full_title()` / `G.is_true_longterm()` / `G.validity_status()` / `G._throttle()`。

> 📌 `G.REC_NOISE_SELECT` 含「银行」，但 `G.is_noise` 有 `"遴选" in title` 前置守卫，
> 实测 7 条银行标题 tier 全对 —— **银行线直接复用不会误伤**，不必自己造一套。

### 🔴 `tier_full` 必须写回，否则「完整标题重分层」是空转

`G.check_item_validity()` 内部会用**文章页完整标题**重跑 `tier()` 并把结果放进
`v["tier_full"]`。**调用方不把它写回条目，这一步就等于没做** —— 列表页被截断的标题
（`…招聘公告` 少了机构名/批次）本该改判的条目会全部留在 `open` 里。

```python
sink = {"proc": "proc", "event": "event", "nav": "nav", "noise": "noise"}
for r in results:
    keep = []
    for i in r["rec"]:
        v = vmap.get(i["url"].split("#")[0]) or {}
        tf = v.get("tier_full")
        if tf and tf != "open":
            i["tier_final"] = tf
            i["full_title"] = v.get("full_title", "")
            r[sink.get(tf, "noise")].append(i)   # 移出 rec，归入对应桶
        else:
            keep.append(i)
    r["rec"] = keep
# ⛔ 改判必须在 vstat 统计之前做完
```

🔴 **顺序是硬要求**：先按 `tier_full` 缩小 `rec`，再对留在 `rec` 里的条目统计 `vstat`。
反了就会出「主口径已缩小、守恒却按旧数算」的自相矛盾报告。

---

## 三、🔴 分层加总必须＝主口径（守恒自检）

**每份报告的概览必须写死这一行**，且必须把「存疑/新近」也列出来：

```python
s = sum(vstat[k] for k in ("有效","长期","已过期","待核","存疑","新近"))
ok = "✅ 守恒" if s == rec_total else "❌ 不守恒（差 %d）" % (s - rec_total)
A(f"> **守恒自检**：…＝ **{s}**；主口径 **{rec_total}**；{ok}")
```

**为什么必须写**：2026-09-29 实测电力报告「主口径 659 / 分层加总 28」——
概览漏了 `存疑/新近` 两态（631 条），报告自相矛盾且没人发现。
🔴 漏写「存疑」行 = 必出矛盾报告，这是本工作区最容易被忽略的 bug。

**自查脚本**（按 `## ` 切段，正文表格行实测 vs 概览声明）：

```python
import re
from collections import Counter
t = open(report, encoding="utf-8").read()
secs = {p.split("\n",1)[0].strip(): p for p in re.split(r"\n## ", t)[1:]}
ov = secs["一、概览"]
main = int(re.search(r"在架招聘公告（真·开启[^）]*）\*\*\s*\|\s*\*\*(\d+) 条\*\*", ov).group(1))
lay = {k: int(re.search(rf"├?\s*{k}[^|]*\|\s*(\d+) 条", ov).group(1))
       for k in ["有效","长期","已过期","待核","存疑","新近"] if re.search(rf"{k}[^|]*\|\s*(\d+) 条", ov)}
rows = lambda seg: [l for l in seg.split("\n") if l.startswith("|") and "http" in l]
s3  = rows(secs.get("三、当前在架招聘公告（真·开启·有效性核验后，按单位）",""))
s35 = rows(secs.get("三之五、已过期/待核（不混入主口径，供核对与复盘）",""))
actual = sum(1 for l in s3+s35 for k in ["有效","长期","已过期","待核","存疑","新近"] if f"| {k} |" in l)
print(main, sum(lay.values()), actual, "✅" if main==sum(lay.values())==actual else "❌")
```

🔴 **正文渲染必须与概览分层用同一个字段**。反面案例：去重逻辑改了 `d["new_rec"]`，
报告渲染的却是 `d["new"]` —— 同一条公告被 3 个省站各印一遍，概览却写「均已去重」。

---

## 四、🔴 抓取判别（0 条目 ≠ 改版）

| 现象 | 含义 | 处理 |
|---|---|---|
| HTTP 200 + 解析出条目 | 真抓到 | 入快照 |
| **HTTP 200 + 0 条目** | **SPA 空壳**（软 404 会让任意路径返回同一首页且无异常信号） | 标记待适配，走 ego |
| 412 / 403 | **有 WAF**，不是域名不存在 | 退避重试（`G._WAF_JITTER` 抖动） |
| 5xx | 临时故障 | 退避重试，不当终局 |

- 判「软 404 回退首页」：**响应字节数 + 页面标题指纹**，不看 HTTP 码。
- 🔴 **412/403/5xx 必须退避重试不当终局**；同源最小间隔按二级域（netloc 末三段）`G._throttle`。
- 🔴 **所有来源 q<3 拒落盘**（空壳会被索引表当已下载勾稽）。
- 跨源去重**必须排在有效性深检之前**（省站转载总部要闻会把 1 条算成 3 倍；深检最贵，去重后再深检能大幅降低被 WAF 403 概率）。
- **深检的过滤维度不能与业务决策混**：调用方已传全部 URL 时，深检内部再按时间窗裁剪会静默丢弃条目。改按**条数分批**（每批独立 ego task space 名），时间维度交给 `validity_status` 判层。

---

## 四之二、🔴 告警源逐个定性：四类根因（2026-09-30 银行线 38 源实测）

⛔ **「抓不到」必须分四类，处置动作完全不同**。混在一起会导致「重跑一万次也拿不到」的白干：

| 类 | 判据（必须两条路都走通） | 处置 |
|---|---|---|
| **A 域名已死** | **两路 DoH**（`dns.google/resolve` ＋ `cloudflare-dns.com/dns-query`）均 `Status=3`（NXDOMAIN） | ⛔ **ego 无解**，必须换官方入口，回填 xlsx |
| **B 无 www 被本机 TUN 误路由** | DoH 拿真实 IP → `curl --resolve host:443:IP` 直连 **200** | ✅ **URL 没错**，加 `www.` 或换 host，**别改 xlsx** |
| **C 解析器不适用** | 200 且字节数大（几万～百万）但**可见文本仅 8～1000 字** | 纯 JS 渲染 ⇒ 专用解析器 / 抓后端 API / ego |
| **D 未定性** | 以上都不成立 | ego 真浏览器或换网络出口再判 |

🔴 **本机代理坑（macOS + Clash TUN，务必先读）**：
- `HTTP_PROXY/HTTPS_PROXY` 指向 sandbox 端口；**DNS 全部返 `198.18.x.x` fake-IP**。
- ⛔ **`curl --noproxy '*'` 无效**（fake-IP 仍被 TUN 接管）；⛔ **`dig @223.5.5.5` 也会被劫持**（连 DNS 查询本身都走 TUN）。
- ✅ 唯一可靠路径：**DoH（走 HTTPS）拿真实公网 IP → `curl --resolve`**。
- 📌 曾据此差点误判「渤海银行 URL 错」——实为无 `www` 被误路由，加 `www.` 后 200/187KB。**判死 URL 前必须先走 DoH＋resolve。**

### 入口失效时的正确做法：`URL_ALIAS` 兜底表（不改 xlsx）

```python
URL_ALIAS = {
    "https://zhaopin.hxb.com.cn": ["https://hxb.hotjob.cn"],   # A 类：旧域名已注销
    "https://cbhb.com.cn/.../index.shtml": ["https://www.cbhb.com.cn/.../index.shtml"],  # B 类
}
```
- `work()` 里：主 URL 失败**或解析出 0 条目** → 依次试 alias，成功则仍记在原机构名下。
- 🔴 **alias 只认「解析出条目」，不看 HTTP 200**——实测 `hxb.hotjob.cn` 返回 200 但是 0 条 SPA 空壳，看 200 会把空壳当成功、**掩盖真实告警**。
- 🔴 **命中必须在报告「源状态明细」显式披露**（URL 列打「✅别名兜底→ 真实入口」），否则 URL 列仍是失效旧入口，看不出实际抓了哪个。
- ⛔ 别名表是**脚本内兜底，不等于改表**；xlsx 回填仍需朱总放行。

### 🔴 多源共用同一 URL ⇒ 主口径必须全局去重

**实测**：邮储 ＋ 中邮理财 都写 `psbc.com/cn/gyyc/rczp` ⇒ 同一份 2027 校招公告被算成 **2 条「有效」**，且明细按源遍历又印两遍 ⇒ **概览 3 条 / 明细 2 行，自相矛盾**。

```python
rec_index = {}                      # URL → 条目（全局去重）
for r in results:
    for i in r["rec"]:
        k = i["url"].split("#")[0]
        it = rec_index.setdefault(k, i)
        it.setdefault("banks_all", [])          # ⛔ 不能只在 if 分支里初始化
        for b in r["target"]["banks"]:
            if b not in it["banks_all"]: it["banks_all"].append(b)
vstat = Counter(i.get("vstat") or "待核" for i in rec_index.values())
rec_total = len(rec_index)
```
- 🔴 **`banks_all` 必须用 `setdefault` 两分支统一初始化**——写成「只在 `if k not in rec_index` 里 `i["banks_all"]=[]`」会让**同一 URL 第二次出现走 else 分支直接读该 key ⇒ `KeyError`**，且 `--ego-fallback` 单轮 20+ 分钟，崩一次代价极高（2026-09-30 实测白跑 22 分 56 秒）。
- 📌 **改报告层数据结构 ⇒ 先用构造数据做单元回归**（3 条假数据 3 秒复现+验证两个分支），⛔ 不要靠全量跑试错。
- 🔴 **根因分布里「已过期」必须单列，不能塞进待核桶**：它是**已确认**、不是「待核的一种根因」。混进去会出现 `A+B+C ≠ 概览待核数` 的自相矛盾报告。正确表述：`待核共 N 条 ＝ A + B + C；另「已过期」M 条单列`。
- ⛔ **`rec_total` 绝不能再用 `sum(len(r["rec"]) for r in results)` 覆盖**（那是源视角，会重复计数）——曾因此出现概览/明细打架。
- 报告「三」与「三之五」两节**都必须走同一份 `rec_index`**，否则各算各的。
- 源状态明细表仍按源展示（源视角，不参与守恒），但要标明该源用了哪个 `used_url`。

### 🔴「待核」必须按根因拆 A/B（否则无法判断能不能写稿）

「待核」是**证据不足**的第三态，⛔ 既不等于「已过期」也不等于「在招」。报告必须拆开：

| 根因 | 含义 | 能否直接写稿 |
|---|---|---|
| **A 文章页未取到** | 公告在架但正文抓取失败（0/400/412/403） | ⛔ 不能，**先修抓取**；抓到正文拿到截止日再判 |
| **B 正文无截止日** | 正文抓到了，公告本身没写截止（常见「邮箱投递/仅受理网上报名」） | ⚠️ 需人工判窗口表述，**⛔ 不得推断截止日** |

- 🔴 **实测铁证**（银行线 2026-09-30）：A 类 37 条逐条回原文复核后 → **15 条其实在招、14 条早已过期**，此前全错标「待核」。**只要文章页能抓到，截止日就能提取到**（`extract_deadline` 在正常源上命中率很高）。
- 📌 复核脚本模式：读报告「三之五」表格 → 逐条 `fetch()` → 打印 `code / 正文长度 / extract_deadline / 截止表述原文片段`。**这一步是唯一能证明「是否在招」的动作**，光看报告的「待核」二字会误判成「银行没在招」。
- ⛔ **B 类才是真「需人工判窗口」**：中信金租实证——正文只写「本次招聘报名仅受理网上报名方式」无任何截止日，判「长期」必须人确认，不得按业务经验推断。

### 🔴 `article_full_title` 只读 `<title>` 会误判（母本缺陷）

实测中信金租 `…/shzp/20260910/37624.html` 的 `<title>` **就是站点名「中信金租」**，真标题「中信金融租赁有限公司2026年社会招聘」只在正文 ⇒ 拿站点名去 `tier()` 必然判不出 `open`，条目被错归 `noise`。

```python
def article_title_extended(html):
    # 兜底顺序：<title> → og:title → h1 → 面包屑/正文首个含招聘词根长句
    # 优先返回第一个命中 REC_KW 的候选
```


---

## 五、🔴 隔离回归法（改脚本必走）

**别直接改工作区文件**。流程：

```bash
mkdir -p /tmp/xxx && cd /tmp/xxx
cp 工作区/脚本.py ./脚本.py            # 1 改前备份到 /tmp
ln -sf 工作区/gov_recruit_monitor.py .   # 2 软链依赖（词表母本 + xlsx）
ln -sf 工作区/单位与招聘信息总表.xlsx .
# 3 在这里改，改完全量跑，落 /tmp 零污染
# 4 验证通过后才 cp 回工作区
```

**三必做回归**：
1. **新功能命中** —— 新加的清洗/过滤在真实数据上确实生效
2. **默认行为未变** —— 没开新参数时与旧版一致
3. **特殊源不炸** —— 空值 / None / 污染值 / 超长文本不抛异常

改完 **全量重跑 + 核对守恒自检行**，两层都对才落盘。

---

## 六、🔴 栏目页 vs 真公告（三次翻车定稿）

列表页里 `/index.shtml` 这类纯导航页会把主口径灌爆（实测苏农 138 条里 **123 条是栏目页**），
但**不能简单按「index 结尾」杀**。

```python
COLUMN_TAIL_RE = re.compile(r"/(index|default|list)\.(s?html?|jsp|php|aspx)$", re.I)

def is_column_page(absu):
    absu = absu.split("#")[0]              # 坑① 锚点必须先剥
    m = COLUMN_TAIL_RE.search(absu)
    if not m:
        return False
    prev = absu[:m.start()].rstrip("/").rsplit("/", 1)[-1]
    return not prev.isdigit()              # 坑②③ 纯数字目录 = 详情页，放行
```

**三个坑（都是 2026-09-29 实测翻车）**：
| 坑 | 症状 | 正解 |
|---|---|---|
| ① `#锚点` | `…/index.shtml#dw`、`…/index.shtml#诚聘英才` 不匹配 → **漏杀** | 先 `split("#")[0]` |
| ② 数字目录 | 哈行真公告是 `/hxzp/1282898/index.html`，被当栏目页**误杀 15 条** | 前一段是纯数字 → 放行 |
| ③ 只看后缀 | 渤银 `/cbhbank/2026-09/21/article_….shtml` 与栏目页同页混排 | 按「前一段是否数字」判 |

> 📌 **`gov.CONTENT_RE` 判不出 `/index.shtml`**（它匹配 `list.shtml$` / `/col\d` 这类），
> 所以栏目页判据必须自己写。
> 📌 同 URL 多次出现会被 `seen` 去重合并 —— **差异条数不等于误伤条数**，
> 回归断言别写粗（我曾把「同 URL 去重」误判成「栏目页误杀」）。

---

## 七、🔴 xlsx 脏数据（脚本只读 + 报告披露）

巡检脚本**永不写表**。脏数据按「清洗 + 报告披露」处理，报告里出「清洗记录」章节：

| 症状 | 清洗 |
|---|---|
| 一格塞多个网址（中文分号 `；`） | `re.split(r"[；;、\n\r]+", s)` 逐个入监测目标；未切会抛 `'latin-1' codec can't encode character '\uff1b'` |
| 无 scheme（`bosc.zhiye.com`） | 补 `https://` |
| 尾斜杠 / 全角空格 | `rstrip("/")` + `strip("　 ")` |
| 填了要闻/About 页 | **脚本不动**，报告第二节标「非招聘页」，由人放行后回写 |
| 官网 == 招聘官网 | 同上披露，不擅自改 |

清洗后 URL 数会**变多**（污染行拆成 2 个），报告要写清「N 行 → M 个去重 URL」。

---

## 八、🔴 SPA 空壳源与 ego 兜底（银行线 44/89 空壳）

银行招聘站几乎 100% 是 Vue/React SPA。实测 89 个去重 URL：
22 个能静态解析 / **44 个 200 但 0 条目（空壳）** / 21 个传输层异常。

### 8.1 移植而非重写

`_ego_run` / `_ego_cleanup` / `_ego_sweep` / `ego_fetch` / `items_from_ego_*`
从 `power_recruit_monitor.py` **逐字移植**，只换 `EGO_TASK_PREFIX`
（银行线用 `bank_monitor_`，电力线 `power_monitor_`）。
这些函数封装的是 **ego 运行时契约**（launchctl 前缀、清理 API、超时 kill），
不是业务口径 —— 任何「顺手优化」都会重新踩坑。
业务差异只在解析器：母本用 `parse_items`，银行线用自己的 `parse_items_generic`。

### 8.2 🔴 兜底触发条件：`items 为空 或 code != 200`（两个都要）

电力线曾把条件写成 `if code != 200`，而判定又要求 `code == 200` ⇒ **开关白开**，
SSL 异常源（`code=0`）永远走不到 ego。正确：

```python
_need = [r for r in results if len(r["items"]) == 0 or r["code"] != 200]
```

⚠️ **并发必须 1**：ego task space 名带秒级时间戳，并发会撞同名空间互相关闭。

### 8.3 🔴🔴 浏览器错误页会伪装成「渲染成功」（本轮最贵的坑）

`ego_fetch` 的成功判据是 `links>0 or lines>0 or len(body)>=200`。
但**浏览器打不开站点时会渲染错误页，它照样有链接**：

```
https://cbhb.com.cn/…  →  links=1
  L: 检查代理服务器和防火墙 -> chrome-error://chromewebdata/#buttons
```

`links=1` ⇒ 旧判据认定「渲染成功」⇒ 把「打不开的站」误记成「打开成功但没公告」，
这类源会静默混进正常源里，不再出现在告警里。**必须先剔错误页再判成功**：

```python
real_links = [l for l in links
              if not str(l.get("href","")).startswith(("chrome-error://","chrome://","about:"))]
if not real_links and _is_browser_error_page(text):
    ok = False; links = []; err = "浏览器错误页（代理/证书/网络层失败，非站点内容）"

def _is_browser_error_page(text):
    t = re.sub(r"\s+", "", text or "")
    if not t: return True
    return any(m in t for m in ("检查代理服务器和防火墙","无法访问此网站","ERR_",
                 "DNS_PROBE","您的连接不是私密连接","ERR_CERT","ERR_CONNECTION"))
```

实测对照（4/4）：渤海/51job → 判失败；招行/汇丰 → 判成功（汇丰 1378 字 23 链接）。
> 📌 ego **也救不了**老 SSL 栈站点（本机代理下 `cbhb.com.cn` 在浏览器里同样失败）——
> 这类源该标 `ssl` 类并放行，不是无限重试。

### 8.4 其他纪律

- ego 用完必须清理，否则静默泄漏（详见 skill `ego-browser-workbuddy`）：
  `completeTaskSpace(<name>,{keep:false})`（本机**没有** `task.finish`），
  验收必须**另起进程**再 `listTaskSpaces`，并交叉查 `~/.ego-browser/state/space-*.json`。
- 🔴 ego 抓回的 `innerText` 首行**不是**页面 `<title>`，另存 `ego_title`，
  别覆写 `title`（否则每轮误报「页面标题变化」）。
- **共享 URL 必须显式披露**：55 家农商行共用 `campus.51job.com/jsnxzp2027`，
  一条公告会同时算进 55 家银行的数 —— 报告里要写明，否则会被误读成 55 条不同机会。

### 8.5 失败源要按「处置动作」分类，不是一行行堆告警

23 个异常源逐条列是噪音，分类才有行动价值：

| 类别 | 判据 | 处置 |
|---|---|---|
| `waf` | 412 | 加请求头/换 UA，仍失败走 ego |
| `ssl` | err 含 ssl/certificate | 本机 requests 层无解，走 ego 或放弃 |
| `forbid` | 403/400/401/404/410 | 站点侧拒绝，加头无用，确认 URL 是否有效 |
| `redir` | 301/302/307/308 | 入口已迁移，⛔ **需人工回填 xlsx** |
| `dead` | 连接重置/超时/code=0 | 隔天重试 |

```python
def classify_fetch_failure(code, err, url=""):
    e = (err or "").lower()
    if code == 412: return "waf", "412 WAF 拦截（换 UA/加头或走 ego）"
    if code == 403: return "forbid", "403 站点拒绝（加头无用）"
    if code in (400,401,404,410): return "forbid", "%d 入口不可用（疑似已迁移/下线）" % code
    if code in (301,302,307,308): return "redir", "%d 重定向（入口已迁移，需人工回填 xlsx）" % code
    if "ssl" in e or "certificate" in e: return "ssl", "SSL 老旧握手/证书链，本机 requests 层无解"
    if "closed connection" in e or "reset" in e: return "dead", "连接被重置（站点或网络侧）"
    if "timed out" in e or "timeout" in e: return "dead", "超时"
    if code == 0: return "dead", "传输层失败（code=0）"
    return "other", "未归类"
```

### 8.6 渲染层抽条：⛔ 只认确证日期，绝不猜

SPA 列表常是 JS 事件驱动，公告只在 `innerText` 里没有 `<a href>`。
`items_from_ego_text` 按「长标题行 + 相邻日期行」配对，但：

- ✅ **8 位紧凑日期 `20260910` 采信**（含年/月/日，是页面确证的）
- ⛔ `06中国华润…`（只有日）/ `2026校园招聘`（只有年）**一律不还原日期**
  —— 页面没给就是没有；**假日期比没日期危险得多**（会污染有效性分层，
  本该「待核」的变成假「有效」）。取不到就 `date=""` 交深检回官方原文取。

### 8.7 🔴🔴 有效性深检三重陷阱（2026-09-30 银行线同日连踩）

「待核」里最大一桶根因不是源坏了，是**深检自己写错了**。三个坑按出现顺序：

| # | 症状 | 真因 | 正解 |
|---|---|---|---|
| ① | 待核 29 条里 **15 条**是「文章页抓取失败（0）」，全同一域名 | **同源并发限流假象**：8 worker 同时冲 `hrbb.com.cn`，单条 curl 立刻 200/61KB | 深检 `max_workers` 降到 **4**；同源最小间隔已有 `_throttle` 但挡不住 8 并发同打 |
| ② | 改判出主口径的条目 `tier_full` 是 `nav`/`noise` | 母本 `G.article_full_title()` **只读 `<title>`**，站点名型 title（「中信金租」「中国光大银行」）判不出 open | 扩展标题兜底：`<title>` → og:title → h1 → 正文首个招聘词根长句 |
| ③ | 修好 ② 之后，那条**反而判成 `nav`** | **h1/og:title 在银行站普遍是整页导航**：「业务 现代交通 … 社会招聘 校园招聘 首页 > 加入我们 > …」含招聘词根 ⇒ 命中 nav，而重分层把 nav **移出主口径** —— **比原来的 None 更糟**（None 是没抓到，nav 是明确判错） | 候选加**双闸**：长度 ≤60 字 **且** 不含导航串（首页/加入我们/更多/详情/业务/新闻动态/关于…） |

⛔ **12. 包装层绝不能沿用母本再抓一次**：若写成 `out = G.check_item_validity(...)`
再自己 `fetch()` 一次做兜底，等于对同源**加倍请求**，直接把 ① 的限流问题放大一倍。
正确做法＝自己抓一次，母本判据以函数复用（`G.article_full_title` / `G.extract_deadline` /
`G.is_true_longterm`）而不是再调母本入口。
⛔ **失败必须带 err**：母本在 `code != 200` 时直接 return 不写 err，报告里只有
「抓取失败（0）」⇒ 无法区分限流/超时/连接重置/证书错误，四个根因四种处置。

**双向回归最小集（改深检必跑，3 秒）**：`中信金租`（②③ 样本，须 `open`）、
`渤海 cbhb`（标题正常，须 `open` 且 `title_fix` 为空）、`哈行 hrbb`（① 样本，须拿到 deadline）。

---

## 九、🔴 本机环境坑

| 坑 | 现象 | 正解 |
|---|---|---|
| `timeout` 命令 | macOS 无 `timeout` | 用 Python `concurrent.futures.wait(timeout=)` |
| `wait()` 返回值 | 返回**你提交的集合**，不是 future | `futs={ex.submit(f):a for a in xs}` 后要 `f.result()`，**不是 `futs[f].result()`**（`futs[f]` 是入参） |
| `grep "\|"` | 含竖线的 pattern **静默返回空** | 核表格一律用 Python 读 |
| 核 git 路径 | `git ls-files "路径"`（无尾斜杠）返回 0 | 必须带尾斜杠，否则误判「整个目录没被跟踪」 |
| 后台 `nohup … &` | 父进程退出即被 SIGTERM，日志空 | 用工具的 `run_in_background`，不要自己 nohup |
| Bash 工具超时截断 | 跑全量巡检（>2min）报 `Exit 137 SIGTERM` 且**日志全丢** | 一律 `run_in_background=true` + 日志重定向到 `/tmp/*.log` 再读 |
| Python 输出缓冲 | 重定向到文件后 `tail` 是空的（看着像卡住了） | 用 `python3 -u` 强制行缓冲，否则只能等跑完再看 |
| ego 需脱离沙箱 | 沙箱内 `bootstrap_look_up` 查不到 ego lite | Bash 工具带 `dangerouslyDisableSandbox=true` |

---

## 十、巡检频率与消费方式

- **频率**：机关/银行 1-2 天一次；电力/铁路 1 天一次。
- **选活口径**：从报告「三、当前在架」的**有效层**按 `报名截止` **升序**挑最紧迫单位。
- 🔴 巡检「待核」≠「在招」，只当线索，回官方公告原文核实硬信息后才能动笔。
- 报告是**选活入口**，不是事实源；硬信息只认官方公告原文。

---

## 十一、🔴 快照命名与「改名必须带迁移」（2026-09-30 立规）

### 11.1 症状：改了 `snap_path()` 但 diff 静默失效

`snap_path()` 是 `load_snap()` / `save_snap()` **共用的唯一定位函数**。一旦改命名规则而**存量文件没跟着迁移**，
旧档全部读不到 → `load_snap()` 返回 `None` → 报告误判「**首轮基线**」，当日「本次新增」虚高到全量，
**不报错、不告警**，往往一天半后才发现。

🔴 判定失效的通用手法：`fetched_at` 时间分布 + git 跟踪态一起看。
若「新格式文件时间戳全是最新的、旧格式全是很早的」⇒ **改名没迁移**，不是历史遗留。
（2026-09-30 实踩：gov 线中文名 193 份 + md5 名 176 份并存，`git mv` 只在提交时把磁盘现状入库、**不构成迁移**。）

### 11.2 命名要「人工可读」——纯域名一定不够

朱总裁定口径：「hash 命名你处理简单，但人工看压根不懂」。⛔ **纯域名不可用**，
实测 181 源纯域名只有 153 个唯一键、**25 组碰撞**。根因：**「一委三局共用一个域名」是常态**
（`www.wxbh.gov.cn` 3 个源、`www.haian.gov.cn` 2 个、`www.haqjp.gov.cn` 2 个）。

**定稿格式（四条线统一）**：`<协议>.<域名>.<路径各段>.<md5前N位>.json`

| 设计点 | 理由 |
|---|---|
| 域名**保留原样不拆点** | `changshu.gov.cn` 而非 `changshu_gov_cn`。实测点号与下划线在唯一性/长度/隐藏文件风险三项**完全相同**，唯一差别就是人眼可读性 |
| **协议前缀** `http.` / `https.` | 从根上消灭「同一页面 http/https 重复登记」碰撞（实测占 3 组：丹阳、溧阳、njls） |
| **完整路径**各段 | 唯一性从 153 → 180/181 |
| **hash 放末尾** | 人工不用理解 hash 就能认出站点与栏目；6 位实测够但生日碰撞≈0.4%，**用 8 位**（万分之一级，长度只多 2 bytes） |
| ⛔ **query 不进可读部分** | 15 个带 query 的源里 6 个是 JPAAS 接口，全是 `webId=…&tplSetId=…` 噪音 |

实测长度：gov 最长 98 bytes、bank 最长 89 bytes，离 APFS 255 上限很远，**不会超限**。

### 11.3 🔴 迁移工具必备的六条（`migrate_gov_snap_names.py` 是模板）

1. ⛔ **按 JSON 内部 `url` 字段算新名**，⛔ 绝不按旧文件名算。
   实测存在 `丹阳市教育局.json` 里存着人社局 `dyrsj` 域内容的历史错配。
2. 🔴 **冲突必须分三类**，混为一谈会误判：
   - `real` = 同一新名下有【**不同** URL】= 真碰撞，⛔ 必须为 0，有则报错不处理；
   - `dup`  = 同一 URL 有**多份历史快照**（改名没迁移的冗余），保留 `fetched_at` 最新那份；
   - `rename` = 待改名。
   ⚠️ 2026-09-30 实踩：第一版把 `dup` 当 `real`，dry-run 报「174 组冲突」全是误判，**真碰撞实为 0**。
3. `--dry-run` 必做；`--apply` 同名已存在**跳过不覆盖**；`--prune` 删前**逐个**校验内部 `url` 一致。
4. 🔴 **删存量前三重校验**：① 待删内容 md5 全在备份内；② 每个旧档 URL 都有新命名目标；
   ③ 新档内部 url 一致且 `fetched_at` 不旧于旧档。任一不过**禁止删除**。
5. **分批 10 个**执行，每批后校验目录剩余数。
   ⚠️ 判据看「目录剩余数 == 预期」而非失败计数——`to_delete.txt` 存全路径、在目录内执行会误报
   `No such file`（2026-09-30 实测 49 条误报，其实第一批已删成功）。
6. **交叉校验 `snap_path()` 与迁移工具算出的名字逐字一致**——不一致等于白迁移，且同样静默失效。

### 11.4 终验四件套（缺一不可）

```bash
python3 migrate_gov_snap_names.py --verify   # ① 当前源 100% 命中基线、0 内容错配
python3 gov_recruit_monitor.py               # ② 真实全量跑：守恒自检 ✅ + 「本次新增」不再虚高
# ③ 目录现存 json 全为新格式（all(可读格式)==True），子目录（下载的公告原文）未误删
# ④ 备份里的唯一 URL 100% 被当前目录覆盖，缺失 0
```

2026-09-30 gov 线实测：369 份（188 唯一 URL）→ 清理后 **188 份全部可读命名**，
`--verify` 181/181 命中、真实跑「本次新增 0 条真招聘 / 24 条流程后续」、守恒 `25+8+103+80=216` ✅。

### 11.5 四条线现状（2026-09-30）

| 线 | 命名格式 | 状态 |
|---|---|---|
| gov | `<协议>.<域名>.<路径>.<md5前8>` | ✅ 本次统一，188 份 |
| bank | `<md5前12>` | ⛔ **仍是纯 hash**，81 份 = 81 唯一 URL、零双份，改名零冲突风险 |
| power | `<域名>_<md5前8>` | ⚠️ 半可读，23 份 |
| rail | `<平台名>_<md5前6>` | ⚠️ 半可读（平台名如「中国铁建」可读，但同平台多源分不清），12 份 |

---

## 十二、🔴 TrueCMS「onclick 无 href」与 JPAAS 中文参数（2026-09-30 机关线立规）

> 本节两个坑都**静默失败**（不报错、只少数据），是「0 条目」告警里最难查的一类。

### 12.1 症状：列表页 HTTP 200、有 `<li>`、有内容，但 `parse_items` 恒返 0

**判别动作**（三步定位，勿跳）：

```bash
# ① 页面里到底有没有列表 li
python3 -c "import re,sys; h=open('/tmp/page.html',encoding='utf-8').read(); \
  print('li', len(re.findall(r'<li', h)), 'a', len(re.findall(r'<a ', h)))"
# ② li 上有没有 href，只有 onclick？
python3 -c "import re; h=open('/tmp/page.html',encoding='utf-8').read(); \
  print(re.findall(r'<li[^>]*onclick=[^>]*>', h)[:3])"
# ③ 静态只有 1 条 ⇒ 找动态分页接口
python3 -c "import re; h=open('/tmp/page.html',encoding='utf-8').read(); \
  [print(m) for kw in ['proxyUrl','ajaxParam','totalRecord','jpage','\.do'] \
   for m in re.findall(kw, h)[:1]]"
```

### 12.2 🔴 TrueCMS：`li` 只有 `onclick="tz('/path')"`，没有 `<a href>`

**架构特征**（崇川区 / 海安市实测同款）：

- 首屏把**第 1 条**塞进 `<div id="initData"><ul><li …>`，其余全靠 `jquery.jpage.js` 翻页
- 每个 li：`<li onclick="tz('/path/x.htm')">` ＋ `<div class="l1">日期</div>` ＋ `<div class="l2">`内含`l21`=标题、`l23`=摘要
- 分页接口（GET，**jsonp**）：
  ```
  <scheme>://<host>/truecms/messageController/getMessage.do
    ?startrecord=1&endrecord=30&perpage=10&columnId=<GUID>[&isMobile=1]
  → {"result":"<datastore><totalrecord>290</totalrecord><recordset><record><![CDATA[ <li… ]]>…"}
  ```

**四个必须做对的点**：

| # | 做法 | 踩坑后果 |
|---|---|---|
| 1 | `parse_items` 增`onclick` 分支，**过滤门槛与 href 分支完全一致** | 放宽门槛 ⇒ 噪音灌进主口径 |
| 2 | 标题**按 class 优先级逐个试**（`title=`属性 → `l21` → `l2t` → `l2`） | ⛔ 禁"删掉日期块再整体剥标签"：崇川 `l23` 摘要会混进标题、长度 >80 被整条丢弃，**改完仍 0 条**（09-30 实踩） |
| 3 | 反转义顺序 `
`→`
`→`
`→`\/`→`'`→`"`→`\` | jsonp 外壳不还原 ⇒ 一个 `<li>` 都取不到 |
| 4 | `columnId` 从列表页 `ajaxParam:{columnId:'…'}` 抽，**⛔ 禁猜** | 同站多栏目共用 CMS，猜错＝抓到别的栏目 |

⚠️ **"能解析出 1 条"≠修好了**：静态那 1 条常是噪音（海安首条＝"遴选…独立储能项目开发建设主体"＝`is_noise` 命中）。必须看接口全量。

### 12.3 🔴 JPAAS 接口的 `tagId` 是中文值，手抄 URL 必错

`api-gateway/jpaas-publish-server/front/page/build/unit` 的 `tagId` 常是 `当前栏目信息列表` 这类中文。

- ⛔ **禁手写 urlencode 后的 URL**：09-30 实测把「列」的 `%E5%88%97` 抄成「目」的 `%E7%9B%AE`，
  接口返回 **193 字节空模板、`success:true` 但 `data` 为空 —— 不报错**。
- ✅ 正确做法：抓空壳页里的 `queryData="{'parseType':…,'tagId':'…'}"`，用 `urllib.parse.urlencode()` 生成。
- ✅ 回归里加**反向断言**：`bad = 正确串.replace("%E5%88%97","%E7%9B%AE")`，断言 `bad != 正确串 且 bad not in _OVERRIDE_NOTE`。

### 12.4 🔴 报告口径：「守恒」≠「当前可报名」

守恒自检只证明**分层加总＝代码主口径**，不证明覆盖面。09-30机关线报告写「在架招聘公告 ＝ 216 条」，
而 216 ＝ 有效 25 ＋ 长期 8 ＋ **已过期 103 ＋ 待核 80** —— 同一份报告第 13/14 行又写
「已过期/待核**不混入主口径**」，自相矛盾，读者会把 216 误读成「当前有 216 条可报名」。

**定稿措辞**：

```
| 真·开启公告池（主口径，含已过期/待核，见下行分解） | 216 条 |
| └ 其中当前可确认在架（有效＋长期） | 33 条 |
| ├ 已过期（…**下沉三之五，不算在架**） | 103 条 |
> 守恒自检：… ✅ 一致（⚠️ 守恒只证明分层加总＝代码主口径，不证明当前可报名）
```

### 12.5 🔴 加噪音词必须双向回归（记忆 §五的细化）

09-30 人工审出5 条误判，共同特征＝**带招聘词根但整句无招人动作**：
体验官`招募` / 疫苗`遴选结果公示` / 引进人才`待遇发放对象公示` / `选聘…机构` / `选调…公示`。

**判据必须落在语义尾巴上**（`公示`/`结果`/`发放对象`/机构），⛔ 禁加裸单词：

|❌ 禁加 | 会连带杀掉 |
|---|---|
| `招募` | 「公开招募志愿者」也许该留，但「劳务派遣招募」会误伤 |
| `公示` | 几乎所有真公告正文都有"公示"二字 |
| `遴选` | 已由 `REC_NOISE_SELECT` 覆盖 |

✅ 正例：`招募`（该词根在政务语境几乎只指活动志愿者）／`遴选结果|遴选公示|中选结果`／
`待遇发放|补贴发放|发放对象|拟发放|拟兑付`／`选聘.{0,20}(机构|中心|公司|事务所|代理|银行)`／`(选调|选聘|遴选).{0,20}公示`。

⚠️ **回归用例放对分组**：把「选调…**考察**工作公告」放进"必须判噪音"是错的——
它被 `REC_PROC`的「考察」正确判为流程后续（`tier=proc`），不是噪音（`tier=None`）。
**分组判据＝`tier()` 的返回值，不是 `is_noise()`。**

### 12.6 「0 条目」源必须逐个定性，⛔ 禁信告警文案

09-30 机关线 10 条告警实测，四类根因混在一起：

| 根因 | 实例 | 判别|
|---|---|---|
| **间歇性 403** | 常州教育局 / 南京教育局 / 栖霞卫健委 | 重测即200 ⇒ **假告警**，别改 URL |
| **软 404** | 丹阳卫健委 | HTTP 200 ＋ 正文"404网页错误"＋ 标题＝网站名 |
| **真失效** | 江宁卫计（54B空）/ 靖江`/bmgg/`（硬 404） | 空响应或 404 |
| **JS 空壳** | 常高新（回退首页）/ 鼓楼区（49B `window.location.href`） | 标题＝网站名 / 响应仅几十字节 |

🔴🔴 **⛔ 最容易判错的一条：「0 条目」≠ URL 失效（09-30 被朱总当场纠正两次）**

朱总原话：「鼓楼区的没有失效啊，`…/zfbm/index_2.html` 第三页就有」、
「靖江列表就有啊，这是文章页 URL」。

⇒ **我 09-30 上午把这两源判成「URL 失效」是错的**，根因是只看了 col7 里那个 URL，
**没试同站父栏目 / 也没试动态构建接口**。正确判据顺序（⛔ 顺序不能跳）：

| 步骤 | 动作 | 判据 |
|---|---|---|
| ① | 看 col7 URL 的**响应体形态** | 49B `window.location.href` ＝ JS 跳转壳；5KB 空模板＝JPAAS 壳；正文含"404网页错误"＝软 404 |
| ② | **试父栏目 `…/index.html` 与 `index_2/3.html`** | 政务站栏目树是`zfbm/`（父）→ `zfbm/quweijiju/`（子）。子栏目挂掉**不代表**父栏目失效 |
| ③ | 页面含 `unitbuild.js` / `authorizedReadUnitId` ⇒ 抽 `queryData` 走JPAAS 接口 | 抽出即修，⛔ 别急着判失效 |
| ④ | 页面含 `totalRecord` + `proxyUrl` ⇒ TrueCMS jPage jsonp | 同上 |
| ⑤ | 以上全空 ⇒ **才**判URL 需换（并报告"col7 建议改为 X"） |

📌 **实测数据（留作对照）**：
- 鼓楼区：子栏目 `/zfbm/quweijiju/` 49B 空壳 → 父栏目 `/zfbm/index.html` 15 条/页，
  `index_2` 15 条（含《…鼓楼区教育局所属学校2026年7月公开招聘高层次教师、新教师公告》），
  `index_3` 14 条；3 页去重 44 条、真·开启 5 条。⇒ **真招聘在第 2、3 页，首页 0 条**。
- 靖江：`/xwzx/gggs/rs/index.html` 7134B 只有导航 → JPAAS 接口 15 条（含真公告）。

⚠️ **告警只报「0 条目」，不报根因**。且快照里 `items=0` 的源可能**不在当日告警里**
（09-30 快照离线普查出 9 个 0 条目源，当日告警只有 6 个）⇒ 巡检后必做：

```bash
# 离线普查所有 items=0 的源，别只看告警段
python3 -c "import glob,json; [print(json.load(open(p,encoding='utf-8'))['url'])
  for p in glob.glob('snapshots/gov/*.json') if not json.load(open(p,encoding='utf-8'))['items']]"
```

### 12.7 🔴 父栏目回退表 `_PARENT_FALLBACK`（区别于 `_URL_REWRITE`）

三个运行时改写表**职责不同，别混用**：

| 表 | 场景 | 效果 |
|---|---|---|
| `_URL_REWRITE` | col7 是 **JS 空壳**，真实列表在**动态接口** | 换 URL ＋ `mode=json` |
| `_PARENT_FALLBACK` | col7 是**子栏目且该子栏目是空壳**，父栏目正常 | 换父栏目 URL ＋ **按源提高 `pages`** |
| `_EXTRA_SOURCES` | col7 本身没错，只是**漏了**某个栏目 | 并行新增，不改原源 |

⚠️ `_PARENT_FALLBACK` 必须设 `pages`（鼓楼区设 3）——**默认 `--pages 1` 只抓首页，
而真招聘恰好在第 2/3 页**，只换 URL 不翻页仍然是 0 条。

⚠️ 回归里要**钉住前提**：`chk("前提：子栏目仍返回 0 条", parse_items(子栏目) == 0)`。

### 12.8 🔴🔴 `or` 短路吃掉按源配置——`want_pages` 既存 bug（09-30 修，影响所有线）

```python
# ❌ 原写法（gov/rail/power/bank 都可能有）
def want_pages(t):
    return page_cfg_for(t["url"], _page_cfg) or max(1, args.pages)
```

`page_cfg_for()` 在「`gov_source_pages.json` 不存在 / 没配该源」时返回 **0**，
而 `0 or X` 短路成 `X` ⇒ **`t["pages"]` 永远读不到**。
表现＝`load_targets` 里明明写了 `pages=3`，报告源表却打「页数 1」，翻页**静默不发生**。

-09-30 鼓楼区踩中：`_PARENT_FALLBACK` 设了 `pages=3` 但真招聘在第 2/3 页，
首页 0 条 ⇒ 修完 URL 仍是 0 条，**看起来像"修了没用"**。
- ✅ 定稿写法（**取第一个 >1 的值**，而不是简单把 `or` 换 `and`——
  `and` 会让 `--pages 4` 永远赢不过按源配置，优先级会倒过来）：

```python
def want_pages(t):
    for v in (page_cfg_for(t["url"], _page_cfg), int(t.get("pages") or 1), max(1, args.pages)):
        if v and v > 1:
            return int(v)
    return 1
```

⚠️ **回归里必须加反向断言**，否则这个 bug 修不掉也看不出修没修：

```python
_old = lambda tp, pc, ap: pc or max(1, ap)
chk("反向断言：旧 or 写法确实吃掉按源 pages", _old(3, 0, 1) == 1)   # 旧写法给出 1（错）
chk("新写法给出 3", want_pages_sim(3, 0, 1) == 3)
```

📌 通用教训：**配置项有"多来源 + 优先级"时，⛔ 不要用 `or` 串默认值**——
`0` / `""` / `[]` / `{}` 全都是"合法但 falsy"的值，`or` 会把它们当成"没配"。
要用"取第一个**有效**值"的显式循环。
否则将来子栏目修好了、配置也该撤了，测试却因为"仍有条目"而失败，或反之被误认为修好了。

---

## 十三、🔴 告警必须能分辨「间歇性」与「真故障」（2026-09-30 立规，四线通用）

### 13.1 症状：一轮跑出 12 条告警，两分钟后单独重测**全部 200**

09-30 10:56 机关线告警 12（10:46 那轮只有 4），其中 7 条是
`抓取异常 0 Remote end closed connection without response`。
**隔离诊断法**（新旧两个版本并排跑同一批 URL）证明与代码改动**零关系**：

| 源 | 旧版 | 新版 | 结论 |
|---|---|---|---|
| edu.nanjing.gov.cn / njqxq.gov.cn / rsj.nanjing.gov.cn | 403 | 403 | 一致 |
| suqian / taizhou / yangzhou局 / changzhou局 | 200 | 200 | 一致 |

⇒ 告警涨是**网络抖动**，不是回归。⚠️ **但没做这一步对照，就会把锅甩到刚改的代码上**
（或反过来把真 bug 当成抖动放过）。

### 13.2 🔴 `code=0`（连接级失败）的退避必须增长且带抖动

```python
# ❌ 原实现：固定 1.0s、不增长、无抖动
except Exception as e:
    if attempt < retries:
        time.sleep(1.0); _throttle(url); continue
# ⇒ 同一轮 7 个 gov 源集体挂，而两分钟后重测全部 200
```

```python
# ✅ 与 403/429/5xx 同款：增长退避 + WAF 抖动 + 过同源限速闸
    time.sleep(2.0 * (attempt + 1) * (1.0 + random.uniform(*_WAF_JITTER) * 0.3))
    _throttle(url); continue
```

📌 **判据**：`code=0`＝连接都没建起来（WAF 拒连/瞬时抖动），与 `403`（建了连接被拒）
机制不同但**同样不该一次判死**。09-30 前者用 1.0s 固定退避、后者用增长退避 —— 差别只在
「延迟是否够 WAF 的时间窗过去」。

### 13.3 告警文案必须自带可操作判据

```python
_tag = "（连接级失败·多为 WAF 短暂拒连，非源失效，可稍后重试）" if code == 0 else ""
```

并在告警段顶部写**固定说明**，四线通用：

> `抓取异常 0`＝连接级失败，多为 WAF 频率上限的**短暂拒连**——实测同一批 URL 两分钟后
> 单独重测**全部 200**，此时**不必改配置**；同一 URL **连续 3 天**出现才算真故障。
> `403/404` 连续出现也可能是 WAF 或改版，同样先隔日复测再判定。
> `解析出 0 条目` 才是最需要动手的一类。

🔴 **不加标签的代价是真实的**：09-30 一天之内「栖霞区 3 个源 403」就被反复翻查过
（其实是 njqxq.gov.cn 间歇 + nyqzhrss 等），**每天重查同一批假故障＝真故障被淹没**。

### 13.4 🔴 报告里的「已修复 N 个」是硬信息，必须带日期登记簿

09-30 报告写过一句：

> 动态列表适配：9 个源已适配动态列表……**修复前均挂「0 条目」假告警**

这句对 **5 个 09-28/29 就已适配的扬州源是假的** —— 它们不是本轮修的，修复前就在正常抓。
把「本轮新修」和「历史已好的」打包成一句「共 9 个已修复」＝**报告自己制造假因果**，
读者会以为整条线今天才刚修好、或反过来以为 5 个源刚刚出过故障。

**定稿做法**：代码里加**日期登记簿**，报告按日期分组叙述。

```python
_DYN_SINCE = {          # 键＝xlsx col7 原 URL，值＝首次适配日期
    "http://baoying.yangzhou.gov.cn/xwzx/tzgg/index.html": "2026-09-29",
    "https://www.tzhl.gov.cn/xwzx/tzgg/":            "2026-09-30",
    # …
}
```

```
> 动态列表适配（共 9 个源）：… 本次共解析 151 条（真·开启 19 条）
> ├ 本轮新修（4 个，修复前挂「0 条目」假告警）：海安市(17)、崇川区(30)、靖江市(15)、海陵区(15)
> └ 历史已适配（5 个，非本轮所修，修复前即正常在抓）：宝应、邗江、仪征、高邮、扬州市局
```

🔴 **回归必须加「登记簿 vs 实现」一致性断言**，否则登记簿会和实现漂移：

```python
chk("_DYN_SINCE 键 == _URL_REWRITE ∪ _TRUECMS_API（无多余登记）",
    set(_DYN_SINCE) == (set(_URL_REWRITE) | set(_TRUECMS_API)))
```

### 13.5 🔴 概览里「A（HTTP 200 且 B 个）」的「且」字是假的

```python
# ❌ ok_n 只数 code==200，把 200/0 条目的源也算进去
ok_n = sum(1 for r in results if r["code"] == 200)
A(f"| 可解析监测源 | {len(active)} 个（HTTP 200 且解析出条目 {ok_n} 个） |")

# ✅ 拆成两个独立数字
parse_n = sum(1 for r in results if r["code"] == 200 and r["items"])
A(f"| 可解析监测源 | 监测 {len(active)} 个｜HTTP 200 {ok_n} 个｜"
  f"其中**解析出条目** {parse_n} 个（200 但 0 条目 {ok_n - parse_n} 个，见告警） |")
```

⚠️ 09-30 181 源里 `ok_n` 与 `parse_n` **恰好都是 178**（只有一个 200/0 源），
所以错版与对版输出**一模一样** —— 这种巧合最危险，肉眼与 diff 都验不出来，
只有分开写两个变量才暴露。

🔴 同类陷阱：**「已登记 JS 空壳待适配 0 个」** —— `pending` 只是**已手工登记**的待适配清单，
不含本次新出现的 200/0 源（常高新就没登记）。读者会把「0 个」误读成「今天没有异常」。
定稿改「**已登记** JS 空壳待适配」并明写
「⛔ 此数只覆盖**已登记**清单，不含本次新出现的 200/0 条目源——那些看告警」。

📌 **通用教训：凡是「已治理/已适配/已完成 N 个」类汇总，一律要能回答
「哪 N 个是**这次**做的、哪 N 个**早就**好的」。** 答不上来就别这么写。

---

## 十四、🔴 数据源按行业拆sheet 后，代码切换必须带「行号溯源」（2026-09-30 立规，四线通用）

### 14.1 症状：xlsx 按行业拆出独立 sheet 后，脚本仍在读旧全表

`单位与招聘信息总表.xlsx` 从 2026-09-30 起是 **18 sheet** 体系：
`招聘信息 / 公司信息(1390行) / 机关单位(181) / 银行(182) / 基金 / 证券 / 期货 / 保险 / 信托 /
其他 / 电网 / 铁路 / 中烟 / 医院 / 学校 / 填写规范 / 已治理存档-×2`。

机关线原代码是**在「公司信息」里按 col2 性质筛行**：

```python
#❌ 治理后仍这么写 ⇒ 一直读 1390 行全表，永远不会用上新建的「机关单位」sheet
ws = wb["公司信息"]
if "机关单位" not in str(row[2] or ""): continue
```

### 14.2 ✅ 定稿：具名常量 ＋ 双读回退 ＋ 行号带来源 sheet

```python
GOV_SHEET = "机关单位"
GOV_SHEET_FALLBACK = "公司信息"

sheet_fallback = False
if GOV_SHEET in wb.sheetnames:
    ws, need_nature = wb[GOV_SHEET], False        # 独立表：不筛性质
elif GOV_SHEET_FALLBACK in wb.sheetnames:
    ws, need_nature = wb[GOV_SHEET_FALLBACK], True # 老表：仍筛性质
    sheet_fallback = True
    print(f"[WARN] xlsx 缺「{GOV_SHEET}」sheet，已回退「{GOV_SHEET_FALLBACK}」…")
else:
    return []
...
t = by_url.setdefault(url, {"rows": [], "rows_sheet": ws.title, ...})
```

🔴 **三个必做，缺一个就静默出错**：

|# | 做法 | 不做会怎样 |
|---|---|---|
| 1 | 具名常量 `GOV_SHEET` | sheet 改名时全脚本grep 不到出处 |
| 2 | 回退时**打印显式 WARN** | sheet 被改名/误删 ⇒ 静默退回旧口径（181 源），报告无任何异常，但源数差异会被当成"数据丢失"反复排查 |
| 3 | `rows` 旁边存 `rows_sheet`，报告里标出来 | **行号会随 sheet 变义**（旧 sheet r1505 ≠ 新 sheet r1505），照着报告回写会改错行 |

📌 报告里历史行号必须打旧口径标记，否则下一个人会按新行号回写：

```
无待回写项。历史修正（…回读 11/11 一致。
⚠️ 下列行号均为**旧「公司信息」sheet** 口径，治理拆分后行号已变，⛔ 勿按新 sheet 行号回写）：
| r263 | 苏州市人社局 | 首页→通知公告专栏 |
```

### 14.3 🔴 切sheet 后必须验证的 5 件事（缺一项都可能静默错）

```python
# ① 源数变化是否符合预期（含"因裁定而删"的源）
#    机关线 181→177：176 xlsx ＋ 1 脚本补充源；少的 1 个＝浙江人事考试院（朱总裁定不补回）
# ② 旧版运行时改写表在新口径下是否仍命中（_URL_REWRITE / _PARENT_FALLBACK 的键是**旧 col7 原值**）
any("zfbm/index.html" in t["url"] and t.get("pages") == 3 for t in TARGETS)
# ③ 🔴 行号语义 100% 对齐：新 sheet 的 rows[r] 行的 col6 必须真对应这个源
#     ⚠️ 判定要**计入 rewrite/parent 改写**，否则 9 个改写过的源会误报"不匹配"
# ④ 单位字典是否需同步收窄
# ⑤ 来源归属 match_source() 新旧逐条对照必须一致（字典来源变了 ⇒ 可能影响"标题匹配"标注）
```

⚠️ **单位字典必须跟数据源同源**。旧写法读「公司信息」全表 1390 行，
会把银行/电网/医院/学校名全塞进字典，让「标题中最长单位名匹配」跨行业误命中。
切sheet 后字典从"全表"变成"机关单位 160 个名称"，**这一步必须单独验证，否则来源标注悄悄变了**。

### 14.4⚠️ 验证期我自己踩的两个"断言写错"（都不是代码错）

| 坑 | 现象 | 正解 |
|---|---|---|
| grep 数据当代码 | 断言 `"zjks" in _src_old` 失败——`zjks` 是 **xlsx 里的数据**、不是代码常量，源码里必然找不到 | 反向断言要查**旧版模块的实际加载结果**：`[t["url"] for t in _gov_old.TARGETS if "zjks" in t["url"]]` |
| 拿备份文件名直接 `spec_from_file_location` | 备份名 `…py.bak_HHMMSS` **无 `.py` 后缀** ⇒ loader 为 None ⇒ `AttributeError` | 先 `shutil.copy` 成 `.py` 再加载；用 `glob("…bak_*")` 取最新一份 |

📌 **另**：`load_unit_dict()` 返回的是**二级前缀索引 dict**（`{前两字: [名, …]}`），
不是名称集合。校验时必须 `{n for v in d.values() for n in v}` 展平后再比 ——
直接 `u in d` 会全部误报"缺失"（本次先误判 180 个缺失，虚惊一场）。

### 14.5 口径变化必须在代码里写死"这是预期"

治理后源数从 181 变 177 是**裁定结果，不是数据丢失**。⛔ 必须写进模块 docstring：

```
⚠️ 已知口径差：浙江人事考试院（公司信息 行920，标签"省属机关、招考机构"）不在新 sheet，
朱总 11:37 裁定「不补回」⇒ 176 源是预期结果，⛔ 别当数据丢失反复排查。
```

同理，本次治理的漏项根因值得记：新 sheet 城市分布是江苏 13 地市 ＋ 江苏 2 省级，
**按城市筛江苏时漏掉了唯一的外省单位**（城市=浙江）。若日后还有外省单位，先查这张表。
