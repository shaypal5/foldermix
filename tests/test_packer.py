from __future__ import annotations

import json
import time
from pathlib import Path

import pytest
import typer

from foldermix import packer
from foldermix.config import PackConfig
from foldermix.converters.base import ConversionResult


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


def test_pack_dry_run_does_not_write_output(tmp_path: Path) -> None:
    _write(tmp_path / "a.txt", "hello\n")
    out_path = tmp_path / "out.md"
    config = PackConfig(root=tmp_path, out=out_path, dry_run=True, workers=1)

    packer.pack(config)

    assert not out_path.exists()


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
        lambda: _SingleConverterRegistry(_AlwaysFailConverter()),
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
        lambda: _SingleConverterRegistry(_AlwaysFailConverter()),
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
    assert report["schema_version"] == 3
    assert report["included_count"] == 1
    assert report["skipped_count"] == 1
    assert report["included_files"] == [
        {
            "path": "data.txt",
            "size": 3,
            "ext": ".txt",
            "outcome_codes": [],
            "outcomes": [],
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


def test_pack_report_includes_structured_outcomes(tmp_path: Path) -> None:
    (tmp_path / "big.txt").write_text("Contact foo@example.com.\n" * 32, encoding="utf-8")
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

    warning_messages = [
        outcome["message"]
        for outcome in by_path["latin1.txt"]["outcomes"]
        if outcome["code"] == "OUTCOME_CONVERSION_WARNING"
    ]
    assert any("Encoding fallback" in message for message in warning_messages)

    assert report["reason_code_counts"]["OUTCOME_TRUNCATED"] == 1
    assert report["reason_code_counts"]["OUTCOME_REDACTED"] == 1
    assert report["reason_code_counts"]["OUTCOME_CONVERSION_WARNING"] == 1


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
    assert report["schema_version"] == 3
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
        packer, "_build_registry", lambda: _SingleConverterRegistry(_SlowConverter())
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
