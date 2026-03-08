from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "open_release_pr.py"
    spec = importlib.util.spec_from_file_location("open_release_pr", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


release_pr = _load_module()


def test_disallowed_worktree_changes_ignores_uv_lock_only() -> None:
    status_output = "?? uv.lock\n M README.md\n?? notes.txt\n"
    assert release_pr.disallowed_worktree_changes(status_output) == [
        " M README.md",
        "?? notes.txt",
    ]


def test_bump_version_supports_patch_minor_and_major() -> None:
    assert release_pr.bump_version("1.2.3", "patch") == "1.2.4"
    assert release_pr.bump_version("1.2.3", "minor") == "1.3.0"
    assert release_pr.bump_version("1.2.3", "major") == "2.0.0"


def test_replace_project_version_updates_first_project_version_only() -> None:
    pyproject_text = "\n".join(
        [
            "[project]",
            'name = "foldermix"',
            'version = "0.1.18"',
            "",
            "[tool.example]",
            'version = "leave-me-alone"',
            "",
        ]
    )

    updated = release_pr.replace_project_version(pyproject_text, "0.1.19")

    assert 'version = "0.1.19"' in updated
    assert 'version = "leave-me-alone"' in updated


def test_read_current_version_extracts_project_version() -> None:
    pyproject_text = "\n".join(
        [
            "[project]",
            'name = "foldermix"',
            'version = "0.1.18"',
            "",
        ]
    )

    assert release_pr.read_current_version(pyproject_text) == "0.1.18"
