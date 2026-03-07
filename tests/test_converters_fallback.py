from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from foldermix.converters._normalize import normalize_whitespace_line
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


def test_docx_fallback_compacts_blank_runs(monkeypatch, tmp_path: Path) -> None:
    path = tmp_path / "f.docx"
    path.write_text("placeholder", encoding="utf-8")
    paragraphs = [
        SimpleNamespace(text="Title"),
        SimpleNamespace(text=""),
        SimpleNamespace(text=" \t"),
        SimpleNamespace(text="Body"),
    ]
    fake_docx = SimpleNamespace(Document=lambda _: SimpleNamespace(paragraphs=paragraphs))
    monkeypatch.setitem(sys.modules, "docx", fake_docx)

    result = DocxFallbackConverter().convert(path)
    assert result.content == "Title\n\nBody"


def test_normalize_whitespace_line_replaces_nbsp_and_trims_right_edge() -> None:
    assert normalize_whitespace_line("alpha\xa0beta \t") == "alpha beta"


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
    assert result.content == "## Sheet: Sheet1\n\na\t1\nb"
    assert "b\t" not in result.content
    assert result.converter_name == "openpyxl"


def test_xlsx_fallback_trims_blank_tail_and_compacts_internal_gaps(
    monkeypatch, tmp_path: Path
) -> None:
    path = tmp_path / "f.xlsx"
    path.write_text("placeholder", encoding="utf-8")

    class _Worksheet:
        @staticmethod
        def iter_rows(values_only: bool = True):
            assert values_only is True
            return [
                ("header", "value", None),
                ("row1", 1, None),
                (None, None, None),
                (None, None, None),
                ("row2", 2, None),
                (None, None, None),
            ]

    class _Workbook:
        sheetnames = ["Sheet1"]

        @staticmethod
        def __getitem__(name: str):
            assert name == "Sheet1"
            return _Worksheet()

    fake_openpyxl = SimpleNamespace(load_workbook=lambda *_args, **_kwargs: _Workbook())
    monkeypatch.setitem(sys.modules, "openpyxl", fake_openpyxl)

    result = XlsxFallbackConverter().convert(path)
    assert result.content == "## Sheet: Sheet1\n\nheader\tvalue\nrow1\t1\n\nrow2\t2"


def test_xlsx_fallback_skips_leading_blank_rows(monkeypatch, tmp_path: Path) -> None:
    path = tmp_path / "f.xlsx"
    path.write_text("placeholder", encoding="utf-8")

    class _Worksheet:
        @staticmethod
        def iter_rows(values_only: bool = True):
            assert values_only is True
            return [
                (None, None),
                ("  \t", None),
                ("header", None),
                ("row1", None),
            ]

    class _Workbook:
        sheetnames = ["Sheet1"]

        @staticmethod
        def __getitem__(name: str):
            assert name == "Sheet1"
            return _Worksheet()

    fake_openpyxl = SimpleNamespace(load_workbook=lambda *_args, **_kwargs: _Workbook())
    monkeypatch.setitem(sys.modules, "openpyxl", fake_openpyxl)

    result = XlsxFallbackConverter().convert(path)
    assert result.content == "## Sheet: Sheet1\n\nheader\nrow1"


def test_xlsx_fallback_omits_empty_sheet_body(monkeypatch, tmp_path: Path) -> None:
    path = tmp_path / "f.xlsx"
    path.write_text("placeholder", encoding="utf-8")

    class _EmptyWorksheet:
        @staticmethod
        def iter_rows(values_only: bool = True):
            assert values_only is True
            return [
                (None, None),
                (" \t", None),
            ]

    class _Workbook:
        sheetnames = ["Sheet1", "Sheet2"]

        @staticmethod
        def __getitem__(name: str):
            if name == "Sheet1":
                return _EmptyWorksheet()
            if name == "Sheet2":
                return _EmptyWorksheet()
            raise AssertionError(name)

    fake_openpyxl = SimpleNamespace(load_workbook=lambda *_args, **_kwargs: _Workbook())
    monkeypatch.setitem(sys.modules, "openpyxl", fake_openpyxl)

    result = XlsxFallbackConverter().convert(path)
    assert result.content == "## Sheet: Sheet1\n\n## Sheet: Sheet2"


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
    assert result.warnings == []


