"""Easy-install dry-run selects the NGINX ABI matching BunkerWeb."""

import os
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[3] / "misc" / "install-bunkerweb.sh"


@pytest.mark.parametrize(
    ("version", "nginx"),
    [
        ("1.6.11", "1.30.2"),
        ("v1.6.10~rc5", "1.30.1"),
        ("1.6.12", "1.30.3"),
        ("9.9.9", "1.30.3"),
    ],
)
def test_dry_run_resolves_nginx_version(version, nginx):
    result = subprocess.run(
        [
            "bash",
            str(SCRIPT),
            "--dry-run",
            "--yes",
            "--no-tui",
            "--version",
            version,
            "--full",
        ],
        check=True,
        capture_output=True,
        text=True,
        env=os.environ | {"NO_COLOR": "1"},
    )
    assert f"NGINX version: {nginx}" in result.stdout
