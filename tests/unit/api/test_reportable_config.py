"""``/services/{service}`` and ``/global_config`` report what the GENERATOR renders.

Port of dev ``b8f59c5a7`` (#3866). Both read endpoints answered a non-``full`` request with
``get_non_default_settings``, which joins the settings table against the STORED rows: a value a
config TEMPLATE supplies has no row, so it was absent from the answer -- and a service that
inherited a global row while its template overrode that value was told the global value, the one
the generator was about to discard. The endpoints now take ``get_config(methods=True)`` (the same
resolution the generator uses) and reduce it with ``reportable_config``.

The router loaders here mirror ``test_services_reserved.py``'s; ``reportable_config`` itself is
loaded for real from ``src/api/app/utils.py`` (``fixtures/api_utils.py``).
"""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

import pytest
import schemas  # type: ignore

from fixtures.api_utils import load_api_utils

ROOT = Path(__file__).resolve().parents[3]

SERVICE = "app.example.com"

reportable_config = load_api_utils().reportable_config


class _Router:
    def __init__(self, **_kwargs):
        pass

    def get(self, *_args, **_kwargs):
        return lambda function: function

    post = get
    put = get
    patch = get
    delete = get


class _Response:
    def __init__(self, *, status_code, content):
        self.status_code = status_code
        self.content = content