def test_pdf_fallback_enable_ocr_does_not_initialize_engine_when_all_pages_have_text(
    monkeypatch, tmp_path: Path
) -> None:
    path = tmp_path / "f.pdf"
    path.write_text("placeholder", encoding="utf-8")
    init_calls = {"count": 0}

    class _Page:
        @staticmethod
        def extract_text() -> str:
            return "already text"

    class _Reader:
        def __init__(self, _path: str) -> None:
            self.pages = [_Page()]

    def _rapidocr_factory():
        init_calls["count"] += 1
        return object()

    class _PdfiumDoc:
        def __init__(self, _path: str) -> None:
            raise AssertionError("pdfium should not be touched when OCR is unnecessary")

    monkeypatch.setitem(sys.modules, "pypdf", SimpleNamespace(PdfReader=_Reader))
    monkeypatch.setitem(sys.modules, "pypdfium2", SimpleNamespace(PdfDocument=_PdfiumDoc))
    monkeypatch.setitem(
        sys.modules,
        "rapidocr_onnxruntime",
        SimpleNamespace(RapidOCR=_rapidocr_factory),
    )

    result = PdfFallbackConverter().convert(path, enable_ocr=True)
    assert "### Page 1\nalready text" in result.content
    assert result.converter_name == "pypdf"
    assert result.warnings == []
    assert init_calls["count"] == 0


def test_pdf_fallback_warns_when_page_needs_ocr_but_ocr_disabled(
    monkeypatch, tmp_path: Path
) -> None:
    path = tmp_path / "f.pdf"
    path.write_text("placeholder", encoding="utf-8")

    class _Page:
        @staticmethod
        def extract_text() -> str:
            return ""

    class _Reader:
        def __init__(self, _path: str) -> None:
            self.pages = [_Page()]

    monkeypatch.setitem(sys.modules, "pypdf", SimpleNamespace(PdfReader=_Reader))
    result = PdfFallbackConverter().convert(path)
    assert "### Page 1\n" in result.content
    assert len(result.warnings) == 1
    assert "OCR is disabled" in result.warnings[0]


def test_pdf_fallback_warns_when_ocr_enabled_but_deps_missing(monkeypatch, tmp_path: Path) -> None:
    path = tmp_path / "f.pdf"
    path.write_text("placeholder", encoding="utf-8")

    class _Page:
        @staticmethod
        def extract_text() -> str:
            return ""

    class _Reader:
        def __init__(self, _path: str) -> None:
            self.pages = [_Page()]

    monkeypatch.setitem(sys.modules, "pypdf", SimpleNamespace(PdfReader=_Reader))
    monkeypatch.setitem(sys.modules, "pypdfium2", None)
    monkeypatch.setitem(sys.modules, "rapidocr_onnxruntime", None)

    result = PdfFallbackConverter().convert(path, enable_ocr=True)
    assert len(result.warnings) == 1
    assert "OCR dependencies missing" in result.warnings[0]


def test_pdf_fallback_warns_for_each_textless_page_when_ocr_is_unavailable(
    monkeypatch, tmp_path: Path
) -> None:
    path = tmp_path / "f.pdf"
    path.write_text("placeholder", encoding="utf-8")

    class _Page:
        @staticmethod
        def extract_text() -> str:
            return ""

    class _Reader:
        def __init__(self, _path: str) -> None:
            self.pages = [_Page(), _Page()]

    monkeypatch.setitem(sys.modules, "pypdf", SimpleNamespace(PdfReader=_Reader))
    monkeypatch.setitem(sys.modules, "pypdfium2", None)
    monkeypatch.setitem(sys.modules, "rapidocr_onnxruntime", None)

    result = PdfFallbackConverter().convert(path, enable_ocr=True)
    assert len(result.warnings) == 2
    assert all("OCR dependencies missing" in warning for warning in result.warnings)


def test_pdf_fallback_strict_raises_when_ocr_required_and_deps_missing(
    monkeypatch, tmp_path: Path
) -> None:
    path = tmp_path / "f.pdf"
    path.write_text("placeholder", encoding="utf-8")

    class _Page:
        @staticmethod
        def extract_text() -> str:
            return ""

    class _Reader:
        def __init__(self, _path: str) -> None:
            self.pages = [_Page()]

    monkeypatch.setitem(sys.modules, "pypdf", SimpleNamespace(PdfReader=_Reader))
    monkeypatch.setitem(sys.modules, "pypdfium2", None)
    monkeypatch.setitem(sys.modules, "rapidocr_onnxruntime", None)

    with pytest.raises(RuntimeError, match="OCR is unavailable"):
        PdfFallbackConverter().convert(path, enable_ocr=True, ocr_strict=True)


