"""The jobs last-run endpoint exposes one job's newest persisted run."""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

import pytest

ROOT = Path(__file__).resolve().parents[3]


class _Router:
    def __init__(self, **_kwargs):
        self.get_routes = []

    def get(self, path, **kwargs):
        self.get_routes.append((path, kwargs))
        return lambda function: function

    def post(self, *_args, **_kwargs):
        return lambda function: function


class _Response:
    def __init__(self, *, status_code, content):
        self.status_code = status_code
        self.content = content


def _load_router():
    names = {
        "fastapi": ModuleType("fastapi"),
        "fastapi.responses": ModuleType("fastapi.responses"),
        "job_queues": ModuleType("job_queues"),
        "bw_jobs": ModuleType("bw_jobs"),
        "bw_jobs.routers": ModuleType("bw_jobs.routers"),
        "bw_jobs.celery_app": ModuleType("bw_jobs.celery_app"),
        "bw_jobs.schemas": ModuleType("bw_jobs.schemas"),
        "bw_jobs.auth": ModuleType("bw_jobs.auth"),
        "bw_jobs.auth.guard": ModuleType("bw_jobs.auth.guard"),
        "bw_jobs.utils": ModuleType("bw_jobs.utils"),
    }
    names["fastapi"].APIRouter = _Router
    names["fastapi"].Depends = lambda dependency: dependency
    names["fastapi.responses"].JSONResponse = _Response
    names["job_queues"].queue_for = Mock()
    names["bw_jobs"].__path__ = []
    names["bw_jobs.routers"].__path__ = []
    names["bw_jobs.auth"].__path__ = []
    names["bw_jobs.celery_app"].get_celery_app = Mock()
    names["bw_jobs.schemas"].DispatchJobsRequest = object
    names["bw_jobs.schemas"].RunJobsRequest = object
    names["bw_jobs.auth.guard"].guard = object()
    names["bw_jobs.utils"].get_db = Mock()

    with patch.dict(sys.modules, names):
        path = ROOT / "src" / "api" / "app" / "routers" / "jobs.py"
        spec = importlib.util.spec_from_file_location("bw_jobs.routers.jobs", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module


ROUTER = _load_router()


@pytest.fixture
def db(monkeypatch):
    fake_db = Mock()
    monkeypatch.setattr(ROUTER, "get_db", lambda: fake_db)
    return fake_db


def test_last_run_endpoint_returns_the_named_jobs_newest_run(db):
    last_run = {
        "success": False,
        "start_date": "2024-01-01T00:00:00+00:00",
        "end_date": "2024-01-01T00:01:00+00:00",
    }
    db.get_last_job_run.return_value = last_run

    response = ROUTER.get_last_job_run("push-configs")

    assert response.status_code == 200
    assert response.content == {"status": "success", "last_run": last_run}
    db.get_last_job_run.assert_called_once_with("push-configs")


def test_last_run_route_uses_the_same_auth_guard_as_its_siblings():
    route = next(kwargs for path, kwargs in ROUTER.router.get_routes if path == "/{name}/last-run")

    assert route["dependencies"] == [ROUTER.guard]
