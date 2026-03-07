from __future__ import annotations

from pathlib import Path
from typing import Any

try:  # Python 3.11+
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - exercised on py310 CI
    import tomli as tomllib

CONFIG_FILENAME = "foldermix.toml"

_COMMAND_KEYS: dict[str, set[str]] = {
    "pack": {
        "out",
        "format",
        "include_ext",
        "exclude_ext",
        "exclude_dirs",
        "exclude_glob",
        "include_glob",
        "max_bytes",
        "max_total_bytes",
        "max_files",
        "hidden",
        "follow_symlinks",
        "respect_gitignore",
        "line_ending",
        "encoding",
        "workers",
        "progress",
        "dry_run",
        "report",
        "continue_on_error",
        "on_oversize",
        "redact",
        "drop_line_containing",
        "min_line_length",
        "strip_frontmatter",
        "include_sha256",
        "include_toc",
        "dedupe_content",
        "pdf_ocr",
        "pdf_ocr_strict",
        "policy_pack",
        "policy_rules",
        "fail_on_policy_violation",
        "policy_fail_level",
        "policy_dry_run",
        "policy_output",
    },
    "stats": {"include_ext", "hidden"},
}
_ALL_KEYS = set().union(*_COMMAND_KEYS.values())
_SECTION_KEYS = {"pack", "stats", "common"}

_LITERALS: dict[str, set[str]] = {
    "format": {"md", "xml", "jsonl"},
    "on_oversize": {"skip", "truncate"},
    "redact": {"none", "emails", "phones", "all"},
    "line_ending": {"lf", "crlf"},
    "policy_fail_level": {"low", "medium", "high", "critical"},
    "policy_output": {"text", "json"},
}
_INT_KEYS = {"max_bytes", "max_total_bytes", "max_files", "workers", "min_line_length"}
_NON_NEGATIVE_INT_KEYS = {"min_line_length"}
_BOOL_KEYS = {
    "hidden",
    "follow_symlinks",
    "respect_gitignore",
    "progress",
    "dry_run",
    "continue_on_error",
    "strip_frontmatter",
    "include_sha256",
    "include_toc",
    "dedupe_content",
    "pdf_ocr",
    "pdf_ocr_strict",
    "fail_on_policy_violation",
    "policy_dry_run",
}
_STR_KEYS = {"encoding"}
_PATH_KEYS = {"out", "report"}
_LIST_KEYS = {
    "include_ext",
    "exclude_ext",
    "exclude_dirs",
    "exclude_glob",
    "include_glob",
    "drop_line_containing",
}
_POLICY_RULE_KEYS = {
    "rule_id",
    "description",
    "severity",
    "action",
    "stage",
    "path_glob",
    "ext_in",
    "skip_reason_in",
    "content_regex",
    "max_size_bytes",
    "max_total_bytes",
    "max_file_count",
}
_POLICY_RULE_LITERALS: dict[str, set[str]] = {
    "severity": {"low", "medium", "high", "critical"},
    "action": {"warn", "deny"},
    "stage": {"scan", "convert", "pack", "any"},
}
_POLICY_RULE_STR_KEYS = {"rule_id", "description", "path_glob", "content_regex"}
_POLICY_RULE_LIST_KEYS = {"ext_in", "skip_reason_in"}
_POLICY_RULE_INT_KEYS = {"max_size_bytes", "max_total_bytes", "max_file_count"}
_POLICY_MATCHER_KEYS = {
    "path_glob",
    "ext_in",
    "skip_reason_in",
    "content_regex",
    "max_size_bytes",
    "max_total_bytes",
    "max_file_count",
}


