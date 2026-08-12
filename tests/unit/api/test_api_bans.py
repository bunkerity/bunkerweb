"""FastAPI /bans read contract.

Since bans became durable, ``GET /bans`` answers from the database — an instance that just
restarted enumerates an empty shared dict, so the fan-out it replaced under-reported. The old
runtime view is still reachable, unchanged, at ``GET /bans/instances``; these tests pin both
shapes so the split cannot silently collapse back into one.
"""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[3]


class _Router:
    def __init__(self, **_kwargs):
        pass

    def get(self, *_args, **_kwargs):
        return lambda function: function

    post = get
    delete = get


class _Response:
    def __init__(self, *, status_code, content):
        self.status_code = status_code
        self.content = content


DB = SimpleNamespace(get_bans=lambda **_kwargs: [])


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
    names["bw_bans"].__path__ = []
    names["bw_bans.routers"].__path__ = []
    names["bw_bans.auth"].__path__ = []
    names["bw_bans.auth.guard"].guard = object()
    names["bw_bans.deps"].get_instances_api_caller = object()
    names["bw_bans.schemas"].BanRequest = object()
    names["bw_bans.schemas"].UnbanRequest = object()
    names["bw_bans.utils"].get_db = lambda: DB
    names["bw_bans.utils"].LOGGER = Mock()
    with patch.dict(sys.modules, names):
        path = ROOT / "src" / "api" / "app" / "routers" / "bans.py"
        spec = importlib.util.spec_from_file_location("bw_bans.routers.bans", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module


ROUTER = _load_router()


def _ban(ip="1.2.3.4", **over):
    return {
        "ip": ip,
        "reason": "manual",
        "service": "unknown",
        "date": 1704067200,
        "country": "FR",
        "ban_scope": "global",
        "exp": 3600,
        "expires_at": 1704070800,
        "permanent": False,
        "reason_data": {},
    } | over


def test_list_bans_reads_the_database():
    DB.get_bans = Mock(return_value=[_ban()])

    response = ROUTER.list_bans()

    assert response.status_code == 200
    assert response.content == {"status": "success", "data": [_ban()]}
    DB.get_bans.assert_called_once_with()


def test_list_bans_does_not_touch_the_instances():
    # The whole point of the cutover: a restarted instance reports nothing, so asking it would
    # make a durable ban disappear from the list.
    DB.get_bans = Mock(return_value=[])
    assert ROUTER.list_bans().content == {"status": "success", "data": []}


def test_instance_view_keeps_the_pre_1_7_fanout_shape():
    caller = Mock()
    caller.send_to_apis.return_value = (True, {"bw-1": {"status": "success", "msg": [_ban()]}})

    response = ROUTER.list_instance_bans(caller)

    assert response.status_code == 200
    assert response.content == {"bw-1": {"status": "success", "msg": [_ban()]}}
    caller.send_to_apis.assert_called_once_with("GET", "/bans", response=True)


def test_instance_view_reports_502_when_an_instance_fails():
    caller = Mock()
    caller.send_to_apis.return_value = (False, {})

    response = ROUTER.list_instance_bans(caller)

    assert response.status_code == 502
    assert response.content == {"status": "error", "msg": "internal error"}


def _payload(**over):
    return SimpleNamespace(model_dump=lambda: {"ip": "1.2.3.4", "exp": 3600, "reason": "api", "service": None} | over)


def _caller(ok=True):
    caller = Mock()
    caller.send_to_apis.return_value = (ok, {})
    return caller


def test_ban_persists_before_fanning_out():
    DB.upsert_ban = Mock(return_value="")
    caller = _caller()

    response = ROUTER.ban([_payload()], caller)

    assert response.status_code == 200
    kwargs = DB.upsert_ban.call_args.kwargs
    assert DB.upsert_ban.call_args.args == ("1.2.3.4",)
    assert (kwargs["ban_scope"], kwargs["reason"], kwargs["origin"]) == ("global", "api", "api")
    assert kwargs["expires_at"] is not None
    caller.send_to_apis.assert_called_once()


def test_ban_with_exp_zero_is_stored_as_permanent():
    # exp == 0 is the wire's "permanent"; a stored TTL of 0 would instead read as "already expired".
    DB.upsert_ban = Mock(return_value="")
    ROUTER.ban([_payload(exp=0)], _caller())
    assert DB.upsert_ban.call_args.kwargs["expires_at"] is None


def test_ban_still_reaches_the_instances_when_the_database_write_fails():
    # Losing durability is bad; leaving an attacker unblocked is worse. This is the pre-1.7 path.
    DB.upsert_ban = Mock(return_value="database is read-only")
    caller = _caller()

    response = ROUTER.ban([_payload()], caller)

    assert response.status_code == 200
    caller.send_to_apis.assert_called_once()


def test_unban_is_refused_when_the_revoke_cannot_be_persisted():
    # Without the tombstone the convergence job re-learns the ban from an instance that missed
    # this unban and re-pushes it to the fleet, silently undoing the operator.
    DB.revoke_ban = Mock(return_value="database is read-only")
    caller = _caller()

    response = ROUTER.unban([_payload()], caller)

    assert response.status_code == 502
    caller.send_to_apis.assert_not_called()


def test_unban_revokes_then_fans_out():
    DB.revoke_ban = Mock(return_value="")
    caller = _caller()

    response = ROUTER.unban([_payload()], caller)

    assert response.status_code == 200
    assert DB.revoke_ban.call_args.kwargs["ban_scope"] == "global"
    caller.send_to_apis.assert_called_once()


def test_service_scope_is_derived_and_passed_through():
    DB.upsert_ban = Mock(return_value="")
    ROUTER.ban([_payload(service="app.example.com")], _caller())
    kwargs = DB.upsert_ban.call_args.kwargs
    assert (kwargs["ban_scope"], kwargs["service_id"]) == ("service", "app.example.com")


def test_reserved_service_names_fall_back_to_a_global_ban():
    DB.upsert_ban = Mock(return_value="")
    ROUTER.ban([_payload(service="Web UI")], _caller())
    kwargs = DB.upsert_ban.call_args.kwargs
    assert (kwargs["ban_scope"], kwargs["service_id"]) == ("global", "")
