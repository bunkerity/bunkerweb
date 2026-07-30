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
from types import ModuleType
from unittest.mock import Mock, patch

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
