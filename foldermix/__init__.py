"""foldermix - pack a folder into a single LLM-friendly context file."""

import re
from importlib.metadata import version as package_version
from pathlib import Path


def _read_version_from_pyproject() -> str:
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    text = pyproject.read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"([^"]+)"\s*$', text, re.MULTILINE)
    if not match:
        raise RuntimeError("Could not find project version in pyproject.toml")
    return match.group(1)


_PYPROJECT = Path(__file__).resolve().parents[1] / "pyproject.toml"
if _PYPROJECT.exists():
    # Source checkout: trust pyproject as the single source of truth.
    __version__ = _read_version_from_pyproject()
else:
    __version__ = package_version("foldermix")
