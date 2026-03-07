from __future__ import annotations

import json
from pathlib import Path

from foldermix.report import (
    SKIP_REASON_CODES,
    SKIP_REASON_MESSAGES,
    SKIP_REASONS,
    ReportData,
    build_included_file_entry,
    build_policy_finding_counts,
    build_reason_code_counts,
    build_redaction_summary,
    build_skipped_file_entry,
    build_warning_code_counts,
    write_report,
)


def test_build_skipped_file_entry_unknown_reason_uses_fallback_code_and_message() -> None:
    entry = build_skipped_file_entry(path="mystery.bin", reason="mystery_reason")

    assert entry["path"] == "mystery.bin"
    assert entry["reason"] == "mystery_reason"
    assert entry["reason_code"] == "SKIP_UNKNOWN"
    assert entry["message"] == "Path skipped for an unspecified reason."


def test_skip_reason_derived_maps_match_source_of_truth() -> None:
    assert set(SKIP_REASON_CODES) == set(SKIP_REASONS)
    assert set(SKIP_REASON_MESSAGES) == set(SKIP_REASONS)
    for reason, info in SKIP_REASONS.items():
        assert SKIP_REASON_CODES[reason] == info.code
        assert SKIP_REASON_MESSAGES[reason] == info.message


def test_build_skipped_file_entry_supports_conversion_related_reasons() -> None:
    optional_missing = build_skipped_file_entry(
        path="doc.pdf",
        reason="optional_dependency_missing",
    )
    unsupported_ext = build_skipped_file_entry(
        path="notes.custom",
        reason="unsupported_extension",
    )

    assert optional_missing["reason_code"] == "SKIP_OPTIONAL_DEPENDENCY_MISSING"
    assert "optional dependencies are missing" in optional_missing["message"]
    assert unsupported_ext["reason_code"] == "SKIP_UNSUPPORTED_EXTENSION"
    assert "no available converter" in unsupported_ext["message"]


def test_build_skipped_file_entry_supports_duplicate_content_reason() -> None:
    entry = build_skipped_file_entry(path="copy.txt", reason="duplicate_content")

    assert entry["reason_code"] == "SKIP_DUPLICATE_CONTENT"
    assert "duplicates an earlier included file" in entry["message"]


def test_write_report_backfills_reason_code_counts_when_missing(tmp_path: Path) -> None:
    report_path = tmp_path / "report.json"
    data = ReportData(
        included_count=1,
        skipped_count=1,
        total_bytes=3,
        included_files=[
            {
                "path": "a.txt",
                "size": 3,
                "ext": ".txt",
                "outcome_codes": ["OUTCOME_CONVERSION_WARNING"],
                "outcomes": [
                    {
                        "code": "OUTCOME_CONVERSION_WARNING",
                        "message": "example warning",
                    }
                ],
            }
        ],
        skipped_files=[{"path": "missing.txt", "reason": "missing"}],
    )

    write_report(report_path, data)
    payload = json.loads(report_path.read_text(encoding="utf-8"))

    assert payload["reason_code_counts"] == {
        "OUTCOME_CONVERSION_WARNING": 1,
        "SKIP_MISSING": 1,
    }


def test_build_included_file_entry_deduplicates_outcome_codes() -> None:
    entry = build_included_file_entry(
        path="a.txt",
        size=3,
        ext=".txt",
        truncated=False,
        redacted=False,
        warning_messages=["warn-1", "warn-2"],
        redact_mode="none",
    )

    assert entry["outcome_codes"] == ["OUTCOME_CONVERSION_WARNING"]
    assert entry["warning_codes"] == ["unclassified_warning"]
    assert len(entry["outcomes"]) == 2
    assert entry["outcomes"][0]["warning_code"] == "unclassified_warning"
    assert entry["redaction"] == {"mode": "none", "event_count": 0, "categories": []}


def test_build_included_file_entry_backfills_invalid_warning_entries() -> None:
    entry = build_included_file_entry(
        path="a.txt",
        size=3,
        ext=".txt",
        truncated=False,
        redacted=False,
        warning_entries=[
            {"code": "", "message": "skip-empty-code"},
            {"code": "encoding_fallback", "message": 1},
            {"code": "encoding_fallback", "message": "valid"},
        ],
        redact_mode="none",
    )
    assert entry["warning_codes"] == ["unclassified_warning", "encoding_fallback"]
    assert entry["outcomes"] == [
        {
            "code": "OUTCOME_CONVERSION_WARNING",
            "warning_code": "unclassified_warning",
            "message": "skip-empty-code",
        },
        {
            "code": "OUTCOME_CONVERSION_WARNING",
            "warning_code": "encoding_fallback",
            "message": "1",
        },
        {
            "code": "OUTCOME_CONVERSION_WARNING",
            "warning_code": "encoding_fallback",
            "message": "valid",
        },
    ]


