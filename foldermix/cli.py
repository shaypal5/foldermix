from __future__ import annotations

import json
import os
import shlex
import sys
from pathlib import Path

import typer
from rich.console import Console

from . import __version__
from .config import DEFAULT_EXCLUDE_DIRS, DEFAULT_EXCLUDE_EXT, PackConfig
from .config_loader import ConfigLoadError, load_command_config
from .converters.base import ConverterRegistry
from .converters.registry import build_converter_registry
from .effective_config import EffectiveConfig, effective_config_payload, merge_config_layers
from .init_profiles import available_profiles, has_profile, render_profile_config
from .report import build_skipped_file_entry
from .scanner import FileRecord, SkipRecord
from .stdin_paths import parse_stdin_paths

_INIT_PROFILE_CHOICES = ", ".join(available_profiles())

app = typer.Typer(
    name="foldermix",
    help=(
        "Pack a folder into a single LLM-friendly context file.\n\n"
        "Commands:\n\n"
        "  init    – Generate a starter foldermix.toml from a local-use profile.\n\n"
        "  pack    – Scan a directory and write all files into one output file.\n\n"
        "  list    – Preview which files would be included without packing.\n\n"
        "  skiplist – Preview which files would be skipped, with reasons.\n\n"
        "  preview – Render selected files to stdout in pack output format.\n\n"
        "  stats   – Show file-count and byte-size statistics for a directory.\n\n"
        "  version – Print the installed foldermix version.\n\n"
        "Run 'foldermix COMMAND --help' for detailed options on any command.\n\n"
        "Guides:\n\n"
        "  Config-first workflows: https://github.com/shaypal5/foldermix/blob/main/docs/config-first-workflows.md\n\n"
        "  Compliance & safety:   https://github.com/shaypal5/foldermix/blob/main/docs/compliance-safety.md"
    ),
    add_completion=False,
)
console = Console()

_PACK_PARAM_BY_KEY = {
    "root": "path",
    "out": "out",
    "format": "format",
    "include_ext": "include_ext",
    "exclude_ext": "exclude_ext",
    "exclude_dirs": "exclude_dirs",
    "exclude_glob": "exclude_glob",
    "include_glob": "include_glob",
    "max_bytes": "max_bytes",
    "max_total_bytes": "max_total_bytes",
    "max_files": "max_files",
    "hidden": "hidden",
    "follow_symlinks": "follow_symlinks",
    "respect_gitignore": "respect_gitignore",
    "line_ending": "line_ending",
    "encoding": "encoding",
    "workers": "workers",
    "progress": "progress",
    "dry_run": "dry_run",
    "report": "report",
    "continue_on_error": "continue_on_error",
    "on_oversize": "on_oversize",
    "redact": "redact",
    "drop_line_containing": "drop_line_containing",
    "min_line_length": "min_line_length",
    "strip_frontmatter": "strip_frontmatter",
    "include_sha256": "include_sha256",
    "include_toc": "include_toc",
    "pdf_ocr": "pdf_ocr",
    "pdf_ocr_strict": "pdf_ocr_strict",
    "policy_pack": "policy_pack",
    "policy_rules": "policy_rules",
    "fail_on_policy_violation": "fail_on_policy_violation",
    "policy_fail_level": "policy_fail_level",
    "policy_dry_run": "policy_dry_run",
    "policy_output": "policy_output",
}

_LIST_PARAM_BY_KEY = {
    "root": "path",
    "include_ext": "include_ext",
    "exclude_ext": "exclude_ext",
    "exclude_dirs": "exclude_dirs",
    "exclude_glob": "exclude_glob",
    "include_glob": "include_glob",
    "max_bytes": "max_bytes",
    "hidden": "hidden",
    "follow_symlinks": "follow_symlinks",
    "respect_gitignore": "respect_gitignore",
    "on_oversize": "on_oversize",
}

_SKIPLIST_PARAM_BY_KEY = {
    "root": "path",
    "include_ext": "include_ext",
    "exclude_ext": "exclude_ext",
    "exclude_dirs": "exclude_dirs",
    "exclude_glob": "exclude_glob",
    "include_glob": "include_glob",
    "max_bytes": "max_bytes",
    "hidden": "hidden",
    "follow_symlinks": "follow_symlinks",
    "respect_gitignore": "respect_gitignore",
    "on_oversize": "on_oversize",
}

_STATS_PARAM_BY_KEY = {
    "root": "path",
    "include_ext": "include_ext",
    "hidden": "hidden",
}

_OPTIONAL_CONVERTER_HINTS: dict[str, str] = {
    ".pdf": (
        "Install PDF support with 'pip install \"foldermix[pdf]\"' "
        "or OCR support with 'pip install \"foldermix[ocr]\"'."
    ),
    ".docx": "Install Office support with 'pip install \"foldermix[office]\"'.",
    ".xlsx": "Install Office support with 'pip install \"foldermix[office]\"'.",
    ".pptx": "Install Office support with 'pip install \"foldermix[office]\"'.",
}


def _parse_csv(val: str | None) -> list[str] | None:
    if val is None:
        return None
    return [v.strip() for v in val.split(",") if v.strip()]


def _parse_repeatable_csv(values: list[str] | None) -> list[str]:
    if not values:
        return []
    parsed: list[str] = []
    for raw in values:
        if "," in raw:
            parsed.extend(part.strip() for part in raw.split(",") if part.strip())
            continue
        stripped = raw.strip()
        if stripped:
            parsed.append(stripped)
    return parsed


def _print_effective_config(
    command: str, merged: EffectiveConfig, config_path: Path | None
) -> None:
    typer.echo(
        json.dumps(
            effective_config_payload(command=command, merged=merged, config_path=config_path),
            indent=2,
            sort_keys=True,
        )
    )


