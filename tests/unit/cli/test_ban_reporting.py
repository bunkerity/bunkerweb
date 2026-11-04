"""CLI ban and unban reporting against dev's instance-backed ban model."""

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
    """A CLI without __init__: __init__ opens a database, Redis and a terminal."""
    cli = object.__new__(CLI)
    cli._CLI__db = db
    cli._CLI__redis = None
    cli._CLI__logger = Mock()
    cli._CLI__terminal_width = 80
    cli.apis = list(apis)
    cli.send_to_apis = Mock(return_value=(push_ok, {}))
    return cli


def _db(*, upsert_error=None, revoke_error=None):
    db = Mock()
    db.upsert_ban.return_value = upsert_error
    db.revoke_ban.return_value = revoke_error
    db.get_instances.return_value = []
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
    """An empty instance list cannot report a successful push."""

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


class TestBansListingWasNotRegressed:
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
