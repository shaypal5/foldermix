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
                "[pack]",
                'format = "xml"',
                "",
            ]
        ),
        encoding="utf-8",
    )
    nested = tmp_path / "a" / "b"
    nested.mkdir(parents=True)

    values, used_path = load_command_config("pack", root=nested, config_path=None)

    assert used_path == config_path
    assert values["format"] == "xml"


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
                'drop_line_containing = "generated marker, telemetry: trace id"',
                "min_line_length = 7",
                "",
            ]
        ),
        encoding="utf-8",
    )

    values, used_path = load_command_config("pack", root=tmp_path, config_path=config_path)

    assert used_path == config_path
    assert values["include_ext"] == [".py", ".md", ".txt"]
    assert values["drop_line_containing"] == ["generated marker", "telemetry: trace id"]
    assert values["min_line_length"] == 7


def test_load_command_config_accepts_drop_line_containing_list_literals(tmp_path: Path) -> None:
    config_path = tmp_path / "foldermix.toml"
    config_path.write_text(
        "\n".join(
            [
                "[pack]",
                'drop_line_containing = ["do not edit, generated", "multi word marker"]',
                "",
            ]
        ),
        encoding="utf-8",
    )

    values, used_path = load_command_config("pack", root=tmp_path, config_path=config_path)

    assert used_path == config_path
    assert values["drop_line_containing"] == ["do not edit, generated", "multi word marker"]


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


