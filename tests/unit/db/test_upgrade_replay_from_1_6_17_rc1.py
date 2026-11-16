"""Replay real 1.6.17~rc1, 1.6.17 and 1.6.18~rc3 databases with chunked archives and large caches.

Each start uses its tagged model and the scheduler's filename-based version lookup. Every row and
chunk must survive, readers must return the same bytes, and a second upgrade must change nothing.
The rc3 start also carries login-failure rows checked before create_all can mask a missing table.
Deleted normalization stamps exercise each scheduler's actual stamp command on an old SQLite schema.
"""

from datetime import datetime, timezone
from hashlib import sha256
from os import environ, urandom
from pathlib import Path
from subprocess import run
from sys import executable, path as python_path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, insert, inspect, text

from db.alembic_baseline import ALEMBIC, baseline_metadata, product_uri, revision_for, wipe
from db_methods import blobs  # type: ignore
from fixtures.seed import make_core_plugin
from model import Base  # type: ignore

pytestmark = pytest.mark.slow

TAG = "v1.6.17-rc1"
VERSION = "1.6.17~rc1"  # what the product records in bw_metadata.version (the tag spells it with a dash)
NOW = datetime(2026, 10, 15, 12, 0, 0, tzinfo=timezone.utc)
ARCHIVE = urandom(200 * 1024)  # stored as chunks, the way MySQL/MariaDB would store it
CHUNK = 64 * 1024
PAGE = urandom(70 * 1024)
BIG_CACHE = urandom(3 * 1024 * 1024)
PLUGIN = "extplug"
JOB = "extjob"
TEMPLATE = "ext-template"
OWNER = f"bw_plugins:{PLUGIN}"
CHECKSUM = sha256(ARCHIVE).hexdigest()
CHUNKS = [ARCHIVE[start : start + CHUNK] for start in range(0, len(ARCHIVE), CHUNK)]


def _seed(engine, tag=TAG, version=VERSION):
    t = baseline_metadata(tag).tables
    with engine.begin() as conn:
        conn.execute(
            insert(t["bw_plugins"]),
            [
                {
                    "id": PLUGIN,
                    "name": "Ext",
                    "description": "d",
                    "version": "1.0",
                    "type": "external",
                    "method": "scheduler",
                    "data": blobs.BLOB_CHUNK_MARKER + CHECKSUM.encode(),
                    "checksum": "c1",
                },
            ],
        )
        conn.execute(
            insert(t["bw_blob_chunks"]),
            [{"owner": OWNER, "checksum": CHECKSUM, "idx": idx, "data": piece} for idx, piece in enumerate(CHUNKS)],
        )
        conn.execute(insert(t["bw_plugin_pages"]), [{"plugin_id": PLUGIN, "data": PAGE, "checksum": "p1"}])
        conn.execute(insert(t["bw_jobs"]), [{"name": JOB, "plugin_id": PLUGIN, "file_name": "job.py", "every": "day", "reload": False, "run_async": False}])
        conn.execute(insert(t["bw_jobs_cache"]), [{"job_name": JOB, "file_name": "big.bin", "data": BIG_CACHE, "last_update": NOW, "checksum": "j1"}])
        conn.execute(
            insert(t["bw_templates"]),
            [{"id": TEMPLATE, "name": "Ext template", "plugin_id": PLUGIN, "method": "scheduler", "creation_date": NOW, "last_update": NOW}],
        )
        conn.execute(
            insert(t["bw_metadata"]),
            [{"id": 1, "is_initialized": True, "first_config_saved": True, "integration": "Docker", "version": version}],
        )
        if "bw_ui_login_failures" in t:
            conn.execute(
                insert(t["bw_ui_login_failures"]),
                [
                    {"username": "admin", "ip": "192.0.2.1", "failure_date": NOW},
                    {"username": "unknown", "ip": "2001:db8::1", "failure_date": NOW},
                ],
            )


def _config(db_engine):
    config = Config("alembic.ini")
    config.set_main_option("version_locations", f"{db_engine}_versions")
    return config


