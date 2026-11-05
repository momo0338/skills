#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""workspace_source / emit_briefing 测试（2026-11-04 db 版）。

背景
====
2026-11-04 朱总裁定：`单位与招聘信息总表.xlsx`、`内容状态.json`、
`巡检记录/*监测.md` 三套工作区自有事实源**全部废弃**，统一改读流水线 db：

  ① `units` + `unit_sources`/`sources` → 单位档案与招聘官网入口
  ② `announce_pool`                   → 在招公告批次台账
  ③ `drafts` ∪ `articles`             → 写稿进度 / 判重唯一真源
  ④ `monitor_state` / `announce_pool` → 在架公告分层

旧版 1365 行测试全部围绕「tmp 工作区里用 openpyxl 造 xlsx + 写状态 json +
写巡检 md」，测的是已废弃链路，随本次改造一并移除。本文件改为：
  - 每个用例用 pytest `tmp_path` 现场造一份**最小 SQLite db**，
    通过 `PIPELINE_DB` 环境变量注入，⛔ 绝不触碰真实生产库；
  - CLI 用例显式 `--workspace <tmp>` + `PIPELINE_DB`，离线自包含；
  - 断言适配层源码里不再有 openpyxl / xlsx 依赖。
"""
from __future__ import annotations

import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import emit_briefing as emit  # noqa: E402
import workspace_source as wsrc  # noqa: E402

SCRIPT = SCRIPTS / "emit_briefing.py"
ADAPTER = SCRIPTS / "workspace_source.py"

UNIT = "测试单位"
TITLE = "测试单位2027校招"
URL = "https://notice.example/2027"
APPLY = "https://apply.example/2027"

SCHEMA = """
create table units (
  id integer primary key, name text, full_name text, nature text, city text,
  website text, recruit_site text, industry text, deleted text default '0');
create table sources (id integer primary key, name text, url text);
create table announce_pool (
  id integer primary key, url text, title text, pub_date text, end_date text,
  pub_unit text, pub_unit_src text, line text, recruit_type text, recruit_site text,
  fetched_at text, status integer default 1, dup_of text, target_unit_id integer,
  source_id integer);
create table drafts (
  id integer primary key, media_id text, title text, source_url text,
  temp_url text, status text, synced_at text);
create table articles (
  id integer primary key, published_title text, source_url text,
  published_at text, is_deleted text default '0');
