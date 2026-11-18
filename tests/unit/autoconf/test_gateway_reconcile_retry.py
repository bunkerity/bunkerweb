"""A failed reconciliation stays pending until the retry worker can apply it without another event."""

from types import SimpleNamespace

import pytest
from gateway_fakes import backend, crds, gw, route
from kubernetes.client.exceptions import ApiException

import controllers.KubernetesController as module


class StopLoop(BaseException):
    """Stop a controller loop at its sleep boundary."""


@pytest.fixture
def retry_gateway(gateway_build, monkeypatch, tmp_path):
    obj = route(hostnames=["app.example.com"], rules=[{"backendRefs": [backend()]}])
    ctrl = gateway_build(crds(gateways=[gw()], httproutes=[obj]))
    ctrl._status_enabled = False
    ctrl._debounce_delay = 0
    clock = SimpleNamespace(now=100.0)
    monkeypatch.setattr(module, "time", lambda: clock.now)
    monkeypatch.setattr(module, "HEALTHY_PATH", tmp_path / "healthy")

    def stop_sleep(_seconds):
        # Both the watch backoff and the worker tick must sleep outside the apply lock.
        assert ctrl._internal_lock.acquire(blocking=False)
        ctrl._internal_lock.release()
        raise StopLoop

    monkeypatch.setattr(module, "sleep", stop_sleep)
    return ctrl, clock, {"type": "ADDED", "object": obj}


@pytest.mark.parametrize("entrypoint", ["watch", "idle"])
@pytest.mark.parametrize("failures", [1, 2])
@pytest.mark.parametrize("failure_phase", ["list", "apply", "save_exception", "save_error", "apply_false"])
def test_failed_reconciliation_is_retried_without_new_watch_event(retry_gateway, fake_db, monkeypatch, entrypoint, failures, failure_phase):
    ctrl, clock, event = retry_gateway
    original_list = ctrl.api.list_cluster_custom_object
    attempts = []

    def attempt():
        attempts.append(clock.now)
        if len(attempts) <= failures:
            if failure_phase in ("save_error", "apply_false"):
                return False
            raise ApiException(status=500, reason="temporary reconciliation failure")
        return True

    def flaky_list(group, version, plural, **kwargs):
        if plural == "gateways" and failure_phase == "list":
            attempt()
        return original_list(group, version, plural, **kwargs)

    monkeypatch.setattr(ctrl.api, "list_cluster_custom_object", flaky_list)
    original_apply = ctrl.apply_config

    def flaky_apply():
        if not attempt():
            return False
        return original_apply()

    if failure_phase in ("apply", "apply_false"):
        monkeypatch.setattr(ctrl, "apply_config", flaky_apply)
    original_save = fake_db.save_config

    def flaky_save(*args, **kwargs):
        if not attempt():
            return "temporary save failure"
        return original_save(*args, **kwargs)

    if failure_phase in ("save_exception", "save_error"):
        monkeypatch.setattr(fake_db, "save_config", flaky_save)
    events = []

    def one_event(*_args):
        events.append(event)
        yield event
        raise RuntimeError("watch has no more events")

    monkeypatch.setattr(ctrl, "_get_stream_with_retries", one_event)
    if entrypoint == "watch":
        with pytest.raises(StopLoop):
            ctrl._watch("httproute", None)
        assert events == [event]
    else:
        # The backend worker already queued an apply; discovery fails in its idle path.
        ctrl._pending_apply = True
        ctrl._trigger_apply_if_idle()
        assert events == []

    assert fake_db.saved_configs == []
    assert ctrl._pending_apply is True
    assert ctrl._apply_retry_at == 110.0
    for failure in range(failures):
        # A retry before the cooldown must do nothing, including after a second failed list.
        clock.now += 9
        ctrl._retry_deferred_apply()
        assert fake_db.saved_configs == []
        assert len(attempts) == failure + 1
        clock.now += 1
        with pytest.raises(StopLoop):
            ctrl._pending_backends_worker()

    assert len(attempts) == failures + 1
    assert len(fake_db.saved_configs) == 1
    assert fake_db.saved_configs[0]["SERVER_NAME"] == "app.example.com"
    assert ctrl._pending_apply is False
    assert ctrl._apply_retry_at is None
    # Repeated idle ticks must not publish the successful configuration again.
    clock.now += 10
    ctrl._retry_deferred_apply()
    assert len(fake_db.saved_configs) == 1
    assert len(events) == (1 if entrypoint == "watch" else 0)


