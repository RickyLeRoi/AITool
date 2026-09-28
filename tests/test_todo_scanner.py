# tests/test_todo_scanner.py
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "core"))

import todo_scanner


class TestTodoScanner(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="todo_scanner_test_")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def _write(self, name, content):
        with open(os.path.join(self.root, name), "w") as fh:
            fh.write(content)

    def test_no_markers_found(self):
        self._write("clean.py", "x = 1\n")
        result = todo_scanner.digest(self.root)
        self.assertIn("no TODO/FIXME/HACK/XXX markers found", result)

    def test_groups_by_marker_type(self):
        self._write(
            "app.py",
            "# TODO: add validation\n"
            "# FIXME: race condition here\n"
            "# TODO: refactor this later\n",
        )
        result = todo_scanner.digest(self.root)
        self.assertIn("3 markers found", result)
        self.assertIn("TODO (2)", result)
        self.assertIn("FIXME (1)", result)
        self.assertIn("add validation", result)


if __name__ == "__main__":
    unittest.main()
