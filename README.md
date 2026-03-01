# foldermix

**Pack a folder into a single LLM-friendly context file.**

[![CI](https://github.com/shaypal5/foldermix/actions/workflows/ci.yml/badge.svg)](https://github.com/shaypal5/foldermix/actions/workflows/ci.yml)

## Installation

```bash
pip install foldermix
# With optional extras:
pip install "foldermix[all]"   # adds PDF, OCR, Office, tqdm
pip install "foldermix[pdf]"   # pypdf only
pip install "foldermix[ocr]"   # OCR for image-based PDF pages (includes pypdf + rapidocr + pypdfium2)
pip install "foldermix[office]" # docx/xlsx/pptx support
```

### Homebrew (macOS/Linux)

```bash
brew tap shaypal5/tap
brew install foldermix
```

## Quick Start

```bash
# Pack current directory to markdown
foldermix pack .

# Pack to XML format
foldermix pack . --format xml

# Pack to JSONL format
foldermix pack . --format jsonl --out context.jsonl

# Dry run - list files without packing
foldermix pack . --dry-run

# List files that would be included
foldermix list .

# Show statistics
foldermix stats .

# Read explicit file list from stdin
printf 'a.txt\nnotes/b.txt\n' | foldermix pack . --stdin --format jsonl --out context.jsonl

# Read NUL-delimited file list from find -print0
find . -type f -print0 | foldermix pack . --stdin --null --format md --out context.md

# Print merged effective config (defaults + config + CLI) and exit
foldermix pack . --config foldermix.toml --print-effective-config

# Show version
foldermix version

# Bootstrap a local config profile
foldermix init --profile engineering-docs
```

## Features

- **Multiple output formats**: Markdown, XML, JSONL
- **Smart filtering**: gitignore support, extension filters, glob patterns
- **Sensitive file protection**: Automatically skips `.env`, keys, certificates
- **Optional converters**: PDF (pypdf), OCR-enhanced PDF fallback (rapidocr + pypdfium2), Office docs (python-docx, openpyxl, python-pptx), markitdown
- **Redaction**: Email and phone number redaction via `--redact`
- **SHA-256 checksums** per file
- **Parallel processing** with configurable workers
- **Table of contents** in Markdown output

## Config Precedence

`foldermix` resolves effective options in this deterministic order:

1. Built-in defaults
2. `foldermix.toml` values (`--config` or discovered file)
3. Explicit CLI flags

For diagnostics, `pack`, `list`, and `stats` can print the merged result (including source per key) and exit:

```bash
foldermix pack . --print-effective-config
foldermix list . --print-effective-config
foldermix stats . --print-effective-config
```

## Starter Config Profiles

Use `foldermix init` to generate a commented starter `foldermix.toml` for common local workflows:

```bash
foldermix init --profile legal
foldermix init --profile research --out ./configs/foldermix.toml
foldermix init --profile support --force
```

Available profiles:

- `legal` - privacy-first defaults with full redaction and OCR enabled.
- `research` - broad document coverage with OCR and email-only redaction.
- `support` - ticket/runbook focused filters with full redaction defaults.
- `engineering-docs` - technical docs profile with frontmatter stripping and no redaction.

## Options

```
foldermix pack [OPTIONS] [PATH]

Options:
  -o, --out PATH                Output file path
  -f, --format TEXT             Output format: md, xml, jsonl [default: md]
  --include-ext TEXT            Comma-separated extensions to include
  --exclude-ext TEXT            Comma-separated extensions to exclude
  --exclude-dirs TEXT           Comma-separated directory names to exclude
  --exclude-glob TEXT           Glob patterns to exclude
  --include-glob TEXT           Glob patterns to include
  --max-bytes INTEGER           Max bytes per file [default: 10000000]
  --max-total-bytes INTEGER     Max total bytes
  --max-files INTEGER           Max number of files
  --hidden                      Include hidden files
  --follow-symlinks             Follow symbolic links
  --respect-gitignore / --no-respect-gitignore  [default: respect]
  --workers INTEGER             Number of worker threads [default: 4]
  --progress                    Show progress bar (requires tqdm)
  --dry-run                     List files without packing
  --report PATH                 Write JSON report to path
  --continue-on-error           Skip files that fail to convert
  --on-oversize TEXT            skip or truncate [default: skip]
  --redact TEXT                 none, emails, phones, all [default: none]
  --strip-frontmatter           Strip YAML frontmatter from files
  --include-sha256 / --no-include-sha256  [default: include]
  --include-toc / --no-include-toc        [default: include]
  --pdf-ocr / --no-pdf-ocr                Enable OCR fallback for textless PDF pages [default: disabled]
  --pdf-ocr-strict / --no-pdf-ocr-strict  Fail when OCR is needed but unavailable/empty [default: disabled]
  --stdin                        Read explicit file paths from standard input instead of recursive scanning
  --null                         Parse stdin as NUL-delimited paths (for find -print0); requires --stdin
```

## Report Schema

`--report` now writes a versioned schema with machine-actionable reason codes while preserving existing human-readable fields.

- Current schema: `schema_version = 2`
- Compatibility policy:
  - Existing keys are preserved (`included_count`, `skipped_count`, `total_bytes`, `included_files`, `skipped_files`).
  - New top-level fields are additive (`schema_version`, `reason_code_counts`).
  - New per-entry fields are additive (`reason_code`, `message`, `outcome_codes`, `outcomes`).

Example `report.json` shape:

```json
{
  "schema_version": 2,
  "included_count": 2,
  "skipped_count": 1,
  "total_bytes": 1234,
  "included_files": [
    {
      "path": "big.txt",
      "size": 900,
      "ext": ".txt",
      "outcome_codes": ["OUTCOME_TRUNCATED", "OUTCOME_REDACTED"],
      "outcomes": [
        {"code": "OUTCOME_TRUNCATED", "message": "File content was truncated to satisfy --max-bytes."},
        {"code": "OUTCOME_REDACTED", "message": "Content was redacted using mode 'emails'."}
      ]
    }
  ],
  "skipped_files": [
    {
      "path": "image.png",
      "reason": "excluded_ext",
      "reason_code": "SKIP_EXCLUDED_EXT",
      "message": "Path is excluded by extension filtering."
    }
  ],
  "reason_code_counts": {
    "OUTCOME_REDACTED": 1,
    "OUTCOME_TRUNCATED": 1,
    "SKIP_EXCLUDED_EXT": 1
  }
}
```

Canonical reason-code groups:

- Skip reasons: `SKIP_HIDDEN`, `SKIP_EXCLUDED_DIR`, `SKIP_SENSITIVE`, `SKIP_GITIGNORED`, `SKIP_EXCLUDED_GLOB`, `SKIP_EXCLUDED_EXT`, `SKIP_UNREADABLE`, `SKIP_OVERSIZE`, `SKIP_OUTSIDE_ROOT`, `SKIP_MISSING`, `SKIP_NOT_FILE`, `SKIP_UNKNOWN` (fallback when a skip reason cannot be mapped to a specific code)
- Included-file outcomes: `OUTCOME_TRUNCATED`, `OUTCOME_REDACTED`, `OUTCOME_CONVERSION_WARNING`

## Security

See [SECURITY.md](SECURITY.md) for details on sensitive file handling.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidelines.

---

## Developer Guide

### Dev Setup

```bash
pip install uv
uv venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
uv pip install -e ".[dev,all]"
```

### Lint

```bash
ruff check .
ruff format .
```

The CI `lint` job runs `ruff check . && ruff format --check .` on every push and pull request.

### Running Tests

```bash
# Fast unit/smoke tests (excludes integration & slow markers; no coverage gate)
pytest -m "not integration and not slow" -o addopts=

# Full suite with branch coverage (gate: ≥ 98%)
pytest --cov=foldermix --cov-branch --cov-fail-under=98 tests/

# Integration/snapshot tests only (no coverage gate)
pytest -m integration -o addopts=

# Performance smoke test (opt-in via env var)
FOLDERMIX_RUN_PERF_SMOKE=1 pytest tests/test_perf_smoke.py -q -o addopts=

# Mutation testing (install extra first)
pip install -e ".[dev,mutation,all]"
python -m mutmut run
python -m mutmut results
```

### Test Suite Overview

| File | Marker | What it covers |
|------|--------|----------------|
| `test_cli.py` | — | CLI argument validation, config construction, `pack`/`list`/`stats`/`version` commands |
| `test_cli_entrypoint.py` | — | CLI entry-point smoke (`foldermix --help`) |
| `test_converters.py` | — | Converter registry: PDF, Office, markitdown, plain-text |
| `test_converters_fallback.py` | — | Fallback behaviour when optional extras are absent |
| `test_packer.py` | — | Core `packer.pack()` logic, error handling, oversize policy |
| `test_packer_edges.py` | — | Edge cases: symlinks, hidden files, max-file limits, report output |
| `test_scanner.py` | — | File scanner: gitignore, extension filters, glob patterns |
| `test_scanner_edge.py` | — | Scanner edge cases: circular symlinks, deeply nested dirs |
| `test_scanner_properties.py` | — | Hypothesis-based property tests for the scanner |
| `test_snapshot_guard.py` | — | Fast guard that snapshot fixtures in `tests/integration/fixtures/expected/` are in sync with the packer |
| `test_utils.py` | — | Utility helpers (redaction, frontmatter stripping, SHA-256) |
| `test_version_module.py` | — | `foldermix.__version__` is set and non-empty |
| `test_writers.py` | — | All three writer classes (Markdown, XML, JSONL) round-trip |
| `test_writers_edge.py` | — | Writer edge cases: empty bundles, special characters, large content |
| `test_render_homebrew_formula.py` | — | Formula renderer helpers |
| `test_perf_smoke.py` | `slow` | Packs 1,500 synthetic files; asserts wall-clock ≤ 25 s and peak RSS ≤ 256 MB |
| `integration/test_pack_outputs.py` | `integration` | Golden-file snapshot tests: Markdown, XML, JSONL output match fixture files |
| `integration/test_pack_outputs_structured.py` | `integration` | Structured assertions on actual pack output (TOC, SHA-256, XML structure) |
| `integration/test_converters_real_files.py` | `integration` | Real-file converter tests (PDF, docx, xlsx, pptx) |

Snapshot fixtures live in `tests/integration/fixtures/`:

```
tests/integration/fixtures/
├── simple_project/          # input tree used by snapshot tests
│   ├── alpha.md
│   ├── code.py
│   └── nested/
└── expected/                # golden output files
    ├── simple_project.md
    ├── simple_project.xml
    └── simple_project.jsonl
```

### CI Workflows

| Workflow file | Trigger | Jobs |
|---------------|---------|------|
| `ci.yml` | Every push / PR | `lint` → `smoke` (Python 3.10–3.12 on Ubuntu; Python 3.12 on macOS & Windows) → `minimal-deps` → `package-smoke` → `full` (coverage gate + Codecov) → `publish-pypi` → `update-homebrew-tap` → `release-consumer-smoke-pypi` + `release-consumer-smoke-homebrew` |
| `mutation.yml` | Weekly (Sat 09:00 UTC) + `workflow_dispatch` | `mutmut` on core source modules |
| `perf-smoke.yml` | Weekly (Sun 09:00 UTC) + `workflow_dispatch` | Performance smoke test (1,500 files, ≤ 25 s) |
| `security-audit.yml` | Weekly (Mon 09:00 UTC) + `pyproject.toml` changes + `workflow_dispatch` | `pip-audit` dependency vulnerability scan |

**`ci.yml` job details:**

- **`lint`** – Runs `ruff check` and `ruff format --check`.
- **`smoke`** – Runs unit/smoke tests (excludes `integration` and `slow` markers) across five OS/Python combinations.
- **`minimal-deps`** – Installs only `.[dev]` (no optional extras) and runs the core test files to confirm nothing is accidentally coupled to optional dependencies.
- **`package-smoke`** – Builds a wheel with `python -m build`, installs it in a clean venv, then exercises the CLI with black-box shell assertions.
- **`full`** – Runs the complete pytest suite with `--cov-report=xml` and uploads the coverage report to Codecov. Requires all earlier jobs to pass.
- **`publish-pypi`** – Runs only on pushes to `main`. Detects a version bump in `pyproject.toml` by comparing `HEAD` against `HEAD^`. If a bump is detected, builds and publishes to PyPI via OIDC trusted publishing.
- **`update-homebrew-tap`** – Runs after a successful `publish-pypi`. Calls `scripts/render_homebrew_formula.py` to generate a new Homebrew formula and pushes it to `shaypal5/homebrew-tap` using the `HOMEBREW_TAP_GITHUB_TOKEN` secret.
- **`release-consumer-smoke-pypi`** – Runs on release publish pushes (`main` + version bump). Installs `foldermix==<released_version>` from PyPI on Linux and runs black-box `version`/`list`/`pack` checks.
- **`release-consumer-smoke-homebrew`** – Runs on release publish pushes after tap update. Installs from `shaypal5/tap` on macOS and runs black-box `version`/`list`/`pack` checks.
- Both release-consumer jobs upload diagnostic artifacts (`release-consumer-logs`) to simplify install/runtime failure triage.

### Release PR Process

A release is triggered by merging a PR to `main` that bumps the `version` field in `pyproject.toml`. The following checklist describes a complete release PR:

1. **Bump the version** in `pyproject.toml`:
   ```toml
   [project]
   version = "X.Y.Z"
   ```

2. **Update snapshot fixtures** if any packer output has changed:
   - Run the integration tests locally to detect fixture drift:
     ```bash
     pytest -m integration
     ```
   - If `test_pack_outputs.py` or `test_snapshot_guard.py` fail with a diff, copy the fresh output from a passing local run into `tests/integration/fixtures/expected/` and commit the updated fixtures as part of the same PR.

3. **Run the full test suite** locally and confirm all tests pass:
   ```bash
   pytest --cov=foldermix tests/
   ```

4. **Open the PR** targeting `main` and wait for all CI jobs to pass.

5. **Merge to `main`**. The `publish-pypi` job will detect the version bump, build the wheel, and publish to PyPI automatically. The `update-homebrew-tap` job will then update the Homebrew formula, and release-consumer smoke jobs will validate fresh installs from both PyPI and Homebrew.

> **Note:** If `HOMEBREW_TAP_GITHUB_TOKEN` is not configured the tap-update step is silently skipped. Configure it as a repository secret with write access to `shaypal5/homebrew-tap` before the first release.

## License

See [LICENSE](LICENSE).
