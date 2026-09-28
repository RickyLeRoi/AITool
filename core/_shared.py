# core/_shared.py
"""Shared helpers for the local digest tools."""
import os
import re
import subprocess

# 20260926 ++ RG #dotenv_config: project root, one level up from core/
_PROJECT_ROOT = os.path.join(os.path.dirname(__file__), "..")
_DOTENV_PATH = os.path.join(_PROJECT_ROOT, ".env")


def parse_dotenv(path: str = _DOTENV_PATH) -> dict:
    """Parse simple KEY=VALUE lines from a .env file into a plain dict.

    Pure - never touches os.environ. Blank lines and lines starting with
    '#' are skipped. Missing file returns {}, not an error: only
    .env.example is meant to be committed, .env itself is local/gitignored.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except FileNotFoundError:
        return {}

    values = {}
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            values[key] = value
    return values


def load_dotenv(path: str = _DOTENV_PATH) -> None:
    """Load a .env file into os.environ. Never overwrites a variable that's
    already set in the real environment (MCP server registration, Windows
    env var, etc.) - the .env file only fills gaps, real env always wins."""
    for key, value in parse_dotenv(path).items():
        if key not in os.environ:
            os.environ[key] = value


def run_command(cmd: str, cwd: str, timeout: int = 300) -> tuple[int, str]:
    """Run a shell command, return (exit_code, combined stdout+stderr)."""
    proc = subprocess.run(
        cmd,
        cwd=cwd,
        shell=True,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return proc.returncode, proc.stdout + proc.stderr


def cap(text: str, max_chars: int = 2000) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + f"\n...[troncato, {len(text) - max_chars} caratteri omessi]"


def dedupe_lines(lines: list[str], normalize: re.Pattern | None = None) -> list[tuple[str, int]]:
    """Collapse near-identical lines (e.g. same error with different line numbers).

    Returns list of (representative_line, count), most frequent first.
    """
    counts: dict[str, int] = {}
    first_seen: dict[str, str] = {}
    for line in lines:
        key = normalize.sub("#", line) if normalize else line
        counts[key] = counts.get(key, 0) + 1
        first_seen.setdefault(key, line)
    ordered = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
    return [(first_seen[key], count) for key, count in ordered]


NUMBER_RE = re.compile(r"\d+")