def _validate_positive_max_bytes(command: str, value: object) -> None:
    if value <= 0:
        console.print(
            "[red]Invalid --max-bytes:"
            f" {value!r}. Value must be a positive integer.[/red]\n"
            f"Run 'foldermix {command} --help' for full usage information."
        )
        raise typer.Exit(code=1)


def _read_stdin_paths(use_stdin: bool, null_delimited: bool) -> list[Path] | None:
    if not use_stdin:
        if null_delimited:
            console.print("[red]--null requires --stdin.[/red]")
            raise typer.Exit(code=1)
        return None
    data = sys.stdin.buffer.read()
    return parse_stdin_paths(data, null_delimited=null_delimited, cwd=Path.cwd())


def _build_converter_registry() -> ConverterRegistry:
    return build_converter_registry()


def _conversion_skip_entry(record: FileRecord) -> dict[str, str]:
    ext = record.ext.lower()
    optional_hint = _OPTIONAL_CONVERTER_HINTS.get(ext)
    if optional_hint is not None:
        entry = build_skipped_file_entry(
            path=record.relpath,
            reason="optional_dependency_missing",
        )
        detail = f"No converter is available for extension {ext!r}. {optional_hint}"
        entry["message"] = f"{entry['message']} {detail}".strip()
        return entry
    if ext:
        detail = f"No converter is available for extension {ext!r} with current install."
    else:
        detail = "No converter is available for files without an extension with current install."
    entry = build_skipped_file_entry(
        path=record.relpath,
        reason="unsupported_extension",
    )
    entry["message"] = f"{entry['message']} {detail}".strip()
    return entry


def _build_skiplist_entries(
    *, included: list[FileRecord], skipped: list[SkipRecord], conversion_check: bool
) -> tuple[list[dict[str, str]], int]:
    entries = [
        build_skipped_file_entry(path=skip.relpath, reason=skip.reason)
        for skip in sorted(skipped, key=lambda record: record.relpath.casefold())
    ]
    if not conversion_check:
        return entries, 0

    registry = _build_converter_registry()
    converter_missing_count = 0
    for record in included:
        if registry.get_converter(record.ext) is None:
            entries.append(_conversion_skip_entry(record))
            converter_missing_count += 1
    entries.sort(key=lambda entry: entry["path"].casefold())
    return entries, converter_missing_count


def _resolve_preview_paths(root: Path, files: list[Path]) -> list[Path]:
    resolved: list[Path] = []
    for file_path in files:
        candidate = file_path.expanduser()
        if not candidate.is_absolute():
            candidate = root / candidate
        resolved.append(candidate.resolve())
    return resolved


def _sort_records_by_explicit_path_order(
    records: list[FileRecord], explicit_paths: list[Path]
) -> list[FileRecord]:
    order: dict[str, int] = {}
    for idx, path in enumerate(explicit_paths):
        key = os.path.normcase(str(path))
        if key not in order:
            order[key] = idx
    return sorted(
        records,
        key=lambda record: (
            order.get(os.path.normcase(str(record.path.resolve())), len(order)),
            record.relpath.casefold(),
        ),
    )


