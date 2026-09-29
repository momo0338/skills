#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""emit_briefing 测试。

取数层已迁移到 ijob 稳定只读契约（brief JSON），因此这里**不再建任何本地库**：
- 领域语义测试直接喂契约批次对象列表；
- 契约边界测试用假 ijob 技能脚本 / mock subprocess 验证分页、错误与泄漏口径。
"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "emit_briefing.py"
SPEC = importlib.util.spec_from_file_location("emit_briefing", SCRIPT)
EMIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(EMIT)


def brief_item(**overrides):
    """构造一个 ijob brief 契约批次对象（字段名与真实契约一致）。"""
    item = {
        "campaign_id": 1,
        "title": "测试单位2027校招",
        "batch_type": "正式批次",
        "line": "B",
        "recruit_type": "校招",
        "target_graduates": "2027届",
        "min_degree": "本科及以上",
        "total_vacancies": "10人",
        "employment_nature": "合同制",
        "city": "南京",
        "publish_date": "2026-09-01",
        "deadline": "2026-09-20",
        "status": "在招",
        "verdict_summary": "",
        "apply_url": "https://example.test/apply",
        "announcement_url": "https://example.test/notice",
        "consulting_phone": "",
        "wechat_url": "",
        "age_limit": "",
        "cet_requirement": None,
        "computer_cert_requirement": None,
        "chsi_valid_date": "",
        "medical_veto_rules": None,
        "allocation_rules": "",
        "pitfall_warnings": "",
        "company_id": 1,
        "company": "测试单位",
        "full_name": "测试单位有限公司",
        "nature": "国有企业",
        "industry_catalog": "能源",
        "headquarters_city": "南京",
        "official_site": "https://example.test",
        "tags": [],
        "content_state": "unwritten",
        "article_length": 0,
        "article_search_text": "",
        "deadline_verified": True,
    }
    item.update(overrides)
    return item


def brief_envelope(items, total=None, operation="brief", contract="ijob.public", error=None):
    """构造 ijob.public 外壳响应。"""
    payload = {
        "schema_version": "1.0.0",
        "contract": contract,
        "operation": operation,
        "generated_at": "2026-09-25T21:00:00+08:00",
        "data": {
            "total": len(items) if total is None else total,
            "limit": 100,
            "offset": 0,
            "items": items,
        },
        "meta": {"read_only": True, "source": "ijob", "campaign_semantics_version": 3},
        "warnings": [],
    }
    if error is not None:
        payload["data"] = None
        payload["error"] = error
    return payload


