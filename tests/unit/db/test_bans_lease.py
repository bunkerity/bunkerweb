"""CrowdSec ban leases in ``bw_bans`` (wave 25, lane X1A).

A lease is an ordinary ban with ``reason == "crowdsec"`` and ``reason_data.lease`` true; the instance
renews it every ``CROWDSEC_BAN_REFRESH`` seconds under a new ``reason_data.lease_id``. What these tests
pin is the contract the other lanes lean on:

* a lease is never removed by anything that is not that exact lease (``revoke_lease``), and a revoked
  lease never tombstones an explicit ban (X1 amendment 2, R1b);
* ``reason_data`` degrades instead of vanishing, and the identity set survives byte for byte (R3, R3b);
* ``kind`` is computed by one classifier that works on DB rows and on runtime rows alike.
"""

from datetime import datetime, timedelta, timezone
from json import dumps, loads

import pytest
from db_methods.bans import MAX_REASON_DATA, _reason_data_text, ban_kind  # type: ignore
from model import Bans  # type: ignore

LEASE_ID = "0123456789abcdef"
OTHER_ID = "fedcba9876543210"
IDENTITY_KEYS = ("lease", "version", "lease_id", "instance", "connection", "service_scope", "remediation", "source")


def _now():
    return datetime.now(timezone.utc)


def _ts(seconds):
    return (_now() + timedelta(seconds=seconds)).timestamp()


def _rows(db, **filters):
    with db._db_session() as session:
        query = session.query(Bans)
        for field, value in filters.items():
            query = query.filter(getattr(Bans, field) == value)
        return query.order_by(Bans.ip, Bans.ban_scope, Bans.service_id).all()


def _stamp_revoked(db, ip, scope="global", service="", ago=0):
    """Revoke the exact row without going through any revoke method, so a test of the learn path
    does not depend on the revoke path under test."""
    with db._db_session() as session:
        session.query(Bans).filter(Bans.ip == ip, Bans.ban_scope == scope, Bans.service_id == service).update(
            {"revoked_at": _now() - timedelta(seconds=ago), "revoked_by": "test"}
        )
        session.commit()


def _identity(lease_id=LEASE_ID, scope="global"):
    return {
        "lease": True,
        "version": 1,
        "lease_id": lease_id,
        "instance": "bw-1",
        "connection": "default",
        "service_scope": scope,
        "remediation": "ban",
        "source": "crowdsec",
    }


def _lease_data(lease_id=LEASE_ID, **over):
    data = _identity(lease_id) | {"scenario": "crowdsecurity/http-probing", "origin": "cscli", "action": "ban", "decisions": [{"id": 1, "value": "1.2.3.4"}]}
    return data | over


def _record(ip="1.2.3.4", scope="global", service="unknown", date_ago=300, ttl=30, reason="crowdsec", reason_data=None, **over):
    """A record as ``GET /bans`` returns it from an instance. ``date_ago`` is when the instance banned."""
    record = {
        "ip": ip,
        "reason": reason,
        "service": service,
        "date": _ts(-date_ago),
        "country": "FR",
        "ban_scope": scope,
        "exp": ttl,
        "expires_at": _ts(ttl),
        "permanent": False,
        "reason_data": reason_data if reason_data is not None else {},
    }
    return record | over


def _lease(ip="1.2.3.4", lease_id=LEASE_ID, scope="global", service="unknown", **over):
    return _record(ip, scope=scope, service=service, reason_data=_lease_data(lease_id), **over)


def _manual(ip="1.2.3.4", scope="service", service="app.example.com", **over):
    return _record(ip, scope=scope, service=service, reason="manual", reason_data={}, ttl=3600, **over)


