from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from return_series_auditor.cli import main


class CliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name)

    def write_csv(self, content: str) -> Path:
        path = self.root / "input.csv"
        path.write_text(content, encoding="utf-8")
        return path

    def run_cli(self, arguments: list[str]) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = main(arguments)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_json_output_and_non_strict_exit_code(self) -> None:
        path = self.write_csv(
            "date,return\n2025-01-01,0.01\n2025-02-01,0.02\n"
        )

        code, stdout, stderr = self.run_cli([str(path), "--format", "json"])
        document = json.loads(stdout)

        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")
        self.assertEqual(document["schema_version"], "1.0")
        self.assertEqual(document["input_type"], "return")
        self.assertEqual(document["summary_status"], "WARN")
        self.assertEqual(document["metrics"]["observations"], 2)

    def test_markdown_output(self) -> None:
        path = self.write_csv(
            "date,equity\n2025-01-01,100\n2025-02-01,101\n"
        )

        code, stdout, _ = self.run_cli([str(path), "--format", "markdown"])

        self.assertEqual(code, 0)
        self.assertIn("# Return Series Audit", stdout)
        self.assertIn("| Metric | Value |", stdout)
        self.assertIn("| Status | Check | Explanation |", stdout)

    def test_failure_exit_code(self) -> None:
        path = self.write_csv("date,return\n2025-01-01,-1.0\n")

        code, stdout, _ = self.run_cli([str(path)])

        self.assertEqual(code, 1)
        self.assertIn("[FAIL] Impossible returns", stdout)

    def test_strict_mode_turns_warning_into_failure_exit(self) -> None:
        path = self.write_csv(
            "date,return\n2025-01-01,0.01\n2025-02-01,0.02\n"
        )

        code, _, _ = self.run_cli([str(path), "--strict"])

        self.assertEqual(code, 1)

    def test_unreadable_input_exit_code(self) -> None:
        code, stdout, stderr = self.run_cli([str(self.root / "missing.csv")])

        self.assertEqual(code, 2)
        self.assertEqual(stdout, "")
        self.assertIn("return-audit: error:", stderr)

    def test_unsupported_header_exit_code(self) -> None:
        path = self.write_csv("date,price\n2025-01-01,100\n")

        code, _, stderr = self.run_cli([str(path)])

        self.assertEqual(code, 2)
        self.assertIn("exactly one of 'return' or 'equity'", stderr)

    def test_non_utf8_input_exit_code(self) -> None:
        path = self.root / "binary.csv"
        path.write_bytes(b"date,return\n2025-01-01,\xff\n")

        code, stdout, stderr = self.run_cli([str(path)])

        self.assertEqual(code, 2)
        self.assertEqual(stdout, "")
        self.assertIn("cannot parse CSV input", stderr)


if __name__ == "__main__":
    unittest.main()
