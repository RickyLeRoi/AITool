# tests/test_test_digest.py
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "core"))

import test_digest

PASS_CMD = (
    'python -c "print(\'3 passed in 0.01s\')"'
)
FAIL_CMD = (
    'python -c "'
    "print('test_mod.py::test_a PASSED');"
    "print('test_mod.py::test_b FAILED');"
    "print('E   AssertionError: assert 1 == 2');"
    "print('1 failed, 1 passed in 0.02s')"
    '"'
)


class TestTestDigest(unittest.TestCase):
    def test_passing_command_reports_no_failures(self):
        result = test_digest.digest(PASS_CMD, cwd=".")
        self.assertIn("exit_code=0", result)
        self.assertIn("no failures detected", result)

    def test_failing_output_extracts_summary_and_dedupes(self):
        result = test_digest.digest(FAIL_CMD, cwd=".")
        self.assertIn("1 failed, 1 passed in 0.02s", result)
        self.assertIn("AssertionError", result)
        # verbose PASSED/FAILED lines must not be picked up as the summary line
        self.assertNotIn("test_b FAILED\n", result.split("failures", 1)[0])

    def test_output_is_capped(self):
        # Distinct messages (not just repeated ones) so dedup can't collapse
        # them into one short line and the cap actually gets exercised.
        cmd = 'python -c "for i in range(60): print(\'FAILED test_\' + chr(97 + i % 26))"'
        result = test_digest.digest(cmd, cwd=".", max_chars=500)
        self.assertLessEqual(len(result), 600)
        self.assertIn("troncato", result)

    def test_digest_reports_totals_line(self):
        result = test_digest.digest(PASS_CMD, cwd=".")
        self.assertIn("totals: passed=3 failed=0 skipped=0 total=3 (pytest)", result)

    def test_digest_reports_unrecognized_totals_instead_of_guessing(self):
        result = test_digest.digest('python -c "print(\'all good\')"', cwd=".")
        self.assertIn("totals: not recognized", result)

    def test_dotnet_zero_failed_summary_is_not_a_failure(self):
        cmd = 'python -c "print(\'Test summary: total: 42, failed: 0, succeeded: 42, skipped: 0, duration: 3.2s\')"'
        result = test_digest.digest(cmd, cwd=".")
        self.assertIn("no failures detected", result)
        self.assertIn("total=42", result)


class TestParseTotals(unittest.TestCase):
    def assertTotals(self, output, passed, failed, skipped, total):
        totals = test_digest.parse_totals(output)
        self.assertIsNotNone(totals)
        self.assertEqual(
            (totals["passed"], totals["failed"], totals["skipped"], totals["total"]),
            (passed, failed, skipped, total),
        )

    def test_vstest_lines_are_summed_across_assemblies(self):
        output = (
            "Passed!  - Failed:     0, Passed:    40, Skipped:     2, Total:    42, Duration: 1 s - A.Tests.dll (net8.0)\n"
            "Failed!  - Failed:     1, Passed:     9, Skipped:     0, Total:    10, Duration: 2 s - B.Tests.dll (net8.0)\n"
        )
        self.assertTotals(output, 49, 1, 2, 52)

    def test_dotnet_aggregate_summary_wins_over_assembly_lines(self):
        output = (
            "Passed!  - Failed: 0, Passed: 40, Skipped: 2, Total: 42, Duration: 1 s - A.Tests.dll (net8.0)\n"
            "Test summary: total: 42, failed: 0, succeeded: 40, skipped: 2, duration: 1.1s\n"
        )
        totals = test_digest.parse_totals(output)
        self.assertEqual(totals["source"], "dotnet")
        self.assertEqual(totals["total"], 42)

    def test_mtp_multiline_block(self):
        output = (
            "Test run summary: Passed! - bin\\Debug\\net9.0\\Tests.dll (net9.0|x64)\n"
            "  total: 12\n  failed: 1\n  succeeded: 10\n  skipped: 1\n  duration: 1s 234ms\n"
        )
        self.assertTotals(output, 10, 1, 1, 12)

    def test_unittest_ok_with_skips(self):
        self.assertTotals("....s.\n---\nRan 72 tests in 0.512s\n\nOK (skipped=2)\n", 70, 0, 2, 72)

    def test_unittest_failed_counts_failures_and_errors(self):
        self.assertTotals("Ran 10 tests in 0.1s\n\nFAILED (failures=1, errors=2, skipped=1)\n", 6, 3, 1, 10)

    def test_pytest_summary_with_errors_and_warnings(self):
        output = "===== 1 failed, 5 passed, 2 skipped, 1 error, 3 warnings in 0.42s =====\n"
        self.assertTotals(output, 5, 2, 2, 9)

    def test_jest_tests_line(self):
        output = "Test Suites: 1 failed, 3 passed, 4 total\nTests:       1 failed, 1 skipped, 40 passed, 42 total\n"
        self.assertTotals(output, 40, 1, 1, 42)

    def test_unknown_output_returns_none(self):
        self.assertIsNone(test_digest.parse_totals("build succeeded\n"))


if __name__ == "__main__":
    unittest.main()
