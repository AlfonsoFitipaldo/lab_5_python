"""Run the repository's required local checks.

Adapted from the course's scripts/check_all.py. The course version also runs
scripts/smoke_demos.py, which executes lessons/*/demo/*.py; this repository has
no lessons, so that step is replaced by a smoke run of the CLI's --help, which
imports the whole package without touching the network.
"""

import subprocess
import sys


def run(command: list[str]) -> None:
    print(f"+ {' '.join(command)}", flush=True)
    subprocess.run(command, check=True)


def main() -> int:
    commands = [
        [sys.executable, "-m", "ruff", "check", "."],
        [sys.executable, "-m", "ruff", "format", "--check", "."],
        [sys.executable, "-m", "pytest", "-q"],
        [sys.executable, "scripts/check_content.py"],
        [sys.executable, "scripts/check_links.py"],
        [sys.executable, "-m", "registry_client", "--help"],
    ]
    try:
        for command in commands:
            run(command)
    except subprocess.CalledProcessError as error:
        return error.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
