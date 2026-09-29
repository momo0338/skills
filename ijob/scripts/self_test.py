#!/usr/bin/env python3
"""ijob 技能适配器自检；不连接真实 ijob 主库。"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from subprocess import CompletedProcess

SCRIPT = Path(__file__).with_name("ijob.py")
SPEC = importlib.util.spec_from_file_location("ijob_skill", SCRIPT)
IJOB = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(IJOB)


def make_fake_home(root: Path) -> Path:
    home = Path(root)
    api = home / "api"
    api.mkdir(parents=True, exist_ok=True)
    (api / "contract.py").write_text("", encoding="utf-8")
    (api / "public_contract.json").write_text("{}", encoding="utf-8")
    (api / "public_contract.schema.json").write_text("{}", encoding="utf-8")
    return home.resolve()


def public_payload(**overrides) -> dict:
    payload = {
        "schema_version": "1.0.0",
        "contract": "ijob.public",
        "operation": "status",
        "generated_at": "2026-09-25T20:00:00+08:00",
        "data": {},
        "meta": {
            "read_only": True,
            "source": "ijob",
            "campaign_semantics_version": 3,
        },
        "warnings": [],
    }
    payload.update(overrides)
    return payload


class SkillAdapterTests(unittest.TestCase):
    def test_discovery_prefers_explicit_home(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = make_fake_home(tmp)
            self.assertEqual(IJOB.discover_home(str(home)), home)

    def test_discovery_reads_user_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = make_fake_home(Path(tmp) / "ijob")
            config_dir = Path(tempfile.mkdtemp()) / ".config" / "ijob"
            config_dir.mkdir(parents=True)
            config = config_dir / "config.json"
            config.write_text(json.dumps({"ijob_home": str(home)}), encoding="utf-8")
            with mock.patch.object(Path, "home", return_value=config_dir.parent.parent), \
                 mock.patch.dict(os.environ, {}, clear=True), \
                 mock.patch.object(IJOB.shutil, "which", return_value=None):
                self.assertEqual(IJOB.discover_home(), home)

    def test_explicit_invalid_home_does_not_fall_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            good = make_fake_home(Path(tmp) / "good")
            bad = Path(tmp) / "bad"
            bad.mkdir()
            with mock.patch.dict(os.environ, {"IJOB_HOME": str(good)}, clear=False):
                with self.assertRaises(IJOB.SkillError) as ctx:
                    IJOB.discover_home(str(bad))
            self.assertEqual(ctx.exception.code, "ijob_home_invalid")
            self.assertEqual(ctx.exception.details["source"], "explicit")

    def test_invalid_environment_home_does_not_fall_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            make_fake_home(Path(tmp) / "good")
            bad = Path(tmp) / "bad"
            bad.mkdir()
            with mock.patch.dict(os.environ, {"IJOB_HOME": str(bad)}, clear=False):
                with self.assertRaises(IJOB.SkillError) as ctx:
                    IJOB.discover_home()
            self.assertEqual(ctx.exception.code, "ijob_home_invalid")
            self.assertEqual(ctx.exception.details["source"], "environment")

    def test_explicit_invalid_home_reports_json_in_main(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad"
            bad.mkdir()
            with mock.patch.dict(os.environ, {}, clear=True):
                stdout = io.StringIO()
                with contextlib.redirect_stdout(stdout):
                    code = IJOB.main(["discover", "--ijob-home", str(bad)])
            payload = json.loads(stdout.getvalue())
        self.assertEqual(code, 2)
        self.assertEqual(payload["contract"], "ijob.skill")
        self.assertEqual(payload["error"]["code"], "ijob_home_invalid")

    def test_same_major_newer_minor_is_accepted(self):
        payload = public_payload(schema_version="1.7.3")
        self.assertEqual(IJOB.validate_envelope(payload), payload)

    def test_contract_incompatible_is_rejected(self):
        payload = public_payload(schema_version="2.0.0")
        with self.assertRaises(IJOB.SkillError) as ctx:
            IJOB.validate_envelope(payload)
        self.assertEqual(ctx.exception.code, "contract_incompatible")

    def test_below_minimum_minor_is_rejected(self):
        payload = public_payload(schema_version="0.9.0")
        with self.assertRaises(IJOB.SkillError) as ctx:
            IJOB.validate_envelope(payload)
        self.assertEqual(ctx.exception.code, "contract_incompatible")

    def test_mismatched_semantics_version_is_rejected(self):
        payload = public_payload()
        payload["meta"]["campaign_semantics_version"] = 2
        with self.assertRaises(IJOB.SkillError) as ctx:
            IJOB.validate_envelope(payload)
        self.assertEqual(ctx.exception.code, "semantics_incompatible")

    def test_public_error_envelope_is_validated(self):
        payload = public_payload(
            operation="info",
            data=None,
            error={
                "code": "semantics_incompatible",
                "message": "ijob 招聘业务语义不可用",
                "retryable": False,
                "details": {"expected_schema_version": 3},
            },
        )
        self.assertEqual(IJOB.validate_envelope(payload), payload)

    def test_skill_error_envelope_is_validated(self):
        payload = IJOB.make_skill_error(
            "status", IJOB.SkillError("ijob_home_not_found", "未发现 ijob")
        )
        self.assertEqual(IJOB.validate_envelope(payload), payload)
        self.assertEqual(payload["meta"]["source"], "ijob.skill")
        self.assertEqual(payload["meta"]["campaign_semantics_version"], 3)
        self.assertTrue(payload["meta"]["read_only"])
        self.assertTrue(payload["generated_at"])

    def test_contract_error_is_forwarded(self):
        payload = public_payload(
            operation="info",
            data=None,
            error={
                "code": "campaign_not_found",
                "message": "未找到招聘批次",
                "retryable": False,
                "details": {"campaign_id": 9},
            },
        )
        result = CompletedProcess([], 3, json.dumps(payload, ensure_ascii=False), "")
        with mock.patch.object(IJOB.subprocess, "run", return_value=result):
            with self.assertRaises(IJOB.SkillError) as ctx:
                IJOB.call_contract(Path("/tmp/ijob"), "info", [])
        self.assertEqual(ctx.exception.code, "campaign_not_found")
        self.assertEqual(ctx.exception.details["campaign_id"], 9)

    def test_locked_database_error_is_retryable(self):
        payload = public_payload(
            operation="health",
            data=None,
            error={
                "code": "database_locked",
                "message": "无法以只读方式打开 ijob 主库",
                "retryable": True,
                "details": {"sqlite_error": "database is locked"},
            },
        )
        result = CompletedProcess([], 2, json.dumps(payload, ensure_ascii=False), "")
        with mock.patch.object(IJOB.subprocess, "run", return_value=result):
            with self.assertRaises(IJOB.SkillError) as ctx:
                IJOB.call_contract(Path("/tmp/ijob"), "health", [])
        self.assertEqual(ctx.exception.code, "database_locked")

    def test_argparse_error_is_json_not_usage(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            with self.assertRaises(SystemExit) as ctx:
                IJOB.main(["nonexistent-operation"])
        payload = json.loads(stdout.getvalue())
        self.assertEqual(ctx.exception.code, 2)
        self.assertEqual(payload["contract"], "ijob.skill")
        self.assertEqual(payload["error"]["code"], "invalid_request")
        self.assertNotIn("usage:", stderr.getvalue())

    def test_info_requires_selector(self):
        with mock.patch.object(IJOB, "discover_home", return_value=Path("/tmp/ijob")), \
             mock.patch.object(IJOB.sys, "stdout"):
            code = IJOB.main(["info"])
        self.assertEqual(code, 2)

    def test_pure_numeric_query_is_passed_through_as_keyword(self):
        args = IJOB.build_parser().parse_args(["info", "--query", "2027"])
        self.assertEqual(IJOB.contract_arguments(args), ["--query", "2027"])

    # ── 写网关（2026-09-25 新增）────────────────────────────────
    def test_write_requires_write_op(self):
        with mock.patch.object(IJOB, "discover_home", return_value=Path("/tmp/ijob")), \
             mock.patch.object(IJOB.sys, "stdout"):
            code = IJOB.main(["write"])
        self.assertEqual(code, 2)

    def test_write_gate_rejects_non_ijob_write_contract(self):
        payload = json.dumps({"contract": "ijob.public", "schema_version": "1.0.0",
                              "data": {}, "meta": {"source": "ijob"}})
        fake = mock.Mock(returncode=0, stdout=payload, stderr="")
        with mock.patch.object(IJOB.subprocess, "run", return_value=fake):
            with self.assertRaises(IJOB.SkillError) as ctx:
                IJOB.call_write_gate(Path("/tmp/ijob"), write_op="probe", write_args=[],
                                      apply_=False)
        self.assertEqual(ctx.exception.code, "contract_mismatch")

    def test_write_gate_requires_mutating_meta(self):
        payload = json.dumps({"contract": "ijob.write", "schema_version": "1.0.0",
                              "data": {}, "meta": {"source": "ijob"}})
        fake = mock.Mock(returncode=0, stdout=payload, stderr="")
        with mock.patch.object(IJOB.subprocess, "run", return_value=fake):
            with self.assertRaises(IJOB.SkillError) as ctx:
                IJOB.call_write_gate(Path("/tmp/ijob"), write_op="probe", write_args=[],
                                      apply_=False)
        self.assertEqual(ctx.exception.code, "invalid_response")

    def test_write_gate_rejects_incompatible_version(self):
        payload = json.dumps({"contract": "ijob.write", "schema_version": "2.0.0",
                              "data": {}, "meta": {"source": "ijob", "mutating": True}})
        fake = mock.Mock(returncode=0, stdout=payload, stderr="")
        with mock.patch.object(IJOB.subprocess, "run", return_value=fake):
            with self.assertRaises(IJOB.SkillError) as ctx:
                IJOB.call_write_gate(Path("/tmp/ijob"), write_op="probe", write_args=[],
                                      apply_=False)
        self.assertEqual(ctx.exception.code, "contract_incompatible")

    def test_dry_run_must_not_produce_backup(self):
        payload = json.dumps({"contract": "ijob.write", "schema_version": "1.0.0",
                              "data": {"ok": True, "dry_run": True,
                                       "backup": {"path": "/tmp/x.db"}},
                              "meta": {"source": "ijob", "mutating": True}})
        fake = mock.Mock(returncode=0, stdout=payload, stderr="")
        with mock.patch.object(IJOB.subprocess, "run", return_value=fake):
            with self.assertRaises(IJOB.SkillError) as ctx:
                IJOB.call_write_gate(Path("/tmp/ijob"), write_op="probe", write_args=[],
                                      apply_=False)
        self.assertEqual(ctx.exception.code, "degraded_backup")

    def test_write_op_is_forwarded_and_apply_flag_added(self):
        seen = {}

        def fake_run(argv, **kwargs):
            seen["argv"] = argv
            return mock.Mock(returncode=0, stdout=json.dumps({
                "contract": "ijob.write", "schema_version": "1.0.0",
                "data": {"ok": True, "dry_run": False},
                "meta": {"source": "ijob", "mutating": True}}), stderr="")

        with mock.patch.object(IJOB.subprocess, "run", side_effect=fake_run):
            IJOB.call_write_gate(Path("/tmp/ijob"), write_op="promote",
                                  write_args=["2879", "2026-12-31"], apply_=True)
        self.assertIn("promote", seen["argv"])
        self.assertIn("--apply", seen["argv"])
        self.assertIn("2879", seen["argv"])
        self.assertIn("2026-12-31", seen["argv"])

    def test_readonly_operations_reject_write_flags(self):
        """只读 operation 携带 --apply/--write-op 必须报错，
        否则 `status --apply` 会被静默忽略，人以为写了其实没写。"""
        import io
        import contextlib
        for bad in (["status", "--apply"], ["next", "--write-op", "probe"],
                    ["inbox", "--write-arg", "1"]):
            with self.subTest(argv=bad):
                buf = io.StringIO()
                with mock.patch.object(IJOB, "discover_home",
                                       return_value=Path("/tmp/ijob")), \
                     contextlib.redirect_stdout(buf):
                    code = IJOB.main(bad)
                self.assertEqual(code, 2)
                payload = json.loads(buf.getvalue())
                self.assertEqual(payload["error"]["code"], "invalid_request")

    def test_readonly_operations_still_work_without_write_flags(self):
        """加了误用拦截后，纯只读调用不得受影响。"""
        args = IJOB.build_parser().parse_args(["status", "--limit", "5"])
        self.assertEqual(IJOB.contract_arguments(args), ["--limit", "5"])


if __name__ == "__main__":
    unittest.main()
