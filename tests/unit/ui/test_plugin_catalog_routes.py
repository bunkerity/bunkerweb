"""`/plugins/catalog/install` — the gates that only exist in the route.

``test_plugin_catalog.py`` covers the pure functions. What lives here is everything the route
adds on top of them, and each one exists because of a specific finding:

* the three refusals that must happen **before** any lookup or network call (kill switch,
  read-only, non-admin), so a POST that never rendered the page has no side effect;
* the freshness gate evaluated **at install time**, not at render time — a page left open
  overnight must not carry a stale install token;
* ``get_metadata()`` failing **closed** — an unreachable API is not permission to skip a
  version check;
* the ``created == [id]`` assertion, which is the only thing that notices the installer
  silently skipping the write (``_uep_sync_plugin_row`` returns ``(True, False)``, the router
  still appends the id, and ``update_external_plugins`` still returns ``""`` — so the operator
  would be told an install succeeded when nothing happened);
* and the **ordering**: nothing is uploaded when the archive digest does not match what was
  recorded at listing time, and what IS uploaded is a tarball holding exactly the one plugin
  that was asked for — never the release archive, which holds nine and which both install
  branches would loop over.

The route module is loaded with ``app.dependencies`` stubbed, following the pattern in
``test_onboarding_routes.py`` — it reads container-only paths at import time.
"""

import importlib.util
import sys
from datetime import datetime, timedelta
from io import BytesIO
from json import dumps
from pathlib import Path
from tarfile import TarInfo, open as tar_open
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from flask import Flask, get_flashed_messages
from flask_login import LoginManager

from app.models.plugin_catalog import CATALOG_MAX_AGE  # type: ignore

ROUTE_PATH = Path(__file__).resolve().parents[3] / "src" / "ui" / "app" / "routes" / "plugins.py"

TAG = "v1.11"
ROOT = "bunkerity-bunkerweb-plugins-fb55b84"


def _tar(*plugins, root=ROOT):
    """A release source archive: one generated wrapper directory, then one folder per plugin."""
    buf = BytesIO()
    with tar_open(fileobj=buf, mode="w:gz") as tar:
        for folder, declared in plugins:
            body = dumps({"id": declared, "name": declared, "version": "1.11"}).encode()
            info = TarInfo(f"{root}/{folder}/plugin.json")
            info.size = len(body)
            tar.addfile(info, BytesIO(body))
    return buf.getvalue()


def _sha(blob):
    return __import__("hashlib").sha256(blob).hexdigest()


# The real thing holds nine plugins; two is enough to prove only one is uploaded.
ARCHIVE = _tar(("clamav", "clamav"), ("coraza", "coraza"))
DIGEST = _sha(ARCHIVE)


def _entry(**over):
    item = {"id": "clamav", "name": "ClamAV", "description": "", "version": "1.11", "supported": ["1.7.0"], "homepage": None}
    item.update(over)
    return item


def _cache(items=None, tag=TAG, sha=DIGEST, fetched_at=None):
    return {
        "fetched_at": fetched_at or datetime.now().astimezone().isoformat(),
        "catalog": {
            "plugins": {"tag": tag, "sha256": sha, "items": [_entry()] if items is None else items},
            "templates": {"tag": "0.6", "sha256": "b" * 64, "items": []},
        },
    }


@pytest.fixture(scope="module")
def route_module():
    client, config, data = Mock(), Mock(), {}
    dependencies = ModuleType("app.dependencies")
    dependencies.API_CLIENT = client
    dependencies.DATA = data
    dependencies.BW_CONFIG = config
    dependencies.BW_INSTANCES_UTILS = Mock()
    dependencies.LOGGER = Mock()
    dependencies.CONFIG_TASKS_EXECUTOR = SimpleNamespace(submit=lambda fn, *a, **k: fn(*a, **k))
    dependencies.CORE_PLUGINS_PATH = Path("/tmp/_core")
    dependencies.EXTERNAL_PLUGINS_PATH = Path("/tmp/_ext")
    dependencies.PRO_PLUGINS_PATH = Path("/tmp/_pro")

    qrcode = ModuleType("qrcode")
    qrcode_main = ModuleType("qrcode.main")
    qrcode_main.QRCode = Mock()
    qrcode.main = qrcode_main

    module_name = "app.routes._plugins_catalog_test"
    spec = importlib.util.spec_from_file_location(module_name, ROUTE_PATH)
    module = importlib.util.module_from_spec(spec)
    stubs = {"app.dependencies": dependencies, "qrcode": qrcode, "qrcode.main": qrcode_main, module_name: module}
    with patch.dict(sys.modules, stubs):
        spec.loader.exec_module(module)
        yield module, client, config, data