def test_load_command_config_rejects_negative_min_line_length(tmp_path: Path) -> None:
    config_path = tmp_path / "foldermix.toml"
    config_path.write_text(
        "\n".join(
            [
                "[pack]",
                "min_line_length = -1",
                "",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ConfigLoadError) as exc:
        load_command_config("pack", root=tmp_path, config_path=config_path)

    assert "min_line_length: expected a non-negative integer" in str(exc.value)


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

    values, _ = load_command_config("stats", root=tmp_path, config_path=config_path)
    assert values["hidden"] is True


def test_load_command_config_rejects_non_table_command_section(tmp_path: Path) -> None:
    config_path = tmp_path / "foldermix.toml"
    config_path.write_text(
        "\n".join(
            [
                "pack = 1",
                "",
                "[common]",
                "hidden = true",
                "",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ConfigLoadError) as exc:
        load_command_config("pack", root=tmp_path, config_path=config_path)

    assert "config.pack must be a TOML table" in str(exc.value)


def test_load_command_config_rejects_list_section_as_unknown_top_level_key(tmp_path: Path) -> None:
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

    with pytest.raises(ConfigLoadError) as exc:
        load_command_config("pack", root=tmp_path, config_path=config_path)

    assert "config: unknown key 'list'" in str(exc.value)


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


def test_load_command_config_accepts_ipynb_include_outputs(tmp_path: Path) -> None:
    config_path = tmp_path / "foldermix.toml"
    config_path.write_text("[pack]\nipynb_include_outputs = true\n", encoding="utf-8")

    values, used_path = load_command_config(
        "pack",
        root=tmp_path,
        config_path=config_path,
    )

    assert values["ipynb_include_outputs"] is True
    assert used_path == config_path


def test_load_command_config_accepts_policy_rules_tables(tmp_path: Path) -> None:
    config_path = tmp_path / "foldermix.toml"
    config_path.write_text(
        "\n".join(
            [
                "[pack]",
                "",
                "[[pack.policy_rules]]",
                'rule_id = "scan-large"',
                'description = "Flag large files"',
                'stage = "scan"',
                "max_size_bytes = 100",
                'severity = "high"',
                'action = "deny"',
                "",
            ]
        ),
        encoding="utf-8",
    )

    values, _ = load_command_config("pack", root=tmp_path, config_path=config_path)
    assert values["policy_rules"] == [
        {
            "rule_id": "scan-large",
            "description": "Flag large files",
            "stage": "scan",
            "max_size_bytes": 100,
            "severity": "high",
            "action": "deny",
        }
    ]


def test_load_command_config_accepts_policy_pack_string(tmp_path: Path) -> None:
    config_path = tmp_path / "foldermix.toml"
    config_path.write_text(
        "\n".join(
            [
                "[pack]",
                'policy_pack = "strict-privacy"',
                "",
            ]
        ),
        encoding="utf-8",
    )

    values, _ = load_command_config("pack", root=tmp_path, config_path=config_path)
    assert values["policy_pack"] == "strict-privacy"


def test_load_command_config_accepts_policy_enforcement_fields(tmp_path: Path) -> None:
    config_path = tmp_path / "foldermix.toml"
    config_path.write_text(
        "\n".join(
            [
                "[pack]",
                "fail_on_policy_violation = true",
                'policy_fail_level = "high"',
                "",
            ]
        ),
        encoding="utf-8",
    )

    values, _ = load_command_config("pack", root=tmp_path, config_path=config_path)
    assert values["fail_on_policy_violation"] is True
    assert values["policy_fail_level"] == "high"


def test_load_command_config_accepts_policy_dry_run_fields(tmp_path: Path) -> None:
    config_path = tmp_path / "foldermix.toml"
    config_path.write_text(
        "\n".join(
            [
                "[pack]",
                "policy_dry_run = true",
                'policy_output = "json"',
                "",
            ]
        ),
        encoding="utf-8",
    )

    values, _ = load_command_config("pack", root=tmp_path, config_path=config_path)
    assert values["policy_dry_run"] is True
    assert values["policy_output"] == "json"


def test_load_command_config_rejects_invalid_policy_fail_level(tmp_path: Path) -> None:
    config_path = tmp_path / "foldermix.toml"
    config_path.write_text(
        "\n".join(
            [
                "[pack]",
                'policy_fail_level = "blocker"',
                "",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ConfigLoadError) as exc:
        load_command_config("pack", root=tmp_path, config_path=config_path)

    assert "policy_fail_level: expected one of 'critical, high, low, medium'" in str(exc.value)


def test_load_command_config_rejects_invalid_policy_output(tmp_path: Path) -> None:
    config_path = tmp_path / "foldermix.toml"
    config_path.write_text(
        "\n".join(
            [
                "[pack]",
                'policy_output = "yaml"',
                "",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ConfigLoadError) as exc:
        load_command_config("pack", root=tmp_path, config_path=config_path)

    assert "policy_output: expected one of 'json, text'" in str(exc.value)


def test_load_command_config_rejects_non_bool_fail_on_policy_violation(tmp_path: Path) -> None:
    config_path = tmp_path / "foldermix.toml"
    config_path.write_text(
        "\n".join(
            [
                "[pack]",
                'fail_on_policy_violation = "yes"',
                "",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ConfigLoadError) as exc:
        load_command_config("pack", root=tmp_path, config_path=config_path)

    assert "fail_on_policy_violation: expected a boolean" in str(exc.value)


def test_load_command_config_rejects_non_bool_policy_dry_run(tmp_path: Path) -> None:
    config_path = tmp_path / "foldermix.toml"
    config_path.write_text(
        "\n".join(
            [
                "[pack]",
                'policy_dry_run = "yes"',
                "",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ConfigLoadError) as exc:
        load_command_config("pack", root=tmp_path, config_path=config_path)

    assert "policy_dry_run: expected a boolean" in str(exc.value)


def test_load_command_config_rejects_policy_rule_without_matchers(tmp_path: Path) -> None:
    config_path = tmp_path / "foldermix.toml"
    config_path.write_text(
        "\n".join(
            [
                "[pack]",
                "",
                "[[pack.policy_rules]]",
                'rule_id = "bad-rule"',
                'description = "missing matcher"',
                "",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ConfigLoadError) as exc:
        load_command_config("pack", root=tmp_path, config_path=config_path)

    assert "expected at least one matcher key" in str(exc.value)


def test_load_command_config_rejects_policy_rules_when_not_a_list(tmp_path: Path) -> None:
    config_path = tmp_path / "foldermix.toml"
    config_path.write_text(
        "\n".join(
            [
                "[pack]",
                "policy_rules = 1",
                "",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ConfigLoadError) as exc:
        load_command_config("pack", root=tmp_path, config_path=config_path)

    assert "expected a list of policy rule tables" in str(exc.value)


def test_load_command_config_rejects_non_string_policy_pack(tmp_path: Path) -> None:
    config_path = tmp_path / "foldermix.toml"
    config_path.write_text(
        "\n".join(
            [
                "[pack]",
                "policy_pack = 1",
                "",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ConfigLoadError) as exc:
        load_command_config("pack", root=tmp_path, config_path=config_path)

    assert "policy_pack: expected a non-empty string" in str(exc.value)


def test_load_command_config_rejects_policy_rule_entry_when_not_table(tmp_path: Path) -> None:
    config_path = tmp_path / "foldermix.toml"
    config_path.write_text(
        "\n".join(
            [
                "[pack]",
                "policy_rules = [1]",
                "",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ConfigLoadError) as exc:
        load_command_config("pack", root=tmp_path, config_path=config_path)

    assert "expected a TOML table" in str(exc.value)


def test_load_command_config_rejects_policy_rule_invalid_fields_and_literals(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "foldermix.toml"
    config_path.write_text(
        "\n".join(
            [
                "[pack]",
                "",
                "[[pack.policy_rules]]",
                "rule_id = ''",
                "description = ''",
                "ext_in = 1",
                "max_size_bytes = -1",
                "severity = 1",
                "action = 'block'",
                "unknown = true",
                "",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ConfigLoadError) as exc:
        load_command_config("pack", root=tmp_path, config_path=config_path)

    message = str(exc.value)
    assert "unknown key(s): unknown" in message
    assert "rule_id: expected a non-empty string" in message
    assert "description: expected a non-empty string" in message
    assert "ext_in: expected a list of strings" in message
    assert "max_size_bytes: expected a non-negative integer" in message
    assert "severity: expected a string" in message
    assert "action: expected one of deny, warn, got 'block'" in message


def test_extract_config_root_ignores_tool_table_without_foldermix(tmp_path: Path) -> None:
    parsed = {
        "tool": {"name": "demo"},
        "pack": {"workers": 2},
    }
    root = config_loader._extract_config_root(parsed, path=tmp_path / "foldermix.toml")
    assert root == parsed
