# tests/test_diff_digest.py
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "core"))

import diff_digest


def _git(args, cwd):
    subprocess.run(["git"] + args, cwd=cwd, check=True, capture_output=True, text=True)


class TestDiffDigest(unittest.TestCase):
    def setUp(self):
        self.repo = tempfile.mkdtemp(prefix="diff_digest_test_")
        _git(["init", "-q"], self.repo)
        _git(["config", "user.email", "test@example.com"], self.repo)
        _git(["config", "user.name", "Test"], self.repo)
        with open(os.path.join(self.repo, "mod.py"), "w") as fh:
            fh.write("def foo():\n    return 1\n")
        _git(["add", "mod.py"], self.repo)
        _git(["commit", "-q", "-m", "initial"], self.repo)

    def tearDown(self):
        shutil.rmtree(self.repo, ignore_errors=True)

    def test_no_changes_reports_no_changes(self):
        result = diff_digest.digest(self.repo)
        self.assertEqual(result, "no changes (working tree matches ref)")

    def test_reports_stat_and_touched_symbol(self):
        with open(os.path.join(self.repo, "mod.py"), "w") as fh:
            fh.write("def foo():\n    return 2\n\n\ndef bar():\n    return 3\n")
        result = diff_digest.digest(self.repo)
        self.assertIn("1 files changed", result)
        self.assertIn("mod.py:", result)
        self.assertIn("touched symbols", result)
        self.assertIn("foo", result)


if __name__ == "__main__":
    unittest.main()
