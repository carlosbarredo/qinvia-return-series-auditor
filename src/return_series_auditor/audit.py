"""CSV ingestion and explicit audit checks."""

from __future__ import annotations

import csv
import math
from collections import Counter
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from return_series_auditor.metrics import calculate_metrics, infer_frequency
from return_series_auditor.models import AuditReport, Finding, Metrics, Status


class InputError(Exception):
    """Raised when an input cannot be opened or is not a supported CSV."""


@dataclass(frozen=True, slots=True)
class ParsedPoint:
    row_number: int
    date: date
    value: float


def _row_list(rows: list[int]) -> str:
    return ", ".join(str(row) for row in sorted(set(rows)))


def _finding(
    code: str, status: Status, title: str, explanation: str
) -> Finding:
    return Finding(code=code, status=status, title=title, explanation=explanation)


def _read_points(path: Path) -> tuple[str, list[ParsedPoint], list[Finding]]:
    try:
        handle = path.open("r", encoding="utf-8-sig", newline="")
    except OSError as exc:
        raise InputError(f"cannot read {path}: {exc}") from exc

    with handle:
        try:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None:
                raise InputError("CSV input must include a header row")
            normalized_headers = {
                header.strip().lower(): header
                for header in reader.fieldnames
                if header is not None
            }
            if "date" not in normalized_headers:
                raise InputError("CSV header must include a 'date' column")
            value_columns = [
                candidate
                for candidate in ("return", "equity")
                if candidate in normalized_headers
            ]
            if len(value_columns) != 1:
                raise InputError(
                    "CSV header must include exactly one of 'return' or 'equity'"
                )

            input_type = value_columns[0]
            date_header = normalized_headers["date"]
            value_header = normalized_headers[input_type]
            points: list[ParsedPoint] = []
            missing_rows: list[int] = []
            invalid_date_rows: list[int] = []
            invalid_number_rows: list[int] = []
            non_finite_rows: list[int] = []

            for row_number, row in enumerate(reader, start=2):
                raw_date = (row.get(date_header) or "").strip()
                raw_value = (row.get(value_header) or "").strip()
                if not raw_date or not raw_value:
                    missing_rows.append(row_number)
                    continue
                try:
                    parsed_date = date.fromisoformat(raw_date)
                except ValueError:
                    invalid_date_rows.append(row_number)
                    continue
                try:
                    parsed_value = float(raw_value)
                except ValueError:
                    invalid_number_rows.append(row_number)
                    continue
                if not math.isfinite(parsed_value):
                    non_finite_rows.append(row_number)
                    continue
                points.append(ParsedPoint(row_number, parsed_date, parsed_value))
        except (csv.Error, OSError, UnicodeError) as exc:
            raise InputError(f"cannot parse CSV input: {exc}") from exc

    findings: list[Finding] = []
    if missing_rows:
        findings.append(
            _finding(
                "missing_values",
                Status.FAIL,
                "Missing values",
                f"Required date or {input_type} values are missing on CSV row(s) {_row_list(missing_rows)}.",
            )
        )
    else:
        findings.append(
            _finding(
                "missing_values",
                Status.PASS,
                "Missing values",
                "No required values are missing.",
            )
        )

    invalid_rows = invalid_date_rows + invalid_number_rows
    if invalid_rows:
        parts: list[str] = []
        if invalid_date_rows:
            parts.append(f"unparseable date(s) on row(s) {_row_list(invalid_date_rows)}")
        if invalid_number_rows:
            parts.append(
                f"unparseable {input_type} value(s) on row(s) {_row_list(invalid_number_rows)}"
            )
        findings.append(
            _finding(
                "unparseable_values",
                Status.FAIL,
                "Unparseable values",
                "; ".join(parts) + ".",
            )
        )
    else:
        findings.append(
            _finding(
                "unparseable_values",
                Status.PASS,
                "Unparseable values",
                "All non-missing dates and numeric values are parseable.",
            )
        )

    if non_finite_rows:
        findings.append(
            _finding(
                "non_finite_numbers",
                Status.FAIL,
                "Non-finite numbers",
                f"NaN or infinite {input_type} values occur on CSV row(s) {_row_list(non_finite_rows)}.",
            )
        )
    else:
        findings.append(
            _finding(
                "non_finite_numbers",
                Status.PASS,
                "Non-finite numbers",
                "All parsed numeric values are finite.",
            )
        )
    return input_type, points, findings


