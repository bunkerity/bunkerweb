"""The default server, as an operator meets it in the UI.

PO ruling 7 in one sentence: an operator must not have to work out what `default-server` is. The
services list pins it, names it "Default server" and says what it answers; its page offers the
curated subset and nothing else, and no delete.

Three of those are server-side facts and are tested here. The fourth -- the label and the explainer
-- is rendered by `static/js/pages/services.js` from the `reserved` flag this file pins, and the
flag is what the client keys on, so a name comparison never has to exist in JavaScript.
"""

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from flask import Flask
from jinja2 import Environment, FileSystemLoader

from app.utils import can_delete_service, get_filtered_settings, get_multiples
from default_server import DEFAULT_SERVER_ID, DEFAULT_SERVER_PLUGINS  # type: ignore

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_save_scope import _FakeData, _import_services_module  # noqa: E402

_services = _import_services_module()

TEMPLATES = Path(__file__).resolve().parents[3] / "src" / "ui" / "app" / "templates"

ORDINARY = {"id": "app.example.com", "method": "ui", "is_draft": False, "creation_date": None, "last_update": None}
RESERVED = {"id": DEFAULT_SERVER_ID, "method": "wizard", "is_draft": False, "creation_date": None, "last_update": None}


class TestTheRow:
    def test_it_is_flagged_reserved(self):
        rows = {row["name"]: row for row in _services._service_rows([ORDINARY, RESERVED])}
        assert rows[DEFAULT_SERVER_ID]["reserved"] is True
        assert rows[ORDINARY["id"]]["reserved"] is False

    def test_it_is_never_deletable(self):
        rows = {row["name"]: row for row in _services._service_rows([ORDINARY, RESERVED])}
        assert rows[DEFAULT_SERVER_ID]["deletable"] is False
        assert rows[ORDINARY["id"]]["deletable"] is True

    def test_can_delete_service_refuses_the_reserved_row_by_id_AND_method(self):
        """Re-pinned by DS-B4 (PO ruling 4 of 2026-09-06). It used to be by id alone, on the
        argument that the seeding method is an implementation detail -- but the id alone also
        refused an operator's OWN service that took the name before 1.7 reserved it, and that row
        already has no `server{}` block (`http.conf` drops the id by name, whatever the method), so
        the refusal left it with no supported way back at all. Both halves are asserted, so an
        id-only guard and a method-only guard each go red."""
        assert can_delete_service({"id": DEFAULT_SERVER_ID, "method": "wizard"}) is False
        assert can_delete_service({"id": DEFAULT_SERVER_ID, "method": "ui"}) is True
        assert can_delete_service({"id": "app.example.com", "method": "ui"}) is True
        assert can_delete_service({"id": "app.example.com", "method": "wizard"}) is False

    @pytest.mark.parametrize("direction", ("asc", "desc"))
    def test_it_is_pinned_first_whatever_the_sort(self, direction):
        """Sorted by name descending, `default-server` lands wherever the alphabet puts it -- on
        page 7 of a large estate, which is how an operator concludes there is nowhere to configure
        the default server."""
        rows = _services._service_rows([{**ORDINARY, "id": name} for name in ("aaa.example.com", "zzz.example.com")] + [RESERVED])
        ordered = _services._filter_and_sort_services(rows, "", {}, 0, direction)
        assert ordered[0]["name"] == DEFAULT_SERVER_ID
        assert [row["name"] for row in ordered[1:]] == (
            ["aaa.example.com", "zzz.example.com"] if direction == "asc" else ["zzz.example.com", "aaa.example.com"]
        )


def _render_shelf(plugins, allowed_plugins=None):
    env = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=True)  # nosec B701 - HTML, autoescaped
    env.globals.update(
        url_for=lambda endpoint, **kwargs: "/" + endpoint,
        get_filtered_settings=get_filtered_settings,
        is_plugin_active=lambda *args, **kwargs: False,
        is_plugin_active_for_service=lambda *args, **kwargs: False,
        is_editable_method=lambda method: method in ("ui", "api", "wizard"),
        plugin_types={"core": {"icon": "<i class='bx bx-shield'></i>"}},
    )
    return env.get_template("models/compose_shelf.html").render(
        plugins=plugins,
        config={},
        activation_map={},
        shelf_plugin_scope=lambda *args, **kwargs: set(),
        control_keys=lambda *args, **kwargs: set(),
        blacklisted_settings=set(),
        global_page=False,
        is_pro_version=False,
        is_readonly=False,
        service_id=DEFAULT_SERVER_ID,
        attachments={},
        allowed_plugins=allowed_plugins,
    )


