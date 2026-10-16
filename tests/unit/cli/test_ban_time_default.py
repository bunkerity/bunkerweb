"""`bwcli ban` takes its default duration from BAD_BEHAVIOR_BAN_TIME, suffixes included."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]


def _default_in_help(value):
    paths = [ROOT / "src" / "common" / name for name in ("cli", "api", "utils", "db")]
    env = {k: v for k, v in os.environ.items() if k != "BAD_BEHAVIOR_BAN_TIME"} | {"PYTHONPATH": os.pathsep.join(map(str, paths))}
    if value is not None:
        env["BAD_BEHAVIOR_BAN_TIME"] = value
    result = subprocess.run([sys.executable, "src/common/cli/main.py", "ban", "-h"], cwd=ROOT, env=env, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    return result.stdout.split("(default: ")[1].split(",")[0]


@pytest.mark.parametrize(("value", "expected"), [(None, "86400"), ("86400", "86400"), ("1d", "86400"), ("2h", "7200"), ("0", "0"), ("junk", "86400")])
def test_ban_default_duration(value, expected):
    assert _default_in_help(value) == expected
