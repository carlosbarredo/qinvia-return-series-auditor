# Qinvia Return Series Auditor

[![Tests](https://github.com/carlosbarredo/qinvia-return-series-auditor/actions/workflows/tests.yml/badge.svg)](https://github.com/carlosbarredo/qinvia-return-series-auditor/actions/workflows/tests.yml)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

**A dependency-free Python CLI that finds data-quality defects and fragile performance claims before you trust a return series.**

Feed it a dated CSV of decimal returns or equity values. It produces a deterministic audit with explicit `PASS`, `INFO`, `WARN`, and `FAIL` findings—plus standard performance and drawdown metrics—in terminal, Markdown, or versioned JSON format.

```console
$ return-audit examples/clean_returns.csv
RETURN SERIES AUDIT
Source: examples/clean_returns.csv
Input: return
Result: PASS

METRICS
Observations: 60
Total compounded return: 48.42%
Maximum drawdown: -1.80%
...
```

It is designed for researchers, reviewers, and CI pipelines that need an inspectable answer to three questions:

- **Is the input structurally sound?** Missing values, duplicates, bad ordering, impossible returns, invalid equity, and suspicious gaps are surfaced with row- or date-level context.
- **How does the track record behave?** Compounded return, CAGR, volatility, Sharpe, Sortino, drawdown, recovery, and best/worst periods are calculated consistently.
- **How fragile is the headline result?** The audit removes the best 1, 3, and 5 periods and measures concentration in the strongest positive observations.

## Quick start

Python 3.12 or later is required. The package has no third-party runtime dependencies.

```bash
git clone https://github.com/carlosbarredo/qinvia-return-series-auditor.git
cd qinvia-return-series-auditor
python -m pip install -e .
return-audit examples/clean_returns.csv
```

Audit your own file and choose the output contract you need:

```bash
return-audit data.csv                         # human-readable terminal report
return-audit data.csv --format markdown       # report or CI job summary
return-audit data.csv --format json           # stable schema_version 1.0 document
return-audit data.csv --strict                # warnings also return exit code 1
return-audit data.csv --periods-per-year 252  # explicit annualization override
```

The same input and options produce the same ordered findings and values.

## Real-market demonstration

[![Real U.S. market return audit: logarithmic growth of $1 and drawdown](docs/assets/real-market-audit.png)](notebooks/real_market_returns_audit.ipynb)

The executed [real-market audit notebook](notebooks/real_market_returns_audit.ipynb) downloads monthly U.S. market factors directly from the official [Kenneth French Data Library](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html), reconstructs the market return as `Mkt-RF + RF`, and passes the series through the package's public API. It records retrieval provenance and a content hash, visualizes growth and drawdown, tests best-month dependence, and demonstrates detection with a deliberately corrupted temporary copy. No raw external dataset is committed.

To reproduce it:

```bash
python -m pip install -e ".[notebook]"
python -m nbconvert --to notebook --execute --inplace notebooks/real_market_returns_audit.ipynb
```

## Input contract

Use an ISO 8601 date and exactly one value column. Returns are decimals: `0.01` means 1%.

```csv
date,return
2025-01-02,0.0042
```

Alternatively, provide an equity curve:

```csv
date,equity
2025-01-02,100000
```

Column names are case-insensitive and surrounding header whitespace is ignored. Equity is sorted by date after order and duplicate checks, then converted to returns with `current_equity / previous_equity - 1`. Invalid rows and later duplicate occurrences are excluded from calculations; the report always discloses those exclusions.

The synthetic fixtures in [`examples/`](examples) demonstrate clean and problematic inputs. They are not records of real investment performance.

## What the audit checks

| Area | Checks | Classification |
|---|---|---|
| Input integrity | Missing or unparseable values, duplicate dates, non-finite numbers, date order | `PASS` or `FAIL` |
| Economic validity | Returns at or below -100%; zero or negative equity | `PASS` or `FAIL` |
| Continuity | Calendar gaps relative to inferred daily, weekly, or monthly frequency | `PASS`, `INFO`, or `WARN` |
| Statistical reliability | Track-record length and zero or near-zero variance | `PASS`, `WARN`, or `FAIL` |
| Result fragility | Best-period dependence and positive-return concentration | `PASS`, `INFO`, or `WARN` |
| Path risk | Maximum-drawdown recovery by the final observation | `PASS`, `INFO`, or `WARN` |

Warnings and failures include the observed count, rows, dates, threshold, or calculated result that caused the classification. `INFO` means a check is descriptive or cannot be meaningfully classified with the available series. The precise thresholds are intentionally simple and reviewable:

- Gaps longer than 7, 21, or 62 calendar days warn for inferred daily, weekly, or monthly data.
- Fewer than one inferred year of returns, with an absolute floor of 12 observations, warns.
- Annualized volatility no greater than `1e-8` warns because risk-adjusted ratios are unstable.
- Removing the best 1, 3, or 5 periods warns when a positive compounded result becomes non-positive or falls by at least 50% relative to the original result.
- The best three periods contributing at least 50% of all positive arithmetic returns warns.
- An unrecovered maximum drawdown warns.

## Metrics and conventions

- **Total compounded return** is `product(1 + return) - 1`.
- **CAGR** is `(1 + total_return) ** (periods_per_year / observations) - 1` and is unavailable when terminal wealth is not positive or frequency is unknown.
- **Annualized volatility** is sample standard deviation multiplied by the square root of periods per year.
- **Sharpe ratio** is the arithmetic mean return divided by sample standard deviation, annualized by the square root of periods per year. The periodic risk-free rate is zero.
- **Sortino ratio** replaces standard deviation with the root mean square of `min(return, 0)`.
- **Maximum drawdown** is the largest peak-to-trough loss on a wealth index starting at 1.0; duration counts consecutive observations below the running peak.
- **Best/worst periods and removal tests** use dated returns; removal ties are resolved by original chronological position.

Daily, weekly, and monthly data use annualization factors of 252, 52, and 12. `--periods-per-year` overrides the factor but not the reported inferred frequency. Ratios are unavailable when their denominator is effectively zero.

## Exit codes and CI use

| Code | Meaning |
|---:|---|
| `0` | Audit completed without failures. |
| `1` | One or more failures were found. With `--strict`, warnings also produce this code. |
| `2` | Invalid command usage, unreadable input, or an unsupported CSV header. |

For a pipeline that treats statistical warnings as blocking and preserves a machine-readable artifact:

```bash
return-audit data.csv --strict --format json > audit.json
```

The repository workflow lints the code and runs the complete `unittest` suite on Python 3.12, 3.13, and 3.14 for every pull request. Its cost and governance controls are documented in [docs/GITHUB_ACTIONS_COST_CONTROL.md](docs/GITHUB_ACTIONS_COST_CONTROL.md).

## Scope and limitations

Calculations treat observations as one unweighted return stream, assume a consistent periodic convention, use a zero risk-free rate, and do not adjust for cash flows, fees, taxes, inflation, serial correlation, or non-trading calendars. Frequency and gap detection are deterministic heuristics; unusual schedules should use an explicit annualization override. Findings should be reviewed before metrics when invalid data is present.

This tool audits the supplied numbers. It does **not** detect look-ahead bias, survivorship bias, data snooping, hidden leverage, incorrect fills, or fabricated inputs, and it does not prove that a strategy is valid or investable. Historical statistics do not predict future results. This project is for educational and data-quality review purposes only, not investment advice.

The roadmap is deliberately narrow: preserve deterministic behavior and JSON compatibility, strengthen diagnostics where the finding can remain explicit, and avoid becoming a portfolio optimizer, backtester, or market-data client. Proposals should include a concrete failure mode and a testable expected finding.

## Development and project policies

```bash
python -m pip install -e ".[dev]"
python -m ruff check src tests
python -m unittest discover -s tests -v
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the change checklist, [SECURITY.md](SECURITY.md) for responsible vulnerability reporting, and [CITATION.cff](CITATION.cff) for citation metadata.

Created by **Carlos Barredo Lago** and released under the [MIT License](LICENSE).