@app.command("pack")
def pack_cmd(
    ctx: typer.Context,
    path: Path = typer.Argument(Path("."), help="Directory to pack"),
    config_path: Path | None = typer.Option(
        None, "--config", help="Path to a foldermix TOML config file"
    ),
    out: Path | None = typer.Option(
        None,
        "--out",
        "-o",
        help="Output file path (defaults to the input directory name with the appropriate extension, written next to the input directory)",
    ),
    format: str = typer.Option(
        "md", "--format", "-f", help="Output format: md, xml, jsonl [default: md]"
    ),
    include_ext: str | None = typer.Option(
        None,
        "--include-ext",
        help="Comma-separated file extensions to include (e.g. '.py,.md'). When set, only these extensions are packed.",
    ),
    exclude_ext: str | None = typer.Option(
        None,
        "--exclude-ext",
        help="Comma-separated file extensions to exclude (e.g. '.png,.zip'). Overrides the built-in exclusion list when provided.",
    ),
    exclude_dirs: str | None = typer.Option(
        None,
        "--exclude-dirs",
        help="Comma-separated directory names to exclude (e.g. 'node_modules,dist'). Overrides the built-in exclusion list when provided.",
    ),
    exclude_glob: list[str] | None = typer.Option(
        None,
        "--exclude-glob",
        help="Glob pattern(s) to exclude (e.g. '**/*.min.js'). May be repeated.",
    ),
    include_glob: list[str] | None = typer.Option(
        None,
        "--include-glob",
        help="Glob pattern(s) to include (e.g. 'src/**/*.py'). May be repeated. When set, only matching files are packed.",
    ),
    max_bytes: int = typer.Option(
        10_000_000,
        "--max-bytes",
        help="Maximum size in bytes (10 MB) for a single file. Files larger than this are handled according to --on-oversize [default: 10_000_000]",
        min=1,
    ),
    max_total_bytes: int | None = typer.Option(
        None,
        "--max-total-bytes",
        help="Stop packing after this many total bytes have been written. No limit by default.",
    ),
    max_files: int | None = typer.Option(
        None, "--max-files", help="Stop after packing this many files. No limit by default."
    ),
    hidden: bool = typer.Option(
        False, "--hidden", help="Include hidden files and directories (names starting with '.')"
    ),
    follow_symlinks: bool = typer.Option(
        False, "--follow-symlinks", help="Follow symbolic links when scanning the directory tree"
    ),
    respect_gitignore: bool = typer.Option(
        True,
        "--respect-gitignore/--no-respect-gitignore",
        help="Skip files listed in .gitignore [default: respect]",
    ),
    workers: int = typer.Option(
        4,
        "--workers",
        help="Number of parallel worker threads used for file conversion [default: 4]",
    ),
    progress: bool = typer.Option(
        False, "--progress", help="Show a progress bar while packing (requires the 'tqdm' package)"
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="List the files that would be packed without actually writing any output",
    ),
    report: Path | None = typer.Option(
        None, "--report", help="Write a JSON summary report to this path after packing"
    ),
    continue_on_error: bool = typer.Option(
        False,
        "--continue-on-error",
        help="Skip files that fail to read or convert instead of aborting",
    ),
    on_oversize: str = typer.Option(
        "skip",
        "--on-oversize",
        help="What to do when a file exceeds --max-bytes: 'skip' omits it, 'truncate' includes it up to the limit [default: skip]",
    ),
    redact: str = typer.Option(
        "none",
        "--redact",
        help="Redact sensitive patterns before writing: none, emails, phones, all [default: none]",
    ),
    drop_line_containing: list[str] | None = typer.Option(
        None,
        "--drop-line-containing",
        help=(
            "Drop lines that contain any provided literal substring. "
            "May be repeated; each value can also be comma-separated."
        ),
    ),
    min_line_length: int = typer.Option(
        0,
        "--min-line-length",
        help=(
            "Drop lines shorter than this character length. Use 0 to keep all lines [default: 0]."
        ),
    ),
    strip_frontmatter: bool = typer.Option(
        False,
        "--strip-frontmatter",
        help="Strip YAML frontmatter blocks (--- ... ---) from Markdown files before packing",
    ),
    include_sha256: bool = typer.Option(
        True,
        "--include-sha256/--no-include-sha256",
        help="Embed a SHA-256 checksum for each file in the output [default: include]",
    ),
    include_toc: bool = typer.Option(
        True,
        "--include-toc/--no-include-toc",
        help="Prepend a table of contents to Markdown output [default: include]",
    ),
    pdf_ocr: bool = typer.Option(
        False,
        "--pdf-ocr/--no-pdf-ocr",
        help="Attempt OCR for PDF pages with no extractable text when OCR dependencies are installed [default: disabled]",
    ),
    pdf_ocr_strict: bool = typer.Option(
        False,
        "--pdf-ocr-strict/--no-pdf-ocr-strict",
        help="Fail conversion when OCR is required but unavailable or unsuccessful [default: disabled]",
    ),
    policy_pack: str | None = typer.Option(
        None,
        "--policy-pack",
        help="Apply a built-in policy pack (strict-privacy, legal-hold, customer-support)",
    ),
    fail_on_policy_violation: bool = typer.Option(
        False,
        "--fail-on-policy-violation/--no-fail-on-policy-violation",
        help="Exit non-zero when policy findings meet or exceed --policy-fail-level [default: disabled]",
    ),
    policy_fail_level: str = typer.Option(
        "low",
        "--policy-fail-level",
        help="Minimum severity that triggers failure when --fail-on-policy-violation is enabled: low, medium, high, critical [default: low]",
    ),
    policy_dry_run: bool = typer.Option(
        False,
        "--policy-dry-run/--no-policy-dry-run",
        help="Run policy evaluation preview (including conversion-stage checks) without writing the packed output file",
    ),
    policy_output: str = typer.Option(
        "text",
        "--policy-output",
        help="Policy dry-run output format: text, json [default: text]",
    ),
    stdin: bool = typer.Option(
        False,
        "--stdin",
        help="Read explicit file paths from standard input instead of recursively scanning PATH.",
    ),
    null_delimited: bool = typer.Option(
        False,
        "--null",
        help="Parse stdin paths as NUL-delimited entries (compatible with find -print0). Requires --stdin.",
    ),
    print_effective_config: bool = typer.Option(
        False,
        "--print-effective-config",
        help="Print merged effective configuration with value sources and exit",
    ),
) -> None:
    """Pack a directory into a single context file.

    Recursively scans PATH (default: current directory), converts each
    eligible file to plain text, and writes the result to a single output
    file in the chosen format.

    Examples:

    \b
      # Pack current directory to Markdown (default)
      foldermix pack .

    \b
      # Pack to XML, writing to a specific file
      foldermix pack ./my-project --format xml --out context.xml

    \b
      # Include only Python and Markdown files
      foldermix pack . --include-ext .py,.md

    \b
      # Dry-run: see what would be packed without writing anything
      foldermix pack . --dry-run
    """
    from .packer import pack

    inc_ext = _parse_csv(include_ext)
    exc_ext = _parse_csv(exclude_ext) or list(DEFAULT_EXCLUDE_EXT)
    exc_dirs = _parse_csv(exclude_dirs) or list(DEFAULT_EXCLUDE_DIRS)

    values: dict[str, object] = {
        "root": path,
        "out": out,
        "format": format,
        "include_ext": inc_ext,
        "exclude_ext": exc_ext,
        "exclude_dirs": exc_dirs,
        "exclude_glob": exclude_glob or [],
        "include_glob": include_glob or [],
        "max_bytes": max_bytes,
        "max_total_bytes": max_total_bytes,
        "max_files": max_files,
        "hidden": hidden,
        "follow_symlinks": follow_symlinks,
        "respect_gitignore": respect_gitignore,
        "line_ending": "lf",
        "encoding": "utf-8",
        "workers": workers,
        "progress": progress,
        "dry_run": dry_run,
        "report": report,
        "continue_on_error": continue_on_error,
        "on_oversize": on_oversize,
        "redact": redact,
        "drop_line_containing": _parse_repeatable_csv(drop_line_containing),
        "min_line_length": min_line_length,
        "strip_frontmatter": strip_frontmatter,
        "include_sha256": include_sha256,
        "include_toc": include_toc,
        "pdf_ocr": pdf_ocr,
        "pdf_ocr_strict": pdf_ocr_strict,
        "policy_pack": policy_pack,
        "policy_rules": [],
        "fail_on_policy_violation": fail_on_policy_violation,
        "policy_fail_level": policy_fail_level,
        "policy_dry_run": policy_dry_run,
        "policy_output": policy_output,
    }

    try:
        overrides, used_config_path = load_command_config(
            "pack", root=path, config_path=config_path
        )
    except ConfigLoadError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    merged = merge_config_layers(
        ctx,
        defaults=values,
        config_overrides=overrides,
        key_to_param_name=_PACK_PARAM_BY_KEY,
    )
    if print_effective_config:
        _print_effective_config("pack", merged, used_config_path)
        return
    values = merged.values
    _validate_positive_max_bytes("pack", values["max_bytes"])
    policy_output_explicitly_set = merged.sources.get("policy_output") != "default"

    if values["format"] not in ("md", "xml", "jsonl"):
        console.print(
            "[red]Invalid format:"
            f" {values['format']!r}. Valid choices are: md, xml, jsonl.[/red]\n"
            "Run 'foldermix pack --help' for full usage information."
        )
        raise typer.Exit(code=1)

    if values["on_oversize"] not in ("skip", "truncate"):
        console.print(
            "[red]Invalid --on-oversize:"
            f" {values['on_oversize']!r}. Valid choices are: skip, truncate.[/red]\n"
            "Run 'foldermix pack --help' for full usage information."
        )
        raise typer.Exit(code=1)

    if values["redact"] not in ("none", "emails", "phones", "all"):
        console.print(
            "[red]Invalid --redact:"
            f" {values['redact']!r}. Valid choices are: none, emails, phones, all.[/red]\n"
            "Run 'foldermix pack --help' for full usage information."
        )
        raise typer.Exit(code=1)

    if values["min_line_length"] < 0:
        console.print(
            "[red]Invalid --min-line-length:"
            f" {values['min_line_length']!r}. Value must be a non-negative integer.[/red]\n"
            "Run 'foldermix pack --help' for full usage information."
        )
        raise typer.Exit(code=1)

    if values["policy_fail_level"] not in ("low", "medium", "high", "critical"):
        console.print(
            "[red]Invalid --policy-fail-level:"
            f" {values['policy_fail_level']!r}. Valid choices are: low, medium, high, critical.[/red]\n"
            "Run 'foldermix pack --help' for full usage information."
        )
        raise typer.Exit(code=1)

    if values["policy_output"] not in ("text", "json"):
        console.print(
            "[red]Invalid --policy-output:"
            f" {values['policy_output']!r}. Valid choices are: text, json.[/red]\n"
            "Run 'foldermix pack --help' for full usage information."
        )
        raise typer.Exit(code=1)

    if policy_output_explicitly_set and not values["policy_dry_run"]:
        console.print(
            "[red]--policy-output requires --policy-dry-run.[/red]\n"
            "Run 'foldermix pack --help' for full usage information."
        )
        raise typer.Exit(code=1)

    if values["dry_run"] and values["policy_dry_run"]:
        console.print(
            "[red]--dry-run cannot be combined with --policy-dry-run.[/red]\n"
            "Run 'foldermix pack --help' for full usage information."
        )
        raise typer.Exit(code=1)

    stdin_paths = _read_stdin_paths(stdin, null_delimited)
    pack_config = PackConfig(stdin_paths=stdin_paths, **values)  # type: ignore[arg-type]

    pack(pack_config)


