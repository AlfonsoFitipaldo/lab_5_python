"""Fail when private or instructor-only content could be published."""

import re
import subprocess
from pathlib import Path

SELF = Path(__file__).resolve()
ROOT = SELF.parents[1]
SCANNED_SUFFIXES = {".py", ".md", ".json", ".toml", ".yml", ".yaml"}

# Directory names used for private course-administration material. A path
# containing any of these must never reach the student-facing repository.
FORBIDDEN_PATH_PARTS = (
    re.compile(r"^\.instructor$"),
    re.compile(r"^semanas?$", re.IGNORECASE),
    re.compile(r"^entregas?$", re.IGNORECASE),
)

# Patterns rather than literals, so this guard never has to embed the very
# addresses and credentials it exists to keep out of the repository.
FORBIDDEN_TEXT = (
    (
        "personal email address",
        re.compile(r"[\w.+-]+@(?:gmail|hotmail|outlook|yahoo)\.com", re.IGNORECASE),
    ),
    ("internal email address", re.compile(r"[\w.+-]+@pwc\.com", re.IGNORECASE)),
    ("credential keyword", re.compile(r"codigo[_\s-]?maestro|contrase\u00f1a", re.IGNORECASE)),
)


def main() -> int:
    failures: list[str] = []
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    publishable_paths = (ROOT / line for line in result.stdout.splitlines())
    for path in publishable_paths:
        if not path.is_file() or path.resolve() == SELF:
            continue
        relative = path.relative_to(ROOT)
        if any(pattern.match(part) for part in relative.parts for pattern in FORBIDDEN_PATH_PARTS):
            failures.append(f"forbidden path: {relative}")
            continue
        if path.suffix.lower() not in SCANNED_SUFFIXES:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for label, pattern in FORBIDDEN_TEXT:
            if pattern.search(text):
                failures.append(f"{label} found in {relative}")
    if failures:
        print("\n".join(failures))
        return 1
    print("Content safety checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
