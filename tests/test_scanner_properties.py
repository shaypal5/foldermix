from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from foldermix.config import PackConfig
from foldermix.scanner import scan


@pytest.mark.slow
@settings(max_examples=30, deadline=None)
@given(
    st.lists(
        st.tuples(
            st.text(
                alphabet="abcdefghijklmnopqrstuvwxyz0123456789",
                min_size=1,
                max_size=8,
            ),
            st.sampled_from([".txt", ".md", ".py", ".json", ".png"]),
        ),
        min_size=1,
        max_size=20,
        unique_by=lambda t: t[0] + t[1],
    )
)
def test_scan_is_deterministic_and_partitioned(file_specs: list[tuple[str, str]]) -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        for stem, ext in file_specs:
            (root / f"{stem}{ext}").write_text(f"{stem}\n", encoding="utf-8")

        config = PackConfig(root=root)
        included_1, skipped_1 = scan(config)
        included_2, skipped_2 = scan(config)

        inc1 = [r.relpath for r in included_1]
        inc2 = [r.relpath for r in included_2]
        sk1 = [r.relpath for r in skipped_1]
        sk2 = [r.relpath for r in skipped_2]

        assert inc1 == inc2
        assert sk1 == sk2
        assert inc1 == sorted(inc1, key=str.casefold)
        assert set(inc1).isdisjoint(set(sk1))
        assert len(inc1) + len(sk1) == len(file_specs)


@pytest.mark.slow
@settings(max_examples=30, deadline=None)
@given(
    st.lists(
        st.tuples(
            st.text(
                alphabet="abcdefghijklmnopqrstuvwxyz0123456789",
                min_size=1,
                max_size=8,
            ),
            st.sampled_from([".txt", ".md", ".py", ".json"]),
        ),
        min_size=1,
        max_size=20,
        unique_by=lambda t: t[0] + t[1],
    ),
    st.lists(
        st.sampled_from([".txt", ".md", ".py", ".json"]),
        unique=True,
        min_size=1,
        max_size=4,
    ),
)
def test_include_ext_filter_only_allows_selected_extensions(
    file_specs: list[tuple[str, str]],
    include_ext: list[str],
) -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        for stem, ext in file_specs:
            (root / f"{stem}{ext}").write_text(f"{stem}\n", encoding="utf-8")

        included, _ = scan(PackConfig(root=root, include_ext=include_ext))
        allowed = {e.lower() for e in include_ext}
        assert all(r.ext in allowed for r in included)


@pytest.mark.slow
@settings(max_examples=30, deadline=None)
@given(
    st.lists(
        st.text(
            alphabet="abcdefghijklmnopqrstuvwxyz0123456789",
            min_size=1,
            max_size=8,
        ),
        min_size=1,
        max_size=20,
        unique=True,
    ),
    st.lists(st.booleans(), min_size=1, max_size=20),
)
def test_include_glob_overrides_exclude_glob_for_txt_files(
    names: list[str],
    flags: list[bool],
) -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        for name in names:
            (root / f"{name}.txt").write_text("x\n", encoding="utf-8")

        selected = {f"{name}.txt" for name, flag in zip(names, flags, strict=False) if flag}
        config = PackConfig(
            root=root,
            exclude_glob=["*.txt"],
            include_glob=sorted(selected),
        )
        included, skipped = scan(config)
        included_paths = {r.relpath for r in included}
        skipped_map = {r.relpath: r.reason for r in skipped}

        assert selected.issubset(included_paths)
        for name in names:
            rel = f"{name}.txt"
            if rel not in selected:
                assert skipped_map[rel] == "excluded_glob"