def _plugin(plugin_id):
    return {
        "id": plugin_id,
        "name": plugin_id,
        "type": "core",
        "stream": "no",
        "settings": {f"USE_{plugin_id.upper()}": {"context": "multisite", "default": "no", "label": plugin_id, "type": "check", "help": "h"}},
    }


class TestTheShelfSubset:
    PLUGINS = {plugin_id: _plugin(plugin_id) for plugin_id in ("headers", "errors", "reverseproxy", "antibot")}

    def test_without_an_allowlist_every_plugin_is_offered(self):
        """The filter is opt-in: one page passes it, and every other page must be untouched."""
        rendered = _render_shelf(self.PLUGINS)
        for plugin_id in self.PLUGINS:
            assert f"shelf-row-{plugin_id}" in rendered, plugin_id

    def test_with_the_allowlist_only_the_curated_plugins_are_offered(self):
        rendered = _render_shelf(self.PLUGINS, allowed_plugins=DEFAULT_SERVER_PLUGINS)
        assert "shelf-row-headers" in rendered
        assert "shelf-row-errors" in rendered
        # Both assume a service identity: rendering them would produce settings that are stored,
        # shown as configured, and never applied by the default server block.
        assert "shelf-row-reverseproxy" not in rendered
        assert "shelf-row-antibot" not in rendered


# ----------------------------------------------------------------------- route wiring
# The two tests above prove the TEMPLATE narrows the shelf when it is handed an allowlist, and the
# shelf test above it proves it offers everything without one. Neither says the page HANDS it over:
# deleting `allowed_plugins=` from the render call leaves both green while the reserved service's
# page offers reverse proxy, antibot and mTLS again. Same for the plugin page's direct URL, which
# nothing exercised at all.


@pytest.fixture
def route_app():
    app = Flask(__name__)
    app.secret_key = "test"  # nosec B105 - test-only Flask secret
    app.register_blueprint(_services.services)
    app.add_url_rule("/loading", "loading", lambda: "")
    return app


def _get_service_page(app, monkeypatch, service):
    """GET the real route and return the kwargs it renders `service_settings.html` with."""
    api = Mock()
    api.readonly = False
    api.get_service.return_value = {}
    api.get_templates.return_value = {}
    api.get_configs.return_value = []
    api.get_metadata.return_value = {"is_pro": False}
    # The page asks the API whether this id is the RESERVED row or merely a service named like it.
    api.get_services.return_value = [
        {"id": DEFAULT_SERVER_ID, "method": "wizard", "is_draft": False},
        {"id": "app.example.com", "method": "ui", "is_draft": False},
    ]
    for getter, rows_key in (
        ("get_upstreams", "upstreams"),
        ("get_certificates", "certificates"),
        ("get_redirects", "redirects"),
        ("get_workflows", "workflows"),
    ):
        getattr(api, getter).return_value = {rows_key: []}
    bw_config = Mock()
    bw_config.get_plugins.return_value = {}
    bw_config.get_config.return_value = {"SERVER_NAME": f"{DEFAULT_SERVER_ID} app.example.com"}
    monkeypatch.setattr(_services, "API_CLIENT", api)
    monkeypatch.setattr(_services, "BW_CONFIG", bw_config)
    monkeypatch.setattr(_services, "DATA", SimpleNamespace(load_from_file=lambda: None, __enter__=lambda s: {}, __exit__=lambda *a: None))
    monkeypatch.setattr(_services, "build_service_attachments", lambda _service: {})
    monkeypatch.setattr(_services, "get_activation_map", lambda: {})
    captured = {}
    monkeypatch.setattr(_services, "render_template", lambda template, **kwargs: captured.update(kwargs) or "")
    with app.test_request_context(f"/services/{service}", method="GET"):
        _services.services_service_page.__wrapped__(service)
    assert captured, "the route never rendered -- this test proves nothing"
    return captured


