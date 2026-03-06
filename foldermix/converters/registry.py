from __future__ import annotations

from .base import ConverterRegistry
from .docx_fallback import DocxFallbackConverter
from .markitdown_conv import MarkitdownConverter
from .pdf_fallback import PdfFallbackConverter
from .pptx_fallback import PptxFallbackConverter
from .text import TextConverter
from .xlsx_fallback import XlsxFallbackConverter


def build_converter_registry() -> ConverterRegistry:
    registry = ConverterRegistry()
    registry.register(MarkitdownConverter())
    registry.register(PdfFallbackConverter())
    registry.register(DocxFallbackConverter())
    registry.register(XlsxFallbackConverter())
    registry.register(PptxFallbackConverter())
    registry.register(TextConverter())
    return registry
