"""Execute the release pin checker against isolated trees, with read-only git responses."""

import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
VERSION = "1.6.18~rc4"
PINS = {
    "src/bw/Dockerfile": 'LABEL version="{version}"\n',
    "misc/install-bunkerweb.sh": 'DEFAULT_BUNKERWEB_VERSION="{version}"\n',
    "publiccode.yml": "softwareVersion: {version}\n",
    "pyproject.toml": 'version = "{version}"\n',
    ".github/ISSUE_TEMPLATE/bug_report.yml": "      value: {version}\n",
}


@pytest.fixture
def tree(tmp_path):
    for name, template in PINS.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(template.format(version=VERSION))
    (tmp_path / "src/VERSION").write_text(VERSION + "\n")
    bindir = tmp_path / "bin"
    bindir.mkdir()
    git = bindir / "git"
    # Only the checker's two read operations are stubbed; grep runs on actual fixture files.
    git.write_text(
        "#!/usr/bin/env bash\nset -euo pipefail\n"
        'case "$1" in\n'
        'rev-parse) printf "%s\\n" "$FIXTURE_ROOT" ;;\n'
        'grep) grep -nE "$3" src/bw/Dockerfile publiccode.yml pyproject.toml '
        ".github/ISSUE_TEMPLATE/bug_report.yml literals.txt ;;\n"
        "*) exit 2 ;;\nesac\n"
    )
    git.chmod(0o755)
    (tmp_path / "literals.txt").write_text(f"image: bunkerweb:{VERSION.replace('~', '-')}\n")
    return tmp_path


def check(tree):
    return subprocess.run(
        ["bash", str(ROOT / "misc/check-version-consistency.sh")],
        cwd=tree,
        env={**os.environ, "FIXTURE_ROOT": str(tree), "PATH": str(tree / "bin") + os.pathsep + os.environ["PATH"]},
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


def test_consistent_tree_passes(tree):
    result = check(tree)
    assert result.returncode == 0, result.stdout + result.stderr
    assert f"All version pins agree with {VERSION}" in result.stdout


@pytest.mark.parametrize("name", PINS)
@pytest.mark.parametrize("expected,wrong", [(VERSION, VERSION + "0"), ("1.6.18", VERSION)])
def test_pin_must_equal_version(tree, name, expected, wrong):
    (tree / "src/VERSION").write_text(expected + "\n")
    for pin, template in PINS.items():
        (tree / pin).write_text(template.format(version=wrong if pin == name else expected))
    (tree / "literals.txt").write_text("")
    result = check(tree)
    assert result.returncode == 1, result.stdout + result.stderr
    assert f"{name}: pin is" in result.stdout


@pytest.mark.parametrize("stale", [VERSION + "0", VERSION.replace("~", "-") + "0", "1.6.18~rc3", VERSION + "-extra"])
@pytest.mark.parametrize("same_line", [False, True])
def test_stale_token_cannot_hide_behind_current_version(tree, stale, same_line):
    prefix = f"current={VERSION} " if same_line else ""
    (tree / "literals.txt").write_text(f"{prefix}stale={stale}\n")
    result = check(tree)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "literals.txt:1:" in result.stdout


def test_final_release_rejects_stale_rc_literal(tree):
    (tree / "src/VERSION").write_text("1.6.18\n")
    for name, template in PINS.items():
        (tree / name).write_text(template.format(version="1.6.18"))
    result = check(tree)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "literals.txt:1:" in result.stdout