class TestThePageWiring:
    def test_the_reserved_service_page_hands_the_shelf_the_curated_subset(self, route_app, monkeypatch):
        rendered_with = _get_service_page(route_app, monkeypatch, DEFAULT_SERVER_ID)
        assert rendered_with["default_server"] is True
        assert rendered_with["allowed_plugins"] == DEFAULT_SERVER_PLUGINS

    def test_an_ordinary_service_page_hands_over_no_allowlist(self, route_app, monkeypatch):
        """Falsy, not empty: the shelf reads a falsy `allowed_plugins` as "no allowlist", and an
        empty tuple would offer an operator nothing at all on every other service."""
        rendered_with = _get_service_page(route_app, monkeypatch, "app.example.com")
        assert rendered_with["default_server"] is False
        assert rendered_with["allowed_plugins"] is None


class TestThePluginPageDirectURL:
    """The shelf hiding a row is not a guard -- the URL is still typable. A page that saved
    settings the default server block never renders is a form that silently does nothing."""

    def _open(self, app, monkeypatch, plugin):
        api = Mock()
        api.readonly = False
        api.get_service.return_value = {"SERVER_NAME": {"value": DEFAULT_SERVER_ID, "method": "wizard"}}
        api.get_metadata.return_value = {"is_pro": False}
        api.get_services.return_value = [{"id": DEFAULT_SERVER_ID, "method": "wizard", "is_draft": False}]
        bw_config = Mock()
        bw_config.get_plugins.return_value = {plugin: {"id": plugin, "name": plugin, "type": "core", "stream": "no", "settings": {}}}
        monkeypatch.setattr(_services, "API_CLIENT", api)
        monkeypatch.setattr(_services, "BW_CONFIG", bw_config)
        monkeypatch.setattr(_services, "DATA", SimpleNamespace())
        rendered = {}
        monkeypatch.setattr(_services, "render_template", lambda template, **kwargs: rendered.update(kwargs) or "")
        with app.test_request_context(f"/services/{DEFAULT_SERVER_ID}/plugins/{plugin}", method="GET"):
            response = _services.services_plugin_page.__wrapped__(DEFAULT_SERVER_ID, plugin)
        return response, rendered

    def test_a_refused_plugin_is_closed(self, route_app, monkeypatch):
        response, rendered = self._open(route_app, monkeypatch, "reverseproxy")
        assert not rendered, "the page rendered a plugin the default server never applies"
        assert response.status_code == 302
        assert "/services" in response.headers["Location"]

    def test_a_curated_plugin_still_opens(self, route_app, monkeypatch):
        """The guard must be the subset, not the reserved id: closing the whole page would leave
        PO ruling 7 with nowhere to edit the headers and error pages it promises."""
        _, rendered = self._open(route_app, monkeypatch, "headers")
        assert rendered, "the curated subset is unreachable on the page that exists for it"


