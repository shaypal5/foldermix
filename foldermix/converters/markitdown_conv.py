from __future__ import annotations

from pathlib import Path

from .base import ConversionResult


class MarkitdownConverter:
    EXTENSIONS = {".pdf", ".docx", ".pptx", ".xlsx"}

    def can_convert(self, ext: str) -> bool:
        try:
            import markitdown  # noqa: F401

            return ext.lower() in self.EXTENSIONS
        except ImportError:
            return False

    def convert(self, path: Path, encoding: str = "utf-8") -> ConversionResult:
        from markitdown import MarkItDown

        md = MarkItDown()
        result = md.convert(str(path))
        return ConversionResult(
            content=result.text_content,
            converter_name="markitdown",
            original_mime=f"application/{path.suffix.lstrip('.')}",
        )