@pytest.mark.parametrize("entrypoint", ["watch", "idle"])
def test_successful_apply_does_not_queue_a_retry(retry_gateway, fake_db, monkeypatch, entrypoint):
    ctrl, _, event = retry_gateway

    def one_event(*_args):
        yield event
        raise RuntimeError("watch has no more events")

    monkeypatch.setattr(ctrl, "_get_stream_with_retries", one_event)
    if entrypoint == "watch":
        with pytest.raises(StopLoop):
            ctrl._watch("httproute", None)
    else:
        ctrl._pending_apply = True
        ctrl._trigger_apply_if_idle()

    assert len(fake_db.saved_configs) == 1
    assert ctrl._pending_apply is False
    assert ctrl._apply_retry_at is None


@pytest.mark.parametrize("entrypoint", ["watch", "idle"])
def test_retry_persists_latest_config_after_failure_inside_real_db_save(retry_gateway, db, monkeypatch, entrypoint):
    from sqlalchemy import event as sql_event
    from fixtures.seed import seed_minimal

    seed_minimal(db)
    ctrl, clock, event = retry_gateway
    ctrl._db = db
    # No scheduler runs in this SQLite test to consume the change flags.
    monkeypatch.setattr(ctrl, "wait_applying", lambda: None)
    monkeypatch.setattr(ctrl, "have_to_wait", lambda: False)
    assert ctrl.apply([], [{"SERVER_NAME": "old.example.com"}], configs=ctrl._configs)
    ctrl._loaded = True
    failures = []

    def fail_first_service_insert(_conn, _cursor, statement, _params, _context, _many):
        if statement.lstrip().upper().startswith("INSERT INTO BW_SERVICES ") and not failures:
            failures.append(clock.now)
            raise RuntimeError("temporary DB failure inside save_config")

    def one_event(*_args):
        yield event
        raise RuntimeError("watch has no more events")

    monkeypatch.setattr(ctrl, "_get_stream_with_retries", one_event)
    sql_event.listen(db.sql_engine, "before_cursor_execute", fail_first_service_insert)
    try:
        if entrypoint == "watch":
            with pytest.raises(StopLoop):
                ctrl._watch("httproute", None)
        else:
            ctrl._pending_apply = True
            ctrl._trigger_apply_if_idle()
        assert failures == [100.0]
        assert ctrl._pending_apply is True
        assert ctrl._apply_retry_at == 110.0
        assert "app.example.com" not in {service["id"] for service in db.get_services()}
        clock.now += 9
        ctrl._retry_deferred_apply()
        assert "app.example.com" not in {service["id"] for service in db.get_services()}
        clock.now += 1
        with pytest.raises(StopLoop):
            ctrl._pending_backends_worker()
        assert "app.example.com" in {service["id"] for service in db.get_services()}
        assert "old.example.com" not in {service["id"] for service in db.get_services()}
        assert db.get_config()["app.example.com_USE_REVERSE_PROXY"] == "yes"
        assert ctrl._pending_apply is False
        assert ctrl._apply_retry_at is None
    finally:
        sql_event.remove(db.sql_engine, "before_cursor_execute", fail_first_service_insert)


@pytest.mark.parametrize("error", [ApiException(status=500, reason="watch unavailable"), RuntimeError("watch disconnected")])
def test_watch_stream_failure_does_not_queue_an_apply(retry_gateway, fake_db, monkeypatch, error):
    ctrl, _, _ = retry_gateway

    def failed_stream(*_args):
        raise error

    monkeypatch.setattr(ctrl, "_get_stream_with_retries", failed_stream)
    with pytest.raises(StopLoop):
        ctrl._watch("httproute", None)

    assert ctrl._pending_apply is False
    assert ctrl._apply_retry_at is None
    assert fake_db.saved_configs == []
