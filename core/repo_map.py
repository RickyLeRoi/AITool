# core/repo_map.py
"""Produce a compact file tree + top-level symbol outline for a repo, instead of reading every file."""
import ast
import os
import re
import subprocess
import sys

from _shared import cap

EXCLUDE_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build", ".next", "bin", "obj"}
JS_SYMBOL_RE = re.compile(
    r"^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?(?:function\s+(\w+)|class\s+(\w+))", re.MULTILINE
)


def _tracked_files(root: str) -> list[str]:
    try:
        out = subprocess.run(
            ["git", "ls-files"], cwd=root, capture_output=True, text=True, timeout=30
        )
        if out.returncode == 0 and out.stdout.strip():
            return [os.path.join(root, p) for p in out.stdout.splitlines()]
    except Exception:
        pass
    files = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS and not d.startswith(".")]
        for f in filenames:
            files.append(os.path.join(dirpath, f))
    return files


def _py_symbols(path: str) -> list[str]:
    try:
        with open(path, encoding="utf-8", errors="ignore") as fh:
            tree = ast.parse(fh.read())
    except Exception:
        return []
    names = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.append(node.name)
    return names


def _js_symbols(path: str) -> list[str]:
    try:
        with open(path, encoding="utf-8", errors="ignore") as fh:
            text = fh.read()
    except Exception:
        return []
    names = []
    for m in JS_SYMBOL_RE.finditer(text):
        names.append(m.group(1) or m.group(2))
    return names


def digest(root: str = ".", max_chars: int = 2500) -> str:
    files = _tracked_files(root)
    lines = [f"{len(files)} files"]
    for f in sorted(files):
        rel = os.path.relpath(f, root)
        ext = os.path.splitext(f)[1]
        symbols = []
        if ext == ".py":
            symbols = _py_symbols(f)
        elif ext in (".js", ".ts", ".jsx", ".tsx"):
            symbols = _js_symbols(f)
        if symbols:
            lines.append(f"{rel}: {', '.join(symbols[:20])}")
        else:
            lines.append(rel)
    return cap("\n".join(lines), max_chars)


if __name__ == "__main__":
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    print(digest(root))
