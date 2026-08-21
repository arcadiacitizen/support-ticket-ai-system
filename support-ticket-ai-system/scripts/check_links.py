from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parents[1]
LINK_PATTERN = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
REQUIRED_FILES = (
    "README.md",
    "docs/product.md",
    "docs/architecture.md",
    "docs/ml.md",
    "docs/monitoring.md",
    "docs/risks-and-ops.md",
    "AI_USAGE.md",
    "WORKLOG.md",
    "SELF_REVIEW.md",
    "support_ticket_ai/engine.py",
    "tests/test_engine.py",
)


def main() -> int:
    missing = [f"required file: {path}" for path in REQUIRED_FILES if not (ROOT / path).is_file()]
    for markdown in sorted(ROOT.rglob("*.md")):
        if ".git" in markdown.parts:
            continue
        for raw_target in LINK_PATTERN.findall(markdown.read_text(encoding="utf-8")):
            target = raw_target.strip().strip("<>").split("#", 1)[0]
            if not target or target.startswith(("http://", "https://", "mailto:")):
                continue
            resolved = (markdown.parent / unquote(target)).resolve()
            if not resolved.exists():
                missing.append(f"{markdown.relative_to(ROOT)} -> {raw_target}")
    if missing:
        print("Broken local links:", *missing, sep="\n- ")
        return 1
    print("Required files and local Markdown links: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
