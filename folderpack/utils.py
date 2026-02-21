from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path


def sha256_file(path: Path) -> str:
    """Compute SHA-256 of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def mtime_iso(path: Path) -> str:
    ts = path.stat().st_mtime
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat(timespec="seconds")


def detect_encoding(path: Path) -> str:
    """Try to detect encoding; fall back to utf-8."""
    try:
        import charset_normalizer

        result = charset_normalizer.from_path(path)
        best = result.best()
        if best:
            return str(best.encoding)
    except ImportError:
        pass
    try:
        import chardet

        with open(path, "rb") as f:
            raw = f.read(65536)
        detected = chardet.detect(raw)
        if detected.get("encoding"):
            return detected["encoding"]
    except ImportError:
        pass
    return "utf-8"


def read_text_with_fallback(path: Path, encoding: str = "utf-8") -> tuple[str, str]:
    """Read text file with encoding fallback. Returns (text, encoding_used)."""
    try:
        return path.read_text(encoding=encoding), encoding
    except (UnicodeDecodeError, LookupError):
        detected = detect_encoding(path)
        try:
            return path.read_text(encoding=detected), detected
        except (UnicodeDecodeError, LookupError):
            return path.read_text(encoding="utf-8", errors="replace"), "utf-8 (with replacement)"


def apply_redaction(text: str, mode: str) -> str:
    if mode in ("emails", "all"):
        text = re.sub(
            r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b",
            "[REDACTED_EMAIL]",
            text,
        )
    if mode in ("phones", "all"):
        text = re.sub(
            r"\b(\+?1?\s*[-.]?\s*\(?\d{3}\)?[\s.\-]?\d{3}[\s.\-]?\d{4})\b",
            "[REDACTED_PHONE]",
            text,
        )
    return text


def strip_yaml_frontmatter(text: str) -> str:
    return re.sub(r"^---\s*\n.*?\n---\s*\n", "", text, count=1, flags=re.DOTALL)
