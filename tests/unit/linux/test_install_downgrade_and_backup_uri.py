"""Same-core Docker downgrade refusal, and last-wins DATABASE_URI for the upgrade backup.

Port of dev ``da85ff697``. Two independent defects in `misc/install-bunkerweb.sh`:

- `_docker_is_downgrade` compared the numeric core ONLY, so `1.6.15 -> 1.6.15-rc1` (a real
  downgrade: the stable release carries Alembic revisions the rc does not) read as "same core,
  not a downgrade" and was installed silently.
- the pre-upgrade backup took the FIRST env file that declared `DATABASE_URI`, while the
  scheduler exports `variables.env` then `scheduler.env` and lets the LAST one win. A host with
  a stale URI in `variables.env` backed up the wrong database.

Both functions are extracted from the real script and run in a bash subshell, so the assertions
are about the shipped source, not a copy.
"""

import re
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[3] / "misc" / "install-bunkerweb.sh"


def _extract(*names):
    text = SCRIPT.read_text(encoding="utf-8")
    out = []
    for name in names:
        match = re.search(rf"^{re.escape(name)}\(\) \{{\n.*?^\}}\n", text, re.M | re.S)
        assert match, f"{name}() not found in {SCRIPT.name}"
        out.append(match.group(0))
    return "\n".join(out)


DOWNGRADE_SRC = _extract("_docker_version_core", "_docker_prerelease_rank", "_docker_is_downgrade")
BACKUP_URI_SRC = _extract("_upgrade_backup_database_uri")


def _is_downgrade(installed, target) -> bool:
    result = subprocess.run(
        ["bash", "-c", f'{DOWNGRADE_SRC}\nif _docker_is_downgrade "$1" "$2"; then echo yes; else echo no; fi', "_", installed, target],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip() == "yes"


@pytest.mark.parametrize(
    ("installed", "target"),
    [
        ("1.6.15", "1.6.14"),
        ("1.6.15", "1.6.15-rc1"),
        ("1.6.15", "1.6.15~rc2"),
        ("1.6.15-rc2", "1.6.15-rc1"),
        ("1.6.15~rc10", "1.6.15~rc2"),
        # The whole pre-release ladder, not just rc: alpha < beta < rc < stable.
        ("1.7.0~rc1", "1.7.0~beta"),
        ("1.7.0~beta", "1.7.0~alpha2"),
        ("1.7.0~beta2", "1.7.0~beta1"),
        ("1.7.0", "1.7.0~beta"),
    ],
)
def test_a_downgrade_is_recognised(installed, target):
    assert _is_downgrade(installed, target) is True, f"{installed} -> {target} was not refused"


@pytest.mark.parametrize(
    ("installed", "target"),
    [
        ("1.6.14", "1.6.15"),
        ("1.6.15-rc1", "1.6.15"),
        ("1.6.15~rc1", "1.6.15~rc2"),
        ("1.6.15~rc2", "1.6.15~rc10"),
        ("1.6.15", "1.6.15"),
        ("1.6.15-rc1", "1.6.15-rc1"),
        # 1.7 ships `1.7.0~beta` and its next tag is an rc: ranking beta as stable made THIS
        # upgrade refuse to run, and the call site is a bare `exit 1` with no override.
        ("1.7.0~beta", "1.7.0~rc1"),
        ("1.7.0~alpha1", "1.7.0~beta"),
        ("1.7.0~beta1", "1.7.0~beta2"),
        ("1.7.0~beta", "1.7.0"),
        # Floating tags have no comparable core and stay unordered.
        ("latest", "1.6.15"),
        ("1.6.15", "testing"),
    ],
)
def test_a_forward_move_is_allowed(installed, target):
    assert _is_downgrade(installed, target) is False, f"{installed} -> {target} was refused"


def _backup_uri(variables: str, scheduler: str, tmp_path) -> str:
    paths = []
    for name, content in (("variables.env", variables), ("scheduler.env", scheduler)):
        path = tmp_path / name
        if content is not None:
            path.write_text(content, encoding="utf-8")
        paths.append(str(path))
    result = subprocess.run(
        ["bash", "-c", f'{BACKUP_URI_SRC}\n_upgrade_backup_database_uri "$1" "$2"', "_", *paths],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def test_scheduler_env_wins_over_variables_env(tmp_path):
    """Scheduler Only keeps the URI in scheduler.env; a stale one in variables.env must not win."""
    uri = _backup_uri("DATABASE_URI=sqlite:////stale.sqlite3\n", "DATABASE_URI=postgresql://u:p@db/bw\n", tmp_path)
    assert uri == "postgresql://u:p@db/bw"


def test_variables_env_is_used_when_scheduler_env_has_none(tmp_path):
    uri = _backup_uri("DATABASE_URI=postgresql://u:p@db/bw\n", "LOG_LEVEL=info\n", tmp_path)
    assert uri == "postgresql://u:p@db/bw"


def test_a_missing_file_is_not_an_error(tmp_path):
    uri = _backup_uri("DATABASE_URI=postgresql://u:p@db/bw\n", None, tmp_path)
    assert uri == "postgresql://u:p@db/bw"


def test_nothing_declared_yields_an_empty_value(tmp_path):
    assert _backup_uri("LOG_LEVEL=info\n", "LOG_LEVEL=debug\n", tmp_path) == ""
