# core/oracle_config_sync.py
"""Regenerate tools.yaml (MCP Toolbox for Databases config) from .env.

Why this exists: the "oracledb" MCP server used to run
`toolbox --prebuilt oracledb -e ORACLE_CONNECTION_STRING=... --stdio`.
Env vars passed at process start are fixed for the life of that process -
editing .env would never reach an already-running toolbox that way.

Toolbox itself DOES support live config reload, but only for a config
*file* passed via --config (see --disable-reload/--poll-interval in
`toolbox --help` - reload is on by default). So the "oracledb" MCP server
now runs `toolbox --config tools.yaml --stdio` instead, and this script is
the bridge that makes ".env is the single source of truth" actually reach
that file: it resolves the ${VAR}/${VAR:default} placeholders in
tools/oracledb.template.yaml against the current environment (after
loading .env) and writes the literal result to tools.yaml. Toolbox notices
the file changed and reloads live - no MCP server restart needed.

tools/oracledb.template.yaml is vendored verbatim (Apache-2.0) from
internal/prebuiltconfigs/tools/oracledb.yaml in googleapis/mcp-toolbox, so
this reproduces the same 7 built-in tools (execute_sql, list_tables,
list_active_sessions, get_query_plan, list_top_sql_by_resource,
list_tablespace_usage, list_invalid_objects) instead of a hand-rolled,
possibly-incomplete reimplementation.

The Oracle connection comes from the first of these that is configured
(.env or real env):
    1. ORACLE_CONNECTION_STRING - full ODP.NET connection string
       (Data Source=...;User Id=...;Password=...)
    2. ORACLE_HOST + ORACLE_USERNAME + ORACLE_PASSWORD
    3. ORACLE_USER_SECRETS_ID + ORACLE_SECRET_NAME - an entry of a .NET
       user-secrets store (same value shape as 1.)
Whichever wins is turned into the template's own connectionString (always
host:port/service - TNS descriptors are flattened), user and password.

Usage:
    python core/oracle_config_sync.py            # regenerate once
    python core/oracle_config_sync.py --watch     # regenerate on every .env / user-secrets change (Ctrl+C to stop)
"""
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
from _shared import parse_dotenv

PROJECT_ROOT = os.path.join(os.path.dirname(__file__), "..")
TEMPLATE_PATH = os.path.join(PROJECT_ROOT, "tools", "oracledb.template.yaml")
OUTPUT_PATH = os.path.join(PROJECT_ROOT, "tools.yaml")
ENV_PATH = os.path.join(PROJECT_ROOT, ".env")

_VAR_RE = re.compile(r"\$\{([A-Z_][A-Z0-9_]*)(:([^}]*))?\}")
_TEMPLATE_CONNECTION_VARS = ("ORACLE_CONNECTION_STRING", "ORACLE_USERNAME", "ORACLE_PASSWORD")
_NO_CONNECTION_HINT = (
    "no Oracle connection configured - set ORACLE_CONNECTION_STRING, or "
    "ORACLE_HOST + ORACLE_USERNAME + ORACLE_PASSWORD, or "
    "ORACLE_USER_SECRETS_ID + ORACLE_SECRET_NAME (see .env.example)"
)


def _resolve(env: dict, match: "re.Match") -> str:
    name, _, default = match.groups()
    value = env.get(name)
    if value:
        return value
    if default is not None:
        return default
    if name in _TEMPLATE_CONNECTION_VARS:
        raise ValueError(f"{name} unresolved: {_NO_CONNECTION_HINT}")
    raise ValueError(
        f"{name} is not set in .env and the template gives it no default "
        "(see tools/oracledb.template.yaml / .env.example)"
    )


def _descriptor_field(descriptor: str, field: str) -> "str | None":
    match = re.search(rf"\(\s*{field}\s*=\s*([^)\s]+)\s*\)", descriptor, re.IGNORECASE)
    return match.group(1) if match else None


def to_ezconnect(data_source: str) -> str:
    """Flatten a TNS descriptor "(DESCRIPTION=(ADDRESS=(HOST=h)(PORT=p))
    (CONNECT_DATA=(SERVICE_NAME=s)))" into "h:p/s". Anything that isn't a
    descriptor (already host:port/service, or a TNS alias) passes through.
    Only the first ADDRESS is used; SERVER=DEDICATED and the like are dropped."""
    data_source = data_source.strip()
    if not data_source.startswith("("):
        return data_source
    host = _descriptor_field(data_source, "HOST")
    service = _descriptor_field(data_source, "SERVICE_NAME")
    if not host or not service:
        raise ValueError("TNS descriptor needs both HOST and SERVICE_NAME to become host:port/service")
    port = _descriptor_field(data_source, "PORT")
    return f"{host}:{port}/{service}" if port else f"{host}/{service}"


def parse_odp_connection_string(connection_string: str, source: str) -> dict:
    """Split an ODP.NET connection string into the three template vars.
    Keys are matched case- and whitespace-insensitively ("USER ID" ==
    "User Id"). `source` only labels error messages - the value itself is
    never echoed, since it carries a password."""
    fields = {}
    for part in connection_string.split(";"):
        key, sep, value = part.partition("=")
        if sep:
            fields[" ".join(key.split()).upper()] = value.strip()

    missing = [key for key in ("DATA SOURCE", "USER ID", "PASSWORD") if not fields.get(key)]
    if missing:
        raise ValueError(f"{source} is missing {', '.join(missing)}")
    return {
        "ORACLE_CONNECTION_STRING": to_ezconnect(fields["DATA SOURCE"]),
        "ORACLE_USERNAME": fields["USER ID"],
        "ORACLE_PASSWORD": fields["PASSWORD"],
    }