class EmitBriefingDomainTests(unittest.TestCase):
    """领域语义：可信度、占位截止日、稿件状态、草稿箱对账。"""

    def make_row(self, **overrides):
        """契约批次对象 → legacy row（走真实适配层，避免测试自己拼 legacy 键）。"""
        return EMIT.to_legacy_row(brief_item(**overrides))

    def test_exact_thirty_day_deadline_is_vague(self):
        row = self.make_row(deadline="2026-10-01")
        self.assertTrue(EMIT.deadline_is_derived_placeholder(row))
        self.assertEqual(EMIT.grade_deadline(row), "VAGUE")

    def test_non_thirty_day_real_deadline_is_ok(self):
        row = self.make_row(deadline="2026-09-25")
        self.assertFalse(EMIT.deadline_is_derived_placeholder(row))
        self.assertEqual(EMIT.grade_deadline(row), "OK")

    def test_sentinel_deadline_is_vague(self):
        row = self.make_row(deadline=EMIT.PLACEHOLDER_DEADLINE)
        self.assertEqual(EMIT.grade_deadline(row), "VAGUE")

    def test_pending_wording_downgrades_deadline(self):
        row = self.make_row(deadline="2026-11-30", batch_type="待核批次")
        self.assertEqual(EMIT.grade_deadline(row), "VAGUE")

    def test_content_state_drives_draft_progress(self):
        self.assertEqual(EMIT.draft_state(self.make_row(content_state="unwritten")), "库内未排")
        self.assertEqual(EMIT.draft_state(self.make_row(content_state="written")), "库内已成稿")
        self.assertEqual(EMIT.draft_state(self.make_row(content_state="published")), "已发布")

    def test_local_article_is_not_published_or_draftbox_confirmed(self):
        # 正文存在只等于「ijob 侧已成稿」，不等于已推草稿箱、更不等于已发布。
        row = self.make_row(content_state="written", article_length=159740)
        self.assertEqual(EMIT.draft_state(row), "库内已成稿")
        self.assertEqual(
            EMIT.draft_state(self.make_row(
                content_state="published", article_length=159740,
                wechat_url="https://mp.weixin.qq.com/s/example")),
            "已发布",
        )

    def test_draft_state_falls_back_when_contract_omits_content_state(self):
        legacy = dict(self.make_row())
        legacy["content_state"] = ""
        self.assertEqual(EMIT.draft_state(legacy), "库内未排")
        legacy["article_length"] = 51
        self.assertEqual(EMIT.draft_state(legacy), "库内已成稿")
        legacy["wechat_url"] = "https://mp.weixin.qq.com/s/example"
        self.assertEqual(EMIT.draft_state(legacy), "已发布")

    def test_candidate_selection_prefers_published_then_rendered_then_id(self):
        # 三条同标题歧义批次：已发布 > 库内已成稿 > 库内未排，
        # 进度相同时再按正文长度、批次ID 稳定兜底。
        published = self.make_row(
            campaign_id=14, content_state="published", article_length=100,
            wechat_url="https://mp.weixin.qq.com/s/example")
        rendered = self.make_row(campaign_id=11, content_state="written", article_length=100)
        unwritten = self.make_row(campaign_id=20, content_state="unwritten", article_length=0)
        self.assertEqual(EMIT._select_candidate([rendered, published, unwritten])["id"], 14)
        self.assertEqual(EMIT._select_candidate([published, rendered])["id"], 14)
        # 同为「库内已成稿」时长文优先
        self.assertEqual(EMIT._select_candidate([
            self.make_row(campaign_id=14, content_state="written", article_length=20),
            self.make_row(campaign_id=11, content_state="written", article_length=0),
        ])["id"], 14)
        # 进度、正文长度都相同时按批次ID 最小
        self.assertEqual(EMIT._select_candidate([
            self.make_row(campaign_id=14, content_state="unwritten"),
            self.make_row(campaign_id=11, content_state="unwritten"),
        ])["id"], 11)

    def rows(self):
        return [
            self.make_row(campaign_id=11, title="南京大学2027校招",
                          company="南京大学", full_name="南京大学",
                          apply_url="https://nju.example"),
            self.make_row(campaign_id=12, title="中远海运科技2027校招",
                          company="中远海运科技", full_name="中远海运科技有限公司",
                          apply_url="https://cosco.example"),
            # 正文已写但未发布：用于「正文含标题」兜底命中。
            self.make_row(campaign_id=13, title="国网江苏2027校招",
                          company="国网江苏", full_name="国网江苏省电力有限公司",
                          apply_url="https://sgcc.example",
                          content_state="written", article_length=100,
                          article_search_text="正文" + "国网江苏2027校招" + "x" * 80),
        ]

    def test_semantic_match_is_candidate_and_preserves_exact_priority(self):
        matched, unmatched, desync, semantic = EMIT.reconcile_draftbox(self.rows(), [
            "南京大学校招提前批",
            "中远海运科技2027校招",
            "完全不存在的单位",
        ])
        self.assertEqual(len(matched), 2)
        self.assertEqual(len(unmatched), 1)
        self.assertEqual(len(semantic), 1)
        self.assertEqual(semantic[0][1], 11)
        self.assertEqual(len(desync), 1)
        self.assertEqual(desync[0][0], 12)
        self.assertEqual(sum(1 for x in matched if x[1] == 11), 1)

    def test_body_search_text_is_used_for_fallback_match(self):
        rows = self.rows()
        # 草稿标题与批次标题毫无字面关系，只能靠稿件正文命中。
        # 正文只在契约字段 article_search_text 里，必须经适配层进入匹配域。
        rows[2] = self.make_row(
            campaign_id=13, title="国网江苏电力2027校园招聘正式启动",
            content_state="written", article_length=100,
            article_search_text="前文" + "某某神秘标题甲乙丙丁" + "后文" * 40)
        matched, _unmatched, _desync, _semantic = EMIT.reconcile_draftbox(rows, [
            "某某神秘标题甲乙丙丁",
        ])
        self.assertEqual(matched[0][1], 13)
        self.assertEqual(matched[0][4], "正文含标题")

    def test_draft_body_matching_ignores_rows_without_article(self):
        rows = self.rows()
        rows[2] = self.make_row(
            campaign_id=13, title="国网江苏电力2027校园招聘正式启动",
            content_state="unwritten", article_length=0, article_search_text="")
        _matched, unmatched, _desync, _semantic = EMIT.reconcile_draftbox(rows, [
            "某某神秘标题甲乙丙丁",
        ])
        self.assertIn("某某神秘标题甲乙丙丁", unmatched)

    def test_alias_candidate_matches_shorthand_to_full_name(self):
        rows = self.rows()
        rows[1].update(company="华为南研所", full_name="华为技术有限公司南京研究所")
        rows[1]["title"] = "华为南研所2027届校园招聘"
        matched, unmatched, desync, semantic = EMIT.reconcile_draftbox(rows, ["华为南研所校招来了"])
        self.assertEqual(len(unmatched), 0)
        self.assertEqual(matched[0][1], 12)
        self.assertTrue(matched[0][4].startswith("别名候选:"))
        self.assertEqual(semantic, [matched[0]])
        self.assertEqual(desync, [])

    def test_exact_long_alias_matches_nanjing_health_bureau_group(self):
        rows = self.rows()
        rows[1].update(company="南京市卫健委所属事业单位",
                       full_name="南京市卫生健康委员会所属事业单位")
        rows[1]["title"] = "南京市卫健委所属事业单位2026年公开招聘高层次人才"
        matched, unmatched, _desync, _semantic = EMIT.reconcile_draftbox(rows, [
            "南京市卫健委所属8家事业单位招高层次人才338人（编内278人）",
        ])
        self.assertEqual(unmatched, [])
        self.assertEqual(matched[0][1], 12)
        self.assertEqual(matched[0][4], "别名候选:南京市卫健委所属8家事业单位")

    def test_generic_terms_do_not_cross_match_cities_or_agencies(self):
        rows = self.rows()
        rows[1].update(company="江苏省血液中心", full_name="江苏省血液中心")
        rows[1]["title"] = "江苏省血液中心公开招聘"
        matched, unmatched, _desync, _semantic = EMIT.reconcile_draftbox(rows, [
            "南京市红十字血液中心招聘",
            "南京市疾病预防控制中心招聘",
        ])
        self.assertEqual(len(matched), 0)
        self.assertEqual(unmatched, [
            "南京市红十字血液中心招聘",
            "南京市疾病预防控制中心招聘",
        ])

    def test_duplicate_draft_titles_are_counted_separately(self):
        matched, _unmatched, desync, _semantic = EMIT.reconcile_draftbox(self.rows(), [
            "中远海运科技2027校招",
            "中远海运科技2027校招",
        ])
        self.assertEqual(len(matched), 2)
        self.assertEqual(len(desync), 2)

    def test_ambiguous_candidate_excludes_every_possible_campaign(self):
        ambiguous = ("集团校招", 3, "集团", "库内未排", "主体多批次候选:3,7")
        result = EMIT._best_draft_matches([ambiguous])
        self.assertEqual(set(result), {3, 7})
        self.assertEqual(result[3], ambiguous)
        self.assertEqual(result[7], ambiguous)
        self.assertTrue(EMIT._is_candidate_match(ambiguous[4]))
        self.assertTrue(EMIT._is_ambiguous_match(ambiguous[4]))

    def test_duplicate_campaign_title_is_exposed_as_ambiguous_candidate(self):
        rows = self.rows()
        rows.append(self.make_row(campaign_id=14, title="南京大学2027校招",
                                  company="南京大学", full_name="南京大学"))
        matched, _unmatched, _desync, semantic = EMIT.reconcile_draftbox(rows, [
            "南京大学2027校招",
        ])
        self.assertEqual(len(matched), 1)
        self.assertEqual(matched[0][1], 11)
        self.assertEqual(matched[0][4], "标题多批次候选:11,14")
        self.assertEqual(semantic, [matched[0]])

    def test_ambiguous_display_prefers_progress_but_keeps_all_exclusions(self):
        rows = self.rows()
        rows[2]["content_state"] = "unwritten"
        rows[2]["article_length"] = 0
        rows[2]["article_search_text"] = ""
        rows.append(self.make_row(
            campaign_id=14, title="南京大学2027校招", company="南京大学", full_name="南京大学",
            content_state="published", wechat_url="https://mp.weixin.qq.com/s/example"))
        matched, _unmatched, _desync, _semantic = EMIT.reconcile_draftbox(rows, [
            "南京大学2027校招",
        ])
        self.assertEqual(matched[0][1], 14)
        self.assertEqual(matched[0][3], "已发布")
        self.assertEqual(matched[0][4], "标题多批次候选:11,14")
        best = EMIT._best_draft_matches(matched)
        self.assertEqual(set(best), {11, 14})
        self.assertEqual(best[11], matched[0])
        self.assertEqual(best[14], matched[0])

    def test_match_priority_prefers_body_over_weak_candidate(self):
        exact = ("某草稿", 9, "单位", "库内未排", "标题精确")
        body = ("某草稿", 9, "单位", "库内未排", "正文含标题")
        semantic = ("某草稿", 9, "单位", "库内未排", "主体相似:单位")
        alias = ("某草稿", 9, "单位", "库内未排", "别名候选:单位")
        ambiguous = ("某草稿", 9, "单位", "库内未排", "标题多批次候选:9,10")
        self.assertEqual(EMIT._best_draft_matches([semantic, alias, body, ambiguous, exact])[9], exact)
        self.assertEqual(EMIT._best_draft_matches([semantic, body, ambiguous, alias])[9], body)
        self.assertEqual(EMIT._best_draft_matches([semantic, ambiguous, alias])[9], ambiguous)

    def test_candidate_marker_never_claims_confirmed_desync(self):
        self.assertEqual(EMIT.match_marker("库内未排", "主体多批次候选:1,2"), "  ⚠️仅候选")
        self.assertEqual(EMIT.match_marker("库内未排", "标题精确"), "  ⛔确定失同步")
        self.assertEqual(EMIT.match_marker("库内已成稿", "标题精确"), "")

    def test_ready_excludes_local_drafts_and_draftbox_candidates(self):
        rows = [
            self.make_row(campaign_id=1, full_name="本地成稿单位",
                          content_state="written", article_length=100,
                          apply_url="https://local.example"),
            self.make_row(campaign_id=2, full_name="草稿候选单位",
                          apply_url="https://candidate.example"),
            self.make_row(campaign_id=3, full_name="可写单位",
                          apply_url="https://ready.example"),
            self.make_row(campaign_id=4, full_name="占位单位", deadline="2026-10-01",
                          apply_url="https://placeholder.example"),
        ]
        draft_item = ("草稿候选单位校招", 2, "草稿候选单位", "库内未排", "主体相似:草稿候选单位")
        out, err = [], []
        with mock.patch.object(EMIT, "fetch_brief_items", return_value=rows), \
             mock.patch.object(EMIT, "fetch_draft_titles", return_value=(["草稿候选单位校招"], [""])), \
             mock.patch.object(EMIT, "reconcile_draftbox",
                               return_value=([draft_item], [], [(2, "草稿候选单位", "草稿候选单位校招")], [draft_item])), \
             mock.patch("sys.argv", ["emit_briefing.py", "--ready"]):
            with mock.patch("builtins.print", side_effect=lambda *a, **k: out.append(" ".join(str(x) for x in a))), \
                 mock.patch("sys.stderr", new=mock.MagicMock(write=err.append)):
                EMIT.main()
        text = "\n".join(out)
        self.assertIn("可写单位", text)
        self.assertNotIn("本地成稿单位", text.split("按网申入口合并")[-1])
        self.assertNotIn("占位单位", text.split("按网申入口合并")[-1])
        self.assertIn("草稿候选单位", text.split("草稿箱有对应候选")[-1])

    def test_draftbox_failure_is_explicit_and_does_not_look_trustworthy(self):
        rows = [self.make_row(campaign_id=1, full_name="无法排除草稿单位")]
        out = []
        with mock.patch.object(EMIT, "fetch_brief_items", return_value=rows), \
             mock.patch.object(EMIT, "fetch_draft_titles", return_value=(None, [])), \
             mock.patch("sys.argv", ["emit_briefing.py", "--ready"]):
            with mock.patch("builtins.print", side_effect=lambda *a, **k: out.append(" ".join(str(x) for x in a))), \
                 mock.patch("sys.stderr", new=mock.MagicMock()):
                EMIT.main()
        text = "\n".join(out)
        self.assertIn("草稿箱对账**跳过**", text)
        self.assertIn("不可直接采信", text)
        self.assertIn("无法排除草稿单位", text)


