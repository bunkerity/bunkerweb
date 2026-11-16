"""The evidence view shows the real counter even when its event list was capped."""

import re
import shutil
import subprocess
from pathlib import Path

import pytest

NODE = shutil.which("node")
SCRIPT = Path(__file__).resolve().parents[3] / "src/ui/app/static/js/pages/reports.js"


@pytest.mark.skipif(NODE is None, reason="node not installed")
def test_counter_uses_ban_counter_and_keeps_legacy_event_count_fallback():
    source = re.search(r"^  function formatBadBehaviorData\(.*?^  }$", SCRIPT.read_text(), re.M | re.S).group()
    result = subprocess.run(
        [
            NODE,
            "-e",
            """
const assert = require('node:assert/strict');
const t = (_, fallback) => fallback;
const escapeHtml = String;
const getMethodBadgeClass = () => '';
const getStatusBadgeClass = () => '';
const formatBadBehaviorTimestamp = () => '';
"""
            + source
            + """
const count = entries => formatBadBehaviorData(entries).match(/bad-behavior-summary__total-count">([0-9]+)/)[1];
assert.equal(count([{counter: 250}, {counter: 12}]), '250');
assert.equal(count([{}, {}]), '2');
assert.equal(count([{counter: NaN}, {counter: Infinity}]), '2');
""",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