@app.command("list")
def list_cmd(
    ctx: typer.Context,
    path: Path = typer.Argument(Path("."), help="Directory to scan"),
    config_path: Path | None = typer.Option(
        None, "--config", help="Path to a foldermix TOML config file"
    ),
    include_ext: str | None = typer.Option(
        None, "--include-ext", help="Comma-separated file extensions to include (e.g. '.py,.md')"
    ),
    exclude_ext: str | None = typer.Option(
        None, "--exclude-ext", help="Comma-separated file extensions to exclude (e.g. '.png,.zip')"
    ),
    exclude_dirs: str | None = typer.Option(
        None,
        "--exclude-dirs",
        help="Comma-separated directory names to exclude (e.g. 'node_modules,dist')",
    ),
    exclude_glob: list[str] | None = typer.Option(
        None,
        "--exclude-glob",
        help="Glob pattern(s) to exclude (e.g. '**/*.min.js'). May be repeated.",
    ),
    include_glob: list[str] | None = typer.Option(
        None,
        "--include-glob",
        help="Glob pattern(s) to include (e.g. 'src/**/*.py'). May be repeated.",
    ),
    max_bytes: int = typer.Option(
        10_000_000,
        "--max-bytes",
        help="Maximum size in bytes (10 MB) for a single file [default: 10_000_000]",
        min=1,
    ),
    hidden: bool = typer.Option(
        False, "--hidden", help="Include hidden files and directories (names starting with '.')"
    ),
    follow_symlinks: bool = typer.Option(
        False, "--follow-symlinks", help="Follow symbolic links when scanning the directory tree"
    ),
    respect_gitignore: bool = typer.Option(
        True,
        "--respect-gitignore/--no-respect-gitignore",
        help="Skip files listed in .gitignore [default: respect]",
    ),
    on_oversize: str = typer.Option(
        "skip",
        "--on-oversize",
        help="What to do when a file exceeds --max-bytes: skip, truncate [default: skip]",
    ),
    stdin: bool = typer.Option(
        False,
        "--stdin",
        help="Read explicit file paths from standard input instead of recursively scanning PATH.",
    ),
    null_delimited: bool = typer.Option(
        False,
        "--null",
        help="Parse stdin paths as NUL-delimited entries (compatible with find -print0). Requires --stdin.",
    ),
    print_effective_config: bool = typer.Option(
        False,
        "--print-effective-config",
        help="Print merged effective configuration with value sources and exit",
    ),
) -> None:
    """List candidate files that would be packed.

    Performs the same file-discovery logic as 'foldermix pack' but only
    prints the resulting file list — nothing is written.  Useful for
    previewing which files would be included before committing to a full
    pack run.

    Examples:

    \b
      # List all files in the current directory
      foldermix list .

    \b
      # List only Python files, including hidden ones
      foldermix list . --include-ext .py --hidden
    """
    from .config import PackConfig
    from .scanner import scan

    values: dict[str, object] = {
        "root": path,
        "include_ext": _parse_csv(include_ext),
        "exclude_ext": _parse_csv(exclude_ext) or list(DEFAULT_EXCLUDE_EXT),
        "exclude_dirs": _parse_csv(exclude_dirs) or list(DEFAULT_EXCLUDE_DIRS),
        "exclude_glob": exclude_glob or [],
        "include_glob": include_glob or [],
        "max_bytes": max_bytes,
        "hidden": hidden,
        "follow_symlinks": follow_symlinks,
        "respect_gitignore": respect_gitignore,
        "on_oversize": on_oversize,
    }
    try:
        overrides, used_config_path = load_command_config(
            "pack", root=path, config_path=config_path
        )
    except ConfigLoadError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    overrides = {key: value for key, value in overrides.items() if key in values}
    merged = merge_config_layers(
        ctx,
        defaults=values,
        config_overrides=overrides,
        key_to_param_name=_LIST_PARAM_BY_KEY,
    )
    if print_effective_config:
        _print_effective_config("list", merged, used_config_path)
        return
    values = merged.values
    _validate_positive_max_bytes("list", values["max_bytes"])
    if values["on_oversize"] not in ("skip", "truncate"):
        console.print(
            "[red]Invalid --on-oversize:"
            f" {values['on_oversize']!r}. Valid choices are: skip, truncate.[/red]\n"
            "Run 'foldermix list --help' for full usage information."
        )
        raise typer.Exit(code=1)
    stdin_paths = _read_stdin_paths(stdin, null_delimited)

    pack_config = PackConfig(
        root=values["root"],  # type: ignore[arg-type]
        stdin_paths=stdin_paths,
        include_ext=values["include_ext"],  # type: ignore[arg-type]
        exclude_ext=values["exclude_ext"],  # type: ignore[arg-type]
        exclude_dirs=values["exclude_dirs"],  # type: ignore[arg-type]
        exclude_glob=values["exclude_glob"],  # type: ignore[arg-type]
        include_glob=values["include_glob"],  # type: ignore[arg-type]
        max_bytes=values["max_bytes"],  # type: ignore[arg-type]
        hidden=values["hidden"],  # type: ignore[arg-type]
        follow_symlinks=values["follow_symlinks"],  # type: ignore[arg-type]
        respect_gitignore=values["respect_gitignore"],  # type: ignore[arg-type]
        on_oversize=values["on_oversize"],  # type: ignore[arg-type]
    )
    included, skipped = scan(pack_config)
    for r in included:
        console.print(f"{r.relpath}  ({r.size:,} bytes)")
    console.print(f"\n{len(included)} files would be included, {len(skipped)} skipped.")


