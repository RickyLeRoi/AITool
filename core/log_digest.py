# core/log_digest.py
"""Collapse a large log file into its most frequent line patterns, instead of dumping it whole."""
import re
import sys

from _shared import cap, dedupe_lines

TIMESTAMP_RE = re.compile(
    r"\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(\.\d+)?|\d{2}:\d{2}:\d{2}(\.\d+)?"
)
NUMBER_RE = re.compile(r"\d+")


def _normalize(line: str) -> str:
    line = TIMESTAMP_RE.sub("<ts>", line)
    line = NUMBER_RE.sub("#", line)
    return line


def digest(path: str, top_n: int = 25, max_chars: int = 2500) -> str:
    with open(path, encoding="utf-8", errors="ignore") as fh:
        lines = [l.rstrip("\n") for l in fh if l.strip()]

    timestamps = [m.group(0) for l in lines if (m := TIMESTAMP_RE.search(l))]
    time_range = f"{timestamps[0]} .. {timestamps[-1]}" if timestamps else "no timestamps found"

    normalize_re = re.compile("|".join(p.pattern for p in (TIMESTAMP_RE, NUMBER_RE)))
    deduped = dedupe_lines(lines, normalize=normalize_re)

    parts = [f"total_lines={len(lines)}", f"time_range={time_range}", f"distinct_patterns={len(deduped)}"]
    top = deduped[:top_n]
    formatted = "\n".join(f"[x{c}] {l}" for l, c in top)
    parts.append(f"top {len(top)} patterns:\n{formatted}")

    return cap("\n\n".join(parts), max_chars)


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else sys.exit("usage: log_digest.py <path> [top_n]")
    top_n = int(sys.argv[2]) if len(sys.argv) > 2 else 25
    print(digest(path, top_n))
