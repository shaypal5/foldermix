from __future__ import annotations

import itertools
import shutil
from pathlib import Path

import pytest

from foldermix.converters.docx_fallback import DocxFallbackConverter
from foldermix.converters.pdf_fallback import PdfFallbackConverter
from foldermix.converters.xlsx_fallback import XlsxFallbackConverter

pytestmark = pytest.mark.integration

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "noisy_real_files"


def _max_blank_run(text: str) -> int:
    longest = 0
    current = 0
    for line in text.splitlines():
        if line.strip():
            longest = max(longest, current)
            current = 0
        else:
            current += 1
    return max(longest, current)


def _tail_blank_run(text: str) -> int:
    return len(
        list(itertools.takewhile(lambda line: not line.strip(), reversed(text.splitlines())))
    )


def test_noisy_xlsx_output_is_sanitized_and_trimmed() -> None:
    pytest.importorskip("openpyxl")
    result = XlsxFallbackConverter().convert(FIXTURE_DIR / "noisy_grades.xlsx")

    assert "## Sheet: ציונים" in result.content
    assert 'שם פרטי\tשם משפחה\tמספר זהות\tדוא"ל' in result.content
    assert (
        "קפב\tתשמני\t371228406\trgkqcozqs@mail.tau.invalid\trgkqcozqs\t\t77\t6.2\t27\t6\t31\t48\t1737069055"
        in result.content
    )
    assert (
        "אמב\tתהישפממ\t931801734\tqhhstwgod9@mail.tau.invalid\tqhhstwgod9\tקבוצה T - תנשמות האימה\t74\t42\t27\t60\t58\t73\t1737069055"
        in result.content
    )
    assert "@mail.tau.invalid" in result.content
    assert "doravital@mail.tau.ac.il" not in result.content
    assert "204661789" not in result.content
    assert "דור\tאביטל" not in result.content
    assert _tail_blank_run(result.content) == 0
    assert not any(line and not line.strip() for line in result.content.splitlines())


def test_noisy_docx_output_is_sanitized_and_compacted() -> None:
    pytest.importorskip("docx")
    result = DocxFallbackConverter().convert(FIXTURE_DIR / "noisy_feedback.docx")

    assert "2 - Jack & Jill - The Swan Strikers" in result.content
    assert "Research Question & Dataset" in result.content
    assert "Preprocessing" in result.content
    assert "# Jack Jeffries 986838724" in result.content
    assert "# Jill Jamaica 725256142" in result.content
    assert "# Lecturer - Killian Trillian Zapod" in result.content
    assert "Daniel Ninio" not in result.content
    assert "Tehila Malka" not in result.content
    assert "319121067" not in result.content
    assert _max_blank_run(result.content) <= 1
    assert result.content.index("Research Question & Dataset") < result.content.index(
        "Preprocessing"
    )


def test_noisy_pdf_hebrew_rtl_extraction_quality() -> None:
    pytest.importorskip("pypdf")
    if shutil.which("pdftotext") is None:
        pytest.skip("pdftotext unavailable in test environment")
    result = PdfFallbackConverter().convert(FIXTURE_DIR / "noisy_syllabus_hebrew.pdf")

    assert "Text Mining" in result.content
    assert "דרישות קדם" in result.content
    assert "שי פלצ'י אפק" in result.content
    assert "nop@chau.ac.jl" in result.content
    assert result.converter_name == "pdftotext"
    assert "דרישות קדם" in result.content.split("Text Mining", 1)[1]
    assert "ם:דרישות קד" not in result.content


def test_noisy_xlsx_copy_sheets_are_suppressed() -> None:
    pytest.importorskip("openpyxl")
    result = XlsxFallbackConverter().convert(FIXTURE_DIR / "noisy_grades.xlsx")

    assert "## Sheet: ציונים" in result.content
    assert "## Sheet: Copy of ציונים" not in result.content
    assert "## Sheet: Copy of ציונים 1" not in result.content
