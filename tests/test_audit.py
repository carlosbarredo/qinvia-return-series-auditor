from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from return_series_auditor.audit import audit_file
from return_series_auditor.models import AuditReport, Status


def status_for(report: AuditReport, code: str) -> Status:
    return next(finding.status for finding in report.findings if finding.code == code)


class AuditTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name)

    def write_csv(self, content: str) -> Path:
        path = self.root / "input.csv"
        path.write_text(content, encoding="utf-8")
        return path

    def test_valid_returns_input(self) -> None:
        path = self.write_csv(
            "date,return\n"
            + "".join(
                f"2024-{month:02d}-01,{0.005 + month / 10000:.4f}\n"
                for month in range(1, 13)
            )
        )

        report = audit_file(path)

        self.assertEqual(report.input_type, "return")
        self.assertEqual(report.metrics.observations, 12)
        self.assertNotIn(Status.FAIL, {finding.status for finding in report.findings})
        self.assertEqual(status_for(report, "missing_values"), Status.PASS)
        self.assertEqual(status_for(report, "duplicate_dates"), Status.PASS)

    def test_valid_equity_input_is_converted_to_returns(self) -> None:
        path = self.write_csv(
            "date,equity\n"
            "2024-01-01,100\n"
            "2024-02-01,110\n"
            "2024-03-01,99\n"
            "2024-04-01,108\n"
        )

        report = audit_file(path)

        self.assertEqual(report.input_type, "equity")
        self.assertEqual(report.metrics.observations, 3)
        self.assertAlmostEqual(
            report.metrics.total_compounded_return or 0.0, 0.08
        )
        self.assertEqual(status_for(report, "positive_equity"), Status.PASS)

    def test_duplicate_and_unordered_dates_fail(self) -> None:
        path = self.write_csv(
            "date,return\n"
            "2025-01-02,0.01\n"
            "2025-01-02,0.02\n"
            "2025-01-01,0.03\n"
        )

        report = audit_file(path)

        self.assertEqual(status_for(report, "duplicate_dates"), Status.FAIL)
        self.assertEqual(status_for(report, "date_order"), Status.FAIL)
        self.assertEqual(report.metrics.observations, 2)

    def test_missing_invalid_and_non_finite_values_fail(self) -> None:
        path = self.write_csv(
            "date,return\n"
            "2025-01-01,\n"
            "wrong,0.01\n"
            "2025-01-03,nope\n"
            "2025-01-04,NaN\n"
            "2025-01-05,0.01\n"
        )

        report = audit_file(path)

        self.assertEqual(status_for(report, "missing_values"), Status.FAIL)
        self.assertEqual(status_for(report, "unparseable_values"), Status.FAIL)
        self.assertEqual(status_for(report, "non_finite_numbers"), Status.FAIL)
        self.assertEqual(report.metrics.observations, 1)

    def test_return_at_or_below_negative_one_fails(self) -> None:
        path = self.write_csv(
            "date,return\n2025-01-01,0.01\n2025-02-01,-1.0\n"
        )

        report = audit_file(path)

        self.assertEqual(status_for(report, "return_floor"), Status.FAIL)
        self.assertIsNone(report.metrics.cagr)

    def test_non_positive_equity_fails_and_is_excluded(self) -> None:
        path = self.write_csv(
            "date,equity\n"
            "2025-01-01,100\n"
            "2025-02-01,0\n"
            "2025-03-01,110\n"
        )

        report = audit_file(path)

        self.assertEqual(status_for(report, "positive_equity"), Status.FAIL)
        self.assertEqual(report.metrics.observations, 1)
        self.assertAlmostEqual(report.metrics.total_compounded_return or 0.0, 0.10)

    def test_short_track_record_warns(self) -> None:
        path = self.write_csv(
            "date,return\n2025-01-01,0.01\n2025-02-01,0.02\n"
        )

        report = audit_file(path)

        self.assertEqual(status_for(report, "track_record_length"), Status.WARN)
        self.assertEqual(report.exit_code(), 0)
        self.assertEqual(report.exit_code(strict=True), 1)

    def test_flat_series_warns_about_variance(self) -> None:
        path = self.write_csv(
            "date,return\n"
            + "".join(f"2024-{month:02d}-01,0\n" for month in range(1, 13))
        )

        report = audit_file(path)

        self.assertEqual(status_for(report, "variance"), Status.WARN)

    def test_unrecovered_drawdown_warns(self) -> None:
        path = self.write_csv(
            "date,return\n"
            "2025-01-01,0.10\n"
            "2025-02-01,-0.20\n"
            "2025-03-01,0.01\n"
        )

        report = audit_file(path)

        self.assertEqual(status_for(report, "drawdown_recovery"), Status.WARN)
        self.assertFalse(report.metrics.maximum_drawdown_recovered)

    def test_suspicious_gap_warns(self) -> None:
        path = self.write_csv(
            "date,return\n"
            "2025-01-01,0.01\n"
            "2025-01-08,0.01\n"
            "2025-01-15,0.01\n"
            "2025-03-15,0.01\n"
        )

        report = audit_file(path)

        self.assertEqual(status_for(report, "suspicious_gaps"), Status.WARN)

    def test_periods_per_year_override(self) -> None:
        path = self.write_csv(
            "date,return\n2025-01-01,0.01\n2025-02-01,0.02\n"
        )

        report = audit_file(path, periods_per_year=4)

        self.assertEqual(report.metrics.inferred_frequency, "monthly")
        self.assertEqual(report.metrics.periods_per_year, 4)
        self.assertEqual(status_for(report, "track_record_length"), Status.WARN)

    def test_header_only_input_has_no_usable_track_record(self) -> None:
        path = self.write_csv("date,return\n")

        report = audit_file(path)

        self.assertEqual(report.metrics.observations, 0)
        self.assertEqual(status_for(report, "track_record_length"), Status.FAIL)
        self.assertEqual(report.exit_code(), 1)


if __name__ == "__main__":
    unittest.main()
