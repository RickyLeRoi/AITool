# core/project_graph.py
"""Map ProjectReference edges between .csproj files: cycles, layer violations, dangling refs."""
import fnmatch
import os
import re
import sys

from _shared import cap

EXCLUDE_DIRS = {".git", "node_modules", "bin", "obj", ".vs", "packages", "TestResults"}
PROJECT_REF_RE = re.compile(r'<ProjectReference\s+[^>]*?Include\s*=\s*"([^"]+)"', re.IGNORECASE)
WILDCARD_LAYER = "*"


def _norm(path: str) -> str:
    return os.path.normcase(os.path.normpath(os.path.abspath(path)))


def find_projects(root: str) -> list[str]:
    found = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
        found.extend(os.path.join(dirpath, f) for f in filenames if f.lower().endswith(".csproj"))
    return sorted(found)


def read_references(csproj_path: str) -> list[str]:
    with open(csproj_path, encoding="utf-8-sig", errors="replace") as fh:
        text = fh.read()
    base = os.path.dirname(csproj_path)
    return [os.path.join(base, ref.replace("\\", os.sep).replace("/", os.sep)) for ref in PROJECT_REF_RE.findall(text)]


def _display_names(paths: list[str], root: str) -> dict[str, str]:
    """Project file stem, or the root-relative path when two projects share a stem."""
    stems: dict[str, int] = {}
    for p in paths:
        stem = os.path.splitext(os.path.basename(p))[0]
        stems[stem.lower()] = stems.get(stem.lower(), 0) + 1
    names = {}
    for p in paths:
        stem = os.path.splitext(os.path.basename(p))[0]
        names[_norm(p)] = stem if stems[stem.lower()] == 1 else os.path.relpath(p, root).replace("\\", "/")
    return names


def build_graph(root: str) -> tuple[dict[str, list[str]], list[tuple[str, str]]]:
    """Return (adjacency by display name, dangling (project, missing reference path))."""
    projects = find_projects(root)
    names = _display_names(projects, root)
    graph: dict[str, list[str]] = {names[_norm(p)]: [] for p in projects}
    dangling = []
    for p in projects:
        src = names[_norm(p)]
        for ref in read_references(p):
            target = names.get(_norm(ref))
            if target is None:
                dangling.append((src, os.path.relpath(ref, root).replace("\\", "/")))
            elif target not in graph[src]:
                graph[src].append(target)
    return graph, dangling


def _strongly_connected(graph: dict[str, list[str]]) -> list[list[str]]:
    """Iterative Tarjan: no recursion limit on large solutions."""
    index: dict[str, int] = {}
    low: dict[str, int] = {}
    on_stack: set[str] = set()
    stack: list[str] = []
    components = []
    counter = 0

    for start in graph:
        if start in index:
            continue
        work = [(start, iter(graph[start]))]
        index[start] = low[start] = counter
        counter += 1
        stack.append(start)
        on_stack.add(start)
        while work:
            node, children = work[-1]
            child = next(children, None)
            if child is None:
                work.pop()
                if work:
                    parent = work[-1][0]
                    low[parent] = min(low[parent], low[node])
                if low[node] == index[node]:
                    component = []
                    while True:
                        member = stack.pop()
                        on_stack.discard(member)
                        component.append(member)
                        if member == node:
                            break
                    components.append(component)
            elif child not in index:
                index[child] = low[child] = counter
                counter += 1
                stack.append(child)
                on_stack.add(child)
                work.append((child, iter(graph.get(child, []))))
            elif child in on_stack:
                low[node] = min(low[node], index[child])
    return components


def _cycle_through(start: str, members: set[str], graph: dict[str, list[str]]) -> list[str]:
    """Shortest path start -> ... -> start inside one strongly connected component (BFS)."""
    previous = {start: None}
    queue = [start]
    while queue:
        node = queue.pop(0)
        for child in graph[node]:
            if child == start:
                path = [node]
                while previous[path[-1]] is not None:
                    path.append(previous[path[-1]])
                return list(reversed(path)) + [start]
            if child in members and child not in previous:
                previous[child] = node
                queue.append(child)
    return [start, start]


