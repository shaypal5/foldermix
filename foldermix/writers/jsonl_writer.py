from __future__ import annotations

import json
from typing import IO

from .base import FileBundleItem, HeaderInfo, Writer


class JsonlWriter(Writer):
    def write(self, out: IO[str], header: HeaderInfo, items: list[FileBundleItem]) -> None:
        header_line = {
            "type": "header",
            "root": header.root,
            "generated_at": header.generated_at,
            "version": header.version,
            "file_count": header.file_count,
            "total_bytes": header.total_bytes,
            "args": header.args,
        }
        out.write(json.dumps(header_line, ensure_ascii=False) + "\n")

        for item in items:
            file_line = {
                "type": "file",
                "path": item.relpath,
                "ext": item.ext,
                "size_bytes": item.size_bytes,
                "mtime": item.mtime,
                "sha256": item.sha256,
                "converter": item.converter_name,
                "original_mime": item.original_mime,
                "warnings": item.warnings,
                "truncated": item.truncated,
                "content": item.content,
            }
            out.write(json.dumps(file_line, ensure_ascii=False) + "\n")
