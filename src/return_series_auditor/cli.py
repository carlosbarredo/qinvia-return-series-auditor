"""Command-line entry point and deterministic report renderers."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Sequence

from return_series_auditor import __version__
from return_series_auditor.audit import InputError, audit_file
from return_series_auditor.models import AuditReport, Metrics


def _positive_integer(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="return-audit",
        description="Audit a dated return series or equity curve.",
    )
    parser.add_argument("csv_file", help="CSV containing date and return or equity")
    parser.add_argument(
        "--format",
        choices=("terminal", "json", "markdown"),
        default="terminal",
        help="report format (default: terminal)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="return exit code 1 for warnings as well as failures",
    )
    parser.add_argument(
        "--periods-per-year",
        type=_positive_integer,
        help="override the inferred annualization factor",
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    return parser


def _percent(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.2%}"


def _number(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.4f}"


def _date(value: object) -> str:
    return "n/a" if value is None else value.isoformat()


def _metric_rows(metrics: Metrics) -> list[tuple[str, str]]:
    best = (
        "n/a"
        if metrics.best_period is None
        else f"{metrics.best_period.value:.2%} on {metrics.best_period.date.isoformat()}"
    )
    worst = (
        "n/a"
        if metrics.worst_period is None
        else f"{metrics.worst_period.value:.2%} on {metrics.worst_period.date.isoformat()}"
    )
    rows = [
        ("Observations", str(metrics.observations)),
        ("Start date", _date(metrics.start_date)),
        ("End date", _date(metrics.end_date)),
        ("Inferred frequency", metrics.inferred_frequency),
        ("Periods per year", str(metrics.periods_per_year or "n/a")),
        ("Total compounded return", _percent(metrics.total_compounded_return)),
        ("CAGR", _percent(metrics.cagr)),
        ("Annualized volatility", _percent(metrics.annualized_volatility)),
        ("Sharpe ratio", _number(metrics.sharpe_ratio)),
        ("Sortino ratio", _number(metrics.sortino_ratio)),
        ("Maximum drawdown", _percent(metrics.maximum_drawdown)),
        (
            "Maximum drawdown duration",
            "n/a"
            if metrics.maximum_drawdown_duration is None
            else f"{metrics.maximum_drawdown_duration} periods",
        ),
        ("Current drawdown", _percent(metrics.current_drawdown)),
        ("Best period", best),
        ("Worst period", worst),
    ]
    for count, value in sorted(metrics.return_without_best_periods.items()):
        rows.append((f"Return without best {count}", _percent(value)))
    rows.extend(
        [
            (
                "Best-three positive contribution",
                "n/a"
                if metrics.best_three_positive_contribution_pct is None
                else f"{metrics.best_three_positive_contribution_pct:.1f}%",
            ),
            (
                "Maximum drawdown recovered",
                "n/a"
                if metrics.maximum_drawdown_recovered is None
                else "yes" if metrics.maximum_drawdown_recovered else "no",
            ),
        ]
    )
    return rows


def render_terminal(report: AuditReport) -> str:
    lines = [
        "RETURN SERIES AUDIT",
        f"Source: {report.source}",
        f"Input: {report.input_type}",
        f"Result: {report.summary_status.value}",
        "",
        "METRICS",
    ]
    lines.extend(f"{label}: {value}" for label, value in _metric_rows(report.metrics))
    lines.extend(["", "FINDINGS"])
    lines.extend(
        f"[{finding.status.value}] {finding.title}: {finding.explanation}"
        for finding in report.findings
    )
    return "\n".join(lines) + "\n"


def _markdown_escape(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def render_markdown(report: AuditReport) -> str:
    lines = [
        "# Return Series Audit",
        "",
        f"- **Source:** `{_markdown_escape(report.source)}`",
        f"- **Input:** {report.input_type}",
        f"- **Result:** **{report.summary_status.value}**",
        "",
        "## Metrics",
        "",
        "| Metric | Value |",
        "|---|---:|",
    ]
    lines.extend(
        f"| {_markdown_escape(label)} | {_markdown_escape(value)} |"
        for label, value in _metric_rows(report.metrics)
    )
    lines.extend(
        [
            "",
            "## Findings",
            "",
            "| Status | Check | Explanation |",
            "|---|---|---|",
        ]
    )
    lines.extend(
        f"| {finding.status.value} | {_markdown_escape(finding.title)} | {_markdown_escape(finding.explanation)} |"
        for finding in report.findings
    )
    return "\n".join(lines) + "\n"


def render_json(report: AuditReport) -> str:
    return json.dumps(report.as_dict(), indent=2, sort_keys=True) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        report = audit_file(
            args.csv_file, periods_per_year=args.periods_per_year
        )
    except InputError as exc:
        print(f"return-audit: error: {exc}", file=sys.stderr)
        return 2

    renderers = {
        "terminal": render_terminal,
        "json": render_json,
        "markdown": render_markdown,
    }
    print(renderers[args.format](report), end="")
    return report.exit_code(strict=args.strict)


if __name__ == "__main__":
    raise SystemExit(main())
