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


def _load_gitignore_spec(root: Path, respect_gitignore: bool) -> pathspec.PathSpec | None:
    if not respect_gitignore:
        return None
    gitignore_path = root / ".gitignore"
    if not gitignore_path.exists():
        return None
    patterns = gitignore_path.read_text().splitlines()
    return pathspec.PathSpec.from_lines("gitignore", patterns)


def _normalize_include_exts(config: PackConfig) -> set[str] | None:
    if config.include_ext is None:
        return None
    return {e.lower() if e.startswith(".") else f".{e.lower()}" for e in config.include_ext}


def _normalize_exclude_exts(config: PackConfig) -> set[str]:
    return {e.lower() if e.startswith(".") else f".{e.lower()}" for e in config.exclude_ext}


def _has_hidden_segment(rel_path: Path) -> bool:
    return any(part.startswith(".") for part in rel_path.parts if part not in {".", ".."})


def _scan_candidate_file(
    filepath: Path,
    *,
    rel_path: Path,
    rel_str: str,
    config: PackConfig,
    gitignore_spec: pathspec.PathSpec | None,
    include_exts: set[str] | None,
    exclude_exts: set[str],
) -> tuple[FileRecord | None, SkipRecord | None]:
    filename = filepath.name
    ext = filepath.suffix.lower()

    # Hidden files and directories
    if not config.hidden and _has_hidden_segment(rel_path):
        return None, SkipRecord(rel_str, "hidden")

    # Excluded directories
    if any(part in config.exclude_dirs for part in rel_path.parts[:-1]):
        return None, SkipRecord(rel_str, "excluded_dir")

    # Sensitive files
    if is_sensitive(filename):
        return None, SkipRecord(rel_str, "sensitive")

    # gitignore
    if gitignore_spec and gitignore_spec.match_file(rel_str):
        return None, SkipRecord(rel_str, "gitignored")

    # Exclude glob
    excluded_by_glob = any(fnmatch.fnmatch(rel_str, pattern) for pattern in config.exclude_glob)

    # Include glob override
    included_by_glob = any(fnmatch.fnmatch(rel_str, pattern) for pattern in config.include_glob)

    if excluded_by_glob and not included_by_glob:
        return None, SkipRecord(rel_str, "excluded_glob")

    # Extension filters
    if not included_by_glob:
        if include_exts is not None and ext not in include_exts:
            return None, SkipRecord(rel_str, "excluded_ext")
        if ext in exclude_exts:
            return None, SkipRecord(rel_str, "excluded_ext")

    # Size check
    try:
        stat = filepath.stat()
        size = stat.st_size
        mtime = stat.st_mtime
    except OSError:
        return None, SkipRecord(rel_str, "unreadable")

    if size > config.max_bytes and config.on_oversize == "skip":
        return None, SkipRecord(rel_str, "oversize")

    return (
        FileRecord(
            path=filepath,
            relpath=rel_str,
            ext=ext,
            size=size,
            mtime=mtime,
        ),
        None,
    )


def _scan_explicit_paths(config: PackConfig) -> tuple[list[FileRecord], list[SkipRecord]]:
    included: list[FileRecord] = []
    skipped: list[SkipRecord] = []

    root = config.root.resolve()
    gitignore_spec = _load_gitignore_spec(root, config.respect_gitignore)
    include_exts = _normalize_include_exts(config)
    exclude_exts = _normalize_exclude_exts(config)

    seen: set[str] = set()
    for explicit_path in config.stdin_paths or []:
        dedupe_key = os.path.normcase(str(explicit_path))
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)

        try:
            rel_path = explicit_path.relative_to(root)
        except ValueError:
            rel_str = Path(os.path.relpath(explicit_path, root)).as_posix()
            skipped.append(SkipRecord(rel_str, "outside_root"))
            continue

        rel_str = rel_path.as_posix()
        if not explicit_path.exists():
            skipped.append(SkipRecord(rel_str, "missing"))
            continue
        if not explicit_path.is_file():
            skipped.append(SkipRecord(rel_str, "not_file"))
            continue

        record, skip = _scan_candidate_file(
            explicit_path,
            rel_path=rel_path,
            rel_str=rel_str,
            config=config,
            gitignore_spec=gitignore_spec,
            include_exts=include_exts,
            exclude_exts=exclude_exts,
        )
        if skip is not None:
            skipped.append(skip)
            continue
        assert record is not None  # for mypy
        included.append(record)

    included.sort(key=lambda r: r.relpath.casefold())
    return included, skipped


def scan(config: PackConfig) -> tuple[list[FileRecord], list[SkipRecord]]:
    """Walk root and return (included, skipped) file records."""
    if config.stdin_paths is not None:
        return _scan_explicit_paths(config)

    included: list[FileRecord] = []
    skipped: list[SkipRecord] = []

    root = config.root.resolve()

    gitignore_spec = _load_gitignore_spec(root, config.respect_gitignore)
    include_exts = _normalize_include_exts(config)
    exclude_exts = _normalize_exclude_exts(config)

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
            record, skip = _scan_candidate_file(
                filepath,
                rel_path=rel_path,
                rel_str=rel_str,
                config=config,
                gitignore_spec=gitignore_spec,
                include_exts=include_exts,
                exclude_exts=exclude_exts,
            )
            if skip is not None:
                skipped.append(skip)
                continue
            assert record is not None  # for mypy
            included.append(record)

    # Sort deterministically
    included.sort(key=lambda r: r.relpath.casefold())

    return included, skipped