def test_build_included_file_entry_normalizes_missing_warning_message_to_empty_string() -> None:
    entry = build_included_file_entry(
        path="a.txt",
        size=3,
        ext=".txt",
        truncated=False,
        redacted=False,
        warning_entries=[
            {"code": "", "message": None},
        ],
        redact_mode="none",
    )
    assert entry["warning_codes"] == ["unclassified_warning"]
    assert entry["outcomes"] == [
        {
            "code": "OUTCOME_CONVERSION_WARNING",
            "warning_code": "unclassified_warning",
            "message": "",
        }
    ]


def test_build_included_file_entry_backfills_blank_codes_via_classifier() -> None:
    entry = build_included_file_entry(
        path="a.txt",
        size=3,
        ext=".txt",
        truncated=False,
        redacted=False,
        warning_entries=[
            {
                "code": "",
                "message": "Page 3 has no extractable text and OCR produced no text.",
            }
        ],
        redact_mode="none",
    )
    assert entry["warning_codes"] == ["ocr_no_text"]


def test_build_warning_code_counts_groups_warning_codes() -> None:
    counts = build_warning_code_counts(
        included_files=[
            {
                "warning_codes": ["encoding_fallback"],
                "outcomes": [],
            },
            {
                "warning_codes": [],
                "outcomes": [
                    {
                        "code": "OUTCOME_CONVERSION_WARNING",
                        "warning_code": "ocr_no_text",
                        "message": "Page 1 has no extractable text and OCR produced no text.",
                    }
                ],
            },
        ]
    )
    assert counts == {"encoding_fallback": 1, "ocr_no_text": 1}


def test_build_warning_code_counts_ignores_non_dict_outcomes_and_uses_fallback_codes() -> None:
    counts = build_warning_code_counts(
        included_files=[
            {
                "warning_codes": ["converter_unavailable"],
                "outcomes": [1],
            }
        ]
    )
    assert counts == {"converter_unavailable": 1}


def test_build_redaction_summary_aggregates_mode_events_and_categories() -> None:
    summary = build_redaction_summary(
        included_files=[
            {
                "path": "a.txt",
                "redaction": {
                    "mode": "all",
                    "event_count": 2,
                    "categories": ["emails"],
                },
            },
            {
                "path": "b.txt",
                "redaction": {
                    "mode": "all",
                    "event_count": 1,
                    "categories": ["phones"],
                },
            },
            {
                "path": "c.txt",
                "redaction": {
                    "mode": "all",
                    "event_count": 0,
                    "categories": [],
                },
            },
        ]
    )
    assert summary == {
        "mode": "all",
        "files_with_redactions": 2,
        "event_count": 3,
        "categories": ["emails", "phones"],
    }


def test_build_redaction_summary_returns_mixed_mode_for_inconsistent_entries() -> None:
    summary = build_redaction_summary(
        included_files=[
            {"redaction": {"mode": "emails", "event_count": 1, "categories": ["emails"]}},
            {"redaction": {"mode": "phones", "event_count": 1, "categories": ["phones"]}},
        ]
    )
    assert summary["mode"] == "mixed"


def test_build_redaction_summary_uses_default_mode_when_no_files() -> None:
    summary = build_redaction_summary(included_files=[], default_mode="emails")
    assert summary == {
        "mode": "emails",
        "files_with_redactions": 0,
        "event_count": 0,
        "categories": [],
    }


def test_build_reason_code_counts_ignores_non_dict_outcomes_and_uses_fallback_codes() -> None:
    counts = build_reason_code_counts(
        included_files=[
            {
                "outcome_codes": ["OUTCOME_CONVERSION_WARNING"],
                "warning_codes": ["ocr_disabled"],
                "outcomes": [1],
            }
        ],
        skipped_files=[],
    )
    assert counts == {
        "OUTCOME_CONVERSION_WARNING": 1,
        "ocr_disabled": 1,
    }


