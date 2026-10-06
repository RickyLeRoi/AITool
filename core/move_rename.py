# core/move_rename.py
"""Move files and rename namespaces at byte level: CRLF, BOM and non-UTF-8 bytes
survive untouched, nothing is ever decoded and re-encoded."""
import json
import os
import re
import subprocess
import sys

from _shared import cap

EXCLUDE_DIRS = {".git", "node_modules", "bin", "obj", ".vs", "packages", "TestResults"}
NAMESPACE_EXTENSIONS = {
    ".cs", ".razor", ".cshtml", ".csproj", ".props", ".targets", ".xaml", ".resx", ".config", ".json", ".xml",
}
NAMESPACE_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*$")
UTF16_BOMS = (b"\xff\xfe", b"\xfe\xff")
HEADER_RE = re.compile(rb"^(\xef\xbb\xbf)?([ \t]*//[ \t]*)([^\r\n]*?)([ \t]*)(\r?\n|$)")
ASSEMBLY_NAME_RE = re.compile(rb"<AssemblyName>[^<]*</AssemblyName>", re.IGNORECASE)
FILE_SUFFIXES = rb"csproj|sln|slnx|dll|exe|pdb|props|targets|json|xml|config|nupkg"


def load_map(map_path: str, root: str) -> tuple[list[tuple[str, str]], dict[str, str]]:
    with open(map_path, encoding="utf-8-sig") as fh:
        data = json.load(fh)
    moves = [
        (os.path.abspath(os.path.join(root, m["from"])), os.path.abspath(os.path.join(root, m["to"])))
        for m in data.get("moves", [])
    ]
    namespaces = dict(data.get("namespaces", {}))
    return moves, namespaces


def validate(moves: list[tuple[str, str]], namespaces: dict[str, str]) -> list[str]:
    """Everything that would make a partial apply possible is checked upfront."""
    errors = []
    sources = {os.path.normcase(s) for s, _ in moves}
    seen_targets = set()
    for src, dst in moves:
        if not os.path.isfile(src):
            errors.append(f"source missing: {src}")
        if os.path.exists(dst):
            errors.append(f"target already exists: {dst}")
        key = os.path.normcase(dst)
        if key in seen_targets:
            errors.append(f"two moves share the target: {dst}")
        if key in sources:
            errors.append(f"target is also a source (chained move): {dst}")
        seen_targets.add(key)
    for old, new in namespaces.items():
        for value in (old, new):
            if not NAMESPACE_KEY_RE.match(value):
                errors.append(f"not an ASCII dotted identifier: {value!r}")
    return errors


def namespace_pattern(namespaces: dict[str, str]) -> re.Pattern | None:
    """Prefix-aware with identifier boundaries: 'A.B' matches 'A.B' and 'A.B.C', not 'A.BC'
    or 'X.A.B'. Path segments and file names (A.B/..., A.B.csproj) are left alone."""
    if not namespaces:
        return None
    keys = sorted(namespaces, key=len, reverse=True)
    alternation = b"|".join(re.escape(k.encode("ascii")) for k in keys)
    return re.compile(
        rb"(?<![A-Za-z0-9_./\\])(" + alternation + rb")(?![A-Za-z0-9_/\\])(?!\.(?:" + FILE_SUFFIXES + rb")\b)"
    )


def rename_namespaces(data: bytes, pattern: re.Pattern | None, namespaces: dict[str, str]) -> tuple[bytes, int]:
    if pattern is None:
        return data, 0
    protected = [m.span() for m in ASSEMBLY_NAME_RE.finditer(data)]
    replacements = {k.encode("ascii"): v.encode("ascii") for k, v in namespaces.items()}
    count = 0

    def substitute(m: re.Match) -> bytes:
        nonlocal count
        if any(start <= m.start() < end for start, end in protected):
            return m.group(0)
        count += 1
        return replacements[m.group(1)]

    return pattern.sub(substitute, data), count


def _segments(path: str) -> list[str]:
    return [s for s in re.split(r"[\\/]", path) if s and s != "."]


def update_header(data: bytes, old_path: str, new_path: str, root: str) -> tuple[bytes, bool]:
    """If line 1 is `// <path>` and <path> is a tail of old_path, point it at new_path,
    keeping the same base folder and slash style. Only the path bytes change."""
    m = HEADER_RE.match(data)
    if not m or not m.group(3):
        return data, False
    try:
        header = m.group(3).decode("ascii")
    except UnicodeDecodeError:
        return data, False
    header_segments = _segments(header)
    old_segments = _segments(os.path.abspath(old_path))
    tail = old_segments[-len(header_segments):] if header_segments else []
    if not header_segments or [s.lower() for s in tail] != [s.lower() for s in header_segments]:
        return data, False

    base = old_segments[: len(old_segments) - len(header_segments)]
    new_segments = _segments(os.path.abspath(new_path))
    if [s.lower() for s in new_segments[: len(base)]] == [s.lower() for s in base]:
        relative = new_segments[len(base):]
    else:
        relative = _segments(os.path.relpath(new_path, root))
    separator = "\\" if "\\" in header else "/"
    new_header = separator.join(relative).encode("ascii", errors="strict")
    return data[: m.start(3)] + new_header + data[m.end(3):], True


