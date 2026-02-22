#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

DESCRIPTION = "Pack a folder into a single LLM-friendly context file"
HOMEPAGE = "https://github.com/shaypal5/foldermix"
LICENSE = "MIT"
HOMEBREW_PYTHON_FORMULA = "python@3.12"

SKIP_FREEZE_PACKAGES = {
    "foldermix",
    "pip",
    "setuptools",
    "wheel",
}


def _normalize_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _run(cmd: list[str]) -> str:
    return subprocess.check_output(cmd, text=True).strip()


def _retry_backoff_seconds(attempt: int) -> int:
    return min(60, 3 * attempt)


def _fetch_pypi_release_file(package: str, version: str, retries: int = 8) -> tuple[str, str]:
    encoded_package = urllib.parse.quote(package)
    encoded_version = urllib.parse.quote(version)
    url = f"https://pypi.org/pypi/{encoded_package}/{encoded_version}/json"

    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "foldermix-homebrew-generator"}
            )
            with urllib.request.urlopen(req, timeout=20) as response:
                payload = json.load(response)
        except urllib.error.HTTPError as exc:
            if exc.code == 404 and attempt < retries:
                # PyPI metadata can lag briefly right after publish.
                time.sleep(_retry_backoff_seconds(attempt))
                continue
            if (500 <= exc.code < 600 or exc.code == 429) and attempt < retries:
                # Retry on transient server errors and rate limiting.
                time.sleep(_retry_backoff_seconds(attempt))
                continue
            raise RuntimeError(
                f"Failed to fetch PyPI metadata for {package}=={version} from {url}: "
                f"HTTP {exc.code}: {exc}"
            ) from exc
        except urllib.error.URLError as exc:
            if attempt < retries:
                time.sleep(_retry_backoff_seconds(attempt))
                continue
            raise RuntimeError(
                f"Failed to fetch PyPI metadata for {package}=={version} from {url}: {exc}"
            ) from exc

        files = payload.get("urls", [])
        sdist = next((f for f in files if f.get("packagetype") == "sdist"), None)
        if not sdist:
            raise RuntimeError(f"No sdist found on PyPI for {package}=={version} from {url}")

        file_url = sdist["url"]
        sha256 = sdist["digests"]["sha256"]
        return file_url, sha256

    raise RuntimeError(
        f"Unable to fetch metadata for {package}=={version} from {url} after {retries} attempts"
    )


def _resolve_runtime_deps(project_root: Path) -> list[tuple[str, str]]:
    project_root = project_root.resolve()
    with tempfile.TemporaryDirectory(prefix="foldermix-brew-") as tmp:
        venv_dir = Path(tmp) / "venv"
        python = Path(sys.executable)
        _run([str(python), "-m", "venv", str(venv_dir)])

        if sys.platform == "win32":
            pip = venv_dir / "Scripts" / "pip.exe"
        else:
            pip = venv_dir / "bin" / "pip"

        _run([str(pip), "install", "--disable-pip-version-check", "--upgrade", "pip"])
        # Resolve dependency versions from the current release commit source tree.
        _run([str(pip), "install", "--disable-pip-version-check", str(project_root)])
        freeze = _run([str(pip), "freeze", "--all"])

    resolved: dict[str, tuple[str, str]] = {}
    for line in freeze.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-e "):
            continue
        if "@" in line:
            # Skip direct URL/editable lines for robustness.
            continue
        if "==" not in line:
            continue
        name, dep_version = line.split("==", 1)
        norm = _normalize_name(name)
        if norm in SKIP_FREEZE_PACKAGES:
            continue
        resolved[norm] = (name, dep_version)

    return [resolved[key] for key in sorted(resolved)]


def _render_formula(
    package_version: str,
    package_url: str,
    package_sha256: str,
    resources: list[tuple[str, str, str]],
    needs_rust: bool,
) -> str:
    lines = [
        "class Foldermix < Formula",
        "  include Language::Python::Virtualenv",
        "",
        f'  desc "{DESCRIPTION}"',
        f'  homepage "{HOMEPAGE}"',
        f'  url "{package_url}"',
        f'  sha256 "{package_sha256}"',
        f'  license "{LICENSE}"',
        f'  version "{package_version}"',
        "",
        f'  depends_on "{HOMEBREW_PYTHON_FORMULA}"',
    ]

    if needs_rust:
        lines.append('  depends_on "rust" => :build')

    if resources:
        lines.append("")

    for index, (resource_name, resource_url, resource_sha) in enumerate(resources):
        lines.extend(
            [
                f'  resource "{resource_name}" do',
                f'    url "{resource_url}"',
                f'    sha256 "{resource_sha}"',
                "  end",
            ]
        )
        if index != len(resources) - 1:
            lines.append("")

    lines.extend(
        [
            "",
            "  def install",
            "    virtualenv_install_with_resources",
            "  end",
            "",
            "  test do",
            '    (testpath/"a.txt").write("hello\\n")',
            '    assert_match "foldermix #{version}", shell_output("#{bin}/foldermix version")',
            '    system bin/"foldermix", "pack", testpath, "--out", "bundle.md"',
            '    assert_predicate testpath/"bundle.md", :exist?',
            "  end",
            "end",
            "",
        ]
    )

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Render Homebrew formula for foldermix from PyPI.")
    parser.add_argument("--version", required=True, help="foldermix version (e.g. 0.1.1)")
    parser.add_argument(
        "--output",
        default="packaging/homebrew/foldermix.rb",
        help="Output path for rendered formula",
    )
    args = parser.parse_args()

    package_url, package_sha = _fetch_pypi_release_file("foldermix", args.version)
    project_root = Path(__file__).resolve().parents[1]
    runtime_deps = _resolve_runtime_deps(project_root)

    resources: list[tuple[str, str, str]] = []
    needs_rust = False
    for package_name, package_version in runtime_deps:
        resource_url, resource_sha = _fetch_pypi_release_file(package_name, package_version)
        normalized = _normalize_name(package_name)
        if normalized == "pydantic-core":
            needs_rust = True
        resources.append((normalized, resource_url, resource_sha))

    output = _render_formula(
        package_version=args.version,
        package_url=package_url,
        package_sha256=package_sha,
        resources=resources,
        needs_rust=needs_rust,
    )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(output, encoding="utf-8")
    print(f"Wrote Homebrew formula to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
