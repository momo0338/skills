#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""workspace_source —— 「码上职业」流水线 db 数据源适配层（v2 · 2026-11-04）

2026-11-04 朱总裁定：``单位与招聘信息总表.xlsx`` / ``内容状态.json`` /
``巡检记录/*监测.md`` 三套工作区自有事实源**全部废弃**，统一改读流水线 db：

  ① ``units`` + ``unit_sources``/``sources`` → 单位档案与招聘官网入口（原「公司信息」）
  ② ``announce_pool``                       → 在招公告批次台账（原「招聘信息」）
  ③ ``drafts`` ∪ ``articles``               → 写稿进度/判重唯一真源（原「内容状态.json」）
  ④ ``monitor_state`` / ``announce_pool``   → 在架公告分层（原巡检 md）

纪律::

  - **硬信息只认官方公告原文**：人数/截止/岗位/学历，db 字段一律只作线索；
    缺口保持空串由下游 grade() 判缺口，⛔ 不脑补、不把 db 反查值当已核实。
  - 找不到 db → **结构化报错**，绝不静默返回空数据（「找不到」≠「没有批次」）。
  - 状态**只读**：进度由 db 的 drafts/articles 维护，不再写任何本地状态文件；
    判真发表只认 articles.published_title，判草稿存活仍须回读微信草稿箱。

对外函数签名与 legacy row 键保持与 v1 兼容，emit_briefing.py 的数据结构无需改动。

命令行自检::

    python3 workspace_source.py --workspace <工作区> [--json]
    PIPELINE_DB=/path/to.db python3 workspace_source.py --json
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

# ── 真源：流水线数据库 ─────────────────────────────────────────
DB_ENV = "PIPELINE_DB"
DEFAULT_DB = "/Users/zhugx/src/mashangzhiye/data/内容流水线.db"

# 工作区根发现顺序：显式参数 → 环境变量 → 默认路径（只用于扫本地稿件目录）
WORKSPACE_ENV = "JOB_WORKSPACE"
DEFAULT_WORKSPACE = "~/codeup/obsidian/03-工作记录/码上职业"

# 单批载入上限：announce_pool 有 8000+ 行，投料单只取近期有效公告
MAX_BATCHES = 600
MAX_PATROL_ENTRIES = 400

# 四条内容线的稿件目录（本地库存审计用）
CONTENT_LINES = ("2027年校园招聘", "事业单位", "教育系统", "人生方向")
PIECE_SUFFIXES = ("-源稿.md", "-排版.html", "-封面.png")

# 状态机：unwritten(未写) → written(本地已成稿) → draft(已推草稿箱) → published(线上已发布)
STATES = ("unwritten", "written", "draft", "published")
STATE_LABEL = {
    "unwritten": "库内未排",
    "written": "库内已成稿",
    "draft": "已推草稿箱",
    "published": "已发布",
}

RECRUIT_TYPE_LABEL = {
    "campus": "校园招聘", "social": "社会招聘", "general": "公开招聘",
}
DB_LINE_TO_CONTENT = {
    "school": "教育系统", "hospital": "事业单位", "gov": "事业单位",
    "enterprise": "2027年校园招聘", "soe": "2027年校园招聘",
    "bank": "2027年校园招聘", "power": "2027年校园招聘", "rail": "2027年校园招聘",
    "trust": "2027年校园招聘", "insurance": "2027年校园招聘",
    "fund": "2027年校园招聘", "futures": "2027年校园招聘",
    "securities": "2027年校园招聘", "tobacco": "2027年校园招聘",
    "other": "2027年校园招聘",
}
DB_LINE_TO_PATROL = {
    "gov": "机关单位", "power": "电力电网", "rail": "铁路", "bank": "银行",
    "school": "教育系统", "hospital": "事业单位",
}

# legacy row 全键（缺项一律空串，下游 grade() 负责判缺口）
LEGACY_KEYS = (
    "company", "full_name", "nature", "industry_catalog", "headquarters_city",
    "official_site", "recruit_site", "title", "batch_type", "line",
    "target_graduates", "min_degree", "total_vacancies", "employment_nature",
    "city", "publish_date", "deadline", "status", "verdict_summary",
    "apply_url", "announcement_url", "consulting_phone", "wechat_url",
    "age_limit", "cet_requirement", "computer_cert_requirement",
    "chsi_valid_date", "medical_veto_rules", "allocation_rules",
    "pitfall_warnings", "remarks",
)
FACT_KEYS = (
    "full_name", "line", "target_graduates", "employment_nature",
    "wechat_url", "verdict_summary", "chsi_valid_date",
    "medical_veto_rules", "allocation_rules", "pitfall_warnings",
)


class SourceError(RuntimeError):
    """流水线 db 不可用 / 结构不合法 / 调用失败。

    必须显式报错，**绝不降级成「空数据」** —— 否则「本地没查到」会被误当成
    「没有可写单位」，正是凭空写稿的起点。
    """

    def __init__(self, code, message, *, details=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


def _now():
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def _txt(v):
    if v is None:
        return ""
    s = str(v).strip()
    return "" if s.lower() in ("none", "nan") else s


# ─────────────────────────────────────────────────────────────
# db 连接（只读）
# ─────────────────────────────────────────────────────────────
def db_path(explicit=None):
    """定位流水线 db；显式值/环境变量是硬约束（校验不过即报错，不回退）。"""
    p = Path(explicit or os.environ.get(DB_ENV) or DEFAULT_DB).expanduser()
    if not p.is_file():
        raise SourceError(
            "db_not_found", f"流水线数据库不存在：{p}",
            details={"hint": f"用 {DB_ENV} 指定 db 路径；默认 {DEFAULT_DB}"})
    return p


def _connect(path=None):
    p = path or db_path()
    try:
        conn = sqlite3.connect("file:" + quote(str(p)) + "?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        conn.execute("select 1 from units limit 1")
        return conn
    except sqlite3.Error as exc:
        raise SourceError("db_unreadable", f"流水线 db 打不开或缺关键表：{p}（{exc}）",
                          details={"path": str(p)}) from exc


def _table_cols(conn, table):
    return {r[1] for r in conn.execute(f"pragma table_info({table})")}


# ─────────────────────────────────────────────────────────────
# 工作区发现（只用于定位本地稿件目录，不再是事实源）
# ─────────────────────────────────────────────────────────────
def discover_workspace(explicit=None):
    """定位工作区根并校验 db 可用；显式值与环境变量是硬约束。"""
    db_path()
    if explicit:
        p = Path(explicit).expanduser()
        if not p.is_dir():
            raise SourceError("workspace_invalid", f"指定工作区目录不存在：{p}",
                              details={"hint": "传工作区根目录（用于扫描各线稿件目录）"})
        return p
    env = os.environ.get(WORKSPACE_ENV)
    if env:
        p = Path(env).expanduser()
        if not p.is_dir():
            raise SourceError("workspace_invalid",
                              f"{WORKSPACE_ENV} 指向的工作区目录不存在：{p}",
                              details={"hint": f"修正或清空 {WORKSPACE_ENV}"})
        return p
    p = Path(DEFAULT_WORKSPACE).expanduser()
    if p.is_dir():
        return p
    raise SourceError("workspace_not_found",
                      f"未能定位「码上职业」工作区（默认位置：{p}）",
                      details={"checked": [str(p)],
                               "hint": f"用 --workspace 指定，或设置 {WORKSPACE_ENV}"})


# ─────────────────────────────────────────────────────────────
# 状态视图（drafts ∪ articles，只读）
# ─────────────────────────────────────────────────────────────
def state_key(unit, title):
    """批次稳定键：单位专名 + 招聘标题（标题缺失时退化用单位名）。"""
    return f"{(unit or '').strip()}||{(title or '').strip()}"


_PUNCT_RE = re.compile(r"[\s\u3000【】\[\]（）()「」『』：:，,。.、！!？?｜|—\-·]+")


def _nm(s):
    return _PUNCT_RE.sub("", (s or "")).lower()


def _unit_from_title(title):
    """从草稿标题里截出可读的单位名（用于人工核对，不追求精确）。"""
    t = re.sub(r"^[【\[][^】\]]*[】\]]", "", (title or "").strip())
    for sep in ("：", ":", "！", "!", "，", ",", "｜", "|", "（", "("):
        if sep in t:
            t = t.split(sep)[0]
            break
    return t[:28] or (title or "")[:28]


def _url_unit_index(conn):
    """url → 发布单位（用 units.name 优先，退化到 pub_unit）。"""
    idx = {}
    try:
        rows = conn.execute(
            "select ap.url, coalesce(u.name, ap.pub_unit, ap.pub_unit_src, '') as unit "
            "from announce_pool ap left join units u on u.id = ap.target_unit_id "
            "where ap.url is not null and ap.url != ''")
        for r in rows:
            idx.setdefault(r["url"], _txt(r["unit"]))
    except sqlite3.Error:
        pass
    return idx


def load_state(workspace, *, required=True):
    """从 db 的 ``drafts`` ∪ ``articles`` 合成只读状态视图。

    返回结构与 v1 的 ``内容状态.json`` 一致（``batches`` 字典），但**不落盘**：
    判真发表只认 articles.published_title，drafts 仅表示「曾推过草稿」。

    ``required`` 保留参数以兼容旧调用；db 不可用时一律报错，不返回空视图。
    """
    conn = _connect()
    try:
        url_unit = _url_unit_index(conn)
        batches = {}

        def _put(title, url, state, note, media_id=""):
            title = _txt(title)
            url = _txt(url)
            unit = url_unit.get(url) or _unit_from_title(title)
            key = state_key(unit, title)
            rec = {
                "unit": unit, "title": title, "state": state,
                "history": [{"at": _now(), "from": "", "to": state, "by": "db", "note": note}],
                "facts": {}, "files": {}, "notes": note,
                "source_url": url, "media_id": media_id,
            }
            prev = batches.get(key)
            if prev is None or (prev["state"] != "published" and state == "published"):
                batches[key] = rec

        # 真发表：articles（published_title 为准）
        for r in conn.execute(
                "select published_title, source_url, published_at from articles "
                "where coalesce(is_deleted,'0') in ('0',0) and published_title is not null"):
            _put(r["published_title"], r["source_url"], "published",
                 "已发表（articles.published_title）")
        # 已推草稿：drafts（不覆盖 published）
        for r in conn.execute(
                "select title, source_url, media_id from drafts where title is not null"):
            _put(r["title"], r["source_url"], "draft",
                 "db 台账记录：曾推草稿箱；判活须回读微信草稿箱",
                 _txt(r["media_id"]))
        return {
            "schema_version": "2.0.0",
            "updated_at": _now(),
            "authority": (f"流水线 db {db_path()} 的 drafts ∪ articles；"
                          "只读视图，状态不再写本地文件"),
            "states": list(STATES),
            "batches": batches,
        }
    finally:
        conn.close()


def save_state(workspace, state):
    """⛔ 已废弃：状态由 db 维护，禁止写本地状态文件。"""
    raise SourceError("state_readonly",
                      "状态只读：进度由流水线 db 的 drafts/articles 维护，不再写 内容状态.json",
                      details={"db": str(db_path())})


def set_batch_state(workspace, unit, title, to_state, *, by="AI", note="", files=None):
    """⛔ 已废弃：--mark 不再支持，状态以 db 为准。"""
    raise SourceError("state_readonly",
                      "状态只读：--mark 已停用，写稿进度以流水线 db 的 drafts/articles 为准",
                      details={"db": str(db_path())})


def init_state(workspace, *, by="AI", force=False):
    """⛔ 不再需要初始化：状态是 db 的只读视图。保留接口以兼容 CLI。"""
    state = load_state(workspace)
    return state, {"action": "db_managed", "authority": str(db_path()),
                   "batches": len(state["batches"]),
                   "note": "状态由 db 托管，无需生成 内容状态.json"}


def import_draft_titles(workspace, titles, *, apply=False, by="AI"):
    """只读预演：把草稿箱标题与 db 状态比对（不再落盘）。"""
    state = load_state(workspace)
    existing = list(state["batches"].values())
    planned, skipped = [], []
    for t in titles:
        nt = _nm(t)
        hit = None
        for v in existing:
            probe = _nm(v.get("title") or "") or _nm(v.get("unit") or "")
            unit = _nm(v.get("unit") or "")
            if not probe:
                continue
            if (probe in nt or nt[:18] in probe) or (len(unit) >= 4 and unit in nt):
                hit = v
                break
        (skipped if hit else planned).append(
            (t, hit.get("unit"), hit.get("state")) if hit else t)
    if apply:
        raise SourceError("state_readonly",
                          "状态只读：--apply 已停用，草稿箱进度由 db 的 drafts 表记录",
                          details={"db": str(db_path())})
    return {"planned": planned, "skipped": skipped, "applied": 0,
            "note": "只读预演：状态真源＝流水线 db，不会写入任何本地文件"}


# ─────────────────────────────────────────────────────────────
# 单位档案 / 批次台账（units + announce_pool）
# ─────────────────────────────────────────────────────────────
def load_companies(workspace):
    """``units`` → {名称: {legacy 键: 值}}。"""
    conn = _connect()
    try:
        out = {}
        for r in conn.execute(
                "select name, full_name, nature, city, website, recruit_site, industry "
                "from units where coalesce(deleted,'0') in ('0',0) and name is not null"):
            name = _txt(r["name"])
            if not name:
                continue
            out[name] = {
                "full_name": _txt(r["full_name"]),
                "nature": _txt(r["nature"]),
                "headquarters_city": _txt(r["city"]),
                "official_site": _txt(r["website"]),
                "recruit_site": _txt(r["recruit_site"]),
                "industry_catalog": _txt(r["industry"]),
            }
        return out
    finally:
        conn.close()


def _batch_sql(conn):
    cols = _table_cols(conn, "announce_pool")
    dup_guard = "coalesce(ap.dup_of,'')=''" if "dup_of" in cols else "1=1"
    status_col = "coalesce(ap.status,0)" if "status" in cols else "1"
    return (
        "select ap.id, ap.url, ap.title, ap.pub_date, ap.end_date, ap.pub_unit, "
        "ap.pub_unit_src, ap.line, ap.recruit_type, ap.recruit_site, ap.fetched_at, "
        "u.name as unit_name, u.full_name, u.nature, u.city as unit_city, "
        "u.website, u.recruit_site as unit_recruit_site, u.industry "
        "from announce_pool ap left join units u on u.id = ap.target_unit_id "
        f"where {status_col}=1 and {dup_guard} "
        "order by coalesce(ap.pub_date, substr(ap.fetched_at,1,10)) desc, ap.id desc "
        "limit ?")


def load_batches(workspace, state):
    """``announce_pool`` 有效公告 + ``units`` 档案 → legacy row 列表。

    硬信息（人数/学历/电话等）db 里没有可靠字段，一律留空，
    由官方公告原文核实后回填 —— ⛔ 不用 db 反查值冒充已核实。
    """
    conn = _connect()
    try:
        rows = list(conn.execute(_batch_sql(conn), (MAX_BATCHES,)))
    finally:
        conn.close()

    batches = state.get("batches", {}) if state else {}
    by_url = {_txt(rec.get("source_url")): rec
              for rec in batches.values() if _txt(rec.get("source_url"))}
    out = []
    for r in rows:
        row = {k: "" for k in LEGACY_KEYS}
        company = _txt(r["unit_name"]) or _txt(r["pub_unit"]) or _txt(r["pub_unit_src"])
        title = _txt(r["title"])
        row.update({
            "company": company,
            "title": title,
            "batch_type": RECRUIT_TYPE_LABEL.get(_txt(r["recruit_type"]), ""),
            "line": DB_LINE_TO_CONTENT.get(_txt(r["line"]), "2027年校园招聘"),
            "city": _txt(r["unit_city"]),
            "publish_date": _txt(r["pub_date"]),
            "deadline": _txt(r["end_date"]),
            "apply_url": _txt(r["url"]),
            "announcement_url": _txt(r["url"]),
            "full_name": _txt(r["full_name"]),
            "nature": _txt(r["nature"]),
            "industry_catalog": _txt(r["industry"]),
            "headquarters_city": _txt(r["unit_city"]),
            "official_site": _txt(r["website"]),
            "recruit_site": _txt(r["unit_recruit_site"]) or _txt(r["recruit_site"]),
        })
        url = _txt(r["url"])
        key = state_key(company, title)
        rec = (by_url.get(url) or batches.get(key)
               or batches.get(state_key(company, "")) or {})
        content_state = _txt(rec.get("state")) or "unwritten"
        row["status"] = content_state
        row["content_state"] = content_state
        row["db_content_state"] = content_state
        row["db_published"] = "是" if content_state == "published" else "否"
        row["state_key"] = key
        row["state_known"] = bool(rec)
        facts = rec.get("facts") or {}
        for k in FACT_KEYS:
            v = _txt(facts.get(k))
            if v and not row.get(k):
                row[k] = v
        row["cid"] = int(r["id"])
        row["id"] = int(r["id"])
        row["source_url"] = url
        row["rh"] = ""
        row["article_length"] = 0
        row["html_len"] = 0
        out.append(row)
    return out


# ─────────────────────────────────────────────────────────────
# 在架公告（announce_pool + monitor_state，替代巡检 md）
# ─────────────────────────────────────────────────────────────
_LAYER_RANK = {"有效": 0, "长期": 1, "待核": 2}


def _layer_of(end_date):
    d = _txt(end_date)
    if not d:
        return "长期"
    today = datetime.now().strftime("%Y-%m-%d")
    return "有效" if d[:10] >= today else "待核"


def _patrol_rank(e):
    """排序键：先按分层（有效 > 长期 > 待核），再取最新报告优先。"""
    try:
        stamp = -int((e.get("report") or "")[:10].replace("-", ""))
    except ValueError:
        stamp = 0
    return (_LAYER_RANK.get(e["layer"], 9), stamp, e.get("deadline") or "9999")


def load_patrol(workspace, max_reports=12):
    """从 db 读近期在架公告；返回 (entries, reports)，结构与巡检 md 版一致。"""
    conn = _connect()
    try:
        cols = _table_cols(conn, "announce_pool")
        dup_guard = "coalesce(ap.dup_of,'')=''" if "dup_of" in cols else "1=1"
        status_col = "coalesce(ap.status,0)" if "status" in cols else "1"
        src_join = ("left join sources s on s.id = ap.source_id"
                    if "source_id" in cols else "")
        src_col = "s.name" if src_join else "''"
        q = (f"select ap.title, ap.url, ap.pub_date, ap.end_date, ap.pub_unit, "
             f"ap.line, ap.fetched_at, {src_col} as source_name "
             f"from announce_pool ap {src_join} "
             f"where {status_col}=1 and {dup_guard} "
             "order by coalesce(ap.pub_date, substr(ap.fetched_at,1,10)) desc "
             "limit ?")
        entries = []
        for r in conn.execute(q, (MAX_PATROL_ENTRIES,)):
            stamp = (_txt(r["fetched_at"]) or _txt(r["pub_date"]) or _now())[:10]
            entries.append({
                "unit": _txt(r["pub_unit"]),
                "date": _txt(r["pub_date"]),
                "deadline": _txt(r["end_date"]) or "—",
                "layer": _layer_of(r["end_date"]),
                "source": _txt(r["source_name"]),
                "title": _txt(r["title"]),
                "url": _txt(r["url"]),
                "report": f"{stamp}-db",
                "patrol_line": DB_LINE_TO_PATROL.get(_txt(r["line"]), "其他"),
            })
        reports = sorted({e["report"] for e in entries}, reverse=True)[:max_reports]
        return entries, reports
    finally:
        conn.close()


def patrol_for(text, entries, limit=8):
    """按单位专名/关键词在在架条目里查公告（含标题或来源命中），按 url|title 去重。"""
    kw = (text or "").strip()
    if not kw:
        return []
    best = {}
    for e in entries:
        if not (kw in e["unit"] or kw in e["title"] or kw in e["source"]):
            continue
        key = e.get("url") or e.get("title")
        cur = best.get(key)
        if cur is None or _patrol_rank(e) < _patrol_rank(cur):
            best[key] = e
    return sorted(best.values(), key=_patrol_rank)[:limit]


# ─────────────────────────────────────────────────────────────
# 本地稿件目录（只做库存审计，不是事实源）
# ─────────────────────────────────────────────────────────────
def _scan_pieces(workspace):
    """扫各线 待发布/已发布 目录 → {目录: set(稿件前缀)}。"""
    out = {}
    for line in CONTENT_LINES:
        for sub in ("待发布", "已发布"):
            d = Path(workspace) / line / sub
            names = set()
            if d.is_dir():
                for p in d.iterdir():
                    if p.is_file():
                        for suf in PIECE_SUFFIXES:
                            if p.name.endswith(suf):
                                names.add(p.name[: -len(suf)])
            out[f"{line}/{sub}"] = names
    return out


def audit(workspace, state=None, rows=None):
    """db 对账：drafts/articles 进度 ↔ announce_pool 有效批次 ↔ 各线稿件目录。只读。"""
    state = state or load_state(workspace)
    rows = rows if rows is not None else load_batches(workspace, state)
    pieces = _scan_pieces(workspace)
    json_c = Counter((r.get("state") or "unwritten") for r in state["batches"].values())
    db_c = Counter(r["content_state"] for r in rows)
    mismatch, missing_in_state = [], []
    for r in rows:
        if not r["state_known"]:
            missing_in_state.append({"unit": r["company"], "title": r["title"],
                                     "db": r["db_content_state"]})
            continue
        if r["content_state"] != r["db_content_state"]:
            mismatch.append({"unit": r["company"], "title": r["title"][:40],
                             "progress": r["content_state"], "db": r["db_content_state"]})
    published = [v for v in state["batches"].values() if v.get("state") == "published"]
    archived = set()
    for k, v in pieces.items():
        if k.endswith("已发布"):
            archived |= v
    not_archived = []
    for v in published:
        unit = (v.get("unit") or "").strip()
        if unit and not any(unit in a for a in archived):
            not_archived.append(unit)
    return {
        "authority_db": str(db_path()),
        "state_counts": dict(json_c),
        "db_counts": dict(db_c),
        "batches_in_state": len(state["batches"]),
        "batches_in_db": len(rows),
        "state_db_mismatch": mismatch,
        "db_rows_missing_in_state": missing_in_state,
        "local_inventory": {k: len(v) for k, v in pieces.items() if k.endswith("待发布")},
        "local_archived": {k: len(v) for k, v in pieces.items() if k.endswith("已发布")},
        "published_not_archived": not_archived,
    }


def push_state_to_xlsx(workspace, state=None, *, backup=True):
    """⛔ 已停用：总表 xlsx 于 2026-11-04 废弃，不再回推。"""
    raise SourceError("xlsx_retired",
                      "总表回推已停用：单位与招聘信息总表.xlsx 已完全废弃，状态由流水线 db 维护",
                      details={"db": str(db_path())})


# ─────────────────────────────────────────────────────────────
# 自检
# ─────────────────────────────────────────────────────────────
def _db_counts():
    conn = _connect()
    try:
        def n(q):
            try:
                return conn.execute(q).fetchone()[0]
            except sqlite3.Error:
                return 0
        return {
            "units": n("select count(*) from units"),
            "announce_pool": n("select count(*) from announce_pool"),
            "drafts": n("select count(*) from drafts"),
            "articles": n("select count(*) from articles"),
        }
    finally:
        conn.close()


def _selftest(workspace):
    state = load_state(workspace)
    rows = load_batches(workspace, state)
    entries, reports = load_patrol(workspace)
    print(f"真源 db: {db_path()}")
    print(f"工作区（仅扫本地稿件）: {workspace}")
    print(f"db 计数: {_db_counts()}")
    print(f"状态视图: {len(state['batches'])} 个已推/已发批次")
    print(f"公告池有效批次（载入 {len(rows)} 行）")
    print(f"在架条目: {len(entries)} ｜ 报告档: {len(reports)} 份")
    print("最近报告:", ", ".join(reports[:4]))
    return 0


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description="码上职业流水线 db 数据源自检")
    ap.add_argument("--workspace", help=f"工作区根（默认 {DEFAULT_WORKSPACE}）")
    ap.add_argument("--json", action="store_true", help="以 JSON 输出")
    a = ap.parse_args(argv)
    try:
        ws = discover_workspace(a.workspace)
        state = load_state(ws)
        entries, reports = load_patrol(ws)
        if a.json:
            print(json.dumps({"workspace": str(ws), "authority_db": str(db_path()),
                              "db_counts": _db_counts(),
                              "batches_in_state": len(state["batches"]),
                              "batches_loaded": len(load_batches(ws, state)),
                              "patrol_reports": reports,
                              "patrol_entries": len(entries)},
                             ensure_ascii=False, indent=2))
            return 0
        return _selftest(ws)
    except SourceError as exc:
        detail = f"\n细节：{json.dumps(exc.details, ensure_ascii=False)}" if exc.details else ""
        print(f"⛔ 数据源失败 [{exc.code}]：{exc.message}{detail}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
