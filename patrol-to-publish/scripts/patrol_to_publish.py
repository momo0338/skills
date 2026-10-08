#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
巡检 → 写作 → 推送 → 发布 → 状态回填 的单一入口编排器
=========================================================

设计前提（朱总 2026-09-30 裁定）
--------------------------
1. **巡检结果是"候选池"，不是"写作指令"** —— 必须经人工核实裁定后才动笔。
2. **"发了没"的唯一依据是后台发表记录**，草稿箱是暂存区（红线：草稿一旦群发即从draft/batchget 消失）。
3. **状态真源只有一个**：`内容状态.json`，四方对账（状态文件↔ 总表两列 ↔ 各线目录 ↔ 台账）。
4. **发布动作永远由人工在公众号后台点** —— 本脚本⛔ 不调用任何群发/发表接口。
5. 每一步都必须留痕、可回滚、幂等。

子命令
------
  today   生成今日待办清单 + 完整候选池（巡检后第一件事）
  sync    把巡检新条目播种进 `内容状态.json`（幂等，可重复跑）
  mark    推进某批次状态（unwritten→written→draft→published）＋ 回填事实
  audit   四方对账，输出不一致清单
  verify  核验某稿是否已发布（查后台发表记录，⛔ 不看草稿箱）
  archive 归档：把已发布稿从 待发布/  git mv 到 已发布/（红线 11）

统一出口
--------
  所有产物落`运营/流水线/YYYY-MM-DD/`，并在`运营/流水线/待办.md` 维护当期看板。
