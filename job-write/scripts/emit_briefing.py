#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
emit_briefing.py —— 从 ijob「jobs.db」生成写稿用的 BRIEFING（给 AI 的投料单）

为什么要有这个脚本
==================
写稿提示词最大的 token 浪费与最大的质量风险来自同一件事：
  让模型去「找」硬信息。
  - 省 token 的角度：找 = 多轮工具调用 + 正文回流，一次找不全要重找。
  - 质量的角度：找不到时模型会「合理补全」——这正是 09-18 紫金稿翻车的机理
    （非官方口径 60 名 / 11-02 截止被当成事实写进正文）。

所以把「确定性部分」从提示词里拿走：由脚本从主档搬字段 + 显式标出缺口，
模型只做「表达转换」，不做信息检索，也不被允许推测。

数据源（2026-09-21 起）
======================
**唯一事实源 = `/Users/zhugx/src/ijob/data/jobs.db`（SQLite）**。
⛔ 旧主档 `工具/公司主数据.csv` 及其构建脚本已作废，不要再读、不要再改。

用法
====
  # 按关键词出 briefing（打印到 stdout）
  python3 emit_briefing.py "国网江苏"

  # 写成本次写稿的投料单文件
  python3 emit_briefing.py "国网江苏" --out /tmp/briefings/

  # 多条一起（批量开稿前先看缺口全景）
  python3 emit_briefing.py "国网" "南瑞" --gap-only

  # 列出所有「硬信息已够、可以动笔」的单位（选题用；**自动与草稿箱对账**）
  python3 emit_briefing.py --ready

  # 只对账、不改名单：逐条打印「草稿标题 → DB 对应批次 + 稿件状态」
  python3 emit_briefing.py --draftbox-audit

  # 换公众号账号对账（默认 mashang=码上职业）
  python3 emit_briefing.py --ready --profile mashang

字段可信度三档
==============
  OK     主档有确定值（含具体日期/具体人数）
  VAGUE  主档是软词（待核/预计/滚动/招满即止/暂无）→ 不得写进正文，必须回官方补
  EMPTY  主档为空

⛔ 改动主档的口径：事实数据一律进 `jobs.db`
（`companies` / `campaigns`（渠道与排雷字段已并入本表）/ `campaign_articles`（正文）/ `company_profiles` / `patrol_sources`），
不再有 CSV 环节。详见项目 MEMORY.md。

草稿箱对账（2026-09-21 加）
==========================
`campaigns.has_article`（= `rendered_html` 长度 >50）**只反映库里有没有稿**，
**不等于草稿箱的真实状态** —— 推完草稿箱若忘了回填 `rendered_html`，DB 会一直显示「未排」。
所以 `--ready` 在给名单前**强制与草稿箱对一次账**（对账键＝`campaigns.title` 与草稿标题，
标题不匹配时再用「单位名主体前缀互含」兜底）。对上的单位不再算「待写」，单独列进
「⚠️ 疑似已在草稿箱」区；`--include-suspect` 可把它们并回主名单。

