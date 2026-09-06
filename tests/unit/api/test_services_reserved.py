"""``/services`` must refuse to create, rename, draft or delete the reserved default server.

The reserved ``default-server`` row is what makes the default server configurable, and it is
permanent: every path that could remove it is a path to a deployment whose catch-all block silently
falls back to the global-only rendering, with the operator's certificate, TLS and error-page
settings still stored and no longer applied. The database layer refuses to delete the row
(``tests/unit/db/test_default_server_service.py``); this file is the other half -- the API says so,
in one sentence, before anything is written.

Same module-loader + stubbed-``sys.modules`` pattern as ``test_services_validation.py``: there is
no live ``TestClient`` in ``tests/unit/api``, so the handlers are called directly.
"""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

import pytest
import schemas  # type: ignore

from default_server import DEFAULT_SERVER_ID  # type: ignore

ROOT = Path(__file__).resolve().parents[3]

SERVICE = "app.example.com"


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


def _load_router():
    names = {
        "fastapi": ModuleType("fastapi"),
        "fastapi.responses": ModuleType("fastapi.responses"),
        "bw_services": ModuleType("bw_services"),
        "bw_services.routers": ModuleType("bw_services.routers"),
        "bw_services.auth": ModuleType("bw_services.auth"),
        "bw_services.auth.guard": ModuleType("bw_services.auth.guard"),
        "bw_services.schemas": schemas,
        "bw_services.utils": ModuleType("bw_services.utils"),
    }
    names["fastapi"].APIRouter = _Router
    names["fastapi"].Depends = lambda dependency: dependency
    names["fastapi"].Query = lambda default=..., **_kwargs: default
    names["fastapi.responses"].JSONResponse = _Response
    names["bw_services"].__path__ = []
    names["bw_services.routers"].__path__ = []
    names["bw_services.auth"].__path__ = []
    names["bw_services.auth.guard"].guard = object()
    names["bw_services.utils"].get_db = Mock()
    http01_spec = importlib.util.spec_from_file_location("bw_services.http01", ROOT / "src" / "api" / "app" / "http01.py")
    http01 = importlib.util.module_from_spec(http01_spec)
    http01_spec.loader.exec_module(http01)
    names["bw_services.http01"] = http01
    with patch.dict(sys.modules, names):
        path = ROOT / "src" / "api" / "app" / "routers" / "services.py"
        spec = importlib.util.spec_from_file_location("bw_services.routers.services", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module


ROUTER = _load_router()


@pytest.fixture
def db(monkeypatch):
    fake_db = Mock()
    # A fresh dict per call: the handlers mutate the snapshot they are handed, and a shared
    # `return_value` would let one test's delete change the roster the next call sees.
    fake_db.get_non_default_settings.side_effect = lambda *_args, **_kwargs: {"SERVER_NAME": f"{SERVICE} {DEFAULT_SERVER_ID}"}
    fake_db.save_config.return_value = set()
    fake_db.unknown_template_layers.return_value = []
    fake_db.is_valid_setting.return_value = (True, "")
    fake_db.get_config.return_value = {"HTTP_PORT": "8080"}
    # MULTISITE matters to `list_services` since DS-B4: the reserved row is a multisite-only
    # feature and the listing hides it in single-site mode.
    fake_db.is_multisite.return_value = True
    fake_db.get_services.return_value = [
        {"id": SERVICE, "method": "ui", "is_draft": False},
        {"id": DEFAULT_SERVER_ID, "method": "wizard", "is_draft": False},
    ]
    monkeypatch.setattr(ROUTER, "get_db", lambda: fake_db)
    return fake_db


def _explains_why(response):
    """PO ruling 7: the refusal has to say what the default server IS, not just "forbidden"."""
    message = response.content["message"]
    assert DEFAULT_SERVER_ID in message
    assert "match no configured service" in message


class TestRefusals:
    def test_creating_it_is_refused(self, db):
        response = ROUTER.create_service(schemas.ServiceCreateRequest(server_name=DEFAULT_SERVER_ID, variables={}))
        assert response.status_code == 403
        _explains_why(response)
        db.save_config.assert_not_called()

    def test_deleting_it_is_refused(self, db):
        response = ROUTER.delete_service(DEFAULT_SERVER_ID)
        assert response.status_code == 403
        _explains_why(response)
        db.save_config.assert_not_called()
        db.delete_services.assert_not_called()

    def test_renaming_it_away_is_refused(self, db):
        response = ROUTER.update_service(DEFAULT_SERVER_ID, schemas.ServiceUpdateRequest(server_name="anything.example.com"))
        assert response.status_code == 403
        _explains_why(response)
        db.save_config.assert_not_called()

    def test_renaming_another_service_ONTO_the_reserved_id_is_refused(self, db):
        """The direction a name-only guard on the create path misses entirely."""
        response = ROUTER.update_service(SERVICE, schemas.ServiceUpdateRequest(server_name=DEFAULT_SERVER_ID))
        assert response.status_code == 403
        _explains_why(response)
        db.save_config.assert_not_called()

    def test_drafting_it_is_refused(self, db):
        """A drafted row drops out of SERVER_NAME, so the default server falls back to the
        global-only rendering with no error anywhere -- deletion by another name."""
        response = ROUTER.update_service(DEFAULT_SERVER_ID, schemas.ServiceUpdateRequest(is_draft=True))
        assert response.status_code == 403
        db.save_config.assert_not_called()

    def test_converting_it_to_draft_is_refused(self, db):
        response = ROUTER.convert_service(DEFAULT_SERVER_ID, convert_to="draft")
        assert response.status_code == 403
        db.save_config.assert_not_called()


class TestWhatStaysAllowed:
    def test_it_is_configurable(self, db):
        """The point of the row. Refusing the writes that would remove it must not refuse the
        writes that configure it."""
        response = ROUTER.update_service(DEFAULT_SERVER_ID, schemas.ServiceUpdateRequest(variables={"SSL_PROTOCOLS": "TLSv1.3"}))
        assert response.status_code == 200
        saved = db.save_config.call_args[0][0]
        assert saved[f"{DEFAULT_SERVER_ID}_SSL_PROTOCOLS"] == "TLSv1.3"

    def test_a_patch_that_echoes_its_own_name_back_is_not_a_rename(self, db):
        response = ROUTER.update_service(DEFAULT_SERVER_ID, schemas.ServiceUpdateRequest(server_name=DEFAULT_SERVER_ID))
        assert response.status_code == 200

    def test_an_ordinary_service_is_untouched_by_any_of_it(self, db):
        assert ROUTER.delete_service(SERVICE).status_code == 200
        assert ROUTER.update_service(SERVICE, schemas.ServiceUpdateRequest(server_name="renamed.example.com")).status_code == 200

    def test_the_listing_flags_it(self, db):
        """A client cannot hide it -- that would hide the only page its certificate is set on -- so
        it is returned like any other service and flagged instead."""
        response = ROUTER.list_services()
        rows = {row["id"]: row for row in response.content["services"]}
        assert rows[DEFAULT_SERVER_ID]["reserved"] is True
        assert rows[SERVICE]["reserved"] is False


class TestStreamPortRefusal:
    """PO ruling 6 / the approved stream gate.

    Stream has no SNI on plain TCP and none at all on UDP, so NGINX picks the block by
    ``address:port`` alone: a ``default_server`` on a port a service already listens on WINS and
    answers -- then closes -- that service's traffic. Saving such a port is therefore an outage,
    and the API is where an operator finds out, in a sentence naming both the port and the owner.
    """

    @staticmethod
    def _snapshot(**extra):
        base = {
            "SERVER_NAME": f"{SERVICE} {DEFAULT_SERVER_ID}",
            f"{SERVICE}_SERVER_TYPE": "stream",
            f"{SERVICE}_LISTEN_STREAM_PORT": "9000",
            f"{SERVICE}_LISTEN_STREAM_PORT_SSL": "9443",
        }
        base.update(extra)
        return base

    def _patch_ports(self, db, value, **extra):
        db.get_non_default_settings.side_effect = lambda *_a, **_k: self._snapshot(**extra)
        return ROUTER.update_service(DEFAULT_SERVER_ID, schemas.ServiceUpdateRequest(variables={"DEFAULT_SERVER_STREAM_PORTS": value}))

    def test_a_port_a_stream_service_listens_on_is_refused(self, db):
        response = self._patch_ports(db, "9000")
        assert response.status_code == 400
        assert "9000" in response.content["message"]
        assert SERVICE in response.content["message"]
        db.save_config.assert_not_called()

    def test_the_services_ssl_stream_port_is_refused_too(self, db):
        """`LISTEN_STREAM_PORT_SSL` is a listener like any other -- a guard that only scanned
        `LISTEN_STREAM_PORT` would hand the catch-all a service's TLS port."""
        response = self._patch_ports(db, "9443")
        assert response.status_code == 400
        assert "9443" in response.content["message"]
        db.save_config.assert_not_called()

    def test_a_free_port_is_saved(self, db):
        response = self._patch_ports(db, "9999")
        assert response.status_code == 200
        db.save_config.assert_called_once()
        saved = db.save_config.call_args[0][0]
        assert saved[f"{DEFAULT_SERVER_ID}_DEFAULT_SERVER_STREAM_PORTS"] == "9999"

    def test_a_port_declared_by_an_HTTP_service_is_free(self, db):
        """`stream.conf` never includes an http service's `server-stream.conf`, so its stream port
        settings load no listener and cannot collide. Refusing on them would be a refusal an
        operator cannot act on."""
        response = self._patch_ports(db, "9000", **{f"{SERVICE}_SERVER_TYPE": "http"})
        assert response.status_code == 200
        db.save_config.assert_called_once()

    def test_editing_another_service_onto_the_reserved_port_is_NOT_refused(self, db):
        """The gate's asymmetry, on purpose: the collision is resolved at generation time by
        dropping the RESERVED block, never the service's. A 400 here would let the catch-all veto a
        service's configuration."""
        db.get_non_default_settings.side_effect = lambda *_a, **_k: self._snapshot(**{f"{DEFAULT_SERVER_ID}_DEFAULT_SERVER_STREAM_PORTS": "9500"})
        response = ROUTER.update_service(SERVICE, schemas.ServiceUpdateRequest(variables={"LISTEN_STREAM_PORT": "9500"}))
        assert response.status_code == 200
        db.save_config.assert_called_once()


class TestStreamSslSubsetRefusal:
    """`DEFAULT_SERVER_STREAM_PORTS_SSL` is the TLS switch of the ports the default server declares,
    not a second set of listeners. A port only in the SSL list has nothing to switch, so the
    renderer drops it -- and an operator who believes a port is encrypted when it is not, or is not
    served at all, is exactly the outcome a save-time refusal exists to prevent."""

    def _patch(self, db, ports, ssl_ports, **extra):
        db.get_non_default_settings.side_effect = lambda *_a, **_k: TestStreamPortRefusal._snapshot(**extra)
        variables = {}
        if ssl_ports is not None:
            variables["DEFAULT_SERVER_STREAM_PORTS_SSL"] = ssl_ports
        if ports is not None:
            variables["DEFAULT_SERVER_STREAM_PORTS"] = ports
        return ROUTER.update_service(DEFAULT_SERVER_ID, schemas.ServiceUpdateRequest(variables=variables))

    def test_an_ssl_port_outside_the_port_list_is_refused(self, db):
        response = self._patch(db, "9999", "7777")
        assert response.status_code == 400
        assert "7777" in response.content["message"]
        assert "DEFAULT_SERVER_STREAM_PORTS" in response.content["message"]
        db.save_config.assert_not_called()

    def test_an_ssl_port_inside_the_port_list_is_saved(self, db):
        response = self._patch(db, "9999", "9999")
        assert response.status_code == 200, response.content
        db.save_config.assert_called_once()

    def test_shrinking_the_port_list_away_from_a_stored_ssl_port_is_ACCEPTED(self, db):
        """Documented, not an oversight. The refusal is scoped to the ports the REQUEST declares --
        DS-B's rule, because a refusal on stored state locks the page over a pane that may not even
        show the field. So the save that removes 7777 from the port list, without mentioning the SSL
        list, goes through and leaves a stored SSL entry with nothing to switch. `Templator` is where
        the operator finds out: it drops the orphan and logs the reason
        (`tests/unit/gen/test_default_server_stream.py::…_is_an_orphan`)."""
        response = self._patch(db, "9500", None, **{f"{DEFAULT_SERVER_ID}_DEFAULT_SERVER_STREAM_PORTS_SSL": "7777"})
        assert response.status_code == 200, response.content
        db.save_config.assert_called_once()

    def test_the_subset_is_judged_on_the_merge_not_on_the_request(self, db):
        """The port can have been saved in an earlier request. Judging the SSL list against only
        what THIS request carries would refuse a legitimate "make the port I already have TLS"."""
        response = self._patch(db, None, "9500", **{f"{DEFAULT_SERVER_ID}_DEFAULT_SERVER_STREAM_PORTS": "9500"})
        assert response.status_code == 200, response.content
        db.save_config.assert_called_once()


class TestServerTypeRefusal:
    """DS-B's open item 5, ruled on 2026-09-03. `SERVER_TYPE` on the reserved row would be stored,
    shown on its page and do nothing at all: the reserved id is dropped from the roster both
    `http.conf` and `stream.conf` iterate, so it never gets a `server{}` block of either kind."""

    def test_setting_it_on_the_reserved_service_is_refused(self, db):
        response = ROUTER.update_service(DEFAULT_SERVER_ID, schemas.ServiceUpdateRequest(variables={"SERVER_TYPE": "stream"}))
        assert response.status_code == 400
        assert "SERVER_TYPE" in response.content["message"]
        db.save_config.assert_not_called()

    def test_http_is_refused_too_because_the_value_is_not_the_point(self, db):
        response = ROUTER.update_service(DEFAULT_SERVER_ID, schemas.ServiceUpdateRequest(variables={"SERVER_TYPE": "http"}))
        assert response.status_code == 400
        db.save_config.assert_not_called()

    def test_an_ordinary_service_still_sets_it(self, db):
        response = ROUTER.update_service(SERVICE, schemas.ServiceUpdateRequest(variables={"SERVER_TYPE": "stream"}))
        assert response.status_code == 200, response.content
        db.save_config.assert_called_once()


class TestTheRefusalIsScopedToTheRequest:
    """A refusal on stored state locks the resource. A service can take a port the reserved list
    already held -- the renderer resolves that by dropping the reserved block, failing safe towards
    the real service -- so a later write that does not touch the port list must still go through."""

    def _stored_collision(self, db):
        """The state that used to lock the resource: the reserved list already holds 9000 and the
        service took it afterwards."""
        db.get_non_default_settings.side_effect = lambda *_a, **_k: TestStreamPortRefusal._snapshot(
            **{f"{DEFAULT_SERVER_ID}_DEFAULT_SERVER_STREAM_PORTS": "9000"}
        )

    def test_a_write_that_does_not_touch_the_ports_is_not_refused(self, db):
        self._stored_collision(db)
        response = ROUTER.update_service(DEFAULT_SERVER_ID, schemas.ServiceUpdateRequest(variables={"SSL_PROTOCOLS": "TLSv1.3"}))
        assert response.status_code == 200, response.content

    def test_a_write_that_declares_the_colliding_port_is_still_refused(self, db):
        self._stored_collision(db)
        response = ROUTER.update_service(DEFAULT_SERVER_ID, schemas.ServiceUpdateRequest(variables={"DEFAULT_SERVER_STREAM_PORTS": "9000"}))
        assert response.status_code == 400, response.content


class TestTheListingIsMultisiteOnly:
    """PO ruling of 2026-09-06: the reserved service is a multisite feature and the API says so.

    Single-site has no per-service materialisation and no per-site variables table, so the row --
    which a deployment that was multisite once still holds -- would be a page whose every setting
    silently resolves to the globals. Hiding it in the listing is what keeps the UI from pinning it.
    """

    def test_single_site_returns_no_reserved_row(self, db):
        db.is_multisite.return_value = False

        rows = {row["id"] for row in ROUTER.list_services().content["services"]}

        assert rows == {SERVICE}

    def test_a_database_that_cannot_answer_keeps_the_row(self, db):
        """Fails OPEN. The only thing this gate does is hide the row, and hiding it takes the
        operator's Default server page away -- so a hiccup must not."""
        db.is_multisite.side_effect = RuntimeError("boom")

        rows = {row["id"] for row in ROUTER.list_services().content["services"]}

        assert rows == {SERVICE, DEFAULT_SERVER_ID}

    def test_an_operators_own_service_of_that_name_is_never_hidden(self, db):
        """It is a real service. Hiding it would take the operator's own site out of their API."""
        db.is_multisite.return_value = False
        db.get_services.return_value = [
            {"id": SERVICE, "method": "ui", "is_draft": False},
            {"id": DEFAULT_SERVER_ID, "method": "ui", "is_draft": False},
        ]

        rows = {row["id"]: row for row in ROUTER.list_services().content["services"]}

        assert set(rows) == {SERVICE, DEFAULT_SERVER_ID}
        assert rows[DEFAULT_SERVER_ID]["reserved"] is False


class TestAForeignRowKeepsItsRecovery:
    """Finding A of the independent Criticos pass. A service an operator created under the reserved
    name -- before 1.7 reserved it, or through autoconf, where ids come from container and ingress
    names -- gets no `server{}` block any more: `http.conf` drops the id from `map_servers` by NAME,
    whatever the method. The seeding refuses to adopt it and says so; these are the two operations
    that let the operator act on that message without editing the database by hand."""

    @pytest.fixture
    def foreign(self, db):
        db.get_services.return_value = [
            {"id": SERVICE, "method": "ui", "is_draft": False},
            {"id": DEFAULT_SERVER_ID, "method": "ui", "is_draft": False},
        ]
        return db

    def test_renaming_it_away_is_allowed(self, foreign):
        response = ROUTER.update_service(DEFAULT_SERVER_ID, schemas.ServiceUpdateRequest(server_name="recovered.example.com"))

        assert response.status_code == 200
        saved = foreign.save_config.call_args[0][0]
        assert "recovered.example.com" in saved["SERVER_NAME"].split()
        assert DEFAULT_SERVER_ID not in saved["SERVER_NAME"].split()

    def test_deleting_it_is_allowed(self, foreign):
        """The ROUTER half only. `db` is a mock here (this package has no live client), so a 200 says
        the router did not refuse -- it cannot say the row went. That half is
        `tests/unit/db/test_default_server_multisite_gate.py::TestTheRecoveryReachesTheDatabase`,
        against a real database, and it is where a 200-that-deletes-nothing was actually caught: the
        id was excluded from `save_config`'s `missing_ids` by NAME, so this test was green on a build
        where the recovery did not work."""
        response = ROUTER.delete_service(DEFAULT_SERVER_ID)

        assert response.status_code == 200
        # It reaches the writer at all -- the refusal returns before either of these.
        assert foreign.save_config.called or foreign.delete_services.called

    def test_drafting_it_is_allowed(self, foreign):
        """Router half; the database half is `TestTheRecoveryReachesTheDatabase` (see above)."""
        assert ROUTER.update_service(DEFAULT_SERVER_ID, schemas.ServiceUpdateRequest(is_draft=True)).status_code == 200
        assert foreign.save_config.call_args[0][0][f"{DEFAULT_SERVER_ID}_IS_DRAFT"] == "yes"
        assert ROUTER.convert_service(DEFAULT_SERVER_ID, convert_to="draft").status_code == 200

    def test_taking_the_reserved_id_is_STILL_refused(self, foreign):
        """The asymmetry that makes the lift safe: the recovery is one-way. Nothing may move ONTO
        the id, whatever is sitting on it."""
        response = ROUTER.update_service(SERVICE, schemas.ServiceUpdateRequest(server_name=DEFAULT_SERVER_ID))

        assert response.status_code == 403
        _explains_why(response)

    def test_creating_it_is_STILL_refused(self, foreign):
        response = ROUTER.create_service(schemas.ServiceCreateRequest(server_name=DEFAULT_SERVER_ID, variables={}))

        assert response.status_code == 403
