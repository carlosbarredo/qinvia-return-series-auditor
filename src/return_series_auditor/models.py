"""Data models shared by the auditor, metrics, and output renderers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from typing import Any


class Status(StrEnum):
    """Severity assigned to an individual audit finding."""

    PASS = "PASS"
    INFO = "INFO"
    WARN = "WARN"
    FAIL = "FAIL"


@dataclass(frozen=True, slots=True)
class Finding:
    """A deterministic, human-readable result from one audit check."""

    code: str
    status: Status
    title: str
    explanation: str

    def as_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "status": self.status.value,
            "title": self.title,
            "explanation": self.explanation,
        }


@dataclass(frozen=True, slots=True)
class PeriodResult:
    """A dated periodic return."""

    date: date
    value: float

    def as_dict(self) -> dict[str, str | float]:
        return {"date": self.date.isoformat(), "return": self.value}


@dataclass(frozen=True, slots=True)
class Metrics:
    """Transparent statistics calculated from the usable periodic returns."""

    observations: int
    start_date: date | None
    end_date: date | None
    inferred_frequency: str
    periods_per_year: int | None
    total_compounded_return: float | None
    cagr: float | None
    annualized_volatility: float | None
    sharpe_ratio: float | None
    sortino_ratio: float | None
    maximum_drawdown: float | None
    maximum_drawdown_duration: int | None
    current_drawdown: float | None
    best_period: PeriodResult | None
    worst_period: PeriodResult | None
    return_without_best_periods: dict[int, float]
    best_three_positive_contribution_pct: float | None
    maximum_drawdown_recovered: bool | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "observations": self.observations,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "inferred_frequency": self.inferred_frequency,
            "periods_per_year": self.periods_per_year,
            "total_compounded_return": self.total_compounded_return,
            "cagr": self.cagr,
            "annualized_volatility": self.annualized_volatility,
            "sharpe_ratio": self.sharpe_ratio,
            "sortino_ratio": self.sortino_ratio,
            "maximum_drawdown": self.maximum_drawdown,
            "maximum_drawdown_duration_periods": self.maximum_drawdown_duration,
            "current_drawdown": self.current_drawdown,
            "best_period": self.best_period.as_dict() if self.best_period else None,
            "worst_period": self.worst_period.as_dict() if self.worst_period else None,
            "return_without_best_periods": {
                str(key): value
                for key, value in sorted(self.return_without_best_periods.items())
            },
            "best_three_positive_contribution_pct": (
                self.best_three_positive_contribution_pct
            ),
            "maximum_drawdown_recovered": self.maximum_drawdown_recovered,
        }


@dataclass(frozen=True, slots=True)
class AuditReport:
    """Complete result returned by an audit."""

    source: str
    input_type: str
    findings: tuple[Finding, ...]
    metrics: Metrics

    @property
    def summary_status(self) -> Status:
        statuses = {finding.status for finding in self.findings}
        if Status.FAIL in statuses:
            return Status.FAIL
        if Status.WARN in statuses:
            return Status.WARN
        return Status.PASS

    def exit_code(self, *, strict: bool = False) -> int:
        if any(finding.status is Status.FAIL for finding in self.findings):
            return 1
        if strict and any(finding.status is Status.WARN for finding in self.findings):
            return 1
        return 0

    def as_dict(self) -> dict[str, Any]:
        counts = {
            status.value: sum(
                finding.status is status for finding in self.findings
            )
            for status in Status
        }
        return {
            "schema_version": "1.0",
            "source": self.source,
            "input_type": self.input_type,
            "summary_status": self.summary_status.value,
            "finding_counts": counts,
            "metrics": self.metrics.as_dict(),
            "findings": [finding.as_dict() for finding in self.findings],
        }
