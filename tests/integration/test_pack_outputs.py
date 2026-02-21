from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

from foldermix import packer
from foldermix.config import PackConfig

pytestmark = pytest.mark.integration

FIXTURE_DIR = Path(__file__).parent / "fixtures"
FIXED_MTIME = 1704067200  # 2024-01-01T00:00:00+00:00


def _set_fixed_mtime(root: Path) -> None:
    for p in root.rglob("*"):
        if p.is_file():
            os.utime(p, (FIXED_MTIME, FIXED_MTIME))


def test_markdown_output_matches_fixture_snapshot(tmp_path: Path, monkeypatch) -> None:
    src = FIXTURE_DIR / "simple_project"
    expected_path = FIXTURE_DIR / "expected" / "simple_project.md"
    project_dir = tmp_path / "simple_project"
    shutil.copytree(src, project_dir)
    _set_fixed_mtime(project_dir)

    monkeypatch.setattr(packer, "utcnow_iso", lambda: "2024-01-02T00:00:00+00:00")

    out_path = tmp_path / "bundle.md"
    config = PackConfig(
        root=project_dir,
        out=out_path,
        format="md",
        include_sha256=False,
        workers=1,
    )
    packer.pack(config)

    actual = out_path.read_text(encoding="utf-8").replace(str(project_dir), "__ROOT__")
    expected = expected_path.read_text(encoding="utf-8")
    assert actual == expected