class TestTheOtherTwoWritePaths:
    """Neither of these goes through the API services router, which is where the refusals for the
    reserved id live. Both are reachable from the page PO ruling 7 designates."""

    def test_the_bulk_convert_refuses_the_reserved_id(self, route_app, monkeypatch, reserved_method="wizard"):
        """Drafting the row is deletion by another name.

        DS-B4 re-pin: the row is judged on its id AND its method (PO ruling 4), so this carries the
        REAL seeded method. `is_ui_api_method` refuses `wizard` too, which would make an id-guard
        deletion invisible here -- that hole is closed by the sibling below, where a `ui` row named
        `default-server` MUST convert.
        """
        api = Mock()
        api.readonly = False
        api.get_services.return_value = [
            {"id": DEFAULT_SERVER_ID, "method": reserved_method, "is_draft": False},
            {"id": "app.example.com", "method": "ui", "is_draft": False},
        ]
        flashed = []
        monkeypatch.setattr(_services, "API_CLIENT", api)
        monkeypatch.setattr(_services, "DATA", _FakeData(TO_FLASH=flashed))
        monkeypatch.setattr(_services, "wait_applying", lambda: None)
        bw_config = Mock()
        bw_config.get_config.return_value = {"SERVER_NAME": f"{DEFAULT_SERVER_ID} app.example.com"}
        monkeypatch.setattr(_services, "BW_CONFIG", bw_config)
        executor = Mock()
        monkeypatch.setattr(_services, "CONFIG_TASKS_EXECUTOR", executor)

        with route_app.test_request_context(
            "/services/convert", method="POST", data={"services": f"{DEFAULT_SERVER_ID},app.example.com", "convert_to": "draft", "csrf_token": "x"}
        ):
            _services.services_convert.__wrapped__()
        # The route hands the work to the executor; run it here, which is the only way to observe
        # what it decided.
        job, job_args = executor.submit.call_args[0][0], executor.submit.call_args[0][1:]
        job(*job_args)

        # The method is seeded "ui" here on purpose: with the real "wizard" the row is refused by
        # `is_ui_api_method` and this test would pass with the id guard deleted.
        refused = [entry["content"] for entry in flashed if DEFAULT_SERVER_ID in entry.get("content", "") and entry["type"] == "error"]
        assert refused, f"nothing said the reserved service was refused: {flashed}"
        # ...and the ordinary service in the same request still converted, so this refuses one id
        # rather than the whole request.
        converted = [entry["content"] for entry in flashed if entry["type"] == "success"]
        assert converted and "app.example.com" in converted[0]
        assert DEFAULT_SERVER_ID not in converted[0]

    def test_the_page_save_refuses_a_stream_port_a_service_already_listens_on(self, route_app, monkeypatch):
        """The approved gate asks for the refusal on the API router AND mirrored in the UI page.
        This page does not save through that router (`update_service` -> `BW_CONFIG.edit_service`
        -> `save_config`), so without the mirror the operator saves a colliding port, gets no
        error, and the block is dropped at generation time with the reason in a log."""
        api = Mock()
        api.readonly = False
        api.get_service.return_value = {}
        api.get_metadata.return_value = {"is_pro": False}
        bw_config = Mock()
        bw_config.get_plugins.return_value = {}
        bw_config.get_config.return_value = {
            "MULTISITE": "yes",
            "SERVER_NAME": f"{DEFAULT_SERVER_ID} tcp.example.com",
            "tcp.example.com_SERVER_TYPE": "stream",
            "tcp.example.com_LISTEN_STREAM_PORT": "9000",
        }
        executor = Mock()
        monkeypatch.setattr(_services, "API_CLIENT", api)
        monkeypatch.setattr(_services, "BW_CONFIG", bw_config)
        monkeypatch.setattr(_services, "CONFIG_TASKS_EXECUTOR", executor)
        monkeypatch.setattr(_services, "DATA", _FakeData(TO_FLASH=[]))
        monkeypatch.setattr(_services, "resolve_save_mode", lambda *args, **kwargs: "easy")

        with route_app.test_request_context(f"/services/{DEFAULT_SERVER_ID}", method="POST", data={"csrf_token": "x", "DEFAULT_SERVER_STREAM_PORTS": "9000"}):
            response = _services.services_service_page.__wrapped__(DEFAULT_SERVER_ID)

        assert executor.submit.called is False, "the colliding port was saved"
        assert response.status_code == 302

    @staticmethod
    def _page_save(route_app, monkeypatch, data):
        """The page's POST branch, with the collaborators the two tests above stub by hand.

        Returns the executor mock: `submit` called means the save went through, not called means a
        refusal short-circuited it."""
        api = Mock()
        api.readonly = False
        api.get_service.return_value = {}
        api.get_metadata.return_value = {"is_pro": False}
        bw_config = Mock()
        bw_config.get_plugins.return_value = {}
        bw_config.get_config.return_value = {
            "MULTISITE": "yes",
            "SERVER_NAME": f"{DEFAULT_SERVER_ID} tcp.example.com",
            "tcp.example.com_SERVER_TYPE": "stream",
            "tcp.example.com_LISTEN_STREAM_PORT": "9000",
        }
        executor = Mock()
        monkeypatch.setattr(_services, "API_CLIENT", api)
        monkeypatch.setattr(_services, "BW_CONFIG", bw_config)
        monkeypatch.setattr(_services, "CONFIG_TASKS_EXECUTOR", executor)
        monkeypatch.setattr(_services, "DATA", _FakeData(TO_FLASH=[]))
        monkeypatch.setattr(_services, "resolve_save_mode", lambda *args, **kwargs: "easy")
        with route_app.test_request_context(f"/services/{DEFAULT_SERVER_ID}", method="POST", data={"csrf_token": "x"} | data):
            _services.services_service_page.__wrapped__(DEFAULT_SERVER_ID)
        return executor

    def test_the_page_save_refuses_an_ssl_port_outside_the_port_list(self, route_app, monkeypatch):
        """The subset rule, mirrored on this page for the same reason the collision is: the page the
        operator is told to configure the default server on is not the API router's save path."""
        executor = self._page_save(route_app, monkeypatch, {"DEFAULT_SERVER_STREAM_PORTS": "9001", "DEFAULT_SERVER_STREAM_PORTS_SSL": "7777"})
        assert executor.submit.called is False, "an SSL port with no listener was saved"

    def test_the_page_save_accepts_an_ssl_port_inside_the_port_list(self, route_app, monkeypatch):
        executor = self._page_save(route_app, monkeypatch, {"DEFAULT_SERVER_STREAM_PORTS": "9001", "DEFAULT_SERVER_STREAM_PORTS_SSL": "9001"})
        assert executor.submit.called is True

    def test_the_page_save_refuses_server_type(self, route_app, monkeypatch):
        """DS-B's open item 5. Stored, displayed, and inert -- the reserved id never reaches either
        roster loop, so there is no `server{}` block of either kind for it to switch."""
        executor = self._page_save(route_app, monkeypatch, {"SERVER_TYPE": "stream"})
        assert executor.submit.called is False, "SERVER_TYPE was stored on the reserved row"

    def test_a_free_stream_port_still_saves(self, route_app, monkeypatch):
        """The other half: the mirror must refuse a collision, not the feature."""
        api = Mock()
        api.readonly = False
        api.get_service.return_value = {}
        api.get_metadata.return_value = {"is_pro": False}
        bw_config = Mock()
        bw_config.get_plugins.return_value = {}
        bw_config.get_config.return_value = {
            "MULTISITE": "yes",
            "SERVER_NAME": f"{DEFAULT_SERVER_ID} tcp.example.com",
            "tcp.example.com_SERVER_TYPE": "stream",
            "tcp.example.com_LISTEN_STREAM_PORT": "9000",
        }
        executor = Mock()
        monkeypatch.setattr(_services, "API_CLIENT", api)
        monkeypatch.setattr(_services, "BW_CONFIG", bw_config)
        monkeypatch.setattr(_services, "CONFIG_TASKS_EXECUTOR", executor)
        monkeypatch.setattr(_services, "DATA", _FakeData(TO_FLASH=[]))
        monkeypatch.setattr(_services, "resolve_save_mode", lambda *args, **kwargs: "easy")

        with route_app.test_request_context(f"/services/{DEFAULT_SERVER_ID}", method="POST", data={"csrf_token": "x", "DEFAULT_SERVER_STREAM_PORTS": "9001"}):
            _services.services_service_page.__wrapped__(DEFAULT_SERVER_ID)

        assert executor.submit.called is True


