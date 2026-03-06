# Maintainer Playbook

Operational runbooks for maintainers and coding agents working on pull requests, coverage, and releases.

## PR Triage and Completion Loop

Use this loop whenever you are asked to finish or stabilize an open PR:

1. Check CI status and identify failing jobs.
2. Check unresolved PR items (review threads, comments, and Copilot feedback).
3. Propose actions per unresolved item before implementation when requested.
4. Implement approved fixes and push.
5. Resolve only comments that are already addressed in code.
6. Re-check for newly failing workflows and newly unresolved comments.
7. Repeat until CI is green and no actionable unresolved items remain.

## Patch/New-Line Coverage Workflow (Target 100%)

When a PR is asked to raise patch/new-line coverage, validate locally instead of relying only on hosted CI:

1. Run the affected tests locally:
   - `pytest -m "not integration and not slow" -o addopts=`
   - `pytest -m integration -o addopts=` (if snapshot/integration behavior changed)
2. Run full local coverage:
   - `pytest -o addopts= --cov=foldermix --cov-branch --cov-report=term-missing:skip-covered tests/`
3. Add focused tests for each uncovered new/changed branch or line.
4. Re-run coverage until all new lines in the PR are covered (target: 100% for PR-added lines).

## Snapshot and Fixture Update Workflow

If packer or writer behavior changes intentionally:

1. Run integration snapshot tests.
2. Update fixtures under `tests/integration/fixtures/expected/`.
3. Keep fixture updates in the same PR as the behavior change.
4. In the PR description, state why fixture output changed.

## Release and Homebrew Tap Runbook

Version bump releases are triggered by merging a PR to `main` that updates `[project].version` in `pyproject.toml`.

Release checklist:

1. Bump version in `pyproject.toml`.
2. Refresh snapshots/fixtures if behavior changed.
3. Run local tests and coverage checks.
4. Open release PR and merge after required checks pass.

On merge to `main` with a version bump:

- `publish-pypi` publishes to PyPI.
- `update-homebrew-tap` updates `foldermix/homebrew-foldermix` formula when `HOMEBREW_TAP_GITHUB_TOKEN` is configured.

## Homebrew Tap Troubleshooting

### Symptom: `No HOMEBREW_TAP_GITHUB_TOKEN configured; skipping tap update.`

Action:

1. Add repository secret `HOMEBREW_TAP_GITHUB_TOKEN`.
2. Ensure the token has write access to `foldermix/homebrew-foldermix`.

### Symptom: `fatal: repository 'https://github.com/foldermix/homebrew-foldermix.git/' not found`

Checks:

1. Confirm `TAP_REPOSITORY` in CI is correct (`foldermix/homebrew-foldermix`).
2. Confirm the tap repository exists.
3. Confirm the token can access the org repository (org SSO/approval, token scope, and repository access).
4. If using a fine-grained token, ensure repository-level Contents write permission is granted for the tap repo.

### Symptom: Tap checkout works, but push fails

Checks:

1. Confirm token still has write access (token may be revoked/expired).
2. Confirm branch protection settings in the tap repo allow CI push to the target branch.
3. Confirm formula actually changed; if unchanged, CI exits cleanly with no commit.
