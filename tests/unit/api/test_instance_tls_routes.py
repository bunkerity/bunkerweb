import ast
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock

import schemas

ROOT = Path(__file__).resolve().parents[3]
ROUTER_PATH = ROOT / "src" / "api" / "app" / "routers" / "instances.py"


class _Response:
    def __init__(self, *, status_code, content):
        self.status_code = status_code
        self.content = content


def _load_update_instance(db):
    tree = ast.parse(ROUTER_PATH.read_text(encoding="utf-8"))
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "update_instance")
    function.decorator_list = []
    module = ModuleType("instance_update_route")
    module.__dict__.update(
        JSONResponse=_Response,
        InstanceUpdateRequest=schemas.InstanceUpdateRequest,
        get_db=lambda: db,
        _validate_port=lambda value: value,
    )
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(ROUTER_PATH), "exec"), module.__dict__)  # noqa: S102
    return module.update_instance


def test_explicit_empty_fingerprint_clears_storage_when_tls_is_off():
    db = Mock()
    db.get_instance.return_value = {"hostname": "bw-1", "tls_mode": "pinned", "tls_fingerprint": "ab" * 32}
    db.update_instance_fields.return_value = ""
    route = _load_update_instance(db)

    response = route("bw-1", schemas.InstanceUpdateRequest(tls_mode="off", tls_fingerprint=""))

    assert response.status_code == 200
    assert db.update_instance_fields.call_args.kwargs["tls_fingerprint"] == ""