# --------------------------------------------------------------- DS-B4: the three missing guards
# The independent Criticos pass on DS-B found three holes the lane's own tests could not see, plus
# one recovery path that did not exist. All four are here.


def _render_raw(plugins, allowed_plugins=None):
    """`models/plugins_settings_raw.html`, the pane the shelf allowlist never reached."""
    env = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=True)  # nosec B701 - HTML, autoescaped
    env.globals.update(
        url_for=lambda endpoint, **kwargs: "/" + endpoint,
        get_filtered_settings=get_filtered_settings,
        is_editable_method=lambda method, allow_default=False: True,
        get_multiples=get_multiples,
        csrf_token=lambda: "x",
        request=SimpleNamespace(is_secure=True),
        _=lambda key, **kwargs: key,
    )
    return env.get_template("models/plugins_settings_raw.html").render(
        plugins=plugins,
        config={},
        blacklisted_settings=set(),
        current_endpoint=DEFAULT_SERVER_ID,
        clone="",
        theme="light",
        allowed_plugins=allowed_plugins,
    )


class TestTheRawPaneSubset:
    """Criticos REQUIRED 3. The allowlist was added to the compose shelf only, and the Raw tab
    renders every plugin's settings for the same service on the same page -- including SERVER_NAME,
    which is what turned a "rename" through that tab into a silent FORK of the default server into a
    second, billable service."""

    PLUGINS = {plugin_id: _plugin(plugin_id) for plugin_id in ("headers", "errors", "reverseproxy", "antibot")}

    def test_without_an_allowlist_every_plugin_is_offered(self):
        rendered = _render_raw(self.PLUGINS)
        for plugin_id in self.PLUGINS:
            assert f"USE_{plugin_id.upper()}=" in rendered, plugin_id

    def test_with_the_allowlist_only_the_curated_plugins_are_offered(self):
        rendered = _render_raw(self.PLUGINS, allowed_plugins=DEFAULT_SERVER_PLUGINS)
        assert "USE_HEADERS=" in rendered
        assert "USE_ERRORS=" in rendered
        assert "USE_REVERSEPROXY=" not in rendered
        assert "USE_ANTIBOT=" not in rendered

    def test_the_general_plugin_goes_with_them_which_is_what_removes_server_name(self):
        """`SERVER_NAME` belongs to the `general` plugin, which is not in the curated subset, so the
        allowlist takes the rename field out of the editor as well as the refused settings."""
        general = {
            "id": "general",
            "name": "general",
            "type": "core",
            "stream": "no",
            "settings": {"SERVER_NAME": {"context": "multisite", "default": "", "label": "s", "type": "text", "help": "h"}},
        }
        assert "SERVER_NAME=" in _render_raw({"general": general})
        assert "SERVER_NAME=" not in _render_raw({"general": general}, allowed_plugins=DEFAULT_SERVER_PLUGINS)


