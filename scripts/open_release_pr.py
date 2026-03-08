#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True

ROOT = Path.cwd()
PYPROJECT = ROOT / "pyproject.toml"
FIXTURE_DIR = ROOT / "tests" / "integration" / "fixtures"
EXPECTED_DIR = FIXTURE_DIR / "expected"
ALLOWED_DIRTY_PATHS = {"uv.lock"}
FIXED_MTIME = 1704067200  # 2024-01-01T00:00:00+00:00
FIXED_NOW_ISO = "2024-01-02T00:00:00+00:00"
TEXT_FIXTURE_EXTS = {".md", ".py", ".txt"}


def run(cmd: list[str], *, capture_output: bool = False) -> str:
    result = subprocess.run(
        cmd,
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=capture_output,
    )
    if capture_output:
        return result.stdout.strip()
    return ""


def ensure_repo_root() -> None:
    if not PYPROJECT.exists() or not (ROOT / ".git").exists():
        raise SystemExit("Run this script from the repository root.")


def disallowed_worktree_changes(status_output: str) -> list[str]:
    disallowed: list[str] = []
    for raw_line in status_output.splitlines():
        line = raw_line.rstrip()
        if not line:
            continue
        path = line[3:]
        if path in ALLOWED_DIRTY_PATHS:
            continue
        disallowed.append(line)
    return disallowed


def ensure_clean_worktree() -> None:
    status = run(["git", "status", "--porcelain", "--untracked-files=all"], capture_output=True)
    disallowed = disallowed_worktree_changes(status)
    if disallowed:
        joined = "\n".join(disallowed)
        raise SystemExit(f"Working tree is not clean:\n{joined}")


def read_current_version(pyproject_text: str) -> str:
    match = re.search(r'(?m)^version\s*=\s*"([^"]+)"\s*$', pyproject_text)
    if not match:
        raise SystemExit("Could not find [project].version in pyproject.toml")
    return match.group(1)


def bump_version(version: str, bump: str) -> str:
    match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", version)
    if not match:
        raise SystemExit(f"Unsupported semantic version: {version}")
    major, minor, patch = (int(part) for part in match.groups())
    if bump == "major":
        return f"{major + 1}.0.0"
    if bump == "minor":
        return f"{major}.{minor + 1}.0"
    if bump == "patch":
        return f"{major}.{minor}.{patch + 1}"
    raise SystemExit(f"Unsupported bump kind: {bump}")


def replace_project_version(pyproject_text: str, new_version: str) -> str:
    updated, count = re.subn(
        r'(?m)^(version\s*=\s*")([^"]+)("\s*)$',
        rf"\g<1>{new_version}\g<3>",
        pyproject_text,
        count=1,
    )
    if count != 1:
        raise SystemExit("Failed to update [project].version in pyproject.toml")
    return updated


def set_fixed_mtime(root: Path) -> None:
    for path in root.rglob("*"):
        if path.is_file():
            os.utime(path, (FIXED_MTIME, FIXED_MTIME))


def normalize_fixture_newlines_to_lf(root: Path) -> None:
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in TEXT_FIXTURE_EXTS:
            continue
        raw = path.read_bytes()
        normalized = raw.replace(b"\r\n", b"\n")
        if normalized != raw:
            path.write_bytes(normalized)


def normalize_root_path(text: str, project_dir: Path) -> str:
    raw_root = str(project_dir)
    normalized = text.replace(raw_root, "__ROOT__")
    escaped_root = raw_root.replace("\\", "\\\\")
    if escaped_root != raw_root:
        normalized = normalized.replace(escaped_root, "__ROOT__")
    return normalized


