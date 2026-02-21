from __future__ import annotations

import fnmatch
import os
from dataclasses import dataclass
from pathlib import Path

import pathspec

from .config import PackConfig

SENSITIVE_PATTERNS: set[str] = {
    ".env",
    "*.pem",
    "*.key",
    "id_rsa",
    "id_dsa",
    "*.p12",
    "*.pfx",
    ".netrc",
}


@dataclass
class FileRecord:
    path: Path
    relpath: str
    ext: str
    size: int
    mtime: float
    is_binary: bool = False
    mime: str = ""
    sha256: str | None = None


@dataclass
class SkipRecord:
    relpath: str
    reason: str


def is_sensitive(name: str) -> bool:
    for pattern in SENSITIVE_PATTERNS:
        if fnmatch.fnmatch(name, pattern):
            return True
    return False


def scan(config: PackConfig) -> tuple[list[FileRecord], list[SkipRecord]]:
    """Walk root and return (included, skipped) file records."""
    included: list[FileRecord] = []
    skipped: list[SkipRecord] = []

    root = config.root.resolve()

    # Load gitignore
    gitignore_spec: pathspec.PathSpec | None = None
    if config.respect_gitignore:
        gitignore_path = root / ".gitignore"
        if gitignore_path.exists():
            patterns = gitignore_path.read_text().splitlines()
            gitignore_spec = pathspec.PathSpec.from_lines("gitwildmatch", patterns)

    # Determine include extensions
    include_exts: set[str] | None = None
    if config.include_ext:
        include_exts = {
            e.lower() if e.startswith(".") else f".{e.lower()}" for e in config.include_ext
        }

    exclude_exts = {e.lower() if e.startswith(".") else f".{e.lower()}" for e in config.exclude_ext}

    for dirpath_str, dirnames, filenames in os.walk(str(root), followlinks=config.follow_symlinks):
        dirpath = Path(dirpath_str)
        rel_dir = dirpath.relative_to(root)

        # Filter out excluded dirs in-place
        dirnames[:] = [
            d
            for d in sorted(dirnames)
            if (
                (config.hidden or not d.startswith("."))
                and d not in config.exclude_dirs
                and not (gitignore_spec and gitignore_spec.match_file(str(rel_dir / d) + "/"))
            )
        ]

        for filename in sorted(filenames):
            filepath = dirpath / filename
            rel_path = filepath.relative_to(root)
            rel_str = rel_path.as_posix()
            ext = filepath.suffix.lower()

            # Hidden files
            if not config.hidden and filename.startswith("."):
                skipped.append(SkipRecord(rel_str, "hidden"))
                continue

            # Sensitive files
            if is_sensitive(filename):
                skipped.append(SkipRecord(rel_str, "sensitive"))
                continue

            # gitignore
            if gitignore_spec and gitignore_spec.match_file(rel_str):
                skipped.append(SkipRecord(rel_str, "gitignored"))
                continue

            # Exclude glob
            excluded_by_glob = any(
                fnmatch.fnmatch(rel_str, pattern) for pattern in config.exclude_glob
            )

            # Include glob override
            included_by_glob = any(
                fnmatch.fnmatch(rel_str, pattern) for pattern in config.include_glob
            )

            if excluded_by_glob and not included_by_glob:
                skipped.append(SkipRecord(rel_str, "excluded_glob"))
                continue

            # Extension filters
            if not included_by_glob:
                if include_exts is not None and ext not in include_exts:
                    skipped.append(SkipRecord(rel_str, "excluded_ext"))
                    continue
                if ext in exclude_exts:
                    skipped.append(SkipRecord(rel_str, "excluded_ext"))
                    continue

            # Size check
            try:
                stat = filepath.stat()
                size = stat.st_size
                mtime = stat.st_mtime
            except OSError:
                skipped.append(SkipRecord(rel_str, "unreadable"))
                continue

            if size > config.max_bytes:
                if config.on_oversize == "skip":
                    skipped.append(SkipRecord(rel_str, "oversize"))
                    continue
                # truncate mode: include but mark

            included.append(
                FileRecord(
                    path=filepath,
                    relpath=rel_str,
                    ext=ext,
                    size=size,
                    mtime=mtime,
                )
            )

    # Sort deterministically
    included.sort(key=lambda r: r.relpath.casefold())

    return included, skipped
