from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

import foldermix.packer as packer_module
from foldermix import __version__
from foldermix.cli import app

runner = CliRunner()


def test_pack_rejects_invalid_format(tmp_path: Path) -> None:
    result = runner.invoke(app, ["pack", str(tmp_path), "--format", "bad"])
    assert result.exit_code == 1
    assert "Invalid format" in result.output
    assert "md, xml, jsonl" in result.output
    assert "--help" in result.output


def test_pack_rejects_invalid_on_oversize(tmp_path: Path) -> None:
    result = runner.invoke(app, ["pack", str(tmp_path), "--on-oversize", "bad"])
    assert result.exit_code == 1
    assert "Invalid --on-oversize" in result.output
    assert "skip, truncate" in result.output
    assert "--help" in result.output


def test_pack_rejects_invalid_redact(tmp_path: Path) -> None:
    result = runner.invoke(app, ["pack", str(tmp_path), "--redact", "bad"])
    assert result.exit_code == 1
    assert "Invalid --redact" in result.output
    assert "none, emails, phones, all" in result.output
    assert "--help" in result.output


def test_pack_builds_config_and_calls_packer(monkeypatch, tmp_path: Path) -> None:
    captured = {}

    def fake_pack(config) -> None:
        captured["config"] = config

    monkeypatch.setattr(packer_module, "pack", fake_pack)

    result = runner.invoke(
        app,
        [
            "pack",
            str(tmp_path),
            "--format",
            "jsonl",
            "--include-ext",
            ".py,md",
            "--exclude-ext",
            ".txt",
            "--exclude-dirs",
            "node_modules,dist",
            "--on-oversize",
            "truncate",
            "--redact",
            "all",
            "--no-include-sha256",
            "--no-include-toc",
        ],
    )

    assert result.exit_code == 0, result.output
    config = captured["config"]
    assert config.root == tmp_path
    assert config.format == "jsonl"
    assert config.include_ext == [".py", "md"]
    assert config.exclude_ext == [".txt"]
    assert config.exclude_dirs == ["node_modules", "dist"]
    assert config.on_oversize == "truncate"
    assert config.redact == "all"
    assert config.include_sha256 is False
    assert config.include_toc is False


def test_list_shows_included_and_skipped_files(tmp_path: Path) -> None:
    (tmp_path / "keep.txt").write_text("ok")
    (tmp_path / ".hidden").write_text("secret")

    result = runner.invoke(app, ["list", str(tmp_path)])

    assert result.exit_code == 0, result.output
    assert "keep.txt" in result.output
    assert ".hidden" not in result.output
    assert "1 files would be included, 1 skipped." in result.output


def test_stats_prints_summary_and_extensions(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("print('a')\n")
    (tmp_path / "b.py").write_text("print('b')\n")
    (tmp_path / "c.md").write_text("# c\n")

    result = runner.invoke(app, ["stats", str(tmp_path)])

    assert result.exit_code == 0, result.output
    assert "Included files: 3" in result.output
    assert "Skipped files:  0" in result.output
    assert ".py" in result.output
    assert ".md" in result.output


def test_version_prints_package_version() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert f"foldermix {__version__}" in result.output


# ---------------------------------------------------------------------------
# Help-text quality tests
# ---------------------------------------------------------------------------


def test_pack_help_contains_examples() -> None:
    result = runner.invoke(app, ["pack", "--help"])
    assert result.exit_code == 0
    assert "foldermix pack" in result.output
    assert "Examples:" in result.output
    # \b blocks preserve the comment text verbatim
    assert "Pack current directory to Markdown" in result.output
    assert "Dry-run" in result.output


def test_pack_help_all_options_documented(tmp_path: Path) -> None:
    result = runner.invoke(app, ["pack", "--help"])
    assert result.exit_code == 0
    # Options that previously had no help text should now show descriptions.
    # Use short substrings that fit in any column width.
    assert "symbolic" in result.output  # --follow-symlinks
    assert "gitignore" in result.output  # --respect-gitignore
    assert "convert" in result.output  # --continue-on-error
    assert "frontmatter" in result.output  # --strip-frontmatter
    assert "SHA-256" in result.output  # --include-sha256
    assert "table of" in result.output  # --include-toc


def test_list_help_all_options_documented() -> None:
    result = runner.invoke(app, ["list", "--help"])
    assert result.exit_code == 0
    # Options that previously had no help text now show descriptions
    assert "extensions to include" in result.output
    assert "extensions to exclude" in result.output
    assert "hidden" in result.output
    assert "gitignore" in result.output
    assert "Examples:" in result.output


def test_stats_help_all_options_documented() -> None:
    result = runner.invoke(app, ["stats", "--help"])
    assert result.exit_code == 0
    # Options that previously had no help text now show descriptions
    assert "extensions to include" in result.output
    assert "hidden" in result.output
    assert "Examples:" in result.output


def test_root_help_lists_all_commands() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "pack" in result.output
    assert "list" in result.output
    assert "stats" in result.output
    assert "version" in result.output
    assert "foldermix COMMAND" in result.output
