"""D6 keeps 1.7's existing 2048-byte report URL cap."""

import re
import shutil
import subprocess
from pathlib import Path

import pytest

METRICS = Path(__file__).resolve().parents[3] / "src/common/core/metrics/metrics.lua"
LUA = shutil.which("lua") or shutil.which("luajit")


@pytest.mark.skipif(LUA is None, reason="no stand-alone lua/luajit on PATH")
def test_existing_report_url_cap():
    source = METRICS.read_text()
    constant = re.search(r"^local MAX_STORED_URL = \d+$", source, re.M).group()
    bound = re.search(r"^local function bound\(.*?^end$", source, re.M | re.S).group()
    assert "url = bound(self.ctx.bw.request_uri, MAX_STORED_URL)" in source
    result = subprocess.run(
        [LUA, "-"],
        input=constant + "\n" + bound + """
assert(MAX_STORED_URL == 2048)
local url = string.rep("x", 2048)
assert(bound(url, MAX_STORED_URL) == url)
assert(bound(url .. "tail", MAX_STORED_URL) == url .. "...")
""",
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
