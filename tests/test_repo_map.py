# tests/test_repo_map.py
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "core"))

import repo_map


class TestRepoMap(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="repo_map_test_")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def _write(self, rel_path: str, content: str):
        path = os.path.join(self.root, rel_path)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            fh.write(content)

    def test_extracts_python_top_level_symbols(self):
        self._write("mod.py", "def foo():\n    pass\n\nclass Bar:\n    pass\n")
        result = repo_map.digest(self.root)
        self.assertIn("mod.py: foo, Bar", result)

    def test_extracts_js_function_and_class_names(self):
        self._write("app.js", "function handleClick() {}\nclass Widget {}\n")
        result = repo_map.digest(self.root)
        self.assertIn("handleClick", result)
        self.assertIn("Widget", result)

    def test_excludes_node_modules_and_git_dirs(self):
        self._write("node_modules/pkg/index.js", "function ignored() {}")
        self._write(".git/config", "should not appear")
        self._write("real.py", "def kept():\n    pass\n")
        result = repo_map.digest(self.root)
        self.assertIn("real.py", result)
        self.assertNotIn("node_modules", result)
        self.assertNotIn("ignored", result)

    def test_file_count_header(self):
        self._write("a.py", "x = 1\n")
        self._write("b.py", "y = 2\n")
        result = repo_map.digest(self.root)
        self.assertTrue(result.startswith("2 files"))


if __name__ == "__main__":
    unittest.main()
