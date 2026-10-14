"""The upgrade replay with DATA, starting from the FINAL 1.6.16: a database holding a chunked plugin archive and a large job cache.

`test_upgrade_replay_with_blobs.py` starts at 1.6.15 and crosses rc1..rc4 on its way. This one starts
where an operator on 1.6.16 really is: the real `v1.6.16` model, `bw_blob_chunks` already there and
holding rows, stamped at the 1.6.16 revision the way `entrypoint.sh` does it (it resolves the stamped
`bw_metadata.version` by filename, so the lookup is part of what is proved). The single revision
between that stamp and the head is the 1.7.0~alpha one; what must come out is every row and every
chunk unchanged, the readers returning the same bytes, a second upgrade that does nothing, and a
recorded version of 1.7.0~alpha.
"""

from datetime import datetime, timezone
from hashlib import sha256
from os import urandom

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, insert, inspect, text

from db.alembic_baseline import ALEMBIC, baseline_metadata, product_uri, revision_for, wipe
from db_methods import blobs  # type: ignore
from fixtures.seed import make_core_plugin
from model import Base  # type: ignore

pytestmark = pytest.mark.slow

TAG = "v1.6.16"
VERSION = TAG.lstrip("v")
NOW = datetime(2026, 10, 14, 12, 0, 0, tzinfo=timezone.utc)
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


def _seed(engine):
    t = baseline_metadata(TAG).tables
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
            [{"id": 1, "is_initialized": True, "first_config_saved": True, "integration": "Docker", "version": VERSION}],
        )


def _config(db_engine):
    config = Config("alembic.ini")
    config.set_main_option("version_locations", f"{db_engine}_versions")
    return config


@pytest.fixture
def upgraded(db_engine, tmp_path, monkeypatch, quiet_logger):
    uri = product_uri(db_engine, tmp_path)
    monkeypatch.setenv("DATABASE_URI", uri)
    monkeypatch.chdir(ALEMBIC)

    wipe(uri)
    engine = create_engine(uri)
    baseline_metadata(TAG).create_all(engine)
    assert "bw_blob_chunks" in inspect(engine).get_table_names(), "the 1.6.16 baseline must already carry the chunk table"
    _seed(engine)
    engine.dispose()

    config = _config(db_engine)
    command.stamp(config, revision_for(VERSION, db_engine))
    command.upgrade(config, "head")

    engine = create_engine(uri)
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
