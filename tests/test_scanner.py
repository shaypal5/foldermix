from __future__ import annotations

from pathlib import Path

from foldermix.config import PackConfig
from foldermix.scanner import SkipRecord, scan


def test_basic_scan(sample_dir: Path) -> None:
    config = PackConfig(root=sample_dir)
    included, skipped = scan(config)
    relpaths = [r.relpath for r in included]
    assert "sample.txt" in relpaths
    assert "sample.md" in relpaths


def test_hidden_excluded_by_default(sample_dir: Path) -> None:
    config = PackConfig(root=sample_dir)
    included, skipped = scan(config)
    relpaths = [r.relpath for r in included]
    assert ".hidden" not in relpaths
    skip_reasons = {r.relpath: r.reason for r in skipped}
    assert ".hidden" in skip_reasons
    assert skip_reasons[".hidden"] == "hidden"


def test_hidden_included_when_enabled(sample_dir: Path) -> None:
    config = PackConfig(root=sample_dir, hidden=True)
    included, skipped = scan(config)
    relpaths = [r.relpath for r in included]
    assert ".hidden" in relpaths


def test_exclude_ext(sample_dir: Path) -> None:
    config = PackConfig(root=sample_dir, exclude_ext=[".txt"])
    included, skipped = scan(config)
    relpaths = [r.relpath for r in included]
    assert "sample.txt" not in relpaths
    assert "sample.md" in relpaths


def test_include_ext_filter(sample_dir: Path) -> None:
    config = PackConfig(root=sample_dir, include_ext=[".py"])
    included, skipped = scan(config)
    assert all(r.ext == ".py" for r in included)


def test_include_ext_with_multiple(sample_dir: Path) -> None:
    config = PackConfig(root=sample_dir, include_ext=[".txt", ".md"])
    included, skipped = scan(config)
    assert all(r.ext in (".txt", ".md") for r in included)


def test_deterministic_ordering(sample_dir: Path) -> None:
    config = PackConfig(root=sample_dir)
    included1, _ = scan(config)
    included2, _ = scan(config)
    assert [r.relpath for r in included1] == [r.relpath for r in included2]


def test_sort_order(sample_dir: Path) -> None:
    config = PackConfig(root=sample_dir, include_ext=[".txt", ".md"])
    included, _ = scan(config)
    paths = [r.relpath for r in included]
    assert paths == sorted(paths, key=str.casefold)


def test_exclude_glob(sample_dir: Path) -> None:
    config = PackConfig(root=sample_dir, exclude_glob=["*.txt"])
    included, skipped = scan(config)
    relpaths = [r.relpath for r in included]
    assert not any(r.endswith(".txt") for r in relpaths)


def test_include_glob_overrides_exclude(sample_dir: Path) -> None:
    config = PackConfig(
        root=sample_dir,
        exclude_glob=["*.txt"],
        include_glob=["sample.txt"],
    )
    included, skipped = scan(config)
    relpaths = [r.relpath for r in included]
    assert "sample.txt" in relpaths


def test_oversize_skip(sample_dir: Path) -> None:
    config = PackConfig(root=sample_dir, max_bytes=10, on_oversize="skip")
    included, skipped = scan(config)
    for r in included:
        assert r.size <= 10
    skip_reasons = {r.relpath: r.reason for r in skipped}
    oversized = [k for k, v in skip_reasons.items() if v == "oversize"]
    assert len(oversized) > 0


def test_binary_ext_excluded(sample_dir: Path) -> None:
    config = PackConfig(root=sample_dir)
    included, skipped = scan(config)
    relpaths = [r.relpath for r in included]
    assert "image.png" not in relpaths


def test_exclude_dirs(sample_dir: Path) -> None:
    config = PackConfig(root=sample_dir, exclude_dirs=["excluded_dir"])
    included, skipped = scan(config)
    relpaths = [r.relpath for r in included]
    assert not any("excluded_dir" in r for r in relpaths)


def test_nested_files_included(sample_dir: Path) -> None:
    config = PackConfig(root=sample_dir, include_ext=[".txt"])
    included, _ = scan(config)
    relpaths = [r.relpath for r in included]
    assert "nested/child.txt" in relpaths


def test_respect_gitignore(tmp_path: Path) -> None:
    (tmp_path / ".gitignore").write_text("ignored.txt\n")
    (tmp_path / "ignored.txt").write_text("I am ignored")
    (tmp_path / "included.txt").write_text("I am included")
    config = PackConfig(root=tmp_path, respect_gitignore=True)
    included, skipped = scan(config)
    relpaths = [r.relpath for r in included]
    assert "ignored.txt" not in relpaths
    assert "included.txt" in relpaths


def test_no_respect_gitignore(tmp_path: Path) -> None:
    (tmp_path / ".gitignore").write_text("included.txt\n")
    (tmp_path / "included.txt").write_text("I am not ignored when gitignore disabled")
    config = PackConfig(root=tmp_path, respect_gitignore=False)
    included, _ = scan(config)
    relpaths = [r.relpath for r in included]
    assert "included.txt" in relpaths


def test_stdin_paths_outside_root_are_skipped(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("outside", encoding="utf-8")

    config = PackConfig(root=root, stdin_paths=[outside.resolve()])
    included, skipped = scan(config)

    assert included == []
    assert skipped == [SkipRecord("../outside.txt", "outside_root")]


def test_stdin_paths_outside_root_relpath_valueerror_fallback(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("outside", encoding="utf-8")

    def raise_value_error(_path: object, _start: object = None) -> str:
        raise ValueError("cross-drive path")

    monkeypatch.setattr("foldermix.scanner.os.path.relpath", raise_value_error)

    config = PackConfig(root=root, stdin_paths=[outside.resolve()])
    included, skipped = scan(config)

    assert included == []
    assert skipped == [SkipRecord(outside.resolve().as_posix(), "outside_root")]


def test_stdin_paths_dedup_not_file_and_excluded_dir(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    (root / "ok.txt").write_text("ok", encoding="utf-8")
    nested = root / "nested"
    nested.mkdir()
    excluded_dir = root / "excluded_dir"
    excluded_dir.mkdir()
    (excluded_dir / "secret.txt").write_text("secret", encoding="utf-8")

    config = PackConfig(
        root=root,
        stdin_paths=[
            nested.resolve(),  # directory should be skipped as not_file
            (excluded_dir / "secret.txt").resolve(),  # filtered by excluded_dir
            (root / "ok.txt").resolve(),
            (root / "ok.txt").resolve(),  # duplicate should be ignored
        ],
        exclude_dirs=["excluded_dir"],
    )
    included, skipped = scan(config)

    assert [record.relpath for record in included] == ["ok.txt"]
    assert skipped == [
        SkipRecord("nested", "not_file"),
        SkipRecord("excluded_dir/secret.txt", "excluded_dir"),
    ]
