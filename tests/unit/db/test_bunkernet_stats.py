"""DatabaseBunkernetMixin — BunkerNet effectiveness stats (bw_bunkernet_stats).

Exercises the bunkernet pilot end-to-end through the generic plugin DB-extension
mechanism: register the plugin model, create its table, bind ``db.ext("bunkernet")``,
and verify upsert/effectiveness/retention. The plugin lives under the repo's core
dir, injected via the explicit ``paths`` arg (discovery roots are hardcoded).
"""

import logging
from datetime import datetime, timezone
from pathlib import Path

import pytest

import plugin_extensions as pe
from model import Base  # type: ignore

REPO_CORE = Path(__file__).resolve().parents[3] / "src" / "common" / "core"
_PATHS = [(REPO_CORE, "core")]

LOGGER = logging.getLogger("bw-unit-test-bunkernet")
LOGGER.addHandler(logging.NullHandler())


@pytest.fixture
def bdb(db):
    """The ``db`` fixture with the bunkernet plugin model registered + table created
    and ``db.ext('bunkernet')`` primed."""
    pe.register_plugin_models(LOGGER, db=db, paths=_PATHS)
    Base.metadata.create_all(db.sql_engine, checkfirst=True)
    db._ext_mixins = pe.discover_db_methods(LOGGER, db=db, paths=_PATHS)
    return db


def _now_epoch() -> int:
    return int(datetime.now(tz=timezone.utc).timestamp())


def _report(request_id, *, reason, date):
    return {
        "id": request_id,
        "date": date,
        "ip": "9.9.9.9",
        "country": "US",
        "method": "GET",
        "url": "/",
        "status": 403,
        "user_agent": "curl/8",
        "reason": reason,
        "server_name": "app.example.com",
        "data": "",
        "security_mode": "block",
    }


class TestExtAccessor:
    def test_ext_returns_bound_methods(self, bdb):
        ext = bdb.ext("bunkernet")
        # query methods come from the plugin mixin; shared members resolve to the live db
        assert hasattr(ext, "upsert_stats")
        assert ext.readonly is bdb.readonly

    def test_unknown_plugin_raises(self, bdb):
        with pytest.raises(KeyError):
            bdb.ext("does-not-exist")


class TestUpsert:
    def test_insert_and_read_back(self, bdb):
        rows = [
            {"metric": "blocklist_size", "value": 1500},
            {"metric": "reports_pending", "value": 7},
            {"metric": "registered", "value": 1},
        ]
        assert bdb.ext("bunkernet").upsert_stats(rows) == ""
        stats = bdb.ext("bunkernet").get_stats()
        assert {s["metric"]: s["value"] for s in stats} == {"blocklist_size": 1500, "reports_pending": 7, "registered": 1}

    def test_empty_is_noop(self, bdb):
        assert bdb.ext("bunkernet").upsert_stats([]) == ""
        assert bdb.ext("bunkernet").get_stats() == []

    def test_same_bucket_metric_overwrites(self, bdb):
        bucket = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        assert bdb.ext("bunkernet").upsert_stats([{"metric": "blocklist_size", "value": 10}], bucket=bucket) == ""
        assert bdb.ext("bunkernet").upsert_stats([{"metric": "blocklist_size", "value": 42}], bucket=bucket) == ""
        stats = bdb.ext("bunkernet").get_stats(metric="blocklist_size")
        assert len(stats) == 1
        assert stats[0]["value"] == 42

    def test_per_instance_rows_kept_separate(self, bdb):
        bucket = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        rows = [
            {"metric": "connected", "value": 1, "instance_hostname": "bw-1"},
            {"metric": "connected", "value": 0, "instance_hostname": "bw-2"},
        ]
        assert bdb.ext("bunkernet").upsert_stats(rows, bucket=bucket) == ""
        stats = bdb.ext("bunkernet").get_stats(metric="connected")
        assert {s["instance_hostname"]: s["value"] for s in stats} == {"bw-1": 1, "bw-2": 0}


class TestEffectiveness:
    def test_joins_blocks_and_contribution(self, bdb):
        now = _now_epoch()
        # blocks side: two requests blocked by BunkerNet intel land in bw_metrics_requests
        assert (
            bdb.batch_upsert_metrics_requests(
                [_report("b1", reason="bunkernet", date=now), _report("b2", reason="bunkernet", date=now)], instance_hostname="bw-1"
            )
            == ""
        )
        # a non-bunkernet block must not be counted
        assert bdb.batch_upsert_metrics_requests([_report("o1", reason="blacklist", date=now)], instance_hostname="bw-1") == ""
        # contribution side
        assert bdb.ext("bunkernet").upsert_stats([{"metric": "reports_pending", "value": 5}, {"metric": "blocklist_size", "value": 900}]) == ""

        eff = bdb.ext("bunkernet").get_effectiveness()
        assert eff["blocked_by_intel"] == 2
        assert eff["reports_pending"] == 5
        assert eff["blocklist_size"] == 900
        assert isinstance(eff["connected"], dict)

    def test_connected_map(self, bdb):
        bucket = datetime.now(tz=timezone.utc)
        assert (
            bdb.ext("bunkernet").upsert_stats(
                [{"metric": "connected", "value": 1, "instance_hostname": "bw-1"}, {"metric": "connected", "value": 0, "instance_hostname": "bw-2"}],
                bucket=bucket,
            )
            == ""
        )
        eff = bdb.ext("bunkernet").get_effectiveness()
        assert eff["connected"] == {"bw-1": True, "bw-2": False}


class TestRetention:
    def test_cleanup_by_age(self, bdb):
        old = datetime(2000, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        recent = datetime.now(tz=timezone.utc)
        assert bdb.ext("bunkernet").upsert_stats([{"metric": "blocklist_size", "value": 1}], bucket=old) == ""
        assert bdb.ext("bunkernet").upsert_stats([{"metric": "reports_pending", "value": 2}], bucket=recent) == ""
        msg = bdb.ext("bunkernet").cleanup_bunkernet_by_age(30)
        assert "Removed 1 bunkernet stats by age" == msg
        remaining = {s["metric"] for s in bdb.ext("bunkernet").get_stats()}
        assert remaining == {"reports_pending"}