⛔ 登录态失效时**只降级告警、不自动登录**（见项目 MEMORY.md §十）；
脚本取不到草稿列表会明确打印「对账跳过」，此时名单不可直接采信。
"""
import argparse
import os
import re
import sqlite3
import subprocess
import sys
from datetime import datetime

DEFAULT_DB = "/Users/zhugx/src/ijob/data/jobs.db"
# 草稿箱取数脚本（mp-publish 技能内，唯一权威位置）
DRAFT_SCRIPT = os.path.join(
    os.path.expanduser("~"), ".workbuddy/skills/mp-publish/scripts/wx_draft.py")
DEFAULT_PROFILE = "mashang"

DB_PATH = DEFAULT_DB

# 占位截止日：ijob 对「尚未核实截止日」的批次统一用该日期占位，
# 判定时必须结合 batch_type / title 的「待核」字样降级为 VAGUE，否则会把占位日当事实写进正文。
PLACEHOLDER_DEADLINE = "2026-12-31"

SQL = """
SELECT
  co.name                AS company,
  co.full_name           AS full_name,
  co.nature              AS nature,
  co.industry_catalog    AS industry_catalog,
  co.headquarters_city   AS headquarters_city,
  co.official_site       AS official_site,
  c.id                   AS cid,
  c.title                AS title,
  c.batch_type           AS batch_type,
  c.line                 AS line,
  c.target_graduates     AS target_graduates,
  c.min_degree           AS min_degree,
  c.total_vacancies      AS total_vacancies,
  c.employment_nature    AS employment_nature,
  c.city                 AS city,
  c.publish_date         AS publish_date,
  c.deadline             AS deadline,
  c.status               AS status,
  c.verdict_summary      AS verdict_summary,
  c.apply_url            AS apply_url,
  c.announcement_url     AS announcement_url,
  c.consulting_phone     AS consulting_phone,
  c.wechat_url           AS wechat_url,
  c.has_article          AS has_article,
  length(coalesce(a.rendered_html, ''))    AS html_len,
  c.age_limit            AS age_limit,
  c.cet_requirement      AS cet_requirement,
  c.computer_cert_requirement AS computer_cert_requirement,
  c.chsi_valid_date      AS chsi_valid_date,
  c.medical_veto_rules   AS medical_veto_rules,
  c.allocation_rules     AS allocation_rules,
  c.pitfall_warnings     AS pitfall_warnings
