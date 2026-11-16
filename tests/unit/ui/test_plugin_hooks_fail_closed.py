"""A plugin `before_request` hook that raises, or whose hooks fail to load, never serves the page (QAR Q9).

A PRO plugin can ship an authorization check as a `before_request` hook (user_manager's permissions).
`main.py` used to log the exception of a hook that raised and serve the request anyway, and
`refresh_app_context` only logged a `hooks.py` that failed to load, so the check silently
disappeared. Both now answer 500 (`_internal_error_response`).

`main.py` cannot be imported in the unit venv: `before_request` and `refresh_app_context` are
spliced out of its source by name (`test_session_plumbing._shipped`) and run against stubs.
"""

from contextlib import suppress
from datetime import datetime
from importlib.util import module_from_spec, spec_from_file_location
from itertools import chain
from operator import itemgetter
from os import getpid
from os.path import abspath
from unittest.mock import Mock

import pytest
from flask import Blueprint, Flask
from jinja2 import ChoiceLoader, FileSystemLoader

from test_before_request_env import _Data, _app, _metadata
from test_session_plumbing import MAIN, _shipped

DENIED = ("denied", 500)


def _get(hooks):
    application = _app(_metadata(), _Data(LATEST_VERSION_LAST_CHECK=datetime.now().astimezone().isoformat()), [])
    namespace = application.before_request_funcs[None][0].__globals__
    namespace["_internal_error_response"] = lambda: DENIED
    application.config["BEFORE_REQUEST_HOOKS"] = hooks
    return application.test_client().get("/templates", environ_base={"REMOTE_ADDR": "127.0.0.1"}, headers={"User-Agent": "pytest"})


def test_a_hook_that_raises_answers_500_and_the_page_is_not_served():
    def authorize():
        raise RuntimeError("permission lookup failed")

    response = _get([authorize])

    assert response.status_code == 500, response.get_data(as_text=True)
    assert response.get_data(as_text=True) == "denied"


def test_a_hook_response_still_short_circuits_the_request():
    response = _get([lambda: ("redirected", 302)])

    assert response.status_code == 302


def test_hooks_that_return_nothing_let_the_page_through():
    response = _get([lambda: None])

    assert response.status_code == 200


# ---------------------------------------------------------------------------- refresh_app_context


class _Paths:
    """Per-test plugin trees; `refresh_app_context` globs `<root>/*/ui/hooks.py`."""

    def __init__(self, tmp_path):
        self.core = tmp_path / "core"
        self.external = tmp_path / "external"
        self.pro = tmp_path / "pro"
        for path in (self.core, self.external, self.pro):
            path.mkdir()

    def hooks(self, root, plugin, source):
        directory = root / plugin / "ui"
        directory.mkdir(parents=True)
        (directory / "hooks.py").write_text(source, encoding="utf-8")


@pytest.fixture
def refresh(tmp_path):
    paths = _Paths(tmp_path)
    namespace = dict(
        LOGGER=Mock(),
        DATA=_Data(),
        BLUEPRINTS=(),
        CORE_PLUGINS_PATH=paths.core,
        EXTERNAL_PLUGINS_PATH=paths.external,
        PRO_PLUGINS_PATH=paths.pro,
        chain=chain,
        suppress=suppress,
        module_from_spec=module_from_spec,
        spec_from_file_location=spec_from_file_location,
        getpid=getpid,
        abspath=abspath,
        itemgetter=itemgetter,
        Flask=Flask,
        ChoiceLoader=ChoiceLoader,
        FileSystemLoader=FileSystemLoader,
        Blueprint=Blueprint,
        sys_path=[],
        sys_modules={},
        read_plugin_version=lambda root: "1.0",
        _internal_error_response=lambda: DENIED,
    )
    _shipped(
        MAIN,
        ("HOOKS", "should_replace_blueprint", "DynamicFlask", "register_plugin_blueprints", "deny_plugin_requests", "refresh_app_context"),
        namespace,
    )
    application = namespace["DynamicFlask"]("bw_ui_refresh_test")
    application.config["EXTRA_PAGES"] = []
    namespace["app"] = application
    return paths, application, namespace


def _run_hooks(application):
    for hook in application.config["BEFORE_REQUEST_HOOKS"]:
        response = hook()
        if response:
            return response
    return None


GOOD = "def before_request():\n    return None\n"


@pytest.mark.parametrize(
    "source",
    [
        pytest.param("def before_request(:\n", id="syntax-error"),
        pytest.param("raise RuntimeError('boom at import')\n", id="raises-at-import"),
        pytest.param("import module_that_does_not_exist\n", id="missing-import"),
    ],
)
def test_a_plugin_whose_hooks_fail_to_load_denies_every_request(refresh, source):
    paths, application, namespace = refresh
    paths.hooks(paths.external, "authz", source)

    namespace["refresh_app_context"]()

    assert _run_hooks(application) == DENIED


def test_one_broken_plugin_does_not_hide_a_working_one_and_still_denies(refresh):
    paths, application, namespace = refresh
    paths.hooks(paths.core, "fine", GOOD)
    paths.hooks(paths.external, "authz", "raise RuntimeError('boom')\n")

    namespace["refresh_app_context"]()

    assert _run_hooks(application) == DENIED
    assert any(hook.__module__ == "bw_ui_hooks_fine_hooks" for hook in application.config["BEFORE_REQUEST_HOOKS"])


def test_repeated_refreshes_keep_one_stub_per_broken_plugin(refresh):
    paths, application, namespace = refresh
    paths.hooks(paths.external, "authz", "raise RuntimeError('boom')\n")

    namespace["refresh_app_context"]()
    namespace["refresh_app_context"]()

    assert len(application.config["BEFORE_REQUEST_HOOKS"]) == 1


def test_plugins_that_load_cleanly_add_no_denial(refresh):
    paths, application, namespace = refresh
    paths.hooks(paths.core, "fine", GOOD)

    namespace["refresh_app_context"]()

    assert _run_hooks(application) is None


# ---------------------------------------------------------------------------- deleted plugin (0dcbe153e)


def test_a_deleted_plugins_pages_answer_404_not_500(refresh):
    _, application, namespace = refresh
    gone = Blueprint("gone", __name__)

    @gone.route("/gone")
    def page():
        return "still here"

    @gone.route("/gone/detail")
    def detail():
        return "detail"

    application.register_blueprint(gone)
    application.config["EXTRA_PAGES"].append("gone")
    client = application.test_client()
    assert client.get("/gone").get_data(as_text=True) == "still here"

    namespace["refresh_app_context"]()

    assert client.get("/gone").status_code == 404
    assert client.get("/gone/detail").status_code == 404
    assert "gone" not in application.blueprints
    assert "gone" not in application.config["EXTRA_PAGES"]
    assert "gone.page" not in application.view_functions
