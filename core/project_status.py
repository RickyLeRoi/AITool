# core/project_status.py
"""Aggregate repo size, recent diff, and optional test/build results into one executive summary."""
import subprocess
import sys

import build_digest
import diff_digest
import repo_map
import test_digest
from _shared import cap, run_command


def _last_commits(root: str, n: int = 5) -> str:
    code, out = run_command(f"git log -{n} --oneline", root)
    return out.strip() if code == 0 else "not a git repository or no commits"


def digest(root: str = ".", test_command: str = "", build_command: str = "", max_chars: int = 3000) -> str:
    parts = []

    map_result = repo_map.digest(root, max_chars=500)
    file_count_line = map_result.splitlines()[0] if map_result else "unknown"
    parts.append(f"codebase: {file_count_line}")

    parts.append("recent commits:\n" + _last_commits(root))

    diff_result = diff_digest.digest(root, max_chars=600)
    parts.append("pending changes:\n" + diff_result)

    if test_command:
        parts.append("tests:\n" + test_digest.digest(test_command, root, max_chars=600))
    if build_command:
        parts.append("build:\n" + build_digest.digest(build_command, root, max_chars=600))

    return cap("\n\n".join(parts), max_chars)


if __name__ == "__main__":
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    test_command = sys.argv[2] if len(sys.argv) > 2 else ""
    build_command = sys.argv[3] if len(sys.argv) > 3 else ""
    print(digest(root, test_command, build_command))
