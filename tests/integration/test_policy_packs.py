from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from foldermix import packer
from foldermix.config import PackConfig
from foldermix.policy_packs import available_policy_packs, get_policy_pack_definition

pytestmark = pytest.mark.integration

FIXTURE_DIR = Path(__file__).parent / "fixtures"


def _run_pack_with_policy_pack(
    tmp_path: Path, *, policy_pack: str, fixture_root: Path
) -> dict[str, object]:
    corpus_dir = tmp_path / f"corpus-{policy_pack}"
    shutil.copytree(fixture_root, corpus_dir)
    out_path = tmp_path / f"bundle-{policy_pack}.jsonl"
    report_path = tmp_path / f"report-{policy_pack}.json"
    config = PackConfig(
        root=corpus_dir,
        out=out_path,
        format="jsonl",
        report=report_path,
        workers=1,
        include_sha256=False,
        policy_pack=policy_pack,
    )
    packer.pack(config)
    return json.loads(report_path.read_text(encoding="utf-8"))


def test_builtin_policy_packs_report_deltas_match_snapshot(tmp_path: Path) -> None:
    fixture_root = FIXTURE_DIR / "policy_pack_corpus"
    expected_path = FIXTURE_DIR / "expected" / "policy_pack_deltas.json"

    summary: dict[str, object] = {}
    for pack_name in available_policy_packs():
        report = _run_pack_with_policy_pack(
            tmp_path, policy_pack=pack_name, fixture_root=fixture_root
        )
        summary[pack_name] = {
            "pack_version": get_policy_pack_definition(pack_name)["version"],
            "policy_finding_counts": report["policy_finding_counts"],
            "rule_ids": sorted({finding["rule_id"] for finding in report["policy_findings"]}),
        }

    expected = json.loads(expected_path.read_text(encoding="utf-8"))
    assert summary == expected