# ── kind ────────────────────────────────────────────────────────────────────────────────────────
class TestBanKind:
    @pytest.mark.parametrize(
        "row,expected",
        [
            ({"reason": "crowdsec", "reason_data": {"lease": True}}, "crowdsec_lease"),
            ({"reason": "crowdsec", "reason_data": dumps({"lease": True, "lease_id": LEASE_ID})}, "crowdsec_lease"),
            ({"reason": "crowdsec", "reason_data": {"lease": False}}, "ban"),
            ({"reason": "crowdsec", "reason_data": {"lease": "true"}}, "ban"),
            ({"reason": "crowdsec", "reason_data": {"action": "ban"}}, "ban"),
            ({"reason": "crowdsec", "reason_data": {}}, "ban"),
            # Lua's cjson hands an empty table back as an empty array.
            ({"reason": "crowdsec", "reason_data": []}, "ban"),
            ({"reason": "crowdsec", "reason_data": None}, "ban"),
            ({"reason": "crowdsec", "reason_data": "not json"}, "ban"),
            ({"reason": "crowdsec"}, "ban"),
            ({"reason": "manual", "reason_data": {"lease": True}}, "ban"),
            ({"reason": "badbehavior", "reason_data": {"lease": True}}, "ban"),
            ({}, "ban"),
        ],
    )
    def test_classifier(self, row, expected):
        assert ban_kind(row) == expected

    def test_get_bans_rows_carry_kind(self, db):
        db.learn_bans([_lease("1.2.3.4"), _record("5.6.7.8", reason="badbehavior", reason_data={"counter": 3})])
        assert {b["ip"]: b["kind"] for b in db.get_bans()} == {"1.2.3.4": "crowdsec_lease", "5.6.7.8": "ban"}

    def test_the_row_kind_equals_the_classifier_on_the_same_row(self, db):
        db.learn_bans([_lease("1.2.3.4")])
        (ban,) = db.get_bans()
        assert ban["kind"] == ban_kind(ban)


# ── learn: renewal of leases ────────────────────────────────────────────────────────────────────
class TestLeaseRenewal:
    def test_new_lease_id_is_taken_even_when_the_expiry_barely_moves(self, db):
        # Renewed with 28 s left of a 30 s lease: +2 s, inside the jitter slack. The row must still
        # follow the lease_id, otherwise revoke_lease(new id) would match nothing.
        db.learn_bans([_lease(lease_id=LEASE_ID, ttl=30)])
        db.learn_bans([_lease(lease_id=OTHER_ID, ttl=31)])
        (row,) = _rows(db)
        assert loads(row.reason_data)["lease_id"] == OTHER_ID

    def test_older_lease_does_not_replace_a_newer_one(self, db):
        db.learn_bans([_lease(lease_id=OTHER_ID, ttl=60)])
        db.learn_bans([_lease(lease_id=LEASE_ID, ttl=20)])
        (row,) = _rows(db)
        assert loads(row.reason_data)["lease_id"] == OTHER_ID

    def test_explicit_ban_that_replaced_the_lease_is_followed(self, db):
        db.learn_bans([_lease(ttl=300)])
        db.learn_bans([_record("1.2.3.4", reason="manual", ttl=60, reason_data={})])
        (row,) = _rows(db)
        assert row.reason == "manual"
        assert db.get_bans()[0]["kind"] == "ban"

    def test_lease_never_overwrites_an_active_explicit_ban(self, db):
        db.upsert_ban("1.2.3.4", reason="manual", created_by="admin", expires_at=datetime.now(timezone.utc) + timedelta(seconds=10))
        db.learn_bans([_lease(ttl=600)])
        (row,) = _rows(db)
        assert (row.reason, row.created_by) == ("manual", "admin")

    def test_lease_reactivates_an_expired_explicit_row(self, db):
        db.upsert_ban("1.2.3.4", reason="manual", expires_at=datetime.now(timezone.utc) + timedelta(seconds=60))
        with db._db_session() as session:
            session.query(Bans).update({"expires_at": _now() - timedelta(seconds=5)})
            session.commit()
        inserted, _ = db.learn_bans([_lease(ttl=30)])
        assert len(inserted) == 1
        assert db.get_bans()[0]["kind"] == "crowdsec_lease"

    def test_renewed_lease_replaces_reason_data(self, db):
        db.learn_bans([_lease(lease_id=LEASE_ID, ttl=30)])
        db.learn_bans([_lease(lease_id=OTHER_ID, ttl=90)])
        (ban,) = db.get_bans()
        assert ban["reason_data"]["lease_id"] == OTHER_ID
        assert ban["exp"] > 60


