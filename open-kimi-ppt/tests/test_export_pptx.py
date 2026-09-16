#!/usr/bin/env python3
import importlib.util
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "export_pptx.py"
SPEC = importlib.util.spec_from_file_location("export_pptx", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class ExportPptxTests(unittest.TestCase):
    def test_parse_agent_browser_version(self):
        self.assertEqual(MODULE.parse_version("agent-browser 0.33.2"), (0, 33, 2))
        self.assertEqual(MODULE.parse_version("v1.4.0-beta.1"), (1, 4, 0))

    @patch.object(MODULE.subprocess, "run")
    @patch.object(MODULE.shutil, "which")
    def test_old_agent_browser_is_upgraded(self, which, run):
        which.side_effect = ["/bin/agent-browser", "/bin/npm", "/bin/agent-browser"]
        run.side_effect = [
            MODULE.subprocess.CompletedProcess([], 0, "agent-browser 0.17.1\n"),
            MODULE.subprocess.CompletedProcess([], 0, "changed 1 package\n"),
            MODULE.subprocess.CompletedProcess([], 0, "agent-browser 0.33.2\n"),
        ]
        self.assertEqual(MODULE.ensure_agent_browser(), "/bin/agent-browser")
        self.assertEqual(run.call_args_list[1].args[0], [
            "/bin/npm", "install", "-g", "agent-browser@latest"
        ])

    def test_fade_is_inserted_before_timing(self):
        source = (
            b'<?xml version="1.0" encoding="UTF-8"?>'
            b'<p:sld xmlns:p="urn:test"><p:cSld><p:spTree><p:extLst/>'
            b'</p:spTree></p:cSld><p:clrMapOvr/><p:timing/><p:extLst/></p:sld>'
        )
        result_bytes = MODULE.replace_transition(source, "fade")
        result = result_bytes.decode("utf-8")
        self.assertIn("<p:transition", result)
        self.assertIn("<p:fade/>", result)
        self.assertGreater(result.index("<p:transition"), result.index("<p:clrMapOvr"))
        self.assertLess(result.index("<p:transition"), result.index("<p:timing"))
        MODULE.validate_transition_order(result_bytes, "fade")

    def test_existing_transition_is_replaced_or_removed(self):
        source = (
            b'<p:sld xmlns:p="urn:test"><p:cSld/>'
            b'<p:transition><p:wipe/></p:transition><p:extLst/></p:sld>'
        )
        faded = MODULE.replace_transition(source, "fade").decode("utf-8")
        self.assertNotIn("p:wipe", faded)
        self.assertEqual(faded.count("<p:transition"), 1)
        MODULE.validate_transition_order(faded.encode("utf-8"), "fade")
        cleared = MODULE.replace_transition(source, "none").decode("utf-8")
        self.assertNotIn("p:transition", cleared)
        MODULE.validate_transition_order(cleared.encode("utf-8"), "none")

    def test_nested_transition_is_relocated_to_slide_root(self):
        source = (
            b'<p:sld xmlns:p="urn:test"><p:cSld><p:spTree>'
            b'<p:transition><p:fade/></p:transition><p:extLst/>'
            b'</p:spTree></p:cSld><p:clrMapOvr/><p:extLst/></p:sld>'
        )
        result = MODULE.replace_transition(source, "fade")
        MODULE.validate_transition_order(result, "fade")
        self.assertEqual(MODULE.root_child_names(result), [
            "cSld", "clrMapOvr", "transition", "extLst"
        ])

    def test_patch_transitions_preserves_a_valid_zip(self):
        with tempfile.TemporaryDirectory() as name:
            deck = Path(name) / "test.pptx"
            with zipfile.ZipFile(deck, "w", zipfile.ZIP_DEFLATED) as archive:
                archive.writestr(
                    "[Content_Types].xml",
                    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                    '<Override PartName="/ppt/presentation.xml" '
                    f'ContentType="{MODULE.PPTX_CONTENT_TYPE}"/></Types>',
                )
                archive.writestr("ppt/presentation.xml", "<p:presentation xmlns:p=\"urn:test\"/>")
                archive.writestr(
                    "ppt/slides/slide1.xml",
                    '<p:sld xmlns:p="urn:test"><p:cSld/></p:sld>',
                )
            self.assertEqual(MODULE.patch_transitions(deck, "fade"), 1)
            with zipfile.ZipFile(deck) as archive:
                self.assertIsNone(archive.testzip())
                slide = archive.read("ppt/slides/slide1.xml")
                self.assertIn(b"<p:fade/>", slide)


if __name__ == "__main__":
    unittest.main()
