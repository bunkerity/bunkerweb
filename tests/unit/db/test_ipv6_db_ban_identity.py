"""One client address, one ban row: every spelling of an address is the same ``bw_bans`` identity (dev 93c91c40e).

NGINX prints `$remote_addr` in RFC 5952 form and an IPv4-mapped address is its IPv4 address, so the key the runtime
looks a ban up under is that one text. A row stored by an older version under another spelling (here: the mapped one,
which ``str(ip_address())`` kept as such) is the same ban: it must be found, listed once and revoked.
"""

from datetime import datetime, timedelta, timezone

import pytest
from model import Bans  # type: ignore


def _in(seconds):
    return datetime.now(timezone.utc) + timedelta(seconds=seconds)


def _ips(db, **filters):
    with db._db_session() as session:
        query = session.query(Bans)
        for field, value in filters.items():
            query = query.filter(getattr(Bans, field) == value)
        return sorted(row.ip for row in query.all())


def _insert_legacy(db, ip, **over):
    row = {
        "ip": ip,
        "ban_scope": "global",
        "service_id": "",
        "origin": "api",
        "reason": "old",
        "created_at": datetime.now(timezone.utc),
        "expires_at": _in(3600),
    }
    row.update(over)
    with db._db_session() as session:
        session.add(Bans(**row))
        session.commit()


@pytest.mark.parametrize(("given", "stored"), [("2001:0DB8:0:0:0:0:0:1", "2001:db8::1"), ("::ffff:192.0.2.1", "192.0.2.1"), ("::FFFF:C000:201", "192.0.2.1")])
def test_a_ban_is_stored_under_the_canonical_address(db, given, stored):
    assert db.upsert_ban(given, reason="manual", expires_at=_in(60)) == ""
    assert _ips(db) == [stored]
    assert db.upsert_ban(stored, reason="again", expires_at=_in(60)) == ""
    assert _ips(db) == [stored], "a second spelling made a second row"


def test_a_zone_id_or_a_prefix_is_not_an_address(db):
    for bad in ("fe80::1%eth0", "2001:db8::/64", "[2001:db8::1]", "not an ip"):
        assert db.upsert_ban(bad, reason="x", expires_at=_in(60)) == "invalid IP address"
        assert db.revoke_ban(bad) == "invalid IP address"
    assert _ips(db) == []


def test_a_legacy_mapped_row_is_listed_under_its_canonical_address_and_once(db):
    _insert_legacy(db, "::ffff:192.0.2.1")
    assert [ban["ip"] for ban in db.get_bans()] == ["192.0.2.1"]
    # the same address stored under both spellings must never produce two entries (ban_sync refuses duplicates)
    _insert_legacy(db, "192.0.2.1")
    assert [ban["ip"] for ban in db.get_bans()] == ["192.0.2.1"]


def test_a_legacy_row_still_unbans(db):
    _insert_legacy(db, "::ffff:192.0.2.1")
    _insert_legacy(db, "::ffff:c000:201", ban_scope="service", service_id="www")
    assert db.revoke_ban("192.0.2.1") == ""
    assert db.get_bans() == [], "a ban stored under the mapped spelling survived the unban"
    # also through the mapped spelling of the request
    _insert_legacy(db, "::ffff:192.0.2.9")
    assert db.revoke_ban("::ffff:192.0.2.9") == ""
    assert db.get_bans() == []


def test_a_rebanned_legacy_row_is_reused_not_duplicated(db):
    _insert_legacy(db, "::ffff:192.0.2.1")
    assert db.upsert_ban("192.0.2.1", reason="manual", expires_at=_in(120)) == ""
    assert _ips(db, revoked_at=None) == ["192.0.2.1"]
    assert len(db.get_bans()) == 1
