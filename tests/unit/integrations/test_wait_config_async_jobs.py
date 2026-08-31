from http import HTTPStatus
from importlib.util import module_from_spec, spec_from_file_location
from io import BytesIO
from json import dumps
from pathlib import Path
from sys import modules
from types import ModuleType
from unittest.mock import patch
from urllib.error import HTTPError

import pytest

ROOT = Path(__file__).resolve().parents[3]
SPEC = spec_from_file_location("wait_config", ROOT / "tests" / "wait_config.py")
WAIT_CONFIG = module_from_spec(SPEC)
REDIS = ModuleType("redis")
REDIS.Redis = type("Redis", (), {})
UTILS = ModuleType("utils")
UTILS.__path__ = []
UTILS.BW_TESTS_ETC = ROOT
UTILS.execute_query = None
UTILS_LOGGER = ModuleType("utils.logger")
UTILS.logger = UTILS_LOGGER
with patch.dict(modules, {"redis": REDIS, "utils": UTILS, "utils.logger": UTILS_LOGGER}):
    SPEC.loader.exec_module(WAIT_CONFIG)


def queue_response(active=None, reserved=None):
    payload = {"active": active or {}, "reserved": reserved or {}}
    return BytesIO(dumps(payload).encode("utf-8"))


@pytest.mark.parametrize("busy_queue", [{"active": {"worker": [{"id": "running"}]}}, {"reserved": {"worker": [{"id": "waiting"}]}}])
def test_settle_waits_for_active_and_reserved_jobs(busy_queue):
    def queue_quiet():
        return WAIT_CONFIG.jobs_queue_quiet(lambda *_args, **_kwargs: queue_response(**busy_queue))

    assert WAIT_CONFIG.settle_ready(2, 1, 0, 1, 5, 5, queue_quiet) is False


def test_settle_accepts_empty_worker_queues(tmp_path, monkeypatch):
    (tmp_path / "variables.env").write_text("API_TOKEN=action-token\n", encoding="utf-8")
    monkeypatch.setattr(WAIT_CONFIG, "BW_TESTS_ETC", tmp_path)

    def opener(request, timeout):
        assert request.full_url == "http://127.0.0.1:8888/jobs/queue"
        assert request.get_header("Authorization") == "Bearer action-token"
        assert timeout == 15
        return queue_response(active={"worker": []}, reserved={"worker": []})

    assert WAIT_CONFIG.settle_ready(2, 1, 0, 1, 5, 5, lambda: WAIT_CONFIG.jobs_queue_quiet(opener)) is True


def test_queue_probe_falls_back_to_the_default_token(tmp_path, monkeypatch):
    monkeypatch.setattr(WAIT_CONFIG, "BW_TESTS_ETC", tmp_path)

    def opener(request, **_kwargs):
        assert request.get_header("Authorization") == "Bearer tests-secret-token"
        return queue_response()

    assert WAIT_CONFIG.jobs_queue_quiet(opener) is True


@pytest.mark.parametrize(
    "error",
    [
        HTTPError("http://127.0.0.1:8888/jobs/queue", HTTPStatus.SERVICE_UNAVAILABLE, "broker not configured", {}, None),
        OSError("API unreachable"),
    ],
)
def test_queue_probe_failure_preserves_the_existing_settle_behavior(error, monkeypatch):
    messages = []
    monkeypatch.setattr(WAIT_CONFIG.LOGGER, "debug", messages.append)

    def unavailable(*_args, **_kwargs):
        raise error

    assert WAIT_CONFIG.settle_ready(2, 1, 0, 1, 5, 5, lambda: WAIT_CONFIG.jobs_queue_quiet(unavailable)) is True
    assert messages and "Queue inspection unavailable" in messages[0]


@pytest.mark.parametrize(("runs", "previous", "pending", "live_instances"), [(1, 1, 0, 1), (2, 1, 1, 1), (2, 1, 0, 0)])
def test_inherited_settle_terms_short_circuit_the_queue_probe(runs, previous, pending, live_instances):
    def unexpected_probe():
        raise AssertionError("queue probe must not run")

    assert WAIT_CONFIG.settle_ready(runs, previous, pending, live_instances, 5, 5, unexpected_probe) is False


def test_queue_probe_waits_for_the_full_settle_window():
    def unexpected_probe():
        raise AssertionError("queue probe must not run")

    assert WAIT_CONFIG.settle_ready(2, 1, 0, 1, 4, 5, unexpected_probe) is False
