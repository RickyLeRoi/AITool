# tests/test_find_secrets.py
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "core"))

import find_secrets


class TestFindSecrets(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="find_secrets_test_")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def _write(self, name, content):
        with open(os.path.join(self.root, name), "w") as fh:
            fh.write(content)

    def test_clean_repo_reports_nothing(self):
        self._write("app.py", "def add(a, b):\n    return a + b\n")
        result = find_secrets.digest(self.root)
        self.assertIn("no likely secrets found", result)

    def test_detects_generic_api_key_assignment(self):
        self._write("config.py", 'API_KEY = "not-a-real-secret-value-0123456789"\n')
        result = find_secrets.digest(self.root)
        self.assertIn("generic_api_key_assignment", result)
        self.assertIn("config.py:1", result)

    def test_detects_aws_key_and_private_key_header(self):
        self._write(
            "creds.txt",
            "AKIAIOSFODNN7EXAMPLE\n-----BEGIN RSA PRIVATE KEY-----\n",
        )
        result = find_secrets.digest(self.root)
        self.assertIn("aws_access_key", result)
        self.assertIn("private_key_header", result)


if __name__ == "__main__":
    unittest.main()
