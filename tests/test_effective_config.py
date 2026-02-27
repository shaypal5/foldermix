from __future__ import annotations

from pathlib import Path

import pytest
from click.core import ParameterSource

from foldermix.effective_config import effective_config_payload, merge_config_layers


class FakeContext:
    def __init__(self, sources: dict[str, ParameterSource | None] | None = None) -> None:
        self._sources = sources or {}

    def get_parameter_source(self, param_name: str) -> ParameterSource | None:
        return self._sources.get(param_name, ParameterSource.DEFAULT)


@pytest.mark.parametrize(
    ("key", "default_value", "config_value", "cli_value"),
    [
        ("hidden", False, True, False),
        ("include_ext", None, [".py"], [".md"]),
        ("format", "md", "xml", "jsonl"),
    ],
)
def test_merge_config_layers_cli_values_override_config(
    key: str, default_value: object, config_value: object, cli_value: object
) -> None:
    merged = merge_config_layers(
        FakeContext({key: ParameterSource.COMMANDLINE}),
        defaults={key: cli_value},
        config_overrides={key: config_value},
    )

    assert merged.values[key] == cli_value
    assert merged.sources[key] == "cli"

    merged_no_cli = merge_config_layers(
        FakeContext(),
        defaults={key: default_value},
        config_overrides={key: config_value},
    )
    assert merged_no_cli.values[key] == config_value
    assert merged_no_cli.sources[key] == "config"


def test_merge_config_layers_adds_config_only_key() -> None:
    merged = merge_config_layers(
        FakeContext(),
        defaults={"format": "md"},
        config_overrides={"encoding": "latin-1"},
    )

    assert merged.values["format"] == "md"
    assert merged.sources["format"] == "default"
    assert merged.values["encoding"] == "latin-1"
    assert merged.sources["encoding"] == "config"


def test_merge_config_layers_honors_parameter_name_mapping() -> None:
    merged = merge_config_layers(
        FakeContext({"path": ParameterSource.COMMANDLINE}),
        defaults={"root": Path(".")},
        config_overrides={},
        key_to_param_name={"root": "path"},
    )

    assert merged.sources["root"] == "cli"


def test_effective_config_payload_is_deterministic_and_json_safe() -> None:
    merged = merge_config_layers(
        FakeContext({"path": ParameterSource.COMMANDLINE}),
        defaults={"format": "md", "root": Path("/tmp/project")},
        config_overrides={"include_ext": [".py", ".md"]},
        key_to_param_name={"root": "path"},
    )

    payload = effective_config_payload(
        command="pack", merged=merged, config_path=Path("/tmp/project/foldermix.toml")
    )

    assert payload["command"] == "pack"
    assert Path(payload["config_path"]) == Path("/tmp/project/foldermix.toml")
    assert list(payload["effective_config"]) == sorted(payload["effective_config"])
    assert Path(payload["effective_config"]["root"]["value"]) == Path("/tmp/project")
    assert payload["effective_config"]["root"]["source"] == "cli"
    assert payload["effective_config"]["include_ext"]["value"] == [".py", ".md"]


def test_effective_config_payload_converts_nested_dict_values() -> None:
    merged = merge_config_layers(
        FakeContext(),
        defaults={
            "nested": {
                1: Path("/tmp/a"),
                "items": [Path("/tmp/b"), {"k": Path("/tmp/c")}],
            }
        },
        config_overrides={},
    )

    payload = effective_config_payload(command="pack", merged=merged, config_path=None)
    nested = payload["effective_config"]["nested"]["value"]

    assert payload["config_path"] is None
    assert nested["1"] == "/tmp/a"
    assert nested["items"][0] == "/tmp/b"
    assert nested["items"][1]["k"] == "/tmp/c"
