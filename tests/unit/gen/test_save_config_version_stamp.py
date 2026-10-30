"""BW-453: save_config.py must never stamp a version the database schema has not been migrated to.

Linux upgrade: the package swap replaces /usr/share/bunkerweb while the old scheduler still runs. That
scheduler then launches a *fresh* save_config.py, which already runs the new code and reads the new
VERSION, against the old schema. Stamping the new version there makes the next scheduler start skip the
migration and crash on the missing columns. The script is run for real in a child process, with VERSION
faked the way the swap changes it (common_utils.get_version). SAVE_CONFIG_PY points the test at another
copy of the script (the unfixed one, to watch it fail).
"""

import os
import sqlite3
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
SCRIPT = Path(os.environ.get("SAVE_CONFIG_PY", REPO / "src" / "common" / "gen" / "save_config.py"))
LATEST_REVISION_VERSION = "1.6.18~rc2"  # has a revision in sqlite_versions
PREVIOUS_VERSION = "1.6.17"

RUNNER = textwrap.dedent("""
    import runpy, sys
    repo, script, version, plugins, pro_plugins = sys.argv[1:6]
    for sub in ("db", "api", "utils", "gen"):
        sys.path.insert(0, f"{repo}/src/common/{sub}")
    import common_utils
    common_utils.get_version = lambda: version
    sys.argv = [
        script, "--init",
        "--settings", f"{repo}/src/common/settings.json",
        "--core", f"{repo}/src/common/core",
        "--plugins", plugins,
        "--pro-plugins", pro_plugins,
    ]
    runpy.run_path(script, run_name="__main__")
    """)


@pytest.fixture
def env(tmp_path):
    (tmp_path / "plugins").mkdir()
    (tmp_path / "pro").mkdir()
    runner = tmp_path / "runner.py"
    runner.write_text(RUNNER, encoding="utf-8")
    db = tmp_path / "db.sqlite3"
    child_env = {"PATH": os.environ["PATH"], "DATABASE_URI": f"sqlite:///{db}", "LOG_LEVEL": "info", "HOME": str(tmp_path)}

    def run(version):
        return subprocess.run(
            [sys.executable, "-I", str(runner), str(REPO), str(SCRIPT), version, str(tmp_path / "plugins"), str(tmp_path / "pro")],
            env=child_env,
            cwd=tmp_path,
            capture_output=True,
            text=True,
            timeout=300,
        )

    def stored():
        with sqlite3.connect(db) as conn:
            return conn.execute("SELECT version FROM bw_metadata WHERE id = 1").fetchone()[0]

    return SimpleNamespaceLike(run=run, stored=stored)


class SimpleNamespaceLike:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


def test_fresh_database_is_stamped_with_the_installed_version(env):
    result = env.run(PREVIOUS_VERSION)
    assert result.returncode == 0, result.stderr
    assert env.stored() == PREVIOUS_VERSION


def test_new_version_on_disk_does_not_advance_an_unmigrated_database(env):
    assert env.run(PREVIOUS_VERSION).returncode == 0
    # The package swap happened: the child reads the new VERSION, the schema is still the old one.
    result = env.run(LATEST_REVISION_VERSION)
    assert env.stored() == PREVIOUS_VERSION, "the version advanced ahead of the migration"
    assert result.returncode != 0, "a database nobody migrated must stop the saver with an error"
    assert "migration has not run" in result.stdout + result.stderr


def test_matching_version_still_runs(env):
    assert env.run(PREVIOUS_VERSION).returncode == 0
    assert env.run(PREVIOUS_VERSION).returncode == 0
    assert env.stored() == PREVIOUS_VERSION


def test_a_release_without_a_revision_has_nothing_to_wait_for(env):
    assert env.run(PREVIOUS_VERSION).returncode == 0
    assert env.run("9.9.9").returncode == 0
    assert env.stored() == "9.9.9"
