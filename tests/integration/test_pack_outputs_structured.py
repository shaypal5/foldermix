from __future__ import annotations

import os
import shutil
from pathlib import Path

from foldermix import packer
from foldermix.config import PackConfig

FIXTURE_DIR = Path(__file__).parent / "fixtures"
FIXED_MTIME = 1704067200  # 2024-01-01T00:00:00+00:00


def _set_fixed_mtime(root: Path) -> None:
    for p in root.rglob("*"):
        if p.is_file():
            os.utime(p, (FIXED_MTIME, FIXED_MTIME))


def _run_and_normalize(
    tmp_path: Path,
    monkeypatch,
    fmt: str,
    out_name: str,
) -> str:
    src = FIXTURE_DIR / "simple_project"
    project_dir = tmp_path / "simple_project"
    shutil.copytree(src, project_dir)
    _set_fixed_mtime(project_dir)
    monkeypatch.setattr(packer, "utcnow_iso", lambda: "2024-01-02T00:00:00+00:00")

    out_path = tmp_path / out_name
    config = PackConfig(
        root=project_dir,
        out=out_path,
        format=fmt,
        include_sha256=False,
        workers=1,
    )
    packer.pack(config)
    return out_path.read_text(encoding="utf-8").replace(str(project_dir), "__ROOT__")


def test_xml_output_matches_fixture_snapshot(tmp_path: Path, monkeypatch) -> None:
    expected = (FIXTURE_DIR / "expected" / "simple_project.xml").read_text(encoding="utf-8")
    actual = _run_and_normalize(tmp_path, monkeypatch, "xml", "bundle.xml")
    assert actual == expected


def test_jsonl_output_matches_fixture_snapshot(tmp_path: Path, monkeypatch) -> None:
    expected = (FIXTURE_DIR / "expected" / "simple_project.jsonl").read_text(encoding="utf-8")
    actual = _run_and_normalize(tmp_path, monkeypatch, "jsonl", "bundle.jsonl")
    assert actual == expected