def _candidate_files(root: str, skip: set[str]) -> list[str]:
    files = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
        for f in filenames:
            path = os.path.abspath(os.path.join(dirpath, f))
            if os.path.splitext(f)[1].lower() in NAMESPACE_EXTENSIONS and os.path.normcase(path) not in skip:
                files.append(path)
    return sorted(files)


def plan(root: str, moves: list[tuple[str, str]], namespaces: dict[str, str], skip: set[str]) -> dict:
    """Compute every change without touching disk: {'edits': [(src, dst, data, count, header)], 'unreadable': [...]}."""
    destination = {os.path.normcase(s): d for s, d in moves}
    pattern = namespace_pattern(namespaces)
    candidates = set(_candidate_files(root, skip)) | {s for s, _ in moves}
    edits, unreadable = [], []
    for src in sorted(candidates):
        with open(src, "rb") as fh:
            original = fh.read()
        dst = destination.get(os.path.normcase(src), src)
        if original.startswith(UTF16_BOMS) or b"\x00" in original:
            unreadable.append(src)
            if dst != src:
                edits.append((src, dst, original, 0, False))
            continue
        data, header = original, False
        if dst != src:
            data, header = update_header(data, src, dst, root)
        data, count = rename_namespaces(data, pattern, namespaces)
        if dst != src or data != original:
            edits.append((src, dst, data, count, header))
    return {"edits": edits, "unreadable": unreadable}


def _git_root(root: str) -> str | None:
    proc = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"], cwd=root, capture_output=True, text=True, stdin=subprocess.DEVNULL
    )
    return proc.stdout.strip() if proc.returncode == 0 else None


def _is_tracked(git_root: str, path: str) -> bool:
    proc = subprocess.run(
        ["git", "ls-files", "--error-unmatch", path], cwd=git_root, capture_output=True, stdin=subprocess.DEVNULL
    )
    return proc.returncode == 0


def move_file(src: str, dst: str, git_root: str | None) -> str:
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if git_root and _is_tracked(git_root, src):
        proc = subprocess.run(["git", "mv", src, dst], cwd=git_root, capture_output=True, text=True, stdin=subprocess.DEVNULL)
        if proc.returncode == 0:
            return "git mv"
    os.replace(src, dst)
    return "moved"


def _relative(path: str, root: str) -> str:
    return os.path.relpath(path, root).replace(os.sep, "/")


def digest(map_path: str, root: str = ".", apply: bool = False, max_chars: int = 4000) -> str:
    root = os.path.abspath(root)
    try:
        moves, namespaces = load_map(map_path, root)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return f"cannot read map {map_path}: {exc}"
    errors = validate(moves, namespaces)
    if errors:
        return cap("nothing done, map is invalid:\n" + "\n".join(f"  {e}" for e in errors), max_chars)

    result = plan(root, moves, namespaces, skip={os.path.normcase(os.path.abspath(map_path))})
    edits = result["edits"]

    parts = []
    if namespaces:
        parts.append("namespaces:\n" + "\n".join(f"  {k} -> {v}" for k, v in namespaces.items()))

    git_root = _git_root(root) if apply and moves else None
    move_lines = []
    headers = {os.path.normcase(src) for src, _, _, _, header in edits if header}
    for src, dst in moves:
        how = move_file(src, dst, git_root) if apply else "planned"
        flag = ", header updated" if os.path.normcase(src) in headers else ""
        move_lines.append(f"  {_relative(src, root)} -> {_relative(dst, root)} ({how}{flag})")
    if move_lines:
        parts.append(f"moves ({len(moves)}):\n" + "\n".join(move_lines))

    if apply:
        for _, dst, data, _, _ in edits:
            with open(dst, "wb") as fh:
                fh.write(data)

    renamed = sorted(((dst, count) for _, dst, _, count, _ in edits if count), key=lambda x: (-x[1], x[0]))
    if renamed:
        total = sum(c for _, c in renamed)
        listing = "\n".join(f"  {_relative(dst, root)}: {c}" for dst, c in renamed)
        parts.append(f"namespace replacements: {total} in {len(renamed)} files\n{listing}")
    elif namespaces:
        parts.append("namespace replacements: none found")

    if result["unreadable"]:
        listing = "\n".join(f"  {_relative(p, root)}" for p in result["unreadable"])
        parts.append(f"skipped (binary or UTF-16, check by hand):\n{listing}")

    parts.append("applied" if apply else "dry run - call again with apply=True to perform these changes")
    return cap("\n\n".join(parts), max_chars)


if __name__ == "__main__":
    map_path = sys.argv[1]
    root = sys.argv[2] if len(sys.argv) > 2 else "."
    apply = len(sys.argv) > 3 and sys.argv[3].lower() in ("1", "true", "apply")
    print(digest(map_path, root, apply))
