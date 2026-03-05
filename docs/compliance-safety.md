# Compliance & Safety Guide

This guide documents technical and operational controls for policy-aware local-folder packing.
It does not provide legal advice or legal guarantees.

## 1) Choose a Policy Pack

`foldermix` supports built-in policy packs via `--policy-pack` (or `[pack].policy_pack` in `foldermix.toml`):

| Policy pack | Primary intent | Default outcome profile |
| --- | --- | --- |
| `strict-privacy` | Block direct PII/secret indicators early | includes `deny` findings (`high`/`critical`) |
| `legal-hold` | Surface legal-retention and privileged-content markers | advisory `warn` findings |
| `customer-support` | Flag support-facing contact data and log artifacts | advisory `warn` findings |

Use a pack as a baseline and optionally add custom `[[pack.policy_rules]]`.
Pack rules are evaluated before custom rules.

## 2) Enforcement, Preview, and Output Flags

| Flag | Purpose | Notes |
| --- | --- | --- |
| `--policy-pack <name>` | Enable built-in policy pack | valid: `strict-privacy`, `legal-hold`, `customer-support` |
| `--fail-on-policy-violation` | Enforce policy threshold as non-zero exit | only `action="deny"` findings are enforcement-failing |
| `--policy-fail-level <level>` | Minimum severity for enforcement | valid: `low`, `medium`, `high`, `critical` |
| `--policy-dry-run` | Evaluate policy without writing bundle output | still runs scan/convert/pack policy stages |
| `--policy-output <text|json>` | Policy dry-run output format | requires `--policy-dry-run` |
| `--report <path>` | Persist machine-readable findings and counters | recommended for CI and audit trails |

Validation constraints:

- `--policy-output` requires `--policy-dry-run`.
- `--dry-run` and `--policy-dry-run` are mutually exclusive.

## 3) Policy-Related Exit Codes

| Exit code | Meaning |
| --- | --- |
| `0` | Completed successfully (including dry-run) without policy enforcement failure |
| `1` | Invalid CLI/config or policy configuration validation failure |
| `4` | Policy enforcement failure (`--fail-on-policy-violation` with findings meeting `--policy-fail-level`) |

Other non-policy runtime failures may return different non-zero codes.

## 4) Interpreting Findings in `--report`

Policy data appears in:

- `policy_findings[]`: one entry per finding (`rule_id`, `severity`, `action`, `stage`, `path`, `reason_code`, `message`)
- `policy_finding_counts`: aggregate counters (`total`, `by_severity`, `by_action`, `by_reason_code`)
- `reason_code_counts`: cross-cutting skip/outcome/warning reason-code totals (policy reason codes are under `policy_finding_counts.by_reason_code`)
- `warning_code_counts`: extraction/conversion warning totals

Recommended review order:

1. `policy_finding_counts.by_action.deny`
2. `policy_finding_counts.by_severity`
3. Top `reason_code_counts` and `warning_code_counts`
4. Per-file details in `policy_findings[]` and `included_files[].outcomes`

## 5) Quick Reference: Reason and Warning Codes

### Skip reason codes

`SKIP_HIDDEN`, `SKIP_EXCLUDED_DIR`, `SKIP_SENSITIVE`, `SKIP_GITIGNORED`, `SKIP_EXCLUDED_GLOB`, `SKIP_EXCLUDED_EXT`, `SKIP_UNREADABLE`, `SKIP_OVERSIZE`, `SKIP_OUTSIDE_ROOT`, `SKIP_MISSING`, `SKIP_NOT_FILE`, `SKIP_UNKNOWN`

### Included-file outcome codes

`OUTCOME_TRUNCATED`, `OUTCOME_REDACTED`, `OUTCOME_CONVERSION_WARNING`

### Warning taxonomy codes

`encoding_fallback`, `converter_unavailable`, `ocr_disabled`, `ocr_dependencies_missing`, `ocr_initialization_failed`, `ocr_failed`, `ocr_no_text`, `unclassified_warning`

### Policy finding reason codes

`POLICY_RULE_MATCH`, `POLICY_SKIP_REASON_MATCH`, `POLICY_CONTENT_REGEX_MATCH`, `POLICY_FILE_SIZE_EXCEEDED`, `POLICY_TOTAL_BYTES_EXCEEDED`, `POLICY_FILE_COUNT_EXCEEDED`

## 6) Recommended Patterns by Use Case

### Legal

Goal: high-signal retention review and optional strict gates.

```bash
foldermix pack ./matter \
  --policy-pack legal-hold \
  --report legal-report.json
```

Add hard-fail gate only when your policy program requires blocking:

```bash
foldermix pack ./matter \
  --policy-pack strict-privacy \
  --fail-on-policy-violation \
  --policy-fail-level high \
  --report legal-enforced-report.json
```

### Support

Goal: advisory findings for triage quality without blocking.

```bash
foldermix pack ./tickets \
  --policy-pack customer-support \
  --report support-report.json
```

### Research

Goal: preview and inspect policy impact before final export.

```bash
foldermix pack ./corpus \
  --policy-pack strict-privacy \
  --policy-dry-run \
  --policy-output json
```

Then run the final pack with report output:

```bash
foldermix pack ./corpus \
  --policy-pack strict-privacy \
  --report research-report.json
```
