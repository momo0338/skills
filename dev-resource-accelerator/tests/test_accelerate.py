from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest


SCRIPT = Path(__file__).parents[1] / "scripts" / "accelerate.py"
SPEC = importlib.util.spec_from_file_location("dev_resource_accelerate", SCRIPT)
assert SPEC and SPEC.loader
A = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = A
SPEC.loader.exec_module(A)


PUBLIC_REPO = "https://github.com/octocat/Hello-World.git"
PUBLIC_ARCHIVE = "https://github.com/octocat/Hello-World/archive/refs/heads/master.zip"


def config():
    return A.load_config(Path(__file__).parents[1] / "references" / "mirrors.json")


def test_download_candidates_are_mirror_first_and_direct_last():
    candidates = A.build_candidates(PUBLIC_ARCHIVE, "download", config())

    assert candidates[0].name == "ghfast.top"
    assert candidates[0].url.startswith("https://ghfast.top/https://github.com/")
    assert candidates[-1] == A.Candidate("github-direct", PUBLIC_ARCHIVE, False)


def test_clone_candidates_include_gitclone_and_direct():
    candidates = A.build_candidates(PUBLIC_REPO, "clone", config())

    assert any(c.url == "https://gitclone.com/github.com/octocat/Hello-World.git" for c in candidates)
    assert candidates[-1].url == PUBLIC_REPO


@pytest.mark.parametrize(
    "url",
    [
        "git@github.com:owner/private.git",
        "ssh://git@github.com/owner/private.git",
        "https://user:pass@github.com/owner/repo.git",
        "https://api.github.com/repos/owner/repo",
        "https://github.com/owner/repo.git?token=secret",
        "https://github.com/owner/repo.git?access_token=secret",
        "https://github.com/owner/repo/ghp_abcdefghijklmnopqrstuvwxyz",
        "https://example.com/owner/repo.git",
    ],
)
def test_sensitive_or_unsupported_urls_are_rejected(url):
    with pytest.raises(A.AcceleratorError):
        A.build_candidates(url, "auto", config())


def test_network_operations_require_public_confirmation():
    with pytest.raises(A.AcceleratorError):
        A.public_required(False)


def test_unsafe_mirror_registry_is_rejected():
    unsafe = config()
    unsafe["github"]["prefix_mirrors"][0]["base_url"] = "http://mirror.example/"

    with pytest.raises(A.AcceleratorError):
        A.build_candidates(PUBLIC_ARCHIVE, "download", unsafe)


def test_download_rejects_clone_url(tmp_path):
    with patch.object(A, "ensure_binary"):
        with pytest.raises(A.AcceleratorError):
            A.download_public(PUBLIC_REPO, tmp_path / "repo.git", timeout=10, config=config())


def test_download_falls_back_and_atomically_publishes(tmp_path):
    output = tmp_path / "asset.zip"
    calls = []

    def fake_run(command, *, timeout):
        calls.append(command[-1])
        if len(calls) == 1:
            return subprocess.CompletedProcess(command, 22, "", "first failed")
        temp_path = Path(command[command.index("--output") + 1])
        temp_path.write_bytes(b"ok")
        return subprocess.CompletedProcess(command, 0, "", "")

    with patch.object(A, "ensure_binary"), patch.object(A, "run_command", side_effect=fake_run):
        selected = A.download_public(PUBLIC_ARCHIVE, output, timeout=10, config=config())

    assert selected.name == "gh-proxy.com"
    assert output.read_bytes() == b"ok"
    assert len(calls) == 2


def test_empty_download_is_not_published(tmp_path):
    output = tmp_path / "asset.zip"

    def fake_run(command, *, timeout):
        return subprocess.CompletedProcess(command, 0, "", "")

    with patch.object(A, "ensure_binary"), patch.object(A, "run_command", side_effect=fake_run):
        with pytest.raises(A.AcceleratorError):
            A.download_public(PUBLIC_ARCHIVE, output, timeout=10, config=config())

    assert not output.exists()


def test_clone_falls_back_without_leaving_partial_destination(tmp_path):
    destination = tmp_path / "repo"
    calls = []

    def fake_run(command, *, timeout):
        calls.append(command[-2])
        temp_repo = Path(command[-1])
        if len(calls) == 1:
            temp_repo.mkdir(parents=True)
            (temp_repo / "partial").write_text("partial", encoding="utf-8")
            return subprocess.CompletedProcess(command, 1, "", "first failed")
        temp_repo.mkdir(parents=True)
        (temp_repo / "complete").write_text("complete", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, "", "")

    with patch.object(A, "ensure_binary"), patch.object(A, "run_command", side_effect=fake_run):
        selected = A.clone_public(PUBLIC_REPO, destination, timeout=10, depth=1, config=config())

    assert selected.name == "gh-proxy.com"
    assert not (destination / "partial").exists()
    assert (destination / "complete").read_text(encoding="utf-8") == "complete"


def test_existing_output_and_clone_destination_are_refused(tmp_path):
    existing_file = tmp_path / "asset.zip"
    existing_file.write_bytes(b"user data")
    existing_dir = tmp_path / "repo"
    existing_dir.mkdir()

    with pytest.raises(A.AcceleratorError):
        A.download_public(PUBLIC_ARCHIVE, existing_file, timeout=10, config=config())
    with pytest.raises(A.AcceleratorError):
        A.clone_public(PUBLIC_REPO, existing_dir, timeout=10, depth=None, config=config())


def test_clone_falls_back_when_parent_not_writable(tmp_path, monkeypatch):
    fallback = tmp_path / "fallback"
    fallback.mkdir()
    requested = tmp_path / "outside" / "repo"

    with patch.object(A, "writable_parent", side_effect=[False, True]):
        destination = A.resolve_destination(requested, fallback, kind="dir")

    assert destination.parent == fallback
    assert destination.name == "repo-accelerate"
    assert destination.is_dir()


def test_download_falls_back_when_parent_not_writable(tmp_path):
    fallback = tmp_path / "fallback"
    fallback.mkdir()
    requested = tmp_path / "outside" / "asset.zip"

    with patch.object(A, "writable_parent", side_effect=[False, True]):
        destination = A.resolve_destination(requested, fallback, kind="file")

    assert destination.parent == fallback
    assert destination.name == "asset.zip.accelerate"


def test_resolve_destination_without_fallback_raises(tmp_path):
    requested = tmp_path / "outside" / "repo"
    with patch.object(A, "writable_parent", return_value=False):
        with pytest.raises(A.AcceleratorError):
            A.resolve_destination(requested, None, kind="dir")
