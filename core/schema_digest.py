# core/schema_digest.py
"""Dump a database schema (sqlite file) or parse CREATE TABLE statements (.sql file)."""
import os
import re
import sqlite3
import sys

from _shared import cap

CREATE_TABLE_RE = re.compile(
    r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[`\"\[]?(\w+)[`\"\]]?\s*\((.*?)\)\s*;",
    re.IGNORECASE | re.DOTALL,
)
COLUMN_NAME_RE = re.compile(r"^\s*[`\"\[]?(\w+)[`\"\]]?\s+([A-Za-z]+)", re.MULTILINE)


def _from_sqlite(path: str) -> str:
    conn = sqlite3.connect(path)
    try:
        cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = [row[0] for row in cur.fetchall()]
        parts = [f"{len(tables)} tables"]
        for table in tables:
            cols = conn.execute(f"PRAGMA table_info('{table}')").fetchall()
            col_desc = ", ".join(f"{c[1]} {c[2]}" for c in cols)
            parts.append(f"{table}({col_desc})")
        return "\n".join(parts)
    finally:
        conn.close()


def _from_sql_file(path: str) -> str:
    with open(path, encoding="utf-8", errors="ignore") as fh:
        text = fh.read()
    tables = CREATE_TABLE_RE.findall(text)
    if not tables:
        return "no CREATE TABLE statements found"
    parts = [f"{len(tables)} tables"]
    for name, body in tables:
        cols = [m.group(1) for m in COLUMN_NAME_RE.finditer(body)]
        parts.append(f"{name}({', '.join(cols[:20])})")
    return "\n".join(parts)


def digest(path: str, max_chars: int = 2500) -> str:
    ext = os.path.splitext(path)[1].lower()
    try:
        if ext in (".db", ".sqlite", ".sqlite3"):
            result = _from_sqlite(path)
        elif ext == ".sql":
            result = _from_sql_file(path)
        else:
            result = f"unsupported extension '{ext}' (expected .db/.sqlite/.sqlite3 or .sql)"
    except Exception as exc:
        result = f"error reading schema: {exc}"
    return cap(result, max_chars)


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else sys.exit("usage: schema_digest.py <path>")
    print(digest(path))
