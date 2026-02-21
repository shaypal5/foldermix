from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from io import StringIO

from foldermix.writers.base import FileBundleItem, HeaderInfo
from foldermix.writers.jsonl_writer import JsonlWriter
from foldermix.writers.markdown_writer import MarkdownWriter
from foldermix.writers.xml_writer import XmlWriter


def make_header() -> HeaderInfo:
    return HeaderInfo(
        root="/test/root",
        generated_at="2024-01-01T00:00:00+00:00",
        version="0.1.0",
        args={},
        file_count=2,
        total_bytes=100,
    )


def make_items() -> list[FileBundleItem]:
    return [
        FileBundleItem(
            relpath="hello.py",
            ext=".py",
            size_bytes=50,
            mtime="2024-01-01T00:00:00+00:00",
            sha256="abc123",
            content="print('hello')\n",
            converter_name="text",
            original_mime="text/py",
        ),
        FileBundleItem(
            relpath="data/sample.json",
            ext=".json",
            size_bytes=50,
            mtime="2024-01-01T00:00:00+00:00",
            sha256="def456",
            content='{"key": "value"}\n',
            converter_name="text",
            original_mime="text/json",
        ),
    ]


class TestMarkdownWriter:
    def test_produces_markdown(self) -> None:
        writer = MarkdownWriter()
        buf = StringIO()
        writer.write(buf, make_header(), make_items())
        output = buf.getvalue()
        assert "# FolderPack Context" in output
        assert "hello.py" in output
        assert "data/sample.json" in output

    def test_contains_code_blocks(self) -> None:
        writer = MarkdownWriter()
        buf = StringIO()
        writer.write(buf, make_header(), make_items())
        output = buf.getvalue()
        assert "```python" in output
        assert "print('hello')" in output

    def test_contains_toc(self) -> None:
        writer = MarkdownWriter()
        buf = StringIO()
        writer.write(buf, make_header(), make_items())
        output = buf.getvalue()
        assert "Table of Contents" in output

    def test_empty_items(self) -> None:
        writer = MarkdownWriter()
        buf = StringIO()
        writer.write(buf, make_header(), [])
        output = buf.getvalue()
        assert "# FolderPack Context" in output

    def test_sha256_present(self) -> None:
        writer = MarkdownWriter()
        buf = StringIO()
        writer.write(buf, make_header(), make_items())
        output = buf.getvalue()
        assert "abc123" in output

    def test_truncated_flag(self) -> None:
        items = make_items()
        items[0].truncated = True
        writer = MarkdownWriter()
        buf = StringIO()
        writer.write(buf, make_header(), items)
        output = buf.getvalue()
        assert "TRUNCATED" in output


class TestXmlWriter:
    def test_valid_xml(self) -> None:
        writer = XmlWriter()
        buf = StringIO()
        writer.write(buf, make_header(), make_items())
        output = buf.getvalue()
        root = ET.fromstring(output)
        assert root.tag == "foldermix"

    def test_file_elements(self) -> None:
        writer = XmlWriter()
        buf = StringIO()
        writer.write(buf, make_header(), make_items())
        output = buf.getvalue()
        root = ET.fromstring(output)
        files = root.find("files")
        assert files is not None
        file_elements = files.findall("file")
        assert len(file_elements) == 2

    def test_cdata_safety(self) -> None:
        items = [
            FileBundleItem(
                relpath="test.txt",
                ext=".txt",
                size_bytes=20,
                mtime="2024-01-01T00:00:00+00:00",
                sha256=None,
                content="some ]]> tricky content",
                converter_name="text",
                original_mime="text/plain",
            )
        ]
        writer = XmlWriter()
        buf = StringIO()
        writer.write(buf, make_header(), items)
        output = buf.getvalue()
        # Should be parseable and content preserved correctly
        root = ET.fromstring(output)
        content_elem = root.find(".//content")
        assert content_elem is not None
        assert "]]>" in (content_elem.text or "")  # original text preserved by parser

    def test_content_preserved(self) -> None:
        writer = XmlWriter()
        buf = StringIO()
        writer.write(buf, make_header(), make_items())
        output = buf.getvalue()
        assert "print('hello')" in output

    def test_header_info(self) -> None:
        writer = XmlWriter()
        buf = StringIO()
        writer.write(buf, make_header(), make_items())
        output = buf.getvalue()
        root = ET.fromstring(output)
        header = root.find("header")
        assert header is not None
        assert header.find("version").text == "0.1.0"


class TestJsonlWriter:
    def test_valid_jsonl(self) -> None:
        writer = JsonlWriter()
        buf = StringIO()
        writer.write(buf, make_header(), make_items())
        output = buf.getvalue()
        lines = [line for line in output.strip().split("\n") if line]
        # Should have header + 2 items
        assert len(lines) == 3
        for line in lines:
            json.loads(line)  # should not raise

    def test_header_line(self) -> None:
        writer = JsonlWriter()
        buf = StringIO()
        writer.write(buf, make_header(), make_items())
        output = buf.getvalue()
        first_line = json.loads(output.split("\n")[0])
        assert first_line["type"] == "header"
        assert first_line["version"] == "0.1.0"

    def test_file_lines(self) -> None:
        writer = JsonlWriter()
        buf = StringIO()
        writer.write(buf, make_header(), make_items())
        output = buf.getvalue()
        lines = output.strip().split("\n")
        file_line = json.loads(lines[1])
        assert file_line["type"] == "file"
        assert file_line["path"] == "hello.py"
        assert "print('hello')" in file_line["content"]

    def test_empty_items(self) -> None:
        writer = JsonlWriter()
        buf = StringIO()
        writer.write(buf, make_header(), [])
        output = buf.getvalue()
        lines = [line for line in output.strip().split("\n") if line]
        assert len(lines) == 1
        header = json.loads(lines[0])
        assert header["type"] == "header"
