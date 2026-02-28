# AGENTS.md - foldermix

This file defines contributor and coding-agent rules for this repository.
For a deeper orientation see [docs/agents.md](docs/agents.md).

## Scope and intent
- Keep changes focused, minimal, and test-backed.
- Preserve backward compatibility unless the issue or PR explicitly allows breaking changes.
- Prefer clear, deterministic behavior over implicit magic.

## Project basics
- Package: `foldermix`
- Purpose: pack folders into LLM-friendly output formats (`md`, `xml`, `jsonl`)
- Python: `>=3.10`
- Optional extras: `pdf`, `ocr`, `office`, `markitdown`, `all`
- Entry point: `foldermix` CLI (`foldermix/cli.py`) — four commands: `pack`, `list`, `stats`, `version`

## Repository layout

```
foldermix/
├── foldermix/           # Source package
│   ├── cli.py           # Typer CLI (entry point)
│   ├── config.py        # PackConfig dataclass + default include/exclude lists
│   ├── config_loader.py # foldermix.toml loader + validator
│   ├── effective_config.py # Config-layer merge logic (defaults → TOML → CLI)
│   ├── packer.py        # Orchestration: scan → convert → write
│   ├── scanner.py       # File discovery (gitignore, filters, globs, symlinks)
│   ├── report.py        # JSON report writer
│   ├── utils.py         # Redaction, frontmatter stripping, SHA-256, timestamps
│   ├── converters/      # Optional file converters (PDF, Office, markitdown, text)
│   └── writers/         # Output-format writers (Markdown, XML, JSONL)
├── tests/               # Pytest test suite (see Test Suite section below)
├── scripts/             # Maintenance scripts (e.g. render_homebrew_formula.py)
├── docs/
│   └── agents.md        # Detailed agent orientation (architecture, how-tos)
├── pyproject.toml       # Build config, dependencies, tool settings
├── README.md            # User + developer documentation
└── CONTRIBUTING.md      # Contributing guide
```

## Key modules

### `foldermix/config.py`
`PackConfig` is a slots dataclass that holds every pack parameter.  It is the single contract passed from the CLI to the packer — do not add business logic here.  Also defines `DEFAULT_EXCLUDE_EXT`, `DEFAULT_EXCLUDE_DIRS`, and `SENSITIVE_PATTERNS`.

### `foldermix/config_loader.py`
Reads `foldermix.toml` (auto-discovered by walking up from the target path, or explicitly via `--config`).  The TOML file may use a flat layout or named sections (`[pack]`, `[list]`, `[stats]`, `[common]`).  It may also be embedded under `[tool.foldermix]` in any project TOML.  Invalid keys or wrong types raise `ConfigLoadError`.

### `foldermix/scanner.py`
`scan(config) -> (included, skipped)` walks the directory tree and returns `FileRecord` / `SkipRecord` lists.  Key behaviours:
- Respects `.gitignore` via `pathspec`.
- Skips hidden files/dirs unless `--hidden`.
- Skips sensitive files (`.env`, `*.pem`, `*.key`, etc.) unconditionally.
- Applies extension include/exclude, glob include/exclude patterns.
- Output order is always case-folded alphabetical for determinism.

### `foldermix/packer.py`
`pack(config) -> None` orchestrates: scan → parallel convert (`ThreadPoolExecutor`) → sort results back to deterministic order → write via the chosen writer → optionally write a JSON report.

### `foldermix/writers/`
Each writer subclasses the `Writer` base class from `writers/base.py`:
```python
def write(self, out: IO[str], header: HeaderInfo, items: list[FileBundleItem]) -> None: ...
```
- `MarkdownWriter` — fenced-code-block document, optional TOC and SHA-256 entries.
- `XmlWriter` — `<bundle>` document with `<file>` elements.
- `JsonlWriter` — one JSON object per line (header first, then files).

### `foldermix/converters/`
A `ConverterRegistry` tries converters in registration order.  Each converter implements:
```python
def can_convert(self, ext: str) -> bool: ...
def convert(self, path: Path, encoding: str = "utf-8") -> ConversionResult: ...
```
Optional converters (`MarkitdownConverter`, `PdfFallbackConverter`, `DocxFallbackConverter`, `XlsxFallbackConverter`, `PptxFallbackConverter`) are always registered, but their `can_convert()` returns `False` when their extra dependency is not installed.  `TextConverter` is the always-available fallback.

## Configuration system

Config is resolved in this deterministic priority order (higher overrides lower):

1. Built-in defaults in `PackConfig`
2. `foldermix.toml` (auto-discovered or via `--config`)
3. Explicit CLI flags

Use `--print-effective-config` on any command to inspect the merged result with the source of each key.

## Core quality requirements
- Lint must pass:
  - `ruff check .`
  - `ruff format --check .`
- Tests must pass:
  - `pytest -m "not integration and not slow" -o addopts=`  ← fast unit/smoke pass
  - `pytest -m integration -o addopts=`  ← snapshot/end-to-end pass
- Coverage gate:
  - `pytest --cov=foldermix --cov-branch --cov-report=term-missing:skip-covered tests/`
  - Required threshold: at least what CI enforces (currently >=98%).

## Test suite overview

