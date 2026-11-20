"""Plain helpers for the shell-script regression tests: lift code out of a shipped script and run it in bash.

Every test lifts the code it pins out of the real script instead of retyping it, so a rewrite there breaks
the test instead of leaving it asserting a copy that no longer runs.
"""

import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BASH = shutil.which("bash") or "/bin/bash"


def source(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def function(text: str, name: str) -> str:
    """A top-level shell function, from its `name() {` line to the closing brace in column 0."""
    match = re.search(rf"^(?:function\s+)?{re.escape(name)}\s*\(\)\s*\{{\n.*?^\}}\n", text, re.M | re.S)
    assert match, f"{name}() no longer matches -- re-read the script before trusting this test"
    return match.group(0)


def block(text: str, pattern: str, name: str) -> str:
    match = re.search(pattern, text, re.M | re.S)
    assert match, f"{name} no longer matches -- re-read the script before trusting this test"
    return match.group(0)


def retarget(text: str, root: Path, *prefixes: str) -> str:
    """Move absolute paths under `root` so the lifted code never touches the real filesystem."""
    for prefix in prefixes:
        text = re.sub(rf"(?<![\w./-]){re.escape(prefix)}", f"{root}{prefix}", text)
    return text


def bash(script: str, *args: str, env: dict | None = None, timeout: int = 30) -> subprocess.CompletedProcess:
    return subprocess.run([BASH, "-c", script, "_", *args], capture_output=True, text=True, check=False, timeout=timeout, env=env)
