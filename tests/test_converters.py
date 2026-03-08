from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from foldermix.converters.base import ConversionResult, ConverterRegistry
from foldermix.converters.text import TextConverter


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

    def test_convert_warns_on_encoding_fallback(self, monkeypatch, tmp_path: Path) -> None:
        import foldermix.utils as utils

        f = tmp_path / "simple.txt"
        f.write_text("simple text")
        monkeypatch.setattr(utils, "read_text_with_fallback", lambda *_: ("content", "latin-1"))
        converter = TextConverter()
        result = converter.convert(f, encoding="utf-8")
        assert "Encoding fallback" in result.warnings[0]


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
        from foldermix.converters.markitdown_conv import MarkitdownConverter

        converter = MarkitdownConverter()
        with patch.dict(sys.modules, {"markitdown": None}):
            assert converter.can_convert(".pdf") is False

    def test_can_convert_returns_true_when_installed(self) -> None:
        from foldermix.converters.markitdown_conv import MarkitdownConverter

        mock_markitdown = MagicMock()
        converter = MarkitdownConverter()
        with patch.dict(sys.modules, {"markitdown": mock_markitdown}):
            assert converter.can_convert(".pdf") is True

    def test_supported_extensions(self) -> None:
        from foldermix.converters.markitdown_conv import MarkitdownConverter

        conv = MarkitdownConverter()
        mock_mod = MagicMock()
        with patch.dict(sys.modules, {"markitdown": mock_mod}):
            assert conv.can_convert(".pdf") is True
            assert conv.can_convert(".docx") is True
            assert conv.can_convert(".pptx") is True
            assert conv.can_convert(".xlsx") is True
            assert conv.can_convert(".txt") is False


