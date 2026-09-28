# core/deps_digest.py
"""List a project's declared dependencies from common manifest files."""
import json
import os
import re
import sys

from _shared import cap

CSPROJ_REF_RE = re.compile(r'<PackageReference\s+Include="([^"]+)"\s+Version="([^"]+)"')
REQUIREMENTS_RE = re.compile(r"^\s*([A-Za-z0-9_.\-\[\]]+)\s*([=<>!~]{1,2}=?\s*[\w.\*]*)?\s*$")


def _from_package_json(path: str) -> list[str]:
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    out = []
    for section in ("dependencies", "devDependencies"):
        for name, version in data.get(section, {}).items():
            out.append(f"{name}@{version} ({section})")
    return out


def _from_requirements_txt(path: str) -> list[str]:
    out = []
    with open(path, encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("-"):
                continue
            m = REQUIREMENTS_RE.match(line)
            if m:
                out.append(line)
    return out


def _from_csproj(path: str) -> list[str]:
    with open(path, encoding="utf-8", errors="ignore") as fh:
        text = fh.read()
    return [f"{name} {version}" for name, version in CSPROJ_REF_RE.findall(text)]


def digest(root: str = ".", max_chars: int = 2500) -> str:
    parts = []
    for fname in os.listdir(root):
        path = os.path.join(root, fname)
        if not os.path.isfile(path):
            continue
        try:
            if fname == "package.json":
                deps = _from_package_json(path)
                parts.append(f"package.json ({len(deps)} packages):\n" + "\n".join(deps))
            elif fname == "requirements.txt":
                deps = _from_requirements_txt(path)
                parts.append(f"requirements.txt ({len(deps)} packages):\n" + "\n".join(deps))
            elif fname.endswith(".csproj"):
                deps = _from_csproj(path)
                parts.append(f"{fname} ({len(deps)} packages):\n" + "\n".join(deps))
        except Exception as exc:
            parts.append(f"{fname}: could not parse ({exc})")

    if not parts:
        return "no recognized manifest files (package.json, requirements.txt, *.csproj) in root"

    return cap("\n\n".join(parts), max_chars)


if __name__ == "__main__":
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    print(digest(root))
