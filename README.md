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
brew tap foldermix/foldermix
brew install foldermix
```

## Quick Start (Config-First)

`foldermix` is designed around a checked-in (or local) `foldermix.toml`, then command-level overrides only when needed.

1. Bootstrap a starter config for your use case:

```bash
foldermix init --profile engineering-docs
```

2. Inspect the merged effective config (defaults -> TOML -> CLI) before packing:

```bash
foldermix pack . --config foldermix.toml --print-effective-config
```

3. Preview what will be included:

```bash
foldermix list . --config foldermix.toml
foldermix stats . --config foldermix.toml
```

4. Run the pack and emit a machine-readable report:

```bash
foldermix pack . --config foldermix.toml --format md --out context.md --report report.json
```

5. Use explicit file-list pipelines for batch workflows:

```bash
# Newline-delimited
printf 'a.txt\nnotes/b.txt\n' | foldermix pack . --config foldermix.toml --stdin --format jsonl --out context.jsonl

# NUL-delimited (find -print0 compatible)
find . -type f -print0 | foldermix pack . --config foldermix.toml --stdin --null --format md --out context.md
```

6. Show installed version:

```bash
foldermix version
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

## Workflow Recipes

Use these end-to-end patterns as starting points for local-folder runs.

### Legal Review Bundle

```bash
foldermix init --profile legal --out foldermix.toml --force
foldermix pack ./matter --config foldermix.toml --format md --out legal-context.md --report legal-report.json
```

### Research Corpus Bundle (Batch Input)

```bash
foldermix init --profile research --out foldermix.toml --force
find ./corpus -type f -print0 | foldermix pack ./corpus --config foldermix.toml --stdin --null --format jsonl --out research-context.jsonl --report research-report.json
```

### Support Incident Bundle (Explicit Path List)

```bash
foldermix init --profile support --out foldermix.toml --force
printf 'tickets/a.md\ntickets/b.log\n' | foldermix pack . --config foldermix.toml --stdin --format md --out support-context.md --report support-report.json
```

For a longer config-first walkthrough, see [docs/config-first-workflows.md](docs/config-first-workflows.md).

## Command Reference

```
foldermix pack [OPTIONS] [PATH]

Options:
  --config PATH                 Path to foldermix TOML config file
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
  --fail-on-policy-violation / --no-fail-on-policy-violation  Fail command when policy findings meet threshold [default: disabled]
  --policy-fail-level TEXT     Minimum severity for policy-failure threshold: low, medium, high, critical [default: low]
  --policy-dry-run / --no-policy-dry-run  Evaluate policy outcomes without writing packed output [default: disabled]
  --policy-output TEXT          Policy dry-run output format: text, json [default: text]
  --stdin                        Read explicit file paths from standard input instead of recursive scanning
  --null                         Parse stdin as NUL-delimited paths (for find -print0); requires --stdin
  --print-effective-config       Print merged effective config with value sources and exit
```

Additional commands:

```text
foldermix list [OPTIONS] [PATH]
  --config PATH
  --include-ext TEXT
  --exclude-ext TEXT
  --hidden
  --respect-gitignore / --no-respect-gitignore
  --stdin
  --null
  --print-effective-config

foldermix stats [OPTIONS] [PATH]
  --config PATH
  --include-ext TEXT
  --hidden
  --stdin
  --null
  --print-effective-config

foldermix init --profile <legal|research|support|engineering-docs> [--out PATH] [--force]

foldermix version
```

## Report Schema

`--report` writes a versioned schema with machine-actionable reason codes and policy findings while preserving existing human-readable fields.

- Current schema: `schema_version = 5`
- Compatibility policy:
  - Existing keys are preserved (`included_count`, `skipped_count`, `total_bytes`, `included_files`, `skipped_files`).
  - New top-level fields are additive (`schema_version`, `reason_code_counts`, `warning_code_counts`, `redaction_summary`, `policy_findings`, `policy_finding_counts`).
  - New per-entry fields are additive (`reason_code`, `message`, `outcome_codes`, `warning_codes`, `outcomes`, `redaction`).

Example `report.json` shape:

