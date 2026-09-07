"""The cache push has to be given time proportional to what it uploads.

`send_files` gzip-tars the WHOLE `/var/cache/bunkerweb` tree, and its read budget used to be the
flat `(5, 30)` default: a fleet with a hundred services regularly needs longer, and the push failed
on the timeout with every file already built. Port of dev `462c1e851`.

The service count is read from the DATABASE, with the environment as the fallback: a
split-container worker has no `SERVER_NAME` of its own, so an env-only count left exactly the
deployments this budget is for on the floor.
"""

from unittest.mock import Mock, patch

from test_delivery_guarantees import LOGGER, TASKS


def test_the_count_comes_from_the_database():
    db = Mock()
    db.get_services.return_value = [{"id": f"svc-{i}"} for i in range(40)]

    with patch.object(TASKS, "get_worker_db", return_value=db):
        assert TASKS._push_service_count(LOGGER) == 40


def test_the_environment_is_only_the_fallback(monkeypatch):
    """A worker that cannot reach the database still sizes the push from what it does know."""
    db = Mock()
    db.get_services.return_value = []
    monkeypatch.setenv("SERVER_NAME", "a.example.com b.example.com c.example.com")

    with patch.object(TASKS, "get_worker_db", return_value=db):
        assert TASKS._push_service_count(LOGGER) == 3


def test_a_database_failure_is_not_a_push_failure(monkeypatch):
    monkeypatch.delenv("SERVER_NAME", raising=False)

    with patch.object(TASKS, "get_worker_db", side_effect=RuntimeError("database is locked")):
        assert TASKS._push_service_count(LOGGER) == 0


def test_the_budget_the_worker_asks_for_grows_with_the_fleet(monkeypatch):
    """End to end: 40 services must not be pushed with the same 30 s as one."""
    from ApiCaller import folder_push_timeout  # the helper the worker calls

    monkeypatch.delenv("SERVER_NAME", raising=False)
    db = Mock()
    db.get_services.return_value = [{"id": f"svc-{i}"} for i in range(40)]

    with patch.object(TASKS, "get_worker_db", return_value=db):
        assert folder_push_timeout(30, TASKS._push_service_count(LOGGER)) == (5, 120)

    db.get_services.return_value = [{"id": "only-one"}]
    with patch.object(TASKS, "get_worker_db", return_value=db):
        assert folder_push_timeout(30, TASKS._push_service_count(LOGGER)) == (5, 30), "a small install must keep the previous budget"


def test_the_reload_lock_outlives_the_widest_push():
    """A lock that expires mid-push lets a second worker child push concurrently."""
    assert TASKS.RELOAD_LOCK_TTL >= 5 + 120 + 5 + TASKS.RELOAD_TIMEOUT[1], "the lock can expire while the holder is still uploading"
