from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol


@dataclass
class ConversionResult:
    content: str
    warnings: list[str] = field(default_factory=list)
    converter_name: str = "unknown"
    original_mime: str = ""


class Converter(Protocol):
    def can_convert(self, ext: str) -> bool: ...

    def convert(self, path: Path, encoding: str = "utf-8") -> ConversionResult: ...


class ConverterRegistry:
    def __init__(self) -> None:
        self._converters: list[Converter] = []

    def register(self, converter: Converter) -> None:
        self._converters.append(converter)

    def get_converter(self, ext: str) -> Converter | None:
        for c in self._converters:
            if c.can_convert(ext):
                return c
        return None