"""


def _seed(conn, *, with_published=False, with_draft=False):
    conn.executescript(SCHEMA)
    conn.execute(
        "insert into units (id,name,full_name,nature,city,website,recruit_site,industry) "
        "values (1,?,?,?,?,?,?,?)",
        (UNIT, "测试单位有限责任公司", "国有企业", "南京市",
         "https://www.example.com", "https://job.example.com", "金融业"))
    conn.execute("insert into sources (id,name,url) values (1,'测试源','https://src.example')")
    conn.execute(
        "insert into announce_pool (id,url,title,pub_date,end_date,pub_unit,line,"
        "recruit_type,fetched_at,status,target_unit_id,source_id) "
        "values (1,?,?,?,?,?,?,?,?,1,1,1)",
        (URL, TITLE, "2026-11-01", "2026-12-31", UNIT, "enterprise",
         "campus", "2026-11-04T10:00:00"))
    if with_draft:
        conn.execute(
            "insert into drafts (id,media_id,title,source_url,status) "
            "values (1,'MEDIA-1',?,?,'draft')", (TITLE, URL))
    if with_published:
        conn.execute(
            "insert into articles (id,published_title,source_url,published_at,is_deleted) "
            "values (1,?,?,'2026-11-04 12:00:00','0')", (TITLE, URL))
    conn.commit()


@pytest.fixture
def env(tmp_path, monkeypatch):
    """临时 db + 临时工作区；⛔ 不触碰真实生产库。"""
    db = tmp_path / "流水线.db"
    conn = sqlite3.connect(str(db))
    _seed(conn)
    conn.close()
    ws = tmp_path / "码上职业"
    for line in wsrc.CONTENT_LINES:
        (ws / line / "待发布").mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv(wsrc.DB_ENV, str(db))
    monkeypatch.delenv(wsrc.WORKSPACE_ENV, raising=False)
    return {"db": db, "ws": ws, "conn": sqlite3.connect(str(db))}


# ══════════════════════════════════════════════════════════════════════
# 1. db 定位与硬失败
# ══════════════════════════════════════════════════════════════════════
def test_db_path_uses_env_and_missing_db_raises(env, monkeypatch):
    assert wsrc.db_path() == env["db"]
    monkeypatch.setenv(wsrc.DB_ENV, str(env["ws"] / "nope.db"))
    with pytest.raises(wsrc.SourceError) as ei:
        wsrc.db_path()
    assert ei.value.code == "db_not_found"


def test_discover_workspace_never_falls_back_when_db_missing(env, monkeypatch):
    monkeypatch.setenv(wsrc.DB_ENV, str(env["ws"] / "nope.db"))
    with pytest.raises(wsrc.SourceError) as ei:
        wsrc.discover_workspace(str(env["ws"]))
    assert ei.value.code == "db_not_found"


def test_discover_workspace_explicit_path(env):
    assert wsrc.discover_workspace(str(env["ws"])) == env["ws"]


# ══════════════════════════════════════════════════════════════════════
# 2. 单位档案 / 批次台账
# ══════════════════════════════════════════════════════════════════════
def test_load_companies_maps_units_columns(env):
    companies = wsrc.load_companies(env["ws"])
    assert UNIT in companies
    c = companies[UNIT]
    assert c["full_name"] == "测试单位有限责任公司"
    assert c["nature"] == "国有企业"
    assert c["headquarters_city"] == "南京市"
    assert c["official_site"] == "https://www.example.com"
    assert c["recruit_site"] == "https://job.example.com"
    assert c["industry_catalog"] == "金融业"


def test_load_batches_returns_full_legacy_row(env):
    rows = wsrc.load_batches(env["ws"], wsrc.load_state(env["ws"]))
    assert len(rows) == 1
    row = rows[0]
    for k in wsrc.LEGACY_KEYS:
        assert k in row, k
    assert row["company"] == UNIT
    assert row["title"] == TITLE
    assert row["batch_type"] == "校园招聘"
    assert row["line"] == "2027年校园招聘"
    assert row["publish_date"] == "2026-11-01"
    assert row["deadline"] == "2026-12-31"
    assert row["apply_url"] == URL and row["source_url"] == URL
    assert row["cid"] == row["id"] == 1
    # 硬信息 db 里没有可靠字段 → 留空，⛔ 不脑补
    for k in ("total_vacancies", "min_degree", "consulting_phone", "target_graduates"):
        assert row[k] == "", k
    assert row["content_state"] == "unwritten"
    assert row["state_known"] is False
    assert "xlsx" not in " ".join(row.keys())


def test_load_batches_ignores_inactive_pool_rows(env):
    conn = sqlite3.connect(str(env["db"]))
    conn.execute("insert into announce_pool (id,url,title,status) "
                 "values (2,'https://x.example','已失效公告',0)")
    conn.commit()
    conn.close()
    rows = wsrc.load_batches(env["ws"], wsrc.load_state(env["ws"]))
    assert [r["title"] for r in rows] == [TITLE]


# ══════════════════════════════════════════════════════════════════════
# 3. 状态视图（drafts ∪ articles，published 优先）
# ══════════════════════════════════════════════════════════════════════
def _rebuild(env, **kw):
    conn = sqlite3.connect(str(env["db"]))
    conn.executescript("drop table if exists units; drop table if exists sources; "
                       "drop table if exists announce_pool; drop table if exists drafts; "
                       "drop table if exists articles;")
    _seed(conn, **kw)
    conn.close()


def test_load_state_is_empty_without_draft_or_article(env):
    assert wsrc.load_state(env["ws"])["batches"] == {}


def test_load_state_draft_from_drafts(env):
    _rebuild(env, with_draft=True)
    state = wsrc.load_state(env["ws"])
    rec = next(iter(state["batches"].values()))
    assert rec["state"] == "draft"
    assert rec["source_url"] == URL
    assert rec["media_id"] == "MEDIA-1"


def test_load_state_published_wins_over_draft(env):
    _rebuild(env, with_draft=True, with_published=True)
    state = wsrc.load_state(env["ws"])
    states = [r["state"] for r in state["batches"].values()]
    assert states == ["published"]


def test_load_batches_matches_state_by_source_url(env):
    _rebuild(env, with_published=True)
    rows = wsrc.load_batches(env["ws"], wsrc.load_state(env["ws"]))
    assert rows[0]["content_state"] == "published"
    assert rows[0]["state_known"] is True
    assert rows[0]["db_published"] == "是"


def test_state_writes_are_readonly(env):
    with pytest.raises(wsrc.SourceError) as ei:
        wsrc.save_state(env["ws"], {})
    assert ei.value.code == "state_readonly"
    with pytest.raises(wsrc.SourceError) as ei:
        wsrc.set_batch_state(env["ws"], UNIT, TITLE, "draft")
    assert ei.value.code == "state_readonly"
    with pytest.raises(wsrc.SourceError) as ei:
        wsrc.push_state_to_xlsx(env["ws"])
    assert ei.value.code == "xlsx_retired"


def test_init_state_is_db_managed_noop(env):
    state, info = wsrc.init_state(env["ws"], force=True)
    assert info["action"] == "db_managed"
    assert "authority" in info
    assert not (env["ws"] / "内容状态.json").exists()


def test_import_draft_titles_is_dry_run_only(env):
    res = wsrc.import_draft_titles(env["ws"], [TITLE])
    assert res["applied"] == 0
    with pytest.raises(wsrc.SourceError) as ei:
        wsrc.import_draft_titles(env["ws"], [TITLE], apply=True)
    assert ei.value.code == "state_readonly"


# ══════════════════════════════════════════════════════════════════════
# 4. 在架条目（announce_pool，替代巡检 md）
# ══════════════════════════════════════════════════════════════════════
def test_load_patrol_reads_db_pool(env):
    entries, reports = wsrc.load_patrol(env["ws"])
    assert len(entries) == 1
    e = entries[0]
    assert e["title"] == TITLE and e["url"] == URL
    assert e["unit"] == UNIT and e["source"] == "测试源"
    assert e["layer"] in ("有效", "长期", "待核")
    assert e["patrol_line"] == "其他"
    assert reports and reports[0].endswith("-db")


def test_patrol_for_matches_and_dedupes(env):
    entries, _ = wsrc.load_patrol(env["ws"])
    assert len(wsrc.patrol_for("测试单位", entries)) == 1
    assert wsrc.patrol_for("不存在的单位", entries) == []
    dup = dict(entries[0], report="2026-11-03-db")
    assert len(wsrc.patrol_for("测试单位", entries + [dup])) == 1


# ══════════════════════════════════════════════════════════════════════
# 5. 对账 / 源码无 xlsx 依赖
# ══════════════════════════════════════════════════════════════════════
def test_audit_uses_db_keys_only(env):
    rep = wsrc.audit(env["ws"])
    assert rep["authority_db"] == str(env["db"])
    assert rep["batches_in_db"] == 1
    assert "db_counts" in rep and "state_db_mismatch" in rep
    assert not any("xlsx" in k for k in rep)


def test_adapter_source_has_no_xlsx_or_openpyxl():
    src = ADAPTER.read_text(encoding="utf-8")
    assert "import openpyxl" not in src
    assert "TOTAL_XLSX" not in src
    assert "load_workbook" not in src
    assert "sqlite3" in src


# ══════════════════════════════════════════════════════════════════════
# 6. CLI 端到端（离线，显式临时 db 与工作区）
# ══════════════════════════════════════════════════════════════════════
def _cli(env, *args):
    import os
    e = dict(os.environ)
    e[wsrc.DB_ENV] = str(env["db"])
    e.pop(wsrc.WORKSPACE_ENV, None)
    return subprocess.run([sys.executable, str(SCRIPT), "--workspace", str(env["ws"]), *args],
                          capture_output=True, text=True, env=e, timeout=60)


def test_cli_state_audit_prints_db_authority(env):
    r = _cli(env, "--state-audit")
    assert r.returncode == 0, r.stderr
    assert "真源" in r.stdout and str(env["db"]) in r.stdout
    assert "公告池有效批次" in r.stdout


def test_cli_state_push_xlsx_is_retired(env):
    r = _cli(env, "--state-push-xlsx")
    assert r.returncode != 0
    assert "xlsx_retired" in r.stderr or "已停用" in r.stderr


def test_cli_state_init_is_db_managed(env):
    r = _cli(env, "--state-init")
    assert r.returncode == 0, r.stderr
    assert "db_managed" in r.stdout
    assert not (env["ws"] / "内容状态.json").exists()


# ══════════════════════════════════════════════════════════════════════
# 7. emit_briefing 纯逻辑回归（与数据源无关）
# ══════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("state,expected", [
    ("unwritten", "库内未排"), ("written", "库内已成稿"),
    ("draft", "已推草稿箱"), ("published", "已发布"),
])
def test_draft_state_maps_all_four_states(state, expected):
    assert emit.draft_state({"content_state": state}) == expected


def test_grade_gates_and_gate_keys():
    assert isinstance(emit.REQUIRED, dict) and emit.REQUIRED
    assert "deadline" in emit.REQUIRED or "截止" in " ".join(emit.REQUIRED.keys())


def test_clean_url_splits_url_and_note():
    url, note = emit.clean_url("https://a.example/notice （官方公告）")
    assert url.startswith("https://a.example")
    assert note
