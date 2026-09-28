# tests/test_build_digest.py
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "core"))

import build_digest

CLEAN_CMD = 'python -c "print(\'build finished\')"'
ERRORS_CMD = (
    'python -c "'
    "print('src/a.ts(10,5): error TS2322: type mismatch');"
    "print('src/a.ts(99,5): error TS2322: type mismatch');"
    "print('src/c.ts(30,5): warning: unused variable')"
    '"'
)


class TestBuildDigest(unittest.TestCase):
    def test_clean_build_reports_clean(self):
        result = build_digest.digest(CLEAN_CMD, cwd=".")
        self.assertIn("exit_code=0", result)
        self.assertIn("build clean", result)

    def test_errors_are_deduplicated_by_normalizing_numbers(self):
        result = build_digest.digest(ERRORS_CMD, cwd=".")
        self.assertIn("[x2] ", result)
        self.assertIn("TS2322", result)
        self.assertIn("warnings", result)

    def test_output_is_capped(self):
        # Distinct messages (not just repeated ones) so dedup can't collapse
        # them into one short line and the cap actually gets exercised.
        cmd = 'python -c "for i in range(60): print(\'error: boom type \' + chr(97 + i % 26))"'
        result = build_digest.digest(cmd, cwd=".", max_chars=400)
        self.assertLessEqual(len(result), 500)
        self.assertIn("troncato", result)


if __name__ == "__main__":
    unittest.main()
