#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

DESCRIPTION = "Pack a folder into a single LLM-friendly context file"
HOMEPAGE = "https://github.com/shaypal5/foldermix"
LICENSE = "MIT"
HOMEBREW_PYTHON_FORMULA = "python@3.12"


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


def _render_formula(
    package_version: str,
    package_url: str,
    package_sha256: str,
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

    lines.extend(
        [
            "",
            "  def install",
            f'    venv = virtualenv_create(libexec, "{HOMEBREW_PYTHON_FORMULA}")',
            "    # Do not vendor compiled sdists (like pydantic-core), which can",
            "    # force Rust/LLVM downloads. Let pip resolve platform wheels.",
            "    venv.pip_install_and_link buildpath",
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

    output = _render_formula(
        package_version=args.version,
        package_url=package_url,
        package_sha256=package_sha,
    )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(output, encoding="utf-8")
    print(f"Wrote Homebrew formula to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
