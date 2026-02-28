from __future__ import annotations

import json
import re
from pathlib import Path

from typer.testing import CliRunner

import foldermix.packer as packer_module
import foldermix.scanner as scanner_module
from foldermix import __version__
from foldermix.cli import app

runner = CliRunner()
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def _strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)


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
            "--pdf-ocr",
            "--pdf-ocr-strict",
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
    assert config.pdf_ocr is True
    assert config.pdf_ocr_strict is True


def test_pack_loads_values_from_config_file(monkeypatch, tmp_path: Path) -> None:
    captured = {}

    def fake_pack(config) -> None:
        captured["config"] = config

    monkeypatch.setattr(packer_module, "pack", fake_pack)

    config_path = tmp_path / "foldermix.toml"
    config_path.write_text(
        "\n".join(
            [
                "[pack]",
                'format = "xml"',
                'include_ext = [".py", ".md"]',
                "include_sha256 = false",
                "pdf_ocr = true",
                "",
            ]
        ),
        encoding="utf-8",
    )

    result = runner.invoke(app, ["pack", str(tmp_path), "--config", str(config_path)])

    assert result.exit_code == 0, result.output
    config = captured["config"]
    assert config.format == "xml"
    assert config.include_ext == [".py", ".md"]
    assert config.include_sha256 is False
    assert config.pdf_ocr is True


def test_pack_cli_flags_override_config_values(monkeypatch, tmp_path: Path) -> None:
    captured = {}

    def fake_pack(config) -> None:
        captured["config"] = config

    monkeypatch.setattr(packer_module, "pack", fake_pack)

    config_path = tmp_path / "foldermix.toml"
    config_path.write_text(
        "\n".join(
            [
                "[pack]",
                'format = "xml"',
                "include_toc = false",
                "",
            ]
        ),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "pack",
            str(tmp_path),
            "--config",
            str(config_path),
            "--format",
            "jsonl",
            "--include-toc",
        ],
    )

    assert result.exit_code == 0, result.output
    config = captured["config"]
    assert config.format == "jsonl"
    assert config.include_toc is True


def test_pack_reports_invalid_config(tmp_path: Path) -> None:
    config_path = tmp_path / "foldermix.toml"
    config_path.write_text(
        "\n".join(
            [
                "[pack]",
                'workers = "many"',
                "",
            ]
        ),
        encoding="utf-8",
    )

    result = runner.invoke(app, ["pack", str(tmp_path), "--config", str(config_path)])

    assert result.exit_code == 1
    assert "Invalid config at" in result.output
    assert "workers: expected an integer" in result.output


def test_pack_applies_config_only_fields_encoding_and_line_ending(
    monkeypatch, tmp_path: Path
) -> None:
    captured = {}

    def fake_pack(config) -> None:
        captured["config"] = config

    monkeypatch.setattr(packer_module, "pack", fake_pack)

    config_path = tmp_path / "foldermix.toml"
    config_path.write_text(
        "\n".join(
            [
                "[pack]",
                'encoding = "latin-1"',
                'line_ending = "crlf"',
                "",
            ]
        ),
        encoding="utf-8",
    )

    result = runner.invoke(app, ["pack", str(tmp_path), "--config", str(config_path)])

    assert result.exit_code == 0, result.output
    config = captured["config"]
    assert config.encoding == "latin-1"
    assert config.line_ending == "crlf"


