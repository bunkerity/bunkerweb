"""`record_reload_outcome` — the failover banner as a per-host state, updated atomically.

The flag used to be one blind overwrite per reload, so a manual reload that succeeded on one host
erased another host's refusal, and two reloads finishing together lost whichever wrote first. The
state is now a map `{host: refusal message}` stored in `bw_metadata.failover_message`, and every
update is a read-modify-write under the metadata row lock.

Runs against every selected engine via the ``db`` fixture.
"""

import threading

import pytest

from reload_outcome import LEGACY_HOST, parse_failover_message, render_failover_message

REFUSED_A = 'nginx: [emerg] unknown directive "bogus" in /etc/nginx/a.conf:3\nnginx: configuration file test failed'
REFUSED_B = 'nginx: [emerg] host not found in upstream "backend" in /etc/nginx/b.conf:9'
LEGACY = "bw-1 - nginx: [emerg] bad directive\nin /etc/nginx/a.conf:3\nbw-2 - nginx: [emerg] other\nin /etc/nginx/b.conf:7"


@pytest.fixture
def mdb(db):
    db.initialize_db("1.7.0", "Docker")
    return db


def _state(db):
    md = db.get_metadata()
    return md["failover"], parse_failover_message(md["failover_message"]) if md["failover_message"] else {}


class TestPerHostState:
    def test_a_refusal_raises_the_flag_with_the_hosts_message(self, mdb):
        assert mdb.record_reload_outcome({"bw-1": REFUSED_A}) == ""
        assert _state(mdb) == (True, {"bw-1": REFUSED_A})

    def test_sequential_recovery_clears_only_the_host_that_recovered(self, mdb):
        """A and B refused; A succeeds -> only B remains and the flag stays up; B succeeds -> cleared."""
        mdb.record_reload_outcome({"bw-1": REFUSED_A, "bw-2": REFUSED_B})
        assert _state(mdb) == (True, {"bw-1": REFUSED_A, "bw-2": REFUSED_B})

        mdb.record_reload_outcome({"bw-1": None})
        assert _state(mdb) == (True, {"bw-2": REFUSED_B})

        mdb.record_reload_outcome({"bw-2": None})
        md = mdb.get_metadata()
        assert md["failover"] is False
        assert md["failover_message"] == ""

    def test_a_fleet_reload_with_one_host_unreachable_keeps_that_hosts_entry(self, mdb):
        mdb.record_reload_outcome({"bw-1": REFUSED_A, "bw-2": REFUSED_B})
        # bw-2 did not answer this time, so it is absent from the results.
        mdb.record_reload_outcome({"bw-1": None}, fleet=True)
        assert _state(mdb) == (True, {"bw-2": REFUSED_B})

    def test_a_new_refusal_replaces_the_hosts_older_one(self, mdb):
        mdb.record_reload_outcome({"bw-1": REFUSED_A})
        mdb.record_reload_outcome({"bw-1": REFUSED_B})
        assert _state(mdb) == (True, {"bw-1": REFUSED_B})

    def test_a_success_for_a_host_with_no_entry_changes_nothing(self, mdb):
        mdb.record_reload_outcome({"bw-1": REFUSED_A})
        stored = mdb.get_metadata()["failover_message"]
        mdb.record_reload_outcome({"bw-9": None})
        assert mdb.get_metadata()["failover_message"] == stored

    def test_multi_line_messages_survive_the_database_round_trip(self, mdb):
        mdb.record_reload_outcome({"bw-1": REFUSED_A, "bw-2": "first\n  indented\n\nafter blank\nbw-1 - not a block"})
        mdb.record_reload_outcome({"bw-3": REFUSED_B})
        mdb.record_reload_outcome({"bw-2": None})
        assert _state(mdb) == (True, {"bw-1": REFUSED_A, "bw-3": REFUSED_B})

    def test_a_message_quoting_another_hosts_prefix_never_forges_that_host(self, mdb):
        mdb.record_reload_outcome({"bw-1": "nginx failed\nbw-2 - not really bw-2"})
        mdb.record_reload_outcome({"bw-2": None})
        assert _state(mdb) == (True, {"bw-1": "nginx failed\nbw-2 - not really bw-2"})

    def test_a_stale_message_under_a_cleared_flag_is_not_resurrected(self, mdb):
        mdb.set_metadata({"failover": False, "failover_message": "bw-7 - left over"})
        mdb.record_reload_outcome({"bw-1": REFUSED_A})
        assert _state(mdb) == (True, {"bw-1": REFUSED_A})

    def test_nothing_answered_is_a_no_op(self, mdb):
        mdb.record_reload_outcome({"bw-1": REFUSED_A})
        before = mdb.get_metadata()["failover_message"]
        assert mdb.record_reload_outcome({}) == ""
        assert mdb.get_metadata()["failover_message"] == before

    def test_the_metadata_row_must_exist(self, db):
        assert db.record_reload_outcome({"bw-1": None}) == "The metadata are not set yet, try again"

    def test_a_read_only_database_is_reported_not_written(self, mdb):
        mdb.record_reload_outcome({"bw-1": REFUSED_A})
        mdb.readonly = True
        try:
            assert "read-only" in mdb.record_reload_outcome({"bw-1": None})
        finally:
            mdb.readonly = False
        assert _state(mdb) == (True, {"bw-1": REFUSED_A})


