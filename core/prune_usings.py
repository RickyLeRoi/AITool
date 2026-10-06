# core/prune_usings.py
"""Find (and optionally delete) unnecessary C# using directives via IDE0005,
without relying on `dotnet format` or the solution's own analyzer config."""
import json
import os
import re
import shutil
import sys
import tempfile
import urllib.parse
import urllib.request

from _shared import run_command, cap, dedupe_lines, NUMBER_RE

EXCLUDE_DIRS = {".git", "node_modules", "bin", "obj", ".vs", "packages", "TestResults"}
BUILD_TIMEOUT = 1800
UTF8_BOM = b"\xef\xbb\xbf"

BUILD_ERROR_RE = re.compile(r":\s*error\s*(?:(?!IDE0005\b)[A-Z]+\d+\s*)?:", re.IGNORECASE)
GENERATED_PATH_RE = re.compile(r"[\\/](?:obj|bin)[\\/]", re.IGNORECASE)
USING_LINE_RE = re.compile(rb"^[ \t]*(?:global[ \t]+)?using[ \t]+[^;{}()\r\n]+;[ \t]*(?://[^\r\n]*)?\r?\n?$")
SILENCED_RE = re.compile(
    rb"^([ \t]*dotnet_diagnostic\.IDE0005\.severity[ \t]*=[ \t]*)"
    rb"(none|silent|suggestion|hidden|info|default)([ \t]*(?:[#;][^\r\n]*)?)(?=\r?$)",
    re.IGNORECASE | re.MULTILINE,
)
EDITORCONFIG_ROOT_RE = re.compile(rb"^[ \t]*root[ \t]*=[ \t]*true", re.IGNORECASE | re.MULTILINE)

GLOBALCONFIG = """is_global = true
global_level = 1000
dotnet_diagnostic.IDE0005.severity = warning
"""
# 20261006 ++ RG #prune_usings: one SARIF per compilation (project x TFM). The console
# line only carries the first line of each IDE0005 span; SARIF has startLine..endLine,
# and an empty SARIF still proves that TFM was compiled.
TARGETS = """<Project>
  <PropertyGroup>
    <NoWarn>$(NoWarn);CS1570;CS1572;CS1573;CS1574;CS1584;CS1587;CS1591;CS1658</NoWarn>
    <ErrorLog>{sarif_dir}{sep}$(MSBuildProjectName)_$(TargetFramework)_$([MSBuild]::StableStringHash($(MSBuildProjectFullPath))).sarif,version=2.1</ErrorLog>
  </PropertyGroup>
  <ItemGroup>
    <GlobalAnalyzerConfigFiles Include="{globalconfig}" />
  </ItemGroup>
</Project>
"""


def resolve_target(root: str) -> str:
    """root itself if it's a .sln/.slnx/.csproj, else the single solution (or project) in it."""
    if os.path.isfile(root):
        return root
    entries = sorted(os.listdir(root))
    for extensions in ((".sln", ".slnx"), (".csproj",)):
        matches = [e for e in entries if e.lower().endswith(extensions)]
        if len(matches) == 1:
            return os.path.join(root, matches[0])
        if len(matches) > 1:
            raise ValueError(f"ambiguous target in {root}: {', '.join(matches)} - pass one explicitly")
    raise ValueError(f"no .sln/.slnx/.csproj in {root}")


def _editorconfigs(root: str) -> list[str]:
    """Every .editorconfig under root, plus ancestors up to the first `root = true`."""
    found = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
        if ".editorconfig" in filenames:
            found.append(os.path.join(dirpath, ".editorconfig"))
    current = os.path.abspath(root)
    while True:
        candidate = os.path.join(current, ".editorconfig")
        if os.path.isfile(candidate):
            if candidate not in found:
                found.append(candidate)
            with open(candidate, "rb") as fh:
                if EDITORCONFIG_ROOT_RE.search(fh.read()):
                    break
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent
    return found


def patch_editorconfigs(root: str, backup_dir: str, patched: list[tuple[str, bytes]]) -> None:
    """Raise IDE0005 to warning wherever an .editorconfig silences it.
    Appends (path, original bytes) to `patched` as it goes, so a failure halfway
    still leaves the caller a complete restore list; byte copies go to backup_dir."""
    for path in _editorconfigs(root):
        with open(path, "rb") as fh:
            original = fh.read()
        updated, count = SILENCED_RE.subn(rb"\g<1>warning\g<3>", original)
        if not count:
            continue
        with open(os.path.join(backup_dir, f"editorconfig_{len(patched)}.bak"), "wb") as fh:
            fh.write(original)
        with open(path, "wb") as fh:
            fh.write(updated)
        patched.append((path, original))


def restore_files(patched: list[tuple[str, bytes]]) -> list[str]:
    failures = []
    for path, original in patched:
        try:
            with open(path, "wb") as fh:
                fh.write(original)
        except OSError as exc:
            failures.append(f"{path}: {exc}")
    return failures


