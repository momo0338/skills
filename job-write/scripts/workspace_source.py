#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""workspace_source —— 「码上职业」本工作区数据源适配层

本模块取代原先的「外部数据中枢只读契约」适配层（2026-09-30 朱总裁定：
job-write 不再依赖任何外部项目或外部数据库，实现里不出现其名称与路径）。
投料单的输入改为**工作区自有**的三个事实源：

  ① ``单位与招聘信息总表.xlsx``
       - ``招聘信息`` sheet = 在招批次台账（19 列，一行 = 一个批次）
       - ``公司信息`` sheet = 单位档案（全称/性质/城市/官网/行业）
  ② ``巡检记录/*监测.md``    各线最新巡检报告（在架公告分层：有效 / 长期 / 待核 / 已过期）
  ③ ``内容状态.json``        「写没写过 / 推没推草稿箱 / 发没发 / 归档在哪」的**唯一真源**

纪律（沿用被取代那套适配层的硬约束）::

  - 找不到工作区、找不到状态文件 → **结构化报错**，绝不静默返回空数据，
    因为「找不到」和「没有批次」是两回事，混同会直接导致凭空写稿。
  - 台账里的硬信息（人数/截止/学历…）**一律只是线索**，硬信息以官方公告原文为准。
  - 状态文件写入走「一次读一次写 + 原子替换」，避免并发冲刷（工作区共享文件纪律）。

命令行自检::

    python3 workspace_source.py --workspace <工作区> [--json]
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
from collections import Counter
from datetime import datetime
from pathlib import Path

# ── 工作区固定文件名 ──────────────────────────────────────────────
TOTAL_XLSX = "单位与招聘信息总表.xlsx"
STATE_JSON = "内容状态.json"
PATROL_DIR = "巡检记录"
SHEET_BATCHES = "招聘信息"
SHEET_COMPANIES = "公司信息"

# 工作区根发现顺序：显式参数 → 环境变量 → 默认路径
WORKSPACE_ENV = "JOB_WORKSPACE"
DEFAULT_WORKSPACE = "~/codeup/obsidian/03-工作记录/码上职业"

# 四条内容线的稿件目录（审计用）
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
# 内容状态.json → 总表 `招聘信息` 两列的反向映射（总表无 draft 档，draft 记 written 且未发布）
STATE_TO_XLSX = {
    "unwritten": ("unwritten", "否"),
    "written": ("written", "否"),
    "draft": ("written", "否"),
    "published": ("published", "是"),
}

# `招聘信息` 列名 → legacy row 键
BATCH_COLUMNS = {
    "单位名称": "company",
    "招聘类别": "batch_type",
    "招聘标题": "title",
    "地区": "city",
    "发布日期": "publish_date",
    "截止日期": "deadline",
    "网申入口": "apply_url",
    "官方公告链接": "announcement_url",
    "招聘人数": "total_vacancies",
    "学历要求": "min_degree",
    "年龄限制": "age_limit",
    "英语要求": "cet_requirement",
    "计算机要求": "computer_cert_requirement",
    "咨询电话": "consulting_phone",
    "备注": "remarks",
}
BATCH_STATE_COL = "内容状态"
BATCH_PUBLISHED_COL = "是否已发布"

# `公司信息` 列名 → legacy row 键
COMPANY_COLUMNS = {
    "全称": "full_name",
    "性质": "nature",
    "城市": "headquarters_city",
    "官网": "official_site",
    "招聘官网": "recruit_site",
    "所属行业": "industry_catalog",
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
# 可由「内容状态.json 的 facts 袋」补齐的键（台账没有、核过官方公告后回填）
FACT_KEYS = (
    "full_name", "line", "target_graduates", "employment_nature",
    "wechat_url", "verdict_summary", "chsi_valid_date",
    "medical_veto_rules", "allocation_rules", "pitfall_warnings",
)


class SourceError(RuntimeError):
    """工作区数据源不可用 / 结构不合法 / 调用失败。

    必须显式报错，**绝不降级成「空数据」** —— 否则「本地没查到」会被误当成
    「没有可写单位」，正是凭空写稿的起点。
    """

    def __init__(self, code, message, *, details=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


# ─────────────────────────────────────────────────────────────
# 工作区发现
# ─────────────────────────────────────────────────────────────
def discover_workspace(explicit=None):
    """定位工作区根；显式值与环境变量是**硬约束**（校验不过即报错，不回退）。"""
    if explicit:
        p = Path(explicit).expanduser()
        if not (p / TOTAL_XLSX).is_file():
            raise SourceError(
                "workspace_invalid",
                f"指定工作区里没有 `{TOTAL_XLSX}`：{p}",
                details={"hint": "传工作区根目录（内含「单位与招聘信息总表.xlsx」与「巡检记录/」）"})
        return p
    env = os.environ.get(WORKSPACE_ENV)
    if env:
        p = Path(env).expanduser()
        if not (p / TOTAL_XLSX).is_file():
            raise SourceError(
                "workspace_invalid",
                f"{WORKSPACE_ENV} 指向的工作区里没有 `{TOTAL_XLSX}`：{p}",
                details={"hint": f"修正或清空 {WORKSPACE_ENV}"})
        return p
    p = Path(DEFAULT_WORKSPACE).expanduser()
    if (p / TOTAL_XLSX).is_file():
        return p
    raise SourceError(
        "workspace_not_found",
        f"未能定位「码上职业」工作区（默认位置：{p}）",
        details={"checked": [str(p)],
                 "hint": f"用 --workspace 指定，或设置 {WORKSPACE_ENV}"})


def state_path(workspace):
    return Path(workspace) / STATE_JSON


def _now():
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


# ─────────────────────────────────────────────────────────────
# 内容状态.json（唯一真源）
# ─────────────────────────────────────────────────────────────
def state_key(unit, title):
    """批次稳定键：单位专名 + 招聘标题（标题缺失时退化用单位名）。"""
    return f"{(unit or '').strip()}||{(title or '').strip()}"


def _empty_state():
    return {
        "schema_version": "1.0.0",
        "updated_at": _now(),
        "authority": ("本文件是「某单位写没写过 / 有没有推草稿箱 / 发没发 / 归档在哪」的"
                      "唯一真源；由 emit_briefing.py 读取，用 --mark 回填。"),
        "states": list(STATES),
        "batches": {},
    }


def load_state(workspace, *, required=True):
    """读取状态文件。

    ``required=True``（默认）时缺失即报错 —— 与「找不到 ≠ 没有批次」同源纪律。
    初始化场景用 ``required=False``。
    """
    p = state_path(workspace)
    if not p.is_file():
        if not required:
            return _empty_state()
        raise SourceError(
            "state_missing",
            f"未找到内容状态文件 `{STATE_JSON}`（{p}）",
            details={"hint": "先跑 `emit_briefing.py --state-init` 从总表与各线目录初始化；"
                             "⛔ 不要把它当成「什么都没写过」"})
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise SourceError("state_invalid", f"`{STATE_JSON}` 不是合法 JSON：{exc}",
                          details={"path": str(p)}) from exc
    if not isinstance(data, dict) or not isinstance(data.get("batches"), dict):
        raise SourceError("state_invalid", f"`{STATE_JSON}` 结构不合法（缺 batches 字典）",
                          details={"path": str(p)})
    return data


def save_state(workspace, state):
    """原子写回状态文件（临时文件 + 替换），避免半个文件被读到。"""
    state["updated_at"] = _now()
    p = state_path(workspace)
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(p.parent), prefix=".内容状态.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(state, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
        os.replace(tmp, p)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return p


def set_batch_state(workspace, unit, title, to_state, *, by="AI", note="", files=None):
    """把某批次推进到新状态并留痕（history 追加，不覆盖）。"""
    if to_state not in STATES:
        raise SourceError("state_unknown", f"未知状态 `{to_state}`（可选：{'/'.join(STATES)}）")
    state = load_state(workspace)
    key = state_key(unit, title)
    rec = state["batches"].get(key)
    if rec is None:
        rec = {"unit": unit, "title": title, "state": "unwritten",
               "history": [], "facts": {}, "files": {}, "notes": ""}
        state["batches"][key] = rec
    old = rec.get("state") or "unwritten"
    if old != to_state:
        rec.setdefault("history", []).append(
            {"at": _now(), "from": old, "to": to_state, "by": by, "note": note})
    rec["state"] = to_state
    if files:
        rec.setdefault("files", {}).update({k: v for k, v in files.items() if v})
    if note:
        prev = (rec.get("notes") or "").strip()
        rec["notes"] = f"{prev}\n{note}".strip() if prev else note
    state["batches"][key] = rec
    save_state(workspace, state)
    return rec


# ─────────────────────────────────────────────────────────────
# 总表读取
# ─────────────────────────────────────────────────────────────
def _open_xlsx(path):
    try:
        import openpyxl  # 延迟导入：缺失时给出可读报错
    except ImportError as exc:  # pragma: no cover
        raise SourceError("openpyxl_missing",
                          "缺少 openpyxl，无法读总表 xlsx（pip install openpyxl）") from exc
    try:
        return openpyxl.load_workbook(str(path), read_only=True, data_only=True)
    except Exception as exc:  # noqa: BLE001
        raise SourceError("xlsx_unreadable", f"总表打不开：{path}（{exc}）") from exc


def _sheet_rows(ws, sheet_name):
    """把 sheet 读成 (表头 list, 数据行 list[dict])。"""
    if sheet_name not in ws.sheetnames:
        raise SourceError("sheet_missing", f"总表缺少 sheet `{sheet_name}`",
                          details={"sheets": list(ws.sheetnames)})
    sh = ws[sheet_name]
    it = sh.iter_rows(values_only=True)
    try:
        header = [("" if c is None else str(c).strip()) for c in next(it)]
    except StopIteration:
        return [], []
    out = []
    for row in it:
        if row is None or all(c is None or str(c).strip() == "" for c in row):
            continue
        out.append({header[i]: row[i] for i in range(min(len(header), len(row)))})
    return header, out


def _txt(v):
    if v is None:
        return ""
    s = str(v).strip()
    return "" if s.lower() in ("none", "nan") else s


def load_companies(workspace):
    """读 `公司信息` sheet → {名称: {legacy 键: 值}}。"""
    wb = _open_xlsx(Path(workspace) / TOTAL_XLSX)
    try:
        _header, rows = _sheet_rows(wb, SHEET_COMPANIES)
    finally:
        wb.close()
    out = {}
    for r in rows:
        name = _txt(r.get("名称")) or _txt(r.get("全称"))
        if not name:
            continue
        out[name] = {k: _txt(r.get(col)) for col, k in COMPANY_COLUMNS.items()}
    return out


def load_batches(workspace, state):
    """读 `招聘信息` sheet，与状态文件、公司档案合并成 legacy row 列表。"""
    wb = _open_xlsx(Path(workspace) / TOTAL_XLSX)
    try:
        header, rows = _sheet_rows(wb, SHEET_BATCHES)
        for col in (BATCH_STATE_COL, BATCH_PUBLISHED_COL):
            if col not in header:
                raise SourceError(
                    "xlsx_schema_changed",
                    f"`{SHEET_BATCHES}` 缺少列「{col}」—— 状态列是流水线接口，改名会静默丢状态",
                    details={"header": header})
    finally:
        wb.close()

    companies = load_companies(workspace)
    batches = state.get("batches", {})
    out = []
    for idx, r in enumerate(rows, start=1):
        row = {k: "" for k in LEGACY_KEYS}
        for col, key in BATCH_COLUMNS.items():
            row[key] = _txt(r.get(col))
        company = row["company"]
        if company in companies:                       # 单位档案补全
            for k, v in companies[company].items():
                if v and not row.get(k):
                    row[k] = v
        key = state_key(row["company"], row["title"])
        rec = batches.get(key) or batches.get(state_key(row["company"], "")) or {}
        # 状态：内容状态.json 是真源；总表两列仅作审计对照
        row["content_state"] = (rec.get("state") or "").strip() or _state_from_xlsx(r)
        row["xlsx_content_state"] = _txt(r.get(BATCH_STATE_COL))
        row["xlsx_published"] = _txt(r.get(BATCH_PUBLISHED_COL))
        row["state_key"] = key
        row["state_known"] = bool(rec)
        facts = rec.get("facts") or {}
        for k in FACT_KEYS:
            v = _txt(facts.get(k))
            if v and not row.get(k):
                row[k] = v
        if _txt(facts.get("hc")) and not row["total_vacancies"]:
            row["total_vacancies"] = _txt(facts.get("hc"))
        if _txt(facts.get("edu")) and not row["min_degree"]:
            row["min_degree"] = _txt(facts.get("edu"))
        row["cid"] = idx
        row["id"] = idx
        row["source_url"] = row["announcement_url"]
        # 正文（供草稿箱「正文含标题」匹配与稿件长度自证）——仅在本地成稿时读源稿
        rh, alen = _article_text(workspace, rec)
        row["rh"] = rh
        row["article_length"] = alen
        row["html_len"] = alen
        out.append(row)
    return out


def _state_from_xlsx(r):
    return {"published": "published", "written": "written",
            "unwritten": "unwritten"}.get(_txt(r.get(BATCH_STATE_COL)).lower(), "unwritten")


def _article_text(workspace, rec):
    """本地已成稿时读源稿正文（截断），用于对账与长度自证；否则返回空。"""
    src = _txt((rec.get("files") or {}).get("source"))
    if not src:
        return "", 0
    p = Path(workspace) / src
    if not p.is_file():
        return "", 0
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        return "", 0
    return text[:20000], len(text)


# ─────────────────────────────────────────────────────────────
# 巡检报告读取（在架公告分层）
# ─────────────────────────────────────────────────────────────
_UNIT_RE = re.compile(r"^\*\*(.+?)\*\*\s*[（(](.*?)[）)]\s*$")
_LINK_RE = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")
_SECTION_IN_STOCK = re.compile(r"^##\s*三、")
_SECTION_NEXT = re.compile(r"^##\s*三之二")


def _patrol_line_of(name):
    for kw, label in (("机关单位", "机关单位"), ("电力电网", "电力电网"),
                      ("铁路", "铁路"), ("银行", "银行")):
        if kw in name:
            return label
    return "其他"


def parse_patrol_report(path):
    """解析一份巡检报告的「## 三、当前在架招聘公告」表。

    格式（脚本产出，稳定）::

        **单位名**（源 URL）

        | 日期 | 报名截止 | 状态 | 来源 | 标题 |
        |---|---|---|---|---|
        | 2026-09-28 | — | 长期 | 源名 | [标题](url) |

    返回 ``[{unit, date, deadline, layer, source, title, url}]``；
    格式未识别时返回空列表（调用方降级处理，不报错）。
    """
    try:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        return []
    out, unit, in_stock = [], "", False
    for raw in text.splitlines():
        line = raw.rstrip()
        if _SECTION_IN_STOCK.match(line):
            in_stock = True
            continue
        if _SECTION_NEXT.match(line):
            in_stock = False
            continue
        if not in_stock:
            continue
        m = _UNIT_RE.match(line.strip())
        if m:
            unit = m.group(1).strip()
            continue
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if set(cells[0]) <= set("-: "):
            continue
        # 两种表宽并存（实测量：机关单位/电力电网=5 列含「来源」，银行/铁路=4 列无「来源」）
        if len(cells) >= 5:
            date_s, deadline, layer, source, title_cell = cells[:5]
        elif len(cells) == 4:
            date_s, deadline, layer, title_cell = cells
            source = ""
        else:
            continue
        if layer not in ("有效", "长期", "待核"):
            continue
        lm = _LINK_RE.search(title_cell)
        title = lm.group(1) if lm else title_cell
        url = lm.group(2) if lm else ""
        out.append({"unit": unit, "date": date_s, "deadline": deadline,
                    "layer": layer, "source": source, "title": title,
                    "url": url, "report": Path(path).name,
                    "patrol_line": _patrol_line_of(Path(path).name)})
    return out


def load_patrol(workspace, max_reports=12):
    """读最近若干份监测报告的在架条目；返回 (entries, reports)。"""
    d = Path(workspace) / PATROL_DIR
    if not d.is_dir():
        return [], []
    files = sorted((p for p in d.iterdir()
                    if p.is_file() and p.name.endswith("监测.md")),
                   key=lambda p: p.name, reverse=True)[:max_reports]
    entries = []
    for f in files:
        entries.extend(parse_patrol_report(f))
    return entries, [f.name for f in files]


_LAYER_RANK = {"有效": 0, "长期": 1, "待核": 2}


def _patrol_rank(e):
    """排序键：先按分层（有效 > 长期 > 待核），再取**最新报告**优先。"""
    try:
        stamp = -int((e.get("report") or "")[:10].replace("-", ""))
    except ValueError:
        stamp = 0
    return (_LAYER_RANK.get(e["layer"], 9), stamp, e.get("deadline") or "9999")


def patrol_for(text, entries, limit=8):
    """按单位专名/关键词在巡检条目里查在架公告（含标题或来源命中）。

    同一公告常被连续几天的报告重复收录 —— 按 (url|title) 去重，
    只保留「分层更硬、报告更新」的那条，避免投料单里同一条刷三遍。
    """
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
# 初始化 / 审计 / 回推总表
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


_PIECE_PREFIX_RE = re.compile(r"^\d{2,4}[-_]\d{0,4}[-_]?")


def _unit_from_piece(name):
    """从稿件文件名前缀里提取单位专名：剥掉「期号-」「YYYY-MM-DD-」等前缀。

    例：``02-04-中国核电`` → ``中国核电``；``2026-09-30-南京特殊教育师范学院第二批…`` →
    ``南京特殊教育师范学院第二批…``（保留批次描述，只去日期/期号）。
    """
    s = (name or "").strip()
    s = re.sub(r"^\d{4}-\d{2}-\d{2}[-_]?", "", s)      # 先剥裸日期
    s = _PIECE_PREFIX_RE.sub("", s, count=1)              # 再剥期号
    return s or (name or "").strip()


def init_state(workspace, *, by="AI", force=False):
    """从总表 `招聘信息` + 各线目录初始化内容状态文件（幂等：已存在且非 force 则只报差异）。"""
    p = state_path(workspace)
    if p.is_file() and not force:
        state = load_state(workspace)
        return state, {"action": "kept", "path": str(p),
                       "batches": len(state["batches"])}

    wb = _open_xlsx(Path(workspace) / TOTAL_XLSX)
    try:
        _header, rows = _sheet_rows(wb, SHEET_BATCHES)
    finally:
        wb.close()
    pieces = _scan_pieces(workspace)
    written_names = set()
    for k, v in pieces.items():
        if k.endswith("待发布") or k.endswith("已发布"):
            written_names |= v

    state = _empty_state()
    seeded = 0
    for r in rows:
        unit = _txt(r.get("单位名称"))
        title = _txt(r.get("招聘标题"))
        if not unit and not title:
            continue
        st = _state_from_xlsx(r)
        rec = {"unit": unit, "title": title, "state": st, "history": [],
               "facts": {}, "files": {}, "notes": ""}
        rec["history"].append({"at": _now(), "from": "", "to": st, "by": by,
                               "note": "初始化：取自总表「内容状态/是否已发布」"})
        state["batches"][state_key(unit, title)] = rec
        seeded += 1

    # 目录里有成稿但台账没登记的 → 建 written 记录（红线 11 的归档缺口也在这里暴露）
    added = 0
    for name in sorted(written_names):
        if any(name.split("-源稿")[0] in k for k in state["batches"]):
            continue
        unit = _unit_from_piece(name)
        state["batches"][state_key(unit, "")] = {
            "unit": unit, "title": "", "state": "written", "history": [
                {"at": _now(), "from": "", "to": "written", "by": by,
                 "note": f"初始化：仅见于各线目录，台账无此单位（文件名 {name}）"}],
            "facts": {}, "files": {}, "notes": "台账缺登记"}
        added += 1
    save_state(workspace, state)
    return state, {"action": "created" if not force else "rebuilt",
                   "path": str(p), "seeded": seeded, "from_dirs": added,
                   "batches": len(state["batches"])}


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


def import_draft_titles(workspace, titles, *, apply=False, by="AI"):
    """把微信草稿箱里的标题导入 `内容状态.json`（状态 draft）。

    草稿箱是「已推草稿箱」的**现场证据**：稿件一旦群发即从草稿箱消失，
    所以箱里有的 = 已推未发。只对**状态文件里匹配不上**的标题新建记录，
    ⛔ 绝不覆盖已有状态（不会把 published 降级）。

    ``apply=False``（默认）只报告将要做什么，不落盘。
    """
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
            if (probe and (probe in nt or nt[:18] in probe)) or (len(unit) >= 4 and unit in nt):
                hit = v
                break
        if hit:
            skipped.append((t, hit.get("unit"), hit.get("state")))
            continue
        planned.append(t)
    if not apply:
        return {"planned": planned, "skipped": skipped, "applied": 0}
    for t in planned:
        unit = _unit_from_title(t)
        rec = {"unit": unit, "title": t, "state": "draft",
               "history": [{"at": _now(), "from": "", "to": "draft", "by": by,
                            "note": "由微信草稿箱标题导入（箱里有＝已推未发）"}],
               "facts": {}, "files": {}, "notes": "草稿箱导入，台账未登记"}
        state["batches"][state_key(unit, t)] = rec
    if planned:
        save_state(workspace, state)
    return {"planned": planned, "skipped": skipped, "applied": len(planned)}


def audit(workspace, state=None, rows=None):
    """四方对账：内容状态.json ↔ 总表两列 ↔ 各线目录 ↔ 台账登记。

    返回可直接打印的字典；本函数**只读**，不修任何东西。
    """
    state = state or load_state(workspace)
    rows = rows if rows is not None else load_batches(workspace, state)
    pieces = _scan_pieces(workspace)
    json_c = Counter((r.get("state") or "unwritten") for r in state["batches"].values())
    xlsx_c = Counter(r["xlsx_content_state"] or "（空）" for r in rows)
    mismatch, missing_in_state = [], []
    for r in rows:
        if not r["state_known"]:
            missing_in_state.append({"unit": r["company"], "title": r["title"],
                                     "xlsx": r["xlsx_content_state"]})
            continue
        if r["content_state"] != r["xlsx_content_state"]:
            mismatch.append({"unit": r["company"], "title": r["title"][:40],
                             "json": r["content_state"], "xlsx": r["xlsx_content_state"]})
    published = [v for v in state["batches"].values() if v.get("state") == "published"]
    archived = pieces.get("2027年校园招聘/已发布", set()) | pieces.get("事业单位/已发布", set()) \
        | pieces.get("教育系统/已发布", set()) | pieces.get("人生方向/已发布", set())
    not_archived = []
    for v in published:
        unit = (v.get("unit") or "").strip()
        if unit and not any(unit in a for a in archived):
            not_archived.append(unit)
    return {
        "state_file": str(state_path(workspace)),
        "state_counts": dict(json_c),
        "xlsx_counts": dict(xlsx_c),
        "batches_in_state": len(state["batches"]),
        "batches_in_xlsx": len(rows),
        "state_xlsx_mismatch": mismatch,
        "xlsx_rows_missing_in_state": missing_in_state,
        "local_inventory": {k: len(v) for k, v in pieces.items() if k.endswith("待发布")},
        "local_archived": {k: len(v) for k, v in pieces.items() if k.endswith("已发布")},
        "published_not_archived": not_archived,
    }


def push_state_to_xlsx(workspace, state=None, *, backup=True):
    """把内容状态.json 的 state 单向回推总表两列（总表只作流水线快照）。

    ⛔ 会改总表 xlsx —— 改前强制备份到 /tmp 并打印 SHA-256 与回滚命令。
    """
    import openpyxl
    state = state or load_state(workspace)
    p = Path(workspace) / TOTAL_XLSX
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = Path(tempfile.gettempdir()) / f"{p.name}.{stamp}.bak"
    if backup:
        shutil.copy2(p, backup_path)
        digest = hashlib.sha256(backup_path.read_bytes()).hexdigest()
    wb = openpyxl.load_workbook(str(p))
    sh = wb[SHEET_BATCHES]
    header = [("" if c.value is None else str(c.value).strip()) for c in sh[1]]
    i_unit, i_title = header.index("单位名称") + 1, header.index("招聘标题") + 1
    i_state, i_pub = header.index(BATCH_STATE_COL) + 1, header.index(BATCH_PUBLISHED_COL) + 1
    updated = 0
    for row_idx in range(2, sh.max_row + 1):
        unit = _txt(sh.cell(row=row_idx, column=i_unit).value)
        title = _txt(sh.cell(row=row_idx, column=i_title).value)
        rec = state["batches"].get(state_key(unit, title))
        if not rec:
            continue
        st, pub = STATE_TO_XLSX.get(rec.get("state") or "unwritten", ("unwritten", "否"))
        if _txt(sh.cell(row=row_idx, column=i_state).value) == st and \
           _txt(sh.cell(row=row_idx, column=i_pub).value) == pub:
            continue
        sh.cell(row=row_idx, column=i_state).value = st
        sh.cell(row=row_idx, column=i_pub).value = pub
        updated += 1
    wb.save(str(p))
    wb.close()
    return {"updated": updated, "backup": str(backup_path) if backup else "",
            "sha256": digest if backup else "",
            "rollback": f"cp '{backup_path}' '{p}'" if backup else ""}


# ─────────────────────────────────────────────────────────────
# 自检
# ─────────────────────────────────────────────────────────────
def _selftest(workspace):
    rows = None
    state = load_state(workspace, required=False)
    if state["batches"]:
        rows = load_batches(workspace, state)
    entries, reports = load_patrol(workspace)
    print(f"工作区: {workspace}")
    print(f"状态文件: {state_path(workspace)}（{len(state['batches'])} 个批次）")
    print(f"总表批次行: {len(rows) if rows is not None else '（未初始化）'}")
    print(f"巡检报告: {len(reports)} 份 ｜ 在架条目: {len(entries)}")
    print("最近报告:", ", ".join(reports[:4]))
    return 0


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description="码上职业本工作区数据源自检")
    ap.add_argument("--workspace", help=f"工作区根（默认 {DEFAULT_WORKSPACE}）")
    ap.add_argument("--json", action="store_true", help="以 JSON 输出")
    a = ap.parse_args(argv)
    try:
        ws = discover_workspace(a.workspace)
        if a.json:
            state = load_state(ws, required=False)
            entries, reports = load_patrol(ws)
            print(json.dumps({"workspace": str(ws), "state_file": str(state_path(ws)),
                              "batches": len(state["batches"]),
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