class TestNotebookConverter:
    def test_can_convert_ipynb(self) -> None:
        from foldermix.converters.ipynb import NotebookConverter

        converter = NotebookConverter()
        assert converter.can_convert(".ipynb") is True
        assert converter.can_convert(".txt") is False

    def test_convert_notebook_without_outputs(self, tmp_path: Path) -> None:
        from foldermix.converters.ipynb import NotebookConverter

        notebook = tmp_path / "demo.ipynb"
        notebook.write_text(
            (
                '{"metadata":{"language_info":{"name":"python"}},"cells":['
                '{"cell_type":"markdown","source":["# Title\\n","Intro"]},'
                '{"cell_type":"code","source":["print(1)\\n"],"outputs":['
                '{"output_type":"stream","name":"stdout","text":["1\\\\n"]}]}]}'
            ),
            encoding="utf-8",
        )

        result = NotebookConverter(include_outputs=False).convert(notebook)

        assert "### Markdown Cell 1" in result.content
        assert "### Code Cell 2" in result.content
        assert "Language: python" in result.content
        assert "    print(1)" in result.content
        assert "#### Outputs" not in result.content
        assert result.converter_name == "ipynb"

    def test_convert_notebook_with_outputs(self, tmp_path: Path) -> None:
        from foldermix.converters.ipynb import NotebookConverter

        notebook = tmp_path / "demo.ipynb"
        notebook.write_text(
            (
                '{"metadata":{"language_info":{"name":"python"}},"cells":['
                '{"cell_type":"code","source":["print(1)\\n"],"outputs":['
                '{"output_type":"stream","name":"stdout","text":["1\\\\n"]},'
                '{"output_type":"execute_result","data":{"text/plain":["2"]}}]}]}'
            ),
            encoding="utf-8",
        )

        result = NotebookConverter(include_outputs=True).convert(notebook)

        assert "#### Outputs" in result.content
        assert "Output 1:" in result.content
        assert "Output 2:" in result.content
        assert "    1" in result.content
        assert "    2" in result.content
        assert "```text" not in result.content
        assert "1" in result.content
        assert "2" in result.content

    def test_convert_notebook_preserves_leading_indentation(self, tmp_path: Path) -> None:
        from foldermix.converters.ipynb import NotebookConverter

        notebook = tmp_path / "indented.ipynb"
        notebook.write_text(
            (
                '{"metadata":{"language_info":{"name":"python"}},"cells":['
                '{"cell_type":"code","source":["    if True:\\n","        print(1)\\n"]}'
                "]}"
            ),
            encoding="utf-8",
        )

        result = NotebookConverter().convert(notebook)

        assert "    if True:" in result.content
        assert "        print(1)" in result.content

    def test_convert_notebook_covers_raw_custom_and_output_fallbacks(self, tmp_path: Path) -> None:
        from foldermix.converters.ipynb import NotebookConverter

        notebook = tmp_path / "rich.ipynb"
        notebook.write_text(
            (
                '{"metadata":{},"cells":['
                '{"cell_type":"raw","source":["  raw note  "]},'
                '{"cell_type":"custom","source":["custom payload"]},'
                '{"cell_type":"code","source":["x = 1\\n"],"outputs":['
                '{"output_type":"display_data","data":{"application/json":{"value":1}}},'
                '{"output_type":"error","ename":"ValueError","evalue":"bad","traceback":["Trace 1","Trace 2"]},'
                '{"output_type":"mystery","payload":{"ok":true}}'
                "]}]}"
            ),
            encoding="utf-8",
        )

        result = NotebookConverter(include_outputs=True).convert(notebook)

        assert "### Raw Cell 1" in result.content
        assert "raw note" in result.content
        assert "### Custom Cell 2" in result.content
        assert "custom payload" in result.content
        assert '"output_type": "display_data"' in result.content
        assert "Trace 1" in result.content
        assert "Trace 2" in result.content
        assert '"output_type": "mystery"' in result.content

    def test_convert_notebook_error_without_traceback(self, tmp_path: Path) -> None:
        from foldermix.converters.ipynb import NotebookConverter

        notebook = tmp_path / "errors.ipynb"
        notebook.write_text(
            (
                '{"metadata":{},"cells":['
                '{"cell_type":"code","source":["run()\\n"],"outputs":['
                '{"output_type":"error","ename":"RuntimeError","evalue":"boom"}'
                "]}]}"
            ),
            encoding="utf-8",
        )

        result = NotebookConverter(include_outputs=True).convert(notebook)

        assert "RuntimeError: boom" in result.content

    def test_convert_notebook_ignores_non_dict_cells_and_empty_content(
        self, tmp_path: Path
    ) -> None:
        from foldermix.converters.ipynb import NotebookConverter

        notebook = tmp_path / "sparse.ipynb"
        notebook.write_text(
            (
                '{"metadata":{},"cells":['
                '"skip-me",'
                '{"cell_type":"markdown","source":42},'
                '{"cell_type":"code","source":"","outputs":[]}'
                "]}"
            ),
            encoding="utf-8",
        )

        result = NotebookConverter(include_outputs=False).convert(notebook)

        assert result.content == ""

    def test_convert_notebook_covers_empty_branches(self, tmp_path: Path) -> None:
        from foldermix.converters.ipynb import NotebookConverter

        notebook = tmp_path / "branches.ipynb"
        notebook.write_text(
            (
                '{"metadata":"not-a-dict","cells":['
                '{"cell_type":"raw","source":""},'
                '{"cell_type":"custom","source":""},'
                '{"cell_type":"code","source":"","outputs":['
                '{"output_type":"display_data","data":"not-a-dict"},'
                '{"output_type":"error","traceback":["","   "]},'
                '{"output_type":"stream","text":["","   "]}'
                "]}]}"
            ),
            encoding="utf-8",
        )

        result = NotebookConverter(include_outputs=True).convert(notebook)

        assert "### Code Cell 3" in result.content
        assert '"output_type": "display_data"' in result.content
        assert "Error:" in result.content
        assert "#### Outputs" in result.content

    def test_convert_notebook_skips_empty_rendered_outputs(self, tmp_path: Path) -> None:
        from foldermix.converters.ipynb import NotebookConverter

        notebook = tmp_path / "empty-outputs.ipynb"
        notebook.write_text(
            (
                '{"metadata":{},"cells":['
                '{"cell_type":"code","source":"",'
                '"outputs":[{"output_type":"stream","text":["","   "]}]}'
                "]}"
            ),
            encoding="utf-8",
        )

        result = NotebookConverter(include_outputs=True).convert(notebook)

        assert result.content == ""

    def test_convert_notebook_validates_root_and_cells(self, tmp_path: Path) -> None:
        from foldermix.converters.ipynb import NotebookConverter

        bad_root = tmp_path / "bad-root.ipynb"
        bad_root.write_text('["not", "an", "object"]', encoding="utf-8")

        bad_cells = tmp_path / "bad-cells.ipynb"
        bad_cells.write_text('{"metadata":{},"cells":"oops"}', encoding="utf-8")

        converter = NotebookConverter()

        with pytest.raises(RuntimeError, match="Notebook root must be a JSON object"):
            converter.convert(bad_root)

        with pytest.raises(RuntimeError, match="Notebook must contain a list of cells"):
            converter.convert(bad_cells)


class TestPdfFallbackConverter:
    def test_can_convert_returns_false_when_not_installed(self) -> None:
        from foldermix.converters.pdf_fallback import PdfFallbackConverter

        converter = PdfFallbackConverter()
        with patch.dict(sys.modules, {"pypdf": None}):
            assert converter.can_convert(".pdf") is False

    def test_can_convert_pdf(self) -> None:
        from foldermix.converters.pdf_fallback import PdfFallbackConverter

        converter = PdfFallbackConverter()
        mock_pypdf = MagicMock()
        with patch.dict(sys.modules, {"pypdf": mock_pypdf}):
            assert converter.can_convert(".pdf") is True

    def test_cannot_convert_non_pdf(self) -> None:
        from foldermix.converters.pdf_fallback import PdfFallbackConverter

        converter = PdfFallbackConverter()
        mock_pypdf = MagicMock()
        with patch.dict(sys.modules, {"pypdf": mock_pypdf}):
            assert converter.can_convert(".txt") is False
