"""The upgrade replay with DATA: a 1.6.15 database holding a URL-installed plugin, its template, page and a large job cache.

`test_upgrade_schema_parity.py` proves the schema; this proves what the operator cares about -- that
the rows, their `method` labels and their blob bytes come through the 1.7.0~alpha chain unchanged,
that the chunk table (created by the 1.6.16~rc3 revision, not by the head) is there and empty, that
the new `download` label is usable afterwards, and that a second upgrade and a boot are no-ops. The
starting point is the real `v1.6.15` model, stamped and upgraded the way `entrypoint.sh` does it.

The stored labels stay `scheduler`: relabelling to `download` is a runtime step of the download job,
never a migration (PostgreSQL cannot use a new enum label in the transaction that adds it).
"""

from datetime import datetime, timezone
from os import urandom

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, insert, inspect, text

from db.alembic_baseline import ALEMBIC, FINAL_1_6_15_TAG, FINAL_1_6_15_VERSION, baseline_metadata, product_uri, revision_for, wipe
from db_methods import blobs  # type: ignore
from fixtures.seed import make_core_plugin
from model import Base  # type: ignore

pytestmark = pytest.mark.slow

NOW = datetime(2026, 10, 5, 12, 0, 0, tzinfo=timezone.utc)
ARCHIVE = urandom(300 * 1024)
PAGE = urandom(70 * 1024)
BIG_CACHE = urandom(3 * 1024 * 1024)  # far above the 16 KiB chunk floor, below every default packet size
PLUGIN = "extplug"
JOB = "extjob"
TEMPLATE = "ext-template"


def _seed(engine):
    t = baseline_metadata(FINAL_1_6_15_TAG).tables
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
                    "data": ARCHIVE,
                    "checksum": "c1",
                },
            ],
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
            [{"id": 1, "is_initialized": True, "first_config_saved": True, "integration": "Docker", "version": FINAL_1_6_15_VERSION}],
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
    baseline_metadata(FINAL_1_6_15_TAG).create_all(engine)
    _seed(engine)
    engine.dispose()
    assert "bw_blob_chunks" not in inspect(create_engine(uri)).get_table_names(), "the 1.6.15 baseline must not carry the chunk table"

    config = _config(db_engine)
    command.stamp(config, revision_for(FINAL_1_6_15_VERSION, db_engine))
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


def test_every_seeded_row_and_blob_comes_through_unchanged(upgraded):
    db, _ = upgraded
    with db.sql_engine.connect() as conn:
        plugin = conn.execute(text("SELECT method, type, data, checksum FROM bw_plugins WHERE id = :i"), {"i": PLUGIN}).one()
        page = conn.execute(text("SELECT data, checksum FROM bw_plugin_pages WHERE plugin_id = :i"), {"i": PLUGIN}).one()
        cache = conn.execute(text("SELECT data, checksum FROM bw_jobs_cache WHERE job_name = :j"), {"j": JOB}).one()
        template = conn.execute(text("SELECT method FROM bw_templates WHERE id = :i"), {"i": TEMPLATE}).one()

    assert (plugin.method, plugin.type, bytes(plugin.data), plugin.checksum) == ("scheduler", "external", ARCHIVE, "c1")
    assert (bytes(page.data), page.checksum) == (PAGE, "p1")
    assert (bytes(cache.data), cache.checksum) == (BIG_CACHE, "j1")
    assert template.method == "scheduler", "the migration must not relabel anything: that is the download job's runtime step"


def test_the_chunk_table_exists_and_is_empty(upgraded):
    db, _ = upgraded
    assert "bw_blob_chunks" in inspect(db.sql_engine).get_table_names()
    assert _scalar(db, "SELECT COUNT(*) FROM bw_blob_chunks") == 0


def test_the_stamp_and_the_recorded_version_land_on_the_head(upgraded):
    db, _ = upgraded
    assert _scalar(db, "SELECT version_num FROM alembic_version") == revision_for("1.7.0~alpha", db.sql_engine.dialect.name)
    assert _scalar(db, "SELECT version FROM bw_metadata WHERE id = 1") == "1.7.0~alpha"


def test_the_readers_return_the_same_bytes(upgraded):
    db, _ = upgraded
    assert next(p for p in db.get_plugins(with_data=True) if p["id"] == PLUGIN)["data"] == ARCHIVE
    assert db.get_plugin_page(PLUGIN) == PAGE
    assert db.get_job_cache_file(JOB, "big.bin") == BIG_CACHE


def test_a_second_upgrade_is_a_no_op(upgraded):
    db, config = upgraded
    before = {t: _scalar(db, f"SELECT COUNT(*) FROM {t}") for t in ("bw_plugins", "bw_plugin_pages", "bw_jobs_cache", "bw_templates", "bw_blob_chunks")}
    command.upgrade(config, "head")
    after = {t: _scalar(db, f"SELECT COUNT(*) FROM {t}") for t in before}
    assert after == before
    assert db.get_job_cache_file(JOB, "big.bin") == BIG_CACHE


def test_a_boot_loses_nothing_and_the_second_boot_changes_nothing(upgraded):
    db, _ = upgraded
    assert db.init_tables([make_core_plugin("general")])[1] == ""
    assert _scalar(db, "SELECT COUNT(*) FROM bw_plugins WHERE id = :i", i=PLUGIN) == 1, "a legacy `scheduler` plugin must survive init_tables"
    # Its template, job and job cache are NOT asserted here: `init_tables` derives them from the plugin directories it is handed,
    # and this boot is handed none for `extplug`, so it prunes them by design (a production boot passes the directory).
    assert next(p for p in db.get_plugins(with_data=True) if p["id"] == PLUGIN)["data"] == ARCHIVE
    assert db.init_tables([make_core_plugin("general")]) == (False, "")


def test_the_download_label_is_usable_on_the_upgraded_schema(upgraded):
    """On PostgreSQL the label exists only once the upgrade's transaction has committed; it is used here, after."""
    db, _ = upgraded
    with db.sql_engine.begin() as conn:
        conn.execute(text("UPDATE bw_plugins SET method = :m WHERE id = :i"), {"m": "download", "i": PLUGIN})
    assert next(p for p in db.get_plugins() if p["id"] == PLUGIN)["method"] == "download"


def test_a_chunked_blob_round_trips_on_the_upgraded_schema(upgraded, monkeypatch):
    """The table the rc3 revision made takes real chunk rows: forced on every engine, as in production on MySQL/MariaDB."""
    db, _ = upgraded
    monkeypatch.setattr(blobs, "blob_chunk_size", lambda _session: 16 * 1024)
    data = urandom(200 * 1024)
    assert db.upsert_job_cache(None, "chunked.bin", data, job_name=JOB) == ""
    assert _scalar(db, "SELECT COUNT(*) FROM bw_blob_chunks") > 1
    assert db.get_job_cache_file(JOB, "chunked.bin") == data
    assert db.get_job_cache_file(JOB, "big.bin") == BIG_CACHE
