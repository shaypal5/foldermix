# Contributing

## Dev Setup

```bash
pip install uv
uv venv
source .venv/bin/activate
uv pip install -e ".[dev,all]"
```

## Lint

```bash
ruff check .
ruff format .
```

## Test

```bash
pytest -q
pytest --cov=foldermix tests/
```

## Mutation Test (Batch 4)

```bash
pip install -e ".[dev,mutation,all]"
python -m mutmut run
python -m mutmut results
```

## Performance Smoke Test

```bash
FOLDERMIX_RUN_PERF_SMOKE=1 python -m pytest tests/test_perf_smoke.py -q -o addopts=
```

## Homebrew Release Automation

On `main` pushes that bump `pyproject.toml` version:

1. `publish-pypi` publishes to PyPI (trusted publisher).
2. `update-homebrew-tap` renders `Formula/foldermix.rb` and pushes it to the tap repo.

Required one-time setup:

- Create tap repo: `shaypal5/homebrew-tap`.
- Add Actions secret in this repo:
  - `HOMEBREW_TAP_GITHUB_TOKEN`: classic PAT (or fine-grained token) with write access to the tap repo.
