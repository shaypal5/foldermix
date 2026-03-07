# foldermix Docs

`foldermix` packs a directory into a single LLM-friendly context file. The v1 docs site is intentionally one page: enough to install the tool, run it immediately, and find the core commands without reading the full README end to end.

## What It Does

Use `foldermix` when you want to turn a folder of text and document files into one context artifact for an LLM workflow.

Core capabilities:
- pack a folder into `md`, `xml`, or `jsonl`
- preview what will be included or skipped before packing
- handle optional PDF and Office converters when installed
- emit a machine-readable report for audits and cleanup workflows

## Install

### Core install

```bash
pip install foldermix
```

### Homebrew

```bash
brew tap foldermix/foldermix
brew install foldermix
```

Homebrew installs the core feature set only.

### Full optional converter support

```bash
# uv (recommended)
uv tool install "foldermix[all,markitdown]"

# pipx
pipx install "foldermix[all,markitdown]"
```

Optional extras:
- `pdf`: native PDF text extraction
- `ocr`: OCR fallback for textless PDFs
- `office`: `docx` / `xlsx` / `pptx`
- `markitdown`: additional converter support

## Super Quick Start

Run this from the folder you want to pack:

```bash
foldermix pack . --out context.md
```

This writes one Markdown bundle to `./context.md`.

Defaults worth knowing:
- default output format is Markdown (`md`)
- if you omit `--out`, `foldermix` writes a timestamped Markdown file such as `foldermix_20260307_120000.md`

## Core Commands

### `pack`

```bash
foldermix pack PATH [--out FILE] [--format md|xml|jsonl]
```

Use `pack` to create the final bundle.

Common flags:
- `--report report.json`: write a machine-readable report
- `--dedupe-content`: skip later exact-duplicate files by content hash
- `--include-ext`, `--exclude-ext`, `--exclude-dirs`, `--exclude-glob`
- `--pdf-ocr`: enable OCR fallback when OCR dependencies are installed

### `list`

```bash
foldermix list PATH
```

Shows which files would be included by the current pack-style filtering rules.

### `skiplist`

```bash
foldermix skiplist PATH
```

Shows which files would be skipped and why.

### `stats`

```bash
foldermix stats PATH
```

Shows extension and byte-size statistics for the selected tree.

### `version`

```bash
foldermix version
```

Prints the installed version.

## Common Workflows

### Config-first project workflow

```bash
foldermix init --profile engineering-docs
foldermix pack . --config foldermix.toml --format md --out context.md --report report.json
```

### Research corpus batch run

```bash
find ./corpus -type f -print0 | foldermix pack ./corpus --config foldermix.toml --stdin --null --format jsonl --out research-context.jsonl --report research-report.json
```

### Course refresh bundle

```bash
foldermix init --profile course-refresh --out foldermix.toml --force
foldermix pack ./previous-course --config foldermix.toml --format md --out course-refresh-context.md --report course-refresh-report.json
```

### Duplicate cleanup before LLM ingestion

```bash
foldermix pack ./corpus --format md --out deduped-context.md --report dedupe-report.json --dedupe-content
```

## Optional Dependency Guidance

Choose the install method based on the workflow:
- Homebrew: fastest system install, core features only
- `uv tool`: best isolated global install with extras
- `pipx`: similar isolated global install if you already use pipx
- virtualenv + pip: project-specific environments

If you already installed via Homebrew and later need extras, uninstall the Homebrew package and reinstall via `uv tool`, `pipx`, or a virtualenv.

## Build And Publish

This docs site is built with MkDocs and published to GitHub Pages.

Local build:

```bash
pip install -e ".[docs]"
mkdocs serve
mkdocs build --strict
```

Publish path:
- the `docs-site.yml` workflow builds on pull requests
- pushes to `main` deploy the site to GitHub Pages

## More Detailed Docs

This site is intentionally concise. For deeper details, use:
- [README](https://github.com/shaypal5/foldermix/blob/main/README.md)
- [Config-first workflows](https://github.com/shaypal5/foldermix/blob/main/docs/config-first-workflows.md)
- [Compliance and safety](https://github.com/shaypal5/foldermix/blob/main/docs/compliance-safety.md)
- [Contributing](https://github.com/shaypal5/foldermix/blob/main/CONTRIBUTING.md)
