"""GET /metrics/threatmap — the one call the /threatmap page makes.

Same module-loader + stubbed-``sys.modules`` pattern as ``test_metrics_dashboard.py``: there is
no live FastAPI ``TestClient`` fixture in ``tests/unit/api``, so the router function is called
directly against a ``Mock`` db.

What matters here is the two guards the DB layer cannot apply, because both are about a caller
rather than about the data: the window bound (the only thing limiting a scan whose ``country``
GROUP BY has no index behind it) and the recent-row clamp.
"""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

import pytest

ROOT = Path(__file__).resolve().parents[3]

EPOCH = 1704067200
DAY = 86400

PAYLOAD = {
    "count": 3,
    "by_country": [{"name": "US", "count": 2}, {"name": "FR", "count": 1}],
    "by_server": [{"name": "app.example.com", "count": 3}],
    "by_reason": [{"name": "blacklist", "count": 3}],
    "recent": [{"request_id": "r1", "country": "US"}],
}


class _Router:
    def __init__(self, **_kwargs):
        pass

    def get(self, *_args, **_kwargs):
        return lambda function: function


class _Response:
    def __init__(self, *, status_code, content):
        self.status_code = status_code
        self.content = content


def _load_router():
    names = {
        "fastapi": ModuleType("fastapi"),
        "fastapi.responses": ModuleType("fastapi.responses"),
        "bw_metrics": ModuleType("bw_metrics"),
        "bw_metrics.routers": ModuleType("bw_metrics.routers"),
        "bw_metrics.auth": ModuleType("bw_metrics.auth"),
        "bw_metrics.auth.guard": ModuleType("bw_metrics.auth.guard"),
        "bw_metrics.deps": ModuleType("bw_metrics.deps"),
        "bw_metrics.utils": ModuleType("bw_metrics.utils"),
    }
    names["fastapi"].APIRouter = _Router
    names["fastapi"].Depends = lambda dependency: dependency
    names["fastapi.responses"].JSONResponse = _Response
    names["bw_metrics"].__path__ = []
    names["bw_metrics.routers"].__path__ = []
    names["bw_metrics.auth"].__path__ = []
    names["bw_metrics.auth.guard"].guard = object()
    names["bw_metrics.deps"].get_instances_api_caller = object()
    names["bw_metrics.utils"].get_db = Mock()
    with patch.dict(sys.modules, names):
        path = ROOT / "src" / "api" / "app" / "routers" / "metrics.py"
        spec = importlib.util.spec_from_file_location("bw_metrics.routers.metrics", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module


ROUTER = _load_router()


@pytest.fixture
def db(monkeypatch):
    fake_db = Mock()
    fake_db.get_metrics_threatmap.return_value = dict(PAYLOAD)
    monkeypatch.setattr(ROUTER, "get_db", lambda: fake_db)
    return fake_db


def test_it_answers_everything_the_page_paints_in_one_call(db):
    response = ROUTER.query_metrics_threatmap(start=EPOCH, end=EPOCH + DAY)

    assert response.status_code == 200
    assert response.content == {"status": "success", **PAYLOAD}
    db.get_metrics_threatmap.assert_called_once_with(start=EPOCH, end=EPOCH + DAY, recent_limit=50, facet_limit=25, filters={})


def test_it_parses_search_panes_like_the_other_metrics_routes(db):
    ROUTER.query_metrics_threatmap(start=EPOCH, end=EPOCH + DAY, search_panes="server_name:app.example.com")

    assert db.get_metrics_threatmap.call_args.kwargs["filters"] == {"server_name": ["app.example.com"]}


class TestGuards:
    def test_an_inverted_window_is_rejected(self, db):
        """``end <= start`` reaches the DB as an empty BETWEEN and answers 200 with zeroes — an
        operator would read that as "nothing was blocked" rather than "your range is backwards"."""
        response = ROUTER.query_metrics_threatmap(start=EPOCH + DAY, end=EPOCH)

        assert response.status_code == 400
        assert db.get_metrics_threatmap.call_count == 0

    def test_an_empty_window_is_rejected(self, db):
        response = ROUTER.query_metrics_threatmap(start=EPOCH, end=EPOCH)

        assert response.status_code == 400
        assert db.get_metrics_threatmap.call_count == 0

    def test_an_oversized_window_is_refused_before_it_reaches_the_database(self, db):
        """``date`` is the only index this query can lean on and ``country`` has none, so an
        unbounded window is a whole-table GROUP BY an authenticated caller could ask for at will."""
        response = ROUTER.query_metrics_threatmap(start=0, end=ROUTER.MAX_THREATMAP_WINDOW_SECONDS + 1)

        assert response.status_code == 400
        assert "window too large" in response.content["message"]
        assert db.get_metrics_threatmap.call_count == 0

    def test_the_largest_allowed_window_still_goes_through(self, db):
        """Off-by-one guard: the cap is inclusive, so a 31-day window must not be refused."""
        response = ROUTER.query_metrics_threatmap(start=EPOCH, end=EPOCH + ROUTER.MAX_THREATMAP_WINDOW_SECONDS)

        assert response.status_code == 200
        assert db.get_metrics_threatmap.call_count == 1

    def test_the_recent_limit_is_clamped_both_ways(self, db):
        """``limit`` becomes a LIMIT on a row SELECT. Unclamped, one request can pull the whole
        window into memory and back out over HTTP."""
        ROUTER.query_metrics_threatmap(start=EPOCH, end=EPOCH + DAY, limit=100000)
        assert db.get_metrics_threatmap.call_args.kwargs["recent_limit"] == 200

        ROUTER.query_metrics_threatmap(start=EPOCH, end=EPOCH + DAY, limit=0)
        assert db.get_metrics_threatmap.call_args.kwargs["recent_limit"] == 1

        ROUTER.query_metrics_threatmap(start=EPOCH, end=EPOCH + DAY, limit=-5)
        assert db.get_metrics_threatmap.call_args.kwargs["recent_limit"] == 1

    def test_the_facet_limit_is_clamped_both_ways(self, db):
        """Each facet row is a distinct service or reason. Unclamped, a caller can ask a large
        deployment to serialise thousands of them on every 30 s poll."""
        ROUTER.query_metrics_threatmap(start=EPOCH, end=EPOCH + DAY, facet_limit=100000)
        assert db.get_metrics_threatmap.call_args.kwargs["facet_limit"] == 100

        ROUTER.query_metrics_threatmap(start=EPOCH, end=EPOCH + DAY, facet_limit=0)
        assert db.get_metrics_threatmap.call_args.kwargs["facet_limit"] == 1

    def test_a_bad_epoch_is_a_400_not_a_500(self, db):
        db.get_metrics_threatmap.side_effect = ValueError("end epoch out of range: 10**20")

        response = ROUTER.query_metrics_threatmap(start=EPOCH, end=EPOCH + DAY)

        assert response.status_code == 400
        assert response.content == {"status": "error", "message": "end epoch out of range: 10**20"}