@pytest.fixture
def ctx(route_module, monkeypatch):
    module, client, config, data = route_module
    client.reset_mock(return_value=True, side_effect=True)
    config.reset_mock(return_value=True, side_effect=True)
    data.clear()

    monkeypatch.setenv("USE_PLUGIN_CATALOG", "yes")
    data["TO_FLASH"] = []
    data["PLUGIN_CATALOG"] = _cache()
    # `DATA` here is a plain dict; the product's UIData persists on write. The route only uses
    # dict semantics plus `load_from_file`, so a no-op stub is faithful enough.
    data_obj = data

    class _Data(dict):
        def load_from_file(self):
            pass

    holder = _Data(data_obj)
    holder.load_from_file = lambda: None
    monkeypatch.setattr(module, "DATA", holder)

    client.readonly = False
    client.get_metadata.return_value = {"version": "1.7.0"}
    client.upload_plugins.return_value = {"created": ["clamav"]}
    config.get_plugins.return_value = {"blacklist": {}, "antibot": {}}

    app = Flask(__name__)
    app.secret_key = "test"
    app.config["WTF_CSRF_ENABLED"] = False
    # @login_required needs a manager on the app even though every call below drives the view
    # function directly.
    manager = LoginManager()
    manager.init_app(app)
    manager.user_loader(lambda user_id: None)
    app.register_blueprint(module.plugins)
    app.add_url_rule("/loading", endpoint="loading", view_func=lambda: "loading")

    uploads = []
    client.upload_plugins.side_effect = lambda files, method="ui": uploads.append((files, method)) or {"created": ["clamav"]}

    monkeypatch.setattr(module, "wait_applying", lambda *a, **k: None)
    monkeypatch.setattr(module, "fetch_archive", lambda repo, tag: ARCHIVE)

    admin = SimpleNamespace(admin=True, is_authenticated=True, is_active=True, is_anonymous=False, get_id=lambda: "1", list_permissions=["write"])
    monkeypatch.setattr(module, "current_user", admin)

    with app.test_request_context():
        pass
    return SimpleNamespace(app=app, module=module, client=client, config=config, data=holder, uploads=uploads, user=admin, session_flashes=[])


def _post(ctx, **form):
    """Drive the view body past @login_required.

    Same idiom as ``test_dashboard_comfort.py``: ``login_required`` is applied at import time, so
    patching it afterwards does nothing — the view's ``__wrapped__`` is called directly inside a
    request context instead. The guard itself is pinned separately by
    ``test_the_route_is_login_protected``.
    """
    payload = {"csrf_token": "x", "id": "clamav"}
    payload.update(form)
    view = ctx.module.install_catalog_plugin
    with ctx.app.test_request_context("/plugins/catalog/install", method="POST", data=payload):
        response = view.__wrapped__()
        # The route reports on TWO channels and both matter. A refusal that happens before the
        # executor is submitted goes through `handle_error` -> Flask's `flash`; anything the
        # background install decides lands in `DATA["TO_FLASH"]`, because by then the request is
        # long gone. Reading only one of them would let half the failure paths look silent.
        ctx.session_flashes = list(get_flashed_messages())
        return response


def _flashes(ctx):
    async_side = [entry.get("content", "") for entry in ctx.data.get("TO_FLASH", [])]
    return " | ".join(list(getattr(ctx, "session_flashes", [])) + async_side)


# ── The three refusals that happen before anything else ─────────────────────


def test_the_kill_switch_refuses_before_any_lookup(ctx, monkeypatch):
    monkeypatch.setenv("USE_PLUGIN_CATALOG", "no")
    _post(ctx)
    assert ctx.uploads == []
    ctx.client.get_metadata.assert_not_called()


def test_a_read_only_database_refuses(ctx):
    ctx.client.readonly = True
    _post(ctx)
    assert ctx.uploads == []


