from __future__ import annotations

import json
import time
from pathlib import Path

import pytest
import typer

from foldermix import packer
from foldermix.config import PackConfig
from foldermix.converters.base import ConversionResult
from foldermix.scanner import FileRecord
from foldermix.writers.base import FileBundleItem


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


class _AlwaysFailConverter:
    def can_convert(self, ext: str) -> bool:  # pragma: no cover - protocol parity
        return True

    def convert(self, path: Path, encoding: str = "utf-8") -> ConversionResult:
        raise RuntimeError("boom")


class _SingleConverterRegistry:
    def __init__(self, converter) -> None:
        self._converter = converter

    def get_converter(self, ext: str):
        return self._converter


def _record(path: Path) -> FileRecord:
    stat = path.stat()
    return FileRecord(
        path=path,
        relpath=path.name,
        ext=path.suffix.lower(),
        size=stat.st_size,
        mtime=stat.st_mtime,
    )


def test_pack_dry_run_does_not_write_output(tmp_path: Path) -> None:
    _write(tmp_path / "a.txt", "hello\n")
    out_path = tmp_path / "out.md"
    config = PackConfig(root=tmp_path, out=out_path, dry_run=True, workers=1)

    packer.pack(config)

    assert not out_path.exists()


def test_pack_policy_dry_run_text_summarizes_findings_and_skips_output(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _write(tmp_path / "a.txt", "TOP_SECRET_123\n")
    out_path = tmp_path / "out.md"
    config = PackConfig(
        root=tmp_path,
        out=out_path,
        workers=1,
        policy_dry_run=True,
        policy_output="text",
        policy_rules=[
            {
                "rule_id": "convert-secret",
                "description": "Flag secret marker",
                "stage": "convert",
                "content_regex": "SECRET_[0-9]+",
                "severity": "high",
                "action": "deny",
            },
            {
                "rule_id": "pack-total",
                "description": "Total bytes too high",
                "stage": "pack",
                "max_total_bytes": 1,
                "severity": "low",
                "action": "warn",
            },
        ],
    )

    packer.pack(config)

    assert not out_path.exists()
    captured = capsys.readouterr()
    assert "Policy dry run complete." in captured.err
    assert "Policy findings: 2" in captured.err
    assert captured.err.count("Policy findings:") == 1
    assert "Affected files: 1" in captured.err
    assert "a.txt" in captured.err
    assert "Non-file findings: 1" in captured.err


def test_pack_policy_dry_run_json_emits_machine_readable_output(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _write(tmp_path / "a.txt", "TOP_SECRET_123\n")
    out_path = tmp_path / "out.md"
    config = PackConfig(
        root=tmp_path,
        out=out_path,
        workers=1,
        policy_dry_run=True,
        policy_output="json",
        policy_rules=[
            {
                "rule_id": "convert-secret",
                "description": "Flag secret marker",
                "stage": "convert",
                "content_regex": "SECRET_[0-9]+",
                "severity": "high",
                "action": "deny",
            }
        ],
    )

    packer.pack(config)

    assert not out_path.exists()
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["mode"] == "policy_dry_run"
    assert payload["finding_count"] == 1
    assert payload["by_stage"] == {"convert": 1}
    assert payload["affected_files"] == [{"path": "a.txt", "finding_count": 1}]
    assert payload["findings"][0]["rule_id"] == "convert-secret"
    assert "Policy findings:" not in captured.err


def test_pack_policy_dry_run_text_handles_zero_findings(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _write(tmp_path / "a.txt", "hello\n")
    config = PackConfig(
        root=tmp_path,
        workers=1,
        policy_dry_run=True,
        policy_output="text",
        policy_rules=[
            {
                "rule_id": "md-only",
                "description": "Only match markdown files",
                "stage": "convert",
                "path_glob": "*.md",
                "severity": "low",
                "action": "warn",
            }
        ],
    )

    packer.pack(config)

    captured = capsys.readouterr()
    assert "Policy findings: 0" in captured.err
    assert "Affected files: 0" in captured.err


def test_pack_respects_max_files_limit(tmp_path: Path) -> None:
    _write(tmp_path / "a.txt", "hello\n")
    config = PackConfig(root=tmp_path, max_files=0, workers=1)

    with pytest.raises(typer.Exit) as exc_info:
        packer.pack(config)

    assert exc_info.value.exit_code == 3


def test_pack_respects_max_total_bytes_limit(tmp_path: Path) -> None:
    _write(tmp_path / "a.txt", "hello world\n")
    config = PackConfig(root=tmp_path, max_total_bytes=1, workers=1)

    with pytest.raises(typer.Exit) as exc_info:
        packer.pack(config)

    assert exc_info.value.exit_code == 3


def test_pack_continue_on_error_false_exits(tmp_path: Path, monkeypatch) -> None:
    _write(tmp_path / "a.txt", "hello\n")
    monkeypatch.setattr(
        packer,
        "_build_registry",
        lambda _config: _SingleConverterRegistry(_AlwaysFailConverter()),
    )
    config = PackConfig(root=tmp_path, format="jsonl", workers=1, continue_on_error=False)

    with pytest.raises(typer.Exit) as exc_info:
        packer.pack(config)

    assert exc_info.value.exit_code == 2


def test_pack_continue_on_error_true_writes_error_item(tmp_path: Path, monkeypatch) -> None:
    _write(tmp_path / "a.txt", "hello\n")
    out_path = tmp_path / "out.jsonl"
    monkeypatch.setattr(
        packer,
        "_build_registry",
        lambda _config: _SingleConverterRegistry(_AlwaysFailConverter()),
    )
    config = PackConfig(
        root=tmp_path,
        out=out_path,
        format="jsonl",
        workers=1,
        continue_on_error=True,
        include_sha256=False,
    )

    packer.pack(config)

    lines = out_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    file_line = json.loads(lines[1])
    assert file_line["converter"] == "error"
    assert "Error converting file: boom" in file_line["content"]
    assert file_line["warnings"] == ["boom"]
    assert file_line["warning_entries"] == [{"code": "unclassified_warning", "message": "boom"}]


def test_render_preview_continue_on_error_false_exits_cleanly(
    tmp_path: Path, monkeypatch, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "a.txt"
    _write(path, "hello\n")

    def fail_convert(
        record: FileRecord, registry, config: PackConfig
    ) -> FileBundleItem:  # pragma: no cover - exercised by call
        raise RuntimeError("boom")

    monkeypatch.setattr(packer, "_convert_record", fail_convert)

    with pytest.raises(typer.Exit) as exc_info:
        packer.render_preview(PackConfig(root=tmp_path), [_record(path)])

    assert exc_info.value.exit_code == 2
    captured = capsys.readouterr()
    assert "Error converting a.txt: boom" in captured.err
    assert "preview conversion error(s). Use --continue-on-error to skip." in captured.err


def test_render_preview_continue_on_error_true_skips_failed_records(
    tmp_path: Path, monkeypatch
) -> None:
    ok_path = tmp_path / "ok.txt"
    bad_path = tmp_path / "bad.txt"
    _write(ok_path, "ok\n")
    _write(bad_path, "bad\n")

    def convert_or_fail(record: FileRecord, registry, config: PackConfig) -> FileBundleItem:
        if record.relpath == "bad.txt":
            raise RuntimeError("boom")
        return FileBundleItem(
            relpath=record.relpath,
            ext=record.ext,
            size_bytes=record.size,
            mtime="2024-01-01T00:00:00+00:00",
            sha256=None,
            content="ok\n",
            converter_name="text",
            original_mime="text/plain",
            warnings=[],
            warning_entries=[],
            truncated=False,
            redacted=False,
            redaction_mode="none",
            redaction_event_count=0,
            redaction_categories=[],
        )

    monkeypatch.setattr(packer, "_convert_record", convert_or_fail)
    rendered = packer.render_preview(
        PackConfig(root=tmp_path, continue_on_error=True, include_sha256=False),
        [_record(ok_path), _record(bad_path)],
    )

    assert "## ok.txt" in rendered
    assert "## bad.txt" not in rendered


def test_pack_report_included_count_matches_written_items_on_post_convert_error(
    tmp_path: Path, monkeypatch
) -> None:
    _write(tmp_path / "a.txt", "hello\n")
    _write(tmp_path / "b.txt", "world\n")
    out_path = tmp_path / "out.jsonl"
    report_path = tmp_path / "report.json"

    original_mtime_iso = packer.mtime_iso

    def flaky_mtime_iso(path: Path) -> str:
        if path.name == "b.txt":
            raise RuntimeError("mtime lookup failed")
        return original_mtime_iso(path)

    monkeypatch.setattr(packer, "mtime_iso", flaky_mtime_iso)

    config = PackConfig(
        root=tmp_path,
        out=out_path,
        format="jsonl",
        report=report_path,
        workers=1,
        continue_on_error=True,
        include_sha256=False,
    )

    packer.pack(config)

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["included_count"] == 1
    assert len(report["included_files"]) == 1
    assert report["included_files"][0]["path"] == "a.txt"


def test_pack_writes_report_json(tmp_path: Path) -> None:
    # Write bytes directly so expected size is stable across LF/CRLF platforms.
    (tmp_path / "data.txt").write_bytes(b"ok\n")
    (tmp_path / "image.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    out_path = tmp_path / "out.md"
    report_path = tmp_path / "report.json"
    config = PackConfig(
        root=tmp_path,
        out=out_path,
        report=report_path,
        workers=1,
        include_sha256=False,
    )

    packer.pack(config)

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["schema_version"] == 5
    assert report["included_count"] == 1
    assert report["skipped_count"] == 1
    assert report["included_files"] == [
        {
            "path": "data.txt",
            "size": 3,
            "ext": ".txt",
            "outcome_codes": [],
            "warning_codes": [],
            "outcomes": [],
            "redaction": {
                "mode": "none",
                "event_count": 0,
                "categories": [],
            },
        }
    ]
    assert report["skipped_files"] == [
        {
            "path": "image.png",
            "reason": "excluded_ext",
            "reason_code": "SKIP_EXCLUDED_EXT",
            "message": "Path is excluded by extension filtering.",
        }
    ]
    assert report["reason_code_counts"] == {"SKIP_EXCLUDED_EXT": 1}
    assert report["warning_code_counts"] == {}
    assert report["redaction_summary"] == {
        "mode": "none",
        "files_with_redactions": 0,
        "event_count": 0,
        "categories": [],
    }


def test_pack_dedupe_content_skips_later_duplicate_files_and_reports_them(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("same\n", encoding="utf-8")
    (tmp_path / "copy.txt").write_text("same\n", encoding="utf-8")
    (tmp_path / "other.txt").write_text("different\n", encoding="utf-8")
    out_path = tmp_path / "out.jsonl"
    report_path = tmp_path / "report.json"
    config = PackConfig(
        root=tmp_path,
        out=out_path,
        format="jsonl",
        report=report_path,
        workers=1,
        include_sha256=False,
        dedupe_content=True,
    )

    packer.pack(config)

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["included_count"] == 2
    assert sorted(entry["path"] for entry in report["included_files"]) == ["a.txt", "other.txt"]
    assert report["skipped_files"] == [
        {
            "path": "copy.txt",
            "reason": "duplicate_content",
            "reason_code": "SKIP_DUPLICATE_CONTENT",
            "message": "Path content duplicates an earlier included file.",
        }
    ]
    assert report["reason_code_counts"] == {"SKIP_DUPLICATE_CONTENT": 1}


def test_pack_dedupe_content_keeps_all_files_when_no_duplicates_exist(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("one\n", encoding="utf-8")
    (tmp_path / "b.txt").write_text("two\n", encoding="utf-8")
    out_path = tmp_path / "out.jsonl"
    report_path = tmp_path / "report.json"
    config = PackConfig(
        root=tmp_path,
        out=out_path,
        format="jsonl",
        report=report_path,
        workers=1,
        include_sha256=False,
        dedupe_content=True,
    )

    packer.pack(config)

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["included_count"] == 2
    assert report["skipped_files"] == []
    assert report["reason_code_counts"] == {}


def test_dedupe_content_keeps_files_when_hashing_fails(tmp_path: Path, monkeypatch) -> None:
    a_path = tmp_path / "a.txt"
    b_path = tmp_path / "b.txt"
    _write(a_path, "same\n")
    _write(b_path, "same\n")
    records = [_record(a_path), _record(b_path)]

    def flaky_sha256(path: Path) -> str:
        if path.name == "b.txt":
            raise OSError("boom")
        return "same-hash"

    monkeypatch.setattr(packer, "sha256_file", flaky_sha256)

    deduped, skipped = packer._dedupe_included_records_by_content(records)

    assert [record.relpath for record in deduped] == ["a.txt", "b.txt"]
    assert skipped == []
    assert records[0].sha256 == "same-hash"
    assert records[1].sha256 is None


def test_convert_record_reuses_precomputed_sha256(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "a.txt"
    _write(path, "hello\n")
    record = _record(path)
    record.sha256 = "precomputed"
    monkeypatch.setattr(
        packer, "sha256_file", lambda _path: (_ for _ in ()).throw(AssertionError("unused"))
    )

    config = PackConfig(root=tmp_path)
    item = packer._convert_record(record, packer._build_registry(config), config)

    assert item.sha256 == "precomputed"


def test_pack_report_includes_structured_outcomes(tmp_path: Path) -> None:
    # Write bytes directly so truncation/redaction counts are stable on LF/CRLF platforms.
    (tmp_path / "big.txt").write_bytes(b"Contact foo@example.com.\n" * 32)
    (tmp_path / "latin1.txt").write_bytes("café\n".encode("latin-1"))
    out_path = tmp_path / "out.jsonl"
    report_path = tmp_path / "report.json"
    config = PackConfig(
        root=tmp_path,
        out=out_path,
        format="jsonl",
        report=report_path,
        max_bytes=80,
        on_oversize="truncate",
        redact="emails",
        encoding="utf-8",
        workers=1,
        include_sha256=False,
    )

    packer.pack(config)

    report = json.loads(report_path.read_text(encoding="utf-8"))
    by_path = {entry["path"]: entry for entry in report["included_files"]}

    assert "OUTCOME_TRUNCATED" in by_path["big.txt"]["outcome_codes"]
    assert "OUTCOME_REDACTED" in by_path["big.txt"]["outcome_codes"]
    assert "OUTCOME_CONVERSION_WARNING" in by_path["latin1.txt"]["outcome_codes"]
    assert by_path["big.txt"]["redaction"] == {
        "mode": "emails",
        "event_count": 3,
        "categories": ["emails"],
    }
    assert by_path["latin1.txt"]["redaction"] == {
        "mode": "emails",
        "event_count": 0,
        "categories": [],
    }

    warning_outcomes = [
        outcome
        for outcome in by_path["latin1.txt"]["outcomes"]
        if outcome["code"] == "OUTCOME_CONVERSION_WARNING"
    ]
    warning_messages = [outcome["message"] for outcome in warning_outcomes]
    assert any("Encoding fallback" in message for message in warning_messages)
    assert [outcome.get("warning_code") for outcome in warning_outcomes] == ["encoding_fallback"]

    assert report["reason_code_counts"]["OUTCOME_TRUNCATED"] == 1
    assert report["reason_code_counts"]["OUTCOME_REDACTED"] == 1
    assert report["reason_code_counts"]["OUTCOME_CONVERSION_WARNING"] == 1
    assert report["reason_code_counts"]["encoding_fallback"] == 1
    assert report["warning_code_counts"] == {"encoding_fallback": 1}
    assert report["redaction_summary"] == {
        "mode": "emails",
        "files_with_redactions": 1,
        "event_count": 3,
        "categories": ["emails"],
    }


def test_pack_report_includes_policy_findings(tmp_path: Path) -> None:
    (tmp_path / "data.txt").write_text("token SECRET_123\n", encoding="utf-8")
    out_path = tmp_path / "out.jsonl"
    report_path = tmp_path / "report.json"
    config = PackConfig(
        root=tmp_path,
        out=out_path,
        format="jsonl",
        report=report_path,
        workers=1,
        include_sha256=False,
        policy_rules=[
            {
                "rule_id": "scan-size",
                "description": "Flag large files in scan stage",
                "stage": "scan",
                "max_size_bytes": 1,
                "severity": "low",
                "action": "warn",
            },
            {
                "rule_id": "convert-secret",
                "description": "Secret marker detected",
                "stage": "convert",
                "content_regex": "SECRET_[0-9]+",
                "severity": "high",
                "action": "deny",
            },
            {
                "rule_id": "pack-total",
                "description": "Total output too large",
                "stage": "pack",
                "max_total_bytes": 1,
                "severity": "medium",
                "action": "warn",
            },
        ],
    )

    packer.pack(config)

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["schema_version"] == 5
    assert len(report["policy_findings"]) == 3
    assert report["policy_finding_counts"] == {
        "total": 3,
        "by_severity": {"high": 1, "low": 1, "medium": 1},
        "by_action": {"deny": 1, "warn": 2},
        "by_reason_code": {
            "POLICY_CONTENT_REGEX_MATCH": 1,
            "POLICY_FILE_SIZE_EXCEEDED": 1,
            "POLICY_TOTAL_BYTES_EXCEEDED": 1,
        },
    }


def test_pack_report_redaction_metadata_never_leaks_sensitive_literals(tmp_path: Path) -> None:
    secret_email = "alice.secret@example.com"
    secret_phone = "+1 (555) 123-4567"
    (tmp_path / "data.txt").write_text(
        f"owner={secret_email}\nphone={secret_phone}\n",
        encoding="utf-8",
    )
    out_path = tmp_path / "out.md"
    report_path = tmp_path / "report.json"
    config = PackConfig(
        root=tmp_path,
        out=out_path,
        report=report_path,
        redact="all",
        workers=1,
        include_sha256=False,
    )

    packer.pack(config)

    report_text = report_path.read_text(encoding="utf-8")
    report = json.loads(report_text)
    assert secret_email not in report_text
    assert secret_phone not in report_text
    assert report["redaction_summary"] == {
        "mode": "all",
        "files_with_redactions": 1,
        "event_count": 2,
        "categories": ["emails", "phones"],
    }


def test_pack_rejects_invalid_policy_rules(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("hello\n", encoding="utf-8")
    config = PackConfig(
        root=tmp_path,
        out=tmp_path / "out.md",
        workers=1,
        policy_rules=[
            {
                "rule_id": "bad",
                "description": "missing matcher",
            }
        ],
    )

    with pytest.raises(typer.Exit) as exc_info:
        packer.pack(config)

    assert exc_info.value.exit_code == 1


def test_pack_policy_scan_evaluates_skipped_records(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("hello\n", encoding="utf-8")
    (tmp_path / "image.png").write_bytes(b"\x89PNG\r\n\x1a\n")

    out_path = tmp_path / "out.jsonl"
    report_path = tmp_path / "report.json"
    config = PackConfig(
        root=tmp_path,
        out=out_path,
        format="jsonl",
        report=report_path,
        workers=1,
        include_sha256=False,
        policy_rules=[
            {
                "rule_id": "scan-skip-ext",
                "description": "Flag extension-based skips",
                "stage": "scan",
                "skip_reason_in": ["excluded_ext"],
            }
        ],
    )

    packer.pack(config)

    report = json.loads(report_path.read_text(encoding="utf-8"))
    finding = next(
        entry for entry in report["policy_findings"] if entry["rule_id"] == "scan-skip-ext"
    )
    assert finding["path"] == "image.png"
    assert finding["reason_code"] == "POLICY_SKIP_REASON_MATCH"


def test_pack_rejects_unknown_policy_pack(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("hello\n", encoding="utf-8")
    config = PackConfig(
        root=tmp_path,
        out=tmp_path / "out.md",
        workers=1,
        policy_pack="does-not-exist",
    )

    with pytest.raises(typer.Exit) as exc_info:
        packer.pack(config)

    assert exc_info.value.exit_code == 1


def test_pack_combines_builtin_policy_pack_with_custom_rules(tmp_path: Path) -> None:
    (tmp_path / "ticket.txt").write_text(
        "Customer email: alice@example.com\nPhone: +1 415-555-0101\n",
        encoding="utf-8",
    )
    (tmp_path / ".env").write_text("TOKEN=abc123\n", encoding="utf-8")
    out_path = tmp_path / "out.jsonl"
    report_path = tmp_path / "report.json"
    config = PackConfig(
        root=tmp_path,
        out=out_path,
        format="jsonl",
        report=report_path,
        workers=1,
        include_sha256=False,
        policy_pack="customer-support",
        policy_rules=[
            {
                "rule_id": "custom-hidden-scan",
                "description": "Flag hidden skips",
                "stage": "scan",
                "skip_reason_in": ["hidden"],
                "severity": "high",
                "action": "deny",
            }
        ],
    )

    packer.pack(config)

    report = json.loads(report_path.read_text(encoding="utf-8"))
    rule_ids = {finding["rule_id"] for finding in report["policy_findings"]}
    assert "customer-support-contact-email" in rule_ids
    assert "customer-support-contact-phone" in rule_ids
    assert "custom-hidden-scan" in rule_ids


def test_pack_fails_with_exit_code_4_when_policy_enforcement_triggered(tmp_path: Path) -> None:
    (tmp_path / "data.txt").write_text("token SECRET_123\n", encoding="utf-8")
    out_path = tmp_path / "out.jsonl"
    report_path = tmp_path / "report.json"
    config = PackConfig(
        root=tmp_path,
        out=out_path,
        format="jsonl",
        report=report_path,
        workers=1,
        include_sha256=False,
        fail_on_policy_violation=True,
        policy_fail_level="high",
        policy_rules=[
            {
                "rule_id": "convert-secret",
                "description": "Secret marker detected",
                "stage": "convert",
                "content_regex": "SECRET_[0-9]+",
                "severity": "high",
                "action": "deny",
            }
        ],
    )

    with pytest.raises(typer.Exit) as exc_info:
        packer.pack(config)

    assert exc_info.value.exit_code == 4
    assert out_path.exists()
    assert report_path.exists()


def test_pack_policy_enforcement_respects_severity_threshold(tmp_path: Path) -> None:
    (tmp_path / "data.txt").write_text("token SECRET_123\n", encoding="utf-8")
    out_path = tmp_path / "out.jsonl"
    config = PackConfig(
        root=tmp_path,
        out=out_path,
        format="jsonl",
        workers=1,
        include_sha256=False,
        fail_on_policy_violation=True,
        policy_fail_level="critical",
        policy_rules=[
            {
                "rule_id": "convert-secret",
                "description": "Secret marker detected",
                "stage": "convert",
                "content_regex": "SECRET_[0-9]+",
                "severity": "high",
                "action": "deny",
            }
        ],
    )

    packer.pack(config)
    assert out_path.exists()


def test_pack_policy_enforcement_ignores_warn_findings(tmp_path: Path) -> None:
    (tmp_path / "data.txt").write_text("token SECRET_123\n", encoding="utf-8")
    out_path = tmp_path / "out.jsonl"
    config = PackConfig(
        root=tmp_path,
        out=out_path,
        format="jsonl",
        workers=1,
        include_sha256=False,
        fail_on_policy_violation=True,
        policy_fail_level="low",
        policy_rules=[
            {
                "rule_id": "convert-secret-advisory",
                "description": "Secret marker detected",
                "stage": "convert",
                "content_regex": "SECRET_[0-9]+",
                "severity": "critical",
                "action": "warn",
            }
        ],
    )

    packer.pack(config)
    assert out_path.exists()


def test_pack_policy_dry_run_honors_enforcement_threshold(tmp_path: Path) -> None:
    (tmp_path / "secret.txt").write_text("token SECRET_123\n", encoding="utf-8")
    config = PackConfig(
        root=tmp_path,
        workers=1,
        policy_dry_run=True,
        policy_output="json",
        fail_on_policy_violation=True,
        policy_fail_level="high",
        policy_rules=[
            {
                "rule_id": "deny-secret",
                "description": "Reject secret marker",
                "stage": "convert",
                "content_regex": "SECRET_[0-9]+",
                "severity": "high",
                "action": "deny",
            }
        ],
    )

    with pytest.raises(typer.Exit) as exc_info:
        packer.pack(config)

    assert exc_info.value.exit_code == 4


def test_pack_policy_findings_do_not_fail_without_enforcement_flag(tmp_path: Path) -> None:
    (tmp_path / "data.txt").write_text("token SECRET_123\n", encoding="utf-8")
    out_path = tmp_path / "out.jsonl"
    config = PackConfig(
        root=tmp_path,
        out=out_path,
        format="jsonl",
        workers=1,
        include_sha256=False,
        fail_on_policy_violation=False,
        policy_fail_level="critical",
        policy_rules=[
            {
                "rule_id": "convert-secret",
                "description": "Secret marker detected",
                "stage": "convert",
                "content_regex": "SECRET_[0-9]+",
                "severity": "critical",
                "action": "deny",
            }
        ],
    )

    packer.pack(config)
    assert out_path.exists()


def test_count_failing_policy_findings_handles_unknown_or_non_string_severities() -> None:
    count = packer._count_failing_policy_findings(
        [
            {"severity": "medium"},
            {"severity": "unknown"},
            {"severity": 1},
            {},
        ],
        min_severity="medium",
    )

    assert count == 1


def test_deny_policy_findings_filters_non_deny_actions() -> None:
    findings = [
        {"action": "warn", "severity": "critical"},
        {"action": "deny", "severity": "medium"},
        {"action": 1},
        {},
    ]

    assert packer._deny_policy_findings(findings) == [{"action": "deny", "severity": "medium"}]


def test_format_policy_severity_summary_orders_by_defined_severity() -> None:
    summary = packer._format_policy_severity_summary(
        {"critical": 2, "low": 1, "zzz": 3, "medium": 4}
    )
    assert summary == "low=1, medium=4, critical=2, zzz=3"


def test_build_policy_stage_counts_ignores_non_string_stage_values() -> None:
    counts = packer._build_policy_stage_counts(
        [
            {"stage": "convert"},
            {"stage": 1},
            {},
        ]
    )

    assert counts == {"convert": 1}


def test_truncate_text_middle_returns_original_when_content_already_fits() -> None:
    content, truncated = packer._truncate_text_middle("plain text", 64, "utf-8")

    assert content == "plain text"
    assert truncated is False


def test_truncate_text_middle_preserves_valid_utf8_around_multibyte_boundaries() -> None:
    content = "אבג🙂דהו🙂זחט"

    truncated_content, truncated = packer._truncate_text_middle(content, 20, "utf-8")

    assert truncated is True
    assert "[TRUNCATED]" in truncated_content
    assert "\ufffd" not in truncated_content
    assert len(truncated_content.encode("utf-8")) <= 20


def test_truncate_text_middle_handles_max_bytes_smaller_than_separator() -> None:
    truncated_content, truncated = packer._truncate_text_middle("abcdef", 4, "utf-8")

    assert truncated is True
    assert truncated_content == b"\n\n..".decode("utf-8", errors="ignore")
    assert len(truncated_content.encode("utf-8")) <= 4


def test_pack_keeps_deterministic_order_after_parallel_conversion(
    tmp_path: Path, monkeypatch
) -> None:
    _write(tmp_path / "a.txt", "aaa\n")
    _write(tmp_path / "b.txt", "bbb\n")

    class _SlowConverter:
        def convert(self, path: Path, encoding: str = "utf-8") -> ConversionResult:
            if path.name == "a.txt":
                time.sleep(0.05)
            return ConversionResult(
                content=path.read_text(encoding=encoding),
                converter_name="slow",
                original_mime="text/plain",
            )

    captured_order: list[str] = []

    class _CaptureWriter:
        def write(self, out, header, items) -> None:
            captured_order.extend(item.relpath for item in items)
            out.write("ok\n")

    monkeypatch.setattr(
        packer, "_build_registry", lambda _config: _SingleConverterRegistry(_SlowConverter())
    )
    monkeypatch.setattr(packer, "_get_writer", lambda *args, **kwargs: _CaptureWriter())

    config = PackConfig(
        root=tmp_path,
        out=tmp_path / "out.md",
        format="md",
        workers=2,
        include_sha256=False,
    )
    packer.pack(config)

    assert captured_order == ["a.txt", "b.txt"]


def test_pack_include_toc_false_omits_table_of_contents(tmp_path: Path) -> None:
    _write(tmp_path / "a.txt", "hello\n")
    out_path = tmp_path / "out.md"
    config = PackConfig(
        root=tmp_path,
        out=out_path,
        format="md",
        include_toc=False,
        include_sha256=False,
        workers=1,
    )

    packer.pack(config)
    output = out_path.read_text(encoding="utf-8")
    assert "Table of Contents" not in output
