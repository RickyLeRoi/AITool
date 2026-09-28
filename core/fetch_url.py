# core/fetch_url.py
"""Fetch a URL and return a stripped-tags text digest, instead of raw HTML."""
import re
import sys
import urllib.request

from _shared import cap

TAG_RE = re.compile(r"<script.*?</script>|<style.*?</style>|<[^>]+>", re.DOTALL | re.IGNORECASE)
BLANK_RE = re.compile(r"\n\s*\n+")


def digest(url: str, max_chars: int = 3000, timeout: int = 15) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "claude-local-tools/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            content_type = resp.headers.get("Content-Type", "")
            raw = resp.read().decode("utf-8", errors="ignore")
            status = resp.status
    except Exception as exc:
        return f"error fetching {url}: {exc}"

    if "html" in content_type:
        text = TAG_RE.sub(" ", raw)
        text = BLANK_RE.sub("\n", text)
        text = "\n".join(line.strip() for line in text.splitlines() if line.strip())
    else:
        text = raw

    return cap(f"status={status} content_type={content_type}\n\n{text}", max_chars)


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else sys.exit("usage: fetch_url.py <url> [max_chars]")
    max_chars = int(sys.argv[2]) if len(sys.argv) > 2 else 3000
    print(digest(url, max_chars))
