# core/diff_digest.py
"""Summarize a git diff: files changed, +/- counts, and touched symbols — not the full patch."""
import re
import sys

from _shared import run_command, cap

HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+\d+(?:,\d+)? @@\s*(.*)$", re.MULTILINE)


def digest(cwd: str = ".", ref: str = "", max_chars: int = 2000) -> str:
    numstat_cmd = f"git diff --numstat {ref}".strip()
    exit_code, numstat = run_command(numstat_cmd, cwd)
    if exit_code != 0:
        return cap(f"exit_code={exit_code}\n{numstat}", max_chars)

    lines = [l for l in numstat.splitlines() if l.strip()]
    if not lines:
        return "no changes (working tree matches ref)"

    file_lines = []
    total_add = total_del = 0
    for l in lines:
        parts = l.split("\t")
        if len(parts) == 3:
            added, deleted, fname = parts
            added = int(added) if added.isdigit() else 0
            deleted = int(deleted) if deleted.isdigit() else 0
            total_add += added
            total_del += deleted
            file_lines.append(f"{fname}: +{added} -{deleted}")

    diff_cmd = f"git diff {ref}".strip()
    _, full_diff = run_command(diff_cmd, cwd)
    symbols = sorted(set(m.strip() for m in HUNK_RE.findall(full_diff) if m.strip()))

    parts = [
        f"{len(file_lines)} files changed, +{total_add} -{total_del}",
        "\n".join(file_lines),
    ]
    if symbols:
        parts.append("touched symbols:\n" + "\n".join(symbols[:40]))

    return cap("\n\n".join(parts), max_chars)


if __name__ == "__main__":
    cwd = sys.argv[1] if len(sys.argv) > 1 else "."
    ref = sys.argv[2] if len(sys.argv) > 2 else ""
    print(digest(cwd, ref))
