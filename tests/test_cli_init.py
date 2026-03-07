from __future__ import annotations

import shlex
from fnmatch import fnmatch
from pathlib import Path

import pytest
from typer.testing import CliRunner

import foldermix.packer as packer_module
from foldermix.cli import app
from foldermix.init_profiles import available_profiles

try:  # Python 3.11+
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - exercised on py310 CI
    import tomli as tomllib


runner = CliRunner()
FIXTURE_DIR = Path(__file__).parent / "data" / "init_profiles"


def test_init_help_lists_available_profiles() -> None:
    result = runner.invoke(app, ["init", "--help"])
    assert result.exit_code == 0, result.output
    for profile in available_profiles():
        assert profile in result.output


@pytest.mark.parametrize(
    "profile",
    ["legal", "research", "support", "engineering-docs", "course-refresh"],
)
def test_init_writes_expected_profile_template(tmp_path: Path, profile: str) -> None:
    output_path = tmp_path / "foldermix.toml"

    result = runner.invoke(
        app,
        ["init", "--profile", profile, "--out", str(output_path)],
    )

    assert result.exit_code == 0, result.output
    expected = (FIXTURE_DIR / f"{profile}.toml").read_text(encoding="utf-8")
    assert output_path.read_text(encoding="utf-8") == expected

    parsed = tomllib.loads(expected)
    assert isinstance(parsed, dict)
    assert "pack" in parsed
    assert "stats" in parsed
    assert "list" not in parsed


def test_init_rejects_invalid_profile(tmp_path: Path) -> None:
    output_path = tmp_path / "foldermix.toml"
    result = runner.invoke(
        app,
        ["init", "--profile", "unknown", "--out", str(output_path)],
    )

    assert result.exit_code == 1
    assert "Invalid profile" in result.output
    assert "legal" in result.output
    assert "research" in result.output
    assert "support" in result.output
    assert "engineering-docs" in result.output
    assert "course-refresh" in result.output
    assert not output_path.exists()


def test_init_refuses_to_overwrite_without_force(tmp_path: Path) -> None:
    output_path = tmp_path / "foldermix.toml"
    output_path.write_text("sentinel\n", encoding="utf-8")

    result = runner.invoke(
        app,
        ["init", "--profile", "legal", "--out", str(output_path)],
    )

    assert result.exit_code == 1
    assert "Refusing to overwrite existing file" in result.output
    assert output_path.read_text(encoding="utf-8") == "sentinel\n"


def test_init_force_overwrites_existing_file(tmp_path: Path) -> None:
    output_path = tmp_path / "foldermix.toml"
    output_path.write_text("sentinel\n", encoding="utf-8")

    result = runner.invoke(
        app,
        ["init", "--profile", "legal", "--out", str(output_path), "--force"],
    )

    assert result.exit_code == 0, result.output
    assert "Wrote starter config to" in result.output
    assert output_path.read_text(encoding="utf-8") != "sentinel\n"


def test_init_success_message_shell_quotes_output_path() -> None:
    with runner.isolated_filesystem():
        output_path = Path("my profile config.toml")
        result = runner.invoke(
            app,
            ["init", "--profile", "legal", "--out", str(output_path)],
        )

        assert result.exit_code == 0, result.output
        assert "Run:" in result.output
        expected_tail = f"foldermix pack . --config {shlex.quote(str(output_path))}"
        assert expected_tail in result.output


def test_init_reports_write_failure(monkeypatch, tmp_path: Path) -> None:
    output_path = tmp_path / "foldermix.toml"

    def fail_write_text(self: Path, *_args, **_kwargs) -> int:
        raise OSError("disk full")

    monkeypatch.setattr(Path, "write_text", fail_write_text)

    result = runner.invoke(
        app,
        ["init", "--profile", "legal", "--out", str(output_path)],
    )

    assert result.exit_code == 1
    assert "Failed to write config" in result.output
    assert "disk full" in result.output


@pytest.mark.parametrize(
    ("profile", "expected_redact"),
    [
        ("legal", "all"),
        ("research", "emails"),
        ("support", "all"),
        ("engineering-docs", "none"),
        ("course-refresh", "none"),
    ],
)
def test_init_generated_config_runs_with_pack(
    monkeypatch, tmp_path: Path, profile: str, expected_redact: str
) -> None:
    captured: dict[str, object] = {}

    def fake_pack(config) -> None:
        captured["config"] = config

    monkeypatch.setattr(packer_module, "pack", fake_pack)

    config_path = tmp_path / "foldermix.toml"
    init_result = runner.invoke(
        app,
        ["init", "--profile", profile, "--out", str(config_path)],
    )
    assert init_result.exit_code == 0, init_result.output

    input_dir = tmp_path / "input"
    input_dir.mkdir()
    (input_dir / "sample.txt").write_text("hello\n", encoding="utf-8")

    pack_result = runner.invoke(
        app,
        ["pack", str(input_dir), "--config", str(config_path)],
    )
    assert pack_result.exit_code == 0, pack_result.output

    config = captured["config"]
    assert config.redact == expected_redact


def test_course_refresh_profile_sets_exclusion_defaults(tmp_path: Path) -> None:
    output_path = tmp_path / "foldermix.toml"
    result = runner.invoke(
        app,
        ["init", "--profile", "course-refresh", "--out", str(output_path)],
    )

    assert result.exit_code == 0, result.output
    parsed = tomllib.loads(output_path.read_text(encoding="utf-8"))
    assert parsed["pack"]["exclude_dirs"] == [
        "Feedbacks",
        "feedbacks",
        "Responses",
        "responses",
        "Grades",
        "grades",
        "Rosters",
        "rosters",
        "Students",
        "students",
        "Submissions",
        "submissions",
    ]
    assert parsed["pack"]["exclude_glob"] == [
        "*[Gg]rade*",
        "*[Rr]oster*",
        "*[Rr]esponse*",
        "*[Ff]eedback*",
        "*[Ss]ubmission*",
        "*[Ss]tudent*",
    ]
    patterns = parsed["pack"]["exclude_glob"]
    assert any(fnmatch("Grades.xlsx", pattern) for pattern in patterns)
    assert any(fnmatch("nested/course/Feedback Notes.docx", pattern) for pattern in patterns)
