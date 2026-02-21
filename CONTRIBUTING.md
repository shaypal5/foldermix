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
pytest --cov=folderpack tests/
```
