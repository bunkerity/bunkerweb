"""The UI half of the explicit redirect-only declaration: the audit wiring and the action.

Three separate things, and they fail in three different ways:

* **`_redirect_candidates`** feeds one advisory boolean per row. It is polled by a `serverSide`
  table, so its only real failure mode is a spinner that never stops -- it must degrade to no
  badges, never to an exception.
* **`_service_mode_context`** decides whether the settings page offers the action at all, and
  carries the classifier's reasons VERBATIM so the modal can say why it is refused.
* **`services_mode_convert`** is the write. It mirrors `services_convert` -- same executor, same
  loading page -- and goes through the API's convert endpoint rather than writing the row itself,
  because that endpoint owns the refusal.

Same module-loader pattern as `test_services_fetch.py`: `app.dependencies` boots container-only
state at import time.
"""

import importlib.util
import re
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

import pytest
from flask import Flask

ROUTE_PATH = Path(__file__).resolve().parents[3] / "src" / "ui" / "app" / "routes" / "services.py"

SERVICE = "old.example.com"


@pytest.fixture
def services_route():
    dependencies = ModuleType("app.dependencies")
    dependencies.API_CLIENT = Mock()
    dependencies.BW_CONFIG = Mock()
    dependencies.CONFIG_TASKS_EXECUTOR = Mock()
    dependencies.CORE_PLUGINS_PATH = Path("/nonexistent")
    dependencies.DATA = {}

    qrcode = ModuleType("qrcode")
    qrcode_main = ModuleType("qrcode.main")
    qrcode_main.QRCode = Mock()

    module_name = "app.routes._service_mode_test"
    spec = importlib.util.spec_from_file_location(module_name, ROUTE_PATH)
    module = importlib.util.module_from_spec(spec)
    stubs = {"app.dependencies": dependencies, "qrcode": qrcode, "qrcode.main": qrcode_main, module_name: module}
    with patch.dict(sys.modules, stubs):
        spec.loader.exec_module(module)
        yield module


# --------------------------------------------------------------------------------------
# The advisory badge
# --------------------------------------------------------------------------------------
class TestCandidateBadge:
    def test_only_the_qualifying_services_are_named(self, services_route):
        services_route.API_CLIENT.get_redirect_candidates.side_effect = None
        services_route.API_CLIENT.get_redirect_candidates.return_value = [
            {"service": SERVICE, "would_qualify": True, "blocking_reasons": []},
            {"service": "app.example.com", "would_qualify": False, "blocking_reasons": ["setting USE_REVERSE_PROXY is not on redirect-only allowlist v1"]},
        ]

        assert services_route._redirect_candidate_names() == [SERVICE]

    def test_an_unreadable_audit_costs_the_badges_and_nothing_else(self, services_route):
        services_route.API_CLIENT.get_redirect_candidates.side_effect = RuntimeError("boom")

        assert services_route._redirect_candidate_names() == []

    def test_the_table_rows_never_carry_it(self, services_route):
        """The audit must NOT ride on `/services/fetch`. That endpoint runs on every draw of a
        `serverSide` table -- every search keystroke, sort and page change -- and the audit is a
        whole-fleet read (a config snapshot, the custom configs, four resource families). Perf Lot
        D bought this page back from 1089 KB and 260 ms; the badge is not worth spending it again.
        It is read once on the page GET and handed to `services.js` in the document instead."""
        services_route.API_CLIENT.get_redirect_candidates.reset_mock()

        rows = services_route._service_rows([_api_service(f"s{index}.example.com") for index in range(500)])

        assert not any("redirect_candidate" in row for row in rows)
        assert not services_route.API_CLIENT.get_redirect_candidates.called


def _api_service(name):
    return {"id": name, "is_draft": False, "method": "ui", "security_mode": "block", "template": "", "creation_date": None, "last_update": None}