def test_pdf_fallback_uses_ocr_when_available(monkeypatch, tmp_path: Path) -> None:
    path = tmp_path / "f.pdf"
    path.write_text("placeholder", encoding="utf-8")

    class _Page:
        @staticmethod
        def extract_text() -> str:
            return ""

    class _Reader:
        def __init__(self, _path: str) -> None:
            self.pages = [_Page()]

    class _Rendered:
        @staticmethod
        def to_numpy():
            return "image-array"

    class _PdfiumPage:
        @staticmethod
        def render(scale: int = 2):
            assert scale == 2
            return _Rendered()

    class _PdfiumDoc:
        def __init__(self, _path: str) -> None:
            pass

        @staticmethod
        def __getitem__(_idx: int):
            return _PdfiumPage()

    class _RapidOCR:
        @staticmethod
        def __call__(_image):
            return ([[None, "ocr text", 0.99]], 0.01)

    monkeypatch.setitem(sys.modules, "pypdf", SimpleNamespace(PdfReader=_Reader))
    monkeypatch.setitem(sys.modules, "pypdfium2", SimpleNamespace(PdfDocument=_PdfiumDoc))
    monkeypatch.setitem(
        sys.modules,
        "rapidocr_onnxruntime",
        SimpleNamespace(RapidOCR=lambda: _RapidOCR()),
    )

    result = PdfFallbackConverter().convert(path, enable_ocr=True)
    assert "### Page 1\nocr text" in result.content
    assert result.converter_name == "pypdf+rapidocr"
    assert result.warnings == []


def test_pdf_fallback_reuses_ocr_setup_across_textless_pages(monkeypatch, tmp_path: Path) -> None:
    path = tmp_path / "f.pdf"
    path.write_text("placeholder", encoding="utf-8")
    init_calls = {"count": 0}
    ocr_calls = {"count": 0}
    doc_calls = {"open": 0, "close": 0}

    class _Page:
        @staticmethod
        def extract_text() -> str:
            return ""

    class _Reader:
        def __init__(self, _path: str) -> None:
            self.pages = [_Page(), _Page()]

    class _Rendered:
        @staticmethod
        def to_numpy():
            return "image-array"

    class _PdfiumPage:
        @staticmethod
        def render(scale: int = 2):
            assert scale == 2
            return _Rendered()

    class _PdfiumDoc:
        def __init__(self, _path: str) -> None:
            doc_calls["open"] += 1

        @staticmethod
        def __getitem__(_idx: int):
            return _PdfiumPage()

        @staticmethod
        def close() -> None:
            doc_calls["close"] += 1

    class _RapidOCR:
        @staticmethod
        def __call__(_image):
            ocr_calls["count"] += 1
            return ([[None, f"ocr text {ocr_calls['count']}", 0.99]], 0.01)

    def _rapidocr_factory():
        init_calls["count"] += 1
        return _RapidOCR()

    monkeypatch.setitem(sys.modules, "pypdf", SimpleNamespace(PdfReader=_Reader))
    monkeypatch.setitem(sys.modules, "pypdfium2", SimpleNamespace(PdfDocument=_PdfiumDoc))
    monkeypatch.setitem(
        sys.modules,
        "rapidocr_onnxruntime",
        SimpleNamespace(RapidOCR=_rapidocr_factory),
    )

    result = PdfFallbackConverter().convert(path, enable_ocr=True)
    assert "### Page 1\nocr text 1" in result.content
    assert "### Page 2\nocr text 2" in result.content
    assert init_calls["count"] == 1
    assert ocr_calls["count"] == 2
    assert doc_calls["open"] == 1
    assert doc_calls["close"] == 1
    assert result.converter_name == "pypdf+rapidocr"
    assert result.warnings == []