def _post_service_page(app, monkeypatch, service, data, *, services_rows=None):
    """POST the real service page and return (response, flashes). No executor work is run: the
    refusals under test all happen before the submit."""
    api = Mock()
    api.readonly = False
    api.get_services.return_value = services_rows or [{"id": DEFAULT_SERVER_ID, "method": "wizard", "is_draft": False}]
    api.get_metadata.return_value = {"is_pro": False}
    bw_config = Mock()
    bw_config.get_config.return_value = {"SERVER_NAME": f"{DEFAULT_SERVER_ID} app.example.com"}
    monkeypatch.setattr(_services, "API_CLIENT", api)
    monkeypatch.setattr(_services, "BW_CONFIG", bw_config)
    monkeypatch.setattr(_services, "DATA", _FakeData())
    executor = Mock()
    monkeypatch.setattr(_services, "CONFIG_TASKS_EXECUTOR", executor)
    flashed = []
    # `handle_error`, not `flash`: the route refuses through it, and it is what turns a refusal into
    # a redirect the operator can see.
    monkeypatch.setattr(_services, "handle_error", lambda message="", redirect_url="", **kwargs: flashed.append(("error", message)) or "")
    with app.test_request_context(f"/services/{service}", method="POST", data=data):
        response = _services.services_service_page.__wrapped__(service)
    return response, flashed, executor


