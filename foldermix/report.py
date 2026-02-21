from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class ReportData:
    included_count: int
    skipped_count: int
    total_bytes: int
    included_files: list[dict]
    skipped_files: list[dict]


def write_report(report_path: Path, data: ReportData) -> None:
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(asdict(data), f, indent=2)
