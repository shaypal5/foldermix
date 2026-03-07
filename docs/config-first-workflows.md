# Config-First Local Workflows

This guide shows a config-first workflow for local folders and mixed document sets.

## 1) Bootstrap a Profile

Generate a starter `foldermix.toml` using one of the built-in profiles:

```bash
foldermix init --profile legal
foldermix init --profile research --out ./configs/foldermix.toml
foldermix init --profile support --force
foldermix init --profile engineering-docs --out ./foldermix.toml --force
foldermix init --profile course-refresh --out ./foldermix.toml --force
```

Available profiles:

- `legal`: privacy-first defaults, full redaction, OCR enabled.
- `research`: broad file coverage, email redaction, OCR enabled.
- `support`: operational formats, full redaction, OCR disabled.
- `engineering-docs`: docs/code handoff defaults, no redaction, frontmatter stripping.
- `course-refresh`: teaching-material bundle defaults with exclusions for grades, rosters, responses, feedback, submissions, and other student/admin paths.

## 2) Understand Resolution Order

Effective options are deterministic:

1. Built-in defaults
2. `foldermix.toml` (explicit `--config` or discovered by walking upward from target path)
3. Explicit CLI flags

Print merged config (including value source per key):

```bash
foldermix pack . --config foldermix.toml --print-effective-config
foldermix list . --config foldermix.toml --print-effective-config
foldermix stats . --config foldermix.toml --print-effective-config
```

Section guidance:

- put file-selection settings used by `pack`, `list`, and `skiplist` under `[pack]`
- keep `[stats]` for stats-specific defaults

## 3) Preview Before Pack

```bash
foldermix list . --config foldermix.toml
foldermix stats . --config foldermix.toml
```

## 4) Pack with Structured Report Output

```bash
foldermix pack . --config foldermix.toml --format md --out context.md --report report.json
```

The report includes machine-actionable reason codes:

- skip codes such as `SKIP_EXCLUDED_EXT`, `SKIP_MISSING`, `SKIP_OUTSIDE_ROOT`
- included-file outcome codes such as `OUTCOME_TRUNCATED`, `OUTCOME_REDACTED`, `OUTCOME_CONVERSION_WARNING`

## 5) Batch Input Pipelines (`--stdin`, `--null`)

Newline-delimited file list:

```bash
printf 'a.txt\nnested/b.txt\n' | foldermix pack . --config foldermix.toml --stdin --format jsonl --out context.jsonl
```

NUL-delimited file list (for `find -print0`):

```bash
find . -type f -print0 | foldermix pack . --config foldermix.toml --stdin --null --format md --out context.md
```

The same stdin modes are available for preview commands:

```bash
find . -type f -print0 | foldermix list . --config foldermix.toml --stdin --null
find . -type f -print0 | foldermix stats . --config foldermix.toml --stdin --null
```

## 6) Use-Case Recipes

### Legal

```bash
foldermix init --profile legal --out foldermix.toml --force
foldermix pack ./matter --config foldermix.toml --format md --out legal-context.md --report legal-report.json
```

### Research

```bash
foldermix init --profile research --out foldermix.toml --force
find ./corpus -type f -print0 | foldermix pack ./corpus --config foldermix.toml --stdin --null --format jsonl --out research-context.jsonl --report research-report.json
```

### Support

```bash
foldermix init --profile support --out foldermix.toml --force
printf 'tickets/a.md\ntickets/b.log\n' | foldermix pack . --config foldermix.toml --stdin --format md --out support-context.md --report support-report.json
```

### Course Refresh

```bash
foldermix init --profile course-refresh --out foldermix.toml --force
foldermix pack ./previous-course --config foldermix.toml --format md --out course-refresh-context.md --report course-refresh-report.json
```

Default exclusions in the `course-refresh` profile target common course-admin noise:

- grades
- rosters
- responses
- feedback
- submissions
- student-specific folders/files

## Troubleshooting

- `--null` fails:
  - `--null` requires `--stdin`.
- Missing expected files:
  - run `foldermix list` first; check hidden defaults, extension/glob filters, `.gitignore`, and sensitive-file skip rules.
- Converter warnings or import errors:
  - install relevant extras:
    - `pip install "foldermix[pdf]"`
    - `pip install "foldermix[ocr]"`
    - `pip install "foldermix[office]"`
- Unexpected effective values:
  - print merged config with `--print-effective-config`.
