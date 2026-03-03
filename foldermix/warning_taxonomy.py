from __future__ import annotations

from collections.abc import Iterable

WARNING_CODE_ENCODING_FALLBACK = "encoding_fallback"
WARNING_CODE_OCR_DISABLED = "ocr_disabled"
WARNING_CODE_OCR_DEPENDENCIES_MISSING = "ocr_dependencies_missing"
WARNING_CODE_OCR_INITIALIZATION_FAILED = "ocr_initialization_failed"
WARNING_CODE_OCR_FAILED = "ocr_failed"
WARNING_CODE_OCR_NO_TEXT = "ocr_no_text"
WARNING_CODE_CONVERTER_UNAVAILABLE = "converter_unavailable"
WARNING_CODE_UNCLASSIFIED = "unclassified_warning"


def classify_warning_message(message: str) -> str:
    lowered = message.lower()
    if lowered.startswith("encoding fallback:"):
        return WARNING_CODE_ENCODING_FALLBACK
    if "ocr is disabled" in lowered:
        return WARNING_CODE_OCR_DISABLED
    if "ocr dependencies missing" in lowered:
        return WARNING_CODE_OCR_DEPENDENCIES_MISSING
    if "ocr engine initialization failed" in lowered:
        return WARNING_CODE_OCR_INITIALIZATION_FAILED
    if "ocr produced no text" in lowered:
        return WARNING_CODE_OCR_NO_TEXT
    if "ocr failed:" in lowered:
        return WARNING_CODE_OCR_FAILED
    if "dependencies are unavailable" in lowered:
        return WARNING_CODE_CONVERTER_UNAVAILABLE
    return WARNING_CODE_UNCLASSIFIED


def normalize_warning_entries(messages: Iterable[str]) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    for message in messages:
        entries.append(
            {
                "code": classify_warning_message(message),
                "message": message,
            }
        )
    return entries
