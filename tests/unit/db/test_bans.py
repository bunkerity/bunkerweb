"""DatabaseBansMixin — durable ban lifecycle (bw_bans).

The DB is the source of truth; shared dicts and Redis are projections. What these tests pin is
everything that makes that safe: the identity triple can't duplicate, a global revoke covers the
service-scoped rows the Lua unban would also have deleted, and a tombstone survives long enough
that an instance coming back online can't resurrect a ban the operator cleared.

No FKs on the table (a ban outlives its service), so the plain ``db`` fixture suffices.
"""

from datetime import datetime, timedelta, timezone

from model import Bans  # type: ignore


def _rows(db, **filters):
    with db._db_session() as session:
        query = session.query(Bans)
        for field, value in filters.items():
            query = query.filter(getattr(Bans, field) == value)
        return query.order_by(Bans.ip, Bans.ban_scope, Bans.service_id).all()


def _in(seconds):
    return datetime.now().astimezone() + timedelta(seconds=seconds)


def _record(ip="1.2.3.4", **over):
    """A record in the shape ``GET /bans`` returns from an instance."""
    record = {
        "ip": ip,
        "reason": "badbehavior",
        "service": "unknown",
        "date": datetime.now().astimezone().timestamp(),
        "country": "FR",
        "ban_scope": "global",
        "exp": 3600,
        "expires_at": _in(3600).timestamp(),
        "permanent": False,
        "reason_data": {"counter": 12},
    }
    record.update(over)
    return record


class TestUpsert:
    def test_insert(self, db):
        assert db.upsert_ban("1.2.3.4", reason="manual", expires_at=_in(3600), created_by="admin") == ""
        (row,) = _rows(db)
        assert (row.ip, row.ban_scope, row.service_id, row.created_by) == ("1.2.3.4", "global", "", "admin")
        assert row.revoked_at is None

    def test_is_idempotent_on_the_identity_triple(self, db):
        # A nullable service_id would make these two rows distinct on every engine (NULL != NULL
        # inside a UNIQUE constraint), which is exactly the duplicate this asserts against.
        assert db.upsert_ban("1.2.3.4", reason="first", expires_at=_in(3600)) == ""
        assert db.upsert_ban("1.2.3.4", reason="second", expires_at=_in(7200)) == ""
        (row,) = _rows(db)
        assert row.reason == "second"

    def test_global_and_service_scopes_coexist(self, db):
        assert db.upsert_ban("1.2.3.4", expires_at=_in(3600)) == ""
        assert db.upsert_ban("1.2.3.4", ban_scope="service", service_id="app.example.com", expires_at=_in(3600)) == ""
        assert [(r.ban_scope, r.service_id) for r in _rows(db)] == [("global", ""), ("service", "app.example.com")]

    def test_normalizes_the_ip(self, db):
        assert db.upsert_ban("  2001:0DB8::1  ", expires_at=_in(3600)) == ""
        (row,) = _rows(db)
        assert row.ip == "2001:db8::1"

    def test_rejects_garbage_and_past_expiry(self, db):
        assert db.upsert_ban("not-an-ip") == "invalid IP address"
        assert db.upsert_ban("1.2.3.4", expires_at=_in(-60)) == "ban expiration is in the past"
        assert _rows(db) == []

    def test_permanent_ban_has_no_expiry(self, db):
        assert db.upsert_ban("1.2.3.4") == ""
        (row,) = _rows(db)
        assert row.expires_at is None
        assert db.get_bans()[0]["permanent"] is True
        assert db.get_bans()[0]["exp"] == 0

    def test_reban_clears_the_tombstone(self, db):
        db.upsert_ban("1.2.3.4", expires_at=_in(3600))
        db.revoke_ban("1.2.3.4", revoked_by="admin")
        assert db.upsert_ban("1.2.3.4", expires_at=_in(3600)) == ""
        (row,) = _rows(db)
        assert row.revoked_at is None and row.revoked_by is None

    def test_oversized_reason_data_is_dropped_not_stored(self, db):
        db.upsert_ban("1.2.3.4", reason_data={"blob": "x" * 8192}, expires_at=_in(3600))
        (row,) = _rows(db)
        assert row.reason_data is None


