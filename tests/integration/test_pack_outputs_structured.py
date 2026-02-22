from __future__ import annotations

from pathlib import Path

import pytest

from tests.snapshot_helpers import render_simple_project_snapshot

pytestmark = pytest.mark.integration

FIXTURE_DIR = Path(__file__).parent / "fixtures"


def test_xml_output_matches_fixture_snapshot(tmp_path: Path, monkeypatch) -> None:
    expected = (FIXTURE_DIR / "expected" / "simple_project.xml").read_text(encoding="utf-8")
    actual = render_simple_project_snapshot(tmp_path, FIXTURE_DIR, "xml", "bundle.xml", monkeypatch)
    assert actual == expected


def test_jsonl_output_matches_fixture_snapshot(tmp_path: Path, monkeypatch) -> None:
    expected = (FIXTURE_DIR / "expected" / "simple_project.jsonl").read_text(encoding="utf-8")
    actual = render_simple_project_snapshot(tmp_path, FIXTURE_DIR, "jsonl", "bundle.jsonl", monkeypatch)
    assert actual == expected
