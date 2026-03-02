from __future__ import annotations

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
    build_skipped_file_entry,
    write_report,
)
from .scanner import FileRecord, scan
from .utils import mtime_iso, sha256_file, utcnow_iso
from .writers.base import FileBundleItem, HeaderInfo
from .writers.jsonl_writer import JsonlWriter
from .writers.markdown_writer import MarkdownWriter
from .writers.xml_writer import XmlWriter

console = Console(stderr=True)


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
                from .utils import apply_redaction

                redacted_content = apply_redaction(content, config.redact)
                redacted = redacted_content != content
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
        truncated=truncated,
        redacted=redacted,
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

    if policy_findings:
        policy_counts = build_policy_finding_counts(
            policy_findings=[asdict(finding) for finding in policy_findings]
        )
        by_severity = cast(dict[str, int], policy_counts["by_severity"])
        severity_summary = ", ".join(f"{sev}={count}" for sev, count in by_severity.items())
        suffix = f" ({severity_summary})" if severity_summary else ""
        console.print(f"[yellow]Policy findings:[/yellow] {policy_counts['total']}{suffix}")

    if config.max_total_bytes is not None and total_bytes > config.max_total_bytes:
        console.print(
            f"[red]Error:[/red] total {total_bytes:,} bytes exceeds --max-total-bytes={config.max_total_bytes:,}",
        )
        raise typer.Exit(code=3)

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

    if config.report:
        policy_finding_entries = [asdict(finding) for finding in policy_findings]
        included_files = [
            build_included_file_entry(
                path=item.relpath,
                size=item.size_bytes,
                ext=item.ext,
                truncated=item.truncated,
                redacted=item.redacted,
                warning_messages=item.warnings,
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
                included_files=included_files, skipped_files=skipped_files
            ),
            policy_finding_counts=build_policy_finding_counts(
                policy_findings=policy_finding_entries
            ),
        )
        write_report(config.report, report_data)
        console.print(f"Report written to {config.report}")
