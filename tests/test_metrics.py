from __future__ import annotations

import math
import statistics
import unittest
from datetime import date

from return_series_auditor.metrics import calculate_metrics, compound, infer_frequency


class MetricsTests(unittest.TestCase):
    def test_known_metric_calculations(self) -> None:
        returns = [
            (date(2024, 1, 31), 0.10),
            (date(2024, 2, 29), -0.05),
            (date(2024, 3, 31), 0.02),
        ]

        metrics = calculate_metrics(returns, periods_per_year=12)

        self.assertEqual(metrics.observations, 3)
        self.assertEqual(metrics.inferred_frequency, "monthly")
        self.assertAlmostEqual(metrics.total_compounded_return or 0.0, 0.0659)
        self.assertAlmostEqual(
            metrics.cagr or 0.0, (1.0659**4) - 1.0
        )
        self.assertAlmostEqual(
            metrics.annualized_volatility or 0.0,
            statistics.stdev([0.10, -0.05, 0.02]) * math.sqrt(12),
        )
        self.assertAlmostEqual(metrics.maximum_drawdown or 0.0, -0.05)
        self.assertEqual(metrics.maximum_drawdown_duration, 2)
        self.assertAlmostEqual(metrics.current_drawdown or 0.0, -0.031)
        self.assertEqual(metrics.best_period.date, date(2024, 1, 31))
        self.assertEqual(metrics.worst_period.date, date(2024, 2, 29))
        self.assertAlmostEqual(metrics.return_without_best_periods[1], -0.031)
        self.assertFalse(metrics.maximum_drawdown_recovered)

    def test_frequency_inference(self) -> None:
        self.assertEqual(
            infer_frequency([date(2025, 1, 1), date(2025, 1, 2)]), "daily"
        )
        self.assertEqual(
            infer_frequency([date(2025, 1, 1), date(2025, 1, 8)]), "weekly"
        )
        self.assertEqual(
            infer_frequency([date(2025, 1, 1), date(2025, 2, 1)]), "monthly"
        )
        self.assertEqual(infer_frequency([date(2025, 1, 1)]), "unknown")

    def test_compounding_empty_series_is_zero(self) -> None:
        self.assertEqual(compound([]), 0.0)

    def test_empty_metrics_are_explicitly_unavailable(self) -> None:
        metrics = calculate_metrics([])

        self.assertEqual(metrics.observations, 0)
        self.assertIsNone(metrics.total_compounded_return)
        self.assertIsNone(metrics.maximum_drawdown)
        self.assertIsNone(metrics.best_period)

    def test_flat_series_has_zero_volatility_and_no_ratios(self) -> None:
        metrics = calculate_metrics(
            [(date(2025, month, 1), 0.0) for month in range(1, 7)]
        )

        self.assertEqual(metrics.annualized_volatility, 0.0)
        self.assertIsNone(metrics.sharpe_ratio)
        self.assertIsNone(metrics.sortino_ratio)
        self.assertTrue(metrics.maximum_drawdown_recovered)


if __name__ == "__main__":
    unittest.main()
