"""Easy-install dry-run selects the NGINX ABI matching BunkerWeb."""

import os
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[3] / "misc" / "install-bunkerweb.sh"
RC_LINE = "1.6.18"


@pytest.mark.parametrize(
    ("version", "nginx"),
    [
        ("1.6.11", "1.30.2"),
        ("v1.6.10~rc5", "1.30.1"),
        ("1.6.12", "1.30.3"),
        # Releases that were on the previous default stay pinned to it once the default moves on.
        ("1.6.13", "1.30.4"),
        ("1.6.14", "1.30.4"),
        ("1.6.15", "1.30.5"),
        ("1.6.16", "1.30.5"),
        ("1.6.17", "1.30.6"),
        (f"v{RC_LINE}-rc4", "1.30.6"),
        (f"{RC_LINE}~rc5", "1.30.7"),
        # Unknown/future version falls back to DEFAULT_NGINX_VERSION.
        ("9.9.9", "1.30.7"),
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


def _run_dry(*args, env=None):
    return subprocess.run(
        ["bash", str(SCRIPT), "--dry-run", "--yes", "--no-tui", *args, "--full"],
        capture_output=True,
        text=True,
        env=os.environ | {"NO_COLOR": "1"} | (env or {}),
    )


@pytest.mark.parametrize("version", ["dev", "testing", "1.7-dev"])
def test_floating_package_versions_are_refused(version):
    result = _run_dry("--version", version)
    assert result.returncode == 1
    assert f"No '{version}' package is published" in result.stdout + result.stderr


def test_testing_docker_tag_is_still_accepted():
    assert _run_dry("--docker", "--image-tag", "testing").returncode == 0


@pytest.mark.parametrize(
    ("variable", "flag", "password", "valid_password", "message"),
    [
        ("BW_DB_PASSWORD", "--db-password", "short", "Valid-db-12", "8+ chars, no quotes/backslashes"),
        ("BW_UI_ADMIN_PASSWORD", "--ui-admin-password", "nocapitals123!", "Valid-ui-12!", "one lowercase, one uppercase, one digit, one special"),
        ("BW_DB_PASSWORD", "--db-password", "Valid-db-1\nsecond-line", "Valid-db-12", "8+ chars, no quotes/backslashes"),
        ("BW_DB_PASSWORD", "--db-password", "Valid-db-1\rsecond-line", "Valid-db-12", "8+ chars, no quotes/backslashes"),
        ("BW_UI_ADMIN_PASSWORD", "--ui-admin-password", "Valid-ui-1!\nsecond-line", "Valid-ui-12!", "one lowercase, one uppercase, one digit, one special"),
        ("BW_UI_ADMIN_PASSWORD", "--ui-admin-password", "Valid-ui-1!\rsecond-line", "Valid-ui-12!", "one lowercase, one uppercase, one digit, one special"),
        ("BW_REDIS_PASSWORD", "--redis-password", "redis\nsecond-line", "ok", "must be a single line"),
        ("BW_REDIS_PASSWORD", "--redis-password", "redis\rsecond-line", r"a\b", "must be a single line"),
    ],
)
def test_password_validation_matches_for_environment_and_flags(variable, flag, password, valid_password, message):
    from_environment = _run_dry(env={variable: password})
    from_flag = _run_dry(flag, password)
    for result in (from_environment, from_flag):
        output = result.stdout + result.stderr
        assert result.returncode == 1, output
        assert message in output
        assert password not in output

    # A valid flag overrides an invalid environment value, and a valid env value works on its own.
    assert _run_dry(flag, valid_password, env={variable: password}).returncode == 0
    assert _run_dry(env={variable: valid_password}).returncode == 0