# --------------------------------------------------------------------------------------
# Cloning
# --------------------------------------------------------------------------------------
class TestCloneReset:
    def test_a_clone_does_not_inherit_the_declared_mode(self, services_route):
        """The defect this exists to stop: `check_variables` REFUSES a blacklisted key whose posted
        value differs from `db_config` (models/config.py, the blacklist branch), and on the "new"
        page `db_config` is the GLOBAL settings, where SERVICE_MODE is the plain default. A clone
        of a `redirect_only` service therefore answered the very first, perfectly ordinary save with
        "Variable SERVICE_MODE is not editable" and a refusal count."""
        db_config = services_route.neutralize_clone(
            {
                "SERVER_NAME": {"value": "old.example.com", "clone": True},
                "USE_UI": {"value": "yes", "clone": True},
                "SERVICE_MODE": {"value": "redirect_only", "clone": True},
                "REDIRECT_TO": {"value": "https://new.example.com", "clone": True},
            }
        )

        assert db_config["SERVICE_MODE"] == {"value": "standard", "clone": False}
        assert db_config["REDIRECT_TO"]["value"] == "https://new.example.com", "an ordinary setting is still cloned"

    def test_the_two_pre_existing_resets_are_unchanged(self, services_route):
        """SERVICE_MODE joined an existing pair; the pair's behaviour must not have moved."""
        db_config = services_route.neutralize_clone({"SERVER_NAME": {"value": "old.example.com", "clone": True}, "USE_UI": {"value": "yes", "clone": True}})

        assert db_config["SERVER_NAME"] == {"value": "", "clone": False}
        assert db_config["USE_UI"] == {"value": "no", "clone": False}

    def test_a_missing_key_is_not_invented(self, services_route):
        """A degraded API answers `{}`; the reset must not fabricate rows the page would then post."""
        assert services_route.neutralize_clone({}) == {}


# --------------------------------------------------------------------------------------
# The settings-page card
# --------------------------------------------------------------------------------------
class TestModeContext:
    def test_a_standard_candidate_is_offered_the_conversion(self, services_route):
        services_route.API_CLIENT.get_redirect_candidates.side_effect = None
        services_route.API_CLIENT.get_redirect_candidates.return_value = [{"service": SERVICE, "would_qualify": True, "blocking_reasons": []}]

        context = services_route._service_mode_context(SERVICE, {"SERVICE_MODE": {"value": "standard"}})

        assert context == {"current": "standard", "target": "redirect_only", "blocking_reasons": []}

    def test_the_reasons_travel_verbatim(self, services_route):
        """They are already whole sentences naming the setting, the snippet count or the
        attachment type -- rewording them here is how the modal and the 409 start disagreeing."""
        reasons = ["setting USE_REVERSE_PROXY is not on redirect-only allowlist v1", "1 custom config(s) attached"]
        services_route.API_CLIENT.get_redirect_candidates.side_effect = None
        services_route.API_CLIENT.get_redirect_candidates.return_value = [{"service": SERVICE, "would_qualify": False, "blocking_reasons": reasons}]

        assert services_route._service_mode_context(SERVICE, {})["blocking_reasons"] == reasons

    def test_a_redirect_only_service_is_offered_the_way_back_without_an_audit_call(self, services_route):
        """Reverting is always allowed, so there is nothing to ask and nothing to explain."""
        services_route.API_CLIENT.get_redirect_candidates.reset_mock()
        services_route.API_CLIENT.get_redirect_candidates.side_effect = None

        context = services_route._service_mode_context(SERVICE, {"SERVICE_MODE": {"value": "redirect_only"}})

        assert context == {"current": "redirect_only", "target": "standard", "blocking_reasons": []}
        assert not services_route.API_CLIENT.get_redirect_candidates.called

    def test_an_unreadable_audit_hides_the_card(self, services_route):
        """Empty context renders no card: an action whose outcome is unknown is worse than none."""
        services_route.API_CLIENT.get_redirect_candidates.side_effect = RuntimeError("boom")

        assert services_route._service_mode_context(SERVICE, {}) == {}


