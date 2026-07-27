from __future__ import annotations

import argparse
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "prepare_video_evidence.py"
SPEC = importlib.util.spec_from_file_location("prepare_video_evidence", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def parameters(**overrides):
    values = {
        "interval": 0.5,
        "frame_width": 360,
        "sheet_columns": 6,
        "scene_threshold": 0.2,
        "asr_model": None,
        "language": "zh",
    }
    values.update(overrides)
    return MODULE.requested_parameters(argparse.Namespace(**values))


def create_required_bundle(
    output_dir: Path,
    video_hash: str,
    requested: dict,
    *,
    status: str = "complete",
) -> None:
    evidence = output_dir / "evidence"
    frames = evidence / "frames"
    deliverables = output_dir / "deliverables"
    frames.mkdir(parents=True)
    deliverables.mkdir(parents=True)
    for path in MODULE.required_output_paths(
        output_dir,
        require_asr=bool(requested.get("asr_model")),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"data")
    (frames / "frame_000000000ms.jpg").write_bytes(b"frame")
    manifest = {
        "status": status,
        "source": {"sha256": video_hash},
        "parameters": requested,
        "components": {
            "asr": "complete" if requested.get("asr_model") else "skipped",
        },
    }
    (evidence / "evidence-manifest.json").write_text(
        json.dumps(manifest),
        encoding="utf-8",
    )


class EvidencePreparationTests(unittest.TestCase):
    def test_metadata_must_match_video_sha256(self):
        with tempfile.TemporaryDirectory() as directory:
            metadata = Path(directory) / "metadata.json"
            metadata.write_text(
                json.dumps(
                    {
                        "identity": {
                            "aweme_id": "123",
                            "canonical_url": "https://www.douyin.com/video/123",
                        },
                        "local_assets": [
                            {
                                "role": "video",
                                "path": "video.mp4",
                                "sha256": "a" * 64,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            identity = MODULE.validate_metadata_for_video(metadata, "a" * 64)
            self.assertEqual(identity["aweme_id"], "123")
            with self.assertRaisesRegex(RuntimeError, "SHA-256"):
                MODULE.validate_metadata_for_video(metadata, "b" * 64)

    def test_manifest_status_reflects_degraded_components(self):
        self.assertEqual(
            MODULE.evidence_bundle_status(
                "complete",
                "complete",
                "skipped",
                asr_requested=False,
            ),
            "complete",
        )
        self.assertEqual(
            MODULE.evidence_bundle_status(
                "failed",
                "complete",
                "skipped",
                asr_requested=False,
            ),
            "partial",
        )
        self.assertEqual(
            MODULE.evidence_bundle_status(
                "complete",
                "complete",
                "unavailable",
                asr_requested=True,
            ),
            "partial",
        )

    def test_reuse_requires_complete_manifest_parameters_and_files(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "analysis"
            requested = parameters()
            create_required_bundle(output, "a" * 64, requested)
            self.assertEqual(
                MODULE.existing_output_state(output, "a" * 64, requested),
                "reuse",
            )
            (output / "evidence" / "contact-sheet.jpg").unlink()
            self.assertEqual(
                MODULE.existing_output_state(output, "a" * 64, requested),
                "rebuild",
            )

    def test_partial_bundle_is_rebuilt(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "analysis"
            requested = parameters()
            create_required_bundle(output, "a" * 64, requested, status="partial")
            self.assertEqual(
                MODULE.existing_output_state(output, "a" * 64, requested),
                "rebuild",
            )

    def test_publish_replaces_same_source_output_after_staging_completes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "analysis"
            staging = root / ".analysis.staging-test"
            output.mkdir()
            staging.mkdir()
            (output / "old.txt").write_text("old", encoding="utf-8")
            (staging / "new.txt").write_text("new", encoding="utf-8")
            MODULE.publish_output(staging, output)
            self.assertFalse((output / "old.txt").exists())
            self.assertEqual((output / "new.txt").read_text(encoding="utf-8"), "new")
            self.assertFalse(staging.exists())


if __name__ == "__main__":
    unittest.main()
