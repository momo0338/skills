#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
emit_briefing.py —— 从「码上职业」本工作区数据源生成写稿用 BRIEFING（给 AI 的投料单）

为什么要有这个脚本
==================
写稿提示词最大的 token 浪费与最大的质量风险来自同一件事：
  让模型去「找」硬信息。
  - 省 token 的角度：找 = 多轮工具调用 + 正文回流，一次找不全要重找。
  - 质量的角度：找不到时模型会「合理补全」——这正是 09-18 紫金稿翻车的机理
    （非官方口径 60 名 / 11-02 截止被当成事实写进正文）。

所以把「确定性部分」从提示词里拿走：由脚本从**本工作区台账**搬字段 + 显式标出缺口，
模型只做「表达转换」，不做信息检索，也不被允许推测。

数据源（2026-09-30 起 —— 与本工作区「自闭环」口径对齐）
======================================================
**全部来自工作区自有事实源**（实现见同目录 `workspace_source.py`）：
  ① `单位与招聘信息总表.xlsx`：`招聘信息`（批次台账）+ `公司信息`（单位档案）
  ② `巡检记录/*监测.md`：最新巡检报告的在架分层（有效 / 长期 / 待核）
  ③ `内容状态.json`：「写没写过 / 推没推草稿箱 / 发没发」的**唯一真源**

⛔ **不依赖任何外部项目或外部数据库**（2026-09-29 朱总裁定）。
⚠️ 台账里的硬信息**一律只是线索**：人数/截止/岗位/学历仍须回**官方公告原文**逐条核。

用法
====
  # 按关键词出 briefing（打印到 stdout）
  python3 emit_briefing.py "国网江苏"

  # 写成本次写稿的投料单文件
  python3 emit_briefing.py "国网江苏" --out /tmp/briefings/

  # 多条一起（批量开稿前先看缺口全景）
  python3 emit_briefing.py "国网" "南瑞" --gap-only

  # 列出所有「硬信息已够、库内未成稿、草稿箱未命中候选」的单位（选题用）
  python3 emit_briefing.py --ready

  # 只对账、不改名单：逐条打印「草稿标题 → 候选批次 + 库内稿件状态」
  python3 emit_briefing.py --draftbox-audit

  # 换公众号账号对账（默认 mashang=码上职业）
  python3 emit_briefing.py --ready --profile mashang

  # 指定工作区根（默认 ~/codeup/obsidian/03-工作记录/码上职业，或 JOB_WORKSPACE）
  python3 emit_briefing.py --ready --workspace "/path/to/码上职业"

  # 内容状态文件（唯一真源）：初始化 / 四方对账 / 回填 / 单向回推总表
  python3 emit_briefing.py --state-init
  python3 emit_briefing.py --state-audit
  python3 emit_briefing.py --mark "国网江苏" --to written
  python3 emit_briefing.py --state-push-xlsx

字段可信度三档
==============
  OK     台账/状态文件里有确定值（含具体日期/具体人数）
  VAGUE  软词、哨兵日或历史「发布日 +30 天」占位 → 不得写进正文，必须回官方补
  EMPTY  为空

⛔ 补数口径：缺项一律**回官方公告原文核实**，核实结论写回 `内容状态.json` 的
facts 袋（`--mark … --facts`）或人工维护该文件；本脚本只读总表，不替你改总表。

草稿箱对账（2026-09-21 加）
==========================
`内容状态.json` 的 state（unwritten / written / draft / published）**只是本工作区自己记的
进度**，**不等于微信草稿箱里一定没有、更不等于线上一定没发**。所以 `--ready` 在给名单前
**强制与草稿箱对一次账**
（标题精确 → 稿件正文含标题 → 批次标题主体互含 → 单位主体相似 → 人工维护简称/全称别名候选）。
多批次歧义和后三级弱匹配都只生成人工核验候选，不会自动回填，也不会宣称确定失同步。
歧义时优先展示进度最可证实的批次（已发布 > 已推草稿箱 > 库内已成稿 > 库内未排），但仍排除全部可能批次。
对上的单位单独列进「⚠️ 草稿箱候选」区，`--include-suspect` 可在人工核实后并回主名单。