"""

import argparse
import json
import os
import re
import subprocess
import sys
import datetime
from collections import Counter, OrderedDict

# ============================================================
# 路径与常量
# ============================================================

DEFAULT_WS = os.path.expanduser("~/codeup/obsidian/03-工作记录/码上职业")
SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JOB_WRITE = os.path.expanduser("~/src/skills/job-write/scripts/emit_briefing.py")
MP_PUBLISH = os.path.expanduser("~/src/skills/mp-publish/scripts")
VENV_PY = os.path.expanduser("~/.workbuddy/binaries/python/envs/default/bin/python3")

STATE_FILE = "内容状态.json"
XLSX = "单位与招聘信息总表.xlsx"
PIPE_DIR = "运营/流水线"

# 巡检四线 → (报告文件前缀, 引擎判定关键词)
LINES = OrderedDict([
    ("gov",   ("机关单位招聘监测",   "机关")),
    ("power", ("电力电网招聘监测",   "电力")),
    ("rail",  ("铁路招聘监测",       "铁路")),
    ("bank",  ("银行招聘监测",       "银行")),
])

# 写稿引擎分派：按单位/标题关键词 → 引擎名
ENGINE_RULES = [
    # (正则, 引擎, 落点目录, 说明)
    (r"教育局|教育系统|学校|学院|大学|师范|中学|小学|幼儿园|特岗", "school-write", "教育系统/待发布", "教育系统→school-write 7 段"),
    (r"卫健委|卫生健康|医院|卫生|疾控|妇幼|口腔|医疗|血站",       "hospital-write", "事业单位/待发布", "医疗编制→hospital-write"),
    (r"^(?!.*(教育局|学校|学院|大学|师范|中学|小学|幼儿园)).*(选调|强基|升学|特岗计划|志愿服务)", "C线-升学", "人生方向/待发布", "升学政策类⛔不套 job-write"),
]

# 写稿引擎分派：按单位/标题关键词 → 引擎名
DEFAULT_LANDING = {
    "school-write":  "教育系统/待发布",
    "hospital-write": "事业单位/待发布",
    "C线-升学":       "人生方向/待发布",
    "job-write":     "2027年校园招聘/待发布",
}

# 分拣过滤规则（⛔ 命中即排除，并在报告里留痕）
REJECT_RULES = [
    (r"遴选|选聘|竞聘|拟聘|拟录|公示|成绩|资格复审|体检|考察|笔试|面试|资格认定|岗位取消|变更",
     "流程后续/非社会投递窗口"),
    (r"劳务派遣|外包|保安|保洁|食堂|驾驶员|后勤|物业",
     "⛔ 后勤/外包类，分拣准则排除"),
    (r"苏州分行|苏州.*分行",  "⛔ 银行系苏州分行一律不单写（朱总 09-23 裁定，与全省统招重合）"),
]

# ⛔ 往年公告闸门：发布日距今超过这个天数，一律不作为当天写稿候选。
#    实测 2026-09-30 电力线把 2022/2023/2024 三条往年公告判成「长期」留在在架层
#    （报名截止列＝「—」，属巡检分层 bug）。正常校招公告不会发布于 300 天前。
STALE_AFTER_DAYS = 300

# 优先级：截止日距今天数 → 档位
def urgency_bucket(days: int) -> str:
    if days < 0:  return "已过期"
    if days <= 2: return "P0-今天/明天截止"
    if days <= 10: return "P1-10天内截止"
    if days <= 45: return "P2-窗口宽裕"
    return "P3-长期窗口"


# ============================================================
# 工具
# ============================================================
def die(msg: str, code: int = 1):
    print(f"\n❌ {msg}\n", file=sys.stderr)
    sys.exit(code)


def ok(msg: str):
    print(f"✅ {msg}")


def ws_path(ws: str, *parts) -> str:
    return os.path.join(ws, *parts)

def today_str() -> str:
    return datetime.date.today().isoformat()

def py() -> str:
    """⛔ 必须用 venv python：PIL/openpyxl 只装在 envs/default（AGENTS.md 硬门禁）。"""
    return VENV_PY if os.path.exists(VENV_PY) else sys.executable

def load_state(ws: str, required: bool = True) -> dict:
    p = ws_path(ws, STATE_FILE)
    if not os.path.exists(p):
        msg = (f"{STATE_FILE} 不存在。先跑：{py()} {JOB_WRITE} "
               f"--state-init --workspace {ws}")
        if required:
            die(msg)
        # ⛔ 只读分析（today/audit/verify）不该被状态文件阻断——
        #    没有状态文件只是「状态全空」，不是错误（隔离回归时工作区常是空的）。
        print(f"⚠️ {msg}\n   本次按「状态全空」继续。\n")
        return {"schema_version": "1.0.0", "states":
                ["unwritten", "written", "draft", "published"], "batches": {}}
    with open(p, encoding="utf-8") as f:
        return json.load(f)

def save_state(ws: str, data: dict):
    """🔴 写前强制备份到 /tmp（唯一回滚路径，AGENTS.md 纪律）。"""
    p = ws_path(ws, STATE_FILE)
    bak = f"/tmp/{STATE_FILE}.bak-{datetime.datetime.now():%Y%m%d-%H%M%S}"
    with open(p, "rb") as src, open(bak, "wb") as dst:
        dst.write(src.read())
    data["updated_at"] = datetime.datetime.now().isoformat(timespec="seconds")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    ok(f"状态已回填 → {STATE_FILE}（备份 {bak}）")

def parse_date(s: str):
    s = (s or "").strip()
    if not s or s in ("—", "-"):
        return None
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", s)
    if not m:
        return None
    try:        return datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


# ============================================================
# 解析巡检报告
# ============================================================
def latest_report(ws: str, prefix: str):
    d = os.path.join(ws, "巡检记录")
    if not os.path.isdir(d):
        return None
    cands = [f for f in os.listdir(d) if f.endswith("监测.md") and prefix in f]
    if not cands:
        return None
    cands.sort(reverse=True)          # 文件名以日期开头，字典序≈时间序
    return os.path.join(d, cands[0])


ROW_RE = re.compile(r"^\|\s*(\d{4}-\d{2}-\d{2}|\d{4}-\d{2}-\d{2})\s*\|")

def parse_in架(ws: str, line_key: str):
    """从报告「三、当前在架招聘公告」抽条目。

    ⚠️ 守恒自检：**必须**同时读概览的主口径数字，加总 != 主口径就报错——
    防止报告结构变了却静默产出空清单（这正是 glob 失效那次踩的坑）。
    """
    rp = latest_report(ws, line_key)
    if not rp:
        return [], None

    text = open(rp, encoding="utf-8", errors="ignore").read()
    lines = text.split("\n")

    # 定位「三、当前在架」到下一个 ## 之间
    start = end = None
    for i, ln in enumerate(lines):
        if ln.startswith("## ") and "当前在架招聘公告" in ln:
            start = i
        elif start is not None and ln.startswith("## ") and i > start:
            end = i
            break
    if start is None:
        return [], None
    end = end or len(lines)

    unit = ""
    items = []
    # 🔴🔴 四线报告的**表头列数不统一**（实测 2026-09-30）：
    #     机关/银行 = 7 列「日期|报名截止|状态|来源|监测源|热度|标题」
    #     电力/铁路 = 4 列「日期|报名截止|状态|标题」  ← 无来源/监测源/热度
    #⛔ 把列数写死会把三条线解析成 0 条且**不报错**（我09-30 实测踩中）。
    #   ⇒ 必须**按表头名动态映射列索引**，而不是按下标。
    colmap = None
    for ln in lines[start:end]:
        # 二级标题格式也不统一：机关/电力/银行是「**单位**（url）」，铁路是「**单位名**」无括号
        mu = re.match(r"^\*\*(.+?)\*\*\s*(（|\(|$)", ln)
        if mu:
            unit = mu.group(1).strip()
            continue
        if not ln.startswith("|"):
            continue
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]

        # 首次遇到表头 → 记列映射（"标题" 是最后一列）
        if cells and cells[0] == "日期":
            colmap = {name: i for i, name in enumerate(cells)}
            continue
        if colmap is None or "标题" not in colmap:
            continue
        # 行首必须像日期（或"—"），否则是分隔行/残留表头
        if not re.match(r"^(\d{4}-\d{2}-\d{2}|—|-)?$", cells[0]):
            continue

        def pick(name, default_idx=None):
            i = colmap.get(name, default_idx)
            return cells[i] if i is not None and i < len(cells) else "—"

        date, cutoff, status = pick("日期"), pick("报名截止"), pick("状态")
        title_cell = pick("标题")
        mm = re.search(r"\[(.+?)\]\((.+?)\)", title_cell)
        title = mm.group(1) if mm else title_cell
        url = mm.group(2) if mm else ""
        # 🔴 单位专名取「监测源」列而非挂载站——转载稿挂外站时挂载站≠发布单位，
        #    会把稿子算到别人头上。监测源末尾 `*`＝回落挂载站。
        src = pick("监测源")
        src_unit = src.rstrip("*").strip() if src and src != "—" else ""
        items.append({
            "unit": src_unit or unit, "host": unit,
            "date": date, "cutoff": cutoff, "status": status,
            "title": title, "url": url, "heat": pick("热度"),
        })

    meta = _read_claims(lines)

    return items, {
        "report": os.path.basename(rp),
        "claimed_main": meta.get("main"), "parsed": len(items),
        "in_stock": meta.get("in_stock", 0),
        "layers": meta.get("layers", {}),
    }


# 🔴🔴🔴 四线报告的概览表措辞**各不相同**（2026-09-30 实测逐行核对）：
#   机关 | **真·开启公告池（主口径，含已过期/待核，见下行分解）** | **277 条** |
#   电力 | **在架招聘公告（真·开启，主口径）** | **654 条**（跨源去重后；剔除重复 2508 条）
#   铁路 | **在架招聘公告（真·开启）**            | **26 条** |      ← **无「主口径」三字**
#   银行 | **在架招聘公告（真·开启，主口径）** | **36 条** |
#   分层行同样不齐：机关「长期（长期/招满即止类表述）」，铁路「长期」**光秃秃无括号**。
# ⇒⛔ 任何「按固定括号内容写正则」的解法都会在另一条线上静默返回 None（09-30 实测四线全 None）。
#   正确解法＝**逐行扫描概览区**（文件前 60 行），按关键词定位，取该行第一个「N 条」。
MAIN_KEYS = ("真·开启公告池", "在架招聘公告")
LAYER_KEYS = ("有效", "长期", "已过期", "待核")
_NUM_RE = re.compile(r"(\d+)\s*条")

def _first_count(line: str):
    m = _NUM_RE.search(line)
    return int(m.group(1)) if m else None

def _read_claims(lines):
    """读概览区的主口径与四层分层数。**逐行关键词定位**，不写死括号。"""
    out = {"main": None, "layers": {}}
    for ln in lines[:60]:
        s = ln.strip()
        if not s.startswith("|"):
            continue
        # 🔴 主口径行是**第一个**命中「真·开启公告池 / 在架招聘公告」的行；
        #   后面的分层行虽含「不算在架」字样但不含这两个开头词，不会误抢。
        if out["main"] is None and (any(k in s for k in MAIN_KEYS) or "主口径" in s):
            out["main"] = _first_count(s)
        for k in LAYER_KEYS:
            # 形如「├ 有效（…） | 36 条 |」或「├ 长期 | 3 条 |」
            m = re.match(r"^\|\s*[├└]?\s*\*?\*?" + k, s)
            if m:
                n = _first_count(s)
                if n is not None:
                    out["layers"][k] = n
                break
    v, lo = out["layers"].get("有效", 0), out["layers"].get("长期", 0)
    out["in_stock"] = v + lo
    return out

def engine_of(unit: str, title: str):
    text = f"{unit} {title}"
    for pat, eng, landing, note in ENGINE_RULES:
        if re.search(pat, text):
            return eng, landing, note
    return "job-write", DEFAULT_LANDING["job-write"], "默认 job-write 8 段"

def reject_reason(unit: str, title: str):
    text = f"{unit} {title}"
    for pat, why in REJECT_RULES:
        if re.search(pat, text):
            return why
    return None


# ============================================================
# 招聘主体抽取（🔴 2026-09-30 新增，修正一个真实误判）
# ============================================================
# ⛔ 巡检报告的「监测源」列是**转载方**，不是招聘主体。实测江苏省人社厅
#    监测源下 8 条全是高校稿（南京工程学院/扬州大学/泰州学院…），
#    拿「江苏省人力资源和社会保障厅」去搜本地稿件必然全假命中。
# ⇒ 必须从**标题**抽主体。实测主体几乎都是标题的前置专名段。

# 🔴⛔ 词表用 `|` 串起来时**绝不能**直接 `re.split(词表, ...)` ——
#    `re.split` 会把 `|` 当正则的「或」分支，**整个词表变成一个字符类**，
#    于是「江苏海洋大学」被切成「江苏海洋大」+「学」之类，甚至整串原样返回。
#    （09-30 我第一版就这么写的，9/9 用例全错，输出是词表字面量本身。）
#    正确写法：先按 | 切成普通字符串列表，再用 re.escape 逐个拼成 alternation。
_SUBJ_STOP_S = (
    "公告|简章|通知|公示|名单|计划|方案|办法|细则|问答|说明|解读|"
    "招聘|招募|选聘|遴选|引进|录用|招考|报考|笔试|面试|资格|体检|考察|"
    "公开|第二批|第三批|第四批|第五批|提前批|首批|第一批|年度|关于|"
    "转发|印发|报名|岗位|人员|工作人员|专职|辅导员|博士|硕士|本科|"
    "校园|宣讲|行程|专项|管培|菁英|乡村振兴|总部|技术|技能|操作|"
    "2026|2027|年|度|的|和|及|与"
)
_SUBJ_STOP_RE = re.compile(
    "|".join(re.escape(w) for w in _SUBJ_STOP_S.split("|") if w)
)
# 标题里的「2026年」「（第二批）」等噪声先剥掉，否则切不出干净专名
_NOISE_RE = re.compile(
    r"[（(][^）)]*[）)]|20\d{2}\s*年?|\s+|[-—－·、,，.。:：;；!！?？\"'“”‘’]"
)

def extract_subject(title: str, fallback: str = ""):
    """从公告标题抽招聘主体专名。

    策略：剥括号内容与年份数字 → 按 `_SUBJ_STOP` 词表切出**第一个**专名段。
    失败时退回监测源（宁可粗也别空，因为空串会被 written_check 静默放过）。
    """
    t = _NOISE_RE.sub("", title)
    for w in _SUBJ_STOP_RE.split(t):
        w = w.strip("[]【】（）()　 ,，。:：;；-—_")
        if len(w) >= 3 and not re.fullmatch(r"[\d一二三四五六七八九十百千万]+", w):
            return w
    return fallback


# ⛔ 聚合伪单位：监测源自报「全部/所有」，但每条公告主体不同（实测国网线 3 条）
FAKE_AGG_UNITS = ("全部单位", "所有单位", "各省市", "各单位汇总")

def is_fake_agg(unit: str) -> bool:
    return any(k in unit for k in FAKE_AGG_UNITS)


# ============================================================
# 「写过没」判定（⛔ 按单位专名，禁标题精确匹配 —— 红线）
# ============================================================
def load_corpus(ws: str):
    """收集所有本地稿件正文，供单位专名检索。"""
    corp = {}
    for line in ("2027年校园招聘", "事业单位", "教育系统", "人生方向"):
        for sub in ("待发布", "已发布"):
            base = ws_path(ws, line, sub)
            if not os.path.isdir(base):
                continue
            for root, _, files in os.walk(base):
                for fn in files:
                    if not fn.endswith(".md"):
                        continue
                    p = os.path.join(root, fn)
                    try:
                        corp[p] = open(p, encoding="utf-8", errors="ignore").read()
                    except Exception:
                        pass
    return corp

def written_check(unit: str, corp: dict):
    """⛔ 关键词过宽会假命中（实测：串稿检测排除清单 / 场址地名都能命中）。
    因此只用 ≥3 字且区分度高的单位专名片段，且命中后必须人工复核。

    🔴🔴 2026-09-30 实测修正：光「出现过」不足以判「写过」。
       三个真实假阳性——
         · 江苏海洋大学 → 命中扬州大学稿里的**串稿检测排除清单**
         · 扬州大学     → 命中盐城三院稿里的「扬州大学临床医学院」
         · 中国电力     → 命中国电南自稿里的「中国电力二次设备」
       共同点：**只出现在正文散文里，不在标题/落点/单位署名处**。
       ⇒ 判「真写过」必须命中**结构位**：文件名前缀、frontmatter 单位、
         或正文里以该专名**开头**的独立句。散文提及只记为 weak，交人工判断。
    """
    keys = [unit]
    for suffix in ("有限责任公司", "股份有限公司", "有限公司", "公司"):
        if unit.endswith(suffix):
            keys.append(unit[: -len(suffix)])
    keys = [k for k in keys if len(k) >= 3]
    strong, weak = [], []
    for k in keys:
        for p, t in corp.items():
            base = os.path.basename(p)
            # ① 文件名（最硬的证据：稿件以该单位命名）
            if k in base:
                strong.append(p)
                break
            # ② 正文里以专名开头的独立句/行（标题行、单位署名、列表项）
            if re.search(r"(?:^|[\n\|>#\-*])\s*" + re.escape(k), t):
                strong.append(p)
                break
            # ③ 仅散文提及 → 弱命中
            if k in t:
                weak.append(p)
    return {"strong": sorted(set(strong)), "weak": sorted(set(weak))}


# ============================================================
# 子命令 1：today —— 生成待办清单 + 候选池
# ============================================================
def cmd_today(args):
    ws = args.workspace
    today = today_str()
    print(f"\n{'='*78}\n巡检 → 写作流水线· 今日待办（{today}）\n{'='*78}\n")

    corp = load_corpus(ws)
    state = load_state(ws, required=False)
    st_by_key = state.get("batches", {})

    all_items = []
    print("【第0 步】巡检报告解析 + 守恒自检\n" + "-"*78)
    for key, (prefix, label) in LINES.items():
        items, meta = parse_in架(ws, prefix)
        if not items:
            print(f"  ⚠️{label:<6} 未解析到在架条目（报告缺失或结构变了）")
            if meta:
                print(f"      报告={meta['report']}")
            continue
        flag = ""
        if meta["in_stock"] and meta["in_stock"] != meta["parsed"]:
            flag = (f"🔴 渲染层失配！报告称在架 {meta['in_stock']} 条"
                    f"（有效+长期），实际渲染 {meta['parsed']} 条")
        elif meta["claimed_main"] and meta["claimed_main"] < meta["parsed"]:
            flag = (f"⚠️ 抓到的 {meta['parsed']} 条 > 主口径 {meta['claimed_main']}，"
                    f"疑似章节边界错位")
        else:
            flag = f"✅ 守恒（在架 {meta['parsed']} 条）"
        print(f"  {label:<6} {meta['report']:<34} 在架 {meta['parsed']:>3} 条"
              f"（主口径 {meta['claimed_main']}）  {flag}")
        for it in items:
            it["line"] = key
            it["line_label"] = label
            all_items.append(it)

    if not all_items:
        die("四条线都没解析到在架条目。⛔ 不要凭印象选活——先查报告结构是否变了。")

    # 分拣 + 判定
    todo, pool, rejected = [], [], []
    seen_url, seen_title = set(), set()
    dup_count, dup_detail = 0, []
    for it in all_items:
        # 🔴 招聘主体：从**标题**抽，不用监测源（监测源是转载方，见 extract_subject 注释）
        subj = extract_subject(it["title"], it["unit"])
        it["subject"] = subj

        # 🔴🔴 跨源去重**必须双键**，实测 2026-09-30：69 条在架条目里 URL **零重复**
        #    （同一条公告被 2 个监测源各印一遍，URL 完全不同），只按 URL 去重得到 0 —— 假阴性。
        #    归一化标题（去标点空白）后有 **4 组**真重复：
        #      · 无锡滨湖区卫健委  人社局站 vs 区政府站
        #      · 吴江教育系统博士  人社局站 vs 区政府站
        #      · 吴江卫健系统博士  人社局站 vs 区政府站
        #      · 南京市机关事务局  局站 vs 人社局站
        #    ⛔ 但**光按标题也不够**——同名公告可能属于不同单位/不同批次，
        #    故键＝「招聘主体 + 归一化标题」。⛔ 主体用监测源会导致不同单位的
        #    同名公告被误合并（监测源常是同一个市人社局）。
        _t = re.sub(r"[^\w一-鿿]", "", it["title"])
        tkey = f"{subj}||{_t}"
        if (it["url"] and it["url"] in seen_url) or tkey in seen_title:
            dup_count += 1
            dup_detail.append({
                "unit": it["unit"], "subject": subj, "title": it["title"],
                "url": it["url"], "line": it.get("line", ""),
            })
            continue
        if it["url"]:
            seen_url.add(it["url"])
        seen_title.add(tkey)

        rj = reject_reason(it["unit"], it["title"])
        # 🔴 聚合伪单位（监测源自报「国网全部单位」）必须排除：
        #    每条公告主体不同（黑龙江/天津/宁夏），拿聚合名当单位无法定位公告与截止，
        #    写稿时也拿不到对应网申入口。主体已在上面抽出，人工可按主体自行判断。
        if is_fake_agg(it["unit"]):
            rj = rj or f"⚠️ 监测源是聚合伪单位（{it['unit']}），主体见 subject 字段，需人工判断"

        # 🔴🔴 发布时间哨兵：拦「往年公告被误判成在架」。
        #    实测 2026-09-30 电力线：国网技术学院分公司 2022/2023/2023/2024 四条公告
        #    报名截止列全是「—」（正文未取到），却被巡检判成「长期」而留在在架层；
        #    而同站 2021~2025 的相似条目都正确落在「待核」。
        #    ⇒ 这是巡检分层 bug（红线：「抽不到截止≠长期」），**本脚本不擅改巡检**，
        #    但流水线侧必须独立设防：往年公告一律不作为当天写稿候选。
        pd = parse_date(it.get("date", ""))
        age_days = (datetime.date.today() - pd).days if pd else None
        if age_days is not None and age_days > STALE_AFTER_DAYS:
            rj = rj or (f"⛔ 往年公告（发布于 {it['date']}，距今 {age_days} 天）"
                        f"——疑似巡检把它误判成在架/长期，须回原文核实")

        eng, landing, note = engine_of(it["unit"], it["title"])
        cd = parse_date(it["cutoff"])
        days = (cd - datetime.date.today()).days if cd else None
        # 🔴 已写判定用**主体**（招聘单位），不是监测源
        hits = written_check(subj, corp)

        # 状态文件里的对应批次（⛔ 按主体匹配，不是监测源）
        st = None
        for k, v in st_by_key.items():
            if v.get("unit") == subj or (len(subj) >= 4 and subj[:4] in k):
                st = v.get("state")
                break

        rec = dict(it)
        rec.update({
            "engine": eng, "landing": landing, "engine_note": note,
            "days_left": days,
            "urgency": urgency_bucket(days) if days is not None else "待核-无截止日",
            "written_hits": hits,
            "already_written": bool(hits["strong"]),
            "state": st or "（状态文件无条目）",
            "cutoff_parsed": cd.isoformat() if cd else None,
        })

        if rj:
            rec["reject"] = rj
            rejected.append(rec)
        elif hits["strong"]:
            # 强命中＝稿件文件名/署名就是该单位 ⇒ 极可能已写过，排到最后由人确认
            rec["reject"] = (f"本地已有稿（{len(hits['strong'])} 处结构位命中）"
                             f"→ 复核是否已覆盖")
            rejected.append(rec)
        else:
            todo.append(rec)
        pool.append(rec)

    todo.sort(key=lambda r: (r["days_left"] if r["days_left"] is not None else 9999))

    # ---------- 今日待办 ----------
    outdir = ws_path(ws, PIPE_DIR, today)
    os.makedirs(outdir, exist_ok=True)
    todo_md = os.path.join(outdir, "01-今日待办.md")

    with open(todo_md, "w", encoding="utf-8") as f:
        f.write(f"# 今日待办清单 · {today}\n\n")
        f.write("> **你在这里做两件事**：① 勾掉不写的 ② 把要写的排序。\n")
        f.write("> 勾选方式：把`[ ]` 改成 `[x]`，或直接告诉 AI 「写第 N 条」。\n")
        f.write(f"> 数据源：四线最新巡检报告 ＋ `内容状态.json` ＋ 本地稿件单位专名检索。\n\n")

        f.write(f"## 一、建议今天写（{len(todo)} 条，按截止升序）\n\n")
        buckets = OrderedDict()
        for r in todo:
            buckets.setdefault(r["urgency"], []).append(r)
        for b in ("P0-今天/明天截止", "P1-10天内截止", "P2-窗口宽裕", "P3-长期窗口", "待核-无截止日"):
            rows = buckets.get(b, [])
            if not rows:
                continue
            f.write(f"### {b}（{len(rows)} 条）\n\n")
            f.write("| # | 单位 | 公告 | 截止 | 剩 | 引擎 | 落点 |\n|---|---|---|---|---|---|---|\n")
            for i, r in enumerate(rows, 1):
                f.write(f"| {i} | {r['unit']} | {r['title']} | {r['cutoff']} | "
                        f"{r['days_left'] if r['days_left'] is not None else '—'} | {r['engine']} | `{r['landing']}` |\n")
            f.write("\n")

        f.write("## 二、已排除（⛔ 别写，供你复核判断）\n\n")
        f.write("| 单位 | 公告 | 排除原因 |\n|---|---|---|\n")
        for r in rejected:
            f.write(f"| {r['unit']} | {r['title']} | {r['reject']} |\n")
        if not rejected:
            f.write("| — | — | （无） |\n")

        f.write("\n## 三、你确认后，AI 按此执行\n\n")
        f.write("```bash\n")
        f.write(f"# 第 1 步：播种（把上面勾中的条目写进状态文件）\n")
        f.write(f"{py()} {JOB_WRITE} --state-init --workspace {ws}   # 首次才需要\n\n")
        f.write(f"# 第 2 步：出投料单（硬信息仍须回官方原文逐条核）\n")
        f.write(f"{py()} {JOB_WRITE} \"<单位专名>\" --workspace {ws}\n\n")
        f.write(f"# 第 3 步：成稿后回填状态\n")
        f.write(f"{py()} patrol_to_publish.py mark \"<单位专名>\" --to written\n\n")
        f.write(f"# 第 4 步：推草稿箱（⛔ 唯一正确姿势 = --html 排版稿）\n")
        f.write(f"{py()} {MP_PUBLISH}/wx_pipeline.py --profile mashang --html <排版.html>\n\n")
        f.write(f"# 第 5 步：草稿箱验收（draft/get 回读，唯一可信依据）\n")
        f.write(f"{py()} {MP_PUBLISH}/wx_draft.py get <media_id> --profile mashang\n\n")
        f.write(f"# 第 6 步：🧑 你在公众号后台点群发，然后告诉 AI\n")
        f.write(f"# 第 7 步：AI 核验发表记录 + 归档 + 回填 published\n")
        f.write(f"{py()} patrol_to_publish.py verify \"<单位专名>\"\n")
        f.write(f"{py()} patrol_to_publish.py archive \"<单位专名>\"\n")
        f.write("```\n")

    ok(f"今日待办 → {todo_md}")

    # ---------- 完整候选池（JSON，供筛选） ----------
    pool_json = os.path.join(outdir, "02-候选池.json")
    with open(pool_json, "w", encoding="utf-8") as f:
        json.dump({
            "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
            "workspace": ws,
            "counts": {"todo": len(todo), "excluded": len(rejected),
                        "parsed_total": len(pool), "dedup_dropped": dup_count},
            "dedup_dropped_detail": dup_detail,
            "items": pool,
        }, f, ensure_ascii=False, indent=2)
    ok(f"完整候选池 → {pool_json}")

    # ---------- 当期看板 ----------
    board = ws_path(ws, PIPE_DIR, "待办.md")
    os.makedirs(os.path.dirname(board), exist_ok=True)
    with open(board, "w", encoding="utf-8") as f:
        f.write(f"# 流水线看板\n\n> 最近一次生成：{today} {datetime.datetime.now():%H:%M}\n\n")
        f.write(f"- 今日建议写：**{len(todo)}** 条｜ 已排除：{len(rejected)} 条｜ "
                    f"解析总条目：{len(pool)}｜ 跨源重复已去重：{dup_count}\n")
        if dup_detail:
            f.write(f"- ⚠️ 去重明细（转载同一公告）已落 `02-候选池.json` 的 "
                    f"`dedup_dropped_detail`，共 {len(dup_detail)} 组，需人工确认\n")
        f.write(f"- 明细：[今日待办](./{today}/01-今日待办.md)｜ [候选池](./{today}/02-候选池.json)\n")

    print("\n" + "="*78)
    print(f"建议今天写 {len(todo)} 条｜已排除 {len(rejected)} 条｜"
          f"解析总条目 {len(pool)} 条｜跨源重复去重 {dup_count} 条")
    print("="*78)
    for b in ("P0-今天/明天截止", "P1-10天内截止", "P2-窗口宽裕", "P3-长期窗口"):
        rows = buckets.get(b, [])
        if not rows:
            continue
        print(f"\n【{b}】")
        for i, r in enumerate(rows, 1):
            print(f"  {i}. {r['subject']}｜截止 {r['cutoff']}（剩 {r['days_left']}天）｜{r['engine']}")
    print(f"\n📂 明细：{todo_md}")
    print(f"🧑 请在明细里勾选，或直接告诉我写哪几条。")


# ============================================================
# 子命令 2：sync —— 播种巡检条目进状态文件
# ============================================================
def cmd_sync(args):
    ws = args.workspace
    state = load_state(ws)
    batches = state.setdefault("batches", {})

    added, skipped = 0, 0
    for key, (prefix, label) in LINES.items():
        items, meta = parse_in架(ws, prefix)
        if not items:
            continue
        for it in items:
            subj = extract_subject(it["title"], it["unit"])
            k = it["url"] or f"{subj}||{it['title']}"
            if k in batches:
                skipped += 1
                continue
            batches[k] = {
                # 🔴 unit 存**招聘主体**（从标题抽），不是监测源。
                #    存监测源会让「江苏省人社厅」下 8 所高校全被算成同一单位。
                "unit": subj, "host": it.get("host", ""), "patrol_source": it["unit"],
                "title": it["title"], "state": "unwritten",
                "history": [{
                    "at": datetime.datetime.now().isoformat(timespec="seconds"),
                    "from": "", "to": "unwritten", "by": "AI",
                    "note": f"播种：来自 {label}巡检 {meta['report']}",
                }],
                "facts": {
                    "source_url": it["url"],
                    "公告发布日": it["date"],
                    "报名截止": it["cutoff"],
                    "from_patrol": label,
                },
                "files": {}, "notes": "",
            }
            added += 1

    if args.dry_run:
        print(f"\n[dry-run] 将新增 {added} 条，跳过（已存在）{skipped} 条。未落盘。\n")
        return
    save_state(ws, state)
    ok(f"播种完成：新增 {added} 条，跳过 {skipped} 条")


# ============================================================
# 子命令 3：mark —— 推进状态
# ============================================================
def cmd_mark(args):
    ws = args.workspace
    state = load_state(ws)
    batches = state["batches"]

    hits = [(k, v) for k, v in batches.items()
            if args.keyword in v.get("unit", "") or args.keyword in k]
    if not hits:
        die(f"没匹配到批次：{args.keyword}")

    if len(hits) > 1 and not args.all:
        print(f"\n⚠️匹配到 {len(hits)} 条，请指定更精确的关键词，或加 --all：\n")
        for k, v in hits[:20]:
            print(f"   {v.get('state'):<10} {v.get('unit')}｜{v.get('title')[:40]}")
        sys.exit(2)

    target = args.to
    changed, unchanged = [], []
    for k, v in hits:
        old = v.get("state", "")
        if old == target and not args.facts and not args.file:
            # ⛔ 静默 skip 会让人误判「没匹配到」——必须打印是哪条、当前什么态
            unchanged.append((k, old))
            continue
        v["state"] = target
        v.setdefault("history", []).append({
            "at": datetime.datetime.now().isoformat(timespec="seconds"),
            "from": old, "to": target, "by": args.by,
            "note": args.note or f"人工推进 {old}→{target}",
        })
        for kv in (args.facts or []):
            if "=" in kv:
                kk, vv = kv.split("=", 1)
                v.setdefault("facts", {})[kk] = vv
        if args.file:
            v.setdefault("files", {})[target] = args.file
        changed.append((k, old, target))

    for k, o in unchanged:
        print(f"   ⓘ 已是目标态，未变更：[{o}] {k[:60]}")
    if not changed:
        print(f"\n（无变化：命中 {len(hits)} 条，全部已是 {target}）\n")
        return
    if args.dry_run:
        print(f"\n[dry-run] 将变更 {len(changed)} 条：")
        for k, o, t in changed:
            print(f"   {o} → {t}   {k[:60]}")
        return
    save_state(ws, state)
    for k, o, t in changed:
        ok(f"{o} → {t}   {k[:60]}")


# ============================================================
# 子命令 4：audit —— 四方对账
# ============================================================
def cmd_audit(args):
    ws = args.workspace
    print(f"\n{'='*78}\n四方对账（状态文件 ↔ 总表两列 ↔ 各线目录 ↔ 巡检在架）\n{'='*78}\n")

    state = load_state(ws, required=False)
    batches = state.get("batches", {})
    cnt = Counter(v.get("state") for v in batches.values())
    print("【1】状态文件四态分布")
    for s in ("unwritten", "written", "draft", "published"):
        print(f"    {s:<12}{cnt.get(s,0):>4}")
    print(f"    {'合计':<12}{sum(cnt.values()):>4}\n")

    # 目录实况
    print("【2】各线目录实况（磁盘 vs 状态文件）")
    corp = load_corpus(ws)
    for line in ("2027年校园招聘", "事业单位", "教育系统", "人生方向"):
        for sub in ("待发布", "已发布"):
            d = ws_path(ws, line, sub)
            if not os.path.isdir(d):
                print(f"    {line}/{sub:<6} ⚠️ 目录不存在")
                continue
            n = sum(1 for r, _, fs in os.walk(d) for f in fs if f.endswith(".md"))
            print(f"    {line}/{sub:<6} {n:>4} 篇源稿")
    print()

    # 不一致：状态说写了但磁盘找不到
    # 🔴⛔ 2026-09-30 修正：这一项原先用「专名在正文出现过」判存在，
    #    于是 40 条 published / 45 条 written 大面积假警报（实测第 3 项报出几十条，
    #    抽样核对稿件其实都在 待发布/ 里，只是标题被微信为打开率改写过）。
    #    ⇒ 改用 written_check 的**强命中**（文件名或正文行首/署名命中）。
    #    弱命中（仅散文提及）**不算写过**，否则等于没判。
    print("【3】🔴 不一致：状态 written/published 但本地无稿（按强命中判）")
    bad = []
    for k, v in batches.items():
        if v.get("state") not in ("written", "draft", "published"):
            continue
        u = v.get("unit", "")
        if not u:
            continue
        if not written_check(u, corp)["strong"]:
            bad.append((v.get("state"), u, v.get("title", "")[:36]))
    if bad:
        for s, u, t in bad[:30]:
            print(f"    [{s}] {u}｜{t}")
        print(f"    共 {len(bad)} 条")
    else:
        print("    （无）")
    print()

    # 状态文件缺条目
    print("【4】⚠️ 巡检在架但状态文件无条目（需sync）")
    miss = 0
    for key, (prefix, label) in LINES.items():
        items, _ = parse_in架(ws, prefix)
        for it in items or []:
            subj = extract_subject(it["title"], it["unit"])
            k = it["url"] or f"{subj}||{it['title']}"
            if k not in batches:
                # 打主体不打监测源——监测源会把无关公告挂到同一个单位名下
                print(f"    [{label}] {subj}｜{it['title'][:44]}")
                miss += 1
    if miss == 0:
        print("    （无）")
    else:
        print(f"    共 {miss} 条 → 跑 sync 播种")

    print("\n" + "="*78 + "\n")


# ============================================================
# 子命令 5：verify —— 核验是否已发布（⛔ 只认后台发表记录）
# ============================================================
def cmd_verify(args):
    ws = args.workspace
    print(f"\n{'='*78}\n核验是否已发布：{args.keyword}\n{'='*78}\n")
    print("⛔ 判据＝**后台「发表记录」**，草稿箱是暂存区不可作判据")
    print("   （稿一旦群发立刻从 draft/batchget 消失，只在发表记录里）\n")

    ledger = ws_path(ws, "运营/01-线上已发布台账.md")
    if not os.path.exists(ledger):
        die(f"台账不存在：{ledger}")
    text = open(ledger, encoding="utf-8", errors="ignore").read()

    # 🔴 微信为打开率会彻底改写标题 →⛔ 禁标题精确匹配，用主体专名 + 最长公共子串
    keys = [args.keyword]
    for suffix in ("有限责任公司", "股份有限公司", "有限公司", "公司"):
        if args.keyword.endswith(suffix):
            keys.append(args.keyword[: -len(suffix)])
    keys = [k for k in keys if len(k) >= 3]

    hits = [ln for ln in text.split("\n")
            if any(k in ln for k in keys)]
    if hits:
        print("✅ 台账中有匹配记录（⛔ 需回公众号后台「发表记录」二次确认）：\n")
        for h in hits[:8]:
            print(f"   {h.strip()[:150]}")
        print(f"\n下一步：刷新后台发表记录到今天 → 确认是否真已群发。")
    else:
        print("⚠️ 台账中无匹配。可能是真没发，也可能是台账滞后（台账靠人工手填，历史上曾滞后 4–5 天）。")
        print("   → 去公众号后台「发表记录」按主体专名检索确认。")
    print()


# ============================================================
# 子命令 6：archive —— 归档（红线 11）
# ============================================================
def cmd_archive(args):
    ws = args.workspace
    state = load_state(ws, required=False)
    batches = state["batches"]
    corp = load_corpus(ws)

    hits = [(k, v) for k, v in batches.items() if args.keyword in v.get("unit", "")]
    if not hits:
        die(f"状态文件里没匹配到：{args.keyword}")

    moved = []
    for k, v in hits:
        if v.get("state") != "published":
            print(f"⚠️ 跳过：{v.get('unit')} 状态是 {v.get('state')}，⛔ 只有 published 才归档")
            continue
        u = v.get("unit", "")
        keys = [x for x in (u, u.replace("有限公司", ""), u.replace("有限责任公司", "")) if len(x) >= 3]
        srcs = [p for p, t in corp.items()
                if "/待发布/" in p and any(kk in p or kk in t for kk in keys)]
        if not srcs:
            print(f"ℹ️ 已在归档位或本地无稿：{u}")
            continue
        line = srcs[0].split(f"{ws}/")[1].split("/")[0]
        for s in srcs:
            dst_dir = ws_path(ws, line, "已发布")
            os.makedirs(dst_dir, exist_ok=True)
            base = os.path.basename(s)
            dst = os.path.join(dst_dir, base)
            if os.path.exists(dst):
                continue
            # 🔴 必须 git mv：mv 会让稿件脱离版本控制（教育线 3 篇就是这么丢的）
            r = subprocess.run(["git", "mv", s, dst], cwd=os.path.dirname(ws),
                               capture_output=True, text=True)
            if r.returncode != 0:
                # git mv 失败（文件未被跟踪）→ 退回 mv 并明确告警
                subprocess.run(["mv", s, dst])
                print(f"⚠️ {base} 未被 git 跟踪，已用 mv 归档（⛔ 该文件脱离版本控制，建议立即 git add）")
            else:
                print(f"✅ git mv {base} → {line}/已发布/")
            moved.append(base)
            stem = base.rsplit(".", 1)[0]
            for ext in ("-排版.html", "-封面.png", "-源稿.md"):
                pass  # 三件套已在同一目录，一并移动即可
            v.setdefault("files", {})["archived"] = os.path.relpath(dst, ws)

    if moved:
        save_state(ws, state)
        ok(f"归档 {len(moved)} 个文件（红线 11：发布后当天归档）")
    else:
        print("\n（无可归档内容）")


# ============================================================
# CLI
# ============================================================
def main():
    ap = argparse.ArgumentParser(
        description="巡检→写作→推送→发布→回填 的单一入口编排器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
典型一天：
  # 1) 跑完巡检后，生成待办清单（每天一次）
  patrol_to_publish.py today
  # 2) 把清单里要写的条目播种进状态文件
  patrol_to_publish.py sync
  # 3) AI 成稿后推进状态
  patrol_to_publish.py mark "<单位>" --to written --file "<排版.html>"
  # 4) 推草稿箱（走wx_pipeline.py，本脚本不碰发布）
  # 5) 人工后台群发后，核验 + 归档 + 回填
  patrol_to_publish.py verify "<单位>"
  patrol_to_publish.py archive "<单位>"
  patrol_to_publish.py audit
        """)
    ap.add_argument("--workspace", default=DEFAULT_WS, help="工作区根目录")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("today", help="生成今日待办清单 + 完整候选池")
    p.set_defaults(func=cmd_today)

    p = sub.add_parser("sync", help="把巡检条目播种进状态文件（幂等）")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=cmd_sync)

    p = sub.add_parser("mark", help="推进批次状态")
    p.add_argument("keyword")
    p.add_argument("--to", required=True,
                   choices=["unwritten", "written", "draft", "published"])
    p.add_argument("--facts", action="append", help="KEY=VALUE，可重复")
    p.add_argument("--file", help="记录产物路径")
    p.add_argument("--by", default="AI")
    p.add_argument("--note")
    p.add_argument("--all", action="store_true", help="匹配多条时全部推进")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=cmd_mark)

    p = sub.add_parser("audit", help="四方对账")
    p.set_defaults(func=cmd_audit)

    p = sub.add_parser("verify", help="核验是否已发布（⛔ 只认后台发表记录）")
    p.add_argument("keyword")
    p.set_defaults(func=cmd_verify)

    p = sub.add_parser("archive", help="归档已发布稿（红线 11）")
    p.add_argument("keyword")
    p.set_defaults(func=cmd_archive)

    args = ap.parse_args()
    if not os.path.isdir(args.workspace):
        die(f"工作区不存在：{args.workspace}")
    args.func(args)


if __name__ == "__main__":
    main()