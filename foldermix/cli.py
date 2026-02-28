from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console

from . import __version__
from .config import DEFAULT_EXCLUDE_DIRS, DEFAULT_EXCLUDE_EXT, PackConfig
from .config_loader import ConfigLoadError, load_command_config
from .effective_config import EffectiveConfig, effective_config_payload, merge_config_layers

app = typer.Typer(
    name="foldermix",
    help=(
        "Pack a folder into a single LLM-friendly context file.\n\n"
        "Commands:\n\n"
        "  pack    – Scan a directory and write all files into one output file.\n\n"
        "  list    – Preview which files would be included without packing.\n\n"
        "  stats   – Show file-count and byte-size statistics for a directory.\n\n"
        "  version – Print the installed foldermix version.\n\n"
        "Run 'foldermix COMMAND --help' for detailed options on any command."
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
    "strip_frontmatter": "strip_frontmatter",
    "include_sha256": "include_sha256",
    "include_toc": "include_toc",
    "pdf_ocr": "pdf_ocr",
    "pdf_ocr_strict": "pdf_ocr_strict",
}

_LIST_PARAM_BY_KEY = {
    "root": "path",
    "include_ext": "include_ext",
    "exclude_ext": "exclude_ext",
    "hidden": "hidden",
    "respect_gitignore": "respect_gitignore",
}

_STATS_PARAM_BY_KEY = {
    "root": "path",
    "include_ext": "include_ext",
    "hidden": "hidden",
}


def _parse_csv(val: str | None) -> list[str] | None:
    if val is None:
        return None
    return [v.strip() for v in val.split(",") if v.strip()]


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
        _print_effective_config("pack", merged, used_config_path)
        return
    values = merged.values

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

    pack_config = PackConfig(**values)  # type: ignore[arg-type]

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
    hidden: bool = typer.Option(
        False, "--hidden", help="Include hidden files and directories (names starting with '.')"
    ),
    respect_gitignore: bool = typer.Option(
        True,
        "--respect-gitignore/--no-respect-gitignore",
        help="Skip files listed in .gitignore [default: respect]",
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
        "hidden": hidden,
        "respect_gitignore": respect_gitignore,
    }
    try:
        overrides, used_config_path = load_command_config(
            "list", root=path, config_path=config_path
        )
    except ConfigLoadError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
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

    pack_config = PackConfig(
        root=values["root"],  # type: ignore[arg-type]
        include_ext=values["include_ext"],  # type: ignore[arg-type]
        exclude_ext=values["exclude_ext"],  # type: ignore[arg-type]
        hidden=values["hidden"],  # type: ignore[arg-type]
        respect_gitignore=values["respect_gitignore"],  # type: ignore[arg-type]
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

    pack_config = PackConfig(
        root=values["root"],  # type: ignore[arg-type]
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


@app.command("version")
def version_cmd() -> None:
    """Print the version."""
    console.print(f"foldermix {__version__}")


if __name__ == "__main__":
    app()