class IjobContractBoundaryTests(unittest.TestCase):
    """契约边界：发现、分页、错误、结构化校验。"""

    def test_script_source_never_mentions_sqlite_or_local_database(self):
        source = SCRIPT.read_text(encoding="utf-8")
        for banned in ("import sqlite3", "sqlite3.", "jobs.db", "DEFAULT_DB",
                       "campaign_articles", "rendered_html", "has_article",
                       "SELECT ", "FROM campaigns", "--db"):
            self.assertNotIn(banned, source.replace("--db-path", ""),
                             f"脚本源码仍出现数据库直连痕迹：{banned}")
        # 运行期命名空间里也不该有 sqlite3 / 旧 SQL 常量
        self.assertNotIn("sqlite3", vars(EMIT))
        self.assertFalse(hasattr(EMIT, "SQL"))
        self.assertFalse(hasattr(EMIT, "DEFAULT_DB"))
        self.assertFalse(hasattr(EMIT, "fetch_rows"))

    def test_db_cli_flag_is_gone(self):
        help_text = subprocess.run(
            [sys.executable, str(SCRIPT), "--help"], capture_output=True, text=True)
        self.assertNotIn("--db", help_text.stdout)

    def test_find_ijob_script_prefers_env_then_user_then_repo(self):
        with tempfile.TemporaryDirectory() as tmp:
            env_script = os.path.join(tmp, "ijob.py")
            open(env_script, "w").close()
            with mock.patch.dict(os.environ, {EMIT.IJOB_SCRIPT_ENV: env_script}):
                self.assertEqual(EMIT.find_ijob_script()[0], env_script)

            # 环境变量无效路径 → 回落到标准安装位置（真实用户级技能存在时）
            with mock.patch.dict(os.environ, {EMIT.IJOB_SCRIPT_ENV: os.path.join(tmp, "nope.py")}):
                path, origin = EMIT.find_ijob_script()
                self.assertTrue(os.path.isfile(path))
                self.assertNotIn("环境变量", origin)

    def test_find_ijob_script_raises_structured_error_when_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = dict(os.environ)
            env.pop(EMIT.IJOB_SCRIPT_ENV, None)
            with mock.patch.dict(os.environ, env, clear=True), \
                 mock.patch.object(EMIT.os.path, "isfile", return_value=False):
                with self.assertRaises(EMIT.IjobContractError) as ctx:
                    EMIT.find_ijob_script()
        self.assertEqual(ctx.exception.code, "ijob_skill_not_found")
        self.assertIn("IJOB_SKILL_SCRIPT", json.dumps(ctx.exception.details, ensure_ascii=False))

    def test_fetch_brief_items_pages_until_total_is_consumed(self):
        """brief 单页上限 100；必须翻页拉完，不能只取第一页。"""
        pages = {
            0: [brief_item(campaign_id=i) for i in range(1, 101)],
            100: [brief_item(campaign_id=i) for i in range(101, 151)],
        }
        calls = []

        def fake_page(script, offset, limit, timeout=None):
            calls.append((script, offset, limit))
            items = pages.get(offset, [])
            return {"total": 150, "limit": limit, "offset": offset, "items": items}

        with mock.patch.object(EMIT, "call_ijob_brief_page", side_effect=fake_page):
            rows = EMIT.fetch_brief_items(script="/tmp/ijob.py")
        self.assertEqual(len(rows), 150)
        self.assertEqual([c[1] for c in calls], [0, 100])
        self.assertTrue(all(c[2] <= 100 for c in calls), "分页 limit 必须不超过契约上限 100")
        self.assertEqual(rows[-1]["cid"], 150)

    def test_fetch_brief_items_uses_sys_executable_and_brief_operation(self):
        seen = {}

        def fake_run(cmd, **kwargs):
            seen["cmd"] = cmd
            seen["kwargs"] = kwargs
            payload = brief_envelope([brief_item()])
            return subprocess.CompletedProcess(cmd, 0, json.dumps(payload), "")

        with mock.patch.object(EMIT.subprocess, "run", side_effect=fake_run):
            EMIT.fetch_brief_items(script="/tmp/ijob.py")
        self.assertEqual(seen["cmd"], [sys.executable, "/tmp/ijob.py", "brief",
                                       "--limit", "100", "--offset", "0"])
        self.assertIn("timeout", seen["kwargs"])
        self.assertTrue(seen["kwargs"]["timeout"])

    def test_contract_error_is_raised_not_treated_as_empty_data(self):
        payload = brief_envelope([], error={
            "code": "semantics_incompatible", "message": "语义版本不兼容",
            "details": {"expected": 3}})
        with mock.patch.object(EMIT.subprocess, "run",
                               return_value=subprocess.CompletedProcess([], 2, json.dumps(payload), "")):
            with self.assertRaises(EMIT.IjobContractError) as ctx:
                EMIT.fetch_brief_items(script="/tmp/ijob.py")
        self.assertEqual(ctx.exception.code, "semantics_incompatible")
        self.assertIn("语义版本不兼容", ctx.exception.message)

    def test_envelope_contract_and_operation_are_validated(self):
        for bad, code in (
            (brief_envelope([brief_item()], contract="something.else"), "ijob_contract_mismatch"),
            (brief_envelope([brief_item()], operation="info"), "ijob_operation_mismatch"),
            (brief_envelope([brief_item()], contract="ijob.skill"), "ijob_contract_mismatch"),
        ):
            with mock.patch.object(EMIT.subprocess, "run",
                                   return_value=subprocess.CompletedProcess([], 0, json.dumps(bad), "")):
                with self.assertRaises(EMIT.IjobContractError) as ctx:
                    EMIT.fetch_brief_items(script="/tmp/ijob.py")
            self.assertEqual(ctx.exception.code, code)

    def test_skill_error_envelope_is_forwarded_but_never_treated_as_data(self):
        payload = brief_envelope([], error={
            "code": "ijob_home_invalid", "message": "显式 ijob home 无效",
            "details": {"source": "explicit"}})
        payload["contract"] = "ijob.skill"
        with mock.patch.object(EMIT.subprocess, "run",
                               return_value=subprocess.CompletedProcess([], 2, json.dumps(payload), "")):
            with self.assertRaises(EMIT.IjobContractError) as ctx:
                EMIT.fetch_brief_items(script="/tmp/ijob.py")
        self.assertEqual(ctx.exception.code, "ijob_home_invalid")
        self.assertEqual(ctx.exception.details.get("source"), "explicit")

    def test_public_success_requires_version_and_read_only_metadata(self):
        mutations = (
            lambda payload: payload.pop("schema_version"),
            lambda payload: payload.update(schema_version="2.0.0"),
            lambda payload: payload["meta"].pop("read_only"),
            lambda payload: payload["meta"].update(read_only=False),
            lambda payload: payload["meta"].update(source="other"),
        )
        for mutate in mutations:
            payload = brief_envelope([brief_item()])
            mutate(payload)
            with mock.patch.object(EMIT.subprocess, "run",
                                   return_value=subprocess.CompletedProcess([], 0, json.dumps(payload), "")):
                with self.assertRaises(EMIT.IjobContractError) as ctx:
                    EMIT.fetch_brief_items(script="/tmp/ijob.py")
            self.assertIn(ctx.exception.code, {"ijob_invalid_response", "ijob_contract_incompatible"})

    def test_missing_items_or_total_is_rejected(self):
        for mutate in (lambda d: d.pop("items"), lambda d: d.pop("total")):
            payload = brief_envelope([brief_item()])
            mutate(payload["data"])
            with mock.patch.object(EMIT.subprocess, "run",
                                   return_value=subprocess.CompletedProcess([], 0, json.dumps(payload), "")):
                with self.assertRaises(EMIT.IjobContractError) as ctx:
                    EMIT.fetch_brief_items(script="/tmp/ijob.py")
            self.assertEqual(ctx.exception.code, "ijob_invalid_response")

    def test_invalid_json_is_rejected_with_stderr_hint(self):
        proc = subprocess.CompletedProcess([], 1, "not json", "boom: traceback")
        with mock.patch.object(EMIT.subprocess, "run", return_value=proc):
            with self.assertRaises(EMIT.IjobContractError) as ctx:
                EMIT.fetch_brief_items(script="/tmp/ijob.py")
        self.assertEqual(ctx.exception.code, "ijob_invalid_response")
        self.assertIn("boom", json.dumps(ctx.exception.details, ensure_ascii=False))

    def test_timeout_is_reported_explicitly(self):
        with mock.patch.object(EMIT.subprocess, "run",
                               side_effect=subprocess.TimeoutExpired(cmd="ijob", timeout=300)):
            with self.assertRaises(EMIT.IjobContractError) as ctx:
                EMIT.fetch_brief_items(script="/tmp/ijob.py")
        self.assertEqual(ctx.exception.code, "ijob_timeout")

    def test_legacy_adapter_normalises_contract_fields(self):
        row = EMIT.to_legacy_row(brief_item(
            campaign_id=42, content_state="written", article_length=1200,
            article_search_text="正文关键词", cet_requirement=None, wechat_url=""))
        self.assertEqual(row["cid"], 42)
        self.assertEqual(row["id"], 42)
        self.assertEqual(row["html_len"], 1200)
        self.assertEqual(row["rh"], "正文关键词")
        self.assertEqual(row["content_state"], "written")
        # 契约允许 null；legacy row 内部统一空串，避免下游 None 判断
        self.assertEqual(row["cet_requirement"], "")
        self.assertEqual(row["medical_veto_rules"], "")

    def test_paging_never_silently_truncates(self):
        # 服务端永远返回满页但 total 巨大 → 必须显式报错，不能假装拉完了
        with mock.patch.object(EMIT, "call_ijob_brief_page",
                               return_value={"total": 10 ** 6, "limit": 100, "offset": 0,
                                             "items": [brief_item(campaign_id=1)]}):
            with self.assertRaises(EMIT.IjobContractError) as ctx:
                EMIT.fetch_brief_items(script="/tmp/ijob.py", page_limit=1, max_pages=3)
        self.assertEqual(ctx.exception.code, "ijob_paging_exhausted")


