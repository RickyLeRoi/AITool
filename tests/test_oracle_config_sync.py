# tests/test_oracle_config_sync.py
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "core"))

import oracle_config_sync

_ORACLE_ENV_KEYS = (
    "ORACLE_CONNECTION_STRING",
    "ORACLE_HOST",
    "ORACLE_USERNAME",
    "ORACLE_PASSWORD",
    "ORACLE_USER_SECRETS_ID",
    "ORACLE_SECRET_NAME",
    "ORACLE_WALLET",
    "ORACLE_USE_OCI",
)

_DESCRIPTOR = (
    "(DESCRIPTION = (ADDRESS=(PROTOCOL = TCP)(HOST = db.example.local)(PORT = 1521))"
    "(CONNECT_DATA = (SERVER = DEDICATED)(SERVICE_NAME = SVC.example.local)))"
)
_ODP = f"Data Source={_DESCRIPTOR};PERSIST SECURITY INFO=True;USER ID=APP_USER;PASSWORD=app_pwd"
_TEMPLATE = (
    "connectionString: ${ORACLE_CONNECTION_STRING}\n"
    "user: ${ORACLE_USERNAME}\n"
    "password: ${ORACLE_PASSWORD}\n"
)


class _StopWatching(Exception):
    pass


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

        self.secrets_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.secrets_dir, True)
        self.secrets_path = os.path.join(self.secrets_dir, "secrets.json")
        self.real_user_secrets_path = oracle_config_sync.user_secrets_path
        patcher = patch.object(oracle_config_sync, "user_secrets_path", return_value=self.secrets_path)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _write_template(self, content: str) -> None:
        with open(self.template_path, "w", encoding="utf-8") as f:
            f.write(content)

    def _write_env(self, content: str) -> None:
        with open(self.env_path, "w", encoding="utf-8") as f:
            f.write(content)

    def _write_secrets(self, secrets: dict, encoding: str = "utf-8") -> None:
        with open(self.secrets_path, "w", encoding=encoding) as f:
            json.dump(secrets, f)

    def _read_output(self) -> str:
        with open(self.output_path, "r", encoding="utf-8") as f:
            return f.read()

    def _sync(self):
        oracle_config_sync.sync(self.template_path, self.output_path, self.env_path)

    def test_full_connection_string_is_split_into_template_vars(self):
        self._write_template(_TEMPLATE)
        self._write_env(f"ORACLE_CONNECTION_STRING={_ODP}\n")
        self._sync()
        self.assertEqual(
            self._read_output(),
            "connectionString: db.example.local:1521/SVC.example.local\n"
            "user: APP_USER\n"
            "password: app_pwd\n",
        )

    def test_real_os_env_var_wins_over_env_file(self):
        self._write_template(_TEMPLATE)
        self._write_env("ORACLE_CONNECTION_STRING=Data Source=file:1/f;USER ID=u;PASSWORD=p\n")
        with patch.dict(os.environ, {"ORACLE_CONNECTION_STRING": "Data Source=real:1/r;USER ID=u;PASSWORD=p"}):
            self._sync()
        self.assertIn("connectionString: real:1/r\n", self._read_output())

    def test_host_user_password_compose_the_connection(self):
        self._write_template(_TEMPLATE)
        self._write_env("ORACLE_HOST=host:1521/svc\nORACLE_USERNAME=u\nORACLE_PASSWORD=p\n")
        self._sync()
        self.assertEqual(self._read_output(), "connectionString: host:1521/svc\nuser: u\npassword: p\n")

    def test_host_accepts_a_tns_descriptor_too(self):
        self._write_template(_TEMPLATE)
        self._write_env(f"ORACLE_HOST={_DESCRIPTOR}\nORACLE_USERNAME=u\nORACLE_PASSWORD=p\n")
        self._sync()
        self.assertIn("connectionString: db.example.local:1521/SVC.example.local\n", self._read_output())

    def test_user_secret_is_read_from_the_store(self):
        self._write_template(_TEMPLATE)
        self._write_secrets({"APP[TEST]": _ODP, "APP[PROD]": "Data Source=prod:1/p;USER ID=x;PASSWORD=y"})
        self._write_env("ORACLE_USER_SECRETS_ID=some-guid\nORACLE_SECRET_NAME=APP[TEST]\n")
        self._sync()
        self.assertIn("connectionString: db.example.local:1521/SVC.example.local\n", self._read_output())
        self.assertIn("user: APP_USER\n", self._read_output())

    def test_user_secrets_store_with_utf8_bom_is_read(self):
        self._write_template(_TEMPLATE)
        self._write_secrets({"APP[TEST]": _ODP}, encoding="utf-8-sig")
        self._write_env("ORACLE_USER_SECRETS_ID=some-guid\nORACLE_SECRET_NAME=APP[TEST]\n")
        self._sync()
        self.assertIn("user: APP_USER\n", self._read_output())

    def test_connection_string_beats_host_beats_user_secret(self):
        env = {
            "ORACLE_CONNECTION_STRING": "Data Source=cs:1/cs;USER ID=cs_user;PASSWORD=cs_pwd",
            "ORACLE_HOST": "host:1/host",
            "ORACLE_USERNAME": "host_user",
            "ORACLE_PASSWORD": "host_pwd",
            "ORACLE_USER_SECRETS_ID": "some-guid",
            "ORACLE_SECRET_NAME": "APP[TEST]",
        }
        self._write_secrets({"APP[TEST]": _ODP})
        self.assertEqual(oracle_config_sync.resolve_connection(env)["ORACLE_USERNAME"], "cs_user")

        del env["ORACLE_CONNECTION_STRING"]
        self.assertEqual(oracle_config_sync.resolve_connection(env)["ORACLE_USERNAME"], "host_user")

        del env["ORACLE_HOST"]
        self.assertEqual(oracle_config_sync.resolve_connection(env)["ORACLE_USERNAME"], "APP_USER")

    def test_nothing_configured_resolves_to_none(self):
        self.assertIsNone(oracle_config_sync.resolve_connection({}))

    def test_host_without_password_is_an_error_not_a_fall_through(self):
        self._write_secrets({"APP[TEST]": _ODP})
        env = {"ORACLE_HOST": "h:1/s", "ORACLE_USERNAME": "u", "ORACLE_USER_SECRETS_ID": "g", "ORACLE_SECRET_NAME": "APP[TEST]"}
        with self.assertRaises(ValueError) as ctx:
            oracle_config_sync.resolve_connection(env)
        self.assertIn("ORACLE_PASSWORD", str(ctx.exception))

    def test_secret_name_without_secrets_id_is_an_error(self):
        with self.assertRaises(ValueError) as ctx:
            oracle_config_sync.resolve_connection({"ORACLE_SECRET_NAME": "APP[TEST]"})
        self.assertIn("ORACLE_USER_SECRETS_ID", str(ctx.exception))

    def test_missing_secret_names_it_without_leaking_others(self):
        self._write_secrets({"APP[PROD]": _ODP})
        with self.assertRaises(ValueError) as ctx:
            oracle_config_sync.resolve_connection({"ORACLE_USER_SECRETS_ID": "g", "ORACLE_SECRET_NAME": "APP[TEST]"})
        self.assertIn("APP[TEST]", str(ctx.exception))
        self.assertNotIn("app_pwd", str(ctx.exception))

    def test_missing_secrets_store_is_a_clear_error(self):
        with self.assertRaises(ValueError) as ctx:
            oracle_config_sync.resolve_connection({"ORACLE_USER_SECRETS_ID": "g", "ORACLE_SECRET_NAME": "APP[TEST]"})
        self.assertIn("ORACLE_USER_SECRETS_ID", str(ctx.exception))

    def test_connection_string_without_credentials_never_echoes_its_value(self):
        with self.assertRaises(ValueError) as ctx:
            oracle_config_sync.resolve_connection({"ORACLE_CONNECTION_STRING": "Data Source=h:1/s;PASSWORD=secret"})
        self.assertIn("USER ID", str(ctx.exception))
        self.assertNotIn("secret", str(ctx.exception))

    def test_connection_string_keys_are_case_and_whitespace_insensitive(self):
        parsed = oracle_config_sync.parse_odp_connection_string(
            "data source = h:1/s ; User  Id = u ; password=p", "test"
        )
        self.assertEqual(parsed, {"ORACLE_CONNECTION_STRING": "h:1/s", "ORACLE_USERNAME": "u", "ORACLE_PASSWORD": "p"})

    def test_descriptor_without_port_or_server_dedicated(self):
        self.assertEqual(
            oracle_config_sync.to_ezconnect("(DESCRIPTION=(ADDRESS=(HOST=h))(CONNECT_DATA=(SERVICE_NAME=s)))"),
            "h/s",
        )

    def test_descriptor_without_service_name_is_an_error(self):
        with self.assertRaises(ValueError):
            oracle_config_sync.to_ezconnect("(DESCRIPTION=(ADDRESS=(HOST=h)(PORT=1))(CONNECT_DATA=(SID=x)))")

    def test_ezconnect_and_tns_alias_pass_through(self):
        self.assertEqual(oracle_config_sync.to_ezconnect(" h:1521/svc "), "h:1521/svc")
        self.assertEqual(oracle_config_sync.to_ezconnect("MYALIAS"), "MYALIAS")

    def test_user_secrets_path_matches_dotnet_layout(self):
        with patch.dict(os.environ, {"APPDATA": self.secrets_dir}):
            path = self.real_user_secrets_path("abc")
        if os.name == "nt":
            expected = os.path.join(self.secrets_dir, "Microsoft", "UserSecrets", "abc", "secrets.json")
        else:
            expected = os.path.join(os.path.expanduser("~"), ".microsoft", "usersecrets", "abc", "secrets.json")
        self.assertEqual(path, expected)

    def test_watched_paths_include_the_user_secrets_store_only_when_configured(self):
        self.assertEqual(oracle_config_sync.watched_paths(self.env_path), [self.env_path])
        self._write_env("ORACLE_USER_SECRETS_ID=g\n")
        self.assertEqual(oracle_config_sync.watched_paths(self.env_path), [self.env_path, self.secrets_path])

    def test_watch_survives_a_broken_config_and_keeps_the_last_good_output(self):
        self._write_template(_TEMPLATE)
        self._write_env("ORACLE_HOST=good:1/s\nORACLE_USERNAME=u\nORACLE_PASSWORD=p\n")

        def break_env_then_stop(_interval):
            if sleep.call_count == 1:
                self._write_env("ORACLE_HOST=bad:1/s\nORACLE_USERNAME=u\n")
                os.utime(self.env_path, (0, 0))
                return
            raise _StopWatching

        with patch.object(oracle_config_sync.time, "sleep", side_effect=break_env_then_stop) as sleep, \
                patch("sys.stdout", new_callable=io.StringIO) as out:
            with self.assertRaises(_StopWatching):
                oracle_config_sync.watch(self.template_path, self.output_path, self.env_path, interval=0)

        self.assertEqual(sleep.call_count, 2)
        self.assertIn("connectionString: good:1/s\n", self._read_output())
        self.assertIn("Not regenerated: ORACLE_HOST is set but ORACLE_PASSWORD is not", out.getvalue())

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
        self.assertIn("ORACLE_USER_SECRETS_ID", str(ctx.exception))

    def test_missing_non_connection_var_keeps_the_generic_error(self):
        self._write_template("x: ${SOME_OTHER_VAR}\n")
        with self.assertRaises(ValueError) as ctx:
            self._sync()
        self.assertIn("SOME_OTHER_VAR is not set", str(ctx.exception))

    def test_second_call_reflects_an_edited_env_file_without_restarting_anything(self):
        """This is the whole point of the module: --watch calls sync() over
        and over in one long-running process, so a value must never get
        "stuck" from an earlier call once the .env file on disk changes."""
        self._write_template(_TEMPLATE)

        self._write_env("ORACLE_HOST=first-host:1/s\nORACLE_USERNAME=u\nORACLE_PASSWORD=p\n")
        self._sync()
        self.assertIn("first-host", self._read_output())

        self._write_env("ORACLE_HOST=second-host:1/s\nORACLE_USERNAME=u\nORACLE_PASSWORD=p\n")
        self._sync()
        content = self._read_output()
        self.assertIn("second-host", content)
        self.assertNotIn("first-host", content)

    def test_second_call_reflects_an_edited_user_secret(self):
        self._write_template(_TEMPLATE)
        self._write_env("ORACLE_USER_SECRETS_ID=g\nORACLE_SECRET_NAME=APP[TEST]\n")

        self._write_secrets({"APP[TEST]": "Data Source=first:1/s;USER ID=u;PASSWORD=p"})
        self._sync()
        self.assertIn("first:1/s", self._read_output())

        self._write_secrets({"APP[TEST]": "Data Source=second:1/s;USER ID=u;PASSWORD=p"})
        self._sync()
        self.assertIn("second:1/s", self._read_output())

    def test_real_vendored_template_resolves_with_all_required_vars_set(self):
        """Sanity check that the actual vendored oracledb.template.yaml (not
        a hand-written stand-in) only requires the vars we document, and
        that our regex understands every placeholder in it."""
        self._write_env(f"ORACLE_CONNECTION_STRING={_ODP}\n")
        oracle_config_sync.sync(oracle_config_sync.TEMPLATE_PATH, self.output_path, self.env_path)
        content = self._read_output()
        self.assertNotIn("${", content)
        self.assertIn("db.example.local:1521/SVC.example.local", content)


if __name__ == "__main__":
    unittest.main()
