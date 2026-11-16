"""Web UI login throttle, DB side: the count lives in `bw_ui_login_failures`, shared by every UI worker.

Ported from dev's `tests/unit/ui/routes/test_routes_login_throttle.py` (1.6.18~rc3, commit bda10b007), whose
`UIDatabase` methods became `DatabaseUIUsersMixin` methods in 1.7. The route-level half is
`tests/unit/ui/test_login_throttle.py`. Runs on every engine of the matrix.
"""

from datetime import datetime, timedelta, timezone

IP = "203.0.113.1"
WINDOW = 15 * 60
LOCKOUT = 15 * 60


def _failures(db):
    from model import UserLoginFailures

    with db._db_session() as session:
        return [(row.username, row.ip) for row in session.query(UserLoginFailures).order_by(UserLoginFailures.id).all()]


def _seed(db, *minutes_ago, username="alice", ip=IP):
    from model import UserLoginFailures

    now = datetime.now(timezone.utc)
    with db._db_session() as session:
        for minutes in minutes_ago:
            session.add(UserLoginFailures(username=username, ip=ip, failure_date=now - timedelta(minutes=minutes)))
        session.commit()


def _age(db, minutes):
    from model import UserLoginFailures

    with db._db_session() as session:
        for row in session.query(UserLoginFailures).all():
            stored = row.failure_date if row.failure_date.tzinfo else row.failure_date.replace(tzinfo=timezone.utc)
            row.failure_date = stored - timedelta(minutes=minutes)
        session.commit()


def _lock(db, username="alice", ip=IP, *, max_attempts=5, window=WINDOW, lockout=LOCKOUT):
    return db.get_ui_login_lock(username, ip, max_attempts=max_attempts, window=window, lockout=lockout)


def _fail(db, count, username="alice", ip=IP):
    for _ in range(count):
        assert db.add_ui_login_failure(username, ip, retention=WINDOW + LOCKOUT) == ""


class TestLock:
    def test_the_fifth_failure_locks_the_fourth_does_not(self, db):
        _fail(db, 4)
        assert _lock(db) == 0

        _fail(db, 1)

        assert 14 * 60 < _lock(db) <= 15 * 60

    def test_the_lock_expires(self, db):
        _fail(db, 5)
        assert _lock(db) > 0

        _age(db, 16)

        assert _lock(db) == 0

    def test_spread_out_failures_lock_for_the_full_lockout(self, db):
        _seed(db, 26, 23, 20, 17, 14)  # failures at minutes 0, 3, 6, 9 and 12; it is minute 26

        assert 0 < _lock(db) <= 60  # the fifth locked until minute 27, although the first is 26 minutes old

        _age(db, 2)  # minute 28

        assert _lock(db) == 0

    def test_a_lock_outlives_the_window_of_its_failures(self, db):
        _seed(db, 18, 16, 14, 12, 10)  # five failures over 8 minutes; only three are still inside the window

        # MySQL rounds the seeded timestamp to seconds; ceil can add one second.
        assert 4 * 60 < _lock(db) <= 5 * 60 + 1

    def test_failures_too_far_apart_do_not_lock(self, db):
        _seed(db, 40, 30, 20, 10, 1)  # never five within 15 minutes

        assert _lock(db) == 0

    def test_an_ip_locks_whatever_the_username(self, db):
        for name in ("bob", "carol", "dave", "erin", "frank"):
            assert db.add_ui_login_failure(name, "198.51.100.7", retention=WINDOW + LOCKOUT) == ""

        assert _lock(db, "zoe", "198.51.100.7") > 0
        assert _lock(db, "zoe", "198.51.100.8") == 0

    def test_a_username_locks_from_every_ip(self, db):
        for octet in range(10, 15):
            assert db.add_ui_login_failure("alice", f"192.0.2.{octet}", retention=WINDOW + LOCKOUT) == ""

        assert _lock(db, "alice", "192.0.2.99") > 0

    def test_the_username_is_folded(self, db):
        for octet, name in enumerate(("alice", "ALICE", "Alice", " alice", "alice ")):
            assert db.add_ui_login_failure(name, f"192.0.2.{octet + 10}", retention=WINDOW + LOCKOUT) == ""

        assert {name for name, _ in _failures(db)} == {"alice"}
        assert _lock(db, "ALICE ", "192.0.2.99") > 0

    def test_a_username_longer_than_the_column_is_cut_not_refused(self, db):
        assert db.add_ui_login_failure("a" * 400, IP, retention=WINDOW + LOCKOUT) == ""

        assert len(_failures(db)[0][0]) == 256

    def test_the_numbers_are_tunable(self, db):
        _fail(db, 2)

        assert _lock(db, max_attempts=2, window=20 * 60, lockout=30 * 60) > 0
        _age(db, 25)  # out of the 20 minute window, still inside the 30 minute lockout
        assert _lock(db, max_attempts=2, window=20 * 60, lockout=30 * 60) > 0
        _age(db, 10)  # 35 minutes after the last failure
        assert _lock(db, max_attempts=2, window=20 * 60, lockout=30 * 60) == 0


class TestRecord:
    def test_old_failures_are_pruned_when_a_new_one_is_recorded(self, db):
        _fail(db, 2)
        _age(db, 120)

        _fail(db, 1)

        assert len(_failures(db)) == 1

    def test_the_pruning_keeps_the_failures_a_lock_still_needs(self, db):
        _seed(db, 26, 23, 20, 17, 14)  # the lock runs for another minute and needs all five

        assert db.add_ui_login_failure("bob", "198.51.100.7", retention=WINDOW + LOCKOUT) == ""

        assert len(_failures(db)) == 6
        assert _lock(db) > 0

    def test_a_read_only_database_cannot_count(self, db):
        db.readonly = True

        assert "read-only" in db.add_ui_login_failure("alice", IP, retention=WINDOW + LOCKOUT)
        assert "read-only" in db.clear_ui_login_failures("alice")
        assert _failures(db) == []


class TestClear:
    def test_clearing_forgets_one_username_only(self, db):
        _fail(db, 3, "alice")
        _fail(db, 2, "bob", "198.51.100.7")

        assert db.clear_ui_login_failures("Alice ") == ""

        assert {name for name, _ in _failures(db)} == {"bob"}


class TestCleanup:
    """The daily `cleanup-expired-ui-sessions` job is the backstop for rows the throttle stopped pruning (LOGIN_THROTTLE=no)."""

    def test_rows_older_than_the_cap_go_and_recent_ones_stay(self, db):
        _seed(db, 60 * 24 * 9, 60 * 24 * 8, 5)

        assert db.cleanup_expired_ui_sessions(7) == "Removed 0 expired UI user sessions"

        assert len(_failures(db)) == 1

    def test_a_read_only_database_reports_instead_of_removing(self, db):
        _seed(db, 60 * 24 * 9)
        db.readonly = True

        assert "read-only" in db.cleanup_expired_ui_sessions(7)
        assert len(_failures(db)) == 1