@app.command("stats")
def stats_cmd(
    ctx: typer.Context,
    path: Path = typer.Argument(Path("."), help="Directory to scan"),
    config_path: Path | None = typer.Option(
        None, "--config", help="Path to a foldermix TOML config file"
    ),
    include_ext: str | None = typer.Option(
        None, "--include-ext", help="Comma-separated file extensions to include (e.g. '.py,.md')"
    ),
    hidden: bool = typer.Option(
        False, "--hidden", help="Include hidden files and directories (names starting with '.')"
    ),
    stdin: bool = typer.Option(
        False,
        "--stdin",
        help="Read explicit file paths from standard input instead of recursively scanning PATH.",
    ),
    null_delimited: bool = typer.Option(
        False,
        "--null",
        help="Parse stdin paths as NUL-delimited entries (compatible with find -print0). Requires --stdin.",
    ),
    print_effective_config: bool = typer.Option(
        False,
        "--print-effective-config",
        help="Print merged effective configuration with value sources and exit",
    ),
) -> None:
    """Show summary statistics for a directory.

    Counts files and bytes broken down by file extension, giving a quick
    overview of what a directory contains before you pack it.

    Examples:

    \b
      # Stats for the current directory
      foldermix stats .

    \b
      # Stats for Python files only
      foldermix stats ./src --include-ext .py
    """
    from .config import PackConfig
    from .scanner import scan

    values: dict[str, object] = {
        "root": path,
        "include_ext": _parse_csv(include_ext),
        "hidden": hidden,
    }
    try:
        overrides, used_config_path = load_command_config(
            "stats", root=path, config_path=config_path
        )
    except ConfigLoadError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    merged = merge_config_layers(
        ctx,
        defaults=values,
        config_overrides=overrides,
        key_to_param_name=_STATS_PARAM_BY_KEY,
    )
    if print_effective_config:
        _print_effective_config("stats", merged, used_config_path)
        return
    values = merged.values
    stdin_paths = _read_stdin_paths(stdin, null_delimited)

    pack_config = PackConfig(
        root=values["root"],  # type: ignore[arg-type]
        stdin_paths=stdin_paths,
        include_ext=values["include_ext"],  # type: ignore[arg-type]
        hidden=values["hidden"],  # type: ignore[arg-type]
    )
    included, skipped = scan(pack_config)
    total_bytes = sum(r.size for r in included)

    ext_counts: dict[str, int] = {}
    for r in included:
        ext_counts[r.ext] = ext_counts.get(r.ext, 0) + 1

    console.print(f"[bold]Stats for {path}[/bold]")
    console.print(f"  Included files: {len(included)}")
    console.print(f"  Skipped files:  {len(skipped)}")
    console.print(f"  Total bytes:    {total_bytes:,}")
    console.print("\n  [bold]By extension:[/bold]")
    for ext, count in sorted(ext_counts.items(), key=lambda x: -x[1]):
        console.print(f"    {ext or '(none)':15s} {count:5d}")


