# Homebrew/Core Preparation Guide

This guide is for the `homebrew/core` path, not the existing custom tap flow.

## Current state

`foldermix` already supports a custom tap release flow:

- PyPI publish happens from the main repo CI.
- `scripts/render_homebrew_formula.py` renders a Python virtualenv formula.
- `update-homebrew-tap` pushes that formula to `foldermix/homebrew-foldermix`.

That is enough for:

```bash
brew tap foldermix/foldermix
brew install foldermix
```

It is not enough for a clean-machine:

```bash
brew install foldermix
```

That command requires the formula to be merged into `Homebrew/homebrew-core`.

## Current blocker

As of 2026-03-09, the public GitHub repo metadata for `foldermix/foldermix` is:

- Stars: 0
- Forks: 0
- Watchers: 0

That makes `foldermix` a weak candidate for `homebrew/core` right now. Homebrew generally expects a project to be a known tool with evidence of adoption and an ongoing maintenance signal. Until the project has stronger public usage, the likely result is that a core PR is declined even if the formula is technically valid.

## What already looks good

- The package is a pure-Python CLI with a small core dependency set.
- The runtime dependencies are lightweight: `click`, `typer`, `pathspec`, `rich`, plus `tomli` only on Python `< 3.11`.
- The existing formula renderer intentionally excludes optional extras and produces a `virtualenv_install_with_resources` formula, which is the right direction for a Python CLI in Homebrew.
- The formula test already exercises the installed CLI with a real `pack` invocation.

## What to keep out of the core formula

Do not try to submit the full optional feature set to `homebrew/core`.

Keep the formula limited to the core CLI dependency set only. In this repo, that means:

- No `pdf` extra
- No `ocr` extra
- No `office` extra
- No `markitdown` extra

The current tap policy already matches this and should stay that way.

## Pre-submission checklist

Use this checklist before opening any PR to `homebrew/core`.

- Confirm the project has real public usage signals.
- Confirm the project name and formula name should both be `foldermix`.
- Confirm the package is published to PyPI as an sdist and not wheel-only.
- Confirm the core dependency graph stays pure Python.
- Confirm there are no Rust, Go, Node, or vendored binary build requirements in runtime dependencies.
- Confirm the CLI works with only core dependencies installed.
- Confirm the formula test does not require network, secrets, or large fixtures.
- Confirm the repo README documents that Homebrew installs the core-only feature set.
- Confirm the license metadata remains machine-readable and correct.

## Local formula generation

Render a candidate formula from the current published PyPI release:

```bash
python scripts/render_homebrew_formula.py --version 0.1.20 --output /tmp/foldermix.rb
```

Review the output and check for:

- `class Foldermix < Formula`
- `include Language::Python::Virtualenv`
- `depends_on "python@3.12"`
- resource blocks only for the core runtime dependencies
- `virtualenv_install_with_resources`
- a minimal `test do` block that runs offline

## Local homebrew/core validation

Clone `Homebrew/homebrew-core` locally and test the candidate formula inside that checkout.

Example workflow:

```bash
git clone https://github.com/Homebrew/homebrew-core.git /tmp/homebrew-core
python scripts/render_homebrew_formula.py \
  --version 0.1.20 \
  --output /tmp/homebrew-core/Formula/f/foldermix.rb

cd /tmp/homebrew-core
brew style Formula/f/foldermix.rb
brew audit --strict --online --new Formula/f/foldermix.rb
HOMEBREW_NO_INSTALL_FROM_API=1 brew install --build-from-source Formula/f/foldermix.rb
brew test foldermix
```

Notes:

- Use the formula path under `Formula/f/` when testing in a `homebrew/core` checkout.
- `brew audit --strict --online --new` is the important gate for new formulae.
- `brew test foldermix` should pass without internet access.

## Review checklist for the rendered formula

- Description is concise and matches the package purpose.
- Homepage points to the public project repo.
- `url` points to the published PyPI sdist.
- `sha256` matches the sdist.
- The formula does not reference the custom tap repo.
- The formula does not install optional extras.
- The formula does not add unnecessary `depends_on` entries.
- The test creates a tiny input tree and verifies the installed binary.

## Submission checklist

- Wait until the project has stronger public adoption signals.
- Re-render the formula from the latest published release.
- Run `brew style`, `brew audit`, `brew install --build-from-source`, and `brew test` successfully.
- Open a PR against `Homebrew/homebrew-core`.
- In the PR description, explain that `foldermix` is the core-only CLI packaging path and that optional converters remain outside the formula.
- Be prepared to justify why `foldermix` belongs in `homebrew/core` instead of only a custom tap.

## If the core PR is rejected

Do not contort the package to force a core submission.

The fallback is the current supported path:

```bash
brew install foldermix/foldermix/foldermix
```

Or, after a one-time tap:

```bash
brew tap foldermix/foldermix
brew install foldermix
```