def test_pack_print_effective_config_outputs_sources_and_exits(monkeypatch, tmp_path: Path) -> None:
    def fail_pack(_config) -> None:
        raise AssertionError("pack() should not be called in --print-effective-config mode")

    monkeypatch.setattr(packer_module, "pack", fail_pack)

    config_path = tmp_path / "foldermix.toml"
    config_path.write_text(
        "\n".join(
            [
                "[pack]",
                'format = "xml"',
                "include_toc = false",
                "hidden = true",
                'line_ending = "crlf"',
                "",
            ]
        ),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "pack",
            str(tmp_path),
            "--config",
            str(config_path),
            "--format",
            "jsonl",
            "--include-toc",
            "--print-effective-config",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    effective = payload["effective_config"]

    assert payload["command"] == "pack"
    assert payload["config_path"] == str(config_path)
    assert effective["format"]["value"] == "jsonl"
    assert effective["format"]["source"] == "cli"
    assert effective["include_toc"]["value"] is True
    assert effective["include_toc"]["source"] == "cli"
    assert effective["hidden"]["value"] is True
    assert effective["hidden"]["source"] == "config"
    assert effective["line_ending"]["value"] == "crlf"
    assert effective["line_ending"]["source"] == "config"
    assert effective["encoding"]["value"] == "utf-8"
    assert effective["encoding"]["source"] == "default"
    assert effective["pdf_ocr"]["value"] is False
    assert effective["pdf_ocr"]["source"] == "default"
    assert effective["pdf_ocr_strict"]["value"] is False
    assert effective["pdf_ocr_strict"]["source"] == "default"


def test_pack_print_effective_config_includes_pack_defaults(monkeypatch, tmp_path: Path) -> None:
    def fail_pack(_config) -> None:
        raise AssertionError("pack() should not be called in --print-effective-config mode")

    monkeypatch.setattr(packer_module, "pack", fail_pack)

    result = runner.invoke(
        app,
        [
            "pack",
            str(tmp_path),
            "--print-effective-config",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    effective = payload["effective_config"]

    assert effective["line_ending"]["value"] == "lf"
    assert effective["line_ending"]["source"] == "default"
    assert effective["encoding"]["value"] == "utf-8"
    assert effective["encoding"]["source"] == "default"


def test_list_print_effective_config_outputs_sources_and_exits(monkeypatch, tmp_path: Path) -> None:
    def fail_scan(_config):
        raise AssertionError("scan() should not be called in --print-effective-config mode")

    monkeypatch.setattr(scanner_module, "scan", fail_scan)

    config_path = tmp_path / "foldermix.toml"
    config_path.write_text(
        "\n".join(
            [
                "[list]",
                "hidden = true",
                'include_ext = [".py"]',
                "",
            ]
        ),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "list",
            str(tmp_path),
            "--config",
            str(config_path),
            "--include-ext",
            ".md,.txt",
            "--print-effective-config",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    effective = payload["effective_config"]

    assert payload["command"] == "list"
    assert effective["include_ext"]["value"] == [".md", ".txt"]
    assert effective["include_ext"]["source"] == "cli"
    assert effective["hidden"]["value"] is True
    assert effective["hidden"]["source"] == "config"


def test_stats_print_effective_config_outputs_sources_and_exits(
    monkeypatch, tmp_path: Path
) -> None:
    def fail_scan(_config):
        raise AssertionError("scan() should not be called in --print-effective-config mode")

    monkeypatch.setattr(scanner_module, "scan", fail_scan)

    config_path = tmp_path / "foldermix.toml"
    config_path.write_text(
        "\n".join(
            [
                "[stats]",
                'include_ext = [".py"]',
                "",
            ]
        ),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "stats",
            str(tmp_path),
            "--config",
            str(config_path),
            "--hidden",
            "--print-effective-config",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    effective = payload["effective_config"]

    assert payload["command"] == "stats"
    assert effective["hidden"]["value"] is True
    assert effective["hidden"]["source"] == "cli"
    assert effective["include_ext"]["value"] == [".py"]
    assert effective["include_ext"]["source"] == "config"


def test_list_shows_included_and_skipped_files(tmp_path: Path) -> None:
    (tmp_path / "keep.txt").write_text("ok")
    (tmp_path / ".hidden").write_text("secret")

    result = runner.invoke(app, ["list", str(tmp_path)])

    assert result.exit_code == 0, result.output
    assert "keep.txt" in result.output
    assert ".hidden" not in result.output
    assert "1 files would be included, 1 skipped." in result.output


def test_list_discovers_default_config(tmp_path: Path) -> None:
    config_path = tmp_path / "foldermix.toml"
    config_path.write_text(
        "\n".join(
            [
                "[list]",
                "hidden = true",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (tmp_path / "keep.txt").write_text("ok")
    (tmp_path / ".hidden").write_text("secret")

    result = runner.invoke(app, ["list", str(tmp_path)])

    assert result.exit_code == 0, result.output
    assert "keep.txt" in result.output
    assert ".hidden" in result.output
    assert config_path.exists()


def test_list_reports_invalid_config(tmp_path: Path) -> None:
    config_path = tmp_path / "foldermix.toml"
    config_path.write_text(
        "\n".join(
            [
                "[list]",
                'hidden = "yes"',
                "",
            ]
        ),
        encoding="utf-8",
    )

    result = runner.invoke(app, ["list", str(tmp_path), "--config", str(config_path)])

    assert result.exit_code == 1
    assert "Invalid config at" in result.output
    assert "hidden: expected a boolean" in result.output


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


def test_stats_reports_invalid_config(tmp_path: Path) -> None:
    config_path = tmp_path / "foldermix.toml"
    config_path.write_text(
        "\n".join(
            [
                "[stats]",
                "include_ext = 123",
                "",
            ]
        ),
        encoding="utf-8",
    )

    result = runner.invoke(app, ["stats", str(tmp_path), "--config", str(config_path)])

    assert result.exit_code == 1
    assert "Invalid config at" in result.output
    assert "include_ext: expected a list of strings" in result.output


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
    assert "--stdin" in result.output
    assert "--null" in result.output


def test_list_help_all_options_documented() -> None:
    result = runner.invoke(app, ["list", "--help"])
    assert result.exit_code == 0
    output = _strip_ansi(result.output)
    # Options that previously had no help text now show descriptions
    assert "--include-ext" in output
    assert "--exclude-ext" in output
    assert "hidden" in output
    assert "gitignore" in output
    assert "--stdin" in output
    assert "--null" in output
    assert "Examples:" in output


def test_stats_help_all_options_documented() -> None:
    result = runner.invoke(app, ["stats", "--help"])
    assert result.exit_code == 0
    output = _strip_ansi(result.output)
    # Options that previously had no help text now show descriptions
    assert "--include-ext" in output
    assert "hidden" in output
    assert "--stdin" in output
    assert "--null" in output
    assert "Examples:" in output


def test_root_help_lists_all_commands() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "init" in result.output
    assert "pack" in result.output
    assert "list" in result.output
    assert "stats" in result.output
    assert "version" in result.output
    assert "foldermix COMMAND" in result.output
