"""What the global page is allowed to write down onto services.

``update_global_config`` propagates a changed global value to every service (and, with
``OVERRIDE_NON_GLOBAL_SERVICES``, to services holding their own override). That is only safe
while "the user posted this key" and "the global value changed" mean the same thing -- and they
stopped meaning the same thing when ``check_variables`` started *restoring* a rejected value to
the stored one instead of dropping it (``app/models/config.py``): the restored key stays in
``variables_to_check``, so a rejected edit looked exactly like a real change.

Why that is destructive rather than a wasteful no-op: the propagated value equals the global
one, so ``_check_value`` (``db_methods/config_save.py:144-164``) sees a service row that matches
its default and ``config_save.py:1097`` deletes it. A service that had explicitly pinned
``SSL_PROTOCOLS=TLSv1.3`` silently falls back to a global that still allows TLSv1.2 -- from a
save the UI told the user it had rejected.

These tests drive the real ``update_global_config`` around the real ``Config.check_variables``
and assert on the payload handed to ``edit_global_conf`` (which is what reaches
``Database.save_config``).
"""

import importlib.util
import sys
from copy import deepcopy
from pathlib import Path
from json import loads as json_loads
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from app.models.config import Config  # type: ignore  (src/ui on path via the ui conftest)

REPO_ROOT = Path(__file__).resolve().parents[3]
ROUTE_PATH = REPO_ROOT / "src" / "ui" / "app" / "routes" / "global_settings.py"


def _import_route_module(source: Path = ROUTE_PATH) -> ModuleType:
    """Load ``app/routes/global_settings.py`` against stubs, like test_plugin_settings_page.py.

    ``app.dependencies`` builds real singletons at module scope (``Config()`` reads
    ``/usr/share/bunkerweb/settings.json``, present only inside a built image) and
    ``app.routes.utils`` pulls ``qrcode.main`` (absent from the unit-test venv), so a bare import
    fails at collection time. ``source`` is a parameter so a mutation run can point it at a
    modified copy under the scratchpad without touching the repo file.
    """
    dependencies = ModuleType("app.dependencies")
    dependencies.API_CLIENT = Mock()
    dependencies.BW_CONFIG = Mock()
    dependencies.CONFIG_TASKS_EXECUTOR = Mock()
    dependencies.DATA = Mock()
    qrcode = ModuleType("qrcode")
    qrcode_main = ModuleType("qrcode.main")
    qrcode_main.QRCode = Mock()
    qrcode.main = qrcode_main
    module_name = "app.routes._global_settings_under_test"
    spec = importlib.util.spec_from_file_location(module_name, source)
    module = importlib.util.module_from_spec(spec)
    stubs = {"app.dependencies": dependencies, "qrcode": qrcode, "qrcode.main": qrcode_main, module_name: module}
    with patch.dict(sys.modules, stubs):
        spec.loader.exec_module(module)
    return module


_MODULE = _import_route_module()

# Verbatim shape of core/ssl's SSL_PROTOCOLS: a multiselect whose regex REJECTS the empty string
# an emptied multiselect posts -- the value that triggers the restore path in check_variables.
SETTINGS = {
    "SSL_PROTOCOLS": {
        "type": "multiselect",
        "regex": r"^(?! )( ?(?:SSLv[23]|TLSv1(?:\.[1-3])?))+$",
        "context": "multisite",
        "separator": " ",
        "multiselect": [{"id": v, "label": v, "value": v} for v in ("SSLv3", "TLSv1", "TLSv1.1", "TLSv1.2", "TLSv1.3")],
    },
    "SERVER_NAME": {"type": "text", "regex": "^.*$", "context": "multisite"},
}


class _FakeData(dict):
    def load_from_file(self):  # check_variables and the route both call this
        return None


def _stored_config() -> dict:
    """Two services, one inheriting the global value and one overriding it.

    ``svc2`` shares the global entry *object* on purpose: that is what ``get_config`` returns for
    a service with no row of its own (``db_methods/config_read.py:195-202`` does
    ``config.setdefault(f"{service}_{key}", value)`` with the global dict), which is why an
    inheriting service carries ``global: True`` while ``svc1``'s own row carries ``global: False``
    (``config_read.py:247``).
    """
    global_ssl = {"value": "TLSv1.2 TLSv1.3", "global": True, "method": "ui", "default": "TLSv1.2 TLSv1.3", "template": None}
    return {
        "SERVER_NAME": {"value": "svc1 svc2", "global": True, "method": "scheduler", "default": "", "template": None},
        "SSL_PROTOCOLS": global_ssl,
        "svc1_SSL_PROTOCOLS": {"value": "TLSv1.3", "global": False, "method": "ui", "default": "TLSv1.2 TLSv1.3", "template": None},
        "svc2_SSL_PROTOCOLS": global_ssl,
    }