@app.command("skiplist")
def skiplist_cmd(
    ctx: typer.Context,
    path: Path = typer.Argument(Path("."), help="Directory to scan"),
    config_path: Path | None = typer.Option(
        None, "--config", help="Path to a foldermix TOML config file"
    ),
    include_ext: str | None = typer.Option(
        None, "--include-ext", help="Comma-separated file extensions to include (e.g. '.py,.md')"
    ),
    exclude_ext: str | None = typer.Option(
        None, "--exclude-ext", help="Comma-separated file extensions to exclude (e.g. '.png,.zip')"
    ),
    exclude_dirs: str | None = typer.Option(
        None,
        "--exclude-dirs",
        help="Comma-separated directory names to exclude (e.g. 'node_modules,dist')",
    ),
    exclude_glob: list[str] | None = typer.Option(
        None,
        "--exclude-glob",
        help="Glob pattern(s) to exclude (e.g. '**/*.min.js'). May be repeated.",
    ),
    include_glob: list[str] | None = typer.Option(
        None,
        "--include-glob",
        help="Glob pattern(s) to include (e.g. 'src/**/*.py'). May be repeated.",
    ),
    max_bytes: int = typer.Option(
        10_000_000,
        "--max-bytes",
        help="Maximum size in bytes (10 MB) for a single file [default: 10_000_000]",
        min=1,
    ),
    hidden: bool = typer.Option(
        False, "--hidden", help="Include hidden files and directories (names starting with '.')"
    ),
    follow_symlinks: bool = typer.Option(
        False, "--follow-symlinks", help="Follow symbolic links when scanning the directory tree"
    ),
    respect_gitignore: bool = typer.Option(
        True,
        "--respect-gitignore/--no-respect-gitignore",
        help="Skip files listed in .gitignore [default: respect]",
    ),
    on_oversize: str = typer.Option(
        "skip",
        "--on-oversize",
        help="What to do when a file exceeds --max-bytes: skip, truncate [default: skip]",
    ),
    conversion_check: bool = typer.Option(
        False,
        "--conversion-check/--scan-only",
        help=(
            "Also include files with no available converter in the current "
            "optional-dependency install [default: scan-only]"
        ),
    ),
    stdin: bool = typer.Option(
        False,
        "--stdin",
        help="Read explicit file paths from standard input instead of recursively scanning PATH.",
    ),
    null_delimited: bool = typer.Option(
        False,
        "--null",
        help="Parse stdin paths as NUL-delimited entries (compatible with find -print0). Requires --stdin.",
    ),
    print_effective_config: bool = typer.Option(
        False,
        "--print-effective-config",
        help="Print merged effective configuration with value sources and exit",
    ),
) -> None:
    """Show files that would be skipped, with reasons.

    By default, this is the inverse of `foldermix list` for scanner-level
    filtering decisions. With `--conversion-check`, it also reports files
    that have no available converter in the current install.

    Examples:

    \b
      # Show scanner-level skipped files
      foldermix skiplist .

    \b
      # Include conversion-availability checks
      foldermix skiplist . --conversion-check
    """
    from .scanner import scan

    values: dict[str, object] = {
        "root": path,
        "include_ext": _parse_csv(include_ext),
        "exclude_ext": _parse_csv(exclude_ext) or list(DEFAULT_EXCLUDE_EXT),
        "exclude_dirs": _parse_csv(exclude_dirs) or list(DEFAULT_EXCLUDE_DIRS),
        "exclude_glob": exclude_glob or [],
        "include_glob": include_glob or [],
        "max_bytes": max_bytes,
        "hidden": hidden,
        "follow_symlinks": follow_symlinks,
        "respect_gitignore": respect_gitignore,
        "on_oversize": on_oversize,
    }
    try:
        overrides, used_config_path = load_command_config(
            "pack", root=path, config_path=config_path
        )
    except ConfigLoadError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    overrides = {key: value for key, value in overrides.items() if key in values}
    merged = merge_config_layers(
        ctx,
        defaults=values,
        config_overrides=overrides,
        key_to_param_name=_SKIPLIST_PARAM_BY_KEY,
    )
    if print_effective_config:
        _print_effective_config("skiplist", merged, used_config_path)
        return
    values = merged.values
    _validate_positive_max_bytes("skiplist", values["max_bytes"])
    if values["on_oversize"] not in ("skip", "truncate"):
        console.print(
            "[red]Invalid --on-oversize:"
            f" {values['on_oversize']!r}. Valid choices are: skip, truncate.[/red]\n"
            "Run 'foldermix skiplist --help' for full usage information."
        )
        raise typer.Exit(code=1)
    stdin_paths = _read_stdin_paths(stdin, null_delimited)

    pack_config = PackConfig(
        root=values["root"],  # type: ignore[arg-type]
        stdin_paths=stdin_paths,
        include_ext=values["include_ext"],  # type: ignore[arg-type]
        exclude_ext=values["exclude_ext"],  # type: ignore[arg-type]
        exclude_dirs=values["exclude_dirs"],  # type: ignore[arg-type]
        exclude_glob=values["exclude_glob"],  # type: ignore[arg-type]
        include_glob=values["include_glob"],  # type: ignore[arg-type]
        max_bytes=values["max_bytes"],  # type: ignore[arg-type]
        hidden=values["hidden"],  # type: ignore[arg-type]
        follow_symlinks=values["follow_symlinks"],  # type: ignore[arg-type]
        respect_gitignore=values["respect_gitignore"],  # type: ignore[arg-type]
        on_oversize=values["on_oversize"],  # type: ignore[arg-type]
    )
    included, skipped = scan(pack_config)
    skip_entries, converter_missing_count = _build_skiplist_entries(
        included=included,
        skipped=skipped,
        conversion_check=conversion_check,
    )
    for entry in skip_entries:
        console.print(
            f"{entry['path']}  [{entry['reason_code']}] {entry['message']}",
            markup=False,
        )
    if conversion_check:
        console.print(
            "\n"
            f"{len(skipped)} files would be skipped by scanning; "
            f"{converter_missing_count} additional files currently lack a supported converter."
        )
    else:
        console.print(f"\n{len(skip_entries)} files would be skipped.")


