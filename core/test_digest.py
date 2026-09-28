# core/test_digest.py
"""Run a test command and return only the summary + failures, not the full log."""
import re
import sys

from _shared import run_command, cap, dedupe_lines, NUMBER_RE

FAILURE_LINE = re.compile(
    r"(FAILED|FAIL:|Error|ERROR|AssertionError|Traceback|✗|✘|\bfailed\b)", re.IGNORECASE
)
# Lowercase on purpose: pytest/jest use lowercase "passed"/"failed" only in the
# final summary line, while per-test verbose lines use uppercase PASSED/FAILED —
# this keeps individual test lines out of the summary match.
SUMMARY_LINE = re.compile(
    r"(\d+ passed\b|\d+ failed\b|\d+ error(?:s|\(s\))?\b|\d+ skipped\b|Tests:\s*\d+|Test Suites:)"
)


def digest(cmd: str, cwd: str = ".", max_chars: int = 2000) -> str:
    exit_code, output = run_command(cmd, cwd)
    lines = output.splitlines()

    summary_lines = [l for l in lines if SUMMARY_LINE.search(l)]
    failure_lines = [l.strip() for l in lines if FAILURE_LINE.search(l)]
    deduped = dedupe_lines(failure_lines, normalize=NUMBER_RE)

    parts = [f"exit_code={exit_code}"]
    if summary_lines:
        parts.append("summary:\n" + "\n".join(summary_lines[-5:]))
    if deduped:
        top = deduped[:30]
        formatted = "\n".join(f"[x{c}] {l}" for l, c in top)
        parts.append(f"failures ({len(failure_lines)} lines, {len(deduped)} distinct):\n{formatted}")
    elif exit_code == 0:
        parts.append("no failures detected")
    else:
        parts.append("non-zero exit but no recognizable failure lines; last 20 lines:\n" + "\n".join(lines[-20:]))

    return cap("\n\n".join(parts), max_chars)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "pytest"
    cwd = sys.argv[2] if len(sys.argv) > 2 else "."
    print(digest(cmd, cwd))