def test_pdf_fallback_warns_when_ocr_returns_no_text(monkeypatch, tmp_path: Path) -> None:
    path = tmp_path / "f.pdf"
    path.write_text("placeholder", encoding="utf-8")

    class _Page:
        @staticmethod
        def extract_text() -> str:
            return ""

    class _Reader:
        def __init__(self, _path: str) -> None:
            self.pages = [_Page()]

    class _Rendered:
        @staticmethod
        def to_numpy():
            return "image-array"

    class _PdfiumPage:
        @staticmethod
        def render(scale: int = 2):
            assert scale == 2
            return _Rendered()

    class _PdfiumDoc:
        def __init__(self, _path: str) -> None:
            pass

        @staticmethod
        def __getitem__(_idx: int):
            return _PdfiumPage()

    class _RapidOCR:
        @staticmethod
        def __call__(_image):
            return ([], 0.01)

    monkeypatch.setitem(sys.modules, "pypdf", SimpleNamespace(PdfReader=_Reader))
    monkeypatch.setitem(sys.modules, "pypdfium2", SimpleNamespace(PdfDocument=_PdfiumDoc))
    monkeypatch.setitem(
        sys.modules,
        "rapidocr_onnxruntime",
        SimpleNamespace(RapidOCR=lambda: _RapidOCR()),
    )

    result = PdfFallbackConverter().convert(path, enable_ocr=True)
    assert len(result.warnings) == 1
    assert "OCR produced no text" in result.warnings[0]


def test_pdf_fallback_strict_raises_when_ocr_returns_no_text(monkeypatch, tmp_path: Path) -> None:
    path = tmp_path / "f.pdf"
    path.write_text("placeholder", encoding="utf-8")

    class _Page:
        @staticmethod
        def extract_text() -> str:
            return ""

    class _Reader:
        def __init__(self, _path: str) -> None:
            self.pages = [_Page()]

    class _Rendered:
        @staticmethod
        def to_numpy():
            return "image-array"

    class _PdfiumPage:
        @staticmethod
        def render(scale: int = 2):
            assert scale == 2
            return _Rendered()

    class _PdfiumDoc:
        def __init__(self, _path: str) -> None:
            pass

        @staticmethod
        def __getitem__(_idx: int):
            return _PdfiumPage()

    class _RapidOCR:
        @staticmethod
        def __call__(_image):
            return ([], 0.01)

    monkeypatch.setitem(sys.modules, "pypdf", SimpleNamespace(PdfReader=_Reader))
    monkeypatch.setitem(sys.modules, "pypdfium2", SimpleNamespace(PdfDocument=_PdfiumDoc))
    monkeypatch.setitem(
        sys.modules,
        "rapidocr_onnxruntime",
        SimpleNamespace(RapidOCR=lambda: _RapidOCR()),
    )

    with pytest.raises(RuntimeError, match="OCR produced no text"):
        PdfFallbackConverter().convert(path, enable_ocr=True, ocr_strict=True)


def test_pdf_fallback_close_if_possible_calls_close() -> None:
    called = {"closed": False}

    class _Closable:
        @staticmethod
        def close() -> None:
            called["closed"] = True

    PdfFallbackConverter()._close_if_possible(_Closable())
    assert called["closed"] is True


def test_pdf_fallback_extract_ocr_text_handles_none_str_and_dict_entries() -> None:
    converter = PdfFallbackConverter()
    assert converter._extract_ocr_text((None, 0.1)) == ""
    assert converter._extract_ocr_text("  direct text  ") == "direct text"
    assert converter._extract_ocr_text(([{"text": " hello "}], 0.1)) == "hello"
    assert converter._extract_ocr_text(123) == ""
    assert (
        converter._extract_ocr_text(
            ([[None, "   ", 0.5], {"text": "   "}, object(), {"text": 7}], 0.1)
        )
        == ""
    )


