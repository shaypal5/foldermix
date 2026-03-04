from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path

_EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")
_PHONE_PATTERN = re.compile(r"\b(\+?1?\s*[-.]?\s*\(?\d{3}\)?[\s.\-]?\d{3}[\s.\-]?\d{4})\b")


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
    redacted_text, _ = apply_redaction_with_trace(text, mode)
    return redacted_text


def apply_redaction_with_trace(text: str, mode: str) -> tuple[str, dict[str, int]]:
    category_counts: dict[str, int] = {}
    if mode in ("emails", "all"):
        text, email_count = _EMAIL_PATTERN.subn("[REDACTED_EMAIL]", text)
        if email_count > 0:
            category_counts["emails"] = email_count
    if mode in ("phones", "all"):
        text, phone_count = _PHONE_PATTERN.subn("[REDACTED_PHONE]", text)
        if phone_count > 0:
            category_counts["phones"] = phone_count
    return text, category_counts


def strip_yaml_frontmatter(text: str) -> str:
    return re.sub(r"^---\s*\n.*?\n---\s*\n", "", text, count=1, flags=re.DOTALL)
