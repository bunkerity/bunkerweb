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


def _load_route(name):
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
    api = Mock()
    api.request.return_value = (True, "", 200, {})

    response = _load_route("reload_one")("bw-1", True, api)

    assert response.status_code == 200
    api.request.assert_called_once_with("POST", "/reload?test=yes", timeout=(5, 30))
