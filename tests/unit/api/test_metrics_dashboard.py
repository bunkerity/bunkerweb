"""FastAPI metrics-dashboard router contracts (timeseries/top-offenders/top-rules).

Follows the module-loader + stubbed-``sys.modules`` pattern established by
``test_api_web_cache.py``/``test_api_resource_groups.py`` — there is no live FastAPI
``TestClient`` fixture anywhere in ``tests/unit/api`` (checked before writing this file),
so router functions are called directly against a ``Mock`` db rather than over real HTTP.
"""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

import pytest

ROOT = Path(__file__).resolve().parents[3]


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
        "bw_metrics.utils": ModuleType("bw_metrics.utils"),
    }
    names["fastapi"].APIRouter = _Router
    names["fastapi"].Depends = lambda dependency: dependency
    names["fastapi.responses"].JSONResponse = _Response
    names["bw_metrics"].__path__ = []
    names["bw_metrics.routers"].__path__ = []
    names["bw_metrics.auth"].__path__ = []
    names["bw_metrics.auth.guard"].guard = object()
    names["bw_metrics.utils"].get_db = Mock()
    with patch.dict(sys.modules, names):
        path = ROOT / "src" / "api" / "app" / "routers" / "metrics.py"
        spec = importlib.util.spec_from_file_location("bw_metrics.routers.metrics", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module


ROUTER = _load_router()

EPOCH = 1704067200


@pytest.fixture
def db(monkeypatch):
    fake_db = Mock()
    monkeypatch.setattr(ROUTER, "get_db", lambda: fake_db)
    return fake_db


def test_timeseries_endpoint_returns_buckets(db):
    db.get_metrics_timeseries.return_value = {"buckets": [EPOCH], "counts": [1], "total": 1, "prev_total": 0, "trend_pct": None}

    response = ROUTER.query_metrics_timeseries(start=EPOCH, end=EPOCH + 3600, bucket="hour")

    assert response.status_code == 200
    assert response.content == {"status": "success", "buckets": [EPOCH], "counts": [1], "total": 1, "prev_total": 0, "trend_pct": None}
    db.get_metrics_timeseries.assert_called_once_with(start=EPOCH, end=EPOCH + 3600, bucket="hour", filters={})


def test_timeseries_endpoint_parses_search_panes(db):
    db.get_metrics_timeseries.return_value = {"buckets": [], "counts": [], "total": 0, "prev_total": 0, "trend_pct": None}

    ROUTER.query_metrics_timeseries(start=EPOCH, end=EPOCH + 3600, bucket="day", search_panes="ip:1.2.3.4,5.6.7.8;country:US")

    db.get_metrics_timeseries.assert_called_once_with(start=EPOCH, end=EPOCH + 3600, bucket="day", filters={"ip": ["1.2.3.4", "5.6.7.8"], "country": ["US"]})


def test_timeseries_endpoint_returns_400_not_500_on_oversized_window(db):
    # Regression guard: get_metrics_timeseries raises ValueError for a crafted window that would
    # need too many buckets (authenticated-DoS guard). The endpoint must translate that into a
    # clean 400 response rather than letting it propagate as an unhandled 500.
    db.get_metrics_timeseries.side_effect = ValueError("requested range too large: 50000 buckets exceeds 10000")

    response = ROUTER.query_metrics_timeseries(start=0, end=180000000, bucket="hour")

    assert response.status_code == 400
    assert response.content == {"status": "error", "message": "requested range too large: 50000 buckets exceeds 10000"}


def test_top_offenders_endpoint_returns_400_on_value_error(db):
    db.get_metrics_top_offenders.side_effect = ValueError("start epoch out of range: 10**18")

    response = ROUTER.query_metrics_top_offenders(start=10**18, end=10**18 + 3600)

    assert response.status_code == 400
    assert response.content["status"] == "error"


def test_top_rules_endpoint_returns_400_on_value_error(db):
    db.get_metrics_top_rules.side_effect = ValueError("start epoch out of range: 10**18")

    response = ROUTER.query_metrics_top_rules(start=10**18, end=10**18 + 3600)

    assert response.status_code == 400
    assert response.content["status"] == "error"


def test_top_offenders_endpoint(db):
    db.get_metrics_top_offenders.return_value = [{"ip": "1.2.3.4", "blocks": 3}]

    response = ROUTER.query_metrics_top_offenders(start=EPOCH - 1, end=EPOCH + 3600)

    assert response.status_code == 200
    assert response.content == {"status": "success", "offenders": [{"ip": "1.2.3.4", "blocks": 3}]}
    db.get_metrics_top_offenders.assert_called_once_with(start=EPOCH - 1, end=EPOCH + 3600, limit=10, filters={})


def test_top_rules_endpoint(db):
    db.get_metrics_top_rules.return_value = [{"rule_id": "942100", "count": 1}]

    response = ROUTER.query_metrics_top_rules(start=EPOCH - 1, end=EPOCH + 3600)

    assert response.status_code == 200
    assert response.content == {"status": "success", "rules": [{"rule_id": "942100", "count": 1}]}
    db.get_metrics_top_rules.assert_called_once_with(start=EPOCH - 1, end=EPOCH + 3600, limit=10)
