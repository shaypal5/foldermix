from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from foldermix import utils


def test_sha256_file(tmp_path: Path) -> None:
    path = tmp_path / "data.txt"
    # Write bytes directly so LF/CRLF translation cannot affect hash expectations.
    path.write_bytes(b"hello\n")
    expected = hashlib.sha256(b"hello\n").hexdigest()
    assert utils.sha256_file(path) == expected


def test_utcnow_iso_is_timezone_aware() -> None:
    now = utils.utcnow_iso()
    assert now.endswith("+00:00")
    parsed = datetime.fromisoformat(now)
    assert parsed.tzinfo is not None


def test_mtime_iso_uses_file_mtime(tmp_path: Path) -> None:
    path = tmp_path / "a.txt"
    path.write_text("x", encoding="utf-8")
    fixed = 1704067200
    path.touch()
    path.chmod(0o644)
    path.stat()
    import os

    os.utime(path, (fixed, fixed))
    assert utils.mtime_iso(path) == "2024-01-01T00:00:00+00:00"


def test_detect_encoding_uses_charset_normalizer(monkeypatch, tmp_path: Path) -> None:
    path = tmp_path / "enc.txt"
    path.write_bytes(b"abc")

    class _Result:
        @staticmethod
        def best():
            return SimpleNamespace(encoding="utf-16")

    fake_module = SimpleNamespace(from_path=lambda _: _Result())
    monkeypatch.setitem(__import__("sys").modules, "charset_normalizer", fake_module)
    monkeypatch.setitem(__import__("sys").modules, "chardet", None)

    assert utils.detect_encoding(path) == "utf-16"


def test_detect_encoding_uses_chardet_when_charset_unavailable(monkeypatch, tmp_path: Path) -> None:
    path = tmp_path / "enc.txt"
    path.write_bytes(b"abc")
    fake_chardet = SimpleNamespace(detect=lambda _: {"encoding": "latin-1"})
    monkeypatch.setitem(__import__("sys").modules, "charset_normalizer", None)
    monkeypatch.setitem(__import__("sys").modules, "chardet", fake_chardet)
    assert utils.detect_encoding(path) == "latin-1"


def test_detect_encoding_defaults_to_utf8(monkeypatch, tmp_path: Path) -> None:
    path = tmp_path / "enc.txt"
    path.write_bytes(b"abc")
    monkeypatch.setitem(__import__("sys").modules, "charset_normalizer", None)
    monkeypatch.setitem(__import__("sys").modules, "chardet", None)
    assert utils.detect_encoding(path) == "utf-8"


def test_read_text_with_fallback_primary_encoding(tmp_path: Path) -> None:
    path = tmp_path / "ok.txt"
    path.write_text("hello", encoding="utf-8")
    text, enc = utils.read_text_with_fallback(path, "utf-8")
    assert text == "hello"
    assert enc == "utf-8"


def test_read_text_with_fallback_detected_encoding(monkeypatch, tmp_path: Path) -> None:
    path = tmp_path / "latin1.txt"
    path.write_text("cafe\xe9", encoding="latin-1")
    monkeypatch.setattr(utils, "detect_encoding", lambda _: "latin-1")
    text, enc = utils.read_text_with_fallback(path, "utf-8")
    assert text == "cafe\xe9"
    assert enc == "latin-1"


def test_read_text_with_fallback_replacement(monkeypatch, tmp_path: Path) -> None:
    path = tmp_path / "bad.txt"
    path.write_bytes(b"\xff")
    monkeypatch.setattr(utils, "detect_encoding", lambda _: "no-such-encoding")
    text, enc = utils.read_text_with_fallback(path, "utf-8")
    assert enc == "utf-8 (with replacement)"
    assert "\ufffd" in text


def test_apply_redaction_modes() -> None:
    text = "mail me at test@example.com or call +1 (555) 123-4567"
    assert "[REDACTED_EMAIL]" in utils.apply_redaction(text, "emails")
    assert "[REDACTED_PHONE]" not in utils.apply_redaction(text, "emails")
    assert "[REDACTED_PHONE]" in utils.apply_redaction(text, "phones")
    assert "[REDACTED_EMAIL]" not in utils.apply_redaction(text, "phones")
    both = utils.apply_redaction(text, "all")
    assert "[REDACTED_EMAIL]" in both
    assert "[REDACTED_PHONE]" in both
    assert utils.apply_redaction(text, "none") == text


def test_apply_redaction_with_trace_counts_by_category() -> None:
    text = "a@example.com and b@example.com and +1 (555) 123-4567"
    redacted, counts = utils.apply_redaction_with_trace(text, "all")
    assert redacted.count("[REDACTED_EMAIL]") == 2
    assert redacted.count("[REDACTED_PHONE]") == 1
    assert counts == {"emails": 2, "phones": 1}


def test_apply_redaction_with_trace_returns_empty_counts_when_no_match() -> None:
    redacted, counts = utils.apply_redaction_with_trace("no sensitive tokens", "all")
    assert redacted == "no sensitive tokens"
    assert counts == {}


def test_strip_yaml_frontmatter_only_at_start() -> None:
    text = "---\ntitle: test\n---\nbody\n"
    assert utils.strip_yaml_frontmatter(text) == "body\n"

    non_frontmatter = "body\n---\nnot frontmatter\n---\n"
    assert utils.strip_yaml_frontmatter(non_frontmatter) == non_frontmatter
