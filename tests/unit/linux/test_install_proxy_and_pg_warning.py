"""Installer proxy exports and Debian/Ubuntu backup-client warnings, without host changes."""

import json
import os
import re
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[3] / "misc" / "install-bunkerweb.sh"
PROXY_NAMES = ("http_proxy", "https_proxy", "no_proxy")


@pytest.mark.parametrize("mode", ["uppercase", "lowercase", "both", "empty_lowercase", "unset"])
@pytest.mark.parametrize("xtrace", [False, True])
def test_proxy_exports_reach_child_processes_without_tracing_credentials(mode, xtrace):
    env = {key: value for key, value in os.environ.items() if key.lower() not in PROXY_NAMES}
    for name in PROXY_NAMES:
        if mode in ("uppercase", "both", "empty_lowercase"):
            env[name.upper()] = "UPPER_SENTINEL"
        if mode in ("lowercase", "both"):
            env[name] = "lower_sentinel"
        elif mode == "empty_lowercase":
            env[name] = ""
    expected = "lower_sentinel" if mode in ("lowercase", "both") else "UPPER_SENTINEL" if mode == "uppercase" else ""
    # Run only startup exports, before traps, argument parsing or installer actions.
    prefix = SCRIPT.read_text().split("# Registry of 0600 secret tempfiles", 1)[0]
    child = "import json, os; print(json.dumps([os.environ.get(k) for k in ('http_proxy', 'https_proxy', 'no_proxy')]))"
    result = subprocess.run(
        ["bash", "-xc" if xtrace else "-c", prefix + '\npython3 -c "$1"\nprintf "TRACE_RESTORED\\n"', "_", child],
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(result.stdout.splitlines()[0]) == [expected] * 3
    assert "UPPER_SENTINEL" not in result.stderr
    assert "lower_sentinel" not in result.stderr
    assert ("+ printf" in result.stderr) == xtrace


def _function(name):
    match = re.search(rf"^{name}\(\) \{{\n.*?^\}}\n", SCRIPT.read_text(), re.M | re.S)
    assert match, f"{name}() missing"
    return match.group(0)


@pytest.mark.parametrize(
    ("distro", "version", "major", "url_distro"),
    [
        ("debian", "12", "15", "debian"),
        ("debian", "13", "17", "debian"),
        ("ubuntu", "22.04", "14", "ubuntu"),
        ("ubuntu", "24.04", "16", "ubuntu"),
        ("ubuntu", "26.04", "18", "ubuntu"),
        ("ubuntu", "99.04", "(distribution default)", "ubuntu"),
    ],
)
@pytest.mark.parametrize("interactive", ["yes", "no"])
def test_postgresql_warning_names_client_major_and_manual_remediation(distro, version, major, url_distro, interactive):
    result = subprocess.run(
        [
            "bash",
            "-ec",
            _function("show_debian_database_warning") + """
DISTRO_FAMILY=debian; DISTRO_ID=$1; DISTRO_VERSION=$2; INTERACTIVE_MODE=$3
print_warning() { printf 'WARNING:%s\\n' "$*"; }
print_status() { printf 'STATUS:%s\\n' "$*"; }
tui_msgbox() { printf 'DIALOG:%s\\n%s\\n' "$1" "$2"; }
show_debian_database_warning
""",
            "_",
            distro,
            version,
            interactive,
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    assert f"package ships PostgreSQL {major}." in result.stdout
    assert "server version mismatch from pg_dump" in result.stdout
    assert "bwcli plugin backup save" in result.stdout
    assert f"https://www.postgresql.org/download/linux/{url_distro}/" in result.stdout
    assert "${VERSION_CODENAME}-pgdg" in result.stdout
    assert "$(dpkg --print-architecture)" in result.stdout
    assert 'sudo apt install "postgresql-client-${PG_MAJOR}"' in result.stdout
    assert ("DIALOG:" in result.stdout) == (interactive == "yes")
    assert ("Continuing installation..." in result.stdout) == (interactive == "no")


def test_postgresql_warning_skips_non_debian_families():
    result = subprocess.run(
        ["bash", "-ec", _function("show_debian_database_warning") + "\nDISTRO_FAMILY=rhel\nshow_debian_database_warning"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout == ""


@pytest.mark.parametrize(
    ("docker", "start_over", "resuming", "warns"),
    [("no", "no", "no", True), ("no", "yes", "no", True), ("yes", "no", "no", False), ("no", "no", "yes", False)],
)
def test_main_shows_warning_only_for_fresh_native_installs(docker, start_over, resuming, warns):
    main_prefix = _function("main").split("    # Env vars per install type", 1)[0]
    result = subprocess.run(
        [
            "bash",
            "-ec",
            _function("show_debian_database_warning") + main_prefix + "\n}\n" + """
DISTRO_FAMILY=debian; DISTRO_ID=debian; DISTRO_VERSION=12; INTERACTIVE_MODE=no
DOCKER_MODE=$1; _BW_START_OVER=$2; _BW_RESUMING=$3; UPGRADE_SCENARIO=no; _BW_RESUME_AFTER=package
for name in check_root detect_os tui_init detect_architecture ask_deployment_platform \\
    check_docker_prereqs _docker_check_existing_stack check_supported_os \\
    _bw_state_load_and_prompt check_existing_installation show_rhel_database_warning ask_user_preferences; do
    eval "$name() { :; }"
done
print_status() { :; }
print_warning() { printf '%s\\n' "$*"; }
check_ports() { exit 0; }
main
""",
            "_",
            docker,
            start_over,
            resuming,
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    assert ("package ships PostgreSQL 15." in result.stdout) == warns
