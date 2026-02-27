from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Protocol

from click.core import ParameterSource

ConfigSource = Literal["default", "config", "cli"]


class ParameterSourceContext(Protocol):
    def get_parameter_source(self, param_name: str) -> ParameterSource | None: ...


@dataclass(slots=True, frozen=True)
class EffectiveConfig:
    values: dict[str, Any]
    sources: dict[str, ConfigSource]


def merge_config_layers(
    ctx: ParameterSourceContext,
    *,
    defaults: Mapping[str, Any],
    config_overrides: Mapping[str, Any],
    key_to_param_name: Mapping[str, str] | None = None,
) -> EffectiveConfig:
    values = dict(defaults)
    sources: dict[str, ConfigSource] = {}
    param_names = key_to_param_name or {}

    for key in values:
        param_name = param_names.get(key, key)
        if ctx.get_parameter_source(param_name) == ParameterSource.COMMANDLINE:
            sources[key] = "cli"
        else:
            sources[key] = "default"

    for key, value in config_overrides.items():
        if sources.get(key) == "cli":
            continue
        values[key] = value
        sources[key] = "config"

    return EffectiveConfig(values=values, sources=sources)


def effective_config_payload(
    *,
    command: str,
    merged: EffectiveConfig,
    config_path: Path | None,
) -> dict[str, Any]:
    return {
        "command": command,
        "config_path": str(config_path) if config_path is not None else None,
        "effective_config": {
            key: {
                "value": _to_jsonable(merged.values[key]),
                "source": merged.sources.get(key, "default"),
            }
            for key in sorted(merged.values)
        },
    }


def _to_jsonable(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, list):
        return [_to_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _to_jsonable(item) for key, item in value.items()}
    return value
