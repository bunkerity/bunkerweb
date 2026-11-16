"""Reject removed package channels before any fresh-install or upgrade side effect."""

import os
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(os.environ.get("P_RELEASE_ROOT", Path(__file__).resolve().parents[3]))
SCRIPT = ROOT / "misc/install-bunkerweb.sh"
FLOATING = ["dev", "testing", "1.7-dev", "1.7-testing", "1.7_dev", "1.7_testing"]


def function(name):
    match = re.search(rf"^{name}\(\) \{{\n.*?^\}}\n", SCRIPT.read_text(), re.M | re.S)
    assert match, name
    return match.group(0)


@pytest.mark.parametrize("version", FLOATING)
def test_cli_refuses_floating_native_version_before_dry_run(version):
    result = subprocess.run(["bash", str(SCRIPT), "--dry-run", "--yes", "--no-tui", "--full", "--version", version], capture_output=True, text=True)
    assert result.returncode != 0
    assert "published version" in result.stdout + result.stderr
    assert "Docker testing" in result.stdout + result.stderr


@pytest.mark.parametrize("entry", ["install_bunkerweb_debian", "install_bunkerweb_rpm", "upgrade_only"])
@pytest.mark.parametrize("version", FLOATING)
def test_native_entry_points_refuse_floating_versions_before_side_effects(entry, version):
    script = function("_require_versioned_package") + function(entry) + """
BUNKERWEB_VERSION=$1; DOCKER_MODE=no
print_error() { printf '%s\\n' "$*"; }
print_step() { echo SIDE_EFFECT; exit 99; }
run_cmd() { echo SIDE_EFFECT; exit 99; }
""" + entry
    result = subprocess.run(["bash", "-eu", "-c", script, "_", version], capture_output=True, text=True)
    assert result.returncode == 1
    assert "SIDE_EFFECT" not in result.stdout + result.stderr
    assert "published version" in result.stdout


@pytest.mark.parametrize("version", ["1.7.0", "1.7.0~alpha", "1.7.0~rc1"])
def test_versioned_native_dry_run_still_works(version):
    result = subprocess.run(["bash", str(SCRIPT), "--dry-run", "--yes", "--no-tui", "--full", "--version", version], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_docker_testing_tag_still_works():
    result = subprocess.run(
        ["bash", str(SCRIPT), "--docker", "--dry-run", "--yes", "--no-tui", "--full", "--version", "testing"], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Image tag: testing" in result.stdout


def test_installer_never_weakens_dpkg_version_checks():
    text = SCRIPT.read_text()
    assert "force-bad-version" not in text
    assert "_dpkg_allow_testing_dev_version" not in text
