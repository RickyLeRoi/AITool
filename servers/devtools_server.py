# servers/devtools_server.py
"""MCP server exposing local deterministic digest tools over stdio.

Each tool runs work on the local machine and returns a compressed summary,
so Claude does not have to spend tokens reading raw command/log output.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "core"))

import build_digest
import diff_digest
import log_digest
import repo_map
import test_digest
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("devtools")


@mcp.tool()
def run_tests(command: str, cwd: str = ".") -> str:
    """Run a test command (pytest, npm test, dotnet test, ...) and return only
    the exit code, summary line and deduplicated failures — not the full log."""
    return test_digest.digest(command, cwd)


@mcp.tool()
def run_build(command: str, cwd: str = ".") -> str:
    """Run a build/lint command and return deduplicated errors and warnings,
    not the full log."""
    return build_digest.digest(command, cwd)


@mcp.tool()
def map_repo(root: str = ".") -> str:
    """Return a compact file tree with top-level function/class names per file
    (Python via ast, JS/TS via regex), instead of reading every file."""
    return repo_map.digest(root)


@mcp.tool()
def digest_log(path: str, top_n: int = 25) -> str:
    """Collapse a log file into its most frequent line patterns (timestamps and
    numbers normalized away) with counts, instead of the raw log."""
    return log_digest.digest(path, top_n)


@mcp.tool()
def diff_summary(cwd: str = ".", ref: str = "") -> str:
    """Summarize `git diff` as files changed, +/- line counts and touched
    symbol names, instead of the full patch. `ref` can be e.g. 'HEAD~1' or empty
    for the working tree diff."""
    return diff_digest.digest(cwd, ref)


if __name__ == "__main__":
    mcp.run()