@pytest.fixture(params=[(TAG, VERSION), ("v1.6.17", "1.6.17"), ("v1.6.18-rc3", "1.6.18~rc3")], ids=["rc1", "stable", "rc3"])
def upgraded(db_engine, tmp_path, monkeypatch, quiet_logger, request):
    tag, version = request.param
    uri = product_uri(db_engine, tmp_path)
    monkeypatch.setenv("DATABASE_URI", uri)
    monkeypatch.chdir(ALEMBIC)

    wipe(uri)
    engine = create_engine(uri)
    baseline_metadata(tag).create_all(engine)
    assert "bw_blob_chunks" in inspect(engine).get_table_names(), "the 1.6.17~rc1 baseline must already carry the chunk table"
    _seed(engine, tag, version)
    with engine.connect() as conn:
        failures = conn.execute(text("SELECT id, username, ip, failure_date FROM bw_ui_login_failures ORDER BY id")).all() if version == "1.6.18~rc3" else None
    engine.dispose()

    config = _config(db_engine)
    command.stamp(config, revision_for(version, db_engine))
    command.upgrade(config, "head")

    engine = create_engine(uri)
    if failures is not None:
        with engine.connect() as conn:
            assert conn.execute(text("SELECT id, username, ip, failure_date FROM bw_ui_login_failures ORDER BY id")).all() == failures
    Base.metadata.create_all(engine, checkfirst=True)  # what initialization.py does next
    engine.dispose()

    from Database import Database  # noqa: E402 -- imported after sys.path injection

    database = Database(quiet_logger, sqlalchemy_string=uri, log=False)
    try:
        yield database, config
    finally:
        database.sql_engine.dispose()
        wipe(uri)


def _scalar(db, sql, **params):
    with db.sql_engine.connect() as conn:
        return conn.execute(text(sql), params).scalar()


def _plugin_archive(db):
    return next(p for p in db.get_plugins(with_data=True) if p["id"] == PLUGIN)["data"]


def test_every_seeded_row_and_blob_comes_through_unchanged(upgraded):
    db, _ = upgraded
    with db.sql_engine.connect() as conn:
        plugin = conn.execute(text("SELECT method, type, data, checksum FROM bw_plugins WHERE id = :i"), {"i": PLUGIN}).one()
        page = conn.execute(text("SELECT data, checksum FROM bw_plugin_pages WHERE plugin_id = :i"), {"i": PLUGIN}).one()
        cache = conn.execute(text("SELECT data, checksum FROM bw_jobs_cache WHERE job_name = :j"), {"j": JOB}).one()
        template = conn.execute(text("SELECT method FROM bw_templates WHERE id = :i"), {"i": TEMPLATE}).one()

    assert (plugin.method, plugin.type, bytes(plugin.data), plugin.checksum) == ("scheduler", "external", blobs.BLOB_CHUNK_MARKER + CHECKSUM.encode(), "c1")
    assert (bytes(page.data), page.checksum) == (PAGE, "p1")
    assert (bytes(cache.data), cache.checksum) == (BIG_CACHE, "j1")
    assert template.method == "scheduler"


def test_the_chunk_rows_are_kept_byte_for_byte(upgraded):
    db, _ = upgraded
    with db.sql_engine.connect() as conn:
        rows = conn.execute(text("SELECT idx, data FROM bw_blob_chunks WHERE owner = :o AND checksum = :c ORDER BY idx"), {"o": OWNER, "c": CHECKSUM}).all()
    assert [(row.idx, bytes(row.data)) for row in rows] == list(enumerate(CHUNKS))
    assert _scalar(db, "SELECT COUNT(*) FROM bw_blob_chunks") == len(CHUNKS)


def test_the_stamp_and_the_recorded_version_land_on_the_head(upgraded):
    db, _ = upgraded
    assert _scalar(db, "SELECT version_num FROM alembic_version") == revision_for("1.7.0~alpha", db.sql_engine.dialect.name)
    assert _scalar(db, "SELECT version FROM bw_metadata WHERE id = 1") == "1.7.0~alpha"


