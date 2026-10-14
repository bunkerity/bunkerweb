"""A disallowed Host is rejected before any hook reads the session or the signed-in user (D8).

`lift_form_field_limit` is registered at index 0 and reads `current_user` for every POST; the host check lived in
the big `before_request`, which runs after it, after Biscuit and after the CSRF form parse. The real guard and the
real registrations are executed here from main.py's source, like test_resume_form_tasks.py does.
"""

import ast
from pathlib import Path
from unittest.mock import Mock

from flask import Flask, jsonify, make_response, request

MAIN = Path(__file__).resolve().parents[3] / "src/ui/main.py"
ALLOWED = ["ui.example.com", "*.corp.example.com"]


class _User:
    """Counts every read of `is_authenticated`: what a hostile Host must never trigger."""

    reads = 0

    @property
    def is_authenticated(self):
        type(self).reads += 1
        return True


def _host_allowed(host, allowed):
    return host.split(":", 1)[0].lower() in allowed


def _build(allowed_hosts):
    app = Flask(__name__, static_folder=None)
    app.config.update(MAX_CONTENT_LENGTH=2_000_000, ALLOWED_HOSTS=allowed_hosts)
    tree = ast.parse(MAIN.read_text())
    wanted = {"lift_form_field_limit", "reject_disallowed_host"}
    hooks = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name in wanted]
    registrations = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Expr) and ("insert(0, lift_form_field_limit)" in ast.unparse(node) or "insert(0, reject_disallowed_host)" in ast.unparse(node))
    ]
    assert {node.name for node in hooks} == wanted
    assert len(registrations) == 2
    # source order, as main.py registers them: the guard's insert must land after the limit hook's
    ordered = sorted(hooks + registrations, key=lambda node: node.lineno)
    _User.reads = 0
    namespace = {
        "app": app,
        "request": request,
        "current_user": _User(),
        "make_response": make_response,
        "jsonify": jsonify,
        "LOGGER": Mock(),
        "_host_allowed": _host_allowed,
        "is_static_path": lambda path, *extra: path.startswith("/static/"),
    }
    exec(compile(ast.Module(body=ordered, type_ignores=[]), str(MAIN), "exec"), namespace)  # noqa: S102
    app.add_url_rule("/edit", "edit", view_func=lambda: "ok", methods=["POST"])
    app.add_url_rule("/static/<path:name>", "asset", view_func=lambda name: name)
    return app.test_client()


def test_disallowed_host_is_rejected_before_current_user_is_loaded():
    client = _build(ALLOWED)

    response = client.post("/edit", data={"a": "b"}, headers={"Host": "evil.example"})

    assert response.status_code == 400
    assert response.get_json() == {"message": "Invalid host"}
    assert _User.reads == 0


def test_allowed_host_still_reaches_the_form_limit_hook():
    client = _build(ALLOWED)

    response = client.post("/edit", data={"a": "b"}, headers={"Host": "ui.example.com"})

    assert response.status_code == 200
    assert _User.reads == 1


def test_static_paths_skip_the_host_check():
    client = _build(ALLOWED)

    assert client.get("/static/app.css", headers={"Host": "evil.example"}).status_code == 200


def test_no_allowlist_accepts_every_host():
    client = _build([])

    assert client.post("/edit", data={"a": "b"}, headers={"Host": "evil.example"}).status_code == 200


def test_before_request_no_longer_carries_a_second_host_check():
    tree = ast.parse(MAIN.read_text())
    node = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "before_request")

    assert "_host_allowed" not in {name.id for name in ast.walk(node) if isinstance(name, ast.Name)}