class TestRevoke:
    def test_keeps_the_row_as_a_tombstone(self, db):
        db.upsert_ban("1.2.3.4", expires_at=_in(3600))
        assert db.revoke_ban("1.2.3.4", revoked_by="admin") == ""
        (row,) = _rows(db)
        assert row.revoked_at is not None and row.revoked_by == "admin"
        assert db.get_bans() == []
        assert len(db.get_bans(include_revoked=True)) == 1

    def test_global_revoke_covers_service_rows(self, db):
        # utils.remove_ban deletes the global key AND every bans_service_*_ip_<ip>; a tombstone
        # that did not cover the same set would let the next pass re-push the service bans.
        db.upsert_ban("1.2.3.4", expires_at=_in(3600))
        db.upsert_ban("1.2.3.4", ban_scope="service", service_id="app.example.com", expires_at=_in(3600))
        db.upsert_ban("5.6.7.8", ban_scope="service", service_id="app.example.com", expires_at=_in(3600))

        assert db.revoke_ban("1.2.3.4", revoked_by="admin") == ""

        revoked = {(r.ip, r.ban_scope) for r in _rows(db) if r.revoked_at is not None}
        assert revoked == {("1.2.3.4", "global"), ("1.2.3.4", "service")}

    def test_service_revoke_leaves_the_global_ban(self, db):
        db.upsert_ban("1.2.3.4", expires_at=_in(3600))
        db.upsert_ban("1.2.3.4", ban_scope="service", service_id="app.example.com", expires_at=_in(3600))
        assert db.revoke_ban("1.2.3.4", ban_scope="service", service_id="app.example.com") == ""
        assert {(r.ban_scope, r.revoked_at is None) for r in _rows(db)} == {("global", True), ("service", False)}


class TestGetBans:
    def test_hides_expired_rows(self, db):
        db.upsert_ban("1.2.3.4", expires_at=_in(3600))
        db.upsert_ban("5.6.7.8", expires_at=_in(3600))
        with db._db_session() as session:
            session.query(Bans).filter(Bans.ip == "5.6.7.8").update({"expires_at": datetime.now(timezone.utc) - timedelta(seconds=60)})
            session.commit()
        assert [b["ip"] for b in db.get_bans()] == ["1.2.3.4"]

    def test_emits_the_runtime_ban_shape(self, db):
        db.upsert_ban("1.2.3.4", ban_scope="service", service_id="app.example.com", reason="manual", country="FR", reason_data={"n": 1}, expires_at=_in(3600))
        (ban,) = db.get_bans()
        assert set(ban) == {"ip", "reason", "service", "date", "country", "ban_scope", "exp", "expires_at", "permanent", "reason_data"}
        assert (ban["service"], ban["ban_scope"], ban["reason_data"], ban["permanent"]) == ("app.example.com", "service", {"n": 1}, False)
        assert 3500 < ban["exp"] <= 3600

    def test_global_ban_reports_the_placeholder_service(self, db):
        db.upsert_ban("1.2.3.4", expires_at=_in(3600))
        assert db.get_bans()[0]["service"] == "unknown"