def _run_update(posted: dict, *, override: bool):
    """Run the real ``update_global_config``; return (payload sent to save, flashed messages)."""
    module = _MODULE  # looked up at call time so a mutation run can swap it
    stored = _stored_config()
    data = _FakeData(TO_FLASH=[])
    captured = {}

    config = Config.__new__(Config)  # skip __init__ (hardcoded settings.json read)
    config._Config__data = data
    config._Config__ignore_regex_check = False
    config.get_plugins_settings = lambda: SETTINGS
    config.get_config = lambda **kwargs: deepcopy(stored)
    config.edit_global_conf = lambda variables, **kwargs: (captured.setdefault("payload", variables), ("Saved.", 0))[1]

    with patch.object(module, "BW_CONFIG", config), patch.object(module, "DATA", data), patch.object(module, "wait_applying", lambda: None):
        module.update_global_config(dict(posted), override, {}, scope=None)

    return captured.get("payload"), [entry["content"] for entry in data["TO_FLASH"]]


def test_rejected_global_edit_is_not_propagated_to_services():
    # An emptied multiselect: no client gate (the hidden input carries no pattern), rejected by
    # the regex, restored to the stored value by check_variables.
    payload, flashed = _run_update({"SSL_PROTOCOLS": ""}, override=True)

    assert payload is not None, "the save still runs -- the restored key keeps variables_to_check non-empty"
    assert payload["SSL_PROTOCOLS"] == "TLSv1.2 TLSv1.3", "the rejected edit must revert, not delete the global row"
    assert "Variable SSL_PROTOCOLS is not valid." in flashed, "the user must still be told the edit was rejected"
    assert "svc1_SSL_PROTOCOLS" not in payload, "a rejected edit must not overwrite a service's own override"
    assert "svc2_SSL_PROTOCOLS" not in payload, "a rejected edit must not write anything down to services"


def test_valid_global_change_still_propagates_with_the_override_flag():
    payload, flashed = _run_update({"SSL_PROTOCOLS": "TLSv1.2"}, override=True)

    assert flashed == ["Global settings successfully saved.", "The Scheduler will be in charge of applying the changes."]
    assert payload["SSL_PROTOCOLS"] == "TLSv1.2"
    assert payload["svc2_SSL_PROTOCOLS"] == "TLSv1.2", "a service following the global must follow the change"
    assert payload["svc1_SSL_PROTOCOLS"] == "TLSv1.2", "OVERRIDE_NON_GLOBAL_SERVICES must still override an own value"


def test_valid_global_change_leaves_own_overrides_alone_without_the_flag():
    payload, _ = _run_update({"SSL_PROTOCOLS": "TLSv1.2"}, override=False)

    assert payload["svc2_SSL_PROTOCOLS"] == "TLSv1.2"
    assert "svc1_SSL_PROTOCOLS" not in payload, "without the flag a service's own override is untouched"


def test_identical_repost_takes_the_no_change_short_circuit():
    """A save that changes nothing must say so -- and must not trigger a scheduler reload.

    Regression guard for the `global_config_entries` rewrite. `config` here is NOT `global_only`,
    and an INHERITING service key shares its global's dict object (see `_stored_config`), so
    `svc2_SSL_PROTOCOLS` carries `global: True`. Keeping such keys in `global_config_entries` put a
    key no global form ever posts into the "was something removed?" loop: `restore_unowned_settings`
    only restores keys whose method is NOT ui/api/wizard (`save_scope.py`), so for any global an
    admin has ever set from the UI the inherited key was never in `variables`, `no_removed_settings`
    went False unconditionally, and this short-circuit could never fire -- every no-op save reported
    a false success and set CONFIG_CHANGED.

    `SERVER_NAME` is deliberately method `scheduler` in the fixture: it IS restored, so it cannot be
    what keeps the loop happy, and the assertion below turns on the service-prefixed keys alone.
    """
    payload, flashed = _run_update({"SSL_PROTOCOLS": "TLSv1.2 TLSv1.3"}, override=True)

    assert payload is None, "nothing changed, so nothing should have been sent to save"
    assert flashed == ["The global settings were not edited because no values were changed."]


# ------------------------------------------------------- the global page's own save scope
# The global page posted every key and declared no scope, which was safe only while one form
# owned the whole configuration. The compose shelf owns activation keys and nothing else, so it
# has to declare them -- and the two pages' control-key lists differ, so nothing here may be
# copied from the service page.


