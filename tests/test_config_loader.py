from __future__ import annotations

from pathlib import Path

import pytest

from foldermix import config_loader
from foldermix.config_loader import ConfigLoadError, load_command_config


def test_load_command_config_from_tool_section(tmp_path: Path) -> None:
    config_path = tmp_path / "foldermix.toml"
    config_path.write_text(
        "\n".join(
            [
                "[tool.foldermix.pack]",
                'format = "xml"',
                "workers = 2",
                'include_ext = [".py", ".md"]',
                "include_toc = false",
                "pdf_ocr = true",
                "pdf_ocr_strict = false",
                "",
            ]
        ),
        encoding="utf-8",
    )

    values, used_path = load_command_config("pack", root=tmp_path, config_path=config_path)

    assert used_path == config_path
    assert values["format"] == "xml"
    assert values["workers"] == 2
    assert values["include_ext"] == [".py", ".md"]
    assert values["include_toc"] is False
    assert values["pdf_ocr"] is True
    assert values["pdf_ocr_strict"] is False


def test_load_command_config_discovers_parent_file(tmp_path: Path) -> None:
    config_path = tmp_path / "foldermix.toml"
    config_path.write_text(
        "\n".join(
            [
                "[list]",
                "hidden = true",
                "",
            ]
        ),
        encoding="utf-8",
    )
    nested = tmp_path / "a" / "b"
    nested.mkdir(parents=True)

    values, used_path = load_command_config("list", root=nested, config_path=None)

    assert used_path == config_path
    assert values["hidden"] is True