def test_pdf_fallback_render_pdf_page_supports_to_pil_and_raw_return() -> None:
    converter = PdfFallbackConverter()
    fake_path = Path("/tmp/unused.pdf")

    class _RenderedPil:
        @staticmethod
        def to_pil():
            return "pil-image"

    class _PagePil:
        @staticmethod
        def render(scale: int = 2):
            assert scale == 2
            return _RenderedPil()

        @staticmethod
        def close() -> None:
            return None

    class _DocPil:
        def __init__(self, _path: str) -> None:
            pass

        @staticmethod
        def __getitem__(_idx: int):
            return _PagePil()

        @staticmethod
        def close() -> None:
            return None

    class _RenderedRaw:
        pass

    class _PageRaw:
        @staticmethod
        def render(scale: int = 2):
            assert scale == 2
            return _RenderedRaw()

        @staticmethod
        def close() -> None:
            return None

    class _DocRaw:
        def __init__(self, _path: str) -> None:
            pass

        @staticmethod
        def __getitem__(_idx: int):
            return _PageRaw()

        @staticmethod
        def close() -> None:
            return None

    result_pil = converter._render_pdf_page(fake_path, 0, SimpleNamespace(PdfDocument=_DocPil))
    assert result_pil == "pil-image"

    result_raw = converter._render_pdf_page(fake_path, 0, SimpleNamespace(PdfDocument=_DocRaw))
    assert result_raw.__class__.__name__ == "_RenderedRaw"


def test_pdf_fallback_render_pdf_page_closes_doc_when_page_lookup_fails() -> None:
    converter = PdfFallbackConverter()
    fake_path = Path("/tmp/unused.pdf")
    closed = {"doc": False}

    class _Doc:
        def __init__(self, _path: str) -> None:
            pass

        @staticmethod
        def __getitem__(_idx: int):
            raise RuntimeError("page fail")

        @staticmethod
        def close() -> None:
            closed["doc"] = True

    with pytest.raises(RuntimeError, match="page fail"):
        converter._render_pdf_page(fake_path, 0, SimpleNamespace(PdfDocument=_Doc))
    assert closed["doc"] is True


def test_pdf_fallback_warns_when_ocr_engine_init_fails(monkeypatch, tmp_path: Path) -> None:
    path = tmp_path / "f.pdf"
    path.write_text("placeholder", encoding="utf-8")

    class _Page:
        @staticmethod
        def extract_text() -> str:
            return ""

    class _Reader:
        def __init__(self, _path: str) -> None:
            self.pages = [_Page()]

    class _PdfiumDoc:
        def __init__(self, _path: str) -> None:
            pass

    def _raise_init():
        raise RuntimeError("init boom")

    monkeypatch.setitem(sys.modules, "pypdf", SimpleNamespace(PdfReader=_Reader))
    monkeypatch.setitem(sys.modules, "pypdfium2", SimpleNamespace(PdfDocument=_PdfiumDoc))
    monkeypatch.setitem(
        sys.modules,
        "rapidocr_onnxruntime",
        SimpleNamespace(RapidOCR=_raise_init),
    )

    result = PdfFallbackConverter().convert(path, enable_ocr=True)
    assert len(result.warnings) == 1
    assert "initialization failed" in result.warnings[0]


def test_pdf_fallback_warns_when_ocr_runtime_fails(monkeypatch, tmp_path: Path) -> None:
    path = tmp_path / "f.pdf"
    path.write_text("placeholder", encoding="utf-8")
    doc_calls = {"close": 0}

    class _Page:
        @staticmethod
        def extract_text() -> str:
            return ""

    class _Reader:
        def __init__(self, _path: str) -> None:
            self.pages = [_Page()]

    class _Rendered:
        @staticmethod
        def to_numpy():
            return "image-array"

    class _PdfiumPage:
        @staticmethod
        def render(scale: int = 2):
            assert scale == 2
            return _Rendered()

    class _PdfiumDoc:
        def __init__(self, _path: str) -> None:
            pass

        @staticmethod
        def __getitem__(_idx: int):
            return _PdfiumPage()

        @staticmethod
        def close() -> None:
            doc_calls["close"] += 1

    class _RapidOCR:
        @staticmethod
        def __call__(_image):
            raise RuntimeError("ocr boom")

    monkeypatch.setitem(sys.modules, "pypdf", SimpleNamespace(PdfReader=_Reader))
    monkeypatch.setitem(sys.modules, "pypdfium2", SimpleNamespace(PdfDocument=_PdfiumDoc))
    monkeypatch.setitem(
        sys.modules,
        "rapidocr_onnxruntime",
        SimpleNamespace(RapidOCR=lambda: _RapidOCR()),
    )

    result = PdfFallbackConverter().convert(path, enable_ocr=True)
    assert len(result.warnings) == 1
    assert "OCR failed: ocr boom" in result.warnings[0]
    assert doc_calls["close"] == 1