def test_the_readers_reassemble_the_chunked_archive(upgraded):
    db, _ = upgraded
    assert _plugin_archive(db) == ARCHIVE
    assert db.get_plugin_page(PLUGIN) == PAGE
    assert db.get_job_cache_file(JOB, "big.bin") == BIG_CACHE


def test_a_second_upgrade_is_a_no_op(upgraded):
    db, config = upgraded
    tables = ("bw_plugins", "bw_plugin_pages", "bw_jobs_cache", "bw_templates", "bw_blob_chunks")
    before = {t: _scalar(db, f"SELECT COUNT(*) FROM {t}") for t in tables}
    command.upgrade(config, "head")
    assert {t: _scalar(db, f"SELECT COUNT(*) FROM {t}") for t in tables} == before
    assert _plugin_archive(db) == ARCHIVE
    assert _scalar(db, "SELECT version FROM bw_metadata WHERE id = 1") == "1.7.0~alpha"


def test_a_boot_keeps_the_plugin_and_its_chunked_archive(upgraded):
    db, _ = upgraded
    assert db.init_tables([make_core_plugin("general")])[1] == ""
    assert _scalar(db, "SELECT COUNT(*) FROM bw_plugins WHERE id = :i", i=PLUGIN) == 1, "a legacy `scheduler` plugin must survive init_tables"
    assert _plugin_archive(db) == ARCHIVE
    assert db.init_tables([make_core_plugin("general")]) == (False, "")


def test_the_download_label_is_usable_on_the_upgraded_schema(upgraded):
    """On PostgreSQL the label exists only once the upgrade's transaction has committed; it is used here, after."""
    db, _ = upgraded
    with db.sql_engine.begin() as conn:
        conn.execute(text("UPDATE bw_plugins SET method = :m WHERE id = :i"), {"m": "download", "i": PLUGIN})
    assert next(p for p in db.get_plugins() if p["id"] == PLUGIN)["method"] == "download"


@pytest.mark.parametrize("script", ["src/scheduler/entrypoint.sh", "src/linux/scripts/bunkerweb-scheduler.sh"])
def test_deleted_normalization_stamp_replays_through_scheduler_command(script, tmp_path, monkeypatch):
    uri = f"sqlite:///{tmp_path / 'deleted-stamp.sqlite3'}"
    monkeypatch.setenv("DATABASE_URI", uri)
    monkeypatch.chdir(ALEMBIC)
    engine = create_engine(uri)
    baseline_metadata(TAG).create_all(engine)
    _seed(engine)
    queries = (
        "SELECT id, data, checksum FROM bw_plugins ORDER BY id",
        "SELECT job_name, file_name, data, checksum FROM bw_jobs_cache ORDER BY job_name, file_name",
        "SELECT owner, checksum, idx, data FROM bw_blob_chunks ORDER BY owner, checksum, idx",
    )
    with engine.connect() as conn:
        before = [conn.execute(text(query)).all() for query in queries]
    config = _config("sqlite")
    config_path = tmp_path / "alembic.ini"
    with config_path.open("w") as stream:
        config.file_config.write(stream)
    try:
        command.stamp(config, revision_for(VERSION, "sqlite"))
        with engine.begin() as conn:
            conn.execute(text("UPDATE alembic_version SET version_num = 'a41d5e9b7c20'"))
        source = (Path(__file__).resolve().parents[3] / script).read_text()
        stamp = next(line.strip()[3:].removesuffix("; then") for line in source.splitlines() if "-m alembic stamp " in line)
        stamp = stamp.replace("python3", executable).replace("-m alembic ", f'-m alembic -c "{config_path}" ')
        result = run(
            ["bash", "-c", stamp],
            env={**environ, "PYTHONPATH": ":".join(python_path), "PYTHON_BIN": executable, "REVISION": revision_for(VERSION, "sqlite")},
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        command.upgrade(config, "head")
        with engine.connect() as conn:
            assert conn.execute(text("SELECT version FROM bw_metadata WHERE id = 1")).scalar() == "1.7.0~alpha"
            assert [conn.execute(text(query)).all() for query in queries] == before
    finally:
        engine.dispose()