def _uri_to_path(uri: str) -> str:
    parsed = urllib.parse.urlparse(uri)
    if parsed.scheme != "file":
        return urllib.parse.unquote(uri)
    return urllib.request.url2pathname(urllib.parse.unquote(parsed.path))


def _sarif_context(filename: str) -> tuple[str, str]:
    """'Name_net8.0_12345.sarif' -> ('Name_12345', 'net8.0'); the hash disambiguates same-named projects."""
    name, tfm, digest_hash = os.path.splitext(filename)[0].rsplit("_", 2)
    return f"{name}_{digest_hash}", tfm


def parse_sarif_dir(sarif_dir: str) -> tuple[dict[tuple[str, int], dict], dict[str, set[str]]]:
    """Return ((normalized path, line) -> {'path', 'contexts': {(project, tfm)}},
    project -> every TFM it was compiled for)."""
    found: dict[tuple[str, int], dict] = {}
    compiled: dict[str, set[str]] = {}
    for filename in sorted(os.listdir(sarif_dir)):
        if not filename.endswith(".sarif"):
            continue
        project, tfm = _sarif_context(filename)
        compiled.setdefault(project, set()).add(tfm)
        with open(os.path.join(sarif_dir, filename), encoding="utf-8-sig") as fh:
            runs = json.load(fh).get("runs", [])
        for run in runs:
            for result in run.get("results", []):
                if result.get("ruleId") != "IDE0005" or result.get("suppressions"):
                    continue
                for location in result.get("locations", []):
                    physical = location.get("physicalLocation", {})
                    path = _uri_to_path(physical.get("artifactLocation", {}).get("uri", ""))
                    region = physical.get("region", {})
                    if not path.lower().endswith(".cs") or GENERATED_PATH_RE.search(path) or "startLine" not in region:
                        continue
                    for line in range(region["startLine"], region.get("endLine", region["startLine"]) + 1):
                        key = (os.path.normcase(os.path.normpath(path)), line)
                        entry = found.setdefault(key, {"path": path, "contexts": set()})
                        entry["contexts"].add((project, tfm))
    return found, compiled


def select_removable(
    diagnostics: dict, compiled: dict[str, set[str]]
) -> tuple[dict[str, list[int]], dict[str, list[int]]]:
    """Split flagged lines into removable (flagged in every TFM of every project
    compiling the file) and partial (an #if-guarded using, most likely)."""
    removable: dict[str, list[int]] = {}
    partial: dict[str, list[int]] = {}
    for (_, line), entry in sorted(diagnostics.items()):
        seen: dict[str, set[str]] = {}
        for project, tfm in entry["contexts"]:
            seen.setdefault(project, set()).add(tfm)
        complete = all(compiled[project] <= seen_tfms for project, seen_tfms in seen.items())
        (removable if complete else partial).setdefault(entry["path"], []).append(line)
    return removable, partial


def read_lines(path: str) -> list[bytes]:
    with open(path, "rb") as fh:
        return fh.read().splitlines(keepends=True)


def _is_using_line(line: bytes) -> bool:
    return bool(USING_LINE_RE.match(line[len(UTF8_BOM):] if line.startswith(UTF8_BOM) else line))


def remove_using_lines(path: str, line_numbers: list[int]) -> tuple[list[int], list[int]]:
    """Delete the given 1-based lines at byte level (CRLF, BOM and non-UTF-8 bytes untouched).
    A line that is no longer a using directive is skipped, not deleted."""
    lines = read_lines(path)
    removed, skipped = [], []
    for number in sorted(set(line_numbers), reverse=True):
        index = number - 1
        if not (0 <= index < len(lines)) or not _is_using_line(lines[index]):
            skipped.append(number)
            continue
        if index == 0 and lines[0].startswith(UTF8_BOM):
            lines[0] = UTF8_BOM
        else:
            del lines[index]
        removed.append(number)
    if removed:
        with open(path, "wb") as fh:
            fh.write(b"".join(lines))
    return sorted(removed), sorted(skipped)


def keep_using_lines(path: str, line_numbers: list[int]) -> list[int]:
    """An IDE0005 span can cover blank/comment lines between usings - drop those."""
    lines = read_lines(path)
    return [n for n in line_numbers if 0 < n <= len(lines) and _is_using_line(lines[n - 1])]


def _shown(path: str, base: str) -> str:
    """Root-relative when under root (8.3 short names resolved first), absolute otherwise."""
    full, root = os.path.realpath(path), os.path.realpath(base)
    try:
        if os.path.commonpath([full, root]) == root:
            return os.path.relpath(full, root)
    except ValueError:
        pass
    return full


def _preview(path: str, line_numbers: list[int], base: str) -> str:
    lines = read_lines(path)
    shown = [
        f"{n} {lines[n - 1].replace(UTF8_BOM, b'').strip().decode('utf-8', errors='replace')}" for n in line_numbers
    ]
    return f"  {_shown(path, base)}: " + " | ".join(shown)