class TestTheRenameRefusalOnThePage:
    """Criticos REQUIRED 3, second half. The API has refused this since DS-B; this page does not
    save through the API services router -- `update_service` goes to `BW_CONFIG.edit_service` ->
    `save_config` -- so the refusal had to be mirrored or it was not a refusal at all."""

    def test_renaming_the_reserved_service_is_refused(self, route_app, monkeypatch):
        _, flashed, executor = _post_service_page(route_app, monkeypatch, DEFAULT_SERVER_ID, {"csrf_token": "x", "SERVER_NAME": "forked.example.com"})
        assert [message for category, message in flashed if category == "error" and DEFAULT_SERVER_ID in message], flashed
        executor.submit.assert_not_called()

    def test_a_save_that_echoes_its_own_name_back_is_not_a_rename(self, route_app, monkeypatch):
        _, flashed, executor = _post_service_page(route_app, monkeypatch, DEFAULT_SERVER_ID, {"csrf_token": "x", "SERVER_NAME": DEFAULT_SERVER_ID})
        assert not [message for category, message in flashed if category == "error"], flashed
        executor.submit.assert_called_once()

    def test_a_save_that_posts_no_name_at_all_still_goes_through(self, route_app, monkeypatch):
        """The curated raw pane and the compose shelf both post without SERVER_NAME now, so a guard
        that read a missing field as "renamed to empty" would refuse every save on the page."""
        _, flashed, executor = _post_service_page(route_app, monkeypatch, DEFAULT_SERVER_ID, {"csrf_token": "x", "SSL_PROTOCOLS": "TLSv1.3"})
        assert not [message for category, message in flashed if category == "error"], flashed
        executor.submit.assert_called_once()

    def test_an_operators_own_service_of_that_name_can_be_renamed(self, route_app, monkeypatch):
        """PO ruling 4: the rename is that row's only recovery, so the refusal must not reach it."""
        _, flashed, executor = _post_service_page(
            route_app,
            monkeypatch,
            DEFAULT_SERVER_ID,
            {"csrf_token": "x", "SERVER_NAME": "recovered.example.com"},
            services_rows=[{"id": DEFAULT_SERVER_ID, "method": "ui", "is_draft": False}],
        )
        assert not [message for category, message in flashed if category == "error"], flashed
        executor.submit.assert_called_once()

    def test_creating_a_service_under_the_reserved_name_is_refused(self, route_app, monkeypatch):
        """`POST /services` refuses the id (api/app/routers/services.py) and this page creates
        services too. In multisite the collision was caught only incidentally, by the "already
        exists" check in `models/config.py` -- which depends on the reserved row being in the
        roster; in single-site it is not, so nothing caught it at all."""
        _, flashed, executor = _post_service_page(route_app, monkeypatch, "new", {"csrf_token": "x", "SERVER_NAME": DEFAULT_SERVER_ID}, services_rows=[])
        assert [message for category, message in flashed if category == "error" and DEFAULT_SERVER_ID in message], flashed
        executor.submit.assert_not_called()

    def test_creating_an_ordinary_service_still_works(self, route_app, monkeypatch):
        _, flashed, executor = _post_service_page(route_app, monkeypatch, "new", {"csrf_token": "x", "SERVER_NAME": "brand.example.com"}, services_rows=[])
        assert not [message for category, message in flashed if category == "error"], flashed
        executor.submit.assert_called_once()

    def test_an_ordinary_service_is_untouched(self, route_app, monkeypatch):
        _, flashed, executor = _post_service_page(
            route_app,
            monkeypatch,
            "app.example.com",
            {"csrf_token": "x", "SERVER_NAME": "renamed.example.com"},
            services_rows=[{"id": "app.example.com", "method": "ui", "is_draft": False}],
        )
        assert not [message for category, message in flashed if category == "error"], flashed
        executor.submit.assert_called_once()


class TestTheServicesListInSingleSite:
    def test_the_page_asks_whether_this_deployment_is_multisite(self, route_app, monkeypatch):
        """PO ruling 1 of 2026-09-06: no pinned entry in single-site mode -- the API stops returning
        the row -- and one sentence on the list page instead of silence."""
        api = Mock()
        api.get_services.return_value = [{"id": "app.example.com", "method": "ui", "is_draft": False}]
        api.get_configs.return_value = []
        bw_config = Mock()
        monkeypatch.setattr(_services, "API_CLIENT", api)
        monkeypatch.setattr(_services, "BW_CONFIG", bw_config)
        captured = {}
        monkeypatch.setattr(_services, "render_template", lambda template, **kwargs: captured.update(kwargs) or "")

        for multisite, expected in (("no", True), ("yes", False)):
            bw_config.get_config.return_value = {"MULTISITE": multisite}
            with route_app.test_request_context("/services", method="GET"):
                _services.services_page.__wrapped__()
            assert captured["single_site"] is expected, multisite

    def test_an_api_that_cannot_answer_shows_no_notice(self, route_app, monkeypatch):
        """A wrong explainer is worse than none."""
        api = Mock()
        api.get_services.return_value = []
        api.get_configs.return_value = []
        bw_config = Mock()
        bw_config.get_config.side_effect = RuntimeError("boom")
        monkeypatch.setattr(_services, "API_CLIENT", api)
        monkeypatch.setattr(_services, "BW_CONFIG", bw_config)
        captured = {}
        monkeypatch.setattr(_services, "render_template", lambda template, **kwargs: captured.update(kwargs) or "")
        with route_app.test_request_context("/services", method="GET"):
            _services.services_page.__wrapped__()
        assert captured["single_site"] is False
