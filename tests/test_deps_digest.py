# tests/test_deps_digest.py
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "core"))

import deps_digest


class TestDepsDigest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="deps_digest_test_")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def _write(self, name, content):
        with open(os.path.join(self.root, name), "w") as fh:
            fh.write(content)

    def test_no_manifest_files(self):
        result = deps_digest.digest(self.root)
        self.assertIn("no recognized manifest files", result)

    def test_parses_package_json(self):
        self._write(
            "package.json",
            '{"dependencies": {"react": "^18.0.0"}, "devDependencies": {"vitest": "^1.0.0"}}',
        )
        result = deps_digest.digest(self.root)
        self.assertIn("react@^18.0.0 (dependencies)", result)
        self.assertIn("vitest@^1.0.0 (devDependencies)", result)

    def test_parses_requirements_txt(self):
        self._write("requirements.txt", "requests==2.31.0\n# a comment\nflask>=3.0\n")
        result = deps_digest.digest(self.root)
        self.assertIn("requests==2.31.0", result)
        self.assertIn("flask>=3.0", result)

    def test_parses_csproj(self):
        self._write(
            "App.csproj",
            '<Project><ItemGroup><PackageReference Include="Newtonsoft.Json" Version="13.0.3" /></ItemGroup></Project>',
        )
        result = deps_digest.digest(self.root)
        self.assertIn("Newtonsoft.Json 13.0.3", result)


if __name__ == "__main__":
    unittest.main()
