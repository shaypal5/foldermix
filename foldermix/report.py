from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .warning_taxonomy import (
    classify_warning_message,
    normalize_warning_entries,
)

REPORT_SCHEMA_VERSION = 4


@dataclass(frozen=True)
class SkipReasonInfo:
    code: str
    message: str


SKIP_REASONS: dict[str, SkipReasonInfo] = {
    "hidden": SkipReasonInfo(
        code="SKIP_HIDDEN",
        message="Hidden path excluded by default scanner rules.",
    ),
    "excluded_dir": SkipReasonInfo(
        code="SKIP_EXCLUDED_DIR",
        message="Path is inside an excluded directory.",
    ),
    "sensitive": SkipReasonInfo(
        code="SKIP_SENSITIVE",
        message="Path matches a sensitive-file pattern.",
    ),
    "gitignored": SkipReasonInfo(
        code="SKIP_GITIGNORED",
        message="Path is matched by .gitignore rules.",
    ),
    "excluded_glob": SkipReasonInfo(
        code="SKIP_EXCLUDED_GLOB",
        message="Path is excluded by glob filtering.",
    ),
    "excluded_ext": SkipReasonInfo(
        code="SKIP_EXCLUDED_EXT",
        message="Path is excluded by extension filtering.",
    ),
    "unreadable": SkipReasonInfo(
        code="SKIP_UNREADABLE",
        message="Path could not be read from the filesystem.",
    ),
    "oversize": SkipReasonInfo(
        code="SKIP_OVERSIZE",
        message="Path exceeds --max-bytes with skip policy.",
    ),
    "outside_root": SkipReasonInfo(
        code="SKIP_OUTSIDE_ROOT",
        message="Explicit path is outside the configured root.",
    ),
    "missing": SkipReasonInfo(
        code="SKIP_MISSING",
        message="Explicit path does not exist.",
    ),
    "not_file": SkipReasonInfo(
        code="SKIP_NOT_FILE",
        message="Explicit path is not a regular file.",
    ),
}

# Kept as derived mappings for compatibility with existing internal/tests usage.
SKIP_REASON_CODES: dict[str, str] = {reason: info.code for reason, info in SKIP_REASONS.items()}
SKIP_REASON_MESSAGES: dict[str, str] = {
    reason: info.message for reason, info in SKIP_REASONS.items()
}

OUTCOME_TRUNCATED = "OUTCOME_TRUNCATED"
OUTCOME_REDACTED = "OUTCOME_REDACTED"
OUTCOME_CONVERSION_WARNING = "OUTCOME_CONVERSION_WARNING"


@dataclass
class ReportData:
    included_count: int
    skipped_count: int
    total_bytes: int
    included_files: list[dict]
    skipped_files: list[dict]
    policy_findings: list[dict] = field(default_factory=list)
    schema_version: int = REPORT_SCHEMA_VERSION
    reason_code_counts: dict[str, int] = field(default_factory=dict)
    warning_code_counts: dict[str, int] = field(default_factory=dict)
    policy_finding_counts: dict[str, object] = field(default_factory=dict)


def _skip_reason_code(reason: str) -> str:
    info = SKIP_REASONS.get(reason)
    if info is None:
        return "SKIP_UNKNOWN"
    return info.code


def _skip_reason_message(reason: str) -> str:
    info = SKIP_REASONS.get(reason)
    if info is None:
        return "Path skipped for an unspecified reason."
    return info.message


def build_skipped_file_entry(*, path: str, reason: str) -> dict:
    return {
        "path": path,
        "reason": reason,
        "reason_code": _skip_reason_code(reason),
        "message": _skip_reason_message(reason),
    }


