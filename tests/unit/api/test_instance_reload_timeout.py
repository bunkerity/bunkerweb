import ast
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[3]
ROUTER_PATH = ROOT / "src" / "api" / "app" / "routers" / "instances.py"


class _Response:
    def __init__(self, *, status_code, content):
        self.status_code = status_code
        self.content = content


def _load_route(name, api_caller_class=None):
    tree = ast.parse(ROUTER_PATH.read_text(encoding="utf-8"))
    timeout = next(
        node
        for node in tree.body
        if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "RELOAD_TIMEOUT" for target in node.targets)
    )
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name)
    function.decorator_list = []
    module = ModuleType(f"instance_{name}_route")
    module.__dict__.update(
        Depends=lambda _dependency: None,
        JSONResponse=_Response,
        get_api_for_hostname=None,
        get_instances_api_caller=None,
        ApiCaller=api_caller_class,
    )
    exec(compile(ast.Module(body=[timeout, function], type_ignores=[]), str(ROUTER_PATH), "exec"), module.__dict__)  # noqa: S102
    return module.__dict__[name]


def test_broadcast_reload_allows_time_for_nginx_confirmation():
    api_caller = Mock()
    api_caller.send_to_apis.return_value = (True, {})

    response = _load_route("reload_config")(True, api_caller)

    assert response.status_code == 200
    api_caller.send_to_apis.assert_called_once_with("POST", "/reload?test=yes", timeout=(5, 30))


def test_single_reload_allows_time_for_nginx_confirmation():
    """DEV-2b6: it goes through ApiCaller now, so the busy 503 below is retried rather than reported."""
    api = Mock()
    api_caller = Mock()
    api_caller.send_to_apis.return_value = (True, {})

    response = _load_route("reload_one", lambda apis: api_caller)("bw-1", True, api)

    assert response.status_code == 200
    api_caller.send_to_apis.assert_called_once_with("POST", "/reload?test=yes", timeout=(5, 30))
    api.request.assert_not_called()


def test_a_single_reload_waits_out_a_busy_instance_instead_of_reporting_it_failed(monkeypatch):
    """An instance holding its configuration-swap lock answers 503; that is busy, not broken.

    This route used to call the raw client, which has no retry, so a reload issued while a routine
    cache push held the lock came back 502 with nothing trying again. The fleet endpoint above never
    had that problem because it goes through `ApiCaller`.
    """
    import ApiCaller as api_caller_module

    monkeypatch.setattr(api_caller_module, "sleep", lambda _seconds: None)

    class _BusyThenReady:
        endpoint = "http://bw-1:5000/"

        def __init__(self):
            self.statuses = [503, 200]

        def request(self, _method, _url, files=None, data=None, timeout=None, **_kwargs):
            status = self.statuses.pop(0)
            return True, "", status, {"msg": "busy" if status == 503 else "ok"}

    api = _BusyThenReady()
    response = _load_route("reload_one", api_caller_module.ApiCaller)("bw-1", True, api)

    assert response.status_code == 200, "a 503 from a busy instance must be retried, not reported as a failed reload"
    assert api.statuses == [], "the retry never fired"
