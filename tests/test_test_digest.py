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


if __name__ == "__main__":
    unittest.main()
