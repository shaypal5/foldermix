from __future__ import annotations

import importlib.metadata as importlib_metadata
from pathlib import Path

import pytest

import foldermix


def test_read_version_from_pyproject_raises_when_version_missing(monkeypatch) -> None:
    def fake_read_text(self: Path, encoding: str = "utf-8") -> str:  # pragma: no cover
        return '[project]\nname = "foldermix"\n'

    monkeypatch.setattr(Path, "read_text", fake_read_text)

    with pytest.raises(RuntimeError, match="Could not find project version"):
        foldermix._read_version_from_pyproject()


def test_module_falls_back_to_package_metadata_when_pyproject_missing(
    monkeypatch, tmp_path: Path
) -> None:
    init_path = Path("foldermix/__init__.py").resolve()
    source = init_path.read_text(encoding="utf-8")

    fake_pkg_dir = tmp_path / "probe" / "foldermix"
    fake_pkg_dir.mkdir(parents=True)
    fake_init = fake_pkg_dir / "__init__.py"
    fake_init.write_text(source, encoding="utf-8")

    monkeypatch.setattr(importlib_metadata, "version", lambda _: "9.9.9-test")

    namespace = {
        "__name__": "foldermix_version_probe",
        "__file__": str(fake_init),
    }
    exec(compile(source, str(init_path), "exec"), namespace)

    assert namespace["__version__"] == "9.9.9-test"
