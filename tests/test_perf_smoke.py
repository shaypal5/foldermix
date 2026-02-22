from __future__ import annotations

import json
import os
import time
import tracemalloc
from pathlib import Path

import pytest

from foldermix import packer
from foldermix.config import PackConfig


def _build_large_tree(root: Path, file_count: int) -> None:
    for i in range(file_count):
        subdir = root / f"dir_{i % 40:02d}" / f"shard_{i % 10:02d}"
        subdir.mkdir(parents=True, exist_ok=True)
        payload = f"file-{i:05d}\n".encode() + (b"x" * 192) + b"\n"
        (subdir / f"file_{i:05d}.txt").write_bytes(payload)


@pytest.mark.slow
def test_pack_large_tree_performance_smoke(tmp_path: Path) -> None:
    """Guard against major runtime/memory regressions on medium-large trees."""
    if os.getenv("FOLDERMIX_RUN_PERF_SMOKE", "").strip() != "1":
        pytest.skip("Set FOLDERMIX_RUN_PERF_SMOKE=1 to enable perf smoke test.")

    file_count = int(os.getenv("FOLDERMIX_PERF_FILE_COUNT", "1500"))
    max_seconds = float(os.getenv("FOLDERMIX_PERF_MAX_SECONDS", "25.0"))
    max_peak_mb = float(os.getenv("FOLDERMIX_PERF_MAX_PEAK_MB", "256.0"))

    root = tmp_path / "large_tree"
    root.mkdir()
    _build_large_tree(root, file_count)

    out_path = tmp_path / "perf.jsonl"
    report_path = tmp_path / "perf_report.json"
    config = PackConfig(
        root=root,
        out=out_path,
        format="jsonl",
        include_sha256=False,
        workers=4,
        report=report_path,
    )

    tracemalloc.start()
    start = time.perf_counter()
    try:
        packer.pack(config)
        elapsed = time.perf_counter() - start
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["included_count"] == file_count
    assert report["skipped_count"] == 0
    assert out_path.exists() and out_path.stat().st_size > 0

    peak_mb = peak / (1024 * 1024)
    assert elapsed <= max_seconds, (
        f"pack() took {elapsed:.2f}s (limit {max_seconds:.2f}s) for {file_count} files"
    )
    assert peak_mb <= max_peak_mb, (
        f"pack() peak tracemalloc was {peak_mb:.1f} MiB (limit {max_peak_mb:.1f} MiB)"
    )