def _load(package: str, router: str) -> ModuleType:
    names = {
        "fastapi": ModuleType("fastapi"),
        "fastapi.responses": ModuleType("fastapi.responses"),
        package: ModuleType(package),
        f"{package}.routers": ModuleType(f"{package}.routers"),
        f"{package}.auth": ModuleType(f"{package}.auth"),
        f"{package}.auth.guard": ModuleType(f"{package}.auth.guard"),
        f"{package}.schemas": schemas,
        f"{package}.utils": ModuleType(f"{package}.utils"),
    }
    names["fastapi"].APIRouter = _Router
    names["fastapi"].Depends = lambda dependency: dependency
    names["fastapi"].Query = lambda default=..., **_kwargs: default
    names["fastapi.responses"].JSONResponse = _Response
    names[package].__path__ = []
    names[f"{package}.routers"].__path__ = []
    names[f"{package}.auth"].__path__ = []
    names[f"{package}.auth.guard"].guard = object()
    names[f"{package}.utils"].get_db = Mock()
    names[f"{package}.utils"].LOGGER = Mock()
    names[f"{package}.utils"].reportable_config = reportable_config
    http01_spec = importlib.util.spec_from_file_location(f"{package}.http01", ROOT / "src" / "api" / "app" / "http01.py")
    http01 = importlib.util.module_from_spec(http01_spec)
    http01_spec.loader.exec_module(http01)
    names[f"{package}.http01"] = http01
    with patch.dict(sys.modules, names):
        path = ROOT / "src" / "api" / "app" / "routers" / f"{router}.py"
        spec = importlib.util.spec_from_file_location(f"{package}.routers.{router}", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module


SERVICES = _load("bw_rc_services", "services")
GLOBAL_SETTINGS = _load("bw_rc_global", "global_settings")


# A resolved snapshot in `get_config(methods=True)` shape: one explicit row, one value a template
# supplies, one untouched plugin default.
def _resolved(prefix: str = "") -> dict:
    return {
        f"{prefix}USE_ANTIBOT": {"value": "captcha", "global": False, "method": "ui", "default": "no", "template": None},
        f"{prefix}USE_REVERSE_PROXY": {"value": "yes", "global": False, "method": "default", "default": "no", "template": "low"},
        f"{prefix}USE_GZIP": {"value": "no", "global": False, "method": "default", "default": "no", "template": None},
    }


class TestReportableConfig:
    def test_an_explicit_row_is_reported(self):
        assert reportable_config(_resolved(), methods=False)["USE_ANTIBOT"] == "captcha"

    def test_a_template_supplied_value_is_reported(self):
        """The whole point of the row: no stored row, but the generator renders it."""
        assert reportable_config(_resolved(), methods=False)["USE_REVERSE_PROXY"] == "yes"

    def test_an_untouched_plugin_default_stays_out(self):
        assert "USE_GZIP" not in reportable_config(_resolved(), methods=False)

    def test_methods_true_keeps_the_metadata_dict(self):
        entry = reportable_config(_resolved(), methods=True)["USE_REVERSE_PROXY"]
        assert entry["template"] == "low"
        assert entry["value"] == "yes"

    def test_a_non_dict_entry_passes_through(self):
        """`get_config` can hand back a bare value; dropping it would truncate the answer."""
        assert reportable_config({"SERVER_NAME": SERVICE}, methods=True)["SERVER_NAME"] == SERVICE

    def test_a_dict_with_no_method_key_is_treated_as_a_default(self):
        assert reportable_config({"X": {"value": "1"}}, methods=False) == {}

    def test_an_empty_template_string_does_not_promote_a_default(self):
        """`template: ""` is "no owning layer", the same as None -- a truthiness check, not `is not None`."""
        assert reportable_config({"X": {"value": "1", "method": "default", "template": ""}}, methods=False) == {}

    def test_is_draft_survives_the_reduction(self):
        """Criticos: dropping it silently PUBLISHES every draft the operator did not touch.

        `get_config` synthesises `{service}_IS_DRAFT` from the `bw_services` column under the
        synthetic method `default` (`db_methods/config_read.py:185`), so the plain rule drops it.
        This endpoint is the snapshot the UI hands back to `save_config`
        (`src/ui/app/models/config.py:104-127` → `src/ui/app/routes/services.py:604-609`), and
        `save_config` reads an ABSENT key as "not a draft" and un-drafts the service
        (`db_methods/config_save.py:1159`, `:1174-1190`).
        """
        conf = {"app.example.com_IS_DRAFT": {"value": "yes", "global": False, "method": "default", "default": "no", "template": None}}

        assert reportable_config(conf, methods=False) == {"app.example.com_IS_DRAFT": "yes"}

    def test_the_service_view_keeps_its_stripped_is_draft(self):
        """`get_config(service=...)` strips the prefix, so the key arrives bare."""
        conf = {"IS_DRAFT": {"value": "yes", "global": False, "method": "default", "default": "no", "template": None}}

        assert reportable_config(conf, methods=False) == {"IS_DRAFT": "yes"}


@pytest.fixture
def service_db(monkeypatch):
    db = Mock()
    db.get_services.return_value = [{"id": SERVICE, "method": "ui", "is_draft": False}]
    db.get_config.return_value = _resolved()
    db.get_non_default_settings.return_value = {"NEVER": "called"}
    monkeypatch.setattr(SERVICES, "get_db", lambda: db)
    return db


@pytest.fixture
def global_db(monkeypatch):
    db = Mock()
    db.get_config.return_value = _resolved()
    db.get_non_default_settings.return_value = {"NEVER": "called"}
    monkeypatch.setattr(GLOBAL_SETTINGS, "get_db", lambda: db)
    return db


class TestGetServiceEndpoint:
    def test_it_reports_the_template_supplied_value(self, service_db):
        response = SERVICES.get_service(SERVICE, full=False, methods=False)

        assert response.status_code == 200
        assert response.content["config"] == {"USE_ANTIBOT": "captcha", "USE_REVERSE_PROXY": "yes"}

    def test_it_reads_the_resolved_config_not_the_stored_rows(self, service_db):
        SERVICES.get_service(SERVICE, full=False, methods=False)

        service_db.get_non_default_settings.assert_not_called()
        # `methods=True` is not the caller's flag: the reduction needs the metadata to decide, and
        # `methods` only chooses the SHAPE of what survives it.
        assert service_db.get_config.call_args.kwargs["methods"] is True
        assert service_db.get_config.call_args.kwargs["service"] == SERVICE

    def test_full_still_returns_everything(self, service_db):
        response = SERVICES.get_service(SERVICE, full=True, methods=False)

        assert set(response.content["config"]) == {"USE_ANTIBOT", "USE_REVERSE_PROXY", "USE_GZIP"}


class TestReadGlobalSettingsEndpoint:
    def test_it_reports_the_template_supplied_value(self, global_db):
        response = GLOBAL_SETTINGS.read_global_settings(full=False, methods=False)

        assert response.content["settings"] == {"USE_ANTIBOT": "captcha", "USE_REVERSE_PROXY": "yes"}

    def test_it_reads_the_resolved_config_not_the_stored_rows(self, global_db):
        GLOBAL_SETTINGS.read_global_settings(full=False, methods=False, filtered_settings=["USE_ANTIBOT"])

        global_db.get_non_default_settings.assert_not_called()
        assert global_db.get_config.call_args.kwargs["methods"] is True
        assert global_db.get_config.call_args.kwargs["filtered_settings"] == ("USE_ANTIBOT",)


# A resolved snapshot carrying the port-list materialisation `get_config` performs: the global
# entries are copied down to every service, and `config_read.py:222` SHARES the dict object, so an
# inherited copy is the global row -- `global: True`, the global row's method. `HTTP_PORT_1` is
# what makes this reachable: a fleet with more than one listen port.
def _with_inherited_ports() -> dict:
    http_port = {"value": "8080", "global": True, "method": "scheduler", "default": "8080", "template": None}
    http_port_1 = {"value": "8081", "global": True, "method": "manual", "default": "", "template": None}
    antibot = {"value": "captcha", "global": True, "method": "ui", "default": "no", "template": None}
    return {
        "SERVER_NAME": {"value": "app1.example.com app2.example.com", "global": True, "method": "scheduler", "default": "", "template": None},
        "HTTP_PORT": http_port,
        "HTTP_PORT_1": http_port_1,
        "USE_ANTIBOT": antibot,
        # app1 declared its own port; the suffixed member was materialised from the global.
        "app1.example.com_HTTP_PORT": {"value": "9000", "global": False, "method": "ui", "default": "8080", "template": None},
        "app1.example.com_HTTP_PORT_1": http_port_1,
        "app1.example.com_USE_ANTIBOT": antibot,
        # app2 declared nothing at all.
        "app2.example.com_HTTP_PORT": http_port,
        "app2.example.com_HTTP_PORT_1": http_port_1,
    }


class TestInheritedPortLists:
    """A port list a service never declared must never be REPORTED as if it had.

    A service REPLACES the global port list rather than extending it
    (`ports.drop_inherited_ports`), and the presence of a row is the only thing that says "this
    service declared a port" -- which is why `get_non_default_settings` refuses to materialise the
    port families (`config_read.py:199-213`) while `get_config` must.

    This view is handed straight back to `save_config` by three UI flows (bulk convert to draft,
    delete a service, and saving the global settings page), and `_moved_port_groups`
    (`config_save.py:269-334`) reads a PARTIAL list as a move and persists every posted member. So
    reporting the inherited copies rewrites the fleet's ports: measured on a real database,
    converting one unrelated service to a draft gave app1 a `HTTP_PORT_1` row it never declared,
    and in the shape below -- a fleet whose only port row is a SUFFIXED one -- gave every service a
    row that drops the fleet's base port at render time (`ports.drop_inherited_ports`).
    """

    def test_an_inherited_port_member_is_not_reported_for_a_service(self):
        conf = reportable_config(_with_inherited_ports(), methods=True)

        assert "app1.example.com_HTTP_PORT_1" not in conf
        assert "app2.example.com_HTTP_PORT" not in conf
        assert "app2.example.com_HTTP_PORT_1" not in conf

    def test_the_services_own_port_row_is_still_reported(self):
        conf = reportable_config(_with_inherited_ports(), methods=True)

        assert conf["app1.example.com_HTTP_PORT"]["value"] == "9000"

    def test_the_global_port_list_is_still_reported(self):
        """The bare global keys carry `global: True` too, and they are the fleet's real answer."""
        conf = reportable_config(_with_inherited_ports(), methods=True)

        assert conf["HTTP_PORT"]["value"] == "8080"
        assert conf["HTTP_PORT_1"]["value"] == "8081"

    def test_only_the_port_families_are_narrowed(self):
        """The guard is about port lists, not about inheritance in general."""
        conf = reportable_config(_with_inherited_ports(), methods=True)

        assert conf["app1.example.com_USE_ANTIBOT"]["value"] == "captcha"

    def test_the_service_view_drops_the_inherited_member_it_did_not_declare(self):
        """`get_config(service=…)` strips the prefix, so the inheritance shows only in `global`."""
        conf = reportable_config(
            {
                "HTTP_PORT": {"value": "9000", "global": False, "method": "ui", "default": "8080", "template": None},
                "HTTP_PORT_1": {"value": "8081", "global": True, "method": "manual", "default": "", "template": None},
            },
            methods=True,
            service="app1.example.com",
        )

        assert conf["HTTP_PORT"]["value"] == "9000"
        assert "HTTP_PORT_1" not in conf

    def test_a_fleet_whose_only_port_row_is_suffixed_leaks_to_every_service(self):
        """The shape that costs a service the fleet's base port.

        With no global `HTTP_PORT` row, `HTTP_PORT_1` is materialised onto every service on its
        own. Reported, it comes back as that service's WHOLE declared list, and
        `ports.drop_inherited_ports` then renders the service without the fleet's base port.
        """
        http_port_1 = {"value": "8081", "global": True, "method": "manual", "default": "", "template": None}
        conf = reportable_config(
            {
                "SERVER_NAME": {"value": "app1.example.com app2.example.com", "global": True, "method": "scheduler", "default": "", "template": None},
                "HTTP_PORT_1": http_port_1,
                "app1.example.com_HTTP_PORT_1": http_port_1,
                "app2.example.com_HTTP_PORT_1": http_port_1,
            },
            methods=True,
        )

        assert conf["HTTP_PORT_1"]["value"] == "8081", "the fleet's own row is still the answer"
        assert "app1.example.com_HTTP_PORT_1" not in conf
        assert "app2.example.com_HTTP_PORT_1" not in conf

    def test_a_service_id_that_prefixes_another_does_not_leak(self):
        """`SERVER_NAME` allows `_`, so a shortest-first prefix scan mis-splits the longer id."""
        http_port_1 = {"value": "8081", "global": True, "method": "manual", "default": "", "template": None}
        conf = reportable_config(
            {
                "SERVER_NAME": {"value": "app app_staging", "global": True, "method": "scheduler", "default": "", "template": None},
                "HTTP_PORT_1": http_port_1,
                "app_HTTP_PORT_1": http_port_1,
                "app_staging_HTTP_PORT_1": http_port_1,
            },
            methods=True,
        )

        assert "app_HTTP_PORT_1" not in conf
        assert "app_staging_HTTP_PORT_1" not in conf