FROM campaigns c
JOIN companies co ON co.id = c.company_id
LEFT JOIN campaign_articles a ON a.campaign_id = c.id
WHERE c.status != '已截止'
"""

# ── 主档列 → briefing 字段 的映射（左=DB 键, 右=(briefing键, 展示名)）
FIELD_MAP = [
    ("full_name",         ("unit",         "单位全称")),
    ("line",              ("line",         "线(A校招/B编制)")),
    ("industry_catalog",  ("industry",     "行业分组")),
    ("nature",            ("nature",       "单位性质")),
    ("batch_type",        ("batch",        "批次/说明")),
    ("total_vacancies",   ("hc",           "招录规模")),
    ("deadline",          ("deadline",     "报名截止")),
    ("publish_date",      ("announce_date","公告发布日")),
    ("city",              ("location",     "工作地点")),
    ("min_degree",        ("edu",          "学历要求")),
    ("employment_nature", ("employment",   "用工性质")),
    ("target_graduates",  ("target_class", "面向届别")),
    ("status",            ("status",       "批次状态")),
]

# 写稿「必填事实」：缺一项就写不出不误导的招聘稿。
# key -> (展示名, DB 键, 出现在哪一段)
REQUIRED = {
    "unit":          ("单位全称",     "full_name",        "段4 单位来头"),
    "deadline":      ("报名截止",     "deadline",         "段3 宫格 / SEO摘要 / 钩子"),
    "edu":           ("学历要求",     "min_degree",       "段5 岗位表 / FAQ"),
    "employment":    ("用工性质",     "employment_nature","段4 解读四问①"),
    "target_class":  ("面向届别",     "target_graduates", "段6 条件"),
    "location":      ("工作地点",     "city",             "段5 岗位表"),
    "announce_date": ("公告发布日",   "publish_date",     "时效标注"),
}
# 「资格与禁入红线」= **建议项，不阻塞动笔**（ijob 只对部分批次做了结构化，
# 绝大多数批次该组为空，若纳入 REQUIRED 会把全部单位误判为「不可动笔」）。
ADVISORY = {
    "gates": ("资格与禁入红线", "__gates__", "段5 资格与禁入"),
}
# 「资格与禁入」组合判定：以下任一非空即算已结构化
GATE_KEYS = ["age_limit", "cet_requirement", "computer_cert_requirement",
             "medical_veto_rules", "chsi_valid_date"]

# 软词：出现这些 = 未核实，禁止当事实写进正文
VAGUE_PAT = re.compile(
    r"待核|待定|预计|暂无|滚动|招满即止|详见|另行通知|以.{0,6}为准|◐|—|-{2,}|^\s*$"
)
DATE_PAT = re.compile(r"\d{4}-\d{2}-\d{2}|\d{1,2}月\d{1,2}日|\d{2}-\d{2}")


def grade(val):
    """判定字段可信度：OK / VAGUE / EMPTY"""
    v = (val or "").strip()
    if not v:
        return "EMPTY"
    if VAGUE_PAT.search(v) and not DATE_PAT.search(v):
        return "VAGUE"
    return "OK"


def grade_deadline(row):
    """截止日专判：占位日期 + 「待核」字样 → VAGUE，避免把占位日当事实"""
    v = (row["deadline"] or "").strip()
    if not v:
        return "EMPTY"
    blob = f"{row['batch_type'] or ''}{row['title'] or ''}{row['verdict_summary'] or ''}"
    if "待核" in blob or "待官方公告" in blob or "未披露" in blob:
        return "VAGUE"
    if v == PLACEHOLDER_DEADLINE:
        return "VAGUE"
    return grade(v)


def grade_gates(row):
    """资格与禁入：任一红线非空 → OK；全空 → EMPTY"""
    got = [k for k in GATE_KEYS if (row[k] or "").strip()]
    return "OK" if got else "EMPTY"


def draft_state(row):
    """稿件进度（由 ijob 字段推导，替代旧 CSV「稿件」五态）"""
    if (row["wechat_url"] or "").strip() and len(row["wechat_url"].strip()) > 10:
        return "已发布"
    if (row["html_len"] or 0) > 50:
        return "已推草稿箱"
    return "未排"


# ─────────────────────────────────────────────────────────────
# 草稿箱对账（2026-09-21 加）—— `--ready` 的强制前置
# ─────────────────────────────────────────────────────────────
def fetch_draft_titles(profile=DEFAULT_PROFILE, max_pages=12):
    """拉草稿箱全部标题。返回 (titles, media_ids)；
    取不到（脚本缺失/登录态失效/超时）→ (None, [])，调用方必须降级而不是当空箱。"""
    if not os.path.exists(DRAFT_SCRIPT):
        return None, []
    titles, mids = [], []
    try:
        for off in range(0, max_pages * 20, 20):
            p = subprocess.run(
                [sys.executable, DRAFT_SCRIPT, "list", "--profile", profile,
                 "--offset", str(off), "--count", "20"],
                capture_output=True, text=True, timeout=90)
            if p.returncode != 0:
                return None, []
            # 行格式： <idx> <YYYY-MM-DD> <HH:MM:SS> <media_id> <标题>
            lines = [l for l in p.stdout.splitlines()
                     if re.match(r"^\s*\d+\s+\d{4}-\d{2}-\d{2}", l)]
            if not lines:
                break
            for l in lines:
                pr = l.split(None, 4)
                if len(pr) >= 5:
                    m = re.search(r"(Va\w{20,})", pr[3])
                    mids.append(m.group(1) if m else "")
                    titles.append(pr[4].strip())
    except Exception:
        return None, []
    return (titles or None), mids


def _norm(s):
    return re.sub(r"[\s\u3000]+", "", (s or "").strip())


def _cjk_brand(text):
    """从稿题粗提「单位名主体」：去【】前缀 → 切到年份/校招等词 → 取最长中文串。
    例：『1200+岗！江苏农商行系统2027校招启动…』→『江苏农商行系统』"""
    t = re.sub(r"^[【\[][^】\]]*[】\]]", "", text or "").strip()
    t = re.split(r"20\d\d|校招|校园招聘|秋季|春季|秋招|春招|招聘", t)[0]
    runs = re.findall(r"[\u4e00-\u9fa5]{2,}", t)
    return max(runs, key=len) if runs else ""


# 「同前缀但属不同法人/子公司」的后缀：命中则不算同一单位（防 华泰证券资管≈华泰证券 这类误报）
_SUBSIDIARY_SUFFIX = ("资管", "基金", "期货", "信托", "租赁", "理财", "保险",
                      "消费金融", "财富管理", "投资银行", "投行", "国际", "香港")


def draft_hit(campaign_name, draft_brands, min_len=4):
    """单位名是否疑似已在草稿箱：与草稿「单位名主体」前缀互含（长度≥min_len）。
    返回命中的草稿单位名，未命中返回 None。宁可多报（只作告警），不可漏报。"""
    n = _norm(re.sub(r"[（(].*?[）)]", "", campaign_name or ""))
    toks = set(re.findall(r"[\u4e00-\u9fa5]{%d,}" % min_len, n))
    if len(n) >= min_len:
        toks.add(n)
    for b in draft_brands:
        if len(b) < min_len:
            continue
        for t in toks:
            if t == b or b.startswith(t):
                return b
            if t.startswith(b):          # t 比草稿名更长 → 须排除「子公司/兄弟法人」后缀
                rest = t[len(b):]
                if not any(rest.startswith(s) for s in _SUBSIDIARY_SUFFIX):
                    return b
    return None


def norm_apply_url(v):
    """归一化网申入口，用于「同一入口 = 同一写作单位」的合并（去协议/注释/尾斜杠/大小写）"""
    u = re.sub(r"^https?://", "", (v or "").strip()).lower()
    u = re.sub(r"[（(].*?[）)]", "", u)          # 去 '（⛔ 51job专题）' 这类注记
    return u.strip().strip("/")


def reconcile_draftbox(conn, titles):
    """对账：逐条草稿标题 → DB 对应批次 + 稿件状态。
    返回 (rows, unmatched, desync)；desync = 草稿有、DB 却显示「未排」（需回填）。"""
    cur = conn.cursor()
    cur.execute("""SELECT c.id, co.name AS company, co.full_name AS full_name, c.title,
                          c.has_article, c.wechat_url,
                          length(coalesce(a.rendered_html,'')) AS html_len,
                          coalesce(a.rendered_html,'') AS rh
                   FROM campaigns c JOIN companies co ON co.id=c.company_id
                   LEFT JOIN campaign_articles a ON a.campaign_id=c.id""")
    cols = [d[0] for d in cur.description]
    all_rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    by_title = {_norm(r["title"]): r for r in all_rows}
    matched, unmatched, desync = [], [], []
    for t in titles:
        nt = _norm(t)
        r, how = by_title.get(nt), "标题精确"
        if r is None:  # 兜底：正文包含该标题
            probe = nt[:18]
            cand = [x for x in all_rows if probe and x["html_len"] > 0 and probe in _norm(x["rh"])]
            if cand:
                r, how = max(cand, key=lambda x: x["html_len"]), "正文含标题"
        if r is None:
            unmatched.append(t)
            continue
        st = draft_state(r)
        matched.append((t, r["id"], r["full_name"] or r["company"], st, how))
        if st == "未排":
            desync.append((r["id"], r["full_name"] or r["company"], t))
    return matched, unmatched, desync


def pick_sources(row):
    """挑出可用于回官方补数的 URL / 入口"""
    out = []
    for key, label in (("apply_url", "网申入口"), ("announcement_url", "公告原文"),
                       ("official_site", "官网地址"), ("consulting_phone", "咨询电话")):
        v = (row[key] or "").strip()
        if v:
            out.append((label, v))
    return out


def clean_url(v):
    """把 'rsj.taizhou.gov.cn（通知公告栏）' 拆成 url + 注记"""
    m = re.match(r"^([^\s（(]+)\s*[（(]([^）)]*)[）)]", v)
    if m:
        return m.group(1), m.group(2)
    return v, ""


def build_briefing(row, today):
    kname = (row["full_name"] or row["company"] or "").strip()
    line = (row["line"] or "").strip()
    L = []

    L.append(f"# BRIEFING · {kname}")
    L.append("")
    L.append(f"> 机器生成于 {today} ｜ 数据源：`ijob/data/jobs.db`（唯一事实源）｜ "
             f"**本文件不是核实结论，是核实起点**")
    L.append(f"> 批次ID `{row['cid']}` ｜ 稿件进度：**{draft_state(row)}**")
    L.append("")

    # ── A. 主档已有值
    L.append("## A. 主档硬信息（可直接引用，但需与官方公告逐字对照）")
    L.append("")
    L.append("| 字段 | 值 | 可信度 |")
    L.append("|---|---|---|")
    for key, (bkey, label) in FIELD_MAP:
        val = (row[key] or "").strip()
        if not val:
            continue
        g = grade_deadline(row) if key == "deadline" else grade(val)
        g_s = {"OK": "✅ 确定", "VAGUE": "⚠️ 软词·未核", "EMPTY": "—"}[g]
        val_show = val.replace("|", "\\|").replace("\n", " ")[:80]
        L.append(f"| {label} | {val_show} | {g_s} |")
    L.append("")

    # ── A2. 资格与禁入红线（ijob 结构化字段，写稿核心）
    gates = [(k, (row[k] or "").strip()) for k in GATE_KEYS if (row[k] or "").strip()]
    L.append("## A2. 资格与禁入红线（用于「段5 资格与禁入」）")
    L.append("")
    if gates:
        GATE_LABEL = {
            "age_limit": "年龄上限", "cet_requirement": "英语门槛",
            "computer_cert_requirement": "计算机证", "medical_veto_rules": "体检红线",
            "chsi_valid_date": "学信验证/体检细则",
        }
        for k, v in gates:
            L.append(f"- **{GATE_LABEL.get(k, k)}**：{v[:160]}")
        L.append("")
        L.append("⚠️ 以上为 ijob 已结构化字段，仍须与官方公告逐字对照后再写入正文。")
    else:
        L.append("⛔ ijob 未结构化该批次的红线字段 —— 必须回官方公告 §报考条件 逐条核"
                 "（年龄 / 英语等级 / 计算机证 / 体检色盲色弱 / 学信验证码），"
                 "缺则正文写「公告未披露」。")
    L.append("")

    # ── B. 缺口：这才是提示词真正需要的部分
    L.append("## B. ⛔ 缺口清单（必回官方补；**禁止推测、禁止用转载号数字**）")
    L.append("")
    gaps = []
    for key, (label, col, where) in REQUIRED.items():
        val = (row[col] or "").strip()
        g = grade_deadline(row) if col == "deadline" else grade(val)
        if g == "OK":
            continue
        gaps.append((label, where, "主档为空" if g == "EMPTY" else f"主档为软词「{val[:30]}」"))
    if not gaps:
        L.append(f"✅ {len(REQUIRED)} 项必填事实主档均已确定，可直接开写（仍建议抽查 2 项复核）。")
    else:
        L.append("| 缺什么 | 用在哪一段 | 现状 |")
        L.append("|---|---|---|")
        for label, where, why in gaps:
            L.append(f"| **{label}** | {where} | {why} |")
        L.append("")
        if grade_gates(row) != "OK":
            L.append("> ℹ️ 另有「资格与禁入红线」ijob 未结构化 —— **不阻塞动笔**，"
                     "但写「段5」前须回官方公告 §报考条件 逐条核。")
            L.append("")
    L.append("**补数红线**：")
    L.append("- ⛔ 培训号/聚合站的日期与人数一律不采（已实证 yinhangzhaopin.com 六大行日期 6/6 全错）")
    L.append("- ✅ 认官方公告原文、报名站接口、政府网附件 xlsx；补完**回填 `jobs.db`**，不要只写进稿件")
    L.append("- ✅ 官方没写的（薪酬/食宿/经费渠道/专业明细）→ 正文写「**公告未披露**」，不代为断言")
    L.append("")

    # ── C. 回官方补数的入口
    srcs = pick_sources(row)
    L.append("## C. 官方源（回补入口 / `--source-url` 候选项）")
    L.append("")
    if srcs:
        L.append("| 类型 | 地址 | 注记 |")
        L.append("|---|---|---|")
        for label, v in srcs:
            url, note = clean_url(v)
            L.append(f"| {label} | {url} | {note or '—'} |")
        L.append("")
        L.append("⚠️ 「网络报名」≠ 在线系统：须回公告 §报名办法 逐字核（09-17 无锡实证：实为邮箱投递、以收件时间为准）。")
        L.append("⚠️ `--source-url` 优先级：网申系统 > 报名邮箱所在公告页 > 官网栏目页。")
    else:
        L.append("⛔ ijob 无任何官方入口 —— 补数前先在 `campaigns` 补 `apply_url` / `announcement_url` 这两项。")
    L.append("")

    # ── D. 装配指令：机器算好的，别让模型猜
    L.append("## D. 装配指令（脚本已判定，不要再推理）")
    L.append("")
    dl = (row["deadline"] or "").strip()
    blocked = grade_deadline(row) != "OK"
    L.append(f"- **封面母版**：`{'标准社招封面母版.png' if line.upper() == 'B' else '标准校招封面母版.png'}`"
             f"（判据：线={line or '未标'}；面向 2027 届应届生=校招，面向社会/编制=社招）")
    L.append("- **主色**：⛔ 必须先跑 `logo 众数色` 取色，**严禁沿用上一篇色板**（09-17 南京银行误用江苏银行蓝）")
    if blocked:
        L.append(f"- ⛔ **暂不可动笔**：报名截止仍是软词「{dl or '空'}」，定不了标题钩子与 SEO 摘要。先回官方钉死，"
                 f"并把结果写回 `jobs.db` 的 `campaigns.deadline`。")
    else:
        L.append(f"- ✅ 报名截止已确定（{dl}），可动笔；三宫格、摘要、标题钩子用这个值。")
    L.append("")

    return "\n".join(L)


def fetch_rows(conn, keyword=None):
    cur = conn.cursor()
    cur.execute(SQL)
    cols = [d[0] for d in cur.description]
    rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    if keyword:
        kw = keyword.strip()
        rows = [r for r in rows if kw in " ".join(str(r.get(k) or "") for k in
                ("company", "full_name", "title", "city", "batch_type", "industry_catalog"))]
    rows.sort(key=lambda r: (r["deadline"] or "9999-12-31", r["cid"]))
    return rows


def main():
    ap = argparse.ArgumentParser(description="从 ijob jobs.db 生成写稿 BRIEFING")
    ap.add_argument("keywords", nargs="*", help="单位关键词，模糊匹配 公司名/标题/城市")
    ap.add_argument("--db", default=DEFAULT_DB, help="jobs.db 路径（默认 ijob 中枢）")
    ap.add_argument("--out", metavar="DIR", help="写到该目录（文件名=单位.md）；不传则打印到 stdout")
    ap.add_argument("--gap-only", action="store_true", help="只打印缺口一行式摘要")
    ap.add_argument("--ready", action="store_true",
                    help="列出必填事实已齐、**且尚未动笔**的单位（选题池；默认先与草稿箱对账）")
    ap.add_argument("--include-done", action="store_true",
                    help="配合 --ready：把已发布/已推草稿箱的也列出来（防止重复写）")
    ap.add_argument("--profile", default=DEFAULT_PROFILE,
                    help=f"公众号账号别名（默认 {DEFAULT_PROFILE}=码上职业）")
    ap.add_argument("--no-draftbox", dest="draftbox", action="store_false",
                    help="跳过草稿箱对账（⛔ 仅在明确知道登录态不可用时用；名单将不可直接采信）")
    ap.add_argument("--include-suspect", action="store_true",
                    help="把「疑似已在草稿箱」的单位并回主名单")
    ap.add_argument("--no-collapse", action="store_true",
                    help="--ready 不按网申入口合并明细行（默认合并：同入口=1 个写作单位）")
    ap.add_argument("--draftbox-audit", action="store_true",
                    help="只做草稿箱对账并逐条打印映射，不改名单")
    ap.set_defaults(draftbox=True)
    ap.add_argument("--limit", type=int, default=3, help="每个关键词最多匹配几条，默认3")
    a = ap.parse_args()

    if not os.path.exists(a.db):
        sys.exit(f"找不到主档：{a.db}\n用 --db <路径> 显式指定，或确认 ijob 中枢已就位。")

    conn = sqlite3.connect(f"file:{a.db}?mode=ro", uri=True)
    today = datetime.now().strftime("%Y-%m-%d %H:%M")
    all_rows = fetch_rows(conn)

    # ── 草稿箱对账（--ready / --draftbox-audit 共用）
    draft_titles = draft_brands = None
    if a.draftbox and (a.ready or a.draftbox_audit):
        draft_titles, _mids = fetch_draft_titles(a.profile)
        if draft_titles is None:
            print("⚠️ 草稿箱对账**跳过**：取不到草稿列表"
                  f"（脚本缺失 / profile={a.profile} 登录态失效 / 超时）。\n"
                  "   ⛔ 本脚本不自动登录 —— 先手动跑 "
                  "`wx_draft.py list --profile %s` 确认；"
                  "**此名单不可直接采信**。" % a.profile, file=sys.stderr)
        else:
            draft_brands = {b for b in (_cjk_brand(t) for t in draft_titles) if b}
            print(f"[draftbox] profile={a.profile} 取到 {len(draft_titles)} 篇草稿，"
                  f"提取 {len(draft_brands)} 个单位名主体，参与对账", file=sys.stderr)

    if a.draftbox_audit:
        if draft_titles is None:
            sys.exit("草稿箱对账失败，无法审计。先修复登录态再试。")
        matched, unmatched, desync = reconcile_draftbox(conn, draft_titles)
        print(f"# 草稿箱对账 · profile={a.profile} · {today}")
        print(f"# 草稿 {len(draft_titles)} 篇 → 命中 DB {len(matched)} ｜ 无对应 {len(unmatched)} "
              f"｜ ⛔ 失同步(草稿有/DB显示未排) {len(desync)}\n")
        print(f"{'草稿标题':<52} {'DB批次':<14} 稿件状态")
        print("-" * 104)
        for t, cid, name, st, how in matched:
            print(f"{t[:50]:<52} cid={cid:<10} {st}" + ("  ⛔失同步" if st == "未排" else ""))
        if unmatched:
            print(f"\n--- 无 DB 对应的草稿 {len(unmatched)} 篇（多为内容型稿件 / 单位尚未入库）---")
            for t in unmatched:
                print("  -", t)
        if desync:
            print(f"\n⛔ 失同步 {len(desync)} 条 —— 草稿箱已有稿但 DB 仍显示「未排」，"
                  "须回填 `campaign_articles.rendered_html` 并置 `campaigns.has_article=1`：")
            for cid, name, t in desync:
                print(f"  - cid={cid} {name} ← {t[:44]}")
        conn.close()
        return

    if a.ready:
        # ⚠️ 「硬信息齐」≠「还没写」。稿件进度由 ijob 推导
        # （wechat_url 非空=已发布；rendered_html 非空=已推草稿箱）。
        # 不过滤就会把写完的单位混进选题池，导致重复劳动。
        # 但渲染稿未回填时 DB 会误判「未排」→ 故再用草稿箱标题做一次对账。
        DONE = ("已发布", "已推草稿箱")
        ready, done, suspect = [], [], []
        for r in all_rows:
            if any((grade_deadline(r) if c == "deadline" else grade(r[c])) != "OK"
                   for _k, (_l, c, _w) in REQUIRED.items()):
                continue
            name = r["full_name"] or r["company"] or ""
            rec = (r["deadline"] or "", name, draft_state(r))
            if rec[2] in DONE:
                done.append(rec)
                continue
            hit = draft_hit(name, draft_brands) if draft_brands else None
            if hit:
                suspect.append(rec + (hit,))
            else:
                ready.append(rec + (norm_apply_url(r["apply_url"]),))
        ready.sort()
        done.sort()
        suspect.sort()
        if a.include_suspect:
            ready = sorted(ready + [s[:3] + ("",) for s in suspect])
            suspect = []
        print(f"必填 {len(REQUIRED)} 项已齐 **且尚未动笔** 的单位：{len(ready)} 条"
              f"（另有 {len(done)} 条已发布/已推草稿箱，用 --include-done 一并列出）"
              + (f"；{len(suspect)} 条疑似已在草稿箱已单列" if suspect else ""))
        for dl, name, ds, _u in ready:
            print(f"  {dl or '—':<12} {name:<40} 稿件={ds}")
        # ── 同网申入口合并：同一入口 = 1 个写作单位（如 60 家农商行法人共用一个 51job 专题）
        groups = {}
        for dl, name, ds, u in ready:
            if u:
                groups.setdefault((dl, u), []).append(name)
        big = {k: v for k, v in groups.items() if len(v) > 1}
        if big and not a.no_collapse:
            n_member = sum(len(v) for v in big.values())
            print(f"\nℹ️ 按网申入口合并：{len(big)} 个入口覆盖 {n_member} 条明细行 "
                  f"→ **实际只有 {len(big)} 个写作单位**（明细行共用同一入口/截止日，勿逐条开稿）：")
            for (dl, u), names in sorted(big.items()):
                print(f"  {dl or '—':<12} {u:<44} ×{len(names):<3} "
                      f"如：{names[0]}…{names[-1] if len(names) > 1 else ''}")
        if suspect:
            print(f"\n⚠️ 疑似**已在草稿箱**、但 DB 显示未排 —— 动笔前先核实"
                  f"（{len(suspect)} 条；确认已发就回填 rendered_html，"
                  f"确未发用 --include-suspect 并回主名单）：")
            for dl, name, _ds, hit in suspect:
                print(f"  {dl or '—':<12} {name:<40} ≈草稿「{hit}」")
        if a.include_done:
            print(f"\n--- 已完成（勿重复写）{len(done)} 条 ---")
            for dl, name, ds in done:
                print(f"  {dl or '—':<12} {name:<40} 稿件={ds}")
        conn.close()
        return

    if not a.keywords:
        ap.print_help()
        return

    if a.gap_only:
        print(f"{'单位':<40} {'缺':<6} 缺口")
        for kw in a.keywords:
            for r in fetch_rows(conn, kw)[: a.limit]:
                miss = []
                for _k, (lbl, c, _w) in REQUIRED.items():
                    if (grade_deadline(r) if c == "deadline" else grade(r[c])) != "OK":
                        miss.append(lbl)
                tail = "" if grade_gates(r) == "OK" else "  [红线未结构化]"
                print(f"{(r['full_name'] or r['company'])[:38]:<40} {len(miss):<6} "
                      + "、".join(miss) + tail)
        return

    for kw in a.keywords:
        hits = fetch_rows(conn, kw)
        if not hits:
            print(f"[miss] 主档无匹配：{kw}", file=sys.stderr)
            continue
        for r in hits[: a.limit]:
            txt = build_briefing(r, today)
            if a.out:
                os.makedirs(a.out, exist_ok=True)
                name = (r["full_name"] or r["company"] or "未命名").replace("/", "_")
                p = os.path.join(a.out, f"{name}-BRIEFING.md")
                open(p, "w", encoding="utf-8").write(txt)
                print(f"[ok] {p}  (批次 {r['cid']} · {draft_state(r)})", file=sys.stderr)
            else:
                print(txt)
                print("\n" + "=" * 70 + "\n")

    conn.close()


if __name__ == "__main__":
    main()