class ConfigLoadError(RuntimeError):
    """Raised when a foldermix config file cannot be loaded or validated."""

    def __init__(self, path: Path, errors: list[str]) -> None:
        self.path = path
        self.errors = errors
        super().__init__(str(self))

    def __str__(self) -> str:
        details = "\n".join(f"- {err}" for err in self.errors)
        return f"Invalid config at {self.path}:\n{details}"


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _split_csv(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def _coerce_list_str(value: Any, key: str, errors: list[str], *, where: str) -> list[str]:
    if isinstance(value, str):
        return _split_csv(value)
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return value
    errors.append(f"{where}.{key}: expected a list of strings (or CSV string)")
    return []


def _coerce_value(key: str, value: Any, errors: list[str], *, where: str) -> Any:
    if key == "policy_pack":
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{where}.policy_pack: expected a non-empty string")
            return value
        return value

    if key == "policy_rules":
        return _coerce_policy_rules(value, errors, where=where)

    if key in _LITERALS:
        if not isinstance(value, str):
            errors.append(f"{where}.{key}: expected a string")
            return value
        if value not in _LITERALS[key]:
            choices = ", ".join(sorted(_LITERALS[key]))
            errors.append(f"{where}.{key}: expected one of {choices!r}, got {value!r}")
        return value

    if key in _INT_KEYS:
        if value is None and key in {"max_total_bytes", "max_files"}:
            return None
        if not _is_int(value):
            errors.append(f"{where}.{key}: expected an integer")
            return value
        if key in _NON_NEGATIVE_INT_KEYS and value < 0:
            errors.append(f"{where}.{key}: expected a non-negative integer")
        return value

    if key in _BOOL_KEYS:
        if not isinstance(value, bool):
            errors.append(f"{where}.{key}: expected a boolean")
        return value

    if key in _STR_KEYS:
        if not isinstance(value, str):
            errors.append(f"{where}.{key}: expected a string")
        return value

    if key in _PATH_KEYS:
        if value is None:
            return None
        if isinstance(value, str):
            return Path(value)
        errors.append(f"{where}.{key}: expected a filesystem path string")
        return value

    if key in _LIST_KEYS:
        return _coerce_list_str(value, key, errors, where=where)

    errors.append(f"{where}.{key}: unsupported key")
    return value


def _coerce_policy_rules(value: Any, errors: list[str], *, where: str) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        errors.append(f"{where}.policy_rules: expected a list of policy rule tables")
        return []

    normalized_rules: list[dict[str, Any]] = []
    for index, raw_rule in enumerate(value):
        rule_where = f"{where}.policy_rules[{index}]"
        if not isinstance(raw_rule, dict):
            errors.append(f"{rule_where}: expected a TOML table")
            continue

        unknown_keys = sorted(key for key in raw_rule if key not in _POLICY_RULE_KEYS)
        if unknown_keys:
            errors.append(f"{rule_where}: unknown key(s): {', '.join(unknown_keys)}")

        normalized_rule: dict[str, Any] = {}
        for key, raw_val in raw_rule.items():
            if key in _POLICY_RULE_STR_KEYS:
                if not isinstance(raw_val, str) or not raw_val.strip():
                    errors.append(f"{rule_where}.{key}: expected a non-empty string")
                    continue
                normalized_rule[key] = raw_val
                continue

            if key in _POLICY_RULE_LIST_KEYS:
                normalized_rule[key] = _coerce_list_str(raw_val, key, errors, where=rule_where)
                continue

            if key in _POLICY_RULE_INT_KEYS:
                if not _is_int(raw_val) or raw_val < 0:
                    errors.append(f"{rule_where}.{key}: expected a non-negative integer")
                    continue
                normalized_rule[key] = raw_val
                continue

            if key in _POLICY_RULE_LITERALS:
                if not isinstance(raw_val, str):
                    errors.append(f"{rule_where}.{key}: expected a string")
                    continue
                choices = _POLICY_RULE_LITERALS[key]
                if raw_val not in choices:
                    rendered = ", ".join(sorted(choices))
                    errors.append(
                        f"{rule_where}.{key}: expected one of {rendered}, got {raw_val!r}"
                    )
                    continue
                normalized_rule[key] = raw_val
                continue

        if "rule_id" not in normalized_rule:
            errors.append(f"{rule_where}.rule_id: required")
        if "description" not in normalized_rule:
            errors.append(f"{rule_where}.description: required")

        if not any(matcher in normalized_rule for matcher in _POLICY_MATCHER_KEYS):
            errors.append(
                f"{rule_where}: expected at least one matcher key "
                f"({', '.join(sorted(_POLICY_MATCHER_KEYS))})"
            )

        normalized_rules.append(normalized_rule)

    return normalized_rules


def _extract_config_root(data: dict[str, Any], *, path: Path) -> dict[str, Any]:
    tool = data.get("tool")
    if isinstance(tool, dict):
        foldermix = tool.get("foldermix")
        if isinstance(foldermix, dict):
            return foldermix
        if foldermix is not None:
            raise ConfigLoadError(path, ["tool.foldermix must be a TOML table"])

    foldermix = data.get("foldermix")
    if isinstance(foldermix, dict):
        return foldermix
    if foldermix is not None:
        raise ConfigLoadError(path, ["foldermix must be a TOML table"])

    return data


def _resolve_section(
    root: dict[str, Any], command: str, errors: list[str]
) -> tuple[dict[str, Any], str]:
    has_sections = any(key in _SECTION_KEYS for key in root)
    if not has_sections:
        return root, "config"

    unknown = [key for key in root if key not in _SECTION_KEYS]
    if unknown:
        errors.append(
            "config: unknown top-level keys when using sections: " + ", ".join(sorted(unknown))
        )

    section: dict[str, Any] = {}
    common = root.get("common")
    if common is not None:
        if not isinstance(common, dict):
            errors.append("config.common must be a TOML table")
        else:
            section.update(common)

    command_table = root.get(command)
    if command_table is not None:
        if not isinstance(command_table, dict):
            errors.append(f"config.{command} must be a TOML table")
        else:
            section.update(command_table)

    return section, f"config.{command}"


def _validate_and_filter(
    command: str, section: dict[str, Any], *, path: Path, where: str
) -> dict[str, Any]:
    errors: list[str] = []
    normalized: dict[str, Any] = {}
    allowed = _COMMAND_KEYS[command]

    for key, raw_value in section.items():
        if key not in _ALL_KEYS:
            errors.append(f"{where}: unknown key {key!r}")
            continue
        if key not in allowed:
            errors.append(f"{where}: key {key!r} is not valid for {command!r} command")
            continue
        normalized[key] = _coerce_value(key, raw_value, errors, where=where)

    if errors:
        raise ConfigLoadError(path, errors)

    return normalized


def discover_config_path(search_start: Path) -> Path | None:
    """Find the nearest foldermix.toml by walking upward from the target path."""
    base = search_start
    if search_start.exists() and search_start.is_file():
        base = search_start.parent
    if not base.exists():
        base = Path.cwd()
    base = base.resolve()

    for candidate_dir in (base, *base.parents):
        candidate = candidate_dir / CONFIG_FILENAME
        if candidate.is_file():
            return candidate
    return None


def load_command_config(
    command: str, *, root: Path, config_path: Path | None
) -> tuple[dict[str, Any], Path | None]:
    """Load and validate config values for a specific command."""
    if command not in _COMMAND_KEYS:
        raise ValueError(f"Unsupported command: {command}")

    if config_path is not None:
        path = config_path.expanduser()
        if not path.is_file():
            raise ConfigLoadError(path, ["config file does not exist"])
    else:
        path = discover_config_path(root)
        if path is None:
            return {}, None

    try:
        content = path.read_text(encoding="utf-8")
        parsed = tomllib.loads(content)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigLoadError(path, [f"invalid TOML: {exc}"]) from exc
    except OSError as exc:
        raise ConfigLoadError(path, [f"could not read config: {exc}"]) from exc

    if not isinstance(parsed, dict):
        raise ConfigLoadError(path, ["config root must be a TOML table"])

    root_table = _extract_config_root(parsed, path=path)
    errors: list[str] = []
    section, where = _resolve_section(root_table, command, errors)
    if errors:
        raise ConfigLoadError(path, errors)

    command_values = _validate_and_filter(command, section, path=path, where=where)
    return command_values, path
