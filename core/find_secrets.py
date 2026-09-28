# core/find_secrets.py
"""Scan a repo for likely hardcoded credentials, without sending anything anywhere."""
import os
import re
import sys

from _shared import cap
from repo_map import _tracked_files, EXCLUDE_DIRS

PATTERNS = {
    "aws_access_key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "generic_api_key_assignment": re.compile(
        r"""(?i)\b(api[_-]?key|secret|token|password|passwd)\b\s*[:=]\s*['"][A-Za-z0-9_\-/+=]{12,}['"]"""
    ),
    "private_key_header": re.compile(r"-----BEGIN (RSA|EC|OPENSSH|DSA|PGP) PRIVATE KEY-----"),
    "jwt_like": re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
    "connection_string_with_password": re.compile(r"(?i)://[^/\s:]+:[^/\s@]{4,}@"),
}

BINARY_EXT = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".zip", ".exe", ".dll", ".pyc"}


def digest(root: str = ".", max_chars: int = 2000) -> str:
    findings = []
    for path in _tracked_files(root):
        if os.path.splitext(path)[1].lower() in BINARY_EXT:
            continue
        if any(part in EXCLUDE_DIRS for part in path.replace("\\", "/").split("/")):
            continue
        try:
            with open(path, encoding="utf-8", errors="ignore") as fh:
                for lineno, line in enumerate(fh, start=1):
                    for kind, pattern in PATTERNS.items():
                        if pattern.search(line):
                            rel = os.path.relpath(path, root)
                            findings.append(f"[{kind}] {rel}:{lineno}")
        except (OSError, UnicodeDecodeError):
            continue

    if not findings:
        return "no likely secrets found (heuristic regex scan, not a substitute for a real secret scanner)"

    parts = [f"{len(findings)} potential findings:"]
    parts.append("\n".join(findings[:50]))
    return cap("\n".join(parts), max_chars)


if __name__ == "__main__":
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    print(digest(root))
