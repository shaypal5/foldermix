from __future__ import annotations

import pytest

from foldermix import init_profiles


def test_available_profiles_matches_expected_order() -> None:
    assert init_profiles.available_profiles() == (
        "legal",
        "research",
        "support",
        "engineering-docs",
        "course-refresh",
    )


def test_toml_value_renders_integer_literal() -> None:
    assert init_profiles._toml_value(42) == "42"


def test_build_profile_applies_extra_pack_and_stats_values() -> None:
    profile = init_profiles._build_profile(
        slug="custom",
        summary="summary",
        rationale="rationale",
        include_ext=[".txt"],
        on_oversize="truncate",
        continue_on_error=True,
        redact="none",
        strip_frontmatter=False,
        pdf_ocr=False,
        pdf_ocr_strict=False,
        extra_pack_values={"exclude_glob": ["*draft*"]},
        extra_stats_values={"hidden": True},
    )

    assert profile.pack_values["exclude_glob"] == ["*draft*"]
    assert profile.stats_values["hidden"] is True
    assert profile.stats_values["include_ext"] == [".txt"]


def test_toml_value_rejects_unsupported_type() -> None:
    with pytest.raises(TypeError, match="Unsupported TOML value type"):
        init_profiles._toml_value({"k": "v"})
