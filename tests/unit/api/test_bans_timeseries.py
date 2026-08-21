"""``GET /bans/timeseries`` — the router contract and its ACL resolution (#3820).

Two halves, deliberately in one file because the whole point of the endpoint is that it needed
*no* ACL plumbing: the router half uses the stubbed-``sys.modules`` loader of
``test_metrics_dashboard.py`` (there is still no live ``TestClient`` fixture under
``tests/unit/api``), the ACL half uses the AST-exec loader of ``test_instances_acl.py``.
"""

import ast
import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Optional
from unittest.mock import Mock, patch

import pytest

ROOT = Path(__file__).resolve().parents[3]
BISCUIT = ROOT / "src" / "api" / "app" / "auth" / "biscuit.py"

EPOCH = 1704067200
SERIES = {"buckets": [EPOCH], "counts": [3], "total": 3, "prev_total": 1, "trend_pct": 200.0}


class _Router:
    def __init__(self, **_kwargs):
        pass

    def get(self, *_args, **_kwargs):
        return lambda function: function

    post = delete = get


class _Response:
    def __init__(self, *, status_code, content):
        self.status_code = status_code
        self.content = content


def _load_router():
    names = {
        "fastapi": ModuleType("fastapi"),
        "fastapi.responses": ModuleType("fastapi.responses"),
        "bw_bans": ModuleType("bw_bans"),
        "bw_bans.routers": ModuleType("bw_bans.routers"),
        "bw_bans.auth": ModuleType("bw_bans.auth"),
        "bw_bans.auth.guard": ModuleType("bw_bans.auth.guard"),
        "bw_bans.deps": ModuleType("bw_bans.deps"),
        "bw_bans.schemas": ModuleType("bw_bans.schemas"),
        "bw_bans.utils": ModuleType("bw_bans.utils"),
    }
    names["fastapi"].APIRouter = _Router
    names["fastapi"].Depends = lambda dependency: dependency
    names["fastapi.responses"].JSONResponse = _Response
    for package in ("bw_bans", "bw_bans.routers", "bw_bans.auth"):
        names[package].__path__ = []
    names["bw_bans.auth.guard"].guard = object()
    names["bw_bans.deps"].get_instances_api_caller = object()
    names["bw_bans.schemas"].BanRequest = object
    names["bw_bans.schemas"].UnbanRequest = object
    names["bw_bans.utils"].LOGGER = Mock()
    names["bw_bans.utils"].get_db = Mock()
    with patch.dict(sys.modules, names):
        path = ROOT / "src" / "api" / "app" / "routers" / "bans.py"
        spec = importlib.util.spec_from_file_location("bw_bans.routers.bans", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module


ROUTER = _load_router()


@pytest.fixture
def db(monkeypatch):
    fake_db = Mock()
    monkeypatch.setattr(ROUTER, "get_db", lambda: fake_db)
    return fake_db


class TestEndpoint:
    def test_it_returns_the_series_the_db_produced(self, db):
        db.get_bans_timeseries.return_value = SERIES

        response = ROUTER.query_bans_timeseries(start=EPOCH, end=EPOCH + 3600, bucket="hour")

        assert response.status_code == 200
        assert response.content == {"status": "success", **SERIES}
        db.get_bans_timeseries.assert_called_once_with(start=EPOCH, end=EPOCH + 3600, bucket="hour")

    def test_bucket_defaults_to_hour(self, db):
        db.get_bans_timeseries.return_value = SERIES

        ROUTER.query_bans_timeseries(start=EPOCH, end=EPOCH + 3600)

        assert db.get_bans_timeseries.call_args.kwargs["bucket"] == "hour"

    def test_an_oversized_window_is_a_400_not_a_500(self, db):
        # The bucket guard is an authenticated-DoS guard: it must surface as a client error,
        # not as an unhandled exception the way a bare `raise` through FastAPI would.
        db.get_bans_timeseries.side_effect = ValueError("requested range too large: 50000 buckets exceeds 10000")

        response = ROUTER.query_bans_timeseries(start=0, end=180000000, bucket="hour")

        assert response.status_code == 400
        assert response.content == {"status": "error", "message": "requested range too large: 50000 buckets exceeds 10000"}

    def test_an_out_of_range_epoch_is_also_a_400(self, db):
        db.get_bans_timeseries.side_effect = ValueError("start epoch out of range: 999999999999999999")

        assert ROUTER.query_bans_timeseries(start=999999999999999999, end=0).status_code == 400

    def test_the_endpoint_is_registered_on_the_bans_prefix(self):
        source = (ROOT / "src" / "api" / "app" / "routers" / "bans.py").read_text(encoding="utf-8")
        assert 'router = APIRouter(prefix="/bans"' in source
        assert '@router.get("/timeseries", dependencies=[Depends(guard)])' in source

    def test_it_is_guarded_like_every_other_bans_route(self):
        """A route registered without ``Depends(guard)`` would be reachable unauthenticated."""
        source = (ROOT / "src" / "api" / "app" / "routers" / "bans.py").read_text(encoding="utf-8")
        decorators = [line for line in source.splitlines() if line.startswith("@router.")]
        assert len(decorators) >= 6  # RULE 13: floor, not equality -- new routes must not empty this
        assert all("Depends(guard)" in line for line in decorators), decorators


# --------------------------------------------------------------------------------------
# ACL — nothing was written for this endpoint; this is what says the fallback covers it
# --------------------------------------------------------------------------------------


def _load_bans_resolver():
    tree = ast.parse(BISCUIT.read_text(encoding="utf-8"), filename=str(BISCUIT))
    nodes = [
        node
        for node in tree.body
        if (isinstance(node, ast.FunctionDef) and node.name == "_resolve_bans")
        or (isinstance(node, ast.Assign) and any(getattr(tgt, "id", None) == "PERM_VERB_BY_METHOD" for tgt in node.targets))
    ]
    namespace = {"Optional": Optional}
    exec(compile(ast.Module(nodes, type_ignores=[]), str(BISCUIT), "exec"), namespace)
    return namespace["_resolve_bans"]


class TestAcl:
    def test_the_new_get_resolves_to_ban_read_through_the_verb_fallback(self):
        assert _load_bans_resolver()("/bans/timeseries", "GET") == ("bans", "ban_read")

    def test_it_resolves_the_same_way_the_other_read_routes_do(self):
        resolve = _load_bans_resolver()
        assert resolve("/bans/timeseries", "GET") == resolve("/bans", "GET") == resolve("/bans/instances", "GET")

    def test_a_write_verb_on_the_same_path_does_not_inherit_read(self):
        """The fallback is per-verb: reading the chart must not become a way to mutate bans."""
        resolve = _load_bans_resolver()
        assert resolve("/bans/timeseries", "POST") == ("bans", "ban_created")
        assert resolve("/bans/timeseries", "DELETE") == ("bans", "ban_delete")
        assert resolve("/bans/timeseries", "PATCH") == ("bans", "ban_update")

    def test_an_unknown_verb_resolves_to_no_permission_rather_than_a_default_grant(self):
        assert _load_bans_resolver()("/bans/timeseries", "TRACE") == ("bans", None)
