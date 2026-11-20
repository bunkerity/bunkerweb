"""Exercise the CSRF setup from main.py using real Flask-WTF and an HTTP client."""

import ast
from datetime import timedelta
from pathlib import Path

from flask import Flask
from flask_wtf.csrf import CSRFProtect, generate_csrf

_MAIN = Path(__file__).resolve().parents[3] / "src" / "ui" / "main.py"


def test_post_requires_valid_csrf_token():
    application = Flask(__name__)
    application.config.update(TESTING=True, SECRET_KEY="unit-test-csrf-secret", PERMANENT_SESSION_LIFETIME=timedelta(hours=12))
    tree = ast.parse(_MAIN.read_text(encoding="utf-8"))
    # Execute the shipped CSRF configuration and registration, without main.py's startup I/O.
    statements = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            target = ast.unparse(node.targets[0])
            if target == "csrf" or target.startswith("app.config['WTF_CSRF_"):
                statements.append(node)
        elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Call) and ast.unparse(node.value.func) == "csrf.init_app":
            statements.append(node)
    module = ast.Module(body=sorted(statements, key=lambda node: node.lineno), type_ignores=[])
    exec(compile(module, str(_MAIN), "exec"), {"app": application, "CSRFProtect": CSRFProtect})  # noqa: S102

    saved = []

    @application.get("/form")
    def form():
        return generate_csrf()

    @application.post("/save")
    def save():
        saved.append("saved")
        return "saved"

    client = application.test_client()
    token = client.get("/form").get_data(as_text=True)

    assert client.post("/save").status_code == 400
    assert saved == []
    assert client.post("/save", data={"csrf_token": token + "tampered"}).status_code == 400
    assert saved == []
    response = client.post("/save", data={"csrf_token": token})
    assert (response.status_code, response.get_data(as_text=True), saved) == (200, "saved", ["saved"])
