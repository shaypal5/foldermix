# foldermix

**Pack a folder into a single LLM-friendly context file.**

[![CI](https://github.com/foldermix/foldermix/actions/workflows/ci.yml/badge.svg)](https://github.com/foldermix/foldermix/actions/workflows/ci.yml)

## Installation

```bash
pip install foldermix
# With optional extras:
pip install "foldermix[all]"   # adds PDF, Office, tqdm
pip install "foldermix[pdf]"   # pypdf only
pip install "foldermix[office]" # docx/xlsx/pptx support
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

# Show version
foldermix version
```

## Features

- **Multiple output formats**: Markdown, XML, JSONL
- **Smart filtering**: gitignore support, extension filters, glob patterns
- **Sensitive file protection**: Automatically skips `.env`, keys, certificates
- **Optional converters**: PDF (pypdf), Office docs (python-docx, openpyxl, python-pptx), markitdown
- **Redaction**: Email and phone number redaction via `--redact`
- **SHA-256 checksums** per file
- **Parallel processing** with configurable workers
- **Table of contents** in Markdown output

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
```

## Security

See [SECURITY.md](SECURITY.md) for details on sensitive file handling.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

See [LICENSE](LICENSE).