```json
{
  "schema_version": 5,
  "included_count": 2,
  "skipped_count": 1,
  "total_bytes": 1234,
  "included_files": [
    {
      "path": "big.txt",
      "size": 900,
      "ext": ".txt",
      "outcome_codes": ["OUTCOME_TRUNCATED", "OUTCOME_REDACTED"],
      "warning_codes": [],
      "outcomes": [
        {"code": "OUTCOME_TRUNCATED", "message": "File content was truncated to satisfy --max-bytes."},
        {"code": "OUTCOME_REDACTED", "message": "Content was redacted using mode 'emails'."}
      ],
      "redaction": {
        "mode": "emails",
        "event_count": 2,
        "categories": ["emails"]
      }
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
  },
  "warning_code_counts": {},
  "redaction_summary": {
    "mode": "emails",
    "files_with_redactions": 1,
    "event_count": 2,
    "categories": ["emails"]
  },
  "policy_findings": [
    {
      "rule_id": "convert-secret",
      "severity": "high",
      "action": "deny",
      "stage": "convert",
      "path": "notes.txt",
      "reason_code": "POLICY_CONTENT_REGEX_MATCH",
      "message": "Secret marker detected"
    }
  ],
  "policy_finding_counts": {
    "total": 1,
    "by_severity": {"high": 1},
    "by_action": {"deny": 1},
    "by_reason_code": {"POLICY_CONTENT_REGEX_MATCH": 1}
  }
}
```

Canonical reason-code groups:

- Skip reasons: `SKIP_HIDDEN`, `SKIP_EXCLUDED_DIR`, `SKIP_SENSITIVE`, `SKIP_GITIGNORED`, `SKIP_EXCLUDED_GLOB`, `SKIP_EXCLUDED_EXT`, `SKIP_UNREADABLE`, `SKIP_OVERSIZE`, `SKIP_OUTSIDE_ROOT`, `SKIP_MISSING`, `SKIP_NOT_FILE`, `SKIP_UNKNOWN` (fallback when a skip reason cannot be mapped to a specific code)
- Included-file outcomes: `OUTCOME_TRUNCATED`, `OUTCOME_REDACTED`, `OUTCOME_CONVERSION_WARNING`
- Warning taxonomy codes:
  `encoding_fallback`, `converter_unavailable`, `ocr_disabled`, `ocr_dependencies_missing`, `ocr_initialization_failed`, `ocr_failed`, `ocr_no_text`, `unclassified_warning`
- Policy finding reason codes: `POLICY_RULE_MATCH`, `POLICY_SKIP_REASON_MATCH`, `POLICY_CONTENT_REGEX_MATCH`, `POLICY_FILE_SIZE_EXCEEDED`, `POLICY_TOTAL_BYTES_EXCEEDED`, `POLICY_FILE_COUNT_EXCEEDED`

Redaction traceability semantics:

- Per file (`included_files[].redaction`):
  - `mode`: configured redaction mode for the run (`none`, `emails`, `phones`, `all`)
  - `event_count`: number of replacements applied for that file
  - `categories`: redaction categories that matched (`emails`, `phones`)
- Run summary (`redaction_summary`):
  - `mode`: run-level mode (or `mixed` if inconsistent input is provided)
  - `files_with_redactions`: count of files where `event_count > 0`
  - `event_count`: total replacements across all included files
  - `categories`: union of categories matched across included files

## Policy Engine Core

`foldermix` supports rule-based policy evaluation during scan, convert, and pack summary phases.

Use `foldermix.toml` (`[pack]`) to define rules:

```toml
[[pack.policy_rules]]
rule_id = "convert-secret"
description = "Detect secret-like markers in converted content"
stage = "convert" # scan | convert | pack | any
severity = "high" # low | medium | high | critical
action = "deny"   # warn | deny
content_regex = "SECRET_[0-9]+"
```

Each rule must include at least one matcher key:
`path_glob`, `ext_in`, `skip_reason_in`, `content_regex`, `max_size_bytes`, `max_total_bytes`, or `max_file_count`.

### Built-in Policy Packs

Use `--policy-pack` to apply a built-in rule bundle:

