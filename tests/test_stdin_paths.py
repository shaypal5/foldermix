from __future__ import annotations

from pathlib import Path

from foldermix.stdin_paths import parse_stdin_paths


def test_parse_stdin_paths_newline_mode_resolves_relative_paths(tmp_path: Path) -> None:
    base = tmp_path / "base"
    base.mkdir()
    data = b"a.txt\nnested/b.txt\n"

    paths = parse_stdin_paths(data, null_delimited=False, cwd=base)

    assert paths == [
        (base / "a.txt").resolve(strict=False),
        (base / "nested" / "b.txt").resolve(strict=False),
    ]


def test_parse_stdin_paths_null_mode_deduplicates_and_keeps_spaces(tmp_path: Path) -> None:
    base = tmp_path / "base"
    base.mkdir()
    data = "space name.txt\0space name.txt\0unicodé.txt\0".encode()

    paths = parse_stdin_paths(data, null_delimited=True, cwd=base)

    assert paths == [
        (base / "space name.txt").resolve(strict=False),
        (base / "unicodé.txt").resolve(strict=False),
    ]


def test_parse_stdin_paths_keeps_absolute_paths(tmp_path: Path) -> None:
    base = tmp_path / "base"
    base.mkdir()
    absolute = (tmp_path / "absolute.txt").resolve(strict=False)
    data = f"{absolute}\n".encode()

    paths = parse_stdin_paths(data, null_delimited=False, cwd=base)

    assert paths == [absolute]