def build_included_file_entry(
    *,
    path: str,
    size: int,
    ext: str,
    truncated: bool,
    redacted: bool,
    warning_entries: Iterable[dict[str, str]] | None = None,
    warning_messages: Iterable[str] | None = None,
    redact_mode: str,
) -> dict:
    normalized_warning_entries: list[dict[str, str]]
    if warning_entries is not None:
        normalized_warning_entries = _normalize_warning_entries_from_entries(warning_entries)
    else:
        normalized_warning_entries = normalize_warning_entries(warning_messages or [])

    outcomes: list[dict[str, str]] = []
    if truncated:
        outcomes.append(
            {
                "code": OUTCOME_TRUNCATED,
                "message": "File content was truncated to satisfy --max-bytes.",
            }
        )
    if redacted:
        outcomes.append(
            {
                "code": OUTCOME_REDACTED,
                "message": f"Content was redacted using mode '{redact_mode}'.",
            }
        )
    for warning in normalized_warning_entries:
        outcomes.append(
            {
                "code": OUTCOME_CONVERSION_WARNING,
                "warning_code": warning["code"],
                "message": warning["message"],
            }
        )
    outcome_codes = list(dict.fromkeys(outcome["code"] for outcome in outcomes))
    warning_codes = list(dict.fromkeys(warning["code"] for warning in normalized_warning_entries))

    return {
        "path": path,
        "size": size,
        "ext": ext,
        "outcome_codes": outcome_codes,
        "warning_codes": warning_codes,
        "outcomes": outcomes,
    }


def build_reason_code_counts(
    *, included_files: list[dict], skipped_files: list[dict]
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for entry in skipped_files:
        reason_code = entry.get("reason_code")
        if reason_code is None:
            reason = entry.get("reason")
            if isinstance(reason, str):
                reason_code = _skip_reason_code(reason)
            else:
                reason_code = "SKIP_UNKNOWN"
        code = str(reason_code)
        counts[code] = counts.get(code, 0) + 1

    for entry in included_files:
        for code in entry.get("outcome_codes", []):
            code_str = str(code)
            counts[code_str] = counts.get(code_str, 0) + 1

        for warning_code in _iter_warning_codes(entry):
            counts[warning_code] = counts.get(warning_code, 0) + 1

    return dict(sorted(counts.items()))


def build_warning_code_counts(*, included_files: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for entry in included_files:
        for warning_code in _iter_warning_codes(entry):
            counts[warning_code] = counts.get(warning_code, 0) + 1
    return dict(sorted(counts.items()))


def _normalize_warning_entries_from_entries(
    warning_entries: Iterable[dict[str, str]],
) -> list[dict[str, str]]:
    normalized_warning_entries: list[dict[str, str]] = []
    for warning in warning_entries:
        raw_code = warning.get("code")
        raw_message = warning.get("message")

        message = raw_message if isinstance(raw_message, str) else str(raw_message)
        if isinstance(raw_code, str) and raw_code.strip():
            code = raw_code.strip()
        else:
            code = classify_warning_message(message)

        normalized_warning_entries.append({"code": code, "message": message})
    return normalized_warning_entries


def _iter_warning_codes(entry: dict) -> list[str]:
    outcome_warning_codes: list[str] = []
    for outcome in entry.get("outcomes", []):
        if not isinstance(outcome, dict):
            continue
        warning_code = outcome.get("warning_code")
        if isinstance(warning_code, str):
            outcome_warning_codes.append(warning_code)
    if outcome_warning_codes:
        return outcome_warning_codes
    return [str(warning_code) for warning_code in entry.get("warning_codes", [])]


def build_policy_finding_counts(*, policy_findings: list[dict]) -> dict[str, object]:
    by_severity: dict[str, int] = {}
    by_action: dict[str, int] = {}
    by_reason_code: dict[str, int] = {}

    for finding in policy_findings:
        severity = finding.get("severity")
        if isinstance(severity, str):
            by_severity[severity] = by_severity.get(severity, 0) + 1

        action = finding.get("action")
        if isinstance(action, str):
            by_action[action] = by_action.get(action, 0) + 1

        reason_code = finding.get("reason_code")
        if isinstance(reason_code, str):
            by_reason_code[reason_code] = by_reason_code.get(reason_code, 0) + 1

    return {
        "total": len(policy_findings),
        "by_severity": dict(sorted(by_severity.items())),
        "by_action": dict(sorted(by_action.items())),
        "by_reason_code": dict(sorted(by_reason_code.items())),
    }


def write_report(report_path: Path, data: ReportData) -> None:
    payload = asdict(data)
    if not payload["reason_code_counts"]:
        payload["reason_code_counts"] = build_reason_code_counts(
            included_files=payload["included_files"],
            skipped_files=payload["skipped_files"],
        )
    if not payload["warning_code_counts"]:
        payload["warning_code_counts"] = build_warning_code_counts(
            included_files=payload["included_files"],
        )
    if payload["policy_findings"] and not payload["policy_finding_counts"]:
        payload["policy_finding_counts"] = build_policy_finding_counts(
            policy_findings=payload["policy_findings"],
        )
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
