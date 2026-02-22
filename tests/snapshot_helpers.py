from __future__ import annotations

import os
import shutil
from pathlib import Path

from foldermix import packer
from foldermix.config import PackConfig

FIXED_MTIME = 1704067200  # 2024-01-01T00:00:00+00:00
FIXED_NOW_ISO = "2024-01-02T00:00:00+00:00"
_TEXT_FIXTURE_EXTS = {".md", ".py", ".txt"}


def set_fixed_mtime(root: Path) -> None:
    for p in root.rglob("*"):
        if p.is_file():
            os.utime(p, (FIXED_MTIME, FIXED_MTIME))


def normalize_fixture_newlines_to_lf(root: Path) -> None:
    """Avoid CRLF checkout differences changing snapshot byte counts on Windows."""
    for p in root.rglob("*"):
        if not p.is_file() or p.suffix.lower() not in _TEXT_FIXTURE_EXTS:
            continue
        raw = p.read_bytes()
        normalized = raw.replace(b"\r\n", b"\n")
        if normalized != raw:
            p.write_bytes(normalized)


def normalize_root_path(text: str, project_dir: Path) -> str:
    """Normalize root path placeholders for plain and JSON-escaped path forms."""
    raw_root = str(project_dir)
    normalized = text.replace(raw_root, "__ROOT__")
    escaped_root = raw_root.replace("\\", "\\\\")
    if escaped_root != raw_root:
        normalized = normalized.replace(escaped_root, "__ROOT__")
    return normalized


def render_simple_project_snapshot(
    base_tmp: Path,
    fixture_dir: Path,
    fmt: str,
    out_name: str,
    monkeypatch,
) -> str:
    base_tmp.mkdir(parents=True, exist_ok=True)
    src = fixture_dir / "simple_project"
    project_dir = base_tmp / "simple_project"
    shutil.copytree(src, project_dir)
    normalize_fixture_newlines_to_lf(project_dir)
    set_fixed_mtime(project_dir)

    monkeypatch.setattr(packer, "utcnow_iso", lambda: FIXED_NOW_ISO)
    out_path = base_tmp / out_name
    config = PackConfig(
        root=project_dir,
        out=out_path,
        format=fmt,
        include_sha256=False,
        workers=1,
    )
    packer.pack(config)

    return normalize_root_path(out_path.read_text(encoding="utf-8"), project_dir)
