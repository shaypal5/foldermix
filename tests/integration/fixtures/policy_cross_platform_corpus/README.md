Cross-platform policy integration corpus.

This fixture intentionally mixes:
- regular text/markdown/csv files,
- path names with spaces,
- hidden paths,
- sensitive file patterns,
- excluded extensions.

The integration test additionally rewrites selected files with explicit CRLF and
Latin-1 bytes to avoid checkout-dependent newline/encoding behavior.
