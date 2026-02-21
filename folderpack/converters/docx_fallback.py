from __future__ import annotations

from pathlib import Path

from .base import ConversionResult


class DocxFallbackConverter:
    def can_convert(self, ext: str) -> bool:
        try:
            import docx  # noqa: F401

            return ext.lower() == ".docx"
        except ImportError:
            return False

    def convert(self, path: Path, encoding: str = "utf-8") -> ConversionResult:
        import docx

        doc = docx.Document(str(path))
        paragraphs = [p.text for p in doc.paragraphs]
        return ConversionResult(
            content="\n\n".join(paragraphs),
            converter_name="python-docx",
            original_mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
