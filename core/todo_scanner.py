# core/todo_scanner.py
"""Collect TODO/FIXME/HACK/XXX markers across a repo into one grouped list."""
import os
import re
import sys

from _shared import cap
from repo_map import _tracked_files, EXCLUDE_DIRS

MARKER_RE = re.compile(r"\b(TODO|FIXME|HACK|XXX)\b[:\s]?(.*)")
BINARY_EXT = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".zip", ".exe", ".dll", ".pyc"}


def digest(root: str = ".", max_chars: int = 2500) -> str:
    by_marker: dict[str, list[str]] = {}
    for path in _tracked_files(root):
        if os.path.splitext(path)[1].lower() in BINARY_EXT:
            continue
        if any(part in EXCLUDE_DIRS for part in path.replace("\\", "/").split("/")):
            continue
        try:
            with open(path, encoding="utf-8", errors="ignore") as fh:
                for lineno, line in enumerate(fh, start=1):
                    m = MARKER_RE.search(line)
                    if m:
                        rel = os.path.relpath(path, root)
                        text = m.group(2).strip()[:80]
                        by_marker.setdefault(m.group(1), []).append(f"{rel}:{lineno} {text}")
        except (OSError, UnicodeDecodeError):
            continue

    total = sum(len(v) for v in by_marker.values())
    if total == 0:
        return "no TODO/FIXME/HACK/XXX markers found"

    parts = [f"{total} markers found"]
    for marker in ("FIXME", "HACK", "XXX", "TODO"):
        items = by_marker.get(marker)
        if items:
            parts.append(f"{marker} ({len(items)}):\n" + "\n".join(items[:20]))

    return cap("\n\n".join(parts), max_chars)


if __name__ == "__main__":
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    print(digest(root))