# --------------------------------------------------------------------------------------
# The write
# --------------------------------------------------------------------------------------
@pytest.fixture
def route_app(services_route, monkeypatch):
    """A minimal Flask app carrying just the mode route, with login and the loading page stubbed."""
    app = Flask(__name__)
    app.secret_key = "test"  # nosec B105 - unit test
    monkeypatch.setattr(services_route, "wait_applying", Mock())
    monkeypatch.setattr(services_route, "handle_error", lambda message, *_args, **_kwargs: (message, 400))
    # The real helper RETURNS a Response on refusal and `True` otherwise (routes/utils.py:93), and
    # the route branches on that -- so the stub has to answer `True`, not None.
    monkeypatch.setattr(services_route, "verify_data_in_form", lambda **_kwargs: True)
    monkeypatch.setattr(services_route, "_reserved_default_server", lambda _service: False)

    # `DATA` is a UIData in production (a dict with `load_from_file`); the loader stubs it with a
    # plain dict, so give it back the one method the route calls.
    class _Data(dict):
        load_from_file = Mock()

    monkeypatch.setattr(services_route, "DATA", _Data(TO_FLASH=[]))
    services_route.API_CLIENT.readonly = False
    # The real `is_readonly_request` reads `current_user.list_permissions` (app/utils.py:353), and
    # there is no logged-in user here. Stub it on the readonly flag alone; the two cases it exists
    # to separate get their own tests below.
    monkeypatch.setattr(services_route, "is_readonly_request", lambda api_readonly: api_readonly)
    services_route.API_CLIENT.convert_service.reset_mock()
    services_route.API_CLIENT.convert_service.side_effect = None
    services_route.CONFIG_TASKS_EXECUTOR.submit.side_effect = lambda function, *args: function(*args)

    app.add_url_rule("/services/<string:service>/mode", view_func=services_route.services_mode_convert.__wrapped__, methods=["POST"])
    app.add_url_rule("/loading", view_func=lambda: "loading", endpoint="loading")
    app.add_url_rule("/services/<string:service>", view_func=lambda service: service, endpoint="services.services_service_page")
    # The REAL `verify_data_in_form` refuses through `routes/utils.handle_error`, which is a
    # different reference from the one patched on the services module and builds this endpoint.
    app.add_url_rule("/services", view_func=lambda: "services", endpoint="services.services_page")
    return app


