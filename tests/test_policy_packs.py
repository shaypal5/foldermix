from __future__ import annotations

import pytest

from foldermix.policy_packs import (
    POLICY_PACKS_VERSION,
    available_policy_packs,
    combine_policy_rules,
    get_policy_pack_definition,
    get_policy_pack_rules,
)


def test_available_policy_packs_are_stable() -> None:
    assert available_policy_packs() == (
        "customer-support",
        "legal-hold",
        "strict-privacy",
    )


def test_policy_pack_definition_is_versioned() -> None:
    definition = get_policy_pack_definition("strict-privacy")
    assert definition["version"] == POLICY_PACKS_VERSION
    assert definition["rules"]


def test_get_policy_pack_rules_returns_independent_copy() -> None:
    first = get_policy_pack_rules("legal-hold")
    second = get_policy_pack_rules("legal-hold")
    first[0]["rule_id"] = "mutated"
    assert second[0]["rule_id"] != "mutated"


def test_combine_policy_rules_appends_custom_rules_after_pack() -> None:
    combined = combine_policy_rules(
        policy_pack="customer-support",
        policy_rules=[
            {
                "rule_id": "custom-one",
                "description": "custom",
                "path_glob": "*.txt",
            }
        ],
    )

    assert combined[-1]["rule_id"] == "custom-one"
    assert any(rule["rule_id"] == "customer-support-log-file" for rule in combined)


def test_unknown_policy_pack_raises_clear_error() -> None:
    with pytest.raises(ValueError, match="Unknown policy pack"):
        get_policy_pack_rules("does-not-exist")
