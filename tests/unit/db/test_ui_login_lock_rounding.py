"""Second-resolution databases can round a failure timestamp into the future."""

from datetime import datetime, timezone

import pytest


@pytest.mark.parametrize("username,ip", [("alice", "192.0.2.2"), ("bob", "192.0.2.1")], ids=["username", "ip"])
@pytest.mark.parametrize("lockout", [300, 900])
def test_rounded_failure_never_reports_more_than_lockout(db, monkeypatch, username, ip, lockout):
    from db_methods import ui_users
    from model import UserLoginFailures

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 11, 5, 12, 0, 0, 750000, tzinfo=timezone.utc)

    monkeypatch.setattr(ui_users, "datetime", Clock)
    with db._db_session() as session:
        for _ in range(5):
            session.add(UserLoginFailures(username="alice", ip="192.0.2.1", failure_date=datetime(2026, 11, 5, 12, 0, 1, tzinfo=timezone.utc)))
        session.commit()

    assert db.get_ui_login_lock(username, ip, max_attempts=5, window=900, lockout=lockout) == lockout
