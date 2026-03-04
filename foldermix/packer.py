from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from pathlib import Path
from typing import cast

import typer
from rich.console import Console

from . import __version__
from .config import PackConfig
from .converters.base import ConverterRegistry
from .converters.docx_fallback import DocxFallbackConverter
from .converters.markitdown_conv import MarkitdownConverter
from .converters.pdf_fallback import PdfFallbackConverter
from .converters.pptx_fallback import PptxFallbackConverter
from .converters.text import TextConverter
from .converters.xlsx_fallback import XlsxFallbackConverter
from .policy import PolicyEvaluator, normalize_policy_rules
from .policy_packs import combine_policy_rules
from .report import (
    ReportData,
    build_included_file_entry,
    build_policy_finding_counts,
    build_reason_code_counts,
    build_redaction_summary,
    build_skipped_file_entry,
    write_report,
)
from .scanner import FileRecord, SkipRecord, scan
from .utils import mtime_iso, sha256_file, utcnow_iso
from .warning_taxonomy import normalize_warning_entries
from .writers.base import FileBundleItem, HeaderInfo
from .writers.jsonl_writer import JsonlWriter
from .writers.markdown_writer import MarkdownWriter
from .writers.xml_writer import XmlWriter

console = Console(stderr=True)
_POLICY_SEVERITY_ORDER: tuple[str, ...] = ("low", "medium", "high", "critical")
_POLICY_SEVERITY_RANK = {severity: idx for idx, severity in enumerate(_POLICY_SEVERITY_ORDER)}


def _count_failing_policy_findings(
    policy_findings: list[dict[str, object]], *, min_severity: str
) -> int:
    threshold_rank = _POLICY_SEVERITY_RANK[min_severity]
    failing_count = 0
    for finding in policy_findings:
        severity = finding.get("severity")
        if not isinstance(severity, str):
            continue
        severity_rank = _POLICY_SEVERITY_RANK.get(severity)
        if severity_rank is None:
            continue
        if severity_rank >= threshold_rank:
            failing_count += 1
    return failing_count


def _deny_policy_findings(policy_findings: list[dict[str, object]]) -> list[dict[str, object]]:
    return [
        finding
        for finding in policy_findings
        if isinstance(finding.get("action"), str) and finding.get("action") == "deny"
    ]


def _format_policy_severity_summary(by_severity: dict[str, int]) -> str:
    ordered_keys = [key for key in _POLICY_SEVERITY_ORDER if key in by_severity]
    ordered_keys.extend(sorted(key for key in by_severity if key not in _POLICY_SEVERITY_RANK))
    return ", ".join(f"{severity}={by_severity[severity]}" for severity in ordered_keys)


