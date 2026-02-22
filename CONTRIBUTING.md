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
