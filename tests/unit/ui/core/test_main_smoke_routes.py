"""main.py: the app boots for real and serves its small public routes."""

import json


def test_check_endpoint_answers_for_the_setup_wizard(um):
    resp = um.client(None).get("/check")
    assert resp.status_code == 200
    assert json.loads(resp.data) == {"message": "ok"}
    assert resp.headers["Access-Control-Allow-Origin"] == "*"
    assert "connect-src *;" in resp.headers["Content-Security-Policy"]


def test_database_state_check_is_queued_not_run_inside_the_scheduling_lock(um):
    """``schedule_database_state_check`` submits while holding a non-reentrant lock its task takes again; an inline executor deadlocks the request."""
    executor = um.executors["_db_check_executor"]
    um.client(None).get("/check")
    assert len(executor.pending) == 1
    assert um.main._db_check_lock.acquire(blocking=False), "the lock must be free once the request returned"
    um.main._db_check_lock.release()
    executor.run_pending()
    assert um.data["DB_STATE_CHECK_RUNNING"] is False
