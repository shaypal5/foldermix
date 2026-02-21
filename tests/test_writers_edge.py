from __future__ import annotations

from io import StringIO

import pytest

from foldermix.writers.base import FileBundleItem, HeaderInfo, Writer
from foldermix.writers.markdown_writer import MarkdownWriter
from foldermix.writers.xml_writer import XmlWriter


def _header() -> HeaderInfo:
    return HeaderInfo(
        root="/root",
        generated_at="2024-01-01T00:00:00+00:00",
        version="0.1.0",
        args={},
        file_count=1,
        total_bytes=12,
    )


def test_markdown_writer_writes_converter_warnings_and_newline() -> None:
    item = FileBundleItem(
        relpath="file.txt",
        ext=".txt",
        size_bytes=12,
        mtime="2024-01-01T00:00:00+00:00",
        sha256=None,
        content="abc```def",
        converter_name="custom-converter",
        original_mime="text/plain",
        warnings=["warn-1", "warn-2"],
    )
    buf = StringIO()
    MarkdownWriter().write(buf, _header(), [item])
    out = buf.getvalue()

    assert "- **Converter**: custom-converter" in out
    assert "- **⚠️ Warning**: warn-1" in out
    assert "- **⚠️ Warning**: warn-2" in out
    assert "abc` ` `def\n```" in out


def test_markdown_writer_can_disable_toc() -> None:
    item = FileBundleItem(
        relpath="file.txt",
        ext=".txt",
        size_bytes=12,
        mtime="2024-01-01T00:00:00+00:00",
        sha256=None,
        content="abc\n",
        converter_name="text",
        original_mime="text/plain",
    )
    buf = StringIO()
    MarkdownWriter(include_toc=False).write(buf, _header(), [item])
    out = buf.getvalue()
    assert "Table of Contents" not in out


def test_xml_writer_writes_truncated_flag() -> None:
    item = FileBundleItem(
        relpath="file.txt",
        ext=".txt",
        size_bytes=12,
        mtime="2024-01-01T00:00:00+00:00",
        sha256=None,
        content="abc\n",
        converter_name="text",
        original_mime="text/plain",
        truncated=True,
    )
    buf = StringIO()
    XmlWriter().write(buf, _header(), [item])
    out = buf.getvalue()
    assert "<truncated>true</truncated>" in out


def test_base_writer_write_raises_not_implemented() -> None:
    writer = Writer()
    with pytest.raises(NotImplementedError):
        writer.write(StringIO(), _header(), [])
