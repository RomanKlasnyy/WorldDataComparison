"""Check relative Markdown links and image paths in the documentation.

Run: python tools/check_links.py [root]
The optional root defaults to the repository root and can point at an extracted
release folder to validate the portable documentation.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LINK = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
SKIP_PREFIXES = ("http://", "https://", "mailto:", "tel:", "#")


def main() -> int:
    root = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else ROOT
    missing: list[tuple[Path, str]] = []
    checked = 0
    files = [
        *root.glob("*.md"),
        *root.glob("docs/**/*.md"),
        *root.glob(".github/**/*.md"),
        *root.glob("data/**/*.md"),
    ]
    for path in files:
        text = path.read_text(encoding="utf-8")
        for match in LINK.finditer(text):
            target = match.group(1).strip()
            if target.startswith(SKIP_PREFIXES) or target.startswith("//"):
                continue
            target = target.split("#", 1)[0].strip()
            if not target:
                continue
            checked += 1
            resolved = (path.parent / target).resolve()
            if not resolved.exists():
                missing.append((path.relative_to(root), target))
    for path, target in missing:
        print(f"MISSING {path}: {target}")
    print(f"checked {checked} relative targets in {len(files)} files; missing {len(missing)}")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