class TestFleetReloadAndKnownInstances:
    @pytest.fixture
    def fleet(self, mdb):
        for name in ("bw-1", "bw-2"):
            assert mdb.add_instance(name, 5000, "bwapi", "manual") == ""
        return mdb

    def test_an_entry_for_an_instance_that_no_longer_exists_does_not_pin_the_banner(self, fleet):
        """Nothing will ever report on a deleted instance again: a fleet reload that every remaining
        instance accepted must clear its refusal, as the old overwrite did."""
        fleet.record_reload_outcome({"bw-gone": REFUSED_A, "bw-1": REFUSED_B})
        fleet.record_reload_outcome({"bw-1": None, "bw-2": None}, fleet=True)
        md = fleet.get_metadata()
        assert md["failover"] is False and md["failover_message"] == ""

    def test_a_per_host_success_never_prunes_unknown_hosts(self, fleet):
        fleet.record_reload_outcome({"bw-gone": REFUSED_A})
        fleet.record_reload_outcome({"bw-1": None})
        assert _state(fleet) == (True, {"bw-gone": REFUSED_A})

    def test_host_names_compare_case_insensitively_with_the_instance_rows(self, fleet):
        fleet.record_reload_outcome({"bw-1": REFUSED_A})
        fleet.record_reload_outcome({"BW-1": None, "bw-2": None}, fleet=True)
        assert fleet.get_metadata()["failover"] is False


class TestLegacyMessage:
    """Rows from 1.6.x and from the old push-configs hold unindented multi-line `host - msg` text.
    It must never be lost nor split into guessed hosts."""

    @pytest.fixture
    def legacy(self, mdb):
        for name in ("bw-1", "bw-2"):
            assert mdb.add_instance(name, 5000, "bwapi", "manual") == ""
        assert mdb.set_metadata({"failover": True, "failover_message": LEGACY}) == ""
        return mdb

    def test_a_per_host_success_leaves_the_legacy_text_untouched(self, legacy):
        legacy.record_reload_outcome({"bw-1": None})
        md = legacy.get_metadata()
        assert md["failover"] is True
        assert md["failover_message"] == LEGACY

    def test_a_fleet_success_where_one_instance_did_not_answer_keeps_it(self, legacy):
        legacy.record_reload_outcome({"bw-1": None}, fleet=True)
        assert legacy.get_metadata()["failover_message"] == LEGACY

    def test_a_fleet_refusal_keeps_it_next_to_the_new_entry(self, legacy):
        legacy.record_reload_outcome({"bw-1": None, "bw-2": REFUSED_B}, fleet=True)
        md = legacy.get_metadata()
        assert md["failover"] is True
        assert _state(legacy)[1] == {LEGACY_HOST: LEGACY, "bw-2": REFUSED_B}

    def test_a_per_host_success_removes_a_new_entry_but_never_the_legacy_one(self, legacy):
        legacy.record_reload_outcome({"bw-2": REFUSED_B})
        legacy.record_reload_outcome({"bw-2": None})
        assert _state(legacy) == (True, {LEGACY_HOST: LEGACY})

    def test_only_a_fleet_wide_reload_every_instance_accepted_removes_it(self, legacy):
        """The sequence from the plan review: legacy text, a per-host success, then a fleet success."""
        legacy.record_reload_outcome({"bw-1": None})
        assert legacy.get_metadata()["failover_message"] == LEGACY

        legacy.record_reload_outcome({"bw-1": None, "bw-2": None}, fleet=True)
        md = legacy.get_metadata()
        assert md["failover"] is False
        assert md["failover_message"] == ""

    def test_free_text_written_by_someone_else_is_legacy_too(self, mdb):
        mdb.add_instance("bw-1", 5000, "bwapi", "manual")
        mdb.set_metadata({"failover": True, "failover_message": "something an operator wrote"})
        mdb.record_reload_outcome({"bw-1": None})
        assert mdb.get_metadata()["failover_message"] == "something an operator wrote"
        mdb.record_reload_outcome({"bw-1": None}, fleet=True)
        assert mdb.get_metadata()["failover"] is False


