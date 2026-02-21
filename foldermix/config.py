from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

DEFAULT_INCLUDE_EXT: list[str] = [
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
    ".pdf",
    ".docx",
    ".pptx",
    ".xlsx",
]

DEFAULT_EXCLUDE_EXT: list[str] = [
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".bmp",
    ".ico",
    ".svg",
    ".webp",
    ".mp4",
    ".mp3",
    ".avi",
    ".mov",
    ".mkv",
    ".wav",
    ".zip",
    ".tar",
    ".gz",
    ".bz2",
    ".7z",
    ".rar",
    ".exe",
    ".dll",
    ".so",
    ".dylib",
    ".bin",
    ".dat",
    ".db",
    ".sqlite",
    ".lock",
    ".woff",
    ".woff2",
    ".ttf",
    ".eot",
]

DEFAULT_EXCLUDE_DIRS: list[str] = [
    ".git",
    "node_modules",
    "dist",
    "build",
    ".venv",
    "__pycache__",
    ".tox",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
]

SENSITIVE_PATTERNS: set[str] = {
    ".env",
    "*.pem",
    "*.key",
    "id_rsa",
    "id_dsa",
    "*.p12",
    "*.pfx",
    "credentials",
    ".netrc",
}


class PackConfig(BaseModel):
    root: Path
    out: Path | None = None
    format: Literal["md", "xml", "jsonl"] = "md"
    include_ext: list[str] | None = None
    exclude_ext: list[str] = Field(default_factory=lambda: list(DEFAULT_EXCLUDE_EXT))
    exclude_dirs: list[str] = Field(default_factory=lambda: list(DEFAULT_EXCLUDE_DIRS))
    exclude_glob: list[str] = Field(default_factory=list)
    include_glob: list[str] = Field(default_factory=list)
    max_bytes: int = 10_000_000
    max_total_bytes: int | None = None
    max_files: int | None = None
    hidden: bool = False
    follow_symlinks: bool = False
    respect_gitignore: bool = True
    line_ending: Literal["lf", "crlf"] = "lf"
    encoding: str = "utf-8"
    workers: int = 4
    progress: bool = False
    dry_run: bool = False
    report: Path | None = None
    continue_on_error: bool = False
    on_oversize: Literal["skip", "truncate"] = "skip"
    redact: Literal["none", "emails", "phones", "all"] = "none"
    strip_frontmatter: bool = False
    include_sha256: bool = True
    include_toc: bool = True
