from __future__ import annotations

import json
from pathlib import Path

from ._normalize import normalize_whitespace_line
from .base import ConversionResult


def _coerce_text(value: object) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "".join(str(part) for part in value)
    return ""


def _normalize_block(text: str) -> str:
    lines = [normalize_whitespace_line(line) for line in text.splitlines()]
    start = 0
    end = len(lines)
    while start < end and not lines[start].strip():
        start += 1
    while end > start and not lines[end - 1].strip():
        end -= 1
    if start >= end:
        return ""
    return "\n".join(lines[start:end])


def _indent_block(text: str) -> str:
    return "\n".join(f"    {line}" if line else "" for line in text.splitlines())


def _summarize_rich_output(output: dict[str, object]) -> str:
    lines = [f"output_type: {output.get('output_type', 'unknown')}"]
    data = output.get("data")
    if isinstance(data, dict):
        mime_types = ", ".join(sorted(str(key) for key in data))
        if mime_types:
            lines.append(f"data keys: {mime_types}")
    metadata = output.get("metadata")
    if isinstance(metadata, dict) and metadata:
        lines.append(f"metadata keys: {', '.join(sorted(str(key) for key in metadata))}")
    return _normalize_block("\n".join(lines))


def _summarize_unknown_output(output: dict[str, object]) -> str:
    lines = [f"output_type: {output.get('output_type', 'unknown')}"]
    top_level_keys = ", ".join(sorted(str(key) for key in output if key != "output_type"))
    if top_level_keys:
        lines.append(f"top-level keys: {top_level_keys}")
    data = output.get("data")
    if isinstance(data, dict) and data:
        lines.append(f"data keys: {', '.join(sorted(str(key) for key in data))}")
    metadata = output.get("metadata")
    if isinstance(metadata, dict) and metadata:
        lines.append(f"metadata keys: {', '.join(sorted(str(key) for key in metadata))}")
    return _normalize_block("\n".join(lines))


def _render_output(output: dict[str, object]) -> str:
    output_type = output.get("output_type")
    if output_type == "stream":
        return _normalize_block(_coerce_text(output.get("text", "")))
    if output_type in {"display_data", "execute_result", "update_display_data"}:
        data = output.get("data")
        if isinstance(data, dict):
            text_plain = data.get("text/plain")
            rendered = _normalize_block(_coerce_text(text_plain))
            if rendered:
                return rendered
        return _summarize_rich_output(output)
    if output_type == "error":
        traceback = output.get("traceback")
        if isinstance(traceback, list):
            rendered = _normalize_block("\n".join(str(line) for line in traceback))
            if rendered:
                return rendered
        ename = output.get("ename", "Error")
        evalue = output.get("evalue", "")
        return _normalize_block(f"{ename}: {evalue}")
    return _summarize_unknown_output(output)


class NotebookConverter:
    def __init__(self, *, include_outputs: bool = False) -> None:
        self.include_outputs = include_outputs

    def can_convert(self, ext: str) -> bool:
        return ext.lower() == ".ipynb"

    def convert(self, path: Path, encoding: str = "utf-8") -> ConversionResult:
        with path.open("rb") as handle:
            raw = json.load(handle)
        if not isinstance(raw, dict):
            raise RuntimeError("Notebook root must be a JSON object")

        metadata = raw.get("metadata")
        language = "python"
        if isinstance(metadata, dict):
            language_info = metadata.get("language_info")
            if isinstance(language_info, dict):
                language = str(language_info.get("name", language)) or language

        sections: list[str] = []
        cells = raw.get("cells")
        if not isinstance(cells, list):
            raise RuntimeError("Notebook must contain a list of cells")

        for index, cell in enumerate(cells, start=1):
            if not isinstance(cell, dict):
                continue
            cell_type = str(cell.get("cell_type", "raw"))
            source = _normalize_block(_coerce_text(cell.get("source", "")))
            outputs = cell.get("outputs")

            if cell_type == "markdown":
                if source:
                    sections.append(f"### Markdown Cell {index}\n\n{source}")
                continue

            if cell_type == "raw":
                if source:
                    sections.append(f"### Raw Cell {index}\n\n{source}")
                continue

            if cell_type != "code":
                if source:
                    sections.append(f"### {cell_type.title()} Cell {index}\n\n{source}")
                continue

            code_lines = [f"### Code Cell {index}", "", f"Language: {language}"]
            if source:
                code_lines.extend(["", _indent_block(source)])
            section_parts = ["\n".join(code_lines)]
            if self.include_outputs and isinstance(outputs, list):
                rendered_outputs = [
                    rendered
                    for output in outputs
                    if isinstance(output, dict) and (rendered := _render_output(output))
                ]
                if rendered_outputs:
                    output_parts = ["#### Outputs"]
                    for output_index, rendered_output in enumerate(rendered_outputs, start=1):
                        output_parts.extend(
                            [
                                "",
                                f"Output {output_index}:",
                                "",
                                _indent_block(rendered_output),
                            ]
                        )
                    section_parts.append("\n".join(output_parts))
            if source or len(section_parts) > 1:
                sections.append("\n\n".join(section_parts))

        return ConversionResult(
            content="\n\n".join(sections).strip(),
            converter_name="ipynb",
            original_mime="application/x-ipynb+json",
        )
