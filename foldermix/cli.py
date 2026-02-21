from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from . import __version__
from .config import DEFAULT_EXCLUDE_DIRS, DEFAULT_EXCLUDE_EXT, PackConfig

app = typer.Typer(
    name="foldermix",
    help="Pack a folder into a single LLM-friendly context file.",
    add_completion=False,
)
console = Console()


def _parse_csv(val: str | None) -> list[str] | None:
    if val is None:
        return None
    return [v.strip() for v in val.split(",") if v.strip()]


@app.command("pack")
def pack_cmd(
    path: Path = typer.Argument(Path("."), help="Directory to pack"),
    out: Path | None = typer.Option(None, "--out", "-o", help="Output file path"),
    format: str = typer.Option("md", "--format", "-f", help="Output format: md, xml, jsonl"),
    include_ext: str | None = typer.Option(
        None, "--include-ext", help="Comma-separated extensions to include"
    ),
    exclude_ext: str | None = typer.Option(
        None, "--exclude-ext", help="Comma-separated extensions to exclude"
    ),
    exclude_dirs: str | None = typer.Option(
        None, "--exclude-dirs", help="Comma-separated directory names to exclude"
    ),
    exclude_glob: list[str] | None = typer.Option(
        None, "--exclude-glob", help="Glob patterns to exclude"
    ),
    include_glob: list[str] | None = typer.Option(
        None, "--include-glob", help="Glob patterns to include"
    ),
    max_bytes: int = typer.Option(10_000_000, "--max-bytes", help="Max bytes per file"),
    max_total_bytes: int | None = typer.Option(None, "--max-total-bytes", help="Max total bytes"),
    max_files: int | None = typer.Option(None, "--max-files", help="Max number of files"),
    hidden: bool = typer.Option(False, "--hidden", help="Include hidden files"),
    follow_symlinks: bool = typer.Option(False, "--follow-symlinks"),
    respect_gitignore: bool = typer.Option(True, "--respect-gitignore/--no-respect-gitignore"),
    workers: int = typer.Option(4, "--workers", help="Number of worker threads"),
    progress: bool = typer.Option(False, "--progress", help="Show progress bar"),
    dry_run: bool = typer.Option(False, "--dry-run", help="List files without packing"),
    report: Path | None = typer.Option(None, "--report", help="Write JSON report to path"),
    continue_on_error: bool = typer.Option(False, "--continue-on-error"),
    on_oversize: str = typer.Option("skip", "--on-oversize", help="skip or truncate"),
    redact: str = typer.Option("none", "--redact", help="none, emails, phones, all"),
    strip_frontmatter: bool = typer.Option(False, "--strip-frontmatter"),
    include_sha256: bool = typer.Option(True, "--include-sha256/--no-include-sha256"),
    include_toc: bool = typer.Option(True, "--include-toc/--no-include-toc"),
) -> None:
    """Pack a directory into a single context file."""
    from .packer import pack

    inc_ext = _parse_csv(include_ext)
    exc_ext = _parse_csv(exclude_ext) or list(DEFAULT_EXCLUDE_EXT)
    exc_dirs = _parse_csv(exclude_dirs) or list(DEFAULT_EXCLUDE_DIRS)

    if format not in ("md", "xml", "jsonl"):
        console.print(f"[red]Invalid format: {format!r}. Choose md, xml, or jsonl.[/red]")
        raise typer.Exit(code=1)

    if on_oversize not in ("skip", "truncate"):
        console.print(
            f"[red]Invalid --on-oversize: {on_oversize!r}. Choose skip or truncate.[/red]"
        )
        raise typer.Exit(code=1)

    if redact not in ("none", "emails", "phones", "all"):
        console.print(f"[red]Invalid --redact: {redact!r}.[/red]")
        raise typer.Exit(code=1)

    config = PackConfig(
        root=path,
        out=out,
        format=format,  # type: ignore[arg-type]
        include_ext=inc_ext,
        exclude_ext=exc_ext,
        exclude_dirs=exc_dirs,
        exclude_glob=exclude_glob or [],
        include_glob=include_glob or [],
        max_bytes=max_bytes,
        max_total_bytes=max_total_bytes,
        max_files=max_files,
        hidden=hidden,
        follow_symlinks=follow_symlinks,
        respect_gitignore=respect_gitignore,
        workers=workers,
        progress=progress,
        dry_run=dry_run,
        report=report,
        continue_on_error=continue_on_error,
        on_oversize=on_oversize,  # type: ignore[arg-type]
        redact=redact,  # type: ignore[arg-type]
        strip_frontmatter=strip_frontmatter,
        include_sha256=include_sha256,
        include_toc=include_toc,
    )

    pack(config)


@app.command("list")
def list_cmd(
    path: Path = typer.Argument(Path("."), help="Directory to scan"),
    include_ext: str | None = typer.Option(None, "--include-ext"),
    exclude_ext: str | None = typer.Option(None, "--exclude-ext"),
    hidden: bool = typer.Option(False, "--hidden"),
    respect_gitignore: bool = typer.Option(True, "--respect-gitignore/--no-respect-gitignore"),
) -> None:
    """List candidate files that would be packed."""
    from .config import PackConfig
    from .scanner import scan

    config = PackConfig(
        root=path,
        include_ext=_parse_csv(include_ext),
        exclude_ext=_parse_csv(exclude_ext) or list(DEFAULT_EXCLUDE_EXT),
        hidden=hidden,
        respect_gitignore=respect_gitignore,
    )
    included, skipped = scan(config)
    for r in included:
        console.print(f"{r.relpath}  ({r.size:,} bytes)")
    console.print(f"\n{len(included)} files would be included, {len(skipped)} skipped.")


@app.command("stats")
def stats_cmd(
    path: Path = typer.Argument(Path("."), help="Directory to scan"),
    include_ext: str | None = typer.Option(None, "--include-ext"),
    hidden: bool = typer.Option(False, "--hidden"),
) -> None:
    """Show summary statistics for a directory."""
    from .config import PackConfig
    from .scanner import scan

    config = PackConfig(
        root=path,
        include_ext=_parse_csv(include_ext),
        hidden=hidden,
    )
    included, skipped = scan(config)
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