def _integrity_findings(
    input_type: str, points: list[ParsedPoint]
) -> tuple[list[Finding], list[ParsedPoint]]:
    findings: list[Finding] = []
    date_counts = Counter(point.date for point in points)
    duplicate_dates = sorted(
        repeated_date for repeated_date, count in date_counts.items() if count > 1
    )
    duplicate_rows = sum(count - 1 for count in date_counts.values() if count > 1)
    if duplicate_dates:
        dates = ", ".join(value.isoformat() for value in duplicate_dates)
        findings.append(
            _finding(
                "duplicate_dates",
                Status.FAIL,
                "Duplicate dates",
                f"Found {duplicate_rows} duplicate row(s) for date(s): {dates}. Only the first occurrence of each date is analyzed.",
            )
        )
    else:
        findings.append(
            _finding(
                "duplicate_dates",
                Status.PASS,
                "Duplicate dates",
                "Every parsed date is unique.",
            )
        )

    unordered_transitions = sum(
        current.date < previous.date
        for previous, current in zip(points, points[1:])
    )
    if unordered_transitions:
        findings.append(
            _finding(
                "date_order",
                Status.FAIL,
                "Date order",
                f"Dates move backwards {unordered_transitions} time(s) in file order. Metrics use chronological order.",
            )
        )
    else:
        findings.append(
            _finding(
                "date_order",
                Status.PASS,
                "Date order",
                "Parsed dates are in chronological order.",
            )
        )

    first_by_date: dict[date, ParsedPoint] = {}
    for point in points:
        first_by_date.setdefault(point.date, point)
    unique_points = sorted(first_by_date.values(), key=lambda point: point.date)

    if input_type == "return":
        impossible = [point for point in unique_points if point.value <= -1.0]
        if impossible:
            rows = [point.row_number for point in impossible]
            findings.append(
                _finding(
                    "return_floor",
                    Status.FAIL,
                    "Impossible returns",
                    f"Returns at or below -100% occur on CSV row(s) {_row_list(rows)}.",
                )
            )
        else:
            findings.append(
                _finding(
                    "return_floor",
                    Status.PASS,
                    "Impossible returns",
                    "Every parsed return is greater than -100%.",
                )
            )
    else:
        non_positive = [point for point in unique_points if point.value <= 0.0]
        if non_positive:
            rows = [point.row_number for point in non_positive]
            findings.append(
                _finding(
                    "positive_equity",
                    Status.FAIL,
                    "Non-positive equity",
                    f"Equity is zero or negative on CSV row(s) {_row_list(rows)}; those points are excluded from return conversion.",
                )
            )
        else:
            findings.append(
                _finding(
                    "positive_equity",
                    Status.PASS,
                    "Non-positive equity",
                    "Every parsed equity value is positive.",
                )
            )
    return findings, unique_points


def _to_returns(
    input_type: str, unique_points: list[ParsedPoint]
) -> tuple[list[tuple[date, float]], list[date]]:
    if input_type == "return":
        return (
            [(point.date, point.value) for point in unique_points],
            [point.date for point in unique_points],
        )
    positive_points = [point for point in unique_points if point.value > 0.0]
    dated_returns = [
        (current.date, current.value / previous.value - 1.0)
        for previous, current in zip(positive_points, positive_points[1:])
    ]
    return dated_returns, [point.date for point in positive_points]


def _gap_finding(dates: list[date]) -> Finding:
    frequency = infer_frequency(dates)
    if frequency == "unknown":
        return _finding(
            "suspicious_gaps",
            Status.INFO,
            "Suspicious gaps",
            "At least two usable dates are required to assess time-series gaps.",
        )
    limits = {"daily": 7, "weekly": 21, "monthly": 62}
    limit = limits[frequency]
    gaps = [
        (previous, current, (current - previous).days)
        for previous, current in zip(dates, dates[1:])
        if (current - previous).days > limit
    ]
    if gaps:
        examples = ", ".join(
            f"{previous.isoformat()} to {current.isoformat()} ({days} days)"
            for previous, current, days in gaps[:3]
        )
        suffix = "" if len(gaps) <= 3 else f"; plus {len(gaps) - 3} more"
        return _finding(
            "suspicious_gaps",
            Status.WARN,
            "Suspicious gaps",
            f"Found {len(gaps)} gap(s) longer than {limit} calendar days for inferred {frequency} data: {examples}{suffix}.",
        )
    return _finding(
        "suspicious_gaps",
        Status.PASS,
        "Suspicious gaps",
        f"No gap exceeds {limit} calendar days for inferred {frequency} data.",
    )