def render_simple_project_snapshot(fmt: str, out_name: str) -> str:
    import foldermix
    import foldermix.packer as packer_module
    from foldermix.config import PackConfig

    importlib.reload(foldermix)
    packer_module = importlib.reload(packer_module)

    with tempfile.TemporaryDirectory(prefix="foldermix-release-pr-") as tmp:
        base_tmp = Path(tmp)
        src = FIXTURE_DIR / "simple_project"
        project_dir = base_tmp / "simple_project"
        shutil.copytree(src, project_dir)
        normalize_fixture_newlines_to_lf(project_dir)
        set_fixed_mtime(project_dir)

        original_utcnow_iso = packer_module.utcnow_iso
        packer_module.utcnow_iso = lambda: FIXED_NOW_ISO
        try:
            out_path = base_tmp / out_name
            config = PackConfig(
                root=project_dir,
                out=out_path,
                format=fmt,
                include_sha256=False,
                workers=1,
            )
            packer_module.pack(config)
        finally:
            packer_module.utcnow_iso = original_utcnow_iso

        return normalize_root_path(out_path.read_text(encoding="utf-8"), project_dir)


def regenerate_expected_snapshots() -> list[Path]:
    EXPECTED_DIR.mkdir(parents=True, exist_ok=True)
    outputs = [
        ("md", "bundle.md", EXPECTED_DIR / "simple_project.md"),
        ("xml", "bundle.xml", EXPECTED_DIR / "simple_project.xml"),
        ("jsonl", "bundle.jsonl", EXPECTED_DIR / "simple_project.jsonl"),
    ]
    written: list[Path] = []
    for fmt, out_name, expected_path in outputs:
        expected_path.write_text(render_simple_project_snapshot(fmt, out_name), encoding="utf-8")
        written.append(expected_path)
    return written


def update_main() -> None:
    run(["git", "checkout", "main"])
    run(["git", "pull", "--ff-only", "origin", "main"])


def create_release_branch(branch_name: str) -> None:
    run(["git", "checkout", "-b", branch_name])


def run_release_checks() -> None:
    run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-o",
            "addopts=",
            "tests/test_version_module.py",
            "tests/test_snapshot_guard.py",
            "tests/integration/test_pack_outputs.py",
            "tests/integration/test_pack_outputs_structured.py",
        ]
    )


def stage_release_files(paths: list[Path]) -> None:
    run(["git", "add", str(PYPROJECT), *[str(path) for path in paths]])


def commit_push_and_open_pr(new_version: str, branch_name: str) -> str:
    title = f"chore(release): bump version to {new_version}"
    body = "\n".join(
        [
            "## Summary",
            f"- bump `foldermix` version to `{new_version}`",
            "- refresh the versioned `simple_project` snapshot fixtures",
            "",
            "## Validation",
            "- `pytest -o addopts= tests/test_version_module.py tests/test_snapshot_guard.py tests/integration/test_pack_outputs.py tests/integration/test_pack_outputs_structured.py`",
        ]
    )
    run(["git", "commit", "-m", title])
    run(["git", "push", "-u", "origin", branch_name])
    return run(
        [
            "gh",
            "pr",
            "create",
            "--base",
            "main",
            "--head",
            branch_name,
            "--title",
            title,
            "--body",
            body,
        ],
        capture_output=True,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Open a version-bump release PR from the repository root."
    )
    parser.add_argument(
        "--version",
        help="Explicit target version (defaults to incrementing the current patch version).",
    )
    parser.add_argument(
        "--bump",
        choices=("patch", "minor", "major"),
        default="patch",
        help="Semantic version component to bump when --version is not provided.",
    )
    return parser.parse_args()


def main() -> int:
    ensure_repo_root()
    ensure_clean_worktree()

    args = parse_args()
    update_main()

    pyproject_text = PYPROJECT.read_text(encoding="utf-8")
    current_version = read_current_version(pyproject_text)
    new_version = args.version or bump_version(current_version, args.bump)
    if new_version == current_version:
        raise SystemExit(f"Version is already {new_version}")

    branch_name = f"auto/release-{new_version}"
    create_release_branch(branch_name)

    PYPROJECT.write_text(replace_project_version(pyproject_text, new_version), encoding="utf-8")
    fixture_paths = regenerate_expected_snapshots()
    run_release_checks()
    stage_release_files(fixture_paths)
    pr_url = commit_push_and_open_pr(new_version, branch_name)

    print(f"Opened release PR for {new_version}: {pr_url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
