from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from foldermix.cli import app

runner = CliRunner()


def _jsonl_relpaths(path: Path) -> list[str]:
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    return [json.loads(line)["path"] for line in lines[1:]]


def test_pack_stdin_newline_ingests_explicit_paths_and_reports_missing(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "a.txt").write_text("A", encoding="utf-8")
    nested = tmp_path / "sub dir"
    nested.mkdir()
    (nested / "b.txt").write_text("B", encoding="utf-8")
    (tmp_path / "c.txt").write_text("C", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "pack",
            ".",
            "--stdin",
            "--format",
            "jsonl",
            "--out",
            "out.jsonl",
            "--report",
            "report.json",
            "--no-include-sha256",
        ],
        input="a.txt\nsub dir/b.txt\nmissing.txt\n",
    )

    assert result.exit_code == 0, result.output
    assert _jsonl_relpaths(tmp_path / "out.jsonl") == ["a.txt", "sub dir/b.txt"]

    report = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    assert {"path": "missing.txt", "reason": "missing"} in report["skipped_files"]


def test_pack_stdin_null_handles_spaces_unicode_and_dedup(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "space name.txt").write_text("space", encoding="utf-8")
    (tmp_path / "unicodé.txt").write_text("unicode", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "pack",
            ".",
            "--stdin",
            "--null",
            "--format",
            "jsonl",
            "--out",
            "out.jsonl",
            "--no-include-sha256",
        ],
        input="space name.txt\0unicodé.txt\0space name.txt\0",
    )

    assert result.exit_code == 0, result.output
    assert _jsonl_relpaths(tmp_path / "out.jsonl") == ["space name.txt", "unicodé.txt"]


def test_list_and_stats_stdin_use_only_explicit_paths(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "a.txt").write_text("A", encoding="utf-8")
    (tmp_path / "b.txt").write_text("BB", encoding="utf-8")
    (tmp_path / "c.txt").write_text("CCC", encoding="utf-8")

    list_result = runner.invoke(
        app,
        ["list", ".", "--stdin"],
        input="a.txt\nc.txt\nmissing.txt\n",
    )
    assert list_result.exit_code == 0, list_result.output
    assert "a.txt" in list_result.output
    assert "c.txt" in list_result.output
    assert "b.txt" not in list_result.output
    assert "2 files would be included, 1 skipped." in list_result.output

    stats_result = runner.invoke(
        app,
        ["stats", ".", "--stdin"],
        input="a.txt\nb.txt\nmissing.txt\n",
    )
    assert stats_result.exit_code == 0, stats_result.output
    assert "Included files: 2" in stats_result.output
    assert "Skipped files:  1" in stats_result.output
    assert "Total bytes:    3" in stats_result.output


@pytest.mark.parametrize("command", ["pack", "list", "stats"])
def test_null_requires_stdin(command: str, tmp_path: Path) -> None:
    args = [command, str(tmp_path), "--null"]
    result = runner.invoke(app, args)

    assert result.exit_code == 1
    assert "--null requires --stdin." in result.output
