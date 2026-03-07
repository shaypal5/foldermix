# foldermix — AI Coding Agent Guide

This document provides a detailed orientation for AI coding agents (e.g. GitHub Copilot Coding Agent) working on the `foldermix` repository.

---

## Repository Overview

`foldermix` is a CLI tool and Python library that packs a folder into a single LLM-friendly context file in Markdown, XML, or JSONL format. The project is a pure-Python package that ships as a PyPI wheel and a Homebrew formula.

```
foldermix/
├── foldermix/           # Source package
│   ├── cli.py           # Typer CLI (entry point)
│   ├── config.py        # PackConfig dataclass
│   ├── packer.py        # Orchestration: scan → convert → write
│   ├── scanner.py       # File discovery (gitignore, filters, symlinks)
│   ├── report.py        # JSON report writer
│   ├── utils.py         # Redaction, frontmatter, SHA-256, timestamps
│   ├── converters/      # Optional file converters
│   │   ├── base.py          # ConversionResult + registry interfaces
│   │   ├── text.py          # Plain-text / passthrough converter
│   │   ├── pdf_fallback.py  # pypdf-based PDF converter
│   │   ├── docx_fallback.py # python-docx converter
│   │   ├── xlsx_fallback.py # openpyxl converter
│   │   ├── pptx_fallback.py # python-pptx converter
│   │   └── markitdown_conv.py  # markitdown converter
│   └── writers/         # Output format writers
│       ├── base.py          # FileBundleItem, HeaderInfo, Writer protocol
│       ├── markdown_writer.py
│       ├── xml_writer.py
│       └── jsonl_writer.py
├── tests/               # Pytest test suite
├── scripts/             # Maintenance scripts
│   └── render_homebrew_formula.py
├── docs/                # Developer documentation
│   └── agents.md        # This file
├── .github/
│   ├── workflows/       # CI/CD pipelines
│   └── dependabot.yml   # Automated dependency updates
├── pyproject.toml       # Build config, dependencies, tool config
├── README.md            # User + developer documentation
├── CONTRIBUTING.md      # Contributing guide
└── SECURITY.md          # Security policy
```

---

## Key Modules

### `foldermix/cli.py`

Typer application with seven commands: `init`, `pack`, `list`, `skiplist`, `preview`, `stats`, `version`.

- The `pack` command validates its core options early and exits with code 1 on those validation failures; Typer still handles parsing errors and unknown flags (typically with exit code 2).
- Builds a `PackConfig` and delegates to `packer.pack()`.
- The `init` command writes a commented `foldermix.toml` for one of the built-in local-use profiles.

### `foldermix/config.py`

`PackConfig` is a dataclass holding all pack parameters. Passed through from CLI to packer — do not add business logic here.

### `foldermix/scanner.py`

`scan(config: PackConfig) -> list[Path]` discovers files under `config.root`:

- Respects `.gitignore` via `pathspec`.
- Applies extension include/exclude filters.
- Applies glob include/exclude patterns.
- Enforces `max_files`, skips hidden files unless `--hidden`, and follows symlinks only if `--follow-symlinks`.
- Always skips sensitive files (`.env`, `*.pem`, `*.key`, SSH keys, etc.).

### `foldermix/packer.py`

`pack(config: PackConfig) -> None` orchestrates:

1. `scanner.scan()` → list of `Path` objects.
2. Convert each file via the converter registry (parallel with `ThreadPoolExecutor`).
3. Pass `FileBundleItem` list to the appropriate writer.
4. Optionally write a JSON report via `report.write_report()`.

### `foldermix/writers/`

Each writer subclasses the `Writer` interface from `writers/base.py`:

```python
class Writer:
    def write(self, out: IO[str], header: HeaderInfo, items: list[FileBundleItem]) -> None: ...
```

- `MarkdownWriter` — produces a fenced-code-block document with optional TOC and SHA-256 entries.
- `XmlWriter` — produces a `<bundle>` document with `<file>` elements.
- `JsonlWriter` — produces one JSON object per line (header on line 1, files on subsequent lines).

### `foldermix/converters/`

The converter registry tries each registered converter in order. A converter implements:

```python
class Converter(Protocol):
    def can_convert(self, ext: str) -> bool: ...
    def convert(self, path: Path, encoding: str = "utf-8") -> ConversionResult: ...
```

Optional converters (`pdf`, `office`, `markitdown`) are always added to the registry, but they only become active when their optional dependencies (extras) are installed (otherwise their `can_convert()` methods return `False`, making them effective no-ops). The plain-text converter is always available as a fallback.

---

## Test Suite

### Test Markers

Tests use two custom markers declared in `pyproject.toml`:

- `integration` — end-to-end/snapshot tests; excluded from the fast smoke pass.
- `slow` — long-running tests (e.g. perf smoke); excluded by default in CI matrix jobs.

### Snapshot Tests

Snapshot fixtures live in `tests/integration/fixtures/`:

```
tests/integration/fixtures/
├── simple_project/        # Input file tree
│   ├── alpha.md
│   ├── code.py
│   └── nested/
└── expected/              # Golden output files
    ├── simple_project.md
    ├── simple_project.xml
    └── simple_project.jsonl
```