def test_load_command_config_rejects_invalid_types(tmp_path: Path) -> None:
    config_path = tmp_path / "foldermix.toml"
    config_path.write_text(
        "\n".join(
            [
                "[pack]",
                'workers = "fast"',
                "",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ConfigLoadError) as exc:
        load_command_config("pack", root=tmp_path, config_path=config_path)

    message = str(exc.value)
    assert "Invalid config at" in message
    assert "workers: expected an integer" in message


def test_load_command_config_rejects_unknown_key(tmp_path: Path) -> None:
    config_path = tmp_path / "foldermix.toml"
    config_path.write_text(
        "\n".join(
            [
                "[stats]",
                "unknown = 1",
                "",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ConfigLoadError) as exc:
        load_command_config("stats", root=tmp_path, config_path=config_path)

    assert "unknown key" in str(exc.value)


def test_load_command_config_rejects_known_but_invalid_command_key(tmp_path: Path) -> None:
    config_path = tmp_path / "foldermix.toml"
    config_path.write_text(
        "\n".join(
            [
                "[stats]",
                "workers = 2",
                "",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ConfigLoadError) as exc:
        load_command_config("stats", root=tmp_path, config_path=config_path)

    assert "is not valid for 'stats' command" in str(exc.value)


def test_load_command_config_accepts_csv_list_values(tmp_path: Path) -> None:
    config_path = tmp_path / "foldermix.toml"
    config_path.write_text(
        "\n".join(
            [
                "[pack]",
                'include_ext = ".py, .md,  .txt "',
                "",
            ]
        ),
        encoding="utf-8",
    )

    values, used_path = load_command_config("pack", root=tmp_path, config_path=config_path)

    assert used_path == config_path
    assert values["include_ext"] == [".py", ".md", ".txt"]


def test_load_command_config_rejects_invalid_list_shape(tmp_path: Path) -> None:
    config_path = tmp_path / "foldermix.toml"
    config_path.write_text(
        "\n".join(
            [
                "[pack]",
                'include_ext = [".py", 1]',
                "",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ConfigLoadError) as exc:
        load_command_config("pack", root=tmp_path, config_path=config_path)

    assert "expected a list of strings" in str(exc.value)


def test_load_command_config_rejects_literal_non_string(tmp_path: Path) -> None:
    config_path = tmp_path / "foldermix.toml"
    config_path.write_text(
        "\n".join(
            [
                "[pack]",
                "format = 123",
                "",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ConfigLoadError) as exc:
        load_command_config("pack", root=tmp_path, config_path=config_path)

    assert "format: expected a string" in str(exc.value)


def test_load_command_config_rejects_invalid_literal_choice(tmp_path: Path) -> None:
    config_path = tmp_path / "foldermix.toml"
    config_path.write_text(
        "\n".join(
            [
                "[pack]",
                'format = "bad"',
                "",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ConfigLoadError) as exc:
        load_command_config("pack", root=tmp_path, config_path=config_path)

    assert "expected one of" in str(exc.value)


def test_load_command_config_rejects_invalid_bool_and_string_types(tmp_path: Path) -> None:
    config_path = tmp_path / "foldermix.toml"
    config_path.write_text(
        "\n".join(
            [
                "[pack]",
                'hidden = "yes"',
                'pdf_ocr = "yes"',
                "encoding = 1",
                "",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ConfigLoadError) as exc:
        load_command_config("pack", root=tmp_path, config_path=config_path)

    message = str(exc.value)
    assert "hidden: expected a boolean" in message
    assert "pdf_ocr: expected a boolean" in message
    assert "encoding: expected a string" in message


def test_load_command_config_coerces_path_keys(tmp_path: Path) -> None:
    config_path = tmp_path / "foldermix.toml"
    config_path.write_text(
        "\n".join(
            [
                "[pack]",
                'out = "bundle.xml"',
                "",
            ]
        ),
        encoding="utf-8",
    )

    values, _ = load_command_config("pack", root=tmp_path, config_path=config_path)
    assert values["out"] == Path("bundle.xml")


def test_load_command_config_rejects_invalid_path_type(tmp_path: Path) -> None:
    config_path = tmp_path / "foldermix.toml"
    config_path.write_text(
        "\n".join(
            [
                "[pack]",
                "report = 123",
                "",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ConfigLoadError) as exc:
        load_command_config("pack", root=tmp_path, config_path=config_path)

    assert "report: expected a filesystem path string" in str(exc.value)


def test_load_command_config_supports_flat_root_without_sections(tmp_path: Path) -> None:
    config_path = tmp_path / "foldermix.toml"
    config_path.write_text(
        "\n".join(
            [
                'format = "xml"',
                "workers = 2",
                "",
            ]
        ),
        encoding="utf-8",
    )

    values, _ = load_command_config("pack", root=tmp_path, config_path=config_path)
    assert values["format"] == "xml"
    assert values["workers"] == 2


def test_load_command_config_rejects_unknown_top_level_keys_in_section_mode(tmp_path: Path) -> None:
    config_path = tmp_path / "foldermix.toml"
    config_path.write_text(
        "\n".join(
            [
                "extra = 1",
                "",
                "[pack]",
                'format = "md"',
                "",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ConfigLoadError) as exc:
        load_command_config("pack", root=tmp_path, config_path=config_path)

    assert "unknown top-level keys" in str(exc.value)


def test_load_command_config_rejects_non_table_common_section(tmp_path: Path) -> None:
    config_path = tmp_path / "foldermix.toml"
    config_path.write_text(
        "\n".join(
            [
                "common = 1",
                "",
                "[pack]",
                'format = "md"',
                "",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ConfigLoadError) as exc:
        load_command_config("pack", root=tmp_path, config_path=config_path)

    assert "config.common must be a TOML table" in str(exc.value)


def test_load_command_config_merges_common_section_and_command_override(tmp_path: Path) -> None:
    config_path = tmp_path / "foldermix.toml"
    config_path.write_text(
        "\n".join(
            [
                "[common]",
                "hidden = true",
                "",
                "[pack]",
                "hidden = false",
                "workers = 2",
                "",
            ]
        ),
        encoding="utf-8",
    )

    values, _ = load_command_config("pack", root=tmp_path, config_path=config_path)
    assert values["hidden"] is False
    assert values["workers"] == 2


def test_load_command_config_uses_common_section_when_command_section_missing(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "foldermix.toml"
    config_path.write_text(
        "\n".join(
            [
                "[common]",
                "hidden = true",
                "",
            ]
        ),
        encoding="utf-8",
    )

    values, _ = load_command_config("list", root=tmp_path, config_path=config_path)
    assert values["hidden"] is True


def test_load_command_config_rejects_non_table_command_section(tmp_path: Path) -> None:
    config_path = tmp_path / "foldermix.toml"
    config_path.write_text(
        "\n".join(
            [
                "list = 1",
                "",
                "[common]",
                "hidden = true",
                "",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ConfigLoadError) as exc:
        load_command_config("list", root=tmp_path, config_path=config_path)

    assert "config.list must be a TOML table" in str(exc.value)


def test_load_command_config_supports_top_level_foldermix_table(tmp_path: Path) -> None:
    config_path = tmp_path / "foldermix.toml"
    config_path.write_text(
        "\n".join(
            [
                "[foldermix.pack]",
                'format = "jsonl"',
                "",
            ]
        ),
        encoding="utf-8",
    )

    values, _ = load_command_config("pack", root=tmp_path, config_path=config_path)
    assert values["format"] == "jsonl"


def test_load_command_config_rejects_non_table_tool_foldermix(tmp_path: Path) -> None:
    config_path = tmp_path / "foldermix.toml"
    config_path.write_text(
        "\n".join(
            [
                "[tool]",
                "foldermix = 1",
                "",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ConfigLoadError) as exc:
        load_command_config("pack", root=tmp_path, config_path=config_path)

    assert "tool.foldermix must be a TOML table" in str(exc.value)


def test_load_command_config_rejects_non_table_top_level_foldermix(tmp_path: Path) -> None:
    config_path = tmp_path / "foldermix.toml"
    config_path.write_text("foldermix = 1\n", encoding="utf-8")

    with pytest.raises(ConfigLoadError) as exc:
        load_command_config("pack", root=tmp_path, config_path=config_path)

    assert "foldermix must be a TOML table" in str(exc.value)


def test_discover_config_path_handles_file_start_and_missing_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_path = tmp_path / "foldermix.toml"
    config_path.write_text("", encoding="utf-8")
    nested_dir = tmp_path / "nested"
    nested_dir.mkdir()
    target_file = nested_dir / "target.txt"
    target_file.write_text("x", encoding="utf-8")

    assert config_loader.discover_config_path(target_file) == config_path

    monkeypatch.chdir(tmp_path)
    assert config_loader.discover_config_path(tmp_path / "does-not-exist") == config_path


def test_load_command_config_rejects_unsupported_command(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        load_command_config("unknown", root=tmp_path, config_path=None)


def test_load_command_config_rejects_missing_explicit_path(tmp_path: Path) -> None:
    config_path = tmp_path / "missing.toml"
    with pytest.raises(ConfigLoadError) as exc:
        load_command_config("pack", root=tmp_path, config_path=config_path)

    assert "config file does not exist" in str(exc.value)


def test_load_command_config_rejects_invalid_toml(tmp_path: Path) -> None:
    config_path = tmp_path / "foldermix.toml"
    config_path.write_text("[pack\n", encoding="utf-8")

    with pytest.raises(ConfigLoadError) as exc:
        load_command_config("pack", root=tmp_path, config_path=config_path)

    assert "invalid TOML" in str(exc.value)


def test_load_command_config_wraps_os_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_path = tmp_path / "foldermix.toml"
    config_path.write_text("[pack]\n", encoding="utf-8")

    def fail_read_text(self: Path, *, encoding: str) -> str:
        raise OSError("boom")

    monkeypatch.setattr(Path, "read_text", fail_read_text)

    with pytest.raises(ConfigLoadError) as exc:
        load_command_config("pack", root=tmp_path, config_path=config_path)

    assert "could not read config" in str(exc.value)


def test_load_command_config_rejects_non_table_after_parse(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_path = tmp_path / "foldermix.toml"
    config_path.write_text("[pack]\n", encoding="utf-8")

    monkeypatch.setattr(config_loader.tomllib, "loads", lambda _: ["not-a-table"])

    with pytest.raises(ConfigLoadError) as exc:
        load_command_config("pack", root=tmp_path, config_path=config_path)

    assert "config root must be a TOML table" in str(exc.value)


def test_private_coercion_helpers_cover_optional_and_unsupported_keys() -> None:
    errors: list[str] = []
    where = "config.pack"

    assert config_loader._coerce_value("max_total_bytes", None, errors, where=where) is None
    assert config_loader._coerce_value("report", None, errors, where=where) is None
    assert config_loader._coerce_value("out", "bundle.md", errors, where=where) == Path("bundle.md")
    assert config_loader._coerce_value("unsupported", "x", errors, where=where) == "x"

    assert errors == [f"{where}.unsupported: unsupported key"]
