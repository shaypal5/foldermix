from __future__ import annotations

from copy import deepcopy
from typing import TypedDict


class PolicyPackDefinition(TypedDict):
    version: int
    description: str
    rules: list[dict[str, object]]


POLICY_PACKS_VERSION = 1


_POLICY_PACKS: dict[str, PolicyPackDefinition] = {
    "strict-privacy": {
        "version": POLICY_PACKS_VERSION,
        "description": (
            "Prioritize strict privacy controls by flagging direct PII/secret indicators "
            "with deny-level severities."
        ),
        "rules": [
            {
                "rule_id": "strict-privacy-hidden-or-sensitive-scan",
                "description": "Skipped hidden or sensitive files should be reviewed",
                "stage": "scan",
                "severity": "medium",
                "action": "warn",
                "skip_reason_in": ["hidden", "sensitive"],
            },
            {
                "rule_id": "strict-privacy-email",
                "description": "Detected email-like content",
                "stage": "convert",
                "severity": "high",
                "action": "deny",
                "content_regex": r"(?i)[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}",
            },
            {
                "rule_id": "strict-privacy-phone",
                "description": "Detected phone-like content",
                "stage": "convert",
                "severity": "high",
                "action": "deny",
                "content_regex": r"(?:\+?\d[\d .-]{7,}\d)",
            },
            {
                "rule_id": "strict-privacy-secret-token",
                "description": "Detected secret-like token marker",
                "stage": "convert",
                "severity": "critical",
                "action": "deny",
                "content_regex": r"(?i)(api[_-]?key|secret|token)\s*[:=]",
            },
        ],
    },
    "legal-hold": {
        "version": POLICY_PACKS_VERSION,
        "description": (
            "Surface likely legal-retention signals so potentially relevant material "
            "is not silently overlooked."
        ),
        "rules": [
            {
                "rule_id": "legal-hold-privileged-marker",
                "description": "Detected privileged/legal-work marker",
                "stage": "convert",
                "severity": "high",
                "action": "warn",
                "content_regex": r"(?i)(attorney-client|privileged|work product)",
            },
            {
                "rule_id": "legal-hold-destruction-marker",
                "description": "Detected deletion or destruction marker",
                "stage": "convert",
                "severity": "medium",
                "action": "warn",
                "content_regex": r"(?i)\b(delete|destroy|purge)\b",
            },
            {
                "rule_id": "legal-hold-hidden-scan",
                "description": "Hidden files should be reviewed for legal hold completeness",
                "stage": "scan",
                "severity": "low",
                "action": "warn",
                "skip_reason_in": ["hidden"],
            },
        ],
    },
    "customer-support": {
        "version": POLICY_PACKS_VERSION,
        "description": (
            "Highlight support-facing PII and operational log content while keeping "
            "policy outcomes advisory."
        ),
        "rules": [
            {
                "rule_id": "customer-support-contact-email",
                "description": "Detected customer email marker",
                "stage": "convert",
                "severity": "medium",
                "action": "warn",
                "content_regex": r"(?i)[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}",
            },
            {
                "rule_id": "customer-support-contact-phone",
                "description": "Detected customer phone marker",
                "stage": "convert",
                "severity": "medium",
                "action": "warn",
                "content_regex": r"(?:\+?\d[\d .-]{7,}\d)",
            },
            {
                "rule_id": "customer-support-log-file",
                "description": "Log-like files should be reviewed for support context quality",
                "stage": "scan",
                "severity": "low",
                "action": "warn",
                "path_glob": "*trace.txt",
            },
        ],
    },
}


def available_policy_packs() -> tuple[str, ...]:
    return tuple(sorted(_POLICY_PACKS))


def get_policy_pack_definition(name: str) -> PolicyPackDefinition:
    definition = _POLICY_PACKS.get(name)
    if definition is None:
        choices = ", ".join(available_policy_packs())
        raise ValueError(f"Unknown policy pack {name!r}. Valid choices are: {choices}")
    return deepcopy(definition)


def get_policy_pack_rules(name: str) -> list[dict[str, object]]:
    return get_policy_pack_definition(name)["rules"]


def combine_policy_rules(
    *, policy_pack: str | None, policy_rules: list[dict[str, object]]
) -> list[dict[str, object]]:
    combined: list[dict[str, object]] = []
    if policy_pack is not None:
        combined.extend(get_policy_pack_rules(policy_pack))
    combined.extend(deepcopy(policy_rules))
    return combined
