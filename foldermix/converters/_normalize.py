from __future__ import annotations


def normalize_whitespace_line(text: str) -> str:
    return text.replace("\xa0", " ").rstrip()