# ── learn: R1b lease-aware tombstones ───────────────────────────────────────────────────────────
class TestLeaseTombstones:
    def test_revoked_global_lease_does_not_tombstone_a_manual_service_ban(self, db):
        db.learn_bans([_lease("1.2.3.4")])
        assert db.upsert_ban("1.2.3.4", ban_scope="service", service_id="app.example.com", reason="manual", expires_at=_now() + timedelta(hours=1)) == ""
        _stamp_revoked(db, "1.2.3.4")

        inserted, tombstoned = db.learn_bans([_manual()])

        assert tombstoned == []
        assert inserted == []
        assert [(b["ban_scope"], b["service"], b["reason"]) for b in db.get_bans()] == [("service", "app.example.com", "manual")]

    def test_revoked_global_lease_does_not_tombstone_a_new_manual_service_ban(self, db):
        db.learn_bans([_lease("1.2.3.4")])
        _stamp_revoked(db, "1.2.3.4")
        inserted, tombstoned = db.learn_bans([_manual()])
        assert tombstoned == []
        assert len(inserted) == 1
        assert [(b["ban_scope"], b["reason"]) for b in db.get_bans()] == [("service", "manual")]

    def test_revoked_global_lease_tombstones_the_same_lease_with_its_id(self, db):
        db.learn_bans([_lease("1.2.3.4", lease_id=LEASE_ID)])
        _stamp_revoked(db, "1.2.3.4")
        inserted, tombstoned = db.learn_bans([_lease("1.2.3.4", lease_id=LEASE_ID)])
        assert inserted == []
        assert tombstoned == [{"ip": "1.2.3.4", "ban_scope": "global", "service": "", "lease_id": LEASE_ID}]
        assert db.get_bans() == []

    def test_revoked_global_lease_covers_the_same_lease_reported_at_service_scope(self, db):
        db.learn_bans([_lease("1.2.3.4", lease_id=LEASE_ID)])
        _stamp_revoked(db, "1.2.3.4")
        _, tombstoned = db.learn_bans([_lease("1.2.3.4", lease_id=LEASE_ID, scope="service", service="app.example.com")])
        assert tombstoned == [{"ip": "1.2.3.4", "ban_scope": "service", "service": "app.example.com", "lease_id": LEASE_ID}]

    def test_revoked_global_lease_does_not_tombstone_another_lease_at_service_scope(self, db):
        db.learn_bans([_lease("1.2.3.4", lease_id=LEASE_ID)])
        _stamp_revoked(db, "1.2.3.4")
        inserted, tombstoned = db.learn_bans([_lease("1.2.3.4", lease_id=OTHER_ID, scope="service", service="app.example.com")])
        assert tombstoned == []
        assert len(inserted) == 1

    def test_new_lease_id_after_the_revoke_is_learned_as_active(self, db):
        db.learn_bans([_lease("1.2.3.4", lease_id=LEASE_ID, date_ago=300)])
        _stamp_revoked(db, "1.2.3.4", ago=60)
        inserted, tombstoned = db.learn_bans([_lease("1.2.3.4", lease_id=OTHER_ID, date_ago=10)])
        assert tombstoned == []
        assert len(inserted) == 1
        (ban,) = db.get_bans()
        assert ban["reason_data"]["lease_id"] == OTHER_ID

    def test_new_lease_id_dated_before_the_revoke_is_not_covered_by_it_either(self, db):
        # Renewed between preview and apply: the instance holds lease B, the operator revoked lease A.
        # The revoke never named B, so the row follows what the instance really enforces.
        db.learn_bans([_lease("1.2.3.4", lease_id=LEASE_ID, date_ago=300)])
        _stamp_revoked(db, "1.2.3.4", ago=0)
        inserted, tombstoned = db.learn_bans([_lease("1.2.3.4", lease_id=OTHER_ID, date_ago=100)])
        assert tombstoned == []
        assert len(inserted) == 1
        assert db.get_bans()[0]["reason_data"]["lease_id"] == OTHER_ID

    def test_explicit_ban_on_the_identity_of_a_revoked_lease_reactivates_it(self, db):
        db.learn_bans([_lease("1.2.3.4", lease_id=LEASE_ID)])
        _stamp_revoked(db, "1.2.3.4")
        inserted, tombstoned = db.learn_bans([_record("1.2.3.4", reason="badbehavior", reason_data={"counter": 5}, ttl=600, date_ago=100)])
        assert tombstoned == []
        assert len(inserted) == 1
        (ban,) = db.get_bans()
        assert (ban["reason"], ban["kind"]) == ("badbehavior", "ban")

    def test_revoked_lease_rows_tombstone_keeps_its_guard_on_a_concurrent_revoke(self, db):
        db.learn_bans([_lease("1.2.3.4", lease_id=LEASE_ID)])
        _stamp_revoked(db, "1.2.3.4")
        # Reported twice in one batch (instance and Redis both): both are the revoked lease.
        _, tombstoned = db.learn_bans([_lease("1.2.3.4", lease_id=LEASE_ID), _lease("1.2.3.4", lease_id=LEASE_ID)])
        assert len(tombstoned) == 2

    def test_explicit_global_revoke_still_covers_service_records(self, db):
        db.upsert_ban("1.2.3.4", reason="manual", expires_at=_now() + timedelta(hours=1))
        assert db.revoke_ban("1.2.3.4", revoked_by="admin") == ""
        inserted, tombstoned = db.learn_bans([_manual()])
        assert inserted == []
        assert tombstoned == [{"ip": "1.2.3.4", "ban_scope": "service", "service": "app.example.com"}]

    def test_explicit_global_revoke_covers_a_service_lease_and_names_it(self, db):
        db.upsert_ban("1.2.3.4", reason="manual", expires_at=_now() + timedelta(hours=1))
        assert db.revoke_ban("1.2.3.4", revoked_by="admin") == ""
        _, tombstoned = db.learn_bans([_lease("1.2.3.4", lease_id=LEASE_ID, scope="service", service="app.example.com")])
        assert tombstoned == [{"ip": "1.2.3.4", "ban_scope": "service", "service": "app.example.com", "lease_id": LEASE_ID}]

    def test_explicit_tombstone_carries_no_lease_id(self, db):
        db.upsert_ban("1.2.3.4", reason="manual", expires_at=_now() + timedelta(hours=1))
        db.revoke_ban("1.2.3.4")
        _, tombstoned = db.learn_bans([_record("1.2.3.4", reason="manual", scope="global", service="unknown")])
        assert tombstoned == [{"ip": "1.2.3.4", "ban_scope": "global", "service": ""}]


