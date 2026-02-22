from __future__ import annotations

import os
import shutil
from pathlib import Path

from foldermix import packer
from foldermix.config import PackConfig

FIXTURE_DIR = Path(__file__).parent / "integration" / "fixtures"
FIXED_MTIME = 1704067200  # 2024-01-01T00:00:00+00:00
_TEXT_FIXTURE_EXTS = {".md", ".py", ".txt"}


def _set_fixed_mtime(root: Path) -> None:
    for p in root.rglob("*"):
        if p.is_file():
            os.utime(p, (FIXED_MTIME, FIXED_MTIME))


def _normalize_fixture_newlines_to_lf(root: Path) -> None:
    """Avoid CRLF checkout differences changing snapshot byte counts on Windows."""
    for p in root.rglob("*"):
        if not p.is_file() or p.suffix.lower() not in _TEXT_FIXTURE_EXTS:
            continue
        raw = p.read_bytes()
        normalized = raw.replace(b"\r\n", b"\n")
        if normalized != raw:
            p.write_bytes(normalized)


def _render_simple_project_snapshot(base_tmp: Path, fmt: str, out_name: str) -> str:
    base_tmp.mkdir(parents=True, exist_ok=True)
    src = FIXTURE_DIR / "simple_project"
    project_dir = base_tmp / "simple_project"
    shutil.copytree(src, project_dir)
    _normalize_fixture_newlines_to_lf(project_dir)
    _set_fixed_mtime(project_dir)

    original_utcnow_iso = packer.utcnow_iso
    try:
        packer.utcnow_iso = lambda: "2024-01-02T00:00:00+00:00"
        out_path = base_tmp / out_name
        config = PackConfig(
            root=project_dir,
            out=out_path,
            format=fmt,
            include_sha256=False,
            workers=1,
        )
        packer.pack(config)
    finally:
        packer.utcnow_iso = original_utcnow_iso

    return out_path.read_text(encoding="utf-8").replace(str(project_dir), "__ROOT__")


def test_simple_project_expected_snapshots_are_in_sync(tmp_path: Path) -> None:
    """Fast guard against fixture/snapshot drift in non-integration test lanes."""
    expected_dir = FIXTURE_DIR / "expected"
    cases = [
        ("md", "bundle.md", "simple_project.md"),
        ("xml", "bundle.xml", "simple_project.xml"),
        ("jsonl", "bundle.jsonl", "simple_project.jsonl"),
    ]

    for fmt, out_name, expected_name in cases:
        actual = _render_simple_project_snapshot(tmp_path / fmt, fmt, out_name)
        expected = (expected_dir / expected_name).read_text(encoding="utf-8")
        assert actual == expected, f"{fmt} snapshot fixture drifted: {expected_name}"
