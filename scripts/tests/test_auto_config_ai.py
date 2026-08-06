from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parents[1]
sys.path.insert(0, str(SCRIPTS_DIR))

import auto_config_ai as A  # noqa: E402


def _skill(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "sample"
    path.mkdir()
    (path / "SKILL.md").write_text(
        f"---\nname: sample\ndescription: test\n---\n\n{body}\n",
        encoding="utf-8",
    )
    return path


def test_markdown_pip_parser_ignores_local_and_remote_targets(tmp_path):
    path = _skill(
        tmp_path,
        """
```bash
pip install -e .
pip install ./local-package
pip install https://example.com/archive.whl
pip install --index-url https://mirror.example/simple requests>=2 "yt-dlp[default]"
python3 -m pip install -U httpx
```
""",
    )

    assert A.parse_skill_md_deps(path)["pip"] == ["requests", "yt-dlp", "httpx"]


def test_registry_category_overrides_markdown_inference(tmp_path, monkeypatch):
    path = _skill(tmp_path, "pip install fake-package")
    monkeypatch.setitem(A.SKILL_DEPS, "sample", {"pip": ["requests"]})

    ok, missing = A.check_skill_deps("sample", path, {"requests"}, set())

    assert ok is True
    assert missing["pip"] == []


def test_doudian_local_install_is_not_reported_as_pip_package(monkeypatch):
    skill_path = Path(A.DEFAULT_SKILLS_DIR) / "dy-doudian"
    monkeypatch.setattr(A, "command_exists", lambda _name: True)

    ok, missing = A.check_skill_deps(
        "dy-doudian",
        skill_path,
        {"mcp", "httpx", "python-dotenv"},
        set(),
    )

    assert ok is True
    assert "." not in missing["pip"]
    assert ".[browser]" not in missing["pip"]


def test_missing_local_cli_recommends_project_install_only(capsys):
    missing = {"bins": ["dy-fanpai"], "pip": [], "npm": [], "env": []}
    install_cmds = A.SKILL_DEPS["dy-fanpai"]["install_cmds"]

    A.print_deps_report("dy-fanpai", missing, install_cmds)

    output = capsys.readouterr().out
    assert "cd dy-fanpai && pip install -e ." in output
    assert "brew install ffmpeg" not in output


def test_dry_run_treats_local_cli_as_pip_install():
    missing = {"bins": ["dy-fanpai"], "pip": [], "npm": [], "env": []}

    installed_pip, installed_npm, failed = A.install_missing_deps(
        "dy-fanpai", missing, dry_run=True,
    )

    assert installed_pip == ["."]
    assert installed_npm == []
    assert failed == []