def test_a_non_admin_refuses(ctx, monkeypatch):
    monkeypatch.setattr(ctx.module, "current_user", SimpleNamespace(admin=False, is_authenticated=True, list_permissions=["write"]))
    _post(ctx)
    assert ctx.uploads == []


def test_an_unknown_id_installs_nothing(ctx):
    _post(ctx, id="does-not-exist")
    assert ctx.uploads == []


# ── C5: freshness is checked at INSTALL time ────────────────────────────────


def test_a_stale_cache_refuses_the_install(ctx):
    ctx.data["PLUGIN_CATALOG"] = _cache(fetched_at=(datetime.now().astimezone() - CATALOG_MAX_AGE - timedelta(minutes=1)).isoformat())
    _post(ctx)
    assert ctx.uploads == []


def test_a_cache_with_no_pinned_tag_refuses_the_install(ctx):
    # A scrubbed tag (read_cached refuses anything RELEASE_TAG_RX rejects) leaves nothing to pin
    # the re-fetch to, and "fall back to latest" is exactly the drift the pin exists to stop.
    ctx.data["PLUGIN_CATALOG"] = _cache(tag="")
    _post(ctx)
    assert ctx.uploads == []
    assert "incomplete" in _flashes(ctx)


def test_a_cache_with_no_recorded_digest_refuses_the_install(ctx):
    ctx.data["PLUGIN_CATALOG"] = _cache(sha="")
    _post(ctx)
    assert ctx.uploads == []
    assert "incomplete" in _flashes(ctx)


def test_the_re_fetch_is_pinned_to_the_listed_tag_not_to_latest(ctx, monkeypatch):
    seen = []
    monkeypatch.setattr(ctx.module, "fetch_archive", lambda repo, tag: seen.append((repo, tag)) or ARCHIVE)
    _post(ctx)
    assert seen == [("bunkerity/bunkerweb-plugins", TAG)]


# ── C6: the version source fails CLOSED ─────────────────────────────────────


def test_metadata_failure_refuses_rather_than_assuming_unknown(ctx):
    """An unreachable API refuses, and says WHY it refused.

    The message assertion is not decoration. Falling back to ``bw_version = "unknown"`` instead
    of refusing also ends in a refusal, because ``is_compatible`` fails closed on an unparseable
    version — the fail-closed is enforced twice over, which is a good property and a bad test
    condition. Only the message distinguishes "we could not ask" from "we asked and you are too
    old", and those are different things to put in front of an operator.
    """
    from app.api_client import ApiUnavailableError  # type: ignore

    ctx.client.get_metadata.side_effect = ApiUnavailableError("api down")
    _post(ctx)
    assert ctx.uploads == []
    assert "determine the BunkerWeb version" in _flashes(ctx)


def test_an_incompatible_version_refuses(ctx):
    ctx.client.get_metadata.return_value = {"version": "1.6.11"}
    _post(ctx)
    assert ctx.uploads == []


def test_an_item_declaring_no_compatibility_refuses(ctx):
    # The state every real plugin is in today: the plugins repository has shipped v1.9/v1.10/v1.11
    # without a COMPATIBILITY.json line, so `supported` is empty and the gate fails closed.
    ctx.data["PLUGIN_CATALOG"] = _cache(items=[_entry(supported=[])])
    _post(ctx)
    assert ctx.uploads == []
    assert "declares support for no BunkerWeb version" in _flashes(ctx)


def test_a_compatible_version_installs(ctx):
    _post(ctx)
    assert len(ctx.uploads) == 1
    assert "installed successfully" in _flashes(ctx)


# ── The collision gate sees every plugin type ───────────────────────────────


def test_an_id_colliding_with_a_core_plugin_refuses(ctx):
    ctx.config.get_plugins.return_value = {"clamav": {"type": "core"}}
    _post(ctx)
    assert ctx.uploads == []
    assert "already installed" in _flashes(ctx)


# ── C1/C2: ordering. Nothing is uploaded when the bytes are wrong ───────────


