from __future__ import annotations

import pytest

from foldermix import init_profiles


def test_available_profiles_matches_expected_order() -> None:
    assert init_profiles.available_profiles() == (
        "legal",
        "research",
        "support",
        "engineering-docs",
    )


def test_toml_value_renders_integer_literal() -> None:
    assert init_profiles._toml_value(42) == "42"


def test_toml_value_rejects_unsupported_type() -> None:
    with pytest.raises(TypeError, match="Unsupported TOML value type"):
        init_profiles._toml_value({"k": "v"})
