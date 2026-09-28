# tests/test_project_status.py
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "core"))

import project_status


def _git(args, cwd):
    subprocess.run(["git"] + args, cwd=cwd, check=True, capture_output=True, text=True)


class TestProjectStatus(unittest.TestCase):
    def setUp(self):
        self.repo = tempfile.mkdtemp(prefix="project_status_test_")
        _git(["init", "-q"], self.repo)
        _git(["config", "user.email", "test@example.com"], self.repo)
        _git(["config", "user.name", "Test"], self.repo)
        with open(os.path.join(self.repo, "mod.py"), "w") as fh:
            fh.write("def foo():\n    return 1\n")
        _git(["add", "mod.py"], self.repo)
        _git(["commit", "-q", "-m", "initial commit"], self.repo)

    def tearDown(self):
        shutil.rmtree(self.repo, ignore_errors=True)

    def test_reports_files_commits_and_pending_diff(self):
        with open(os.path.join(self.repo, "mod.py"), "w") as fh:
            fh.write("def foo():\n    return 2\n")
        result = project_status.digest(self.repo)
        self.assertIn("codebase: 1 files", result)
        self.assertIn("initial commit", result)
        self.assertIn("mod.py:", result)

    def test_includes_test_results_when_command_given(self):
        result = project_status.digest(self.repo, test_command='python -c "print(1)"')
        self.assertIn("tests:", result)
        self.assertIn("exit_code=0", result)


if __name__ == "__main__":
    unittest.main()