class OutputWordingTests(unittest.TestCase):
    """输出文案不得泄露数据库路径/表名，补数口径统一。"""

    def render(self, **overrides):
        return EMIT.build_briefing(EMIT.to_legacy_row(brief_item(**overrides)), "2026-09-25 21:00")

    def test_briefing_text_has_no_database_paths_or_table_names(self):
        text = self.render()
        for banned in ("jobs.db", "src/ijob", "campaigns", "campaign_articles",
                       "companies", "rendered_html", "apply_url", "announcement_url"):
            self.assertNotIn(banned, text)
        self.assertIn("ijob 稳定只读契约", text)

    def test_briefing_uses_unified_backfill_wording(self):
        text = self.render(deadline=EMIT.PLACEHOLDER_DEADLINE)
        self.assertIn("回 ijob 项目按其交接规则回填并复核", text)
        self.assertNotIn("回填 `jobs.db`", text)

    def test_briefing_marks_vague_deadline_and_routes_backfill_to_ijob(self):
        text = self.render(deadline="2026-11-30", batch_type="待核批次")
        self.assertIn("暂不可动笔", text)
        self.assertIn("ijob 为软词", text)
        self.assertIn("回 ijob 项目按其交接规则回填并复核", text)


if __name__ == "__main__":
    unittest.main()
