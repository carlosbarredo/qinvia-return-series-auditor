"""Metric calculations for dated periodic returns."""

from __future__ import annotations

import math
import statistics
from datetime import date
from typing import Sequence

from return_series_auditor.models import Metrics, PeriodResult

EPSILON = 1e-12
ANNUALIZATION_FACTORS = {"daily": 252, "weekly": 52, "monthly": 12}


def infer_frequency(dates: Sequence[date]) -> str:
    """Infer daily, weekly, or monthly frequency from the median date spacing."""

    unique_dates = sorted(set(dates))
    if len(unique_dates) < 2:
        return "unknown"
    gaps = [
        (current - previous).days
        for previous, current in zip(unique_dates, unique_dates[1:])
        if current > previous
    ]
    if not gaps:
        return "unknown"
    median_gap = statistics.median(gaps)
    if median_gap <= 3:
        return "daily"
    if median_gap <= 10:
        return "weekly"
    return "monthly"


def compound(returns: Sequence[float]) -> float:
    """Compound decimal periodic returns into one total return."""

    return math.prod(1.0 + value for value in returns) - 1.0


def _drawdown_metrics(
    dated_returns: Sequence[tuple[date, float]],
) -> tuple[float, int, float, bool]:
    wealth = 1.0
    peak = 1.0
    underwater_periods = 0
    longest_underwater = 0
    maximum_drawdown = 0.0
    maximum_drawdown_index = -1
    peak_at_maximum_drawdown = 1.0
    wealth_path: list[float] = []

    for index, (_, periodic_return) in enumerate(dated_returns):
        wealth *= 1.0 + periodic_return
        wealth_path.append(wealth)
        if wealth >= peak:
            peak = wealth
            underwater_periods = 0
        else:
            underwater_periods += 1
            longest_underwater = max(longest_underwater, underwater_periods)
        drawdown = wealth / peak - 1.0
        if drawdown < maximum_drawdown:
            maximum_drawdown = drawdown
            maximum_drawdown_index = index
            peak_at_maximum_drawdown = peak

    current_drawdown = wealth / peak - 1.0
    if maximum_drawdown_index < 0:
        recovered = True
    else:
        recovered = any(
            later_wealth >= peak_at_maximum_drawdown - EPSILON
            for later_wealth in wealth_path[maximum_drawdown_index + 1 :]
        )
    return maximum_drawdown, longest_underwater, current_drawdown, recovered


def calculate_metrics(
    dated_returns: Sequence[tuple[date, float]],
    *,
    periods_per_year: int | None = None,
) -> Metrics:
    """Calculate all reported statistics from finite periodic returns."""

    ordered = sorted(dated_returns, key=lambda item: item[0])
    values = [value for _, value in ordered]
    observations = len(values)
    frequency = infer_frequency([period_date for period_date, _ in ordered])
    annualization = periods_per_year or ANNUALIZATION_FACTORS.get(frequency)

    if not values:
        return Metrics(
            observations=0,
            start_date=None,
            end_date=None,
            inferred_frequency=frequency,
            periods_per_year=annualization,
            total_compounded_return=None,
            cagr=None,
            annualized_volatility=None,
            sharpe_ratio=None,
            sortino_ratio=None,
            maximum_drawdown=None,
            maximum_drawdown_duration=None,
            current_drawdown=None,
            best_period=None,
            worst_period=None,
            return_without_best_periods={},
            best_three_positive_contribution_pct=None,
            maximum_drawdown_recovered=None,
        )

    total_return = compound(values)
    terminal_wealth = total_return + 1.0
    cagr = None
    if annualization is not None and terminal_wealth > 0.0:
        cagr = terminal_wealth ** (annualization / observations) - 1.0

    sample_deviation = statistics.stdev(values) if observations >= 2 else None
    annualized_volatility = (
        sample_deviation * math.sqrt(annualization)
        if sample_deviation is not None and annualization is not None
        else None
    )
    sharpe = None
    if (
        sample_deviation is not None
        and sample_deviation > EPSILON
        and annualization is not None
    ):
        sharpe = statistics.fmean(values) / sample_deviation * math.sqrt(annualization)

    downside_deviation = math.sqrt(
        statistics.fmean(min(value, 0.0) ** 2 for value in values)
    )
    sortino = None
    if downside_deviation > EPSILON and annualization is not None:
        sortino = (
            statistics.fmean(values)
            / downside_deviation
            * math.sqrt(annualization)
        )

    maximum_drawdown, duration, current_drawdown, recovered = _drawdown_metrics(
        ordered
    )
    best_date, best_value = max(ordered, key=lambda item: (item[1], -item[0].toordinal()))
    worst_date, worst_value = min(ordered, key=lambda item: (item[1], item[0].toordinal()))

    ranked_indices = sorted(
        range(observations), key=lambda index: (-values[index], index)
    )
    without_best: dict[int, float] = {}
    for count in (1, 3, 5):
        removed = set(ranked_indices[:count])
        without_best[count] = compound(
            [value for index, value in enumerate(values) if index not in removed]
        )

    positives = sorted((value for value in values if value > 0.0), reverse=True)
    positive_contribution = None
    if positives:
        positive_contribution = sum(positives[:3]) / sum(positives) * 100.0

    return Metrics(
        observations=observations,
        start_date=ordered[0][0],
        end_date=ordered[-1][0],
        inferred_frequency=frequency,
        periods_per_year=annualization,
        total_compounded_return=total_return,
        cagr=cagr,
        annualized_volatility=annualized_volatility,
        sharpe_ratio=sharpe,
        sortino_ratio=sortino,
        maximum_drawdown=maximum_drawdown,
        maximum_drawdown_duration=duration,
        current_drawdown=current_drawdown,
        best_period=PeriodResult(best_date, best_value),
        worst_period=PeriodResult(worst_date, worst_value),
        return_without_best_periods=without_best,
        best_three_positive_contribution_pct=positive_contribution,
        maximum_drawdown_recovered=recovered,
    )