def _build_policy_stage_counts(policy_findings: list[dict[str, object]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for finding in policy_findings:
        stage = finding.get("stage")
        if isinstance(stage, str):
            counts[stage] = counts.get(stage, 0) + 1
    return dict(sorted(counts.items()))


def _build_affected_files(policy_findings: list[dict[str, object]]) -> list[dict[str, object]]:
    counts: dict[str, int] = {}
    for finding in policy_findings:
        path = finding.get("path")
        if isinstance(path, str):
            counts[path] = counts.get(path, 0) + 1
    return [{"path": path, "finding_count": counts[path]} for path in sorted(counts)]


def _sorted_policy_findings(policy_findings: list[dict[str, object]]) -> list[dict[str, object]]:
    def _finding_sort_key(
        finding: dict[str, object],
    ) -> tuple[int, str, str, str, str, str, str, str]:
        raw_path = finding.get("path")
        path = raw_path if isinstance(raw_path, str) else ""
        path_rank = 0 if isinstance(raw_path, str) else 1
        stage = finding.get("stage")
        rule_id = finding.get("rule_id")
        reason_code = finding.get("reason_code")
        severity = finding.get("severity")
        action = finding.get("action")
        message = finding.get("message")
        return (
            path_rank,
            path,
            stage if isinstance(stage, str) else "",
            rule_id if isinstance(rule_id, str) else "",
            reason_code if isinstance(reason_code, str) else "",
            severity if isinstance(severity, str) else "",
            action if isinstance(action, str) else "",
            message if isinstance(message, str) else "",
        )

    return sorted(policy_findings, key=_finding_sort_key)


def _build_policy_dry_run_payload(
    *, policy_findings: list[dict[str, object]], policy_counts: dict[str, object] | None
) -> dict[str, object]:
    counts = policy_counts or {
        "total": len(policy_findings),
        "by_severity": {},
        "by_action": {},
        "by_reason_code": {},
    }
    sorted_findings = _sorted_policy_findings(policy_findings)
    return {
        "schema_version": 1,
        "mode": "policy_dry_run",
        "finding_count": len(sorted_findings),
        "by_severity": counts["by_severity"],
        "by_action": counts["by_action"],
        "by_reason_code": counts["by_reason_code"],
        "by_stage": _build_policy_stage_counts(sorted_findings),
        "affected_files": _build_affected_files(sorted_findings),
        "non_file_finding_count": sum(
            1 for finding in sorted_findings if not isinstance(finding.get("path"), str)
        ),
        "findings": sorted_findings,
    }


def _print_policy_dry_run_text(payload: dict[str, object]) -> None:
    finding_count = cast(int, payload["finding_count"])
    by_severity = cast(dict[str, int], payload["by_severity"])
    affected_files = cast(list[dict[str, object]], payload["affected_files"])
    non_file_finding_count = cast(int, payload["non_file_finding_count"])

    console.print("[bold]Policy dry run complete.[/bold] No packed output written.")
    severity_summary = _format_policy_severity_summary(by_severity)
    suffix = f" ({severity_summary})" if severity_summary else ""
    console.print(f"[yellow]Policy findings:[/yellow] {finding_count}{suffix}")

    if affected_files:
        console.print(f"Affected files: {len(affected_files)}")
        for entry in affected_files:
            path = cast(str, entry["path"])
            finding_total = cast(int, entry["finding_count"])
            console.print(f"  [cyan]{path}[/cyan] ({finding_total} findings)")
    else:
        console.print("Affected files: 0")

    if non_file_finding_count:
        console.print(f"Non-file findings: {non_file_finding_count}")


def _write_report_if_requested(
    *,
    config: PackConfig,
    items: list[FileBundleItem],
    skipped: list[SkipRecord],
    total_bytes: int,
    policy_finding_entries: list[dict[str, object]],
    policy_counts: dict[str, object] | None,
) -> None:
    if not config.report:
        return

    included_files = [
        build_included_file_entry(
            path=item.relpath,
            size=item.size_bytes,
            ext=item.ext,
            truncated=item.truncated,
            redacted=item.redacted,
            redaction_event_count=item.redaction_event_count,
            redaction_categories=item.redaction_categories,
            warning_entries=item.warning_entries,
            redact_mode=config.redact,
        )
        for item in items
    ]
    skipped_files = [build_skipped_file_entry(path=r.relpath, reason=r.reason) for r in skipped]
    report_data = ReportData(
        included_count=len(items),
        skipped_count=len(skipped),
        total_bytes=total_bytes,
        included_files=included_files,
        skipped_files=skipped_files,
        policy_findings=policy_finding_entries,
        reason_code_counts=build_reason_code_counts(
            included_files=included_files,
            skipped_files=skipped_files,
        ),
        redaction_summary=build_redaction_summary(
            included_files=included_files,
            default_mode=config.redact,
        ),
        policy_finding_counts=(
            policy_counts
            if policy_counts is not None
            else build_policy_finding_counts(policy_findings=policy_finding_entries)
        ),
    )
    write_report(config.report, report_data)
    console.print(f"Report written to {config.report}")


def _enforce_policy_threshold_if_requested(
    *,
    enabled: bool,
    policy_findings: list[dict[str, object]],
    min_severity: str,
) -> None:
    if not enabled or not policy_findings:
        return

    deny_policy_findings = _deny_policy_findings(policy_findings)
    failing_count = _count_failing_policy_findings(
        deny_policy_findings,
        min_severity=min_severity,
    )
    if failing_count > 0:
        console.print(
            "[red]Policy enforcement failed:[/red] "
            f"{failing_count} deny finding(s) at or above "
            f"--policy-fail-level={min_severity!r}"
        )
        raise typer.Exit(code=4)


def _build_registry() -> ConverterRegistry:
    registry = ConverterRegistry()
    registry.register(MarkitdownConverter())
    registry.register(PdfFallbackConverter())
    registry.register(DocxFallbackConverter())
    registry.register(XlsxFallbackConverter())
    registry.register(PptxFallbackConverter())
    registry.register(TextConverter())
    return registry


def _get_writer(fmt: str, include_toc: bool = True):
    if fmt == "xml":
        return XmlWriter()
    if fmt == "jsonl":
        return JsonlWriter()
    return MarkdownWriter(include_toc=include_toc)


def _convert_record(
    record: FileRecord,
    registry: ConverterRegistry,
    config: PackConfig,
) -> FileBundleItem:
    converter = registry.get_converter(record.ext)
    warnings: list[str] = []
    if record.ext == ".pdf" and config.pdf_ocr:
        pdf_converter = PdfFallbackConverter()
        if pdf_converter.can_convert(record.ext):
            converter = pdf_converter
        else:
            message = (
                "PDF OCR is enabled, but PDF/OCR dependencies are unavailable. "
                "Install the PDF/OCR extras (for example, 'pip install foldermix[ocr]') "
                "or disable --pdf-ocr."
            )
            if config.pdf_ocr_strict:
                raise RuntimeError(message)
            warnings.append(message)
    truncated = False
    redacted = False
    redaction_event_count = 0
    redaction_categories: list[str] = []

    if converter is None:
        content = f"[No converter available for {record.ext}]"
        converter_name = "none"
        original_mime = ""
    else:

        def run_convert(path: Path):
            if isinstance(converter, PdfFallbackConverter):
                return converter.convert(
                    path,
                    config.encoding,
                    enable_ocr=config.pdf_ocr,
                    ocr_strict=config.pdf_ocr_strict,
                )
            return converter.convert(path, config.encoding)

        try:
            if config.on_oversize == "truncate" and record.size > config.max_bytes:
                # Truncate: read first K and last K bytes
                k = config.max_bytes // 2
                with open(record.path, "rb") as f:
                    head = f.read(k)
                    f.seek(-min(k, record.size - k), 2)
                    tail = f.read(k)
                sep = b"\n\n... [TRUNCATED] ...\n\n"
                truncated_bytes = head + sep + tail
                tmp = record.path.parent / (record.path.name + ".truncated.tmp")
                try:
                    tmp.write_bytes(truncated_bytes)
                    result = run_convert(tmp)
                finally:
                    if tmp.exists():
                        tmp.unlink()
                truncated = True
            else:
                result = run_convert(record.path)

            content = result.content
            converter_name = result.converter_name
            original_mime = result.original_mime
            warnings.extend(result.warnings)

            if config.strip_frontmatter:
                from .utils import strip_yaml_frontmatter

                content = strip_yaml_frontmatter(content)

            if config.redact != "none":
                from .utils import apply_redaction_with_trace

                redacted_content, category_counts = apply_redaction_with_trace(
                    content, config.redact
                )
                redaction_event_count = sum(category_counts.values())
                redaction_categories = sorted(category_counts)
                redacted = redaction_event_count > 0
                content = redacted_content

            if config.line_ending == "crlf":
                content = content.replace("\r\n", "\n").replace("\n", "\r\n")

        except Exception as e:
            if config.continue_on_error:
                content = f"[Error converting file: {e}]"
                converter_name = "error"
                original_mime = ""
                warnings.append(str(e))
            else:
                raise

    sha256: str | None = None
    if config.include_sha256:
        try:
            sha256 = sha256_file(record.path)
        except OSError:
            pass

    return FileBundleItem(
        relpath=record.relpath,
        ext=record.ext,
        size_bytes=record.size,
        mtime=mtime_iso(record.path),
        sha256=sha256,
        content=content,
        converter_name=converter_name,
        original_mime=original_mime,
        warnings=warnings,
        warning_entries=normalize_warning_entries(warnings),
        truncated=truncated,
        redacted=redacted,
        redaction_mode=config.redact,
        redaction_event_count=redaction_event_count,
        redaction_categories=redaction_categories,
    )


def pack(config: PackConfig) -> None:
    """Main entry point for packing."""
    policy_evaluator: PolicyEvaluator | None = None
    try:
        raw_policy_rules = combine_policy_rules(
            policy_pack=config.policy_pack,
            policy_rules=config.policy_rules,
        )
    except ValueError as exc:
        console.print(f"[red]Invalid policy configuration:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    if raw_policy_rules:
        try:
            policy_rules = normalize_policy_rules(raw_policy_rules)
        except ValueError as exc:
            console.print(f"[red]Invalid policy configuration:[/red] {exc}")
            raise typer.Exit(code=1) from exc
        policy_evaluator = PolicyEvaluator(policy_rules)

    policy_findings = []

    console.print(f"[bold]Scanning[/bold] {config.root} ...")
    included, skipped = scan(config)

    console.print(
        f"Found [green]{len(included)}[/green] files, [yellow]{len(skipped)}[/yellow] skipped"
    )

    if policy_evaluator is not None:
        for record in included:
            policy_findings.extend(
                policy_evaluator.evaluate_scan_included(
                    path=record.relpath,
                    ext=record.ext,
                    size_bytes=record.size,
                )
            )
        for skip in skipped:
            policy_findings.extend(
                policy_evaluator.evaluate_scan_skipped(
                    path=skip.relpath,
                    skip_reason=skip.reason,
                )
            )

    # Check limits
    if config.max_files is not None and len(included) > config.max_files:
        console.print(
            f"[red]Error:[/red] {len(included)} files exceeds --max-files={config.max_files}",
        )
        raise typer.Exit(code=3)

    if config.dry_run:
        for r in included:
            console.print(f"  [cyan]{r.relpath}[/cyan] ({r.size:,} bytes)")
        console.print(f"\n[bold]Dry run complete.[/bold] Would pack {len(included)} files.")
        return

    registry = _build_registry()
    writer = _get_writer(config.format, include_toc=config.include_toc)

    # Convert files
    items: list[FileBundleItem] = []
    errors: list[str] = []

    use_progress = config.progress
    try:
        import tqdm as _tqdm  # noqa: F401

        has_tqdm = True
    except ImportError:
        has_tqdm = False

    def convert_with_idx(record: FileRecord) -> tuple[FileRecord, FileBundleItem | Exception]:
        try:
            item = _convert_record(record, registry, config)
            return record, item
        except Exception as e:
            return record, e

    if use_progress and has_tqdm:
        from tqdm import tqdm

        with ThreadPoolExecutor(max_workers=config.workers) as executor:
            futures = {executor.submit(convert_with_idx, r): r for r in included}
            results = []
            for future in tqdm(as_completed(futures), total=len(included), desc="Converting"):
                results.append(future.result())
    else:
        with ThreadPoolExecutor(max_workers=config.workers) as executor:
            futures = {executor.submit(convert_with_idx, r): r for r in included}
            results = [f.result() for f in as_completed(futures)]

    # Re-sort to maintain deterministic order
    record_to_item: dict[str, FileBundleItem | Exception] = {}
    for record, result in results:
        record_to_item[record.relpath] = result

    for record in included:
        result = record_to_item[record.relpath]
        if isinstance(result, Exception):
            errors.append(f"{record.relpath}: {result}")
            console.print(f"[red]Error[/red] converting {record.relpath}: {result}")
        else:
            items.append(result)
            if policy_evaluator is not None:
                policy_findings.extend(
                    policy_evaluator.evaluate_converted(
                        path=result.relpath,
                        ext=result.ext,
                        size_bytes=result.size_bytes,
                        content=result.content,
                    )
                )

    if errors and not config.continue_on_error:
        console.print(
            f"[red]{len(errors)} conversion error(s). Use --continue-on-error to skip.[/red]"
        )
        raise typer.Exit(code=2)

    total_bytes = sum(i.size_bytes for i in items)

    if policy_evaluator is not None:
        policy_findings.extend(
            policy_evaluator.evaluate_pack_summary(
                file_count=len(items),
                total_bytes=total_bytes,
            )
        )

    policy_finding_entries = [asdict(finding) for finding in policy_findings]
    policy_counts: dict[str, object] | None = None
    if policy_finding_entries:
        policy_counts = build_policy_finding_counts(policy_findings=policy_finding_entries)
        by_severity = cast(dict[str, int], policy_counts["by_severity"])
        severity_summary = _format_policy_severity_summary(by_severity)
        suffix = f" ({severity_summary})" if severity_summary else ""
        console.print(f"[yellow]Policy findings:[/yellow] {policy_counts['total']}{suffix}")

    if config.max_total_bytes is not None and total_bytes > config.max_total_bytes:
        console.print(
            f"[red]Error:[/red] total {total_bytes:,} bytes exceeds --max-total-bytes={config.max_total_bytes:,}",
        )
        raise typer.Exit(code=3)

    if config.policy_dry_run:
        policy_payload = _build_policy_dry_run_payload(
            policy_findings=policy_finding_entries,
            policy_counts=policy_counts,
        )
        if config.policy_output == "json":
            typer.echo(json.dumps(policy_payload, indent=2, sort_keys=True))
        else:
            _print_policy_dry_run_text(policy_payload)

        _write_report_if_requested(
            config=config,
            items=items,
            skipped=skipped,
            total_bytes=total_bytes,
            policy_finding_entries=policy_finding_entries,
            policy_counts=policy_counts,
        )
        _enforce_policy_threshold_if_requested(
            enabled=config.fail_on_policy_violation,
            policy_findings=policy_finding_entries,
            min_severity=config.policy_fail_level,
        )
        return

    header = HeaderInfo(
        root=str(config.root),
        generated_at=utcnow_iso(),
        version=__version__,
        args={},
        file_count=len(items),
        total_bytes=total_bytes,
    )

    # Determine output path
    out_path = config.out
    if out_path is None:
        ext_map = {"md": "md", "xml": "xml", "jsonl": "jsonl"}
        from datetime import datetime, timezone

        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        out_path = Path(f"foldermix_{ts}.{ext_map[config.format]}")

    console.print(f"Writing to [bold]{out_path}[/bold] ...")

    with open(out_path, "w", encoding="utf-8", newline="") as f:
        writer.write(f, header, items)

    console.print(f"[green]Done![/green] {len(items)} files, {total_bytes:,} bytes -> {out_path}")

    _write_report_if_requested(
        config=config,
        items=items,
        skipped=skipped,
        total_bytes=total_bytes,
        policy_finding_entries=policy_finding_entries,
        policy_counts=policy_counts,
    )
    _enforce_policy_threshold_if_requested(
        enabled=config.fail_on_policy_violation,
        policy_findings=policy_finding_entries,
        min_severity=config.policy_fail_level,
    )
