from __future__ import annotations

from collections.abc import Iterable


def normalize_whitespace_line(text: str) -> str:
    return text.replace("\xa0", " ").rstrip()


def collapse_blank_runs(lines: Iterable[str], *, max_blank_lines: int = 1) -> list[str]:
    normalized: list[str] = []
    blank_run = 0
    seen_content = False

    for raw in lines:
        line = normalize_whitespace_line(raw)
        if not line.strip():
            if not seen_content:
                continue
            blank_run += 1
            if blank_run <= max_blank_lines:
                normalized.append("")
            continue

        seen_content = True
        blank_run = 0
        normalized.append(line)

    while normalized and not normalized[-1]:
        normalized.pop()
    return normalized