class TestConcurrency:
    def _second_connection(self, db):
        from Database import Database

        return Database(db.logger, sqlalchemy_string=db.database_uri, log=False)

    def test_a_success_and_a_refusal_landing_together_both_survive(self, mdb, monkeypatch):
        """Deterministic interleaving. The first writer is held between its read and its write; the
        second starts meanwhile. Without the row lock taken BEFORE the read, the second reads the old
        state and the first writer's update is overwritten (a lost refusal on one side, a resurrected
        one on the other)."""
        import db_methods.metadata as metadata_module

        mdb.record_reload_outcome({"bw-1": REFUSED_A})
        other = self._second_connection(mdb)
        entered, finish = threading.Event(), threading.Event()
        real_parse = metadata_module.parse_failover_message
        slow_thread = {}

        def parse(text):
            result = real_parse(text)
            if threading.current_thread().name == slow_thread["name"]:
                entered.set()
                finish.wait(10)
            return result

        monkeypatch.setattr(metadata_module, "parse_failover_message", parse)
        errors = []

        def slow():  # bw-1 recovers, held mid-transaction
            try:
                errors.append(mdb.record_reload_outcome({"bw-1": None}))
            except BaseException as exc:  # noqa: BLE001
                errors.append(repr(exc))

        def quick():  # bw-2 is refused while the first is in flight
            try:
                errors.append(other.record_reload_outcome({"bw-2": REFUSED_B}))
            except BaseException as exc:  # noqa: BLE001
                errors.append(repr(exc))

        first = threading.Thread(target=slow, name="slow-writer")
        slow_thread["name"] = first.name
        second = threading.Thread(target=quick, name="quick-writer")
        try:
            first.start()
            assert entered.wait(10), "the first writer never reached its read"
            second.start()
            # Give the second writer every chance to read the stale state if nothing stops it.
            second.join(1.0)
            finish.set()
            first.join(20)
            second.join(20)
        finally:
            finish.set()
            other.close()

        assert errors == ["", ""], errors
        assert _state(mdb) == (True, {"bw-2": REFUSED_B}), "an update was lost: the two writers did not serialise"

    def test_many_racing_pairs_always_end_with_exactly_the_refused_host(self, mdb):
        other = self._second_connection(mdb)
        try:
            for round_number in range(15):
                mdb.set_metadata({"failover": False, "failover_message": ""})
                mdb.record_reload_outcome({"bw-1": REFUSED_A})
                barrier = threading.Barrier(2)
                results = []

                def recover():
                    barrier.wait(10)
                    results.append(mdb.record_reload_outcome({"bw-1": None}))

                def refuse():
                    barrier.wait(10)
                    results.append(other.record_reload_outcome({"bw-2": REFUSED_B}))

                threads = [threading.Thread(target=recover), threading.Thread(target=refuse)]
                for thread in threads:
                    thread.start()
                for thread in threads:
                    thread.join(30)
                assert results == ["", ""], (round_number, results)
                assert _state(mdb) == (True, {"bw-2": REFUSED_B}), f"round {round_number}: lost update"
        finally:
            other.close()


def test_the_stored_text_is_what_the_renderer_produces(mdb):
    mdb.record_reload_outcome({"bw-2": "b\nb2", "bw-1": "a"})
    assert mdb.get_metadata()["failover_message"] == render_failover_message({"bw-1": "a", "bw-2": "b\nb2"})
