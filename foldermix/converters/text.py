from __future__ import annotations

from pathlib import Path

from .base import ConversionResult

TEXT_EXTENSIONS = {
    ".txt",
    ".md",
    ".rst",
    ".py",
    ".js",
    ".ts",
    ".jsx",
    ".tsx",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".ini",
    ".cfg",
    ".csv",
    ".tsv",
    ".sql",
    ".html",
    ".htm",
    ".css",
    ".sh",
    ".bash",
    ".zsh",
    ".fish",
    ".ps1",
    ".rb",
    ".go",
    ".rs",
    ".java",
    ".kt",
    ".swift",
    ".c",
    ".cpp",
    ".h",
    ".hpp",
    ".cs",
    ".php",
    ".xml",
    ".r",
    ".scala",
    ".clj",
    ".ex",
    ".exs",
    ".erl",
    ".hs",
    ".lua",
    ".pl",
    ".pm",
    ".t",
    ".vim",
    ".nix",
    ".tf",
    ".dockerfile",
    ".makefile",
    ".gitignore",
    ".gitattributes",
    ".editorconfig",
    ".env.example",
}


class TextConverter:
    def can_convert(self, ext: str) -> bool:
        return ext.lower() in TEXT_EXTENSIONS

    def convert(self, path: Path, encoding: str = "utf-8") -> ConversionResult:
        from foldermix.utils import read_text_with_fallback

        text, enc_used = read_text_with_fallback(path, encoding)
        warnings: list[str] = []
        if enc_used != encoding:
            warnings.append(f"Encoding fallback: used {enc_used!r} instead of {encoding!r}")
        return ConversionResult(
            content=text,
            warnings=warnings,
            converter_name="text",
            original_mime=f"text/{path.suffix.lstrip('.') or 'plain'}",
        )