def test_a_re_cut_tag_uploads_nothing(ctx, monkeypatch):
    """The gate that replaces the manifest's published hash.

    A git tag can be force-moved, and codeload then serves different bytes for the same URL. The
    digest recorded when the catalogue was listed is what makes "listed" and "installed" the same
    bytes, and nothing is uploaded when they differ.
    """
    monkeypatch.setattr(ctx.module, "fetch_archive", lambda repo, tag: _tar(("clamav", "clamav"), ("evil", "evil")))
    _post(ctx)
    assert ctx.uploads == []
    assert "no longer matches" in _flashes(ctx)


def test_a_folder_missing_from_the_archive_uploads_nothing(ctx, monkeypatch):
    other = _tar(("coraza", "coraza"))
    ctx.data["PLUGIN_CATALOG"] = _cache(sha=_sha(other))
    monkeypatch.setattr(ctx.module, "fetch_archive", lambda repo, tag: other)
    _post(ctx)
    assert ctx.uploads == []
    assert "no folder named clamav" in _flashes(ctx)


def test_only_the_requested_plugin_is_uploaded_never_the_whole_archive(ctx):
    """The structural half of the identity guarantee.

    Both install branches in this router loop over every plugin.json they find, so handing over
    the release archive would install all nine on one click, none of them the one clicked. What
    goes up is a tarball built here holding exactly one folder.
    """
    _post(ctx)
    assert len(ctx.uploads) == 1
    _, (_, handle, _) = ctx.uploads[0][0][0]
    with tar_open(fileobj=BytesIO(handle.read())) as tar:
        names = tar.getnames()
    assert names and all(n == "clamav" or n.startswith("clamav/") for n in names)
    assert not any("coraza" in n for n in names)


def test_a_download_failure_uploads_nothing(ctx, monkeypatch):
    def _boom(repo, tag):
        raise ValueError("URL is not allowlisted")

    monkeypatch.setattr(ctx.module, "fetch_archive", _boom)
    _post(ctx)
    assert ctx.uploads == []
    assert "Refused to download" in _flashes(ctx)


# ── C4: the API response is checked, not trusted ────────────────────────────


def test_an_empty_created_list_is_a_failure_not_a_success(ctx):
    ctx.client.upload_plugins.side_effect = lambda files, method="ui": ctx.uploads.append((files, method)) or {"created": []}
    _post(ctx)
    flashes = _flashes(ctx)
    assert "did not complete" in flashes
    assert "installed successfully" not in flashes


def test_a_different_id_in_created_is_a_failure(ctx):
    # This is the shape a silent skip produces when something else was installed instead.
    ctx.client.upload_plugins.side_effect = lambda files, method="ui": ctx.uploads.append((files, method)) or {"created": ["something-else"]}
    _post(ctx)
    assert "did not complete" in _flashes(ctx)


def test_an_extra_id_in_created_is_a_failure(ctx):
    # Membership would pass this; equality is what catches "it installed more than we asked".
    ctx.client.upload_plugins.side_effect = lambda files, method="ui": ctx.uploads.append((files, method)) or {"created": ["clamav", "extra"]}
    _post(ctx)
    flashes = _flashes(ctx)
    assert "did not complete" in flashes
    assert "installed successfully" not in flashes


def test_errors_in_the_response_are_a_failure_even_alongside_a_created_id(ctx):
    ctx.client.upload_plugins.side_effect = lambda files, method="ui": ctx.uploads.append((files, method)) or {
        "created": ["clamav"],
        "errors": [{"file": "clamav.tar.gz", "error": "boom"}],
    }
    _post(ctx)
    assert "did not complete" in _flashes(ctx)


def test_the_upload_carries_the_catalogue_id_as_the_filename(ctx):
    _post(ctx)
    files, method = ctx.uploads[0]
    assert method == "ui"
    field, (filename, handle, content_type) = files[0]
    assert field == "files" and filename == "clamav.tar.gz" and content_type == "application/gzip"
    # NOT the archive that was downloaded: what goes up is the repacked single-plugin tarball.
    assert handle.read() != ARCHIVE


def test_the_route_is_login_protected(ctx):
    """The decorator itself, since every other test in this file drives the body past it."""
    assert getattr(ctx.module.install_catalog_plugin, "__wrapped__", None) is not None
    with ctx.app.test_client() as http:
        assert http.post("/plugins/catalog/install", data={"id": "clamav"}).status_code in (302, 401)
    assert ctx.uploads == []
