# Contributing

Focused fixes and small, testable improvements are welcome.

## Before opening a change

1. Open an issue for behavior changes so the input, threshold, finding, and compatibility impact can be agreed first.
2. Keep the audit deterministic and dependency-free at runtime.
3. Preserve the JSON `schema_version` contract. Treat renamed or removed fields as breaking changes.
4. Add or update tests for every behavior change, including the relevant exit code or rendered output.
5. Avoid embedding external datasets. Prefer a minimal synthetic fixture or a reproducible retrieval step with provenance.

## Local checks

```bash
python -m pip install -e ".[dev]"
python -m ruff check src tests
python -m unittest discover -s tests -v
return-audit examples/clean_returns.csv
```

Pull requests should explain the failure mode being addressed, show the expected finding, and note any output or schema compatibility impact. By contributing, you agree that your work will be released under the repository's [MIT License](LICENSE).
