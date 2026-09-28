# tests/test_shared.py
import os
import re
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "core"))

from _shared import cap, dedupe_lines, load_dotenv, parse_dotenv, run_command


class TestCap(unittest.TestCase):
    def test_under_limit_unchanged(self):
        self.assertEqual(cap("short", 100), "short")

    def test_over_limit_truncated_with_marker(self):
        text = "x" * 3000
        result = cap(text, 100)
        self.assertTrue(result.startswith("x" * 100))
        self.assertIn("troncato", result)
        self.assertIn("2900", result)


class TestDedupeLines(unittest.TestCase):
    def test_counts_and_orders_by_frequency(self):
        lines = ["a", "b", "a", "a", "b"]
        result = dedupe_lines(lines)
        self.assertEqual(result[0], ("a", 3))
        self.assertEqual(result[1], ("b", 2))

    def test_normalize_collapses_near_identical_lines(self):
        lines = ["error at line 10", "error at line 42", "error at line 99"]
        result = dedupe_lines(lines, normalize=re.compile(r"\d+"))
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0][1], 3)


class TestRunCommand(unittest.TestCase):
    def test_captures_exit_code_and_output(self):
        code, output = run_command('python -c "print(1)"', cwd=".")
        self.assertEqual(code, 0)
        self.assertIn("1", output)

    def test_captures_nonzero_exit_code(self):
        code, _ = run_command('python -c "import sys; sys.exit(3)"', cwd=".")
        self.assertEqual(code, 3)


class TestLoadDotenv(unittest.TestCase):
    def _write_env_file(self, content: str) -> str:
        fd, path = tempfile.mkstemp(suffix=".env")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        self.addCleanup(os.remove, path)
        return path

    def test_sets_variables_not_already_in_environment(self):
        path = self._write_env_file("SOME_VAR=hello\n")
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SOME_VAR", None)
            load_dotenv(path)
            self.assertEqual(os.environ["SOME_VAR"], "hello")

    def test_does_not_override_an_already_set_variable(self):
        path = self._write_env_file("SOME_VAR=from_file\n")
        with patch.dict(os.environ, {"SOME_VAR": "from_real_env"}):
            load_dotenv(path)
            self.assertEqual(os.environ["SOME_VAR"], "from_real_env")

    def test_skips_blank_lines_and_comments(self):
        path = self._write_env_file("# a comment\n\nSOME_VAR=value\n")
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SOME_VAR", None)
            load_dotenv(path)
            self.assertEqual(os.environ["SOME_VAR"], "value")

    def test_strips_surrounding_quotes_from_value(self):
        path = self._write_env_file('SOME_VAR="quoted value"\n')
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SOME_VAR", None)
            load_dotenv(path)
            self.assertEqual(os.environ["SOME_VAR"], "quoted value")

    def test_missing_file_is_a_noop_not_an_error(self):
        load_dotenv("this_file_does_not_exist.env")  # should not raise


class TestParseDotenv(unittest.TestCase):
    """parse_dotenv() is the pure building block load_dotenv() wraps around
    os.environ - covered separately since oracle_config_sync.py also calls
    it directly, without going through os.environ at all."""

    def _write_env_file(self, content: str) -> str:
        fd, path = tempfile.mkstemp(suffix=".env")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        self.addCleanup(os.remove, path)
        return path

    def test_returns_a_plain_dict_without_touching_os_environ(self):
        path = self._write_env_file("SOME_VAR=hello\n")
        os.environ.pop("SOME_VAR", None)
        result = parse_dotenv(path)
        self.assertEqual(result, {"SOME_VAR": "hello"})
        self.assertNotIn("SOME_VAR", os.environ)

    def test_missing_file_returns_empty_dict(self):
        self.assertEqual(parse_dotenv("this_file_does_not_exist.env"), {})


if __name__ == "__main__":
    unittest.main()
