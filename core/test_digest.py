# core/test_digest.py
"""Run a test command and return only the summary + failures, not the full log."""
import re
import sys

from _shared import run_command, cap, dedupe_lines, NUMBER_RE

FAILURE_LINE = re.compile(
    r"(FAILED|FAIL:|Error|ERROR|AssertionError|Traceback|✗|✘|\bfailed\b)", re.IGNORECASE
)
# Lowercase on purpose: pytest/jest use lowercase "passed"/"failed" only in the
# final summary line, while per-test verbose lines use uppercase PASSED/FAILED —
# this keeps individual test lines out of the summary match.
SUMMARY_LINE = re.compile(
    r"(\d+ passed\b|\d+ failed\b|\d+ error(?:s|\(s\))?\b|\d+ skipped\b|Tests:\s*\d+|Test Suites:"
    r"|\w+!\s+-\s+Failed:\s*\d+|Test summary:|Test run summary:|^Ran \d+ tests? in "
    r"|^\s*(?:total|failed|succeeded|skipped):\s*\d+\s*$)"
)

# 20261006 ++ RG #test_totals: aggregate formats first (one line for the whole run),
# per-assembly VSTest lines are summed only when no aggregate is present.
DOTNET_AGGREGATE_RE = re.compile(
    r"Test summary:\s*total:\s*(\d+),\s*failed:\s*(\d+),\s*succeeded:\s*(\d+),\s*skipped:\s*(\d+)",
    re.IGNORECASE,
)
MTP_BLOCK_RE = re.compile(
    r"^\s*total:\s*(\d+)\s*\n\s*failed:\s*(\d+)\s*\n\s*succeeded:\s*(\d+)\s*\n\s*skipped:\s*(\d+)",
    re.IGNORECASE | re.MULTILINE,
)
VSTEST_ASSEMBLY_RE = re.compile(
    r"\w+!\s+-\s+Failed:\s*(\d+),\s*Passed:\s*(\d+),\s*Skipped:\s*(\d+),\s*Total:\s*(\d+)"
)
JEST_TESTS_RE = re.compile(r"^Tests:\s+(.*\d+ total)", re.MULTILINE)
PYTEST_SUMMARY_RE = re.compile(r"^[=\s]*((?:\d+ \w+(?:, )?)+) in \d+(?:\.\d+)?s", re.MULTILINE)
UNITTEST_RAN_RE = re.compile(r"^Ran (\d+) tests? in ", re.MULTILINE)
UNITTEST_RESULT_RE = re.compile(r"^(OK|FAILED)(?: \(([^)]*)\))?\s*$", re.MULTILINE)
COUNT_WORD_RE = re.compile(r"(\d+) (\w+)")
KEY_VALUE_RE = re.compile(r"(\w+)=(\d+)")


def _totals(passed: int, failed: int, skipped: int, source: str, total: int | None = None) -> dict:
    return {
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "total": passed + failed + skipped if total is None else total,
        "source": source,
    }


def _from_count_words(text: str, source: str) -> dict:
    counts: dict[str, int] = {}
    for number, word in COUNT_WORD_RE.findall(text):
        counts[word.lower()] = counts.get(word.lower(), 0) + int(number)
    passed = counts.get("passed", 0) + counts.get("xpassed", 0)
    failed = counts.get("failed", 0) + counts.get("error", 0) + counts.get("errors", 0)
    skipped = counts.get("skipped", 0) + counts.get("xfailed", 0) + counts.get("todo", 0)
    return _totals(passed, failed, skipped, source, counts.get("total"))


def parse_totals(output: str) -> dict | None:
    """Extract passed/failed/skipped/total from known runner summaries, or None."""
    aggregate = DOTNET_AGGREGATE_RE.findall(output)
    if aggregate:
        total, failed, passed, skipped = map(int, aggregate[-1])
        return _totals(passed, failed, skipped, "dotnet", total)

    mtp = MTP_BLOCK_RE.findall(output)
    if mtp:
        total, failed, passed, skipped = map(int, mtp[-1])
        return _totals(passed, failed, skipped, "dotnet-mtp", total)

    assemblies = VSTEST_ASSEMBLY_RE.findall(output)
    if assemblies:
        sums = [sum(int(row[i]) for row in assemblies) for i in range(4)]
        failed, passed, skipped, total = sums
        return _totals(passed, failed, skipped, f"vstest x{len(assemblies)} assemblies", total)

    jest = JEST_TESTS_RE.findall(output)
    if jest:
        return _from_count_words(jest[-1], "jest")

    ran = UNITTEST_RAN_RE.findall(output)
    results = UNITTEST_RESULT_RE.findall(output)
    if ran and results:
        total = int(ran[-1])
        details = {k: int(v) for k, v in KEY_VALUE_RE.findall(results[-1][1])}
        failed = details.get("failures", 0) + details.get("errors", 0) + details.get("unexpected_successes", 0)
        skipped = details.get("skipped", 0) + details.get("expected_failures", 0)
        return _totals(total - failed - skipped, failed, skipped, "unittest", total)

    pytest = PYTEST_SUMMARY_RE.findall(output)
    if pytest:
        return _from_count_words(pytest[-1], "pytest")

    return None


def _format_totals(totals: dict | None) -> str:
    if totals is None:
        return "totals: not recognized"
    return (
        f"totals: passed={totals['passed']} failed={totals['failed']} "
        f"skipped={totals['skipped']} total={totals['total']} ({totals['source']})"
    )


def digest(cmd: str, cwd: str = ".", max_chars: int = 2000) -> str:
    exit_code, output = run_command(cmd, cwd)
    lines = output.splitlines()

    summary_lines = [l for l in lines if SUMMARY_LINE.search(l)]
    # 20261006 ** RG #test_totals: summary lines like "failed: 0" are not failures
    failure_lines = [l.strip() for l in lines if FAILURE_LINE.search(l) and not SUMMARY_LINE.search(l)]
    deduped = dedupe_lines(failure_lines, normalize=NUMBER_RE)

    parts = [f"exit_code={exit_code}", _format_totals(parse_totals(output))]
    if summary_lines:
        parts.append("summary:\n" + "\n".join(summary_lines[-5:]))
    if deduped:
        top = deduped[:30]
        formatted = "\n".join(f"[x{c}] {l}" for l, c in top)
        parts.append(f"failures ({len(failure_lines)} lines, {len(deduped)} distinct):\n{formatted}")
    elif exit_code == 0:
        parts.append("no failures detected")
    else:
        parts.append("non-zero exit but no recognizable failure lines; last 20 lines:\n" + "\n".join(lines[-20:]))

    return cap("\n\n".join(parts), max_chars)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "pytest"
    cwd = sys.argv[2] if len(sys.argv) > 2 else "."
    print(digest(cmd, cwd))
