"""Check local Markdown links."""

import re
from pathlib import Path

ROOT = Path(__file__).parents[1]
LINK_PATTERN = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


def main() -> int:
    failures: list[str] = []
    for document in ROOT.rglob("*.md"):
        if any(part in {".git", ".instructor", ".venv"} for part in document.parts):
            continue
        for target in LINK_PATTERN.findall(document.read_text(encoding="utf-8")):
            if target.startswith(("http://", "https://", "#", "mailto:")):
                continue
            path_text = target.split("#", maxsplit=1)[0]
            if path_text and not (document.parent / path_text).exists():
                failures.append(f"{document.relative_to(ROOT)} -> {target}")
    if failures:
        print("\n".join(failures))
        return 1
    print("Local Markdown links passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