def _build_command(target: str, targets_path: str) -> str:
    return (
        f'dotnet build "{target}" --no-incremental -nologo -clp:NoSummary'
        " -p:GenerateDocumentationFile=true -p:EnforceCodeStyleInBuild=true"
        " -p:TreatWarningsAsErrors=false -p:CodeAnalysisTreatWarningsAsErrors=false"
        f' "-p:CustomBeforeMicrosoftCommonTargets={targets_path}"'
    )


def digest(root: str = ".", apply: bool = False, max_chars: int = 4000) -> str:
    try:
        target = resolve_target(root)
    except ValueError as exc:
        return str(exc)
    base = root if os.path.isdir(root) else os.path.dirname(os.path.abspath(root))

    work_dir = tempfile.mkdtemp(prefix="prune_usings_")
    sarif_dir = os.path.join(work_dir, "sarif")
    os.makedirs(sarif_dir)
    globalconfig_path = os.path.join(work_dir, "prune.globalconfig")
    targets_path = os.path.join(work_dir, "prune.targets")
    with open(globalconfig_path, "w", encoding="utf-8") as fh:
        fh.write(GLOBALCONFIG)
    with open(targets_path, "w", encoding="utf-8") as fh:
        fh.write(TARGETS.format(globalconfig=globalconfig_path, sarif_dir=sarif_dir, sep=os.sep))

    parts = [f"target: {_shown(target, base)}"]
    diagnostics: dict = {}
    compiled: dict[str, set[str]] = {}
    patched: list[tuple[str, bytes]] = []
    restore_failures: list[str] = []
    try:
        patch_editorconfigs(base, work_dir, patched)
        exit_code, output = run_command(
            _build_command(target, targets_path),
            cwd=base,
            timeout=BUILD_TIMEOUT,
            env={"MSBUILDTERMINALLOGGER": "off", "DOTNET_CLI_UI_LANGUAGE": "en"},
        )
        diagnostics, compiled = parse_sarif_dir(sarif_dir)
    finally:
        # 20261006 ++ RG #prune_usings: restore before anything else can fail;
        # keep the byte backups on disk if the restore itself failed.
        restore_failures = restore_files(patched)
        if not restore_failures:
            shutil.rmtree(work_dir, ignore_errors=True)

    if patched:
        names = ", ".join(_shown(p, base) for p, _ in patched)
        status = "restored" if not restore_failures else f"RESTORE FAILED, backups in {work_dir}"
        parts.append(f"editorconfig: IDE0005 raised to warning temporarily in {names} ({status})")
    if restore_failures:
        parts.append("restore errors:\n" + "\n".join(restore_failures))

    build_errors = [l.strip() for l in output.splitlines() if BUILD_ERROR_RE.search(l)]
    if exit_code != 0 and build_errors:
        top = "\n".join(f"[x{c}] {l}" for l, c in dedupe_lines(build_errors, normalize=NUMBER_RE)[:10])
        parts.append(f"build failed (exit_code={exit_code}), nothing removed - diagnostics would be incomplete:\n{top}")
        return cap("\n\n".join(parts), max_chars)

    contexts = sum(len(t) for t in compiled.values())
    parts.append(f"build: exit_code={exit_code}, {len(compiled)} projects / {contexts} compilations analyzed")
    if not compiled:
        tail = "\n".join(output.strip().splitlines()[-20:])
        parts.append(f"no compilation produced an error log - nothing analyzed; last build output lines:\n{tail}")
        return cap("\n\n".join(parts), max_chars)

    removable, partial = select_removable(diagnostics, compiled)
    removable = {p: kept for p, n in removable.items() if (kept := keep_using_lines(p, n))}
    partial = {p: kept for p, n in partial.items() if (kept := keep_using_lines(p, n))}
    line_total = sum(len(v) for v in removable.values())

    if partial:
        listing = "\n".join(f"  {_shown(p, base)}: lines {', '.join(map(str, n))}" for p, n in partial.items())
        parts.append(f"kept - flagged only for some target frameworks ({sum(map(len, partial.values()))} lines):\n{listing}")

    if not removable:
        parts.append("no unnecessary usings")
        return cap("\n\n".join(parts), max_chars)

    if not apply:
        preview = "\n".join(_preview(p, n, base) for p, n in removable.items())
        parts.append(f"removable ({line_total} lines, {len(removable)} files):\n{preview}")
        parts.append("dry run - call again with apply=True to delete these lines")
        return cap("\n\n".join(parts), max_chars)

    removed_total, skipped_report = 0, []
    for path, numbers in removable.items():
        removed, skipped = remove_using_lines(path, numbers)
        removed_total += len(removed)
        if skipped:
            skipped_report.append(f"  {_shown(path, base)}: lines {', '.join(map(str, skipped))}")
    parts.append(f"removed {removed_total} lines in {len(removable)} files")
    if skipped_report:
        parts.append("skipped (line no longer a using directive):\n" + "\n".join(skipped_report))
    return cap("\n\n".join(parts), max_chars)


if __name__ == "__main__":
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    apply = len(sys.argv) > 2 and sys.argv[2].lower() in ("1", "true", "apply")
    print(digest(root, apply))