⛔ 登录态失效时**只降级告警、不自动登录**；
脚本取不到草稿列表会明确打印「对账跳过」，此时名单不可直接采信。
"""
import argparse
import json
import os
import re
import subprocess
import sys
from datetime import date, datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import workspace_source as wsrc  # noqa: E402  （同目录：本工作区数据源适配层）

# 草稿箱取数脚本（mp-publish 技能内，唯一权威位置）
DRAFT_SCRIPT = os.path.join(
    os.path.expanduser("~"), ".workbuddy/skills/mp-publish/scripts/wx_draft.py")
DEFAULT_PROFILE = "mashang"

# 占位截止日：台账历史导入曾把「尚未核实截止日」的批次统一写成该日期，
# 判定时必须结合 batch_type / title 的「待核」字样降级为 VAGUE，否则会把占位日当事实写进正文。
PLACEHOLDER_DEADLINE = "2026-12-31"

# 数据源错误类型由 workspace_source 提供（`wsrc.SourceError`）：
# 「找不到工作区 / 状态文件」必须显式报错，绝不降级成「没有批次」。

# ── 主档列 → briefing 字段 的映射（左=legacy 键, 右=(briefing键, 展示名)）
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
# key -> (展示名, legacy row 键, 出现在哪一段)
REQUIRED = {
    "unit":          ("单位全称",     "full_name",        "段4 单位来头"),
    "deadline":      ("报名截止",     "deadline",         "段3 宫格 / SEO摘要 / 钩子"),
    "edu":           ("学历要求",     "min_degree",       "段5 岗位表 / FAQ"),
    "employment":    ("用工性质",     "employment_nature","段4 解读四问①"),
    "target_class":  ("面向届别",     "target_graduates", "段6 条件"),
    "location":      ("工作地点",     "city",             "段5 岗位表"),
    "announce_date": ("公告发布日",   "publish_date",     "时效标注"),
}
# 「资格与禁入红线」= **建议项，不阻塞动笔**（本地台账默认不登记该组，
# 绝大多数批次为空，若纳入 REQUIRED 会把全部单位误判为「不可动笔」）。
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


def deadline_is_derived_placeholder(row):
    """识别历史导入的「发布日 + 30 天」占位日期。

    旧导入曾把无法核实的报名截止批量写成公告日后 30 天。仅靠日期格式无法
    区分真实截止与占位；生产库已有大量此类记录，因此写稿入口必须降级复核。
    """
    publish = (row["publish_date"] or "").strip()[:10]
    deadline = (row["deadline"] or "").strip()[:10]
    if not publish or not deadline:
        return False
    try:
        return (date.fromisoformat(deadline) - date.fromisoformat(publish)).days == 30
    except ValueError:
        return False


def grade_deadline(row):
    """截止日专判：明确待核词、哨兵日或发布日 +30 天占位均降级为 VAGUE。"""
    v = (row["deadline"] or "").strip()
    if not v:
        return "EMPTY"
    blob = f"{row['batch_type'] or ''}{row['title'] or ''}{row['verdict_summary'] or ''}"
    if "待核" in blob or "待官方公告" in blob or "未披露" in blob:
        return "VAGUE"
    if v == PLACEHOLDER_DEADLINE or deadline_is_derived_placeholder(row):
        return "VAGUE"
    return grade(v)


def grade_gates(row):
    """资格与禁入：任一红线非空 → OK；全空 → EMPTY"""
    got = [k for k in GATE_KEYS if (row[k] or "").strip()]
    return "OK" if got else "EMPTY"


def draft_state(row):
    """按可证实程度返回稿件状态；绝不把「本地有正文」推断成「已推微信草稿箱」。

    优先用 `内容状态.json` 的 state（unwritten / written / draft / published）；
    缺该字段时回退到「可发布链接 + 正文长度」自证。
    """
    state = (row.get("content_state") or "").strip()
    if state == "published":
        return "已发布"
    if state == "draft":
        return "已推草稿箱"
    if state == "written":
        return "库内已成稿"
    if state == "unwritten":
        return "库内未排"
    wechat = (row.get("wechat_url") or "").strip()
    if len(wechat) > 10:
        return "已发布"
    if (row.get("article_length") or row.get("html_len") or 0) > 50:
        return "库内已成稿"
    return "库内未排"


# ─────────────────────────────────────────────────────────────
# 本工作区数据源适配（2026-09-30 起：数据全部来自工作区内部，无外部项目依赖）
# ─────────────────────────────────────────────────────────────
def load_workspace(workspace=None):
    """定位工作区并载入批次台账 + 巡检在架条目。

    返回 ``(ws, state, rows, patrol_entries, patrol_reports)``。
    任何一步失败都抛 ``wsrc.SourceError`` —— **绝不返回空数据**，
    因为「取不到」被当成「没有可写单位」正是凭空写稿的起点。
    """
    ws = wsrc.discover_workspace(workspace)
    state = wsrc.load_state(ws)          # 缺状态文件 → 报错并提示 --state-init
    rows = wsrc.load_batches(ws, state)
    entries, reports = wsrc.load_patrol(ws)
    return ws, state, rows, entries, reports








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
    """从稿题粗提「单位名主体」，只用于对账候选。

    先去掉方括号前缀，再在年份、招聘动作词和标点前截断；返回最靠前的
    连续中文主体，避免把「智能网联算法落户江宁」这类后半段卖点当单位名。
    """
    t = re.sub(r"^[【\[][^】\]]*[】\]]", "", text or "").strip()
    t = re.split(
        r"20\d{2}|(?:校招|校园招聘|秋季|春季|秋招|春招|招聘|招考|招录|招募|直聘|报名)",
        t, maxsplit=1)[0]
    t = re.split(r"[：:！!，,。｜|—\-]", t, maxsplit=1)[0]
    t = re.sub(r"(?:全面|正式|已经|已)?(?:开启|启动)(?:招聘|招募)?$", "", t.strip())
    runs = re.findall(r"[\u4e00-\u9fa5]{2,}", t)
    return runs[0] if runs else ""


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


def _semantic_draft_brand(text):
    """粗提草稿标题里的单位主体，供 DB 对账兜底；只用于候选，不直接回填。"""
    b = _cjk_brand(text)
    if b:
        return b
    # 标题常在“单位·行业/子公司/地点”结构中，取最长的 2~24 字中文连续段。
    runs = re.findall(r"[\u4e00-\u9fa5·]{4,}", text or "")
    return max(runs, key=len).strip("·") if runs else ""


# 标题常用简称，台账里可能存的是全称；只作人工候选，不自动回填。
# 值为批次对象文本中必须同时出现的关键词组；不把“疾病预防控制中心/血液中心”
# 这类跨城市通用词放入别名表，避免把南京红十字血液中心误认成江苏省血液中心。
_SEMANTIC_ALIASES = {
    "华为南研所": (("华为技术有限公司", "南京研究所"),),
    "中移苏研": (("中移苏研",),),
    "南瑞集团": (("南瑞集团",),),
    "国药集团": (("国药集团",),),
    "中国融通集团": (("中国融通集团",),),
    "省沿海开发集团": (("沿海开发集团",),),
    "沿海开发集团": (("沿海开发集团",),),
    "润和软件": (("润和软件",),),
    "长安汽车": (("长安汽车", "南京研发中心"),),
    "东方电气集团": (("东方电气",),),
    # 精确长标题别名：草稿中的“所属8家事业单位”与批次主体“所属事业单位”不互含，
    # 不用通用词“卫健委”兜底，避免跨城市误配。
    "南京市卫健委所属8家事业单位": (("南京市卫健委所属事业单位",),),
}


def _semantic_alias_hits(text):
    """返回标题命中的别名及其关键词组，仅用于人工核验。"""
    nt = _norm(text)
    hits = []
    for alias, keyword_groups in _SEMANTIC_ALIASES.items():
        if _norm(alias) in nt:
            hits.extend((alias, group) for group in keyword_groups)
    return hits


def _match_strength(how):
    """草稿→批次匹配证据等级；数值越小，证据越强。"""
    if how.startswith("标题精确"):
        return 0
    if how.startswith("正文含标题") or how.startswith("正文多批次候选"):
        return 1
    if how.startswith("标题多批次候选"):
        return 2
    if how.startswith("标题主体包含") or how.startswith("标题主体多批次候选"):
        return 3
    if how.startswith("主体相似"):
        return 4
    if how.startswith("主体多批次候选"):
        return 5
    if how.startswith("别名候选"):
        return 6
    if how.startswith("别名多批次候选"):
        return 7
    return 99


def _is_candidate_match(how):
    return (how.startswith("正文多批次候选")
            or how.startswith("标题多批次候选")
            or how.startswith("标题主体")  # 含“标题主体多批次候选”
            or how.startswith("主体相似")
            or how.startswith("主体多批次候选")
            or how.startswith("别名候选")
            or how.startswith("别名多批次候选"))


def _is_ambiguous_match(how):
    return "多批次候选" in how


def _select_candidate(rows):
    """多批次歧义时优先展示进度最可证实的记录：已发布 > 库内成稿 > 未排。"""
    rank = {"已发布": 2, "库内已成稿": 1, "库内未排": 0}
    return min(rows, key=lambda x: (
        -rank.get(draft_state(x), 0),
        -(x.get("html_len") or 0),
        x["id"],
    ))


def match_marker(state, how):
    """审计行标记：候选不得同时显示为“确定失同步”。"""
    parts = []
    if state == "库内未排" and not _is_candidate_match(how):
        parts.append("⛔确定失同步")
    if _is_candidate_match(how):
        parts.append("⚠️仅候选")
    return "  " + "  ".join(parts) if parts else ""


def _match_candidate_cids(item):
    """从 how 字段提取歧义候选 ID；无歧义时只返回当前映射批次。"""
    how = item[4] or ""
    m = re.search(r"(?:^|:)(\d+(?:,\d+)*)$", how)
    if m:
        return [int(x) for x in m.group(1).split(",")]
    return [item[1]]


def _best_draft_matches(matched):
    """构建 campaign_id → 最强草稿证据；歧义候选排除所有可能批次。"""
    result = {}
    for item in matched:
        for cid in _match_candidate_cids(item):
            old = result.get(cid)
            if old is None or _match_strength(item[4]) < _match_strength(old[4]):
                result[cid] = item
    return result


def reconcile_draftbox(all_rows, titles):
    """对账草稿标题与本工作区台账批次。

    ``all_rows`` 是工作区适配出的 legacy row 列表（含 id / title /
    full_name / company / wechat_url / html_len / rh）。

    返回 ``(matched, unmatched, desync, semantic_matches)``。
    匹配顺序：标题精确 → 稿件正文含标题 → 批次标题主体互含 →
    单位主体与批次单位主体互含 → 人工维护的简称/全称别名。
    多批次命中与后两级兜底均显式标记为候选，只供人工核验，不会回填任何数据。
    """
    all_rows = [dict(r) for r in all_rows]
    for r in all_rows:
        r.setdefault("id", r.get("cid"))
        r.setdefault("html_len", r.get("article_length") or 0)
        r.setdefault("rh", "")
    by_title = {}
    for row in all_rows:
        by_title.setdefault(_norm(row["title"]), []).append(row)
    matched, unmatched, desync, semantic_matches = [], [], [], []
    # 精确/正文命中可视为确定映射；标题主体包含、主体相似、别名命中
    # 始终保留为“仅候选”，即使当前只命中一条，也必须人工核对公告和入口。
    for t in titles:
        nt = _norm(t)
        exact_rows = by_title.get(nt, [])
        # 同一标题对应多个历史批次时不能冒充“精确唯一命中”；继续走候选兜底，
        # 至少让报告显式暴露歧义，禁止误把某条旧批次当成确定映射。
        r = exact_rows[0] if len(exact_rows) == 1 else None
        how = "标题精确"
        if r is None:  # 兜底：正文包含该标题
            probe = nt[:18]
            cand = [x for x in all_rows if probe and x["html_len"] > 0 and probe in _norm(x["rh"])]
            if cand:
                r = _select_candidate(cand)
                how = "正文含标题"
                if len(cand) > 1:
                    how = f"正文多批次候选:{','.join(str(x['id']) for x in cand)}"
        if r is None and exact_rows:
            # 标题完全相同却对应多个历史批次：显式暴露歧义，不冒充精确命中。
            r = _select_candidate(exact_rows)
            how = f"标题多批次候选:{','.join(str(x['id']) for x in exact_rows)}"
        if r is None:
            # 先按批次标题与草稿标题的互相包含关系找候选，可覆盖
            # 「南京鼓楼医院」→「南京鼓楼医院中医科」「中国电科」→下属院所
            # 等主体前缀关系；同一品牌多条时仍显式标成多批次候选。
            title_candidates = []
            ntitle = _norm(t)
            for x in all_rows:
                nct = _norm(x["title"])
                if nct and (nct in ntitle or ntitle in nct):
                    title_candidates.append(x)
            if title_candidates:
                r = _select_candidate(title_candidates)
                how = "标题主体包含"
                if len(title_candidates) > 1:
                    how = f"标题主体多批次候选:{','.join(str(x['id']) for x in title_candidates)}"
        if r is None:
            brand = _semantic_draft_brand(t)
            if brand:
                candidates = []
                for x in all_rows:
                    unit = x["full_name"] or x["company"] or ""
                    hit = draft_hit(unit, {brand})
                    if hit:
                        candidates.append(x)
                if candidates:
                    # 多批次命中时全部列入歧义集合，交给人工确认是哪条公告。
                    r = _select_candidate(candidates)
                    how = f"主体相似:{brand}"
                    if len(candidates) > 1:
                        how = f"主体多批次候选:{','.join(str(x['id']) for x in candidates)}"
        if r is None:
            # 常见简称/全称不是互含关系时，命中人工维护的别名表；仍只生成候选。
            for alias, keywords in _semantic_alias_hits(t):
                cand = []
                for x in all_rows:
                    hay = " ".join((x["title"] or "", x["full_name"] or "", x["company"] or ""))
                    if all(_norm(k) in _norm(hay) for k in keywords):
                        cand.append(x)
                if cand:
                    r = _select_candidate(cand)
                    how = f"别名候选:{alias}"
                    if len(cand) > 1:
                        how = f"别名多批次候选:{','.join(str(x['id']) for x in cand)}"
                    break
        if r is None:
            unmatched.append(t)
            continue
        st = draft_state(r)
        item = (t, r["id"], r["full_name"] or r["company"], st, how)
        matched.append(item)
        if _is_candidate_match(how):
            semantic_matches.append(item)

    # 所有语义/别名候选都只是“草稿有稿、某批次未排”的提示，不自动宣称
    # 真失同步；这是审计层保守口径，真失同步由逐条人工确认后单独计数。
    for item in matched:
        if _is_candidate_match(item[4]):
            continue
        if item[3] == "库内未排":
            desync.append((item[1], item[2], item[0]))

    return matched, unmatched, desync, semantic_matches


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


def _patrol_lines(entries):
    """把巡检在架条目渲染成 Markdown 表格行（无命中返回空列表）。"""
    if not entries:
        return []
    out = ["| 状态 | 报名截止 | 标题 | 来源 | 报告 |", "|---|---|---|---|---|"]
    for e in entries:
        title = (e["title"] or "")[:52]
        link = f"[{title}]({e['url']})" if e.get("url") else title
        out.append(f"| {e['layer']} | {e['deadline'] or '—'} | {link} | "
                   f"{(e['source'] or '—')[:22]} | {e['report']} |")
    return out


def build_briefing(row, today, patrol=None):
    kname = (row["full_name"] or row["company"] or "").strip()
    line = (row["line"] or "").strip()
    L = []

    L.append(f"# BRIEFING · {kname}")
    L.append("")
    L.append(f"> 机器生成于 {today} ｜ 数据源：**本工作区台账**"
             f"（总表 `招聘信息` + `内容状态.json` + 巡检报告）｜ "
             f"**本文件不是核实结论，是核实起点**")
    L.append(f"> 批次ID `{row['cid']}` ｜ 稿件进度：**{draft_state(row)}**"
             + ("" if row.get("state_known")
                else "（⚠️ 状态文件缺该批次，进度取自总表旧列，建议先 `--state-audit`）"))
    L.append("")

    # ── A. 台账登记值（线索，不是结论）
    L.append("## A. 台账登记硬信息（⚠️ **只是线索**：写进正文前必须与官方公告逐字对照）")
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

    # ── A2. 资格与禁入红线（本地只在核过官方公告并回填后才有值）
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
        L.append("⚠️ 以上为本工作区已回填的红线字段，仍须与官方公告逐字对照后再写入正文。")
    else:
        L.append("⛔ 本工作区台账未登记该批次的红线字段 —— 必须回官方公告 §报考条件 逐条核"
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
        gaps.append((label, where,
                     "台账未登记" if g == "EMPTY" else f"台账为软词「{val[:30]}」"))
    if not gaps:
        L.append(f"✅ {len(REQUIRED)} 项必填事实在台账均已确定，可直接开写（仍建议抽查 2 项复核）。")
    else:
        L.append("| 缺什么 | 用在哪一段 | 现状 |")
        L.append("|---|---|---|")
        for label, where, why in gaps:
            L.append(f"| **{label}** | {where} | {why} |")
        L.append("")
        if grade_gates(row) != "OK":
            L.append("> ℹ️ 另有「资格与禁入红线」台账未登记 —— **不阻塞动笔**，"
                     "但写「段5」前须回官方公告 §报考条件 逐条核。")
            L.append("")
    L.append("**补数红线**：")
    L.append("- ⛔ 培训号/聚合站的日期与人数一律不采（已实证 yinhangzhaopin.com 六大行日期 6/6 全错）")
    L.append("- ✅ 认官方公告原文、报名站接口、政府网附件 xlsx；补完把结论**回写 `内容状态.json` "
             "的 facts 袋**（`--mark … --facts`），不要只写进稿件")
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
        L.append("⛔ 台账里该批次没有任何官方入口 —— 补数前先回单位官网/主管局公告栏"
                 "补齐网申入口与公告原文这两项，并回写台账。")
    L.append("")

    # ── C2. 巡检报告的在架条目（比台账更新，用于确认「今天还开着」）
    L.append("## C2. 巡检报告·在架条目（本工作区 `巡检记录/` 最新报告）")
    L.append("")
    if patrol:
        L.extend(_patrol_lines(patrol))
        L.append("")
        L.append("⚠️ 巡检报告的「有效/长期」是**抓取时点**的判断，发布与撤回都可能在抓取之后发生；"
                 "写稿前仍须打开公告原文确认仍在招。")
    else:
        L.append(f"（巡检报告里没匹配到「{kname}」的在架条目 —— 可能是台账登记的批次较新、"
                 "报告尚未覆盖，或该公告不在四条巡检线内。**这不等于没在招**，"
                 "以官方公告原文为准。）")
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
        L.append(f"- ⛔ **暂不可动笔**：报名截止为软词、空值、哨兵日或历史「发布日 +30 天」占位"
                 f"（当前值「{dl or '空'}」），定不了标题钩子与 SEO 摘要。先回官方钉死，"
                 f"并把结论**回写 `内容状态.json`**（`--mark \"{kname}\" --to written "
                 f"--facts deadline=YYYY-MM-DD`）。")
    else:
        L.append(f"- ✅ 报名截止已确定（{dl}），可动笔；三宫格、摘要、标题钩子用这个值。")
    L.append("")

    return "\n".join(L)


def filter_rows(all_rows, keyword=None):
    """按关键词模糊过滤批次，并按 (截止日, 批次ID) 稳定排序。"""
    rows = all_rows
    if keyword:
        kw = keyword.strip()
        rows = [r for r in rows if kw in " ".join(str(r.get(k) or "") for k in
                ("company", "full_name", "title", "city", "batch_type", "industry_catalog"))]
    return sorted(rows, key=lambda r: (r["deadline"] or "9999-12-31", r["cid"]))


def _print_state_audit(rep):
    """打印四方对账报告（只读）。"""
    print(f"# 内容状态对账 · {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"# 真源：{rep['state_file']}")
    print()
    print("## 一、五个数（口径不可混用）")
    sc = rep["state_counts"]
    print(f"- 状态文件在册批次：**{rep['batches_in_state']}**"
          f"（未排 {sc.get('unwritten', 0)} ｜ 已成稿 {sc.get('written', 0)}"
          f" ｜ 已推草稿箱 {sc.get('draft', 0)} ｜ 已发布 {sc.get('published', 0)}）")
    inv = rep["local_inventory"]
    print(f"- 本地库存（各线 `待发布/` 稿件数）：" + "、".join(f"{k.split('/')[0]} {v}" for k, v in inv.items()))
    arch = rep["local_archived"]
    total_arch = sum(arch.values())
    print(f"- 本地已归档（各线 `已发布/`）：**{total_arch}**"
          + ("　🔴 **这一档接近空 —— 红线 11「发布当天归档」事实上未执行**" if total_arch <= 2 else ""))
    print(f"- 总表在册批次：{rep['batches_in_xlsx']} 行（内容状态分布 {rep['xlsx_counts']}）")
    print()
    print("## 二、状态文件 ↔ 总表旧列")
    mm = rep["state_xlsx_mismatch"]
    print(f"- 两处不一致：**{len(mm)}** 行")
    for x in mm[:20]:
        print(f"  - {x['unit']} ｜ {x['title']} ｜ json={x['json']} xlsx={x['xlsx']}")
    if len(mm) > 20:
        print(f"  …另有 {len(mm) - 20} 行")
    miss = rep["xlsx_rows_missing_in_state"]
    print(f"- 总表有、状态文件没有：**{len(miss)}** 行"
          + ("（⛔ 状态文件是真源，缺行会让这些批次失去进度记录）" if miss else " ✅"))
    if miss:
        for x in miss[:10]:
            print(f"  - {x['unit']} ｜ {x['xlsx'] or '（空）'}")
        print("  → 修法：`--state-init --force` 重建，或 `--mark <单位> --to <状态>` 逐条补")
    print()
    print("## 三、已发布 ↔ 本地归档（红线 11）")
    na = rep["published_not_archived"]
    print(f"- 状态=published 但 `已发布/` 里找不到：**{len(na)}** 条")
    for u in na[:15]:
        print(f"  - {u}")
    if len(na) > 15:
        print(f"  …另有 {len(na) - 15} 条")
    print()
    print("> ⛔ 本报告只读，不改任何文件。要推进状态用 `--mark`；要回推总表用 `--state-push-xlsx`。")


def _apply_mark(workspace, keyword, to_state, facts_list, by):
    """把匹配关键词的批次状态推进到 ``to_state``，可同时回填 facts（KEY=VALUE）。"""
    facts = {}
    for kv in facts_list:
        if "=" not in kv:
            raise wsrc.SourceError("facts_invalid", f"--facts 需要 KEY=VALUE 形式：{kv}")
        k, v = kv.split("=", 1)
        facts[k.strip()] = v.strip()
    state = wsrc.load_state(workspace)
    rows = wsrc.load_batches(workspace, state)
    # 目标既可以是台账行，也可以是状态文件里已有的条目（各线目录补录的那批台账里没有），
    # 合并去重后再落状态，避免「同一单位在状态文件里出现两条」。
    targets = {}
    for r in rows:
        if keyword in " ".join(str(r.get(k) or "") for k in
                               ("company", "full_name", "title", "city")):
            targets[(r["full_name"] or r["company"], r["title"])] = True
    for v in state["batches"].values():
        if keyword in (v.get("unit") or "") or keyword in (v.get("title") or ""):
            targets[((v.get("unit") or ""), (v.get("title") or ""))] = True
    if not targets:  # 哪儿都没有 → 也允许直接建（本地留痕优先）
        rec = wsrc.set_batch_state(workspace, keyword, "", to_state, by=by,
                                   note="--mark 新建（台账与状态文件均无此批次）")
        print(f"[ok] 新建并置为 {to_state}：{keyword}")
        return 1
    for unit, title in sorted(targets):
        wsrc.set_batch_state(workspace, unit, title, to_state, by=by)
        if facts:
            st2 = wsrc.load_state(workspace)
            st2["batches"][wsrc.state_key(unit, title)].setdefault("facts", {}).update(facts)
            wsrc.save_state(workspace, st2)
        print(f"[ok] {unit} ｜ {(title or '（无标题）')[:36]} → {to_state}"
              + (f" ｜ facts+{','.join(facts)}" if facts else ""))
    return len(targets)


def main():
    ap = argparse.ArgumentParser(description="从「码上职业」本工作区数据源生成写稿 BRIEFING")
    ap.add_argument("keywords", nargs="*", help="单位关键词，模糊匹配 公司名/标题/城市")
    ap.add_argument("--out", metavar="DIR", help="写到该目录（文件名=单位.md）；不传则打印到 stdout")
    ap.add_argument("--gap-only", action="store_true", help="只打印缺口一行式摘要")
    ap.add_argument("--ready", action="store_true",
                    help="列出必填事实已齐、本地未成稿且草稿箱未命中候选的单位（选题池）")
    ap.add_argument("--ready-loose", action="store_true",
                    help="选题宽松档：只要求「单位/截止/地点/公告发布日」齐（本地台账没有"
                         "用工性质与面向届别两列）；仍⛔必须回官方原文补齐后再动笔")
    ap.add_argument("--include-done", action="store_true",
                    help="配合 --ready：把已发布/已成稿/已推草稿箱的也列出来（防止重复写）")
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
    ap.add_argument("--workspace", metavar="DIR",
                    help=f"工作区根（默认 {wsrc.DEFAULT_WORKSPACE}；也可用环境变量 {wsrc.WORKSPACE_ENV}）")
    ap.add_argument("--state-init", action="store_true",
                    help="从总表与各线目录初始化 `内容状态.json`（已存在则保留，配 --force 重建）")
    ap.add_argument("--state-audit", action="store_true",
                    help="四方对账：内容状态.json ↔ 总表两列 ↔ 各线 待发布/已发布 ↔ 台账登记")
    ap.add_argument("--state-push-xlsx", action="store_true",
                    help="把内容状态.json 单向回推总表两列（改 xlsx 前强制备份到 /tmp）")
    ap.add_argument("--mark", metavar="关键词", help="把匹配到的批次状态推进到 --to")
    ap.add_argument("--to", choices=list(wsrc.STATES), help="配合 --mark：目标状态")
    ap.add_argument("--facts", action="append", default=[], metavar="KEY=VALUE",
                    help="配合 --mark：回填已核实字段（可重复，如 --facts employment_nature=合同制）")
    ap.add_argument("--by", default="AI", help="配合 --mark：留痕人（默认 AI）")
    ap.add_argument("--force", action="store_true", help="配合 --state-init：重建状态文件")
    ap.add_argument("--state-import-draftbox", action="store_true",
                    help="把微信草稿箱里的标题导入状态文件（状态=draft）；默认只预演，配 --apply 才落盘")
    ap.add_argument("--apply", action="store_true",
                    help="配合 --state-import-draftbox：真的写状态文件（不加则 dry-run）")
    ap.set_defaults(draftbox=True)
    ap.add_argument("--limit", type=int, default=3, help="每个关键词最多匹配几条，默认3")
    a = ap.parse_args()

    today = datetime.now().strftime("%Y-%m-%d %H:%M")

    # ── 状态文件子命令（先于台账载入，因为它们的入口正是状态文件本身）
    try:
        if a.state_init:
            _ws = wsrc.discover_workspace(a.workspace)
            _state, info = wsrc.init_state(_ws, by=a.by, force=a.force)
            print(f"[ok] {info['action']}：{info['path']}")
            for k in ("seeded", "from_dirs", "batches"):
                if k in info:
                    print(f"     {k}: {info[k]}")
            print("接着跑 `--state-audit` 看四方对账，把与总表旧列的差异先消掉。")
            return
        if a.state_audit:
            _print_state_audit(wsrc.audit(wsrc.discover_workspace(a.workspace)))
            return
        if a.state_push_xlsx:
            res = wsrc.push_state_to_xlsx(wsrc.discover_workspace(a.workspace))
            print(f"[ok] 已回推总表：更新 {res['updated']} 行")
            if res.get("backup"):
                print(f"     备份 {res['backup']}\n     SHA-256 {res['sha256']}\n"
                      f"     回滚 {res['rollback']}")
            return
        if a.state_import_draftbox:
            _ws = wsrc.discover_workspace(a.workspace)
            titles, _mids = fetch_draft_titles(a.profile)
            if titles is None:
                sys.exit(f"⛔ 取不到草稿箱列表（脚本缺失 / profile={a.profile} 登录态失效 / 超时）；"
                         "先手动跑 `wx_draft.py list --profile mashang` 确认。")
            res = wsrc.import_draft_titles(_ws, titles, apply=a.apply, by=a.by)
            print(f"# 草稿箱导入预演 · profile={a.profile} · 草稿 {len(titles)} 篇"
                  + ("" if not a.apply else "（已落盘）"))
            print(f"# 与状态文件已匹配（跳过，不覆盖）：{len(res['skipped'])} 篇")
            print(f"# 状态文件缺登记、将补为 draft：{len(res['planned'])} 篇")
            for t in res["planned"]:
                print(f"  + {wsrc._unit_from_title(t)[:26]:<28} ← {t[:52]}")
            if not a.apply and res["planned"]:
                print("\n（预演结束，未写任何文件。确认无误后加 `--apply` 落盘。）")
            return
        if a.mark:
            if not a.to:
                sys.exit("⛔ --mark 必须同时给 --to（unwritten/written/draft/published）")
            n = _apply_mark(wsrc.discover_workspace(a.workspace), a.mark, a.to, a.facts, a.by)
            if not n:
                sys.exit(f"⛔ 台账与状态文件里都没有匹配「{a.mark}」的批次；"
                         "先 `--state-init` 或核对单位专名。")
            return
    except wsrc.SourceError as exc:
        detail = f"\n细节：{json.dumps(exc.details, ensure_ascii=False)}" if exc.details else ""
        sys.exit(f"⛔ 数据源失败 [{exc.code}]：{exc.message}{detail}")

    try:
        ws, state, all_rows, patrol_entries, patrol_reports = load_workspace(a.workspace)
    except wsrc.SourceError as exc:
        detail = ""
        if exc.details:
            detail = "\n细节：" + json.dumps(exc.details, ensure_ascii=False)
        sys.exit(f"⛔ 本地取数失败 [{exc.code}]：{exc.message}{detail}\n"
                 "   本次没有任何批次数据，**不得把失败当成「没有可写单位」**。"
                 "修好后重试（首次使用先跑 `--state-init`）。")
    del ws

    # ── 草稿箱对账（--ready / --draftbox-audit 共用）
    draft_titles = None
    draft_audit = None
    draft_matches = {}
    if a.draftbox and (a.ready or a.ready_loose or a.draftbox_audit):
        draft_titles, _mids = fetch_draft_titles(a.profile)
        if draft_titles is None:
            print("⚠️ 草稿箱对账**跳过**：取不到草稿列表"
                  f"（脚本缺失 / profile={a.profile} 登录态失效 / 超时）。\n"
                  "   ⛔ 本脚本不自动登录 —— 先手动跑 "
                  "`wx_draft.py list --profile %s` 确认；"
                  "**此名单不可直接采信**。" % a.profile, file=sys.stderr)
        else:
            draft_audit = reconcile_draftbox(all_rows, draft_titles)
            # 同一批次可能被多条相似标题命中；只保留证据最强的一条。
            draft_matches = _best_draft_matches(draft_audit[0])
            print(f"[draftbox] profile={a.profile} 取到 {len(draft_titles)} 篇草稿，"
                  f"形成 {len(draft_matches)} 个候选批次，参与对账", file=sys.stderr)

    if a.draftbox_audit:
        if draft_audit is None:
            sys.exit("草稿箱对账失败，无法审计。先修复登录态再试。")
        matched, unmatched, desync, semantic_matches = draft_audit
        desync_cids = {cid for cid, _name, _t in desync}
        desync_titles = {_norm(t) for _cid, _name, t in desync}
        candidate_items = semantic_matches
        candidate_cids = {cid for item in candidate_items for cid in _match_candidate_cids(item)}
        candidate_titles = {_norm(item[0]) for item in candidate_items}
        ambiguous_titles = {_norm(item[0]) for item in candidate_items
                            if _is_ambiguous_match(item[4])}
        print(f"# 草稿箱对账 · profile={a.profile} · {today}")
        print(f"# 草稿 {len(draft_titles)} 行 / {len(set(map(_norm, draft_titles)))} 个唯一标题"
              f" → 匹配候选 {len(matched)} 行 / {len({x[1] for x in matched})} 个批次"
              f" ｜ 无对应候选 {len(unmatched)} 行 / {len(set(map(_norm, unmatched)))} 个唯一标题"
              f" ｜ ⛔ 确定失同步 {len(desync)} 行 / {len(desync_titles)} 个唯一标题"
              f" / {len(desync_cids)} 个批次 ｜ 语义/别名候选 {len(candidate_items)} 行"
              f" / {len(candidate_titles)} 个唯一标题 / {len(candidate_cids)} 个候选批次"
              f"（其中多批次歧义 {len(ambiguous_titles)} 个标题）\n")
        print(f"{'草稿标题':<52} {'候选批次':<14} 稿件状态")
        print("-" * 104)
        for t, cid, name, st, how in matched:
            print(f"{t[:50]:<52} cid={cid:<10} {st}{match_marker(st, how)}")
        if unmatched:
            print(f"\n--- 无对应候选的草稿 {len(unmatched)} 篇（内容型稿件 / 单位尚未入库，或仍需人工映射）---")
            for t in unmatched:
                print("  -", t)
        if desync:
            print(f"\n⛔ 确定失同步 {len(desync)} 行"
                  f"（{len(desync_titles)} 个唯一草稿标题 / {len(desync_cids)} 个候选批次）"
                  " —— 人工核对公告/报名入口后，用 `--mark \"<单位>\" --to draft`"
                  "把 `内容状态.json` 推进到「已推草稿箱」；语义/别名候选不自动计入：")
            for cid, name, t in desync:
                print(f"  - cid={cid} {name} ← {t[:44]}")
        return

    if a.ready or a.ready_loose:
        # ⚠️ 「硬信息齐」≠「还没写」。稿件进度取自 `内容状态.json`（唯一真源）：
        # published=已发布；draft=已推草稿箱；written=库内已成稿；unwritten=库内未排。
        # 不过滤就会把成稿单位混进选题池；草稿箱标题只作人工核验候选。
        DONE = ("已发布", "已推草稿箱", "库内已成稿")
        # 严格档＝REQUIRED 全齐；宽松档＝只要本地台账真正持有的四项
        # （用工性质/面向届别本工作区台账没有列，永远进不了严格档）。
        LOOSE_KEYS = {"unit", "deadline", "location", "announce_date"}
        gate = [(_k, _l, c, _w) for _k, (_l, c, _w) in REQUIRED.items()
                if not a.ready_loose or _k in LOOSE_KEYS]
        today_s = datetime.now().strftime("%Y-%m-%d")
        expired = 0
        ready, done, suspect = [], [], []
        for r in all_rows:
            bad = False
            for _k, _l, c, _w in gate:
                if _k == "unit":
                    ok = bool((r["full_name"] or r["company"] or "").strip())
                elif c == "deadline":
                    ok = grade_deadline(r) == "OK"
                else:
                    ok = grade(r[c]) == "OK"
                if not ok:
                    bad = True
                    break
            if bad:
                continue
            dl10 = (r["deadline"] or "").strip()[:10]
            if re.match(r"\d{4}-\d{2}-\d{2}$", dl10) and dl10 < today_s:
                expired += 1          # 已过期≠选题池，必须剔除（本地台账含历史行）
                continue
            name = r["full_name"] or r["company"] or ""
            rec = (r["deadline"] or "", name, draft_state(r))
            if rec[2] in DONE:
                done.append(rec)
                continue
            item = draft_matches.get(r["cid"])
            if item is not None:
                suspect.append(rec + (item[0], item[4]))
            else:
                ready.append(rec + (norm_apply_url(r["apply_url"]),))
        ready.sort()
        done.sort()
        suspect.sort()
        if a.include_suspect:
            ready = sorted(ready + [s[:3] + ("",) for s in suspect])
            suspect = []
        trust_note = "" if draft_titles is not None else "（⚠️ 草稿箱取数失败，以下未排除线上草稿，不可直接采信）"
        mode = "宽松档（单位/截止/地点/公告日）" if a.ready_loose else f"严格档（必填 {len(gate)} 项全齐）"
        print(f"[{mode}] 本地未成稿且草稿箱未命中候选的单位：{len(ready)} 条"
              f"（已剔除报名截止已过期 {expired} 条；另有 {len(done)} 条已完成，`--include-done` 可列出）"
              + (f"；{len(suspect)} 条草稿箱候选已单列" if suspect else "")
              + trust_note)
        if a.ready_loose:
            print("⚠️ 宽松档只保证本地台账有的四项 —— **「用工性质」「面向届别」「学历」**"
                  "以及资格红线必须回官方公告原文补齐后再动笔（红线 2）。")
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
            print(f"\n⚠️ 草稿箱有对应候选、但本地状态显示未成稿 —— 先人工核实"
                  f"（{len(suspect)} 条；确认同一公告后用 `--mark \"<单位>\" --to draft`"
                  f"把状态推进到「已推草稿箱」；确未发再用 --include-suspect 并回主名单）：")
            for dl, name, _ds, draft_title, how in suspect:
                print(f"  {dl or '—':<12} {name:<40} 草稿「{draft_title[:30]}」 [{how}]")
        if a.include_done:
            print(f"\n--- 已完成（勿重复写）{len(done)} 条 ---")
            for dl, name, ds in done:
                print(f"  {dl or '—':<12} {name:<40} 稿件={ds}")
        return

    if not a.keywords:
        ap.print_help()
        return

    if a.gap_only:
        print(f"{'单位':<40} {'缺':<6} 缺口")
        for kw in a.keywords:
            for r in filter_rows(all_rows, kw)[: a.limit]:
                miss = []
                for _k, (lbl, c, _w) in REQUIRED.items():
                    if (grade_deadline(r) if c == "deadline" else grade(r[c])) != "OK":
                        miss.append(lbl)
                tail = "" if grade_gates(r) == "OK" else "  [红线未登记]"
                print(f"{(r['full_name'] or r['company'])[:38]:<40} {len(miss):<6} "
                      + "、".join(miss) + tail)
        return

    for kw in a.keywords:
        hits = filter_rows(all_rows, kw)
        patrol_hits = wsrc.patrol_for(kw, patrol_entries)
        if not hits:
            if patrol_hits:
                print(f"# 台账无「{kw}」批次，但**巡检报告有 {len(patrol_hits)} 条在架条目**"
                      f"（台账未登记 ≠ 没在招）：")
                print()
                for line in _patrol_lines(patrol_hits):
                    print(line)
                print()
                print("→ 打开公告原文确认仍在招 → 补台账（总表 `招聘信息` 新增一行）"
                      "→ 再跑本脚本出投料单。⛔ 不要跳过投料单直接写稿。")
                print()
                continue
            print(f"[miss] 本地台账与巡检报告都没有「{kw}」"
                  "（⛔ 疑似凭空写 —— 先确认该单位确在招，再补台账/核对单位专名，别跳过投料单）",
                  file=sys.stderr)
            continue
        for r in hits[: a.limit]:
            txt = build_briefing(r, today, patrol_hits)
            if a.out:
                os.makedirs(a.out, exist_ok=True)
                name = (r["full_name"] or r["company"] or "未命名").replace("/", "_")
                p = os.path.join(a.out, f"{name}-BRIEFING.md")
                open(p, "w", encoding="utf-8").write(txt)
                print(f"[ok] {p}  (批次 {r['cid']} · {draft_state(r)})", file=sys.stderr)
            else:
                print(txt)
                print("\n" + "=" * 70 + "\n")


if __name__ == "__main__":
    main()