def test_write_report_backfills_unknown_reason_code_for_non_string_reason(tmp_path: Path) -> None:
    report_path = tmp_path / "report.json"
    data = ReportData(
        included_count=0,
        skipped_count=1,
        total_bytes=0,
        included_files=[],
        skipped_files=[{"path": "mystery.bin", "reason": 123}],
    )

    write_report(report_path, data)
    payload = json.loads(report_path.read_text(encoding="utf-8"))

    assert payload["reason_code_counts"] == {"SKIP_UNKNOWN": 1}


def test_write_report_backfills_redaction_summary_when_missing(tmp_path: Path) -> None:
    report_path = tmp_path / "report.json"
    data = ReportData(
        included_count=1,
        skipped_count=0,
        total_bytes=3,
        included_files=[
            {
                "path": "a.txt",
                "size": 3,
                "ext": ".txt",
                "outcome_codes": ["OUTCOME_REDACTED"],
                "warning_codes": [],
                "outcomes": [
                    {
                        "code": "OUTCOME_REDACTED",
                        "message": "Content was redacted using mode 'all'.",
                    }
                ],
                "redaction": {
                    "mode": "all",
                    "event_count": 2,
                    "categories": ["emails"],
                },
            }
        ],
        skipped_files=[],
    )

    write_report(report_path, data)
    payload = json.loads(report_path.read_text(encoding="utf-8"))

    assert payload["redaction_summary"] == {
        "mode": "all",
        "files_with_redactions": 1,
        "event_count": 2,
        "categories": ["emails"],
    }


def test_build_policy_finding_counts_groups_by_key_dimensions() -> None:
    counts = build_policy_finding_counts(
        policy_findings=[
            {
                "rule_id": "a",
                "severity": "high",
                "action": "warn",
                "reason_code": "POLICY_RULE_MATCH",
            },
            {
                "rule_id": "b",
                "severity": "high",
                "action": "deny",
                "reason_code": "POLICY_RULE_MATCH",
            },
            {
                "rule_id": "c",
                "severity": "low",
                "action": "warn",
                "reason_code": "POLICY_CONTENT_REGEX_MATCH",
            },
        ]
    )

    assert counts == {
        "total": 3,
        "by_severity": {"high": 2, "low": 1},
        "by_action": {"deny": 1, "warn": 2},
        "by_reason_code": {
            "POLICY_CONTENT_REGEX_MATCH": 1,
            "POLICY_RULE_MATCH": 2,
        },
    }


def test_build_policy_finding_counts_ignores_non_string_dimensions() -> None:
    counts = build_policy_finding_counts(
        policy_findings=[
            {
                "rule_id": "a",
                "severity": 1,
                "action": None,
                "reason_code": ["x"],
            },
            {
                "rule_id": "b",
                "severity": "medium",
                "action": "warn",
                "reason_code": "POLICY_RULE_MATCH",
            },
        ]
    )

    assert counts == {
        "total": 2,
        "by_severity": {"medium": 1},
        "by_action": {"warn": 1},
        "by_reason_code": {"POLICY_RULE_MATCH": 1},
    }


def test_write_report_backfills_policy_finding_counts_when_missing(tmp_path: Path) -> None:
    report_path = tmp_path / "report.json"
    data = ReportData(
        included_count=0,
        skipped_count=0,
        total_bytes=0,
        included_files=[],
        skipped_files=[],
        policy_findings=[
            {
                "rule_id": "r1",
                "severity": "medium",
                "action": "warn",
                "stage": "scan",
                "path": "a.txt",
                "reason_code": "POLICY_RULE_MATCH",
                "message": "hit",
            }
        ],
    )

    write_report(report_path, data)
    payload = json.loads(report_path.read_text(encoding="utf-8"))

    assert payload["policy_finding_counts"] == {
        "total": 1,
        "by_severity": {"medium": 1},
        "by_action": {"warn": 1},
        "by_reason_code": {"POLICY_RULE_MATCH": 1},
    }
    assert payload["warning_code_counts"] == {}


def test_write_report_preserves_precomputed_warning_code_counts(tmp_path: Path) -> None:
    report_path = tmp_path / "report.json"
    data = ReportData(
        included_count=0,
        skipped_count=0,
        total_bytes=0,
        included_files=[],
        skipped_files=[],
        warning_code_counts={"already_set": 2},
    )

    write_report(report_path, data)
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["warning_code_counts"] == {"already_set": 2}