def user_secrets_path(secrets_id: str) -> str:
    """Same location `dotnet user-secrets` writes to on each OS."""
    if os.name == "nt":
        root = os.path.join(os.environ["APPDATA"], "Microsoft", "UserSecrets")
    else:
        root = os.path.join(os.path.expanduser("~"), ".microsoft", "usersecrets")
    return os.path.join(root, secrets_id, "secrets.json")


def read_user_secret(secrets_id: str, name: str) -> str:
    path = user_secrets_path(secrets_id)
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            secrets = json.load(f)
    except FileNotFoundError:
        raise ValueError(f"no user-secrets store at {path} (check ORACLE_USER_SECRETS_ID)") from None
    if name not in secrets:
        raise ValueError(f"secret {name!r} not found in {path} (check ORACLE_SECRET_NAME)")
    return secrets[name]


def resolve_connection(env: dict) -> "dict | None":
    """Pick the connection source by priority. A source is selected by its
    leading var alone (ORACLE_CONNECTION_STRING, ORACLE_HOST, or either
    user-secrets var): once selected, its companions are required - a
    half-configured source is an error, never a silent fall-through to the
    next one. Returns None when no source is configured at all."""
    if env.get("ORACLE_CONNECTION_STRING"):
        return parse_odp_connection_string(env["ORACLE_CONNECTION_STRING"], "ORACLE_CONNECTION_STRING")

    if env.get("ORACLE_HOST"):
        missing = [key for key in ("ORACLE_USERNAME", "ORACLE_PASSWORD") if not env.get(key)]
        if missing:
            raise ValueError(f"ORACLE_HOST is set but {', '.join(missing)} is not")
        return {
            "ORACLE_CONNECTION_STRING": to_ezconnect(env["ORACLE_HOST"]),
            "ORACLE_USERNAME": env["ORACLE_USERNAME"],
            "ORACLE_PASSWORD": env["ORACLE_PASSWORD"],
        }

    secrets_id = env.get("ORACLE_USER_SECRETS_ID")
    secret_name = env.get("ORACLE_SECRET_NAME")
    if secrets_id or secret_name:
        if not (secrets_id and secret_name):
            raise ValueError("ORACLE_USER_SECRETS_ID and ORACLE_SECRET_NAME must be set together")
        return parse_odp_connection_string(read_user_secret(secrets_id, secret_name), f"user secret {secret_name!r}")

    return None


def _load_env(env_path: str) -> dict:
    return {**parse_dotenv(env_path), **os.environ}


def sync(template_path: str = TEMPLATE_PATH, output_path: str = OUTPUT_PATH, env_path: str = ENV_PATH) -> str:
    """Resolve the template's ${VAR}/${VAR:default} placeholders and write
    tools.yaml. Parses .env fresh on every call (pure - never touches
    os.environ) and layers a real OS env var on top when both exist, same
    precedence as load_dotenv(): real env wins, .env fills gaps. Re-parsing
    the file every call (rather than caching) is what lets --watch pick up
    an edited value without restarting anything."""
    env = _load_env(env_path)
    # 20261008 ++ RG #oracle_connection_sources
    # .env's ORACLE_CONNECTION_STRING is a full ODP.NET string, the template's
    # placeholder of the same name is host:port/service - overwrite, don't merge.
    connection = resolve_connection(env)
    if connection:
        env.update(connection)

    with open(template_path, "r", encoding="utf-8") as f:
        template = f.read()
    resolved = _VAR_RE.sub(lambda m: _resolve(env, m), template)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(resolved)
    return output_path


def _mtime(path: str) -> "float | None":
    try:
        return os.path.getmtime(path)
    except FileNotFoundError:
        return None


def watched_paths(env_path: str = ENV_PATH) -> list:
    """.env, plus the user-secrets store it points at (if any) - so a
    `dotnet user-secrets set ...` reloads too, not just a .env edit."""
    paths = [env_path]
    secrets_id = _load_env(env_path).get("ORACLE_USER_SECRETS_ID")
    if secrets_id:
        paths.append(user_secrets_path(secrets_id))
    return paths


def watch(template_path: str = TEMPLATE_PATH, output_path: str = OUTPUT_PATH, env_path: str = ENV_PATH, interval: int = 2) -> None:
    """Regenerate tools.yaml every time .env's (or the user-secrets
    store's) mtime changes. Blocks forever - run this in its own terminal
    for fully automatic hot reload instead of re-running `sync()` by hand
    after each edit. A broken config is reported and skipped, not fatal:
    the last good tools.yaml stays in place until the next valid edit."""
    last_seen = None
    print(f"Watching {env_path} (+ user-secrets store, if configured) for changes (Ctrl+C to stop)...")
    while True:
        snapshot = [(path, _mtime(path)) for path in watched_paths(env_path)]
        if snapshot != last_seen:
            last_seen = snapshot
            try:
                sync(template_path, output_path, env_path)
                print(f"Regenerated {output_path}")
            except (ValueError, OSError) as e:
                print(f"Not regenerated: {e}")
        time.sleep(interval)


if __name__ == "__main__":
    if "--watch" in sys.argv:
        watch()
    else:
        print(f"Wrote {sync()}")
