from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def sample_dir(tmp_path: Path) -> Path:
    """Create a sample directory structure for testing."""
    # Create some sample files
    (tmp_path / "sample.txt").write_text("Hello, world!\nThis is a text file.")
    (tmp_path / "sample.md").write_text("# Title\n\nSome markdown content.")
    (tmp_path / "sample.json").write_text('{"key": "value", "number": 42}')
    (tmp_path / "sample.csv").write_text("name,age,city\nAlice,30,NYC\nBob,25,LA")

    # Nested directory
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "child.txt").write_text("I am a child file.")

    # Excluded directory
    excluded = tmp_path / "excluded_dir"
    excluded.mkdir()
    (excluded / "ignored.txt").write_text("I should be excluded.")

    # Binary-like file
    (tmp_path / "image.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

    # Hidden file
    (tmp_path / ".hidden").write_text("hidden content")

    # Large file placeholder
    (tmp_path / "huge.txt").write_text("x" * 1000)

    return tmp_path