@app.command("preview")
def preview_cmd(
    ctx: typer.Context,
    path: Path = typer.Argument(
        Path("."), help="Directory root used to resolve relative file paths"
    ),
    files: list[Path] | None = typer.Argument(
        None,
        help=(
            "One or more file paths to preview. Relative paths are resolved against PATH. "
            "Can be combined with --stdin."
        ),
    ),
    config_path: Path | None = typer.Option(
        None, "--config", help="Path to a foldermix TOML config file"
    ),
    format: str = typer.Option(
        "md", "--format", "-f", help="Output format: md, xml, jsonl [default: md]"
    ),
    include_ext: str | None = typer.Option(
        None, "--include-ext", help="Comma-separated file extensions to include (e.g. '.py,.md')"
    ),
    exclude_ext: str | None = typer.Option(
        None, "--exclude-ext", help="Comma-separated file extensions to exclude (e.g. '.png,.zip')"
    ),
    hidden: bool = typer.Option(
        False, "--hidden", help="Include hidden files and directories (names starting with '.')"
    ),
    respect_gitignore: bool = typer.Option(
        True,
        "--respect-gitignore/--no-respect-gitignore",
        help="Skip files listed in .gitignore [default: respect]",
    ),
    max_bytes: int = typer.Option(
        10_000_000,
        "--max-bytes",
        help="Maximum size in bytes (10 MB) for a single file [default: 10_000_000]",
        min=1,
    ),
    on_oversize: str = typer.Option(
        "skip",
        "--on-oversize",
        help="What to do when a file exceeds --max-bytes: skip, truncate [default: skip]",
    ),
    continue_on_error: bool = typer.Option(
        False,
        "--continue-on-error",
        help="Skip files that fail to read or convert instead of aborting",
    ),
    redact: str = typer.Option(
        "none",
        "--redact",
        help="Redact sensitive patterns before rendering: none, emails, phones, all [default: none]",
    ),
    drop_line_containing: list[str] | None = typer.Option(
        None,
        "--drop-line-containing",
        help=(
            "Drop lines that contain any provided literal substring. "
            "May be repeated; each value can also be comma-separated."
        ),
    ),
    min_line_length: int = typer.Option(
        0,
        "--min-line-length",
        help="Drop lines shorter than this length [default: 0]",
    ),
    strip_frontmatter: bool = typer.Option(
        False,
        "--strip-frontmatter",
        help="Strip YAML frontmatter blocks from Markdown files before rendering",
    ),
    include_sha256: bool = typer.Option(
        True,
        "--include-sha256/--no-include-sha256",
        help="Include SHA-256 checksums in output [default: include]",
    ),
    include_toc: bool = typer.Option(
        True,
        "--include-toc/--no-include-toc",
        help="Include a TOC in Markdown output [default: include]",
    ),
    pdf_ocr: bool = typer.Option(
        False,
        "--pdf-ocr/--no-pdf-ocr",
        help="Attempt OCR for PDFs when dependencies are installed [default: disabled]",
    ),
    pdf_ocr_strict: bool = typer.Option(
        False,
        "--pdf-ocr-strict/--no-pdf-ocr-strict",
        help="Fail conversion when OCR is required but unavailable [default: disabled]",
    ),
    stdin: bool = typer.Option(
        False,
        "--stdin",
        help="Read additional file paths from standard input.",
    ),
    null_delimited: bool = typer.Option(
        False,
        "--null",
        help="Parse stdin paths as NUL-delimited entries (compatible with find -print0). Requires --stdin.",
    ),
    print_effective_config: bool = typer.Option(
        False,
        "--print-effective-config",
        help="Print merged effective configuration with value sources and exit",
    ),
) -> None:
    """Render selected file(s) to stdout in packed-output format.

    Examples:

    \b
      # Preview a single file as Markdown (default)
      foldermix preview . README.md

    \b
      # Preview multiple files as JSONL
      foldermix preview . src/a.py src/b.py --format jsonl

    \b
      # Preview files from stdin
      printf 'README.md\nsrc/a.py\n' | foldermix preview . --stdin
    """
    from .packer import render_preview
    from .scanner import scan

    values: dict[str, object] = {
        "root": path,
        "format": format,
        "include_ext": _parse_csv(include_ext),
        "exclude_ext": _parse_csv(exclude_ext) or list(DEFAULT_EXCLUDE_EXT),
        "exclude_dirs": list(DEFAULT_EXCLUDE_DIRS),
        "exclude_glob": [],
        "include_glob": [],
        "hidden": hidden,
        "follow_symlinks": False,
        "respect_gitignore": respect_gitignore,
        "line_ending": "lf",
        "encoding": "utf-8",
        "max_bytes": max_bytes,
        "on_oversize": on_oversize,
        "continue_on_error": continue_on_error,
        "redact": redact,
        "drop_line_containing": _parse_repeatable_csv(drop_line_containing),
        "min_line_length": min_line_length,
        "strip_frontmatter": strip_frontmatter,
        "include_sha256": include_sha256,
        "include_toc": include_toc,
        "pdf_ocr": pdf_ocr,
        "pdf_ocr_strict": pdf_ocr_strict,
    }
    try:
        overrides, used_config_path = load_command_config(
            "pack", root=path, config_path=config_path
        )
    except ConfigLoadError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    merged = merge_config_layers(
        ctx,
        defaults=values,
        config_overrides=overrides,
        key_to_param_name=_PACK_PARAM_BY_KEY,
    )
    if print_effective_config:
        _print_effective_config("preview", merged, used_config_path)
        return
    values = merged.values

    if values["format"] not in ("md", "xml", "jsonl"):
        console.print(
            "[red]Invalid format:"
            f" {values['format']!r}. Valid choices are: md, xml, jsonl.[/red]\n"
            "Run 'foldermix preview --help' for full usage information."
        )
        raise typer.Exit(code=1)
    if values["on_oversize"] not in ("skip", "truncate"):
        console.print(
            "[red]Invalid --on-oversize:"
            f" {values['on_oversize']!r}. Valid choices are: skip, truncate.[/red]\n"
            "Run 'foldermix preview --help' for full usage information."
        )
        raise typer.Exit(code=1)
    if values["redact"] not in ("none", "emails", "phones", "all"):
        console.print(
            "[red]Invalid --redact:"
            f" {values['redact']!r}. Valid choices are: none, emails, phones, all.[/red]\n"
            "Run 'foldermix preview --help' for full usage information."
        )
        raise typer.Exit(code=1)
    if values["min_line_length"] < 0:
        console.print(
            "[red]Invalid --min-line-length:"
            f" {values['min_line_length']!r}. Value must be a non-negative integer.[/red]\n"
            "Run 'foldermix preview --help' for full usage information."
        )
        raise typer.Exit(code=1)

    preview_root = path.resolve()
    arg_files = list(files or [])
    stdin_paths: list[Path] = []
    if stdin:
        data = sys.stdin.buffer.read()
        stdin_paths = parse_stdin_paths(
            data,
            null_delimited=null_delimited,
            cwd=preview_root,
        )
    elif null_delimited:
        console.print("[red]--null requires --stdin.[/red]")
        raise typer.Exit(code=1)
    explicit_paths = _resolve_preview_paths(preview_root, arg_files) + stdin_paths
    if not explicit_paths:
        console.print(
            "[red]No input files provided.[/red]\n"
            "Provide one or more FILE paths as arguments, or use --stdin."
        )
        raise typer.Exit(code=1)

    preview_config = PackConfig(
        root=values["root"],  # type: ignore[arg-type]
        format=values["format"],  # type: ignore[arg-type]
        include_ext=values["include_ext"],  # type: ignore[arg-type]
        exclude_ext=values["exclude_ext"],  # type: ignore[arg-type]
        exclude_dirs=values["exclude_dirs"],  # type: ignore[arg-type]
        exclude_glob=values["exclude_glob"],  # type: ignore[arg-type]
        include_glob=values["include_glob"],  # type: ignore[arg-type]
        hidden=values["hidden"],  # type: ignore[arg-type]
        follow_symlinks=values["follow_symlinks"],  # type: ignore[arg-type]
        respect_gitignore=values["respect_gitignore"],  # type: ignore[arg-type]
        line_ending=values["line_ending"],  # type: ignore[arg-type]
        encoding=values["encoding"],  # type: ignore[arg-type]
        max_bytes=values["max_bytes"],  # type: ignore[arg-type]
        on_oversize=values["on_oversize"],  # type: ignore[arg-type]
        continue_on_error=values["continue_on_error"],  # type: ignore[arg-type]
        redact=values["redact"],  # type: ignore[arg-type]
        drop_line_containing=values["drop_line_containing"],  # type: ignore[arg-type]
        min_line_length=values["min_line_length"],  # type: ignore[arg-type]
        strip_frontmatter=values["strip_frontmatter"],  # type: ignore[arg-type]
        include_sha256=values["include_sha256"],  # type: ignore[arg-type]
        include_toc=values["include_toc"],  # type: ignore[arg-type]
        pdf_ocr=values["pdf_ocr"],  # type: ignore[arg-type]
        pdf_ocr_strict=values["pdf_ocr_strict"],  # type: ignore[arg-type]
        stdin_paths=explicit_paths,
    )
    included, skipped = scan(preview_config)
    if skipped:
        skip_entries = sorted(
            (build_skipped_file_entry(path=skip.relpath, reason=skip.reason) for skip in skipped),
            key=lambda entry: entry["path"].casefold(),
        )
        for entry in skip_entries:
            console.print(
                f"{entry['path']}  [{entry['reason_code']}] {entry['message']}",
                markup=False,
            )
        console.print(
            "\n[red]Preview aborted:[/red] one or more selected files cannot be previewed."
        )
        raise typer.Exit(code=1)

    ordered_records = _sort_records_by_explicit_path_order(included, explicit_paths)
    typer.echo(render_preview(preview_config, ordered_records), nl=False)


