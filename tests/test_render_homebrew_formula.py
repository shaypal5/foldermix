from __future__ import annotations

import importlib.util
import io
import urllib.error
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
        needs_rust=True,
    )

    assert 'depends_on "python@3.12"' in formula
    assert 'depends_on "rust" => :build' in formula
    assert 'resource "annotated-types" do' in formula
    assert 'resource "pydantic-core" do' in formula
    assert 'assert_match "foldermix #{version}"' in formula


def test_fetch_retries_on_http_5xx_and_succeeds(monkeypatch) -> None:
    module = _load_renderer_module()
    calls = {"count": 0}
    sleeps: list[int] = []

    def fake_sleep(seconds: int) -> None:
        sleeps.append(seconds)

    class _Resp:
        def __enter__(self):
            return io.StringIO(
                '{"urls":[{"packagetype":"sdist","url":"https://files/a.tar.gz","digests":{"sha256":"abc"}}]}'
            )

        def __exit__(self, exc_type, exc, tb):
            return False

    def fake_urlopen(req, timeout=20):
        calls["count"] += 1
        if calls["count"] == 1:
            raise urllib.error.HTTPError(req.full_url, 503, "Service Unavailable", {}, None)
        return _Resp()

    monkeypatch.setattr(module.time, "sleep", fake_sleep)
    monkeypatch.setattr(module.urllib.request, "urlopen", fake_urlopen)

    url, sha = module._fetch_pypi_release_file("foldermix", "0.1.1", retries=2)
    assert url == "https://files/a.tar.gz"
    assert sha == "abc"
    assert sleeps == [3]


def test_fetch_http_500_failure_mentions_url(monkeypatch) -> None:
    module = _load_renderer_module()

    def fake_urlopen(req, timeout=20):
        raise urllib.error.HTTPError(req.full_url, 500, "Internal Server Error", {}, None)

    monkeypatch.setattr(module.urllib.request, "urlopen", fake_urlopen)

    expected_url = "https://pypi.org/pypi/pkg/9.9.9/json"
    try:
        module._fetch_pypi_release_file("pkg", "9.9.9", retries=1)
    except RuntimeError as exc:
        text = str(exc)
        assert expected_url in text
        assert "HTTP 500" in text
    else:
        raise AssertionError("Expected RuntimeError")
