from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.snapshot_helpers import (
    render_policy_cross_platform_report,
    summarize_policy_cross_platform_report,
)

pytestmark = pytest.mark.integration

FIXTURE_DIR = Path(__file__).parent / "fixtures"


def test_policy_cross_platform_fixture_matches_expected_snapshot(tmp_path: Path) -> None:
    expected_path = FIXTURE_DIR / "expected" / "policy_cross_platform_summary.json"
    report = render_policy_cross_platform_report(tmp_path, FIXTURE_DIR)
    summary = summarize_policy_cross_platform_report(report)

    findings = report["policy_findings"]
    assert isinstance(findings, list)
    assert any(
        isinstance(finding, dict)
        and finding.get("rule_id") == "convert-crlf-token"
        and finding.get("path") == "windows_newlines.txt"
        and finding.get("reason_code") == "POLICY_CONTENT_REGEX_MATCH"
        for finding in findings
    )
    assert any(
        isinstance(finding, dict)
        and finding.get("rule_id") == "convert-secret-marker"
        and finding.get("path") == "latin1.txt"
        and finding.get("reason_code") == "POLICY_CONTENT_REGEX_MATCH"
        for finding in findings
    )
    assert any(
        isinstance(finding, dict)
        and finding.get("rule_id") == "convert-path-space"
        and finding.get("path") == "nested folder/space name.txt"
        and finding.get("reason_code") == "POLICY_RULE_MATCH"
        for finding in findings
    )
    assert any(
        isinstance(finding, dict)
        and finding.get("rule_id") == "scan-excluded-ext"
        and finding.get("path") == "image.png"
        and finding.get("reason_code") == "POLICY_SKIP_REASON_MATCH"
        for finding in findings
    )
    assert any(
        isinstance(finding, dict)
        and finding.get("rule_id") == "scan-sensitive-file"
        and finding.get("path") == "secrets.key"
        and finding.get("reason_code") == "POLICY_SKIP_REASON_MATCH"
        for finding in findings
    )
    assert any(
        isinstance(finding, dict)
        and finding.get("rule_id") == "pack-max-file-count"
        and finding.get("path") is None
        and finding.get("reason_code") == "POLICY_FILE_COUNT_EXCEEDED"
        for finding in findings
    )

    expected = json.loads(expected_path.read_text(encoding="utf-8"))
    assert summary == expected
