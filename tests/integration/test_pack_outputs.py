from __future__ import annotations

from pathlib import Path

import pytest

from tests.snapshot_helpers import render_simple_project_snapshot

pytestmark = pytest.mark.integration

FIXTURE_DIR = Path(__file__).parent / "fixtures"


def test_markdown_output_matches_fixture_snapshot(tmp_path: Path, monkeypatch) -> None:
    expected_path = FIXTURE_DIR / "expected" / "simple_project.md"
    actual = render_simple_project_snapshot(tmp_path, FIXTURE_DIR, "md", "bundle.md", monkeypatch)
    expected = expected_path.read_text(encoding="utf-8")
    assert actual == expected
