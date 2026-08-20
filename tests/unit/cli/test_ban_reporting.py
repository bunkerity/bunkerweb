"""What `bwcli ban` / `bwcli unban` report, and whether it matches what actually happened.

Two failures, and the second one only exists on 1.7.

`ApiCaller.send_to_apis` returns `(ok, responses)`. `if self.send_to_apis(...)` tests the tuple,
which is always truthy, so every ban and unban reported success -- including one that reached no
instance at all. And with `self.apis` empty the executor loop never runs, so `ret` comes back True:
a vacuous success on top of a vacuous test.

The report itself has to follow 1.7's model rather than 1.6's. Bans live in the database with a
`sync-bans` job that pushes them out (`core/jobs/jobs/sync-bans.py:139` for bans, `:214` for
revokes), so a persisted ban whose push failed is *recorded and converging*, not failed. Saying
"failed" there would be a truthful sentence about the wrong model.
"""

import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

_ROOT = Path(__file__).resolve().parents[3]
for _p in (_ROOT / "src" / "common" / "cli", _ROOT / "src" / "common" / "api", _ROOT / "src" / "common" / "utils", _ROOT / "src" / "common" / "db"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from CLI import CLI  # noqa: E402


def _cli(*, db=None, apis=(), push_ok=True):
    """A CLI without __init__ -- __init__ opens a database, Redis and a terminal."""
    cli = object.__new__(CLI)
    cli._CLI__db = db
    cli._CLI__logger = Mock()
    cli._CLI__terminal_width = 80
    cli.apis = list(apis)
    cli.send_to_apis = Mock(return_value=(push_ok, {}))
    return cli


def _db(*, upsert_error=None, revoke_error=None):
    db = Mock()
    db.upsert_ban.return_value = upsert_error
    db.revoke_ban.return_value = revoke_error
    return db


class TestTheTupleWasAlwaysTruthy:
    def test_a_failed_push_with_no_database_is_not_reported_as_a_ban(self):
        cli = _cli(db=None, apis=[Mock()], push_ok=False)
        ok, message = cli.ban("10.0.0.1", 0, "testing")
        assert ok is False
        assert "Failed to ban" in message

    def test_a_failed_push_with_no_database_is_not_reported_as_an_unban(self):
        cli = _cli(db=None, apis=[Mock()], push_ok=False)
        ok, message = cli.unban("10.0.0.1")
        assert ok is False
        assert "Failed to unban" in message

    def test_a_successful_push_still_reports_success(self):
        cli = _cli(db=None, apis=[Mock()], push_ok=True)
        ok, message = cli.ban("10.0.0.1", 0, "testing")
        assert ok is True
        assert "has been banned" in message


class TestNoInstanceToTalkTo:
    """`send_to_apis` returns ret=True when `self.apis` is empty: the loop never runs."""

    def test_banning_with_no_instance_and_no_database_fails_loudly(self):
        cli = _cli(db=None, apis=[])
        ok, message = cli.ban("10.0.0.1", 0, "testing")
        assert ok is False
        assert "no BunkerWeb instance" in message
        cli.send_to_apis.assert_not_called()

    def test_unbanning_with_no_instance_and_no_database_fails_loudly(self):
        cli = _cli(db=None, apis=[])
        ok, message = cli.unban("10.0.0.1")
        assert ok is False
        assert "no BunkerWeb instance" in message
        cli.send_to_apis.assert_not_called()


class TestTheDatabaseIsWhatMakesItDurable:
    """1.7 only. A persisted ban converges through sync-bans, so a failed push is not a failure --
    but the operator has to be told the instances have not applied it yet."""

    def test_a_persisted_ban_with_no_reachable_instance_succeeds_with_a_caveat(self):
        cli = _cli(db=_db(), apis=[])
        ok, message = cli.ban("10.0.0.1", 0, "testing")
        assert ok is True
        assert "has been banned" in message
        assert "ban sync will push it" in message

    def test_a_persisted_ban_whose_push_failed_succeeds_with_a_caveat(self):
        cli = _cli(db=_db(), apis=[Mock()], push_ok=False)
        ok, message = cli.ban("10.0.0.1", 0, "testing")
        assert ok is True
        assert "ban sync will push it" in message

    def test_a_ban_the_database_refused_and_the_push_failed_is_a_failure(self):
        cli = _cli(db=_db(upsert_error="disk full"), apis=[Mock()], push_ok=False)
        ok, message = cli.ban("10.0.0.1", 0, "testing")
        assert ok is False
        assert "Failed to ban" in message

    def test_a_successful_push_carries_no_caveat(self):
        cli = _cli(db=_db(), apis=[Mock()], push_ok=True)
        ok, message = cli.ban("10.0.0.1", 0, "testing")
        assert ok is True
        assert "ban sync will push it" not in message

    def test_a_revoke_the_database_refused_is_a_failure_even_if_the_push_would_work(self):
        """Refusing a non-durable revoke is deliberate: without the tombstone, sync-bans re-learns
        the ban from an instance that missed this unban and pushes it straight back."""
        cli = _cli(db=_db(revoke_error="locked"), apis=[Mock()], push_ok=True)
        ok, message = cli.unban("10.0.0.1")
        assert ok is False
        assert "locked" in message
        cli.send_to_apis.assert_not_called()

    def test_a_tombstoned_revoke_whose_push_failed_succeeds_with_a_caveat(self):
        cli = _cli(db=_db(), apis=[Mock()], push_ok=False)
        ok, message = cli.unban("10.0.0.1")
        assert ok is True
        assert "has been unbanned" in message
        assert "ban sync will push it" in message


class TestBansListingWasNotRegressed:
    """dev's third hunk adds `or not resp` to the `bans()` guard. 1.7 must NOT take it: 1.7 already
    prefers the database and falls back to it when the instances answer nothing, and `or not resp`
    would turn a database-only listing back into an error."""

    def test_the_database_still_answers_when_the_instances_do_not(self):
        db = Mock()
        db.get_bans.return_value = [{"ip": "10.0.0.1", "ban_scope": "global", "reason": "testing", "exp": 0, "date": 0, "service": "bwcli"}]
        cli = _cli(db=db, apis=[])
        cli.send_to_apis = Mock(return_value=(False, None))
        cli._CLI__redis = None
        ok, _ = cli.bans()
        assert ok is True, "a database-only ban listing must not report failure"

    def test_it_still_fails_when_nothing_at_all_answers(self):
        db = Mock()
        db.get_bans.return_value = []
        cli = _cli(db=db, apis=[])
        cli.send_to_apis = Mock(return_value=(False, None))
        cli._CLI__redis = None
        ok, message = cli.bans()
        assert ok is False
        assert "Failed to retrieve ban information" in message


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
