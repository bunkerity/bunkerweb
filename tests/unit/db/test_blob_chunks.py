"""Large-blob chunking (#3965): Plugins.data, Plugin_pages.data and Jobs_cache.data above one statement.

MySQL/MariaDB cannot carry a statement larger than ``max_allowed_packet`` and a non-SUPER user cannot
raise it, so such a blob lives in ``bw_blob_chunks`` and its owner column holds a marker. PostgreSQL and
SQLite chunk in production only content that starts with ``BLOB_CHUNK_MARKER``, so every behaviour test forces a small chunk size and runs on every
engine; the real-packet tests at the end use a real MariaDB with a small ``max_allowed_packet``.
"""

import sys
import threading
import time
from hashlib import sha256
from os import urandom
from shutil import which
from subprocess import DEVNULL, PIPE, run
from unittest.mock import Mock
from uuid import uuid4

import pytest
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError, OperationalError

from db_methods import blobs  # type: ignore
from db_methods.blobs import BLOB_CHUNK_MARKER, BLOB_MARKER_LENGTH, blob_load, blob_matches, blob_store, blob_sweep, chunk_size_for  # type: ignore
from db_methods.common import delete_service_rows  # type: ignore
from fixtures.seed import add_jobs_cache_row, add_service, make_core_plugin, make_external_plugin, seed_minimal, seed_multisite, session
from model import Blob_chunks, Jobs, Jobs_cache, Plugin_pages, Plugins  # type: ignore

CHUNK = 1024


@pytest.fixture
def small(monkeypatch):
    """Force a 1 KiB chunk size on whatever engine runs, so PostgreSQL and SQLite exercise the code path too."""
    monkeypatch.setattr(blobs, "blob_chunk_size", lambda _session: CHUNK)
    return CHUNK


@pytest.fixture
def jdb(db):
    seed_minimal(db)
    return db


def blob(size=CHUNK * 5 + 17):
    return urandom(size)


def chunk_sets(db):
    with session(db) as s:
        return sorted({(row.owner, row.checksum) for row in s.execute(select(Blob_chunks.owner, Blob_chunks.checksum))})


def chunk_count(db):
    with session(db) as s:
        return len(s.execute(select(Blob_chunks.idx)).all())


def raw(db, column, **filters):
    """The owner column exactly as stored (a marker when chunked)."""
    with session(db) as s:
        return s.execute(select(column).filter_by(**filters)).scalar()


def cache_id(db, **filters):
    with session(db) as s:
        return s.execute(select(Jobs_cache.id).filter_by(**filters)).scalar()


def marker_of(data):
    return BLOB_CHUNK_MARKER + sha256(data).hexdigest().encode()


