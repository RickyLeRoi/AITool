# core/build_digest.py
"""Run a build/lint command and return a deduplicated error list, not the full log."""
import re
import sys

from _shared import run_command, cap, dedupe_lines, NUMBER_RE

ERROR_LINE = re.compile(r"(error|Error|ERROR)", re.IGNORECASE)
WARNING_LINE = re.compile(r"(warning|Warning|WARN)", re.IGNORECASE)


def digest(cmd: str, cwd: str = ".", max_chars: int = 2000) -> str:
    exit_code, output = run_command(cmd, cwd)
    lines = output.splitlines()

    error_lines = [l.strip() for l in lines if ERROR_LINE.search(l)]
    warning_lines = [l.strip() for l in lines if WARNING_LINE.search(l) and not ERROR_LINE.search(l)]

    deduped_errors = dedupe_lines(error_lines, normalize=NUMBER_RE)
    deduped_warnings = dedupe_lines(warning_lines, normalize=NUMBER_RE)

    parts = [f"exit_code={exit_code}"]
    if deduped_errors:
        formatted = "\n".join(f"[x{c}] {l}" for l, c in deduped_errors[:30])
        parts.append(f"errors ({len(error_lines)} lines, {len(deduped_errors)} distinct):\n{formatted}")
    if deduped_warnings:
        formatted = "\n".join(f"[x{c}] {l}" for l, c in deduped_warnings[:15])
        parts.append(f"warnings ({len(warning_lines)} lines, {len(deduped_warnings)} distinct):\n{formatted}")
    if not deduped_errors and not deduped_warnings:
        parts.append("build clean" if exit_code == 0 else "non-zero exit, no recognizable error lines; last 20 lines:\n" + "\n".join(lines[-20:]))

    return cap("\n\n".join(parts), max_chars)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "npm run build"
    cwd = sys.argv[2] if len(sys.argv) > 2 else "."
    print(digest(cmd, cwd))
