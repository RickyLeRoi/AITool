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

Usage:
    python core/oracle_config_sync.py            # regenerate once
    python core/oracle_config_sync.py --watch     # regenerate on every .env change (Ctrl+C to stop)
"""
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


def _resolve(env: dict, match: "re.Match") -> str:
    name, _, default = match.groups()
    value = env.get(name)
    if value:
        return value
    if default is not None:
        return default
    raise ValueError(
        f"{name} is not set in .env and the template gives it no default "
        "(see tools/oracledb.template.yaml / .env.example)"
    )


def sync(template_path: str = TEMPLATE_PATH, output_path: str = OUTPUT_PATH, env_path: str = ENV_PATH) -> str:
    """Resolve the template's ${VAR}/${VAR:default} placeholders and write
    tools.yaml. Parses .env fresh on every call (pure - never touches
    os.environ) and layers a real OS env var on top when both exist, same
    precedence as load_dotenv(): real env wins, .env fills gaps. Re-parsing
    the file every call (rather than caching) is what lets --watch pick up
    an edited value without restarting anything."""
    env = {**parse_dotenv(env_path), **os.environ}

    with open(template_path, "r", encoding="utf-8") as f:
        template = f.read()
    resolved = _VAR_RE.sub(lambda m: _resolve(env, m), template)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(resolved)
    return output_path


def watch(template_path: str = TEMPLATE_PATH, output_path: str = OUTPUT_PATH, env_path: str = ENV_PATH, interval: int = 2) -> None:
    """Regenerate tools.yaml every time .env's mtime changes. Blocks
    forever - run this in its own terminal for fully automatic hot reload
    instead of re-running `sync()` by hand after each edit."""
    last_seen = None
    print(f"Watching {env_path} for changes (Ctrl+C to stop)...")
    while True:
        try:
            mtime = os.path.getmtime(env_path)
        except FileNotFoundError:
            mtime = None
        if mtime != last_seen:
            last_seen = mtime
            sync(template_path, output_path, env_path)
            print(f"Regenerated {output_path}")
        time.sleep(interval)


if __name__ == "__main__":
    if "--watch" in sys.argv:
        watch()
    else:
        print(f"Wrote {sync()}")
