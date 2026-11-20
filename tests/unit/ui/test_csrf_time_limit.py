"""The CSRF token lifetime must follow the session lifetime (dev eb6c32e2d, #2359).

Flask-WTF expires a CSRF token after ``WTF_CSRF_TIME_LIMIT`` (default 3600 s). The session lives
``SESSION_LIFETIME_HOURS`` (default 12), so a form left open for more than an hour failed with a CSRF error
while the user was still logged in.

``main.py`` cannot be imported in the unit venv, so the configuration lines are spliced out of its source.
"""

import ast
from datetime import timedelta
from pathlib import Path

from flask import Flask

_MAIN = Path(__file__).resolve().parents[3] / "src" / "ui" / "main.py"


def _config_statements():
    """The top-level ``app.config[...] = ...`` assignments of the session and CSRF configuration, in source order."""
    tree = ast.parse(_MAIN.read_text(encoding="utf-8"))
    wanted = {"PERMANENT_SESSION_LIFETIME", "WTF_CSRF_METHODS", "WTF_CSRF_SSL_STRICT", "WTF_CSRF_TIME_LIMIT"}
    found = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Subscript)):
            continue
        target = node.targets[0]
        config = target.value  # `app.config`
        if not (isinstance(config, ast.Attribute) and config.attr == "config" and isinstance(config.value, ast.Name) and config.value.id == "app"):
            continue
        if isinstance(target.slice, ast.Constant) and target.slice.value in wanted:
            found.append(node)
    assert {n.targets[0].slice.value for n in found} >= {"PERMANENT_SESSION_LIFETIME"}, "session lifetime assignment not found in main.py"
    return sorted(found, key=lambda node: node.lineno)


def _configured(hours: float) -> Flask:
    application = Flask("csrf_time_limit_test")
    module = ast.Module(body=_config_statements(), type_ignores=[])
    # `session_lifetime_hours` is the local `main.py` computes from SESSION_LIFETIME_HOURS before these lines.
    exec(compile(module, str(_MAIN), "exec"), {"app": application, "timedelta": timedelta, "session_lifetime_hours": hours})  # noqa: S102
    return application


def test_the_csrf_time_limit_equals_the_session_lifetime():
    application = _configured(12.0)

    assert application.config.get("WTF_CSRF_TIME_LIMIT") == int(application.config["PERMANENT_SESSION_LIFETIME"].total_seconds()) == 12 * 3600


def test_the_csrf_time_limit_follows_a_custom_session_lifetime():
    assert _configured(2.5).config.get("WTF_CSRF_TIME_LIMIT") == 9000
