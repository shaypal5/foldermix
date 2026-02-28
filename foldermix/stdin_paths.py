from __future__ import annotations

import os
import sys
from pathlib import Path


def parse_stdin_paths(data: bytes, *, null_delimited: bool, cwd: Path | None = None) -> list[Path]:
    base = (cwd or Path.cwd()).resolve()
    text = data.decode(sys.getfilesystemencoding(), errors="surrogateescape")
    raw_items = text.split("\0") if null_delimited else text.splitlines()

    resolved: list[Path] = []
    seen: set[str] = set()
    for raw_item in raw_items:
        item = raw_item if null_delimited else raw_item.rstrip("\r")
        if not item:
            continue
        path = Path(item).expanduser()
        if not path.is_absolute():
            path = base / path
        normalized = path.resolve(strict=False)
        dedupe_key = os.path.normcase(str(normalized))
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        resolved.append(normalized)
    return resolved
