from __future__ import annotations

import runpy
import warnings

import typer.main


def test_module_entrypoint_invokes_typer_app(monkeypatch) -> None:
    calls = {"count": 0}

    def fake_call(self, *args, **kwargs):
        calls["count"] += 1
        return 0

    monkeypatch.setattr(typer.main.Typer, "__call__", fake_call)

    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message=r"'foldermix\.cli' found in sys\.modules .* unpredictable behaviour",
            category=RuntimeWarning,
        )
        runpy.run_module("foldermix.cli", run_name="__main__")

    assert calls["count"] == 1