def _post_global_page(monkeypatch, *, query="", form=None, permissions=("read", "write")):
    """POST the real route and return the (args, kwargs) handed to the executor."""
    from flask import Flask

    api = Mock()
    api.readonly = False
    api.get_global_settings.return_value = {"SSL_PROTOCOLS": {"value": "TLSv1.2", "method": "ui", "global": True}}
    api.get_metadata.return_value = {"is_pro": False}
    bw_config = Mock()
    bw_config.get_plugins.return_value = _REAL_PLUGINS
    executor = Mock()
    monkeypatch.setattr(_MODULE, "API_CLIENT", api)
    monkeypatch.setattr(_MODULE, "BW_CONFIG", bw_config)
    monkeypatch.setattr(_MODULE, "CONFIG_TASKS_EXECUTOR", executor)
    monkeypatch.setattr(_MODULE, "DATA", _FakeData(TO_FLASH=[]))

    app = Flask(__name__)
    app.secret_key = "test"
    app.register_blueprint(_MODULE.global_settings)
    app.add_url_rule("/loading", "loading", lambda: "")
    data = {"csrf_token": "x"} | (form or {})
    with app.test_request_context(f"/global-settings{query}", method="POST", data=data), patch(
        "app.utils.current_user", SimpleNamespace(list_permissions=list(permissions))
    ):
        _MODULE.global_settings_page.__wrapped__()
    assert executor.submit.called, "the route returned before submitting -- this test proves nothing"
    return executor.submit.call_args


def _real_plugins():
    plugins = {}
    for manifest_path in sorted((REPO_ROOT / "src" / "common" / "core").glob("*/plugin.json")):
        manifest = json_loads(manifest_path.read_text(encoding="utf-8"))
        plugins[manifest.get("id") or manifest_path.parent.name] = manifest | {"type": "core"}
    return plugins


_REAL_PLUGINS = _real_plugins()


def test_the_global_compose_shelf_declares_a_scope(monkeypatch):
    call = _post_global_page(monkeypatch, query="?mode=compose")
    scope = call.kwargs["scope"]

    assert scope is not None
    assert "USE_BACKUP" in scope, "a `global` context activation key belongs to the GLOBAL shelf"
    assert "USE_ANTIBOT" in scope
    assert "BLACKLIST_COUNTRY" not in scope and "REDIRECT_TO" not in scope, "multiselect/multiple rows post nothing"


@pytest.mark.parametrize("query", ["", "?mode=advanced", "?mode=wat"])
def test_the_global_advanced_pane_still_claims_everything(monkeypatch, query):
    """This page's default pane is `advanced` (global_settings.py:192) and it posts every rendered
    key, so `scope=None` is correct for it -- and an unrecognised mode renders that same pane, so
    it must save the same way. A declared scope here would let a pane that posts multi-value rows
    have a DELETED clone restored behind the user's back."""
    assert _post_global_page(monkeypatch, query=query).kwargs["scope"] is None


def test_the_global_raw_pane_still_claims_everything(monkeypatch):
    assert _post_global_page(monkeypatch, query="?mode=raw").kwargs["scope"] is None


def test_a_readonly_global_user_gets_an_empty_scope(monkeypatch):
    """At global scope this is the sharp one: "in scope but not posted" means DELETE, so a
    read-only POST with a claimed scope wipes a plugin's whole global configuration."""
    assert _post_global_page(monkeypatch, query="?mode=compose", permissions=("read",)).kwargs["scope"] == set()


def test_the_global_restore_skip_does_not_pick_up_the_service_control_keys():
    """The two pages' skip sets differ and copying one onto the other loses a global.

    `USE_UI` is in the SERVICE page's `restore_skip` (it flows through that page's own control
    inputs) and is NOT in `get_blacklisted_settings(True)`. Emitting the service list here would
    put it in the global skip set, where nothing posts it back -- so a global `USE_UI` the form
    did not carry stops being restored and its row is deleted.
    """
    config = {
        "SERVER_NAME": {"value": "svc1", "method": "scheduler", "global": True},
        "USE_UI": {"value": "yes", "method": "scheduler", "global": True},
        "SSL_PROTOCOLS": {"value": "TLSv1.2", "method": "ui", "global": True},
    }
    bw_config = Mock()
    bw_config.get_config.return_value = config
    bw_config.check_variables.side_effect = lambda variables, *args, **kwargs: variables
    bw_config.edit_global_conf.return_value = ("saved", None)
    with patch.object(_MODULE, "BW_CONFIG", bw_config), patch.object(_MODULE, "DATA", _FakeData(TO_FLASH=[])), patch.object(
        _MODULE, "wait_applying", lambda: None
    ):
        _MODULE.update_global_config({"SSL_PROTOCOLS": "TLSv1.3"}, False, {}, scope={"SSL_PROTOCOLS"})

    payload = bw_config.edit_global_conf.call_args[0][0]
    assert payload["USE_UI"] == "yes", "a global outside the scope must be preserved, not skipped"
