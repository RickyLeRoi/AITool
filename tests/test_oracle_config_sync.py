# tests/test_oracle_config_sync.py
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "core"))

import oracle_config_sync

_ORACLE_ENV_KEYS = (
    "ORACLE_CONNECTION_STRING",
    "ORACLE_USERNAME",
    "ORACLE_PASSWORD",
    "ORACLE_WALLET",
    "ORACLE_USE_OCI",
)


class TestOracleConfigSync(unittest.TestCase):
    def setUp(self):
        # sync() layers real os.environ on top of the .env file (real env
        # wins, same precedence as load_dotenv()) - but importing
        # local_llm_client anywhere in this test run already calls
        # load_dotenv() eagerly, which pulls EVERY key from the real
        # project .env into os.environ, ORACLE_* included, not just
        # LOCAL_LLM_*. Without clearing these first, tests here would see
        # whatever real Oracle credentials happen to be in that file
        # instead of the values they explicitly set up.
        self._env_backup = {}
        for key in _ORACLE_ENV_KEYS:
            if key in os.environ:
                self._env_backup[key] = os.environ.pop(key)
        self.addCleanup(os.environ.update, self._env_backup)

        fd, self.template_path = tempfile.mkstemp(suffix=".yaml")
        os.close(fd)
        fd, self.output_path = tempfile.mkstemp(suffix=".yaml")
        os.close(fd)
        fd, self.env_path = tempfile.mkstemp(suffix=".env")
        os.close(fd)
        os.remove(self.env_path)  # most tests want "no .env file" as the starting point
        self.addCleanup(os.remove, self.template_path)
        self.addCleanup(os.remove, self.output_path)
        self.addCleanup(lambda: os.path.exists(self.env_path) and os.remove(self.env_path))

    def _write_template(self, content: str) -> None:
        with open(self.template_path, "w", encoding="utf-8") as f:
            f.write(content)

    def _write_env(self, content: str) -> None:
        with open(self.env_path, "w", encoding="utf-8") as f:
            f.write(content)

    def _read_output(self) -> str:
        with open(self.output_path, "r", encoding="utf-8") as f:
            return f.read()

    def _sync(self):
        oracle_config_sync.sync(self.template_path, self.output_path, self.env_path)

    def test_resolves_simple_placeholder_from_env_file(self):
        self._write_template("connectionString: ${ORACLE_CONNECTION_STRING}\n")
        self._write_env("ORACLE_CONNECTION_STRING=host:1521/svc\n")
        self._sync()
        self.assertEqual(self._read_output(), "connectionString: host:1521/svc\n")

    def test_real_os_env_var_wins_over_env_file(self):
        self._write_template("connectionString: ${ORACLE_CONNECTION_STRING}\n")
        self._write_env("ORACLE_CONNECTION_STRING=from-file\n")
        with patch.dict(os.environ, {"ORACLE_CONNECTION_STRING": "from-real-env"}):
            self._sync()
        self.assertEqual(self._read_output(), "connectionString: from-real-env\n")

    def test_uses_default_when_var_missing_everywhere(self):
        self._write_template("useOCI: ${ORACLE_USE_OCI:false}\n")
        self._sync()
        self.assertEqual(self._read_output(), "useOCI: false\n")

    def test_empty_default_resolves_to_empty_string(self):
        self._write_template("walletLocation: ${ORACLE_WALLET:}\n")
        self._sync()
        self.assertEqual(self._read_output(), "walletLocation: \n")

    def test_env_file_value_overrides_its_own_default(self):
        self._write_template("useOCI: ${ORACLE_USE_OCI:false}\n")
        self._write_env("ORACLE_USE_OCI=true\n")
        self._sync()
        self.assertEqual(self._read_output(), "useOCI: true\n")

    def test_missing_required_var_raises_clear_error(self):
        self._write_template("user: ${ORACLE_USERNAME}\n")
        with self.assertRaises(ValueError) as ctx:
            self._sync()
        self.assertIn("ORACLE_USERNAME", str(ctx.exception))

    def test_second_call_reflects_an_edited_env_file_without_restarting_anything(self):
        """This is the whole point of the module: --watch calls sync() over
        and over in one long-running process, so a value must never get
        "stuck" from an earlier call once the .env file on disk changes."""
        self._write_template("connectionString: ${ORACLE_CONNECTION_STRING}\n")

        self._write_env("ORACLE_CONNECTION_STRING=first-value\n")
        self._sync()
        self.assertIn("first-value", self._read_output())

        self._write_env("ORACLE_CONNECTION_STRING=second-value\n")
        self._sync()
        content = self._read_output()
        self.assertIn("second-value", content)
        self.assertNotIn("first-value", content)

    def test_real_vendored_template_resolves_with_all_required_vars_set(self):
        """Sanity check that the actual vendored oracledb.template.yaml (not
        a hand-written stand-in) only requires the vars we document, and
        that our regex understands every placeholder in it."""
        self._write_env(
            "ORACLE_CONNECTION_STRING=host:1521/svc\n"
            "ORACLE_USERNAME=u\n"
            "ORACLE_PASSWORD=p\n"
        )
        oracle_config_sync.sync(oracle_config_sync.TEMPLATE_PATH, self.output_path, self.env_path)
        content = self._read_output()
        self.assertNotIn("${", content)
        self.assertIn("host:1521/svc", content)


if __name__ == "__main__":
    unittest.main()
