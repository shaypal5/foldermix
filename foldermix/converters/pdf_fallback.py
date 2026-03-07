from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

from .base import ConversionResult

_RTL_RANGES = (
    ("\u0590", "\u05ff"),  # Hebrew
    ("\u0600", "\u06ff"),  # Arabic
    ("\u0750", "\u077f"),  # Arabic Supplement
    ("\u08a0", "\u08ff"),  # Arabic Extended-A
)
_BIDI_CONTROL_CHARS = {
    ord(ch): None
    for ch in "\u200e\u200f\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069\ufeff"
}


class PdfFallbackConverter:
    def can_convert(self, ext: str) -> bool:
        try:
            import pypdf  # noqa: F401

            return ext.lower() == ".pdf"
        except ImportError:
            return False

    @staticmethod
    def _close_if_possible(obj: Any) -> None:
        close = getattr(obj, "close", None)
        if callable(close):
            close()

    @staticmethod
    def _load_ocr_dependencies() -> tuple[Any | None, Any | None, list[str]]:
        missing: list[str] = []
        pdfium = None
        rapid_ocr_cls = None
        try:
            import pypdfium2 as pdfium  # type: ignore[assignment]
        except ImportError:
            missing.append("pypdfium2")
        try:
            from rapidocr_onnxruntime import RapidOCR as rapid_ocr_cls  # type: ignore[assignment]
        except ImportError:
            missing.append("rapidocr-onnxruntime")
        return pdfium, rapid_ocr_cls, missing

    @staticmethod
    def _extract_ocr_text(ocr_result: Any) -> str:
        entries = ocr_result
        if isinstance(entries, tuple) and entries:
            entries = entries[0]

        if entries is None:
            return ""
        if isinstance(entries, str):
            return entries.strip()

        texts: list[str] = []
        if isinstance(entries, list):
            for entry in entries:
                if (
                    isinstance(entry, (list, tuple))
                    and len(entry) > 1
                    and isinstance(entry[1], str)
                ):
                    text = entry[1].strip()
                    if text:
                        texts.append(text)
                elif isinstance(entry, dict):
                    text = entry.get("text")
                    if isinstance(text, str):
                        text = text.strip()
                        if text:
                            texts.append(text)
        return "\n".join(texts)

    @staticmethod
    def _contains_rtl_text(text: str) -> bool:
        return any(start <= char <= end for char in text for start, end in _RTL_RANGES)

    @staticmethod
    def _clean_poppler_page_text(text: str) -> str:
        lines = [line.translate(_BIDI_CONTROL_CHARS).rstrip() for line in text.splitlines()]
        while lines and not lines[0].strip():
            lines.pop(0)
        while lines and not lines[-1].strip():
            lines.pop()
        return "\n".join(lines)

    @classmethod
    def _extract_poppler_pages(cls, path: Path) -> list[str] | None:
        if shutil.which("pdftotext") is None:
            return None

        try:
            completed = subprocess.run(
                ["pdftotext", "-layout", "-enc", "UTF-8", str(path), "-"],
                check=True,
                capture_output=True,
                text=True,
            )
        except (OSError, subprocess.CalledProcessError):
            return None

        raw_pages = completed.stdout.split("\f")
        if raw_pages and not raw_pages[-1].strip():
            raw_pages.pop()
        return [cls._clean_poppler_page_text(page) for page in raw_pages]

    def _render_pdf_page(
        self, path: Path, page_index: int, pdfium: Any, *, pdf_doc: Any | None = None
    ) -> Any:
        doc = pdf_doc if pdf_doc is not None else pdfium.PdfDocument(str(path))
        close_doc = pdf_doc is None
        page = None
        try:
            page = doc[page_index]
            rendered = page.render(scale=2)
            if hasattr(rendered, "to_numpy"):
                return rendered.to_numpy()
            if hasattr(rendered, "to_pil"):
                return rendered.to_pil()
            return rendered
        finally:
            if page is not None:
                self._close_if_possible(page)
            if close_doc:
                self._close_if_possible(doc)

    def _ocr_page(
        self,
        path: Path,
        page_index: int,
        *,
        pdfium: Any,
        ocr_engine: Any,
        pdf_doc: Any | None = None,
    ) -> str:
        image = self._render_pdf_page(path, page_index, pdfium, pdf_doc=pdf_doc)
        ocr_result = ocr_engine(image)
        return self._extract_ocr_text(ocr_result)

    def convert(
        self,
        path: Path,
        encoding: str = "utf-8",
        *,
        enable_ocr: bool = False,
        ocr_strict: bool = False,
    ) -> ConversionResult:
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        extracted_pages = [(page.extract_text() or "") for page in reader.pages]
        converter_name = "pypdf"
        if any(self._contains_rtl_text(text) for text in extracted_pages):
            poppler_pages = self._extract_poppler_pages(path)
            if poppler_pages and len(poppler_pages) == len(extracted_pages):
                extracted_pages = poppler_pages
                converter_name = "pdftotext"

        warnings: list[str] = []
        ocr_used = False
        ocr_unavailable_reason: str | None = None
        ocr_setup_attempted = False
        pdfium = None
        ocr_engine = None
        pdf_doc = None

        def unresolved_ocr(message: str) -> None:
            warnings.append(message)
            if ocr_strict:
                raise RuntimeError(message)

        pages = []
        try:
            for i, page in enumerate(reader.pages):
                text = extracted_pages[i]
                page_num = i + 1
                page_text = text
                if not text.strip():
                    if not enable_ocr:
                        unresolved_ocr(
                            f"Page {page_num} has no extractable text. OCR is disabled; use --pdf-ocr to attempt OCR."
                        )
                    elif ocr_unavailable_reason:
                        unresolved_ocr(
                            f"Page {page_num} has no extractable text and OCR is unavailable. {ocr_unavailable_reason}."
                        )
                    else:
                        if not ocr_setup_attempted:
                            ocr_setup_attempted = True
                            pdfium, rapid_ocr_cls, missing = self._load_ocr_dependencies()
                            if missing:
                                ocr_unavailable_reason = "OCR dependencies missing: " + ", ".join(
                                    missing
                                )
                            else:
                                try:
                                    ocr_engine = rapid_ocr_cls()
                                except Exception as exc:
                                    ocr_unavailable_reason = (
                                        f"OCR engine initialization failed: {exc}"
                                    )

                        if ocr_unavailable_reason:
                            unresolved_ocr(
                                f"Page {page_num} has no extractable text and OCR is unavailable. {ocr_unavailable_reason}."
                            )
                            pages.append(f"### Page {page_num}\n{page_text}")
                            continue

                        if pdf_doc is None:
                            pdf_doc = pdfium.PdfDocument(str(path))

                        try:
                            ocr_text = self._ocr_page(
                                path,
                                i,
                                pdfium=pdfium,
                                ocr_engine=ocr_engine,
                                pdf_doc=pdf_doc,
                            )
                        except Exception as exc:
                            unresolved_ocr(f"Page {page_num} OCR failed: {exc}")
                        else:
                            if ocr_text.strip():
                                page_text = ocr_text
                                ocr_used = True
                            else:
                                unresolved_ocr(
                                    f"Page {page_num} has no extractable text and OCR produced no text."
                                )

                pages.append(f"### Page {page_num}\n{page_text}")
        finally:
            if pdf_doc is not None:
                self._close_if_possible(pdf_doc)

        if ocr_used:
            converter_name = f"{converter_name}+rapidocr"
        return ConversionResult(
            content="\n\n".join(pages),
            warnings=warnings,
            converter_name=converter_name,
            original_mime="application/pdf",
        )
