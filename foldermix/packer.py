from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

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
from .report import ReportData, write_report
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


def _get_writer(fmt: str):
    if fmt == "xml":
        return XmlWriter()
    if fmt == "jsonl":
        return JsonlWriter()
    return MarkdownWriter()


def _convert_record(
    record: FileRecord,
    registry: ConverterRegistry,
    config: PackConfig,
) -> FileBundleItem:
    converter = registry.get_converter(record.ext)
    truncated = False
    warnings: list[str] = []

    if converter is None:
        content = f"[No converter available for {record.ext}]"
        converter_name = "none"
        original_mime = ""
    else:
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
                    result = converter.convert(tmp, config.encoding)
                finally:
                    if tmp.exists():
                        tmp.unlink()
                truncated = True
            else:
                result = converter.convert(record.path, config.encoding)

            content = result.content
            converter_name = result.converter_name
            original_mime = result.original_mime
            warnings = result.warnings

            if config.strip_frontmatter:
                from .utils import strip_yaml_frontmatter

                content = strip_yaml_frontmatter(content)

            if config.redact != "none":
                from .utils import apply_redaction

                content = apply_redaction(content, config.redact)

            if config.line_ending == "crlf":
                content = content.replace("\r\n", "\n").replace("\n", "\r\n")

        except Exception as e:
            if config.continue_on_error:
                content = f"[Error converting file: {e}]"
                converter_name = "error"
                original_mime = ""
                warnings = [str(e)]
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
    )


def pack(config: PackConfig) -> None:
    """Main entry point for packing."""
    console.print(f"[bold]Scanning[/bold] {config.root} ...")
    included, skipped = scan(config)

    console.print(
        f"Found [green]{len(included)}[/green] files, [yellow]{len(skipped)}[/yellow] skipped"
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
    writer = _get_writer(config.format)

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

    if errors and not config.continue_on_error:
        console.print(
            f"[red]{len(errors)} conversion error(s). Use --continue-on-error to skip.[/red]"
        )
        raise typer.Exit(code=2)

    total_bytes = sum(i.size_bytes for i in items)

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
        report_data = ReportData(
            included_count=len(included),
            skipped_count=len(skipped),
            total_bytes=total_bytes,
            included_files=[{"path": r.relpath, "size": r.size, "ext": r.ext} for r in included],
            skipped_files=[{"path": r.relpath, "reason": r.reason} for r in skipped],
        )
        write_report(config.report, report_data)
        console.print(f"Report written to {config.report}")
