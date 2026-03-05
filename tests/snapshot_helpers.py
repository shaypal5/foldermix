from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

from foldermix import packer
from foldermix.config import PackConfig

FIXED_MTIME = 1704067200  # 2024-01-01T00:00:00+00:00
FIXED_NOW_ISO = "2024-01-02T00:00:00+00:00"
_TEXT_FIXTURE_EXTS = {".md", ".py", ".txt"}
_POLICY_CROSS_PLATFORM_RULES: list[dict[str, object]] = [
    {
        "rule_id": "scan-excluded-ext",
        "description": "Flag excluded extension skips",
        "stage": "scan",
        "skip_reason_in": ["excluded_ext"],
        "severity": "low",
        "action": "warn",
    },
    {
        "rule_id": "scan-sensitive-file",
        "description": "Flag sensitive file skips",
        "stage": "scan",
        "skip_reason_in": ["sensitive"],
        "severity": "high",
        "action": "deny",
    },
    {
        "rule_id": "convert-secret-marker",
        "description": "Flag secret markers in converted text",
        "stage": "convert",
        "content_regex": r"SECRET_[0-9]+",
        "severity": "high",
        "action": "deny",
    },
    {
        "rule_id": "convert-crlf-token",
        "description": "Ensure CRLF fixture content is matched deterministically",
        "stage": "convert",
        "content_regex": "CRLF_TOKEN",
        "severity": "medium",
        "action": "warn",
    },
    {
        "rule_id": "convert-path-space",
        "description": "Paths with spaces stay matchable with POSIX-style separators",
        "stage": "convert",
        "path_glob": "nested folder/*.txt",
        "severity": "low",
        "action": "warn",
    },
    {
        "rule_id": "pack-max-file-count",
        "description": "Pack summary captures file-count threshold findings",
        "stage": "pack",
        "max_file_count": 3,
        "severity": "medium",
        "action": "warn",
    },
]


def set_fixed_mtime(root: Path) -> None:
    for p in root.rglob("*"):
        if p.is_file():
            os.utime(p, (FIXED_MTIME, FIXED_MTIME))


def normalize_fixture_newlines_to_lf(root: Path) -> None:
    """Avoid CRLF checkout differences changing snapshot byte counts on Windows."""
    for p in root.rglob("*"):
        if not p.is_file() or p.suffix.lower() not in _TEXT_FIXTURE_EXTS:
            continue
        raw = p.read_bytes()
        normalized = raw.replace(b"\r\n", b"\n")
        if normalized != raw:
            p.write_bytes(normalized)


def normalize_root_path(text: str, project_dir: Path) -> str:
    """Normalize root path placeholders for plain and JSON-escaped path forms."""
    raw_root = str(project_dir)
    normalized = text.replace(raw_root, "__ROOT__")
    escaped_root = raw_root.replace("\\", "\\\\")
    if escaped_root != raw_root:
        normalized = normalized.replace(escaped_root, "__ROOT__")
    return normalized


def render_simple_project_snapshot(
    base_tmp: Path,
    fixture_dir: Path,
    fmt: str,
    out_name: str,
    monkeypatch,
) -> str:
    base_tmp.mkdir(parents=True, exist_ok=True)
    src = fixture_dir / "simple_project"
    project_dir = base_tmp / "simple_project"
    shutil.copytree(src, project_dir)
    normalize_fixture_newlines_to_lf(project_dir)
    set_fixed_mtime(project_dir)

    monkeypatch.setattr(packer, "utcnow_iso", lambda: FIXED_NOW_ISO)
    out_path = base_tmp / out_name
    config = PackConfig(
        root=project_dir,
        out=out_path,
        format=fmt,
        include_sha256=False,
        workers=1,
    )
    packer.pack(config)

    return normalize_root_path(out_path.read_text(encoding="utf-8"), project_dir)


def render_policy_cross_platform_report(base_tmp: Path, fixture_dir: Path) -> dict[str, object]:
    base_tmp.mkdir(parents=True, exist_ok=True)
    src = fixture_dir / "policy_cross_platform_corpus"
    project_dir = base_tmp / "policy_cross_platform_corpus"
    shutil.copytree(src, project_dir)

    # Write deterministic edge-case bytes per run to avoid checkout/OS text normalization drift.
    (project_dir / "windows_newlines.txt").write_bytes(b"Header\r\nCRLF_TOKEN SECRET_101\r\n")
    (project_dir / "latin1.txt").write_bytes("caf\xe9 SECRET_202\n".encode("latin-1"))
    set_fixed_mtime(project_dir)

    out_path = base_tmp / "policy-cross-platform-output.jsonl"
    report_path = base_tmp / "policy-cross-platform-report.json"
    config = PackConfig(
        root=project_dir,
        out=out_path,
        format="jsonl",
        report=report_path,
        workers=1,
        include_sha256=False,
        encoding="latin-1",
        policy_rules=[dict(rule) for rule in _POLICY_CROSS_PLATFORM_RULES],
    )
    packer.pack(config)
    return json.loads(report_path.read_text(encoding="utf-8"))


def summarize_policy_cross_platform_report(report: dict[str, object]) -> dict[str, object]:
    policy_findings = report["policy_findings"]
    assert isinstance(policy_findings, list)

    stage_counts: dict[str, int] = {}
    reason_codes: set[str] = set()
    rule_ids: set[str] = set()
    paths: set[str] = set()

    for finding in policy_findings:
        if not isinstance(finding, dict):
            continue
        stage = finding.get("stage")
        if isinstance(stage, str):
            stage_counts[stage] = stage_counts.get(stage, 0) + 1
        reason_code = finding.get("reason_code")
        if isinstance(reason_code, str):
            reason_codes.add(reason_code)
        rule_id = finding.get("rule_id")
        if isinstance(rule_id, str):
            rule_ids.add(rule_id)
        path = finding.get("path")
        if isinstance(path, str):
            paths.add(path)

    policy_finding_counts = report["policy_finding_counts"]
    assert isinstance(policy_finding_counts, dict)
    return {
        "policy_finding_counts": policy_finding_counts,
        "rule_ids": sorted(rule_ids),
        "reason_codes": sorted(reason_codes),
        "stage_counts": dict(sorted(stage_counts.items())),
        "paths": sorted(paths),
    }