| File | Marker | What it covers |
|------|--------|----------------|
| `test_cli.py` | — | CLI argument validation, config construction, all four commands |
| `test_cli_entrypoint.py` | — | CLI entry-point smoke (`foldermix --help`) |
| `test_config_loader.py` | — | Raw config file loading, path resolution, error reporting |
| `test_effective_config.py` | — | Merging of defaults, CLI flags, and config files into the effective config |
| `test_converters.py` | — | Converter registry, PDF/Office/markitdown/text converters |
| `test_converters_fallback.py` | — | Graceful degradation when optional extras are absent |
| `test_packer.py` | — | Core `packer.pack()` logic, error handling, oversize policy |
| `test_packer_edges.py` | — | Symlinks, hidden files, max-file limits, report output |
| `test_scanner.py` | — | Gitignore, extension filters, glob patterns |
| `test_scanner_edge.py` | — | Circular symlinks, deeply nested directories |
| `test_scanner_properties.py` | — | Hypothesis-based property tests for the scanner |
| `test_snapshot_guard.py` | — | Fast guard that snapshot fixtures are in sync with the packer |
| `test_utils.py` | — | Redaction, frontmatter stripping, SHA-256 helpers |
| `test_version_module.py` | — | `foldermix.__version__` is set and non-empty |
| `test_writers.py` | — | All three writer classes round-trip |
| `test_writers_edge.py` | — | Empty bundles, special characters, large content |
| `test_render_homebrew_formula.py` | — | Formula renderer helpers |
| `test_perf_smoke.py` | `slow` | 1,500 synthetic files; asserts ≤ 25 s wall-clock (configurable via `FOLDERMIX_PERF_MAX_SECONDS`) and ≤ 256 MB `tracemalloc` peak (configurable via `FOLDERMIX_PERF_MAX_PEAK_MB`) |
| `integration/test_pack_outputs.py` | `integration` | Golden-file snapshot tests for md/xml/jsonl output |
| `integration/test_pack_outputs_structured.py` | `integration` | Structured assertions on TOC, SHA-256, XML structure |
| `integration/test_converters_real_files.py` | `integration` | Real-file converter tests (PDF, docx, xlsx, pptx) |

### Snapshot tests
Fixtures live in `tests/integration/fixtures/`:
- `simple_project/` — input file tree (source of truth for golden outputs).
- `expected/` — golden output files (`simple_project.md`, `.xml`, `.jsonl`).

When packer output changes intentionally, regenerate fixtures and commit them in the same PR:
```bash
# Run the packer against the simple_project fixture and capture the output
pytest -o addopts= tests/integration/test_pack_outputs.py -m integration -v
# If tests fail with a diff, copy the fresh output into the expected/ directory:
# tests/integration/fixtures/expected/simple_project.{md,xml,jsonl}
# then commit the updated files as part of the same PR
```

## CI/CD workflows

| Workflow | Trigger | Key jobs |
|----------|---------|----------|
| `ci.yml` | Every push / PR | `lint` → `smoke` → `minimal-deps` → `package-smoke` → `full` (coverage gate) → `publish-pypi` → `update-homebrew-tap` |
| `mutation.yml` | Weekly Sat 09:00 UTC + `workflow_dispatch` | `mutmut` on core source modules |
| `perf-smoke.yml` | Weekly Sun 09:00 UTC + `workflow_dispatch` | Performance smoke (1,500 files) |
| `security-audit.yml` | Weekly Mon 09:00 UTC + `pyproject.toml` changes | `pip-audit` dependency CVE scan |

`full` CI job requires all earlier jobs to pass and enforces ≥ 98% branch coverage.  A bump to the `version` field in the `[project]` table of `pyproject.toml` on `main` (detected by comparing `HEAD` vs `HEAD^`) triggers automatic PyPI publish + Homebrew formula update.

## Common tasks

### Adding a new output format
1. Create `foldermix/writers/myformat_writer.py` implementing the `Writer` protocol.
2. Register it in `_get_writer()` in `foldermix/packer.py` and in the CLI format validation in `foldermix/cli.py`.
3. Add unit tests in `tests/test_writers.py` and edge-case tests in `tests/test_writers_edge.py`.
4. Add a snapshot fixture in `tests/integration/fixtures/expected/` and wire it into `tests/integration/test_pack_outputs.py` and `tests/test_snapshot_guard.py`.

### Adding a new converter
1. Create `foldermix/converters/myconv.py` implementing the `Converter` protocol.
2. Add the optional dependency to `pyproject.toml` under a new or existing extra.
3. Register the converter in `packer._build_registry()`.
4. Add unit tests in `tests/test_converters.py` and a fallback test in `tests/test_converters_fallback.py`.
5. Add real-file integration tests in `tests/integration/test_converters_real_files.py`.

## Coding expectations
- Maintain deterministic behavior and stable output ordering.
- Add tests for new behavior and edge cases.
- Do not silently swallow actionable errors.
- Keep dependency additions justified and documented.
- Update README and docs when user-visible behavior or options change.
- New or modified Python modules should start with `from __future__ import annotations`; document any intentional exceptions (for example, specific `__init__.py` files).
- Use `Protocol` for interfaces; type hints throughout.

## PR expectations
- Keep PR descriptions explicit: behavior change, flags and config keys, dependency impact, and test evidence.
- Prefer one logical change per PR.
- Ensure CI is green before merge.

## Local overrides (optional, untracked)
- If `LOCAL_AGENTS.md` exists at repo root, treat it as additive local instructions.
- On conflicts:
  - Security and repository policy rules take precedence.
  - Then `LOCAL_AGENTS.md` may refine local workflow and tool routing.
- Never commit machine-specific paths, personal tokens, or local MCP server names into tracked docs.

## Security and secrets
- Never commit secrets or credentials.
- Respect existing sensitive-file handling and redaction behavior.
- Sensitive files (`.env`, `*.pem`, `*.key`, SSH keys, etc.) are skipped unconditionally by the scanner — do not weaken this behavior.