class TestLearn:
    def test_inserts_unknown_bans(self, db):
        inserted, tombstoned = db.learn_bans([_record("1.2.3.4"), _record("5.6.7.8")])
        assert len(inserted) == 2 and tombstoned == []
        assert {r.ip for r in _rows(db)} == {"1.2.3.4", "5.6.7.8"}
        assert {r.origin for r in _rows(db)} == {"instance"}

    def test_known_active_ban_is_a_no_op(self, db):
        db.upsert_ban("1.2.3.4", reason="manual", created_by="admin", expires_at=_in(3600))
        inserted, tombstoned = db.learn_bans([_record("1.2.3.4")])
        assert (inserted, tombstoned) == ([], [])
        (row,) = _rows(db)
        assert row.reason == "manual" and row.created_by == "admin"

    def test_revoked_ban_is_tombstoned_not_relearned(self, db):
        # The instance whose API path was down never got POST /unban and still reports the ban.
        db.upsert_ban("1.2.3.4", expires_at=_in(3600))
        db.revoke_ban("1.2.3.4", revoked_by="admin")
        inserted, tombstoned = db.learn_bans([_record("1.2.3.4", date=(datetime.now().astimezone() - timedelta(minutes=5)).timestamp())])
        assert inserted == []
        assert tombstoned == [{"ip": "1.2.3.4", "ban_scope": "global", "service": ""}]
        (row,) = _rows(db)
        assert row.revoked_at is not None

    def test_revoked_global_ban_tombstones_a_service_record(self, db):
        db.upsert_ban("1.2.3.4", expires_at=_in(3600))
        db.revoke_ban("1.2.3.4", revoked_by="admin")
        record = _record("1.2.3.4", ban_scope="service", service="app.example.com", date=(datetime.now().astimezone() - timedelta(minutes=5)).timestamp())
        inserted, tombstoned = db.learn_bans([record])
        assert inserted == []
        assert tombstoned == [{"ip": "1.2.3.4", "ban_scope": "service", "service": "app.example.com"}]

    def test_ban_recorded_after_the_revoke_is_reactivated(self, db):
        # Operator unbans, the attacker misbehaves again, badbehavior re-bans locally. That is a
        # genuine new ban, not the stale one — suppressing it would disarm badbehavior.
        db.upsert_ban("1.2.3.4", expires_at=_in(3600))
        db.revoke_ban("1.2.3.4", revoked_by="admin")
        inserted, tombstoned = db.learn_bans([_record("1.2.3.4", date=_in(1).timestamp())])
        assert tombstoned == []
        assert inserted == [{"ip": "1.2.3.4", "ban_scope": "global", "service": ""}]
        (row,) = _rows(db)
        assert row.revoked_at is None

    def test_permanent_record_stores_no_expiry(self, db):
        db.learn_bans([_record("1.2.3.4", permanent=True, exp=0, expires_at=0)])
        (row,) = _rows(db)
        assert row.expires_at is None

    def test_placeholder_service_names_collapse_to_a_global_ban(self, db):
        db.learn_bans([_record("1.2.3.4", service="unknown"), _record("5.6.7.8", service="_")])
        assert {(r.ban_scope, r.service_id) for r in _rows(db)} == {("global", "")}

    def test_bad_ip_is_skipped_without_killing_the_batch(self, db):
        inserted, _ = db.learn_bans([_record("nonsense"), _record("1.2.3.4")])
        assert [i["ip"] for i in inserted] == ["1.2.3.4"]


class TestPurge:
    def test_drops_old_tombstones_and_keeps_recent_ones(self, db):
        db.upsert_ban("1.2.3.4", expires_at=_in(3600))
        db.upsert_ban("5.6.7.8", expires_at=_in(3600))
        db.revoke_ban("1.2.3.4")
        db.revoke_ban("5.6.7.8")
        with db._db_session() as session:
            session.query(Bans).filter(Bans.ip == "1.2.3.4").update({"revoked_at": datetime.now(timezone.utc) - timedelta(days=45)})
            session.commit()

        assert db.purge_bans() == ""
        assert [r.ip for r in _rows(db)] == ["5.6.7.8"]

    def test_keeps_active_bans_whatever_their_age(self, db):
        db.upsert_ban("1.2.3.4")  # permanent
        assert db.purge_bans() == ""
        assert [r.ip for r in _rows(db)] == ["1.2.3.4"]