# ── revoke_lease ────────────────────────────────────────────────────────────────────────────────
class TestRevokeLease:
    def test_revokes_the_row_with_that_lease_id(self, db):
        db.learn_bans([_lease("1.2.3.4", lease_id=LEASE_ID)])
        assert db.revoke_lease("1.2.3.4", ban_scope="global", service_id="", lease_id=LEASE_ID, revoked_by="admin") == ""
        (row,) = _rows(db)
        assert row.revoked_at is not None and row.revoked_by == "admin"
        assert db.get_bans() == []

    def test_a_different_lease_id_revokes_nothing(self, db):
        db.learn_bans([_lease("1.2.3.4", lease_id=OTHER_ID)])
        assert db.revoke_lease("1.2.3.4", ban_scope="global", service_id="", lease_id=LEASE_ID) == ""
        assert _rows(db)[0].revoked_at is None

    def test_an_empty_lease_id_is_refused_and_revokes_nothing(self, db):
        db.learn_bans([_lease("1.2.3.4", lease_id=LEASE_ID)])
        assert db.revoke_lease("1.2.3.4", ban_scope="global", service_id="", lease_id="") != ""
        assert _rows(db)[0].revoked_at is None

    def test_never_widens_to_the_service_scope(self, db):
        db.learn_bans([_lease("1.2.3.4", lease_id=LEASE_ID), _lease("1.2.3.4", lease_id=LEASE_ID, scope="service", service="app.example.com")])
        assert db.revoke_lease("1.2.3.4", ban_scope="global", service_id="", lease_id=LEASE_ID) == ""
        assert {(r.ban_scope, r.revoked_at is None) for r in _rows(db)} == {("global", False), ("service", True)}

    def test_never_widens_to_other_services(self, db):
        db.learn_bans(
            [
                _lease("1.2.3.4", lease_id=LEASE_ID, scope="service", service="a.example.com"),
                _lease("1.2.3.4", lease_id=LEASE_ID, scope="service", service="b.example.com"),
            ]
        )
        assert db.revoke_lease("1.2.3.4", ban_scope="service", service_id="a.example.com", lease_id=LEASE_ID) == ""
        assert {(r.service_id, r.revoked_at is None) for r in _rows(db)} == {("a.example.com", False), ("b.example.com", True)}

    def test_never_touches_an_explicit_ban_even_with_a_matching_lease_id(self, db):
        db.upsert_ban("1.2.3.4", reason="manual", reason_data={"lease_id": LEASE_ID}, expires_at=_now() + timedelta(hours=1))
        assert db.revoke_lease("1.2.3.4", ban_scope="global", service_id="", lease_id=LEASE_ID) == ""
        assert _rows(db)[0].revoked_at is None

    def test_leaves_a_manual_service_ban_next_to_a_global_lease(self, db):
        db.learn_bans([_lease("1.2.3.4", lease_id=LEASE_ID)])
        db.upsert_ban("1.2.3.4", ban_scope="service", service_id="app.example.com", reason="manual", expires_at=_now() + timedelta(hours=1))
        assert db.revoke_lease("1.2.3.4", ban_scope="global", service_id="", lease_id=LEASE_ID) == ""
        assert [(b["ban_scope"], b["reason"]) for b in db.get_bans()] == [("service", "manual")]

    def test_is_idempotent_and_keeps_the_first_revocation(self, db):
        db.learn_bans([_lease("1.2.3.4", lease_id=LEASE_ID)])
        db.revoke_lease("1.2.3.4", ban_scope="global", service_id="", lease_id=LEASE_ID, revoked_by="first")
        db.revoke_lease("1.2.3.4", ban_scope="global", service_id="", lease_id=LEASE_ID, revoked_by="second")
        assert _rows(db)[0].revoked_by == "first"

    def test_unknown_identity_is_not_an_error(self, db):
        assert db.revoke_lease("1.2.3.4", ban_scope="global", service_id="", lease_id=LEASE_ID) == ""

    def test_garbage_ip_is_refused(self, db):
        assert db.revoke_lease("nope", ban_scope="global", service_id="", lease_id=LEASE_ID) == "invalid IP address"

    def test_normalizes_the_ip_like_every_other_ban_method(self, db):
        db.learn_bans([_lease("2001:db8::1", lease_id=LEASE_ID)])
        assert db.revoke_lease("2001:0DB8::1", ban_scope="global", service_id="", lease_id=LEASE_ID) == ""
        assert _rows(db)[0].revoked_at is not None

    def test_the_tombstone_it_leaves_replays_the_same_lease_and_spares_a_new_one(self, db):
        db.learn_bans([_lease("1.2.3.4", lease_id=LEASE_ID)])
        db.revoke_lease("1.2.3.4", ban_scope="global", service_id="", lease_id=LEASE_ID)
        _, tombstoned = db.learn_bans([_lease("1.2.3.4", lease_id=LEASE_ID)])
        assert [t["lease_id"] for t in tombstoned] == [LEASE_ID]
        inserted, tombstoned = db.learn_bans([_lease("1.2.3.4", lease_id=OTHER_ID, date_ago=0)])
        assert tombstoned == [] and len(inserted) == 1


