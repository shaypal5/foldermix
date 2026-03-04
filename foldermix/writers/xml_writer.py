from __future__ import annotations

import xml.sax.saxutils as saxutils
from typing import IO

from .base import FileBundleItem, HeaderInfo, Writer


class XmlWriter(Writer):
    def write(self, out: IO[str], header: HeaderInfo, items: list[FileBundleItem]) -> None:
        out.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        out.write("<foldermix>\n")
        out.write("  <header>\n")
        out.write(f"    <root>{saxutils.escape(header.root)}</root>\n")
        out.write(f"    <generated_at>{header.generated_at}</generated_at>\n")
        out.write(f"    <version>{saxutils.escape(header.version)}</version>\n")
        out.write(f"    <file_count>{header.file_count}</file_count>\n")
        out.write(f"    <total_bytes>{header.total_bytes}</total_bytes>\n")
        out.write("  </header>\n")
        out.write("  <files>\n")

        for item in items:
            out.write("    <file>\n")
            out.write(f"      <path>{saxutils.escape(item.relpath)}</path>\n")
            out.write(f"      <size>{item.size_bytes}</size>\n")
            out.write(f"      <mtime>{item.mtime}</mtime>\n")
            if item.sha256:
                out.write(f"      <sha256>{item.sha256}</sha256>\n")
            out.write(f"      <converter>{saxutils.escape(item.converter_name)}</converter>\n")
            if item.truncated:
                out.write("      <truncated>true</truncated>\n")
            warning_entries = item.warning_entries
            if not warning_entries and item.warnings:
                warning_entries = [
                    {
                        "code": "unclassified_warning",
                        "message": warning,
                    }
                    for warning in item.warnings
                ]
            if warning_entries:
                out.write("      <warnings>\n")
                for warning in warning_entries:
                    raw_code = warning.get("code", "")
                    code_text = str(raw_code).strip() or "unclassified_warning"
                    code = saxutils.escape(code_text)

                    raw_message = warning.get("message", "")
                    message_text = str(raw_message)
                    message = saxutils.escape(message_text)
                    out.write(f'        <warning code="{code}">{message}</warning>\n')
                out.write("      </warnings>\n")
            safe_content = item.content.replace("]]>", "]]]]><![CDATA[>")
            out.write(f"      <content><![CDATA[{safe_content}]]></content>\n")
            out.write("    </file>\n")

        out.write("  </files>\n")
        out.write("</foldermix>\n")
