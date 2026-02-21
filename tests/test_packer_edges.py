from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

from foldermix import packer
from foldermix.config import PackConfig
from foldermix.converters.base import ConversionResult
from foldermix.scanner import FileRecord


class _RegistryNone:
    @staticmethod
    def get_converter(_ext: str):
        return None


class _RegistryOne:
    def __init__(self, converter) -> None:
        self.converter = converter

    def get_converter(self, _ext: str):
        return self.converter


def test_convert_record_without_converter(tmp_path: Path) -> None:
    path = tmp_path / "a.unknown"
    path.write_text("raw", encoding="utf-8")
    record = FileRecord(path=path, relpath="a.unknown", ext=".unknown", size=3, mtime=0.0)
    item = packer._convert_record(
        record, _RegistryNone(), PackConfig(root=tmp_path, include_sha256=False)
    )
    assert item.converter_name == "none"
    assert item.content == "[No converter available for .unknown]"


def test_convert_record_truncate_and_cleanup(tmp_path: Path) -> None:
    path = tmp_path / "big.txt"
    path.write_text("0123456789abcdef", encoding="utf-8")

    class _Conv:
        @staticmethod
        def convert(p: Path, encoding: str = "utf-8") -> ConversionResult:
            return ConversionResult(content=p.read_text(encoding=encoding), converter_name="fake")

    config = PackConfig(
        root=tmp_path,
        on_oversize="truncate",
        max_bytes=8,
        include_sha256=False,
    )
    record = FileRecord(path=path, relpath="big.txt", ext=".txt", size=16, mtime=0.0)
    item = packer._convert_record(record, _RegistryOne(_Conv()), config)

    assert item.truncated is True
    assert "[TRUNCATED]" in item.content
    assert not (tmp_path / "big.txt.truncated.tmp").exists()


def test_convert_record_applies_frontmatter_redaction_and_crlf(tmp_path: Path) -> None:
    path = tmp_path / "doc.md"
    path.write_text("x", encoding="utf-8")

    class _Conv:
        @staticmethod
        def convert(_p: Path, encoding: str = "utf-8") -> ConversionResult:
            content = "---\ntitle: test\n---\nmail test@example.com\ncall +1 (555) 123-4567\n"
            return ConversionResult(content=content, converter_name="fake")

    config = PackConfig(
        root=tmp_path,
        include_sha256=False,
        strip_frontmatter=True,
        redact="all",
        line_ending="crlf",
    )
    record = FileRecord(path=path, relpath="doc.md", ext=".md", size=1, mtime=0.0)
    item = packer._convert_record(record, _RegistryOne(_Conv()), config)

    assert "title:" not in item.content
    assert "[REDACTED_EMAIL]" in item.content
    assert "[REDACTED_PHONE]" in item.content
    assert "\r\n" in item.content


def test_convert_record_ignores_sha256_oserror(monkeypatch, tmp_path: Path) -> None:
    path = tmp_path / "a.txt"
    path.write_text("abc", encoding="utf-8")

    class _Conv:
        @staticmethod
        def convert(_p: Path, encoding: str = "utf-8") -> ConversionResult:
            return ConversionResult(content="ok", converter_name="fake")

    monkeypatch.setattr(packer, "sha256_file", lambda _p: (_ for _ in ()).throw(OSError("boom")))
    record = FileRecord(path=path, relpath="a.txt", ext=".txt", size=3, mtime=0.0)
    item = packer._convert_record(record, _RegistryOne(_Conv()), PackConfig(root=tmp_path))
    assert item.sha256 is None


def test_pack_uses_progress_branch_with_tqdm(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "a.txt").write_text("ok", encoding="utf-8")
    out_path = tmp_path / "out.md"

    fake_tqdm = SimpleNamespace(tqdm=lambda iterable, **kwargs: iterable)
    monkeypatch.setitem(sys.modules, "tqdm", fake_tqdm)

    config = PackConfig(
        root=tmp_path,
        out=out_path,
        progress=True,
        include_sha256=False,
        workers=1,
    )
    packer.pack(config)
    assert out_path.exists()


def test_pack_progress_falls_back_when_tqdm_missing(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "a.txt").write_text("ok", encoding="utf-8")
    out_path = tmp_path / "out.md"

    # When tqdm import fails, pack should still succeed via non-progress path.
    monkeypatch.setitem(sys.modules, "tqdm", None)
    config = PackConfig(
        root=tmp_path,
        out=out_path,
        progress=True,
        include_sha256=False,
        workers=1,
    )
    packer.pack(config)
    assert out_path.exists()


def test_pack_generates_default_output_name_when_out_not_set(tmp_path: Path, monkeypatch) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "a.txt").write_text("ok", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    config = PackConfig(root=project, out=None, format="md", include_sha256=False, workers=1)
    packer.pack(config)

    generated = list(tmp_path.glob("foldermix_*.md"))
    assert len(generated) == 1
    assert "# FolderPack Context" in generated[0].read_text(encoding="utf-8")
