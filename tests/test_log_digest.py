# tests/test_log_digest.py
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "core"))

import log_digest


class TestLogDigest(unittest.TestCase):
    def _write_log(self, lines):
        fh = tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False)
        fh.write("\n".join(lines))
        fh.close()
        return fh.name

    def test_groups_repeated_patterns_ignoring_timestamps_and_numbers(self):
        lines = [
            "2026-09-25 10:00:01 INFO request id=1 ok",
            "2026-09-25 10:00:02 INFO request id=2 ok",
            "2026-09-25 10:00:03 ERROR request id=3 timeout",
        ]
        path = self._write_log(lines)
        try:
            result = log_digest.digest(path, top_n=5)
        finally:
            os.remove(path)
        self.assertIn("total_lines=3", result)
        self.assertIn("distinct_patterns=2", result)
        self.assertIn("[x2]", result)
        self.assertIn("[x1]", result)

    def test_time_range_reported(self):
        lines = [
            "2026-09-25 10:00:01 INFO start",
            "2026-09-25 10:05:00 INFO end",
        ]
        path = self._write_log(lines)
        try:
            result = log_digest.digest(path, top_n=5)
        finally:
            os.remove(path)
        self.assertIn("2026-09-25 10:00:01 .. 2026-09-25 10:05:00", result)

    def test_no_timestamps_still_works(self):
        lines = ["plain line one", "plain line one", "plain line two"]
        path = self._write_log(lines)
        try:
            result = log_digest.digest(path, top_n=5)
        finally:
            os.remove(path)
        self.assertIn("no timestamps found", result)
        self.assertIn("[x2] plain line one", result)


if __name__ == "__main__":
    unittest.main()
