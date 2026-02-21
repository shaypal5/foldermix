from __future__ import annotations

from pathlib import Path

from .base import ConversionResult


class PdfFallbackConverter:
    def can_convert(self, ext: str) -> bool:
        try:
            import pypdf  # noqa: F401

            return ext.lower() == ".pdf"
        except ImportError:
            return False

    def convert(self, path: Path, encoding: str = "utf-8") -> ConversionResult:
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        pages = []
        for i, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            pages.append(f"### Page {i + 1}\n{text}")
        return ConversionResult(
            content="\n\n".join(pages),
            converter_name="pypdf",
            original_mime="application/pdf",
        )
