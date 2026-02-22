from __future__ import annotations

from pathlib import Path

from tests.snapshot_helpers import render_simple_project_snapshot

FIXTURE_DIR = Path(__file__).parent / "integration" / "fixtures"


def test_simple_project_expected_snapshots_are_in_sync(tmp_path: Path, monkeypatch) -> None:
    """Fast guard against fixture/snapshot drift in non-integration test lanes."""
    expected_dir = FIXTURE_DIR / "expected"
    cases = [
        ("md", "bundle.md", "simple_project.md"),
        ("xml", "bundle.xml", "simple_project.xml"),
        ("jsonl", "bundle.jsonl", "simple_project.jsonl"),
    ]

    for fmt, out_name, expected_name in cases:
        actual = render_simple_project_snapshot(
            tmp_path / fmt,
            FIXTURE_DIR,
            fmt,
            out_name,
            monkeypatch,
        )
        expected = (expected_dir / expected_name).read_text(encoding="utf-8")
        assert actual == expected, f"{fmt} snapshot fixture drifted: {expected_name}"
