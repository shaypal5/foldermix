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


def test_pack_writes_report_json(tmp_path: Path) -> None:
    _write(tmp_path / "data.txt", "ok\n")
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
    assert report["included_count"] == 1
    assert report["skipped_count"] == 1
    assert report["included_files"] == [{"path": "data.txt", "size": 3, "ext": ".txt"}]
    assert report["skipped_files"] == [{"path": "image.png", "reason": "excluded_ext"}]


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

    monkeypatch.setattr(packer, "_build_registry", lambda: _SingleConverterRegistry(_SlowConverter()))
    monkeypatch.setattr(packer, "_get_writer", lambda fmt: _CaptureWriter())

    config = PackConfig(
        root=tmp_path,
        out=tmp_path / "out.md",
        format="md",
        workers=2,
        include_sha256=False,
    )
    packer.pack(config)

    assert captured_order == ["a.txt", "b.txt"]


@pytest.mark.xfail(
    reason="include_toc is accepted in config but not applied by markdown output flow yet",
    strict=True,
)
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