def _statistical_findings(metrics: Metrics) -> list[Finding]:
    findings: list[Finding] = []
    annualization = metrics.periods_per_year
    required_observations = max(12, annualization or 12)
    if metrics.observations == 0:
        findings.append(
            _finding(
                "track_record_length",
                Status.FAIL,
                "Track-record length",
                "No usable periodic returns are available for analysis.",
            )
        )
    elif metrics.observations < required_observations:
        findings.append(
            _finding(
                "track_record_length",
                Status.WARN,
                "Track-record length",
                f"Only {metrics.observations} periodic return(s) are usable; at least {required_observations} are required for one inferred year and the minimum sample floor.",
            )
        )
    else:
        findings.append(
            _finding(
                "track_record_length",
                Status.PASS,
                "Track-record length",
                f"The series contains {metrics.observations} usable returns, meeting the {required_observations}-period threshold.",
            )
        )

    if metrics.observations < 2:
        findings.append(
            _finding(
                "variance",
                Status.WARN,
                "Return variance",
                "Fewer than two usable returns are available, so variance cannot be estimated.",
            )
        )
    else:
        values_volatility = metrics.annualized_volatility
        if values_volatility is None or values_volatility <= 1e-8:
            findings.append(
                _finding(
                    "variance",
                    Status.WARN,
                    "Return variance",
                    "Annualized volatility is zero or no greater than 0.000001%, so risk-adjusted ratios are not stable.",
                )
            )
        else:
            findings.append(
                _finding(
                    "variance",
                    Status.PASS,
                    "Return variance",
                    f"Annualized volatility is {values_volatility:.6%}, above the near-zero threshold.",
                )
            )

    total_return = metrics.total_compounded_return
    for count in (1, 3, 5):
        code = f"best_{count}_dependence"
        title = f"Dependence on best {count} period" + ("" if count == 1 else "s")
        if metrics.observations <= count:
            findings.append(
                _finding(
                    code,
                    Status.INFO,
                    title,
                    f"The series has too few observations to remove {count} period(s) meaningfully.",
                )
            )
            continue
        removed_return = metrics.return_without_best_periods[count]
        if total_return is None or total_return <= 0.0:
            findings.append(
                _finding(
                    code,
                    Status.INFO,
                    title,
                    f"Dependence is not classified as excessive because the original compounded return is {total_return:.2%}.",
                )
            )
            continue
        reduction = (total_return - removed_return) / total_return * 100.0
        excessive = removed_return <= 0.0 or reduction >= 50.0
        status = Status.WARN if excessive else Status.PASS
        explanation = (
            f"Removing the best {count} period(s) changes compounded return from "
            f"{total_return:.2%} to {removed_return:.2%}, a {reduction:.1f}% reduction relative to the original result."
        )
        findings.append(_finding(code, status, title, explanation))

    contribution = metrics.best_three_positive_contribution_pct
    if contribution is None:
        findings.append(
            _finding(
                "best_three_positive_contribution",
                Status.INFO,
                "Best-three positive contribution",
                "There are no positive returns from which to calculate a contribution percentage.",
            )
        )
    else:
        status = Status.WARN if contribution >= 50.0 else Status.PASS
        findings.append(
            _finding(
                "best_three_positive_contribution",
                status,
                "Best-three positive contribution",
                f"The best three periods contribute {contribution:.1f}% of the sum of all positive periodic returns.",
            )
        )

    if metrics.maximum_drawdown is None:
        findings.append(
            _finding(
                "drawdown_recovery",
                Status.INFO,
                "Maximum drawdown recovery",
                "No usable returns are available to assess drawdown recovery.",
            )
        )
    elif abs(metrics.maximum_drawdown) <= 1e-12:
        findings.append(
            _finding(
                "drawdown_recovery",
                Status.INFO,
                "Maximum drawdown recovery",
                "The analyzed equity path never fell below a prior peak.",
            )
        )
    elif not metrics.maximum_drawdown_recovered:
        findings.append(
            _finding(
                "drawdown_recovery",
                Status.WARN,
                "Maximum drawdown recovery",
                f"The {-metrics.maximum_drawdown:.2%} maximum drawdown had not recovered to its preceding peak by the final observation.",
            )
        )
    else:
        findings.append(
            _finding(
                "drawdown_recovery",
                Status.PASS,
                "Maximum drawdown recovery",
                f"The {-metrics.maximum_drawdown:.2%} maximum drawdown recovered to its preceding peak before the series ended.",
            )
        )
    return findings


def audit_file(
    path: str | Path, *, periods_per_year: int | None = None
) -> AuditReport:
    """Read a supported CSV and return a complete deterministic audit report."""

    if periods_per_year is not None and periods_per_year <= 0:
        raise ValueError("periods_per_year must be a positive integer")
    source_path = Path(path)
    input_type, points, findings = _read_points(source_path)
    integrity, unique_points = _integrity_findings(input_type, points)
    findings.extend(integrity)
    dated_returns, gap_dates = _to_returns(input_type, unique_points)
    findings.append(_gap_finding(gap_dates))
    metrics = calculate_metrics(
        dated_returns, periods_per_year=periods_per_year
    )
    findings.extend(_statistical_findings(metrics))
    return AuditReport(
        source=str(source_path),
        input_type=input_type,
        findings=tuple(findings),
        metrics=metrics,
    )