```bash
foldermix pack . --policy-pack strict-privacy --report report.json
```

Or persist it in `foldermix.toml`:

```toml
[pack]
policy_pack = "strict-privacy" # strict-privacy | legal-hold | customer-support
```

Pack intents and tradeoffs:

- `strict-privacy`:
  prioritize deny-level findings for direct PII/secret markers; higher false-positive tolerance.
- `legal-hold`:
  advisory warnings for legal-retention signals (privileged/destruction markers, hidden-scan coverage).
- `customer-support`:
  advisory findings focused on contact PII and log-like support artifacts.

`policy_pack` rules are combined with explicit `policy_rules` (pack rules first, then custom rules).
Unknown pack names fail with a clear validation error.

### Policy Enforcement Flags (CI/Automation)

Enable deterministic policy-based failure in automation:

```bash
foldermix pack . \
  --policy-pack strict-privacy \
  --fail-on-policy-violation \
  --policy-fail-level high \
  --report report.json
```

Semantics:

- `--fail-on-policy-violation` enables enforcement mode.
- Only policy findings with `action = "deny"` are enforcement-failing.
- `--policy-fail-level` sets the minimum severity for those deny findings (`low`, `medium`, `high`, `critical`).
- Findings are still reported in terminal summary and `--report` output before exiting.
- Enforcement failures exit with code `4`.

### Policy Dry-Run / Explain Mode

Preview policy impact without writing a packed output bundle:

```bash
foldermix pack . \
  --policy-pack strict-privacy \
  --policy-dry-run
```

For machine-readable automation output:

```bash
foldermix pack . \
  --policy-pack strict-privacy \
  --policy-dry-run \
  --policy-output json
```

Semantics:

- `--policy-dry-run` executes scan/convert/pack policy evaluation but skips bundle write.
- Text mode prints a deterministic summary and affected-file list.
- `--policy-output json` emits a deterministic JSON payload to stdout for CI/automation.
- `--policy-output` requires `--policy-dry-run`.
- `--dry-run` and `--policy-dry-run` are mutually exclusive.

## Troubleshooting

- `--null` requires `--stdin`
  - `--null` is only valid when reading explicit paths from standard input.
- `No module named ...` or converter-specific warnings for PDF/Office/OCR
  - install matching extras, for example: `pip install "foldermix[pdf]"`, `pip install "foldermix[ocr]"`, or `pip install "foldermix[office]"`.
- Expected files are missing from output
  - run `foldermix list . --config foldermix.toml` first to inspect skip behavior.
  - check `.gitignore`, hidden-path defaults, extension/glob filters, and sensitive-file protection.
- Need to see exactly which layer set each value
  - use `--print-effective-config` on `pack`, `list`, or `stats`.
- `stdin` path list includes files outside target root
  - these are skipped with structured reason codes (for example `SKIP_OUTSIDE_ROOT`) and included in `--report`.

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
- **`update-homebrew-tap`** – Runs after a successful `publish-pypi`. Calls `scripts/render_homebrew_formula.py` to generate a new Homebrew formula and pushes it to `foldermix/homebrew-foldermix` using the `HOMEBREW_TAP_GITHUB_TOKEN` secret.
- **`release-consumer-smoke-pypi`** – Runs on release publish pushes (`main` + version bump). Installs `foldermix==<released_version>` from PyPI on Linux and runs black-box `version`/`list`/`pack` checks.
- **`release-consumer-smoke-homebrew`** – Runs on release publish pushes after tap update. Installs from `foldermix/foldermix` on macOS and runs black-box `version`/`list`/`pack` checks.
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

5. **Merge to `main`**. The `publish-pypi` job will detect the version bump, build the wheel, and publish to PyPI automatically. The `update-homebrew-tap` job will then update the Homebrew formula, and release-consumer smoke jobs will validate fresh installs from PyPI and, when tap credentials are configured, from Homebrew.

> **Note:** If `HOMEBREW_TAP_GITHUB_TOKEN` is not configured, both tap update and Homebrew release-consumer smoke are skipped. Configure it as a repository secret with write access to `foldermix/homebrew-foldermix` before the first release.

## License

See [LICENSE](LICENSE).