def find_cycles(graph: dict[str, list[str]]) -> list[list[str]]:
    cycles = []
    for component in _strongly_connected(graph):
        if len(component) > 1 or component[0] in graph[component[0]]:
            start = min(component)
            cycles.append(_cycle_through(start, set(component), graph))
    return sorted(cycles)


def parse_layers(spec: str) -> list[list[str]]:
    """'Utility; DB,FS; *; WebApi' -> [['utility'], ['db', 'fs'], ['*'], ['webapi']], lowest first."""
    layers = []
    for chunk in spec.split(";"):
        tokens = [t.strip().lower() for t in chunk.split(",") if t.strip()]
        if tokens:
            layers.append(tokens)
    return layers


def _token_matches(token: str, name: str) -> bool:
    lowered = name.lower()
    if any(c in token for c in "*?["):
        return fnmatch.fnmatchcase(lowered, token)
    segments = re.split(r"[./\\]", lowered)
    return token in segments


def layer_of(name: str, layers: list[list[str]]) -> int | None:
    """First layer with a token matching a dot-separated segment of the name
    (or the whole name, for glob tokens); the bare '*' layer catches the rest."""
    wildcard = None
    for position, tokens in enumerate(layers):
        for token in tokens:
            if token == WILDCARD_LAYER:
                wildcard = position
            elif _token_matches(token, name):
                return position
    return wildcard


def find_violations(graph: dict[str, list[str]], layers: list[list[str]]) -> tuple[list[tuple], list[str]]:
    """Upward references (same layer is allowed) + projects matching no layer."""
    levels = {name: layer_of(name, layers) for name in graph}
    unassigned = sorted(n for n, level in levels.items() if level is None)
    violations = []
    for src, targets in graph.items():
        for dst in targets:
            if levels[src] is not None and levels[dst] is not None and levels[dst] > levels[src]:
                violations.append((src, levels[src], dst, levels[dst]))
    return sorted(violations), unassigned


def digest(root: str = ".", layers: str = "", max_chars: int = 4000) -> str:
    graph, dangling = build_graph(root)
    if not graph:
        return f"no .csproj files under {root}"

    edge_count = sum(len(t) for t in graph.values())
    parts = [f"{len(graph)} projects, {edge_count} references"]

    cycles = find_cycles(graph)
    parts.append(
        f"cycles ({len(cycles)}):\n" + "\n".join("  " + " -> ".join(c) for c in cycles) if cycles else "cycles: none"
    )

    if layers.strip():
        parsed = parse_layers(layers)
        legend = " | ".join(f"L{i}={','.join(t)}" for i, t in enumerate(parsed))
        violations, unassigned = find_violations(graph, parsed)
        if violations:
            lines = "\n".join(f"  {s} (L{sl}) -> {d} (L{dl})" for s, sl, d, dl in violations)
            parts.append(f"layers: {legend}\nlayer violations ({len(violations)}):\n{lines}")
        else:
            parts.append(f"layers: {legend}\nlayer violations: none")
        if unassigned:
            parts.append(f"unassigned ({len(unassigned)}): " + ", ".join(unassigned))

    if dangling:
        parts.append(f"dangling references ({len(dangling)}):\n" + "\n".join(f"  {s} -> {r}" for s, r in dangling))

    adjacency = "\n".join(f"  {src} -> {', '.join(sorted(t)) or '(none)'}" for src, t in sorted(graph.items()))
    parts.append("graph:\n" + adjacency)

    return cap("\n\n".join(parts), max_chars)


if __name__ == "__main__":
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    layers = sys.argv[2] if len(sys.argv) > 2 else ""
    print(digest(root, layers))
