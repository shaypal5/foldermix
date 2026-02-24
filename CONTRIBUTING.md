# Contributing

For a full developer guide including test overview, CI workflow details, and release PR process, see the [Developer Guide](README.md#developer-guide) section in the README.

## Dev Setup

```bash
pip install uv
uv venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
uv pip install -e ".[dev,all]"
```

## Lint

```bash
ruff check .
ruff format .
```

## Test

```bash
# Fast unit/smoke tests
pytest -m "not integration and not slow"

# Full suite with coverage
pytest --cov=foldermix tests/

# Integration/snapshot tests
pytest -m integration
```

## Mutation Test

```bash
pip install -e ".[dev,mutation,all]"
python -m mutmut run
python -m mutmut results
```

## Performance Smoke Test

```bash
FOLDERMIX_RUN_PERF_SMOKE=1 python -m pytest tests/test_perf_smoke.py -q -o addopts=
```

## Release PR Process

1. Bump `version` in `pyproject.toml`.
2. If packer output changed, regenerate snapshot fixtures in `tests/integration/fixtures/expected/` and commit them in the same PR.
3. Run `pytest --cov=foldermix tests/` locally and confirm all tests pass.
4. Open a PR targeting `main`; merge once all CI jobs pass.

On merge, `publish-pypi` detects the version bump and publishes to PyPI automatically; `update-homebrew-tap` then updates the Homebrew formula.

See the [Release PR Process](README.md#release-pr-process) section in the README for the full checklist.

## Homebrew Release Automation

On `main` pushes that bump `pyproject.toml` version:

1. `publish-pypi` publishes to PyPI (OIDC trusted publisher).
2. `update-homebrew-tap` renders `Formula/foldermix.rb` and pushes it to the tap repo.

Required one-time setup:

- Create tap repo: `shaypal5/homebrew-tap`.
- Add Actions secret in this repo:
  - `HOMEBREW_TAP_GITHUB_TOKEN`: classic PAT (or fine-grained token) with write access to the tap repo.

## AI Coding Agent Guide

See [docs/agents.md](docs/agents.md) for a detailed orientation for AI coding agents working on this repository.
