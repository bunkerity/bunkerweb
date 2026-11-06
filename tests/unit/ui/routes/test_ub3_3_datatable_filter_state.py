"""Collect the SearchPanes Node tests in the normal UI pytest suite (UB3-5)."""

import shutil
import subprocess
from pathlib import Path

import pytest


def test_datatable_filter_state():
    node = shutil.which("node")
    if not node:
        pytest.skip("node not installed")
    root = Path(__file__).resolve().parents[4]
    result = subprocess.run([node, "--test", str(root / "tests/ui/datatable_filter_state.test.js")], cwd=root, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
