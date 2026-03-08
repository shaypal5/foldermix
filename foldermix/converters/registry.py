from __future__ import annotations

from .base import ConverterRegistry
from .docx_fallback import DocxFallbackConverter
from .ipynb import NotebookConverter
from .markitdown_conv import MarkitdownConverter
from .pdf_fallback import PdfFallbackConverter
from .pptx_fallback import PptxFallbackConverter
from .text import TextConverter
from .xlsx_fallback import XlsxFallbackConverter


def build_converter_registry(*, ipynb_include_outputs: bool = False) -> ConverterRegistry:
    registry = ConverterRegistry()
    registry.register(MarkitdownConverter())
    registry.register(PdfFallbackConverter())
    registry.register(DocxFallbackConverter())
    registry.register(XlsxFallbackConverter())
    registry.register(PptxFallbackConverter())
    registry.register(NotebookConverter(include_outputs=ipynb_include_outputs))
    registry.register(TextConverter())
    return registry
