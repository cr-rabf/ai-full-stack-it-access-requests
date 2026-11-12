#!/usr/bin/env python3
"""Check that this computer and this copy of the repository are ready for the Challenge.

Run it from the root of your clone:

    python3 tools/check_prerequisites.py

It checks four things and prints PASS or FAIL for each, with what to do on a FAIL:

  1. Codex is installed and signed in.
  2. This folder is a clone of the Challenge repository, with every supplied file in place.
  3. Entire records your coding sessions in this repository.
  4. The repository's tests run on mock responses: no model is called and API_KEY is not used.

The last line is READY when all four pass. Python 3.10 or later, standard library only.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUPPLIED = ["CHALLENGE.md", "snapshot.schema.json", "materials/office-policy.md", "docs/requirements.md"]
REQUESTS = 20


def run(command: list[str], env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True, timeout=300,
                          stdin=subprocess.DEVNULL)


def check_codex() -> tuple[bool, str]:
    if not shutil.which("codex"):
        return False, "codex is not on your PATH. Install the Codex CLI the way the facilitator shows you, then open a new terminal."
    version = run(["codex", "--version"])
    if version.returncode != 0:
        return False, f"codex --version failed: {version.stderr.strip() or version.stdout.strip()}"
    login = run(["codex", "login", "status"])
    if login.returncode != 0:
        return False, f"{version.stdout.strip()} is installed but not signed in. Sign in with the class key the facilitator gives you."
    return True, f"{version.stdout.strip()}; {login.stdout.strip() or login.stderr.strip()}"


def check_clone() -> tuple[bool, str]:
    inside = run(["git", "rev-parse", "--show-toplevel"])
    if inside.returncode != 0 or Path(inside.stdout.strip()).resolve() != ROOT:
        return False, "this folder is not the top of a Git clone. Clone your copy of the repository and run this from its root."
    if not run(["git", "remote", "get-url", "origin"]).stdout.strip():
        return False, "the clone has no remote named origin. Clone your copy of the repository from GitHub."
    missing = [name for name in SUPPLIED if not (ROOT / name).is_file()]
    if missing:
        return False, f"missing supplied files: {', '.join(missing)}. Clone the repository again."
    exports = sorted((ROOT / "materials" / "requests").glob("*.json"))
    if len(exports) != REQUESTS:
        return False, f"materials/requests/ holds {len(exports)} JSON files, not {REQUESTS}. Clone the repository again."
    for path in exports:
        try:
            if not isinstance(json.loads(path.read_bytes().decode("utf-8")).get("message"), str):
                return False, f"{path.name} has no message text. Clone the repository again."
        except (UnicodeDecodeError, ValueError, AttributeError):
            return False, f"{path.name} is not UTF-8 JSON. Clone the repository again."
    return True, f"clone of {run(['git', 'remote', 'get-url', 'origin']).stdout.strip()}; {len(exports)} request exports read"


def check_capture() -> tuple[bool, str]:
    if not shutil.which("entire"):
        return False, "entire is not on your PATH. Install the Entire CLI as the course's session-capture guide says."
    status = run(["entire", "status", "--json"])
    try:
        state = json.loads(status.stdout)
    except ValueError:
        return False, f"entire status gave no answer: {status.stderr.strip() or status.stdout.strip()}"
    if not state.get("enabled"):
        return False, "Entire is not enabled in this repository. Run: entire enable --agent codex"
    if "Codex" not in (state.get("agents") or []):
        return False, "Entire is enabled but not for Codex. Run: entire agent add codex"
    return True, f"Entire enabled for {', '.join(state['agents'])}"


def check_tests() -> tuple[bool, str]:
    env = {key: value for key, value in os.environ.items() if key != "API_KEY"}
    tests = run([sys.executable, "-m", "unittest", "discover", "-s", "tests"], env=env)
    summary = [line for line in tests.stderr.splitlines() if line.startswith(("Ran ", "OK", "FAILED"))]
    if tests.returncode != 0:
        return False, "the tests failed with API_KEY unset:\n" + tests.stderr.strip()
    return True, "; ".join(summary) + " (API_KEY unset)"


def main() -> int:
    if sys.version_info < (3, 10):
        print(f"FAIL  Python {sys.version.split()[0]}: this Challenge needs Python 3.10 or later.")
        return 1
    checks = [("Codex", check_codex), ("Repository", check_clone),
              ("Session capture", check_capture), ("Tests on mock responses", check_tests)]
    passed = 0
    for number, (name, check) in enumerate(checks, 1):
        ok, detail = check()
        passed += ok
        print(f"{'PASS' if ok else 'FAIL'}  {number}. {name}: {detail}")
    if passed == len(checks):
        print(f"READY: all {len(checks)} checks passed. Start docs/01-research-to-spec.md.")
        return 0
    print(f"NOT READY: {len(checks) - passed} of {len(checks)} checks failed. Fix each FAIL above and run this again;"
          " if one still fails, ask the facilitator.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
