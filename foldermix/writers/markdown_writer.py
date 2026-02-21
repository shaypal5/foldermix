from __future__ import annotations

from typing import IO

from .base import FileBundleItem, HeaderInfo, Writer

LANG_MAP: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".jsx": "jsx",
    ".tsx": "tsx",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".sh": "bash",
    ".bash": "bash",
    ".zsh": "bash",
    ".fish": "fish",
    ".ps1": "powershell",
    ".rb": "ruby",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".kt": "kotlin",
    ".swift": "swift",
    ".c": "c",
    ".cpp": "cpp",
    ".h": "c",
    ".hpp": "cpp",
    ".cs": "csharp",
    ".php": "php",
    ".xml": "xml",
    ".html": "html",
    ".htm": "html",
    ".css": "css",
    ".sql": "sql",
    ".r": "r",
    ".md": "markdown",
    ".rst": "rst",
    ".csv": "csv",
    ".tsv": "tsv",
}


def _make_anchor(relpath: str) -> str:
    """Generate a GitHub-style markdown anchor from a file's relative path."""
    return relpath.replace("/", "").replace(".", "").replace("_", "").replace("-", "").lower()


class MarkdownWriter(Writer):
    def __init__(self, include_toc: bool = True) -> None:
        self.include_toc = include_toc

    def write(self, out: IO[str], header: HeaderInfo, items: list[FileBundleItem]) -> None:
        out.write("# FolderPack Context\n\n")
        out.write(f"- **Root**: `{header.root}`\n")
        out.write(f"- **Generated**: {header.generated_at}\n")
        out.write(f"- **Version**: {header.version}\n")
        out.write(f"- **Files**: {header.file_count}\n")
        out.write(f"- **Total bytes**: {header.total_bytes:,}\n\n")

        if self.include_toc and items:
            out.write("## Table of Contents\n\n")
            for item in items:
                anchor = _make_anchor(item.relpath)
                out.write(f"- [{item.relpath}](#{anchor})\n")
            out.write("\n")

        out.write("---\n\n")

        for idx, item in enumerate(items):
            anchor = _make_anchor(item.relpath)
            out.write(f"## {item.relpath} {{#{anchor}}}\n\n")
            out.write(f"- **Size**: {item.size_bytes:,} bytes\n")
            out.write(f"- **Modified**: {item.mtime}\n")
            if item.sha256:
                out.write(f"- **SHA256**: `{item.sha256}`\n")
            if item.converter_name and item.converter_name != "text":
                out.write(f"- **Converter**: {item.converter_name}\n")
            if item.truncated:
                out.write("- **⚠️ TRUNCATED**\n")
            if item.warnings:
                for w in item.warnings:
                    out.write(f"- **⚠️ Warning**: {w}\n")
            out.write("\n")

            lang = LANG_MAP.get(item.ext, "")
            out.write(f"```{lang}\n")
            content = item.content
            # Escape closing fence inside content
            content = content.replace("```", "` ` `")
            out.write(content)
            if not content.endswith("\n"):
                out.write("\n")
            out.write("```\n\n")
            if idx < len(items) - 1:
                out.write("---\n\n")
            else:
                out.write("---\n")
