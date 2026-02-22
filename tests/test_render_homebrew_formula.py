from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_renderer_module():
    script = Path(__file__).resolve().parents[1] / "scripts" / "render_homebrew_formula.py"
    spec = importlib.util.spec_from_file_location("render_homebrew_formula", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[assignment]
    return module


def test_normalize_name() -> None:
    module = _load_renderer_module()
    assert module._normalize_name("Pydantic_Core") == "pydantic-core"
    assert module._normalize_name("typing.extensions") == "typing-extensions"


def test_render_formula_includes_resources_and_rust_when_needed() -> None:
    module = _load_renderer_module()
    formula = module._render_formula(
        package_version="0.1.1",
        package_url="https://files.pythonhosted.org/foldermix-0.1.1.tar.gz",
        package_sha256="abc123",
        resources=[
            (
                "annotated-types",
                "https://files.pythonhosted.org/annotated-types-0.7.0.tar.gz",
                "r1",
            ),
            ("pydantic-core", "https://files.pythonhosted.org/pydantic-core-2.41.5.tar.gz", "r2"),
        ],
        python_formula="python@3.12",
        needs_rust=True,
    )

    assert 'depends_on "python@3.12"' in formula
    assert 'depends_on "rust" => :build' in formula
    assert 'resource "annotated-types" do' in formula
    assert 'resource "pydantic-core" do' in formula
    assert 'assert_match "foldermix #{version}"' in formula
