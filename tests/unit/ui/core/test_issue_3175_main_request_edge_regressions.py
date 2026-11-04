"""Request-pipeline regressions in ``src/ui/main.py``: error handling without a user context (#3175), the
reverse-proxied index (#839), the all-in-one start without ``_zstd``, version-free static directory URLs, and
form fields above Flask's default 500 kB cap for signed-in users.
"""

import sys
from types import SimpleNamespace

import pytest

from flask import request
from werkzeug.exceptions import RequestEntityTooLarge


class _NoUserContext:
    """``current_user`` when Flask-Login has no app or request context to resolve it from."""

    def get_id(self):
        raise RuntimeError("Working outside of request context.")

    @property
    def is_authenticated(self):
        raise AssertionError("no request context")

    def __bool__(self):
        raise RuntimeError("Working outside of request context.")


def test_csrf_error_without_a_resolvable_user_still_redirects(um, monkeypatch):
    monkeypatch.setattr(um.main, "current_user", _NoUserContext())
    um.users["root"] = SimpleNamespace(username="root")

    with um.app.test_request_context("/services", method="POST"):
        response = um.main.handle_csrf_error(None)

    assert response.status_code == 303


def test_teardown_without_a_resolvable_user_does_not_raise(um, monkeypatch):
    monkeypatch.setattr(um.main, "current_user", _NoUserContext())

    with um.app.test_request_context("/home"):
        um.main.teardown_request(None)

    assert um.executors["_user_access_executor"].submitted == []


def test_the_index_matches_with_and_without_the_trailing_slash(um):
    adapter = um.app.url_map.bind("localhost", script_name="/bw")

    assert adapter.match("/", method="GET")[0] == "index"
    assert adapter.match("", method="GET")[0] == "index"


def test_a_static_directory_url_has_no_version_query_but_a_file_url_does(um):
    with um.app.test_request_context("/"):
        directory = um.main.custom_url_for("static", filename="img/flags")
        trailing = um.main.custom_url_for("static", filename="img/flags/")
        asset = um.main.custom_url_for("static", filename="img/logo.svg")

    assert "?" not in directory and "?" not in trailing
    assert asset.endswith(f"?v={um.main.BW_VERSION}")


FIELD = "x" * 600_000  # above Flask's 500 kB default for one form field, below MAX_CONTENT_LENGTH


def test_the_form_field_limit_is_lifted_before_any_form_parsing(um):
    hooks = um.app.before_request_funcs[None]

    assert hooks[0].__name__ == "lift_form_field_limit"


def test_a_signed_in_post_may_carry_a_large_form_field(um):
    response = um.client("alice").post("/set_theme", data={"theme": FIELD}, content_type="multipart/form-data")

    assert response.status_code != 413


def test_an_anonymous_post_keeps_the_default_form_field_limit(um):
    with um.app.test_request_context("/login", method="POST", data={"username": FIELD}, content_type="multipart/form-data"):
        um.app.preprocess_request()
        with pytest.raises(RequestEntityTooLarge):
            request.form["username"]


def test_main_loads_when_python_has_no_zstd_module(tmp_path, monkeypatch):
    from _ui_core_main import LoadedMain

    for name in [n for n in sys.modules if n == "flask_compress" or n.startswith(("flask_compress.", "compression.zstd"))]:
        monkeypatch.delitem(sys.modules, name)
    monkeypatch.setitem(sys.modules, "_zstd", None)  # `import _zstd` raises ModuleNotFoundError, like Alpine's python3

    loaded = LoadedMain(tmp_path)
    try:
        assert loaded.main.Compress is not None
        assert "compression.zstd" not in sys.modules, "the stub must not outlive the Flask-Compress import"
    finally:
        loaded.close()