class TestModeConversionRoute:
    def test_it_calls_the_api_convert_endpoint_with_the_mode(self, services_route, route_app):
        with route_app.test_client() as client:
            response = client.post(f"/services/{SERVICE}/mode", data={"mode": "redirect_only"})

        assert response.status_code == 302
        services_route.API_CLIENT.convert_service.assert_called_once_with(SERVICE, mode="redirect_only")

    def test_it_never_writes_the_row_itself(self, services_route, route_app):
        """The refusal lives in the API endpoint. A UI that called `save_config` directly would be
        a second, weaker copy of the rule -- the exact drift the shared classifier exists to stop."""
        with route_app.test_client() as client:
            client.post(f"/services/{SERVICE}/mode", data={"mode": "redirect_only"})

        assert not services_route.API_CLIENT.save_config.called

    def test_a_payload_with_no_mode_is_flashed_not_crashed(self, services_route, route_app, monkeypatch):
        """`verify_data_in_form` RETURNS a Response, it does not abort (routes/utils.py:74-93).
        Discarding it -- which the two older sibling routes do -- lets the request fall through to
        `request.form["mode"]` and raise a bare 400 page, so the `err_message` never reaches
        anyone. Here the real helper runs, and its refusal has to be what the caller gets back."""
        monkeypatch.undo()
        monkeypatch.setattr(services_route, "wait_applying", Mock())
        monkeypatch.setattr(services_route, "handle_error", lambda message, *_args, **_kwargs: (message, 400))
        monkeypatch.setattr(services_route, "is_readonly_request", lambda api_readonly: api_readonly)

        with route_app.test_client() as client:
            response = client.post(f"/services/{SERVICE}/mode", data={"nothing": "useful"})

        # The helper flashes and redirects. Before the fix this was a 400 `BadRequestKeyError`
        # page raised out of `request.form["mode"]`, with the flash never queued.
        assert response.status_code == 302, response.data[:200]
        assert not services_route.API_CLIENT.convert_service.called

    def test_a_user_without_write_gets_the_permission_message_not_the_database_one(self, services_route, route_app, monkeypatch):
        """Two causes, two messages: the database is fine, the permission is not."""
        monkeypatch.setattr(services_route, "is_readonly_request", lambda api_readonly: True)

        with route_app.test_client() as client:
            response = client.post(f"/services/{SERVICE}/mode", data={"mode": "redirect_only"})

        assert b"permission" in response.data and b"read-only" not in response.data

    def test_an_unknown_mode_is_refused_before_anything(self, services_route, route_app):
        with route_app.test_client() as client:
            response = client.post(f"/services/{SERVICE}/mode", data={"mode": "free"})

        # The message, not the status: `handle_error` is stubbed in the fixture, so a status
        # assertion would be testing the stub.
        assert b"Invalid mode" in response.data
        assert not services_route.API_CLIENT.convert_service.called

    def test_a_refusal_from_the_api_is_flashed_and_nothing_reloads(self, services_route, route_app):
        services_route.API_CLIENT.convert_service.side_effect = services_route.ApiClientError("Service cannot be converted to redirect-only")

        with route_app.test_client() as client:
            client.post(f"/services/{SERVICE}/mode", data={"mode": "redirect_only"})

        assert services_route.DATA["TO_FLASH"][-1]["type"] == "error"
        assert services_route.DATA["RELOADING"] is False

    def test_the_reserved_default_server_has_no_mode(self, services_route, route_app, monkeypatch):
        monkeypatch.setattr(services_route, "_reserved_default_server", lambda _service: True)

        with route_app.test_client() as client:
            response = client.post("/services/default-server/mode", data={"mode": "redirect_only"})

        assert b"match no configured service" in response.data, "the refusal must say what the default server IS"
        assert not services_route.API_CLIENT.convert_service.called

    def test_a_read_only_database_refuses(self, services_route, route_app):
        services_route.API_CLIENT.readonly = True

        with route_app.test_client() as client:
            response = client.post(f"/services/{SERVICE}/mode", data={"mode": "redirect_only"})

        assert b"read-only" in response.data
        assert not services_route.API_CLIENT.convert_service.called

    def test_a_user_without_write_refuses_too(self, services_route, route_app, monkeypatch):
        """The route gates on `is_readonly_request`, not on `API_CLIENT.readonly` alone: the
        settings page dims the button for a user without `write`, and an action that is only dimmed
        is still reachable by POST. `services_convert`/`services_delete` check only the database —
        that older gap is not this lane's to close, but the new route must not reproduce it."""
        monkeypatch.setattr(services_route, "is_readonly_request", lambda api_readonly: True)

        with route_app.test_client() as client:
            client.post(f"/services/{SERVICE}/mode", data={"mode": "redirect_only"})

        assert not services_route.API_CLIENT.convert_service.called


# --------------------------------------------------------------------------------------
# The card's markup
# --------------------------------------------------------------------------------------
TEMPLATE = Path(__file__).resolve().parents[3] / "src" / "ui" / "app" / "templates" / "service_settings.html"


def test_the_card_posts_to_a_route_that_exists(services_route):
    """`url_for` renders "#" for an unknown endpoint instead of raising, so a typo here ships a
    button that silently posts to the page it is on. Assert the name the template writes against
    the view the blueprint really carries."""
    markup = TEMPLATE.read_text(encoding="utf-8")
    endpoint = re.search(r"url_for\('(services\.[a-z_]+)', service=service_id\)", markup)
    assert endpoint, "the mode card no longer posts anywhere"

    # A blueprint records its routes as deferred functions, not as resolvable endpoints, so read
    # the view name off the module: the decorator bound it there under the exact name `url_for`
    # resolves, and the blueprint's own name prefixes it.
    blueprint, view = endpoint.group(1).split(".", 1)
    assert blueprint == services_route.services.name
    assert hasattr(services_route, view), f"{endpoint.group(1)} is not a view on the services blueprint"


def test_the_confirm_button_is_disabled_when_the_declaration_is_refused():
    """A modal that shows the reasons and still lets the operator click Confirm is a modal that
    teaches them the reasons are advisory."""
    markup = TEMPLATE.read_text(encoding="utf-8")

    assert markup.count("disabled=mode_disabled") == 2, "both the action and the confirm button must be gated"
    assert "blocked|length > 0 or is_readonly" in markup, "a read-only page must not offer an action that can only flash an error"
