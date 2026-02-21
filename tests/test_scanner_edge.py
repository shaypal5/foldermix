from __future__ import annotations

from pathlib import Path

from foldermix.config import PackConfig
from foldermix.scanner import is_sensitive, scan


def test_sensitive_files_are_skipped(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text("TOKEN=secret", encoding="utf-8")
    (tmp_path / "server.pem").write_text("key", encoding="utf-8")
    (tmp_path / "keep.txt").write_text("ok", encoding="utf-8")

    included, skipped = scan(PackConfig(root=tmp_path, hidden=True))
    included_paths = [r.relpath for r in included]
    skipped_map = {r.relpath: r.reason for r in skipped}

    assert included_paths == ["keep.txt"]
    assert skipped_map[".env"] == "sensitive"
    assert skipped_map["server.pem"] == "sensitive"


def test_scan_marks_unreadable_files(monkeypatch, tmp_path: Path) -> None:
    bad = tmp_path / "bad.txt"
    good = tmp_path / "good.txt"
    bad.write_text("bad", encoding="utf-8")
    good.write_text("good", encoding="utf-8")

    original_stat = Path.stat

    def fake_stat(self: Path, *args, **kwargs):
        if self.name == "bad.txt":
            raise OSError("cannot read")
        return original_stat(self, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", fake_stat)
    included, skipped = scan(PackConfig(root=tmp_path))

    assert [r.relpath for r in included] == ["good.txt"]
    skipped_map = {r.relpath: r.reason for r in skipped}
    assert skipped_map["bad.txt"] == "unreadable"


def test_is_sensitive_matches_patterns() -> None:
    assert is_sensitive(".env") is True
    assert is_sensitive("id_rsa") is True
    assert is_sensitive("cert.p12") is True
    assert is_sensitive("notes.txt") is False