@app.command("init")
def init_cmd(
    profile: str = typer.Option(
        ...,
        "--profile",
        help=(
            f"Starter profile name: {_INIT_PROFILE_CHOICES}. "
            "Use this to bootstrap a local foldermix.toml."
        ),
    ),
    out: Path = typer.Option(
        Path("foldermix.toml"),
        "--out",
        "-o",
        help="Path to write the generated config file [default: ./foldermix.toml]",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Overwrite an existing output file. By default existing files are preserved.",
    ),
) -> None:
    """Generate a starter foldermix.toml for common local workflows."""
    normalized = profile.strip().lower()
    if not has_profile(normalized):
        valid = ", ".join(available_profiles())
        console.print(
            "[red]Invalid profile:"
            f" {profile!r}. Valid choices are: {valid}.[/red]\n"
            "Run 'foldermix init --help' for usage information."
        )
        raise typer.Exit(code=1)

    output_path = out.expanduser()
    if output_path.exists() and not force:
        console.print(
            f"[red]Refusing to overwrite existing file: {output_path}.[/red]\n"
            "Use --force to overwrite."
        )
        raise typer.Exit(code=1)

    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(render_profile_config(normalized), encoding="utf-8")
    except OSError as exc:
        console.print(f"[red]Failed to write config: {exc}[/red]")
        raise typer.Exit(code=1) from exc

    console.print(
        f"Wrote starter config to {output_path} using profile '{normalized}'. "
        "Run: foldermix pack . --config "
        f"{shlex.quote(str(output_path))}"
    )


@app.command("version")
def version_cmd() -> None:
    """Print the version."""
    console.print(f"foldermix {__version__}")


if __name__ == "__main__":
    app()
