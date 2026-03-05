from __future__ import annotations

import json
import shutil
from pathlib import Path

from foldermix import packer
from foldermix.config import PackConfig
from foldermix.policy_packs import available_policy_packs, get_policy_pack_definition
from tests.snapshot_helpers import (
    render_policy_cross_platform_report,
    render_simple_project_snapshot,
    summarize_policy_cross_platform_report,
)

FIXTURE_DIR = Path(__file__).parent / "integration" / "fixtures"


def test_simple_project_expected_snapshots_are_in_sync(tmp_path: Path, monkeypatch) -> None:
    """Fast guard against fixture/snapshot drift in non-integration test lanes."""
    expected_dir = FIXTURE_DIR / "expected"
    cases = [
        ("md", "bundle.md", "simple_project.md"),
        ("xml", "bundle.xml", "simple_project.xml"),
        ("jsonl", "bundle.jsonl", "simple_project.jsonl"),
    ]

    for fmt, out_name, expected_name in cases:
        actual = render_simple_project_snapshot(
            tmp_path / fmt,
            FIXTURE_DIR,
            fmt,
            out_name,
            monkeypatch,
        )
        expected = (expected_dir / expected_name).read_text(encoding="utf-8")
        assert actual == expected, f"{fmt} snapshot fixture drifted: {expected_name}"


def test_policy_pack_expected_snapshots_are_in_sync(tmp_path: Path) -> None:
    expected_path = FIXTURE_DIR / "expected" / "policy_pack_deltas.json"
    corpus_root = FIXTURE_DIR / "policy_pack_corpus"

    summary: dict[str, object] = {}
    for pack_name in available_policy_packs():
        corpus_dir = tmp_path / f"corpus-{pack_name}"
        shutil.copytree(corpus_root, corpus_dir)
        out_path = tmp_path / f"bundle-{pack_name}.jsonl"
        report_path = tmp_path / f"report-{pack_name}.json"
        config = PackConfig(
            root=corpus_dir,
            out=out_path,
            format="jsonl",
            report=report_path,
            workers=1,
            include_sha256=False,
            policy_pack=pack_name,
        )
        packer.pack(config)
        report = json.loads(report_path.read_text(encoding="utf-8"))
        summary[pack_name] = {
            "pack_version": get_policy_pack_definition(pack_name)["version"],
            "policy_finding_counts": report["policy_finding_counts"],
            "rule_ids": sorted({finding["rule_id"] for finding in report["policy_findings"]}),
        }

    expected = json.loads(expected_path.read_text(encoding="utf-8"))
    assert summary == expected, "policy pack snapshot fixture drifted: policy_pack_deltas.json"


def test_policy_cross_platform_expected_snapshot_is_in_sync(tmp_path: Path) -> None:
    expected_path = FIXTURE_DIR / "expected" / "policy_cross_platform_summary.json"
    report = render_policy_cross_platform_report(tmp_path, FIXTURE_DIR)
    summary = summarize_policy_cross_platform_report(report)

    expected = json.loads(expected_path.read_text(encoding="utf-8"))
    assert summary == expected, "policy cross-platform snapshot fixture drifted"
