"""Execute main.py hooks without booting its container-only application."""

import ast
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from flask import Flask, jsonify, request

MAIN = Path(__file__).resolve().parents[3] / "src/ui/main.py"


def test_signed_in_large_multipart_field_passes_csrf_parser():
    app = Flask(__name__)
    app.secret_key = "test"
    app.config.update(MAX_CONTENT_LENGTH=2_000_000, WTF_CSRF_ENABLED=False)
    tree = ast.parse(MAIN.read_text())
    # Execute the production limit hook and its registration, if present.
    nodes = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == "lift_form_field_limit"]
    registrations = [node for node in ast.walk(tree) if isinstance(node, ast.Expr) and "insert(0, lift_form_field_limit)" in ast.unparse(node)]
    namespace = {"app": app, "request": request, "current_user": SimpleNamespace(is_authenticated=True)}

    @app.before_request
    def parse_like_csrf():
        request.form.get("csrf_token")

    exec(compile(ast.Module(body=nodes + registrations, type_ignores=[]), str(MAIN), "exec"), namespace)

    app.add_url_rule("/edit", view_func=lambda: str(len(request.form["value"])), methods=["POST"])
    client = app.test_client()
    response = client.post("/edit", data={"value": "x" * 600_000}, content_type="multipart/form-data")
    assert response.status_code == 200
    assert response.data == b"600000"
    namespace["current_user"].is_authenticated = False
    assert client.post("/edit", data={"value": "x" * 600_000}, content_type="multipart/form-data").status_code == 413
    namespace["current_user"].is_authenticated = True
    assert client.post("/edit", data={"value": "x" * 2_100_000}, content_type="multipart/form-data").status_code == 413


@pytest.mark.parametrize("body_cleared_state", [False, True])
@pytest.mark.parametrize("current_time", [100, 200])
def test_loading_waits_for_a_task_while_scheduler_metadata_is_idle(body_cleared_state, current_time):
    tree = ast.parse(MAIN.read_text())
    node = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "check_reloading")
    node.decorator_list = []
    data = {"RELOADING": not body_cleared_state, "LAST_RELOAD": 97}
    data = type("Data", (dict,), {"load_from_file": lambda self: None})(data)
    namespace = {
        "DATA": data,
        "time": lambda: current_time,
        "API_CLIENT": Mock(),
        "active_config_tasks": lambda: 1,
        "jsonify": jsonify,
        "LOGGER": Mock(),
        "flash": Mock(),
        "translated": lambda *_args: None,
    }
    namespace["API_CLIENT"].get_metadata.return_value = {}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(MAIN), "exec"), namespace)
    with Flask(__name__).app_context():
        assert namespace["check_reloading"]().json == {"reloading": True}
