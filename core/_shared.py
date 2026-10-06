# core/_shared.py
"""Shared helpers for the local digest tools."""
import os
import re
import signal
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


TIMEOUT_EXIT_CODE = 124


def _kill_tree(proc: subprocess.Popen) -> None:
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
            stdin=subprocess.DEVNULL,
            capture_output=True,
        )
    else:
        os.killpg(proc.pid, signal.SIGKILL)


def run_command(cmd: str, cwd: str, timeout: int = 300, env: dict | None = None) -> tuple[int, str]:
    """Run a shell command, return (exit_code, combined stdout+stderr).

    On timeout the whole process tree is killed and exit code 124 is returned
    with whatever output was captured. `env` entries are added on top of the
    current environment, not a replacement for it.
    """
    # 20261006 ** RG #mcp_stdin_hang: under an MCP stdio server the inherited
    # stdin is the JSON-RPC pipe; on Windows a child touching it blocks behind
    # the server's pending read forever. shell=True also leaves the real command
    # as a grandchild, so killing only the shell kept the pipes open on timeout.
    proc = subprocess.Popen(
        cmd,
        cwd=cwd,
        shell=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        errors="replace",
        start_new_session=os.name != "nt",
        env={**os.environ, **env} if env else None,
    )
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
        return proc.returncode, stdout + stderr
    except subprocess.TimeoutExpired:
        _kill_tree(proc)
        try:
            stdout, stderr = proc.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            stdout, stderr = "", ""
        return TIMEOUT_EXIT_CODE, f"{stdout}{stderr}\n[timeout after {timeout}s, process tree killed]"


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
