"""LX1-01: migrate without changing packaged Alembic configuration."""

import os
import shutil
import sqlite3
import sys

import pytest
from _t7_helpers import ROOT, bash, function, retarget, source


@pytest.fixture
def migration_root(tmp_path):
    directory = tmp_path / "usr/share/bunkerweb/db/alembic"
    directory.mkdir(parents=True)
    for filename in ("env.py", "alembic.ini"):
        shutil.copyfile(ROOT / "src/common/db/alembic" / filename, directory / filename)
    # Two tiny revisions exercise real Alembic discovery, stamping and SQLite DDL.
    for engine in ("sqlite", "mysql", "mariadb", "postgresql"):
        revisions = directory / f"{engine}_versions"
        revisions.mkdir()
        (revisions / "a111_upgrade_to_version_1_6_17.py").write_text("revision = 'a111'\ndown_revision = None\ndef upgrade(): pass\n")
        (revisions / "b222_upgrade_to_version_1_6_18_rc4.py").write_text(
            "from alembic import op\nimport sqlalchemy as sa\nrevision = 'b222'\ndown_revision = 'a111'\n"
            "def upgrade(): op.create_table('lxq_proof', sa.Column('id', sa.Integer, primary_key=True))\n"
        )
    (directory.parent.parent / "VERSION").write_text("1.6.18~rc4")
    (tmp_path / "etc/bunkerweb").mkdir(parents=True)
    for name in ("variables.env", "scheduler.env"):
        (tmp_path / "etc/bunkerweb" / name).touch()
    (tmp_path / "var/lib/bunkerweb").mkdir(parents=True)
    return directory


@pytest.mark.parametrize("engine", ["sqlite", "mysql", "mariadb", "postgresql"])
def test_env_override_alone_is_too_late_for_revision_discovery(migration_root, engine):
    """Counterexample to removing all version-location configuration: env.py loads after ScriptDirectory."""
    uri = "sqlite:///unused.db" if engine == "sqlite" else f"{engine}://user:password@db.invalid/test"
    result = bash(
        f"cd '{migration_root}'\n'{sys.executable}' -s -m alembic stamp --sql a111",
        env=os.environ | {"DATABASE_URI": uri, "PYTHONPATH": str(ROOT / "src/common/db")},
    )
    assert result.returncode != 0
    assert "Can't locate revision identified by 'a111'" in result.stdout + result.stderr
    assert "version_locations = versions" in (migration_root / "alembic.ini").read_text()


@pytest.mark.parametrize("failure", [None, "stamp", "upgrade"])
def test_wrapper_migrates_using_a_private_config_and_preserves_packaged_ini(tmp_path, migration_root, failure):
    ini = migration_root / "alembic.ini"
    original = ini.read_bytes()
    ini.chmod(0o444)
    migration_root.chmod(0o555)
    database = tmp_path / "var/lib/bunkerweb/db.sqlite3"
    called = tmp_path / "commands"
    wrapper = retarget(function(source("src/linux/scripts/bunkerweb-scheduler.sh"), "start"), tmp_path, "/usr/share", "/etc", "/var")
    try:
        result = bash(
            f"""
            log() {{ echo "$*"; }}
            stop() {{ :; }}
            chown() {{ :; }}
            get_python_bin() {{ echo python_command; }}
            get_bunkerweb_pythonpath() {{ echo '{ROOT}/src/common/db:{ROOT}/src/common/utils'; }}
            export_env_file() {{ :; }}
            create_private_tmpdir() {{ mktemp -d '{tmp_path}/private.XXXXXX'; }}
            run_as_nginx() {{ "$@"; }}
            env() {{
                case "$1" in PYTHONPATH=*) export "$1"; shift ;; esac
                "$@"
            }}
            python_command() {{
                case "$*" in
                    *version_check.py)
                        echo 'sqlite:///{database}' > '{tmp_path}/var/tmp/bunkerweb/database_uri'
                        echo 1.6.17 ;;
                    '-s -m alembic '*)
                        echo "$*" >> '{called}'
                        if [ "$4" = '{failure}' ]; then return 7; fi
                        '{sys.executable}' "$@" ;;
                    *scheduler/main.py*) echo scheduler >> '{called}' ;;
                    *) return 99 ;;
                esac
            }}
            DATABASE_URI='sqlite:///{database}'
            PYTHON_BIN=python_command
            {wrapper}
            start
            """,
        )
    finally:
        migration_root.chmod(0o755)
    assert result.returncode == (1 if failure else 0), result.stdout + result.stderr
    assert ini.read_bytes() == original, "packaged ini must remain byte-identical, including on failure"
    assert not list(tmp_path.glob("private.*")), "temporary migration configuration leaked"
    assert called.exists(), "Alembic was never reached: " + result.stdout + result.stderr
    commands = called.read_text().splitlines()
    if failure:
        assert "scheduler" not in commands
        assert ("migration failed" if failure == "upgrade" else "Failed to stamp") in result.stdout
    else:
        assert commands[-1] == "scheduler"
        with sqlite3.connect(database) as db:
            assert db.execute("SELECT version_num FROM alembic_version").fetchone() == ("b222",)
            assert db.execute("SELECT name FROM sqlite_master WHERE name='lxq_proof'").fetchone() == ("lxq_proof",)
