from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

from folderpack.converters.base import ConversionResult, ConverterRegistry
from folderpack.converters.text import TextConverter


class TestTextConverter:
    def test_can_convert_py(self) -> None:
        converter = TextConverter()
        assert converter.can_convert(".py") is True

    def test_can_convert_md(self) -> None:
        converter = TextConverter()
        assert converter.can_convert(".md") is True

    def test_cannot_convert_png(self) -> None:
        converter = TextConverter()
        assert converter.can_convert(".png") is False

    def test_convert_text_file(self, tmp_path: Path) -> None:
        f = tmp_path / "hello.py"
        f.write_text("print('hello')\n")
        converter = TextConverter()
        result = converter.convert(f)
        assert "print('hello')" in result.content
        assert result.converter_name == "text"

    def test_convert_utf8(self, tmp_path: Path) -> None:
        f = tmp_path / "unicode.txt"
        f.write_text("Hello 你好 🌍\n", encoding="utf-8")
        converter = TextConverter()
        result = converter.convert(f, encoding="utf-8")
        assert "你好" in result.content

    def test_convert_no_warnings_on_correct_encoding(self, tmp_path: Path) -> None:
        f = tmp_path / "simple.txt"
        f.write_text("simple text")
        converter = TextConverter()
        result = converter.convert(f, encoding="utf-8")
        assert result.warnings == []


class TestConverterRegistry:
    def test_register_and_get(self) -> None:
        registry = ConverterRegistry()
        converter = TextConverter()
        registry.register(converter)
        result = registry.get_converter(".py")
        assert result is converter

    def test_get_none_for_unknown(self) -> None:
        registry = ConverterRegistry()
        result = registry.get_converter(".unknown_xyz")
        assert result is None

    def test_first_registered_wins(self) -> None:
        registry = ConverterRegistry()

        class FakeConverter:
            def can_convert(self, ext: str) -> bool:
                return ext == ".py"

            def convert(self, path: Path, encoding: str = "utf-8") -> ConversionResult:
                return ConversionResult(content="fake", converter_name="fake")

        fake = FakeConverter()
        registry.register(fake)
        registry.register(TextConverter())
        result = registry.get_converter(".py")
        assert result is fake


class TestMarkitdownConverter:
    def test_can_convert_returns_false_when_not_installed(self) -> None:
        from folderpack.converters.markitdown_conv import MarkitdownConverter

        converter = MarkitdownConverter()
        with patch.dict(sys.modules, {"markitdown": None}):
            assert converter.can_convert(".pdf") is False

    def test_can_convert_returns_true_when_installed(self) -> None:
        from folderpack.converters.markitdown_conv import MarkitdownConverter

        mock_markitdown = MagicMock()
        converter = MarkitdownConverter()
        with patch.dict(sys.modules, {"markitdown": mock_markitdown}):
            assert converter.can_convert(".pdf") is True

    def test_supported_extensions(self) -> None:
        from folderpack.converters.markitdown_conv import MarkitdownConverter

        conv = MarkitdownConverter()
        mock_mod = MagicMock()
        with patch.dict(sys.modules, {"markitdown": mock_mod}):
            assert conv.can_convert(".pdf") is True
            assert conv.can_convert(".docx") is True
            assert conv.can_convert(".pptx") is True
            assert conv.can_convert(".xlsx") is True
            assert conv.can_convert(".txt") is False


class TestPdfFallbackConverter:
    def test_can_convert_returns_false_when_not_installed(self) -> None:
        from folderpack.converters.pdf_fallback import PdfFallbackConverter

        converter = PdfFallbackConverter()
        with patch.dict(sys.modules, {"pypdf": None}):
            assert converter.can_convert(".pdf") is False

    def test_can_convert_pdf(self) -> None:
        from folderpack.converters.pdf_fallback import PdfFallbackConverter

        converter = PdfFallbackConverter()
        mock_pypdf = MagicMock()
        with patch.dict(sys.modules, {"pypdf": mock_pypdf}):
            assert converter.can_convert(".pdf") is True

    def test_cannot_convert_non_pdf(self) -> None:
        from folderpack.converters.pdf_fallback import PdfFallbackConverter

        converter = PdfFallbackConverter()
        mock_pypdf = MagicMock()
        with patch.dict(sys.modules, {"pypdf": mock_pypdf}):
            assert converter.can_convert(".txt") is False