`tests/snapshot_helpers.py` provides `render_simple_project_snapshot()`, which:

1. Copies `simple_project/` to a temp directory.
2. Normalises newlines (CRLF → LF) and sets a fixed mtime to ensure deterministic output.
3. Monkeypatches `packer.utcnow_iso` to a fixed timestamp.
4. Runs `packer.pack()` and normalises the root path to `__ROOT__`.

The fast `test_snapshot_guard.py` runs in every CI lane (no `integration` marker) to catch fixture drift quickly. The `integration/test_pack_outputs.py` tests run only in the `full` CI job.

**Regenerating snapshots:** When packer output changes intentionally (e.g. new header fields), regenerate the fixtures by running:

```bash
pytest -o addopts= tests/integration/test_pack_outputs.py -m integration -v
```

If the test fails with a diff, update the expected files in `tests/integration/fixtures/expected/` with the new output, then commit the updated fixtures as part of the same PR.

---

## CI / CD Workflows

All workflows are in `.github/workflows/`.

### `ci.yml` — Main CI Pipeline

Triggered on every push to `main` and every pull request.

| Job | Depends on | Purpose |
|-----|-----------|---------|
| `lint` | — | `ruff check` + `ruff format --check` |
| `smoke` | — | Unit tests on Ubuntu (3.10, 3.11, 3.12), macOS (3.12), and Windows (3.12) |
| `minimal-deps` | — | Core tests without optional extras installed |
| `package-smoke` | — | Build wheel → clean-venv install → CLI black-box assertions |
| `full` | lint, smoke, minimal-deps, package-smoke | Full pytest suite with ≥ 98% branch coverage; uploads to Codecov |
| `publish-pypi` | full | Version-bump detection; publishes to PyPI via OIDC if bumped |
| `update-homebrew-tap` | publish-pypi | Renders Homebrew formula and pushes to `foldermix/homebrew-foldermix` |

### `mutation.yml` — Mutation Testing

- Runs weekly (Saturday 09:00 UTC) and on `workflow_dispatch`.
- Installs `.[dev,mutation,all]` and runs `mutmut` on six core source modules.
- Uploads `.mutmut-cache` as an artifact for review.
- Mutated modules: `scanner.py`, `packer.py`, `writers/base.py`, `writers/markdown_writer.py`, `writers/xml_writer.py`, `writers/jsonl_writer.py`.

### `perf-smoke.yml` — Performance Smoke

- Runs weekly (Sunday 09:00 UTC) and on `workflow_dispatch`.
- Sets `FOLDERMIX_RUN_PERF_SMOKE=1` and runs `test_perf_smoke.py`.
- Asserts: pack 1,500 synthetic files in ≤ 25 s, peak Python `tracemalloc` memory ≤ 256 MiB (as configured by `FOLDERMIX_PERF_MAX_PEAK_MB`).

### `security-audit.yml` — Dependency Audit

- Runs weekly (Monday 09:00 UTC), on `pyproject.toml` changes, and on `workflow_dispatch`.
- Runs `pip-audit` to check all installed dependencies for known CVEs.

---

## Adding a New Output Format

1. Create `foldermix/writers/myformat_writer.py` implementing the `Writer` protocol.
2. Register it in `foldermix/writers/__init__.py` and `foldermix/cli.py` format lookup.
3. Add unit tests in `tests/test_writers.py` and edge-case tests in `tests/test_writers_edge.py`.
4. Add a snapshot fixture: copy `tests/integration/fixtures/expected/simple_project.md` as a template, run the packer against the `simple_project` fixture, and save the output to `tests/integration/fixtures/expected/simple_project.myformat`.
5. Add snapshot assertions to `tests/integration/test_pack_outputs.py` and `tests/test_snapshot_guard.py`.

## Adding a New Converter

1. Create `foldermix/converters/myconv.py` implementing the `Converter` protocol.
2. Add the optional dependency to `pyproject.toml` under a new or existing extra.
3. Register the converter in the registry (conditionally on the import being available).
4. Add tests in `tests/test_converters.py` (unit) and `tests/integration/test_converters_real_files.py` (real-file integration test).
5. Add a fallback test in `tests/test_converters_fallback.py` that verifies graceful degradation when the extra is not installed.

---

## Release Checklist

See the [Release PR Process](../README.md#release-pr-process) section in README.md for the full step-by-step guide.

**Key points:**

- A version bump in `pyproject.toml` is the sole trigger for a PyPI release.
- The `publish-pypi` job compares `HEAD` vs `HEAD^` to detect the bump.
- Snapshot fixtures must be updated in the same PR if packer output changed.
- The `HOMEBREW_TAP_GITHUB_TOKEN` secret must be configured for tap updates to succeed.

---

## Code Style

- **Python**: `ruff` with `line-length = 100`, target `py310`, rules `E F I UP`.
- **Imports**: `from __future__ import annotations` at the top of every module.
- **Type hints**: Used throughout; use `Protocol` for interfaces.
- **No comments** except where they explain non-obvious logic.
