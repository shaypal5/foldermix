# Security Policy

## Sensitive File Handling

folderpack automatically skips the following sensitive file patterns:
- `.env` - Environment variable files
- `*.pem`, `*.key` - SSL/TLS certificates and keys
- `id_rsa`, `id_dsa` - SSH private keys
- `*.p12`, `*.pfx` - PKCS certificate bundles
- `.netrc` - Network authentication credentials

These files are **never included** in output, even if you explicitly request them via `--include-ext`.

## Redaction

Use `--redact=emails` to redact email addresses, `--redact=phones` for phone numbers, or `--redact=all` for both.

## Reporting Vulnerabilities

Please report vulnerabilities by opening a GitHub issue.