# ── reason_data degrades instead of dropping ────────────────────────────────────────────────────
def _payload_of_stored_length(target, decisions=3):
    """A lease payload whose stored text is exactly ``target`` characters, built by padding the last
    decision with ASCII (one character each)."""
    payload = _lease_data(decisions=[{"id": i, "type": "ban", "value": "v"} for i in range(decisions)])
    base = len(dumps(payload, default=str))
    assert base <= target
    payload["decisions"][-1]["value"] = "v" * (1 + target - base)
    assert len(dumps(payload, default=str)) == target
    return payload


def _unicode_heavy():
    names = ["🔥🐛 scénario-ünïcode", "漢字のシナリオ/拡張", "سيناريو-الهجوم-الطويل", "𝔘𝔫𝔦𝔠𝔬𝔡𝔢-😀😀😀"]
    data = _lease_data(scenario=names[0] * 3, origin="来源-" + names[2])
    data["decisions"] = [{"id": i, "scenario": names[i % 4] * 8, "value": f"203.0.113.{i}", "origin": "ü" * 20} for i in range(40)]
    return data


class TestReasonDataDegrades:
    def test_a_payload_that_fits_is_stored_untouched(self):
        data = _lease_data()
        assert loads(_reason_data_text(data)) == data

    def test_text_input_that_fits_is_returned_as_is(self):
        assert _reason_data_text('{"a": 1}') == '{"a": 1}'

    def test_empty_values_store_nothing(self):
        assert all(_reason_data_text(v) is None for v in (None, "", {}, []))

    @pytest.mark.parametrize("delta", [-1, 0])
    def test_at_or_under_the_limit_nothing_is_removed(self, delta):
        payload = _payload_of_stored_length(MAX_REASON_DATA + delta)
        text = _reason_data_text(payload)
        assert text == dumps(payload, default=str)
        assert len(loads(text)["decisions"]) == 3

    def test_one_over_the_limit_drops_a_decision_from_the_end(self):
        payload = _payload_of_stored_length(MAX_REASON_DATA + 1)
        text = _reason_data_text(payload)
        assert len(text) <= MAX_REASON_DATA
        stored = loads(text)
        assert [d["id"] for d in stored["decisions"]] == [0, 1]
        assert {k: stored[k] for k in IDENTITY_KEYS} == _identity()
        assert (stored["scenario"], stored["origin"], stored["action"]) == ("crowdsecurity/http-probing", "cscli", "ban")

    def test_decisions_go_before_scenario_origin_and_action(self):
        payload = _lease_data(decisions=[{"v": "x" * 5000}])
        stored = loads(_reason_data_text(payload))
        assert "decisions" not in stored
        assert (stored["scenario"], stored["origin"], stored["action"]) == ("crowdsecurity/http-probing", "cscli", "ban")

    def test_scenario_origin_action_are_dropped_whole_never_cut_mid_value(self):
        payload = _lease_data(scenario="s" * 3000, origin="o" * 3000, action="a" * 3000, decisions=[])
        stored = loads(_reason_data_text(payload))
        for key in ("scenario", "origin", "action"):
            assert key not in stored or len(stored[key]) == 3000
        assert {k: stored[k] for k in IDENTITY_KEYS} == _identity()

    def test_unicode_heavy_payload_keeps_the_identity_set_exactly(self):
        data = _unicode_heavy()
        assert len(dumps(data, default=str)) > 2 * MAX_REASON_DATA  # the old code dropped all of it
        text = _reason_data_text(data)
        assert text is not None and len(text) <= MAX_REASON_DATA
        stored = loads(text)
        assert {k: stored[k] for k in IDENTITY_KEYS} == _identity()

    def test_identity_fields_are_never_shortened(self):
        # An identity value that is long but fits on its own: it stays whole while others go.
        data = _lease_data(instance="i" * 900, connection="c" * 900, decisions=[{"v": "x" * 4000}])
        stored = loads(_reason_data_text(data))
        assert (stored["instance"], stored["connection"]) == ("i" * 900, "c" * 900)

    def test_a_payload_whose_identity_alone_cannot_fit_is_dropped_not_shortened(self):
        data = _lease_data(instance="i" * 5000)
        assert _reason_data_text(data) is None

    def test_unknown_oversized_keys_are_dropped_not_the_whole_payload(self):
        stored = loads(_reason_data_text(_lease_data(blob="x" * 9000)))
        assert "blob" not in stored and stored["lease_id"] == LEASE_ID

    def test_non_lease_oversized_payload_is_still_dropped(self):
        assert _reason_data_text({"blob": "x" * 8192}) is None

    def test_oversized_text_input_degrades_like_a_dict(self):
        text = _reason_data_text(dumps(_lease_data(decisions=[{"v": "x" * 5000}])))
        assert loads(text)["lease_id"] == LEASE_ID

    def test_unparseable_oversized_text_is_dropped(self):
        assert _reason_data_text("{" + "x" * 5000) is None

    def test_long_decision_lists_degrade_without_quadratic_cost(self):
        data = _lease_data(decisions=[{"id": i, "value": "x" * 50} for i in range(20000)])
        stored = loads(_reason_data_text(data))
        assert 0 < len(stored["decisions"]) < 20000
        assert stored["decisions"] == [{"id": i, "value": "x" * 50} for i in range(len(stored["decisions"]))]

    # The DB path ------------------------------------------------------------------------------
    @pytest.mark.parametrize("delta", [-1, 0, 1])
    def test_boundary_sizes_still_classify_as_leases_and_revoke_by_lease_id(self, db, delta):
        db.learn_bans([_record("1.2.3.4", reason_data=_payload_of_stored_length(MAX_REASON_DATA + delta))])
        (row,) = _rows(db)
        assert len(row.reason_data) <= MAX_REASON_DATA
        assert db.get_bans()[0]["kind"] == "crowdsec_lease"
        assert db.revoke_lease("1.2.3.4", ban_scope="global", service_id="", lease_id=LEASE_ID) == ""
        assert _rows(db)[0].revoked_at is not None

    def test_unicode_heavy_lease_classifies_and_matches_revoke_lease(self, db):
        db.learn_bans([_record("1.2.3.4", reason_data=_unicode_heavy())])
        (row,) = _rows(db)
        assert row.reason_data is not None and len(row.reason_data) <= MAX_REASON_DATA
        assert db.get_bans()[0]["kind"] == "crowdsec_lease"
        assert db.revoke_lease("1.2.3.4", ban_scope="global", service_id="", lease_id=OTHER_ID) == ""
        assert _rows(db)[0].revoked_at is None
        assert db.revoke_lease("1.2.3.4", ban_scope="global", service_id="", lease_id=LEASE_ID) == ""
        assert _rows(db)[0].revoked_at is not None

    def test_a_degraded_row_still_tombstones_its_own_lease_by_id(self, db):
        db.learn_bans([_record("1.2.3.4", reason_data=_unicode_heavy())])
        _stamp_revoked(db, "1.2.3.4")
        _, tombstoned = db.learn_bans([_record("1.2.3.4", reason_data=_unicode_heavy())])
        assert [t["lease_id"] for t in tombstoned] == [LEASE_ID]

    def test_upsert_ban_degrades_the_same_way(self, db):
        assert db.upsert_ban("1.2.3.4", reason="crowdsec", reason_data=_unicode_heavy(), expires_at=_now() + timedelta(seconds=30)) == ""
        assert db.get_bans()[0]["kind"] == "crowdsec_lease"
