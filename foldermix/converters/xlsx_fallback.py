from __future__ import annotations

from pathlib import Path

from ._normalize import collapse_blank_runs, normalize_whitespace_line
from .base import ConversionResult


class XlsxFallbackConverter:
    def can_convert(self, ext: str) -> bool:
        try:
            import openpyxl  # noqa: F401

            return ext.lower() == ".xlsx"
        except ImportError:
            return False

    def convert(self, path: Path, encoding: str = "utf-8") -> ConversionResult:
        import openpyxl

        wb = openpyxl.load_workbook(str(path), read_only=True, data_only=True)
        parts: list[str] = []
        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            parts.append(f"## Sheet: {sheet_name}")
            rows: list[str] = []
            for row in ws.iter_rows(values_only=True):
                cells = [normalize_whitespace_line("" if v is None else str(v)) for v in row]
                while cells and not cells[-1].strip():
                    cells.pop()
                rows.append("\t".join(cells))
            parts.append("\n".join(collapse_blank_runs(rows)))
        return ConversionResult(
            content="\n\n".join(parts),
            converter_name="openpyxl",
            original_mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
