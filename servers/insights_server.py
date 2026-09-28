# servers/insights_server.py
"""MCP server exposing local static-analysis / reporting tools over stdio.

Kept separate from devtools_server.py so no single server's tool list grows
past ~6-8 entries (every registered tool costs context tokens on every turn).
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "core"))

import deps_digest
import fetch_url
import find_secrets
import project_status
import schema_digest
import todo_scanner
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("insights")


@mcp.tool()
def fetch(url: str, max_chars: int = 3000) -> str:
    """Fetch a URL and return a tags-stripped text digest, not raw HTML."""
    return fetch_url.digest(url, max_chars)


@mcp.tool()
def scan_secrets(root: str = ".") -> str:
    """Heuristic regex scan for likely hardcoded credentials (API keys, private
    keys, JWTs, connection strings with passwords). Not a substitute for a real
    secret scanner — use before a commit/PR review, not as a security guarantee."""
    return find_secrets.digest(root)


@mcp.tool()
def scan_todos(root: str = ".") -> str:
    """Collect TODO/FIXME/HACK/XXX markers across a repo, grouped by marker."""
    return todo_scanner.digest(root)


@mcp.tool()
def list_dependencies(root: str = ".") -> str:
    """List declared dependencies from package.json, requirements.txt or *.csproj
    in the given directory."""
    return deps_digest.digest(root)


@mcp.tool()
def dump_schema(path: str) -> str:
    """Dump a database schema: table/column list for a .db/.sqlite file (via
    sqlite3), or parsed CREATE TABLE statements for a .sql migration file."""
    return schema_digest.digest(path)


@mcp.tool()
def status_report(root: str = ".", test_command: str = "", build_command: str = "") -> str:
    """Executive summary: file count, recent commits, pending diff, and
    optionally test/build results — for status updates rather than deep review."""
    return project_status.digest(root, test_command, build_command)


if __name__ == "__main__":
    mcp.run()