class TestPureHelpers:
    def test_marker_is_80_bytes(self):
        assert len(BLOB_CHUNK_MARKER) == 16
        assert BLOB_MARKER_LENGTH == 80
        assert len(marker_of(b"x")) == BLOB_MARKER_LENGTH

    @pytest.mark.parametrize(
        "packet, expected",
        [
            (16 * 1024 * 1024, 4 * 1024 * 1024),  # the cap
            (64 * 1024 * 1024, 4 * 1024 * 1024),
            (1024 * 1024, (1024 * 1024 - 64 * 1024) // 3),  # a third of the packet less 64 KiB of headroom
            (100 * 1024, 16 * 1024),  # the floor
            (1024, 16 * 1024),
        ],
    )
    @pytest.mark.parametrize("dialect", ["mysql", "mariadb"])
    def test_chunk_size_on_mysql_family(self, dialect, packet, expected):
        assert chunk_size_for(dialect, packet) == expected

    @pytest.mark.parametrize("dialect", ["sqlite", "postgresql"])
    def test_no_chunking_on_engines_without_a_packet_limit(self, dialect):
        assert chunk_size_for(dialect, 1024) is None

    def test_blob_matches_plain_and_marker(self):
        data = b"payload"
        assert blob_matches(data, data)
        assert not blob_matches(data, b"other")
        assert blob_matches(None, None)
        assert not blob_matches(None, data)
        assert blob_matches(marker_of(data), data)
        assert not blob_matches(marker_of(data), b"other")
        assert not blob_matches(marker_of(data), None)


class TestStoreAndLoad:
    def test_fits_in_one_statement_is_returned_unchanged(self, jdb, small):
        data = b"x" * CHUNK
        with session(jdb) as s:
            assert blob_store(s, "bw_jobs_cache:1", data) == data
            assert blob_store(s, "bw_jobs_cache:1", None) is None
        assert chunk_count(jdb) == 0

    def test_round_trip_in_ordered_chunks(self, jdb, small):
        data = blob()
        with session(jdb) as s:
            value = blob_store(s, "bw_jobs_cache:9", data)
        assert value == marker_of(data)
        assert chunk_count(jdb) == -(-len(data) // CHUNK)
        with session(jdb) as s:
            assert blob_load(s, "bw_jobs_cache:9", value, jdb.logger) == data

    def test_same_set_is_not_written_twice(self, jdb, small):
        data = blob()
        with session(jdb) as s:
            blob_store(s, "bw_jobs_cache:9", data)
        before = chunk_sets(jdb)
        with session(jdb) as s:
            blob_store(s, "bw_jobs_cache:9", data)
        assert chunk_sets(jdb) == before
        assert chunk_count(jdb) == -(-len(data) // CHUNK)

    def test_rewrite_drops_the_other_sets_of_that_owner_only(self, jdb, small):
        first, second, neighbour = blob(), blob(CHUNK * 2 + 1), blob()
        with session(jdb) as s:
            blob_store(s, "bw_jobs_cache:1", first)
            blob_store(s, "bw_jobs_cache:2", neighbour)
            blob_store(s, "bw_jobs_cache:1", second)
        assert chunk_sets(jdb) == sorted([("bw_jobs_cache:1", sha256(second).hexdigest()), ("bw_jobs_cache:2", sha256(neighbour).hexdigest())])

    def test_a_blob_that_shrinks_to_fit_leaves_no_chunks(self, jdb, small):
        with session(jdb) as s:
            blob_store(s, "bw_jobs_cache:1", blob())
            assert blob_store(s, "bw_jobs_cache:1", b"tiny") == b"tiny"
        assert chunk_count(jdb) == 0

    def test_plain_values_pass_through_load(self, jdb):
        with session(jdb) as s:
            assert blob_load(s, "bw_jobs_cache:1", b"plain", jdb.logger) == b"plain"
            assert blob_load(s, "bw_jobs_cache:1", None, jdb.logger) is None
            assert blob_load(s, "bw_jobs_cache:1", b"", jdb.logger) == b""

    def test_missing_chunks_load_as_none_and_log(self, jdb):
        logger = Mock()
        with session(jdb) as s:
            assert blob_load(s, "bw_jobs_cache:1", marker_of(b"gone"), logger) is None
        logger.error.assert_called_once()

    def test_reader_follows_a_writer_that_swapped_the_set(self, jdb, small):
        """Between the marker read and the chunk read a writer commits a new set and drops the old one:
        ``reread`` hands the reader the newer marker (READ COMMITTED on PostgreSQL, autocommit reads on SQLite)."""
        old, new = blob(), blob(CHUNK * 3)
        with session(jdb) as s:
            stale = blob_store(s, "bw_jobs_cache:1", old)
            live = blob_store(s, "bw_jobs_cache:1", new)
        assert stale != live
        calls = []

        def reread():
            calls.append(1)
            return live

        with session(jdb) as s:
            assert blob_load(s, "bw_jobs_cache:1", stale, jdb.logger, reread) == new
        assert len(calls) == 1

    def test_reader_gives_up_after_three_attempts(self, jdb, small):
        gone = marker_of(b"gone")
        logger, calls = Mock(), []
        with session(jdb) as s:
            assert blob_load(s, "bw_jobs_cache:1", gone, logger, lambda: calls.append(1) or gone) is None
        assert len(calls) == 3
        logger.error.assert_called_once()


class TestSweep:
    def test_sweep_keeps_live_sets_and_drops_orphans(self, jdb, small):
        assert jdb.upsert_job_cache(None, "a.bin", blob(), job_name="testjob") == ""
        live = chunk_sets(jdb)
        with session(jdb) as s:
            blob_store(s, "bw_jobs_cache:999", blob())  # no such row
            blob_store(s, "bw_plugins:ghost", blob())  # no such plugin
            blob_store(s, "bw_plugin_pages:ghost", blob())
        assert len(chunk_sets(jdb)) == len(live) + 3
        with session(jdb) as s:
            blob_sweep(s)
        assert chunk_sets(jdb) == live

    def test_sweep_drops_a_set_the_owner_no_longer_points_at(self, jdb, small):
        assert jdb.upsert_job_cache(None, "a.bin", blob(), job_name="testjob") == ""
        row = cache_id(jdb, file_name="a.bin")
        with session(jdb) as s:
            blob_store(s, f"bw_jobs_cache:{row}", blob(CHUNK * 2 + 3))  # a set the marker does not name
            # blob_store drops the other sets: re-point the owner at a plain value instead.
        with session(jdb) as s:
            s.execute(update(Jobs_cache).filter_by(id=row).values(data=b"plain"))
        with session(jdb) as s:
            blob_sweep(s)
        assert chunk_count(jdb) == 0

    def test_sweep_is_a_noop_without_chunks(self, jdb):
        with session(jdb) as s:
            blob_sweep(s)
        assert chunk_count(jdb) == 0


# Data that starts with the marker but is not (or not yet) a reference: external list or cache content can be anything.
HEX64 = b"a" * 64
INLINE_LOOKALIKES = {
    "marker-only": BLOB_CHUNK_MARKER,
    "marker-plus-3": BLOB_CHUNK_MARKER + b"abc",
    "marker-plus-non-utf8": BLOB_CHUNK_MARKER + b"\xff\xfe",
    "80-byte-collision": BLOB_CHUNK_MARKER + HEX64,
    "80-byte-non-utf8-suffix": BLOB_CHUNK_MARKER + b"\xff" * 64,
    "80-byte-non-hex-ascii": BLOB_CHUNK_MARKER + b"g" * 64,
    "80-byte-uppercase-hex": BLOB_CHUNK_MARKER + b"A" * 64,
    "longer-than-a-reference": BLOB_CHUNK_MARKER + HEX64 + b"tail",
}
# Not written by the fixed codec: only a legacy row (or the 1.6.16 writer) can hold these inline.
LEGACY_INLINE = {name: value for name, value in INLINE_LOOKALIKES.items() if name != "80-byte-collision"}


class TestMarkerPrefixedData:
    """Data that merely starts with the marker must round trip: a reference is told from data by its exact shape."""

    @pytest.mark.parametrize("data", INLINE_LOOKALIKES.values(), ids=INLINE_LOOKALIKES.keys())
    def test_store_load_and_matches_round_trip(self, jdb, data):
        with session(jdb) as s:
            value = blob_store(s, "bw_jobs_cache:1", data)
        assert len(value) == BLOB_MARKER_LENGTH and value == marker_of(data), "marker-prefixed data must never be stored inline"
        assert chunk_count(jdb) >= 1
        with session(jdb) as s:
            assert blob_load(s, "bw_jobs_cache:1", value, jdb.logger) == data
        assert blob_matches(value, data)
        assert not blob_matches(value, data + b"x")

    @pytest.mark.parametrize("data", INLINE_LOOKALIKES.values(), ids=INLINE_LOOKALIKES.keys())
    def test_job_cache_reader_returns_the_exact_bytes(self, jdb, data):
        assert jdb.upsert_job_cache(None, "a.bin", data, job_name="testjob", checksum="c1") == ""
        assert jdb.get_job_cache_file("testjob", "a.bin") == data
        assert jdb.get_jobs_cache_files(job_name="testjob")[0]["data"] == data

    @pytest.mark.parametrize("data", INLINE_LOOKALIKES.values(), ids=INLINE_LOOKALIKES.keys())
    def test_rewriting_the_same_lookalike_keeps_one_readable_set(self, jdb, data):
        assert jdb.upsert_job_cache(None, "a.bin", data, job_name="testjob", checksum="c1") == ""
        assert jdb.upsert_job_cache(None, "a.bin", data, job_name="testjob", checksum="c2") == ""
        assert len(chunk_sets(jdb)) == 1
        assert jdb.get_job_cache_file("testjob", "a.bin") == data

    def test_a_lookalike_replaced_by_plain_data_leaves_no_chunks(self, jdb):
        assert jdb.upsert_job_cache(None, "a.bin", INLINE_LOOKALIKES["80-byte-collision"], job_name="testjob", checksum="c1") == ""
        assert jdb.upsert_job_cache(None, "a.bin", b"plain", job_name="testjob", checksum="c2") == ""
        assert chunk_count(jdb) == 0
        assert jdb.get_job_cache_file("testjob", "a.bin") == b"plain"

    def test_a_plugin_archive_and_page_that_look_like_a_marker_round_trip(self, db):
        data = INLINE_LOOKALIKES["80-byte-collision"]
        assert db.update_external_plugins([_plugin("lookalike", data, "s1")], _type="external") == ""
        assert next(p for p in db.get_plugins(_type="external", with_data=True) if p["id"] == "lookalike")["data"] == data
        # Unchanged on the next boot: the diff compares the raw column with the incoming bytes.
        before = chunk_sets(db)
        assert db.update_external_plugins([_plugin("lookalike", data, "s1")], _type="external") == ""
        assert chunk_sets(db) == before

    def test_a_well_formed_reference_written_by_1_6_16_still_loads(self, jdb):
        """1.6.16 wrote the same ``BLOB_CHUNK_MARKER`` + 64 hex, with chunks in ``bw_blob_chunks``."""
        data = blob()
        with session(jdb) as s:
            s.add(Blob_chunks(owner="bw_jobs_cache:1", checksum=sha256(data).hexdigest(), idx=0, data=data[:CHUNK]))
            s.add(Blob_chunks(owner="bw_jobs_cache:1", checksum=sha256(data).hexdigest(), idx=1, data=data[CHUNK:]))
        with session(jdb) as s:
            assert blob_load(s, "bw_jobs_cache:1", marker_of(data), jdb.logger) == data
        assert blob_matches(marker_of(data), data)

    def test_an_unwritten_well_formed_reference_is_still_a_reference(self, jdb):
        """The one ambiguity left: an inline value byte-identical to a reference written before this fix."""
        logger = Mock()
        with session(jdb) as s:
            assert blob_load(s, "bw_jobs_cache:1", INLINE_LOOKALIKES["80-byte-collision"], logger) is None
        logger.error.assert_called_once()

    @pytest.mark.parametrize("value", LEGACY_INLINE.values(), ids=LEGACY_INLINE.keys())
    def test_legacy_inline_values_load_unchanged(self, jdb, value):
        logger = Mock()
        with session(jdb) as s:
            assert blob_load(s, "bw_jobs_cache:1", value, logger) == value
        logger.error.assert_not_called()
        assert blob_matches(value, value)
        assert not blob_matches(value, value + b"x")

    @pytest.mark.parametrize("value", LEGACY_INLINE.values(), ids=LEGACY_INLINE.keys())
    def test_legacy_inline_rows_read_back_through_the_database(self, jdb, value):
        add_jobs_cache_row(jdb, file_name="legacy.bin", data=value)
        assert jdb.get_job_cache_file("testjob", "legacy.bin") == value
        assert jdb.get_jobs_cache_files(job_name="testjob")[0]["data"] == value

    @pytest.mark.parametrize("value", LEGACY_INLINE.values(), ids=LEGACY_INLINE.keys())
    def test_sweep_survives_inline_lookalikes_and_keeps_the_live_set(self, jdb, small, value):
        add_jobs_cache_row(jdb, file_name="legacy.bin", data=value)
        assert jdb.upsert_job_cache(None, "live.bin", blob(), job_name="testjob") == ""
        live = chunk_sets(jdb)
        assert len(live) == 1
        with session(jdb) as s:
            blob_sweep(s)
        assert chunk_sets(jdb) == live
        assert jdb.get_job_cache_file("testjob", "legacy.bin") == value

    def test_sweep_does_not_treat_a_lookalike_as_a_live_reference(self, jdb, small):
        """An 80-byte non-hex value names no set: a set stored under that owner is an orphan."""
        add_jobs_cache_row(jdb, file_name="legacy.bin", data=LEGACY_INLINE["80-byte-non-hex-ascii"])
        row = cache_id(jdb, file_name="legacy.bin")
        with session(jdb) as s:
            blob_store(s, f"bw_jobs_cache:{row}", blob())
        with session(jdb) as s:
            blob_sweep(s)
        assert chunk_count(jdb) == 0


class TestJobsCache:
    def test_every_reader_gets_the_original_bytes(self, jdb, small):
        data = blob()
        assert jdb.upsert_job_cache(None, "a.bin", data, job_name="testjob", checksum="c1") == ""
        row = cache_id(jdb, file_name="a.bin")

        assert raw(jdb, Jobs_cache.data, id=row) == marker_of(data)
        assert chunk_count(jdb) == -(-len(data) // CHUNK)
        assert jdb.get_job_cache_file("testjob", "a.bin") == data
        info = jdb.get_job_cache_file("testjob", "a.bin", with_info=True)
        assert info["data"] == data and info["checksum"] == "c1"
        assert jdb.get_job_cache_file("testjob", "a.bin", with_info=True, with_data=False)["checksum"] == "c1"
        assert jdb.get_job_cache_file("testjob", "a.bin", plugin_id="general") == data
        assert jdb.get_jobs_cache_files(job_name="testjob")[0]["data"] == data
        assert jdb.get_jobs_cache_files(job_name="testjob", data_job_name="testjob")[0]["data"] == data

    def test_a_sibling_job_blob_is_not_resolved_for_data_job_name(self, jdb, small):
        """The Codex-modified reader keeps sibling rows' metadata without their blobs: a chunked sibling must stay that way."""
        with session(jdb) as s:
            s.add(Jobs(name="sibling", plugin_id="general", file_name="sibling.py", every="hour", reload=False, run_async=False))
        assert jdb.upsert_job_cache(None, "a.bin", blob(), job_name="testjob") == ""
        assert jdb.upsert_job_cache(None, "b.bin", blob(), job_name="sibling") == ""

        rows = {row["job_name"]: row for row in jdb.get_jobs_cache_files(plugin_id="general", data_job_name="testjob")}

        assert len(rows["testjob"]["data"]) == CHUNK * 5 + 17
        assert "data" not in rows["sibling"]
        assert rows["sibling"]["checksum"] is None

    def test_rewrite_shrinks_the_set_and_unchanged_checksum_keeps_it(self, jdb, small):
        assert jdb.upsert_job_cache(None, "a.bin", blob(CHUNK * 6), job_name="testjob", checksum="c1") == ""
        second = blob(CHUNK * 2 + 5)
        assert jdb.upsert_job_cache(None, "a.bin", second, job_name="testjob", checksum="c2") == ""
        assert chunk_sets(jdb) == [(f"bw_jobs_cache:{cache_id(jdb, file_name='a.bin')}", sha256(second).hexdigest())]
        before = chunk_sets(jdb)
        assert jdb.upsert_job_cache(None, "a.bin", second, job_name="testjob", checksum="c2") == ""
        assert chunk_sets(jdb) == before
        assert jdb.get_job_cache_file("testjob", "a.bin") == second

    def test_a_blob_that_shrinks_to_fit_goes_back_inline(self, jdb, small):
        assert jdb.upsert_job_cache(None, "a.bin", blob(), job_name="testjob", checksum="c1") == ""
        assert jdb.upsert_job_cache(None, "a.bin", b"tiny", job_name="testjob", checksum="c2") == ""
        assert chunk_count(jdb) == 0
        assert jdb.get_job_cache_file("testjob", "a.bin") == b"tiny"

    def test_delete_job_cache_sweeps(self, jdb, small):
        assert jdb.upsert_job_cache(None, "a.bin", blob(), job_name="testjob") == ""
        assert jdb.upsert_job_cache(None, "b.bin", blob(), job_name="testjob") == ""
        assert jdb.delete_job_cache("a.bin", job_name="testjob") == ""
        assert [owner for owner, _ in chunk_sets(jdb)] == [f"bw_jobs_cache:{cache_id(jdb, file_name='b.bin')}"]
        assert jdb.delete_job_cache("b.bin", job_name="testjob") == ""
        assert chunk_count(jdb) == 0

    def test_delete_services_sweeps(self, jdb, small):
        assert jdb.upsert_job_cache("app1.example.com", "a.bin", blob(), job_name="testjob") == ""
        assert jdb.upsert_job_cache(None, "g.bin", blob(), job_name="testjob") == ""
        assert chunk_count(jdb) > 0
        assert jdb.delete_services(["app1.example.com"]) == ""
        assert [owner for owner, _ in chunk_sets(jdb)] == [f"bw_jobs_cache:{cache_id(jdb, file_name='g.bin')}"]

    def test_delete_service_rows_sweeps_for_every_save_config_deletion(self, jdb, small):
        """``delete_service_rows`` is the one choke point under both ``delete_services`` and the ``save_config`` hard delete."""
        assert jdb.upsert_job_cache("app1.example.com", "a.bin", blob(), job_name="testjob") == ""
        with jdb._db_session() as s:
            delete_service_rows(s, ["app1.example.com"])
            s.commit()
        assert chunk_count(jdb) == 0

    def test_save_config_service_deletion_sweeps(self, db, small):
        """The ``save_config`` hard delete reaches ``delete_service_rows`` too: its chunked caches must not outlive the service."""
        seed_multisite(db)
        conf = {k: v for k, v in db.get_non_default_settings(methods=False, with_drafts=True).items() if not k.endswith("IS_DRAFT")}
        with_service = dict(conf, SERVER_NAME=f"{conf['SERVER_NAME']} api.example.com", **{"api.example.com_USE_REVERSE_PROXY": "yes"})
        assert not isinstance(db.save_config(with_service, "api", changed=True), str)
        assert db.upsert_job_cache("api.example.com", "a.bin", blob(), job_name="testjob") == ""
        assert chunk_count(db) > 0

        assert not isinstance(db.save_config(conf, "api", changed=True), str)

        assert chunk_count(db) == 0

    def test_a_service_rename_keeps_the_cache_readable(self, jdb, small):
        """The owner key is the row id, so re-keying ``service_id`` moves nothing."""
        data = blob()
        add_service(jdb, "renamed.example.com")
        assert jdb.upsert_job_cache("app1.example.com", "a.bin", data, job_name="testjob") == ""
        before = chunk_sets(jdb)
        with session(jdb) as s:
            s.execute(update(Jobs_cache).filter_by(file_name="a.bin").values(service_id="renamed.example.com"))
        assert chunk_sets(jdb) == before
        assert jdb.get_job_cache_file("testjob", "a.bin", service_id="renamed.example.com") == data

    def test_a_missing_chunk_reads_as_none_and_logs(self, jdb, small, monkeypatch):
        assert jdb.upsert_job_cache(None, "a.bin", blob(), job_name="testjob") == ""
        with session(jdb) as s:
            s.query(Blob_chunks).filter_by(idx=1).delete()
        logger = Mock()
        monkeypatch.setattr(jdb, "logger", logger)
        assert jdb.get_job_cache_file("testjob", "a.bin") is None
        assert jdb.get_jobs_cache_files(job_name="testjob")[0]["data"] is None
        assert logger.error.called

    def test_a_corrupted_chunk_reads_as_none_and_logs(self, jdb, small, monkeypatch):
        assert jdb.upsert_job_cache(None, "a.bin", blob(), job_name="testjob") == ""
        with session(jdb) as s:
            s.execute(update(Blob_chunks).where(Blob_chunks.idx == 0).values(data=b"corrupted"))
        logger = Mock()
        monkeypatch.setattr(jdb, "logger", logger)
        assert jdb.get_job_cache_file("testjob", "a.bin") is None
        assert logger.error.called


def _plugin(plugin_id, data, checksum, **kw):
    return make_external_plugin(plugin_id, data=data, checksum=checksum, **kw)


class TestPlugins:
    def test_plugin_archive_round_trip_and_icon_reader(self, db, small):
        data = blob()
        assert db.update_external_plugins([_plugin("bigplug", data, "s1")], _type="external") == ""

        assert raw(db, Plugins.data, id="bigplug") == marker_of(data)
        assert chunk_sets(db) == [("bw_plugins:bigplug", sha256(data).hexdigest())]
        assert next(p for p in db.get_plugins(_type="external", with_data=True) if p["id"] == "bigplug")["data"] == data
        assert db.get_plugin_icon("bigplug")[2] == data
        assert "data" not in next(p for p in db.get_plugins(_type="external") if p["id"] == "bigplug")

    def test_update_replaces_the_set_and_a_small_archive_goes_inline(self, db, small):
        first, second = blob(), blob(CHUNK * 2 + 9)
        assert db.update_external_plugins([_plugin("bigplug", first, "s1")], _type="external") == ""
        assert db.update_external_plugins([_plugin("bigplug", second, "s2")], _type="external") == ""
        assert chunk_sets(db) == [("bw_plugins:bigplug", sha256(second).hexdigest())]
        assert db.update_external_plugins([_plugin("bigplug", b"fake-tar", "s3")], _type="external") == ""
        assert chunk_count(db) == 0
        assert db.get_plugin_icon("bigplug")[2] == b"fake-tar"

    def test_unchanged_archive_is_not_rewritten(self, db, small):
        data = blob()
        assert db.update_external_plugins([_plugin("bigplug", data, "s1")], _type="external") == ""
        before = chunk_sets(db)
        assert db.update_external_plugins([_plugin("bigplug", data, "s1")], _type="external") == ""
        assert chunk_sets(db) == before

    def _with_page(self, db, monkeypatch, tmp_path, plugin_id, page_bytes):
        ui = tmp_path / plugin_id / "ui"
        ui.mkdir(parents=True, exist_ok=True)
        (ui / "page.bin").write_bytes(page_bytes)
        monkeypatch.setattr(db, "_uep_resolve_plugin_dir", lambda *_: tmp_path / plugin_id)
        return ui

    def test_plugin_page_round_trip_insert_update_and_removal(self, db, small, monkeypatch, tmp_path):
        ui = self._with_page(db, monkeypatch, tmp_path, "pageplug", blob(CHUNK * 4))
        plugin = _plugin("pageplug", b"fake-tar", "s1")
        plugin["page"] = True
        assert db.update_external_plugins([plugin], _type="external") == ""

        page = db.get_plugin_page("pageplug")
        assert page is not None and len(page) > CHUNK
        assert sha256(page).hexdigest() == raw(db, Plugin_pages.checksum, plugin_id="pageplug")
        assert raw(db, Plugin_pages.data, plugin_id="pageplug") == marker_of(page)
        assert chunk_sets(db) == [("bw_plugin_pages:pageplug", sha256(page).hexdigest())]

        (ui / "page.bin").write_bytes(blob(CHUNK * 2))
        assert db.update_external_plugins([_plugin("pageplug", b"fake-tar", "s1") | {"page": True}], _type="external") == ""
        updated = db.get_plugin_page("pageplug")
        assert updated != page
        assert chunk_sets(db) == [("bw_plugin_pages:pageplug", sha256(updated).hexdigest())]

        for path in ui.iterdir():
            path.unlink()
        ui.rmdir()
        assert db.update_external_plugins([_plugin("pageplug", b"fake-tar", "s1")], _type="external") == ""
        assert db.get_plugin_page("pageplug") is None
        assert chunk_count(db) == 0

    def _populated(self, db, monkeypatch, tmp_path, plugin_id="gone"):
        """A plugin whose archive, page and job cache are all chunked."""
        seed_minimal(db)
        self._with_page(db, monkeypatch, tmp_path, plugin_id, blob(CHUNK * 3))
        plugin = _plugin(plugin_id, blob(), "s1")
        plugin["page"] = True
        plugin["jobs"] = [{"name": f"{plugin_id}-job", "file": "job.py", "every": "hour", "reload": False}]
        assert db.update_external_plugins([plugin], _type="external") == ""
        assert db.upsert_job_cache(None, "c.bin", blob(), job_name=f"{plugin_id}-job") == ""
        assert {owner.split(":")[0] for owner, _ in chunk_sets(db)} == {"bw_plugins", "bw_plugin_pages", "bw_jobs_cache"}

    def test_delete_plugin_sweeps_archive_page_and_job_cache(self, db, small, monkeypatch, tmp_path):
        self._populated(db, monkeypatch, tmp_path)
        assert db.delete_plugin("gone", "manual") == ""
        assert chunk_count(db) == 0

    def test_delete_missing_sweeps_archive_page_and_job_cache(self, db, small, monkeypatch, tmp_path):
        self._populated(db, monkeypatch, tmp_path)
        assert db.update_external_plugins([_plugin("keeper", b"fake-tar", "k1")], _type="external", delete_missing=True) == ""
        assert chunk_count(db) == 0
        assert {p["id"] for p in db.get_plugins(_type="external")} == {"keeper"}

    def test_delete_missing_sweeps_without_per_plugin_commit(self, db, small, monkeypatch, tmp_path):
        self._populated(db, monkeypatch, tmp_path)
        assert db.update_external_plugins([_plugin("keeper", b"fake-tar", "k1")], _type="external", delete_missing=True, per_plugin_commit=False) == ""
        assert chunk_count(db) == 0

    def test_only_clear_metadata_sweeps_the_archive_and_the_page(self, db, small, monkeypatch, tmp_path):
        self._populated(db, monkeypatch, tmp_path)
        assert db.update_external_plugins([], _type="external", delete_missing=True, only_clear_metadata=True) == ""
        assert raw(db, Plugins.data, id="gone") is None
        assert {owner.split(":")[0] for owner, _ in chunk_sets(db)} == {"bw_jobs_cache"}  # job caches are preserved on purpose

    def test_removed_job_sweeps_its_cache(self, db, small, monkeypatch, tmp_path):
        self._populated(db, monkeypatch, tmp_path)
        plugin = _plugin("gone", blob(), "s1")
        plugin["jobs"] = []
        plugin["page"] = True
        # the same archive: only the job disappears
        assert db.update_external_plugins([plugin | {"data": db.get_plugin_icon("gone")[2]}], _type="external") == ""
        assert "bw_jobs_cache" not in {owner.split(":")[0] for owner, _ in chunk_sets(db)}


def _external_manual(plugin_id, data, checksum="c1"):
    plugin = make_core_plugin(plugin_id)
    plugin.update({"type": "external", "method": "manual", "data": data, "checksum": checksum})
    return plugin


class TestInitTables:
    def test_unchanged_archive_is_not_rewritten_on_every_boot(self, db, small):
        data = blob()
        assert db.init_tables([_external_manual("extp", data)]) == (True, "")
        assert raw(db, Plugins.data, id="extp") == marker_of(data)
        before = chunk_sets(db)
        assert before == [("bw_plugins:extp", sha256(data).hexdigest())]

        assert db.init_tables([_external_manual("extp", data)]) == (False, "")

        assert chunk_sets(db) == before
        assert next(p for p in db.get_plugins(with_data=True) if p["id"] == "extp")["data"] == data

    def test_a_changed_archive_replaces_the_set(self, db, small):
        assert db.init_tables([_external_manual("extp", blob(), "c1")]) == (True, "")
        new = blob(CHUNK * 2 + 1)
        assert db.init_tables([_external_manual("extp", new, "c2")]) == (True, "")
        assert chunk_sets(db) == [("bw_plugins:extp", sha256(new).hexdigest())]
        assert next(p for p in db.get_plugins(with_data=True) if p["id"] == "extp")["data"] == new

    def test_a_removed_plugin_sweeps_its_archive(self, db, small):
        assert db.init_tables([make_core_plugin("alpha"), _external_manual("extp", blob())]) == (True, "")
        assert chunk_count(db) > 0
        assert db.init_tables([make_core_plugin("alpha")]) == (True, "")
        assert chunk_count(db) == 0

    def _inject_page(self, db, monkeypatch, plugin_id, data):
        original = db._it_build_desired_plugins

        def build(*args, **kwargs):
            desired = original(*args, **kwargs)
            desired["plugin_pages"][plugin_id] = {"data": data, "checksum": sha256(data).hexdigest()}
            return desired

        monkeypatch.setattr(db, "_it_build_desired_plugins", build)

    def test_plugin_pages_chunk_update_and_sweep(self, db, small, monkeypatch):
        page = blob()
        self._inject_page(db, monkeypatch, "extp", page)
        assert db.init_tables([_external_manual("extp", b"fake-tar")]) == (True, "")
        assert chunk_sets(db) == [("bw_plugin_pages:extp", sha256(page).hexdigest())]
        assert db.get_plugin_page("extp") == page

        assert db.init_tables([_external_manual("extp", b"fake-tar")]) == (False, "")  # unchanged: no rewrite

        newer = blob(CHUNK * 2 + 3)
        self._inject_page(db, monkeypatch, "extp", newer)
        assert db.init_tables([_external_manual("extp", b"fake-tar")]) == (True, "")
        assert chunk_sets(db) == [("bw_plugin_pages:extp", sha256(newer).hexdigest())]
        assert db.get_plugin_page("extp") == newer

        monkeypatch.undo()
        monkeypatch.setattr(blobs, "blob_chunk_size", lambda _session: CHUNK)
        assert db.init_tables([_external_manual("extp", b"fake-tar")]) == (True, "")  # the page vanished from disk
        assert chunk_count(db) == 0


class TestChunkingInProduction:
    def test_only_mysql_family_chunks_with_the_real_packet_size(self, jdb):
        data = urandom(5 * 1024 * 1024)  # above the 4 MiB cap, below any default packet size
        assert jdb.upsert_job_cache(None, "big.bin", data, job_name="testjob") == ""
        stored = raw(jdb, Jobs_cache.data, file_name="big.bin")
        if jdb.sql_engine.dialect.name in ("mysql", "mariadb"):
            assert stored == marker_of(data)
            assert chunk_count(jdb) == 2
        else:
            assert stored == data
            assert chunk_count(jdb) == 0
        assert jdb.get_job_cache_file("testjob", "big.bin") == data


# --- concurrency (Q6): real parallel connections, PostgreSQL and MariaDB only -------------------
@pytest.fixture
def cdb(db, small):
    if db.sql_engine.dialect.name == "sqlite":
        pytest.skip("SQLite serialises writers: the interleavings below cannot happen")
    seed_minimal(db)
    return db


def _run(*targets, timeout=120):
    """Run every target in its own thread, return the exceptions they raised."""
    errors = []

    def wrap(target):
        def go():
            try:
                target()
            except BaseException as e:  # noqa: BLE001 -- collected, asserted empty by the caller
                errors.append(e)

        return go

    threads = [threading.Thread(target=wrap(t)) for t in targets]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout)
    assert not any(thread.is_alive() for thread in threads), "a worker is stuck: deadlock?"
    return errors


class TestConcurrency:
    def test_a_reader_never_sees_a_torn_blob_while_a_writer_swaps_sets(self, cdb):
        first, second = blob(CHUNK * 6), blob(CHUNK * 4 + 5)
        assert cdb.upsert_job_cache(None, "a.bin", first, job_name="testjob", checksum="0") == ""
        stop, seen, failures = threading.Event(), [], []

        def writer():
            for i in range(25):
                err = cdb.upsert_job_cache(None, "a.bin", (second, first)[i % 2], job_name="testjob", checksum=f"w{i}")
                if err:
                    failures.append(err)
                time.sleep(0.01)
            stop.set()

        def reader():
            while not stop.is_set():
                seen.append(cdb.get_job_cache_file("testjob", "a.bin"))

        errors = _run(writer, reader, reader)

        assert not errors and not failures
        assert seen and all(value in (first, second) for value in seen), "a reader got None or a mixed blob"
        assert len(chunk_sets(cdb)) == 1

    def test_a_sweep_never_deletes_a_set_committed_while_it_runs(self, cdb):
        payloads = [blob(CHUNK * 3 + i) for i in range(20)]
        failures, stop = [], threading.Event()

        def uploader():
            for i, data in enumerate(payloads):
                err = cdb.upsert_job_cache(None, f"f{i}.bin", data, job_name="testjob", checksum=f"u{i}")
                if err:
                    failures.append(err)
            stop.set()

        def sweeper():
            while not stop.is_set():
                with cdb._db_session() as s:
                    blob_sweep(s)
                    s.commit()

        errors = _run(uploader, sweeper, sweeper)

        assert not errors and not failures
        assert [cdb.get_job_cache_file("testjob", f"f{i}.bin") for i in range(20)] == payloads

    def test_concurrent_upserts_on_adjacent_owners_do_not_deadlock_or_fail(self, cdb):
        """MariaDB error 1020 came from a ranged DELETE next-key-locking a neighbouring owner's chunk rows."""
        for i in range(4):
            assert cdb.upsert_job_cache(None, f"n{i}.bin", blob(CHUNK * 4), job_name="testjob", checksum="seed") == ""
        failures = []

        def worker(n):
            def go():
                for i in range(15):
                    err = cdb.upsert_job_cache(None, f"n{n}.bin", blob(CHUNK * 3 + i), job_name="testjob", checksum=f"{n}-{i}")
                    if err:
                        failures.append(err)

            return go

        errors = _run(*(worker(n) for n in range(4)))

        assert not errors and not failures, failures
        assert len(chunk_sets(cdb)) == 4

    def test_concurrent_writers_of_the_same_set_leave_one_consistent_set(self, cdb):
        """Two transactions storing the identical set for one owner: the loser may be refused (a duplicate key on
        PostgreSQL, error 1020 on MariaDB, the same refusal the owner row's own UPDATE already gets), but nothing
        deadlocks, nothing is torn and exactly one readable set remains."""
        data = blob(CHUNK * 5)
        outcomes = []

        def writer(delay):
            def go():
                time.sleep(delay)
                with cdb._db_session() as s:
                    try:
                        blob_store(s, "bw_jobs_cache:77", data)
                        time.sleep(0.5)
                        s.commit()
                        outcomes.append("committed")
                    except (IntegrityError, OperationalError):
                        s.rollback()
                        outcomes.append("refused")

            return go

        errors = _run(writer(0), writer(0.1))

        assert not errors
        assert "committed" in outcomes and len(outcomes) == 2
        assert chunk_sets(cdb) == [("bw_jobs_cache:77", sha256(data).hexdigest())]
        with session(cdb) as s:
            assert blob_load(s, "bw_jobs_cache:77", marker_of(data), cdb.logger) == data


# --- #3965 itself: a real MariaDB whose max_allowed_packet cannot carry the blob -------------------
def _docker_ok():
    return which("docker") is not None and run(["docker", "info"], stdout=DEVNULL, stderr=DEVNULL).returncode == 0


@pytest.fixture(scope="module")
def small_packet_uri():
    """A throwaway MariaDB started with an explicit 1 MiB ``max_allowed_packet`` (unique name, removed afterwards)."""
    if not _docker_ok():
        pytest.skip("docker is not available")
    name = f"bw-l4a-packet-{uuid4().hex[:10]}"
    started = run(
        ["docker", "run", "-d", "--name", name, "-p", "127.0.0.1::3306"]
        + ["-e", "MARIADB_USER=bw", "-e", "MARIADB_PASSWORD=bw", "-e", "MARIADB_DATABASE=bw_test", "-e", "MARIADB_ROOT_PASSWORD=root"]
        + ["mariadb:11", "--max-allowed-packet=1048576"],
        stdout=PIPE,
        stderr=PIPE,
        text=True,
    )
    if started.returncode != 0:
        pytest.skip(f"cannot start the throwaway MariaDB: {started.stderr.strip()}")
    try:
        port = run(["docker", "port", name, "3306/tcp"], stdout=PIPE, text=True, check=True).stdout.strip().splitlines()[0].rsplit(":", 1)[1]
        uri = f"mariadb://bw:bw@127.0.0.1:{port}/bw_test"
        from fixtures.engines import _with_driver  # type: ignore
        from sqlalchemy import create_engine, text

        deadline = time.time() + 90
        while True:
            try:
                engine = create_engine(_with_driver(uri))
                with engine.connect() as conn:
                    assert conn.execute(text("SELECT @@max_allowed_packet")).scalar() == 1048576
                engine.dispose()
                break
            except Exception:  # noqa: BLE001 -- the server is still starting
                if time.time() > deadline:
                    raise
                time.sleep(1)
        yield uri
    finally:
        run(["docker", "rm", "-f", name], stdout=DEVNULL, stderr=DEVNULL)


@pytest.fixture
def pdb(small_packet_uri, quiet_logger, _clean_env):
    from fixtures.engines import reset_schema  # type: ignore

    reset_schema(small_packet_uri)
    from Database import Database  # type: ignore

    database = Database(quiet_logger, sqlalchemy_string=small_packet_uri, log=False)
    try:
        seed_minimal(database)
        yield database
    finally:
        database.close()


class TestSmallMaxAllowedPacket:
    SIZE = 20 * 1024 * 1024

    def test_a_20_mib_job_cache_is_stored_and_read_back(self, pdb):
        data = urandom(self.SIZE)
        assert pdb.upsert_job_cache(None, "big.bin", data, job_name="testjob") == ""
        assert pdb.get_job_cache_file("testjob", "big.bin") == data
        assert raw(pdb, Jobs_cache.data, file_name="big.bin") == marker_of(data)
        assert chunk_count(pdb) == -(-self.SIZE // chunk_size_for("mariadb", 1048576))

    def test_a_20_mib_plugin_archive_and_page_are_stored_and_read_back(self, pdb, monkeypatch, tmp_path):
        data = urandom(self.SIZE)
        ui = tmp_path / "bigplug" / "ui"
        ui.mkdir(parents=True)
        (ui / "page.bin").write_bytes(urandom(self.SIZE))
        monkeypatch.setattr(pdb, "_uep_resolve_plugin_dir", lambda *_: tmp_path / "bigplug")
        plugin = make_external_plugin("bigplug", data=data, checksum="s1")
        plugin["page"] = True

        assert pdb.update_external_plugins([plugin], _type="external") == ""

        assert pdb.get_plugin_icon("bigplug")[2] == data
        assert next(p for p in pdb.get_plugins(_type="external", with_data=True) if p["id"] == "bigplug")["data"] == data
        page = pdb.get_plugin_page("bigplug")
        assert page is not None and len(page) > self.SIZE
        assert pdb.delete_plugin("bigplug", "manual") == ""
        assert chunk_count(pdb) == 0

    def test_init_tables_stores_a_20_mib_archive(self, pdb):
        data = urandom(self.SIZE)
        assert pdb.init_tables([_external_manual("extp", data)]) == (True, "")
        assert next(p for p in pdb.get_plugins(with_data=True) if p["id"] == "extp")["data"] == data
        assert pdb.init_tables([_external_manual("extp", data)]) == (False, "")


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
