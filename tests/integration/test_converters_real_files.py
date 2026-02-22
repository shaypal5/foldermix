from __future__ import annotations

from pathlib import Path

import pytest

from foldermix.converters.docx_fallback import DocxFallbackConverter
from foldermix.converters.pdf_fallback import PdfFallbackConverter
from foldermix.converters.pptx_fallback import PptxFallbackConverter
from foldermix.converters.xlsx_fallback import XlsxFallbackConverter

pytestmark = pytest.mark.integration

FIXTURE_DIR = Path(__file__).parent / "fixtures"
REAL_DIR = FIXTURE_DIR / "real_files"
EXPECTED_DIR = FIXTURE_DIR / "expected" / "real_files"


@pytest.mark.parametrize(
    (
        "required_module",
        "converter",
        "src_name",
        "expected_name",
        "expected_converter",
        "expected_mime",
    ),
    [
        (
            "pypdf",
            PdfFallbackConverter(),
            "sample.pdf",
            "sample_pdf.txt",
            "pypdf",
            "application/pdf",
        ),
        (
            "docx",
            DocxFallbackConverter(),
            "sample.docx",
            "sample_docx.txt",
            "python-docx",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ),
        (
            "pptx",
            PptxFallbackConverter(),
            "sample.pptx",
            "sample_pptx.txt",
            "python-pptx",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ),
        (
            "openpyxl",
            XlsxFallbackConverter(),
            "sample.xlsx",
            "sample_xlsx.txt",
            "openpyxl",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ),
    ],
)
def test_real_file_converter_outputs(
    required_module: str,
    converter,
    src_name: str,
    expected_name: str,
    expected_converter: str,
    expected_mime: str,
) -> None:
    pytest.importorskip(required_module)
    src = REAL_DIR / src_name
    expected = (EXPECTED_DIR / expected_name).read_text(encoding="utf-8")

    result = converter.convert(src)

    assert result.content == expected
    assert result.converter_name == expected_converter
    assert result.original_mime == expected_mime


@pytest.mark.parametrize(
    ("required_module", "converter", "ext"),
    [
        ("pypdf", PdfFallbackConverter(), ".pdf"),
        ("docx", DocxFallbackConverter(), ".docx"),
        ("pptx", PptxFallbackConverter(), ".pptx"),
        ("openpyxl", XlsxFallbackConverter(), ".xlsx"),
    ],
)
def test_real_file_converter_can_convert_when_dependency_installed(
    required_module: str,
    converter,
    ext: str,
) -> None:
    pytest.importorskip(required_module)
    assert converter.can_convert(ext) is True
