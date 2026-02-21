from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

from foldermix.converters.docx_fallback import DocxFallbackConverter
from foldermix.converters.markitdown_conv import MarkitdownConverter
from foldermix.converters.pdf_fallback import PdfFallbackConverter
from foldermix.converters.pptx_fallback import PptxFallbackConverter
from foldermix.converters.xlsx_fallback import XlsxFallbackConverter


def test_docx_fallback_can_convert_when_installed(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "docx", SimpleNamespace(Document=lambda _: None))
    assert DocxFallbackConverter().can_convert(".docx") is True
    assert DocxFallbackConverter().can_convert(".txt") is False


def test_docx_fallback_can_convert_false_when_missing(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "docx", None)
    assert DocxFallbackConverter().can_convert(".docx") is False


def test_docx_fallback_convert(monkeypatch, tmp_path: Path) -> None:
    path = tmp_path / "f.docx"
    path.write_text("placeholder", encoding="utf-8")
    paragraphs = [SimpleNamespace(text="Title"), SimpleNamespace(text="Paragraph")]
    fake_docx = SimpleNamespace(Document=lambda _: SimpleNamespace(paragraphs=paragraphs))
    monkeypatch.setitem(sys.modules, "docx", fake_docx)

    result = DocxFallbackConverter().convert(path)
    assert result.content == "Title\n\nParagraph"
    assert result.converter_name == "python-docx"


def test_pptx_fallback_can_convert_when_installed(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "pptx", SimpleNamespace(Presentation=lambda _: None))
    assert PptxFallbackConverter().can_convert(".pptx") is True
    assert PptxFallbackConverter().can_convert(".txt") is False


def test_pptx_fallback_can_convert_false_when_missing(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "pptx", None)
    assert PptxFallbackConverter().can_convert(".pptx") is False


def test_pptx_fallback_convert(monkeypatch, tmp_path: Path) -> None:
    path = tmp_path / "f.pptx"
    path.write_text("placeholder", encoding="utf-8")
    slide1 = SimpleNamespace(shapes=[SimpleNamespace(text="Slide One"), object()])
    slide2 = SimpleNamespace(shapes=[SimpleNamespace(text="Slide Two")])
    fake_pptx = SimpleNamespace(Presentation=lambda _: SimpleNamespace(slides=[slide1, slide2]))
    monkeypatch.setitem(sys.modules, "pptx", fake_pptx)

    result = PptxFallbackConverter().convert(path)
    assert "### Slide 1" in result.content
    assert "Slide One" in result.content
    assert "### Slide 2" in result.content
    assert "Slide Two" in result.content
    assert result.converter_name == "python-pptx"


def test_xlsx_fallback_can_convert_when_installed(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "openpyxl", SimpleNamespace(load_workbook=lambda *_: None))
    assert XlsxFallbackConverter().can_convert(".xlsx") is True
    assert XlsxFallbackConverter().can_convert(".txt") is False


def test_xlsx_fallback_can_convert_false_when_missing(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "openpyxl", None)
    assert XlsxFallbackConverter().can_convert(".xlsx") is False


def test_xlsx_fallback_convert(monkeypatch, tmp_path: Path) -> None:
    path = tmp_path / "f.xlsx"
    path.write_text("placeholder", encoding="utf-8")

    class _Worksheet:
        @staticmethod
        def iter_rows(values_only: bool = True):
            assert values_only is True
            return [("a", 1), ("b", None)]

    class _Workbook:
        sheetnames = ["Sheet1"]

        @staticmethod
        def __getitem__(name: str):
            assert name == "Sheet1"
            return _Worksheet()

    fake_openpyxl = SimpleNamespace(load_workbook=lambda *_args, **_kwargs: _Workbook())
    monkeypatch.setitem(sys.modules, "openpyxl", fake_openpyxl)

    result = XlsxFallbackConverter().convert(path)
    assert "## Sheet: Sheet1" in result.content
    assert "a\t1" in result.content
    assert "b\t" in result.content
    assert result.converter_name == "openpyxl"


def test_markitdown_convert(monkeypatch, tmp_path: Path) -> None:
    path = tmp_path / "f.pdf"
    path.write_text("placeholder", encoding="utf-8")

    class _MarkItDown:
        @staticmethod
        def convert(_path: str):
            return SimpleNamespace(text_content="converted markdown")

    monkeypatch.setitem(sys.modules, "markitdown", SimpleNamespace(MarkItDown=_MarkItDown))
    result = MarkitdownConverter().convert(path)
    assert result.content == "converted markdown"
    assert result.converter_name == "markitdown"


def test_pdf_fallback_convert(monkeypatch, tmp_path: Path) -> None:
    path = tmp_path / "f.pdf"
    path.write_text("placeholder", encoding="utf-8")

    class _Page:
        def __init__(self, text: str) -> None:
            self._text = text

        def extract_text(self) -> str:
            return self._text

    class _Reader:
        def __init__(self, _path: str) -> None:
            self.pages = [_Page("first"), _Page("second")]

    monkeypatch.setitem(sys.modules, "pypdf", SimpleNamespace(PdfReader=_Reader))
    result = PdfFallbackConverter().convert(path)
    assert "### Page 1\nfirst" in result.content
    assert "### Page 2\nsecond" in result.content
    assert result.converter_name == "pypdf"
