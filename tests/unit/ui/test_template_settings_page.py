"""The per-service template page: what it renders, what it may post, and what a save keeps.

Three artefacts share this file because they share one contract, and each of them can destroy
data on its own:

* `postable_template_scope` (`app/routes/services.py`) declares the keys the stepper's form can
  actually submit. An in-scope key the form does not post is DELETED
  (`db_methods/config_save.py:592`), so an over-claim is silent destruction, not a harmless
  approximation.
* `template_settings_page.html` + `models/template_steps_body.html` are what makes that
  declaration true: the control keys it must post because `restore_unowned_settings` refuses to
  restore them, the `data-plugin-settings-form` marker without which an unchecked switch posts
  nothing at all, and `novalidate` without which Save silently does nothing.
* `js/components/settings-widgets.js` + `js/pages/template-settings-page.js` carry the two
  invariants that rot invisibly: the ace mirror sync (lose it and every custom-config edit
  vanishes with no error) and the capture-phase submit gate (bind it on the form instead and it
  still looks correct, still blocks, and reintroduces a stale-config write on the next save).

There is no JS test harness in this repo (Prettier only, no Jest -- see src/ui/CLAUDE.md), so the
JS is covered by `node --check` plus assertions on its source text.
"""

import importlib.util
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlsplit

import pytest
from flask import Flask
from jinja2 import ChoiceLoader, DictLoader, Environment, FileSystemLoader

from app.utils import get_blacklisted_settings, get_filtered_settings, get_multiples, is_editable_method

REPO_ROOT = Path(__file__).resolve().parents[3]
TEMPLATES = REPO_ROOT / "src" / "ui" / "app" / "templates"
STATIC = REPO_ROOT / "src" / "ui" / "app" / "static"
MANIFESTS = REPO_ROOT / "src" / "common" / "core" / "templates" / "templates"

WIDGETS_JS = STATIC / "js" / "components" / "settings-widgets.js"
PAGE_JS = STATIC / "js" / "pages" / "template-settings-page.js"


def _import_services_module():
    """``app.routes.services`` transitively imports ``app.dependencies``, which builds real
    singletons at module scope (``Config()`` reads ``/usr/share/bunkerweb/settings.json`` --
    only present inside a built image, never in a bare checkout) and, via
    ``app.routes.configs`` -> ``app.routes.utils``, ``qrcode.main.QRCode`` (absent from the
    pared-down unit-test venv). A bare ``from app.routes.services import ...`` fails at
    collection time regardless of whether the symbol exists, so load the file directly against
    stub modules for both -- the same pattern ``test_plugin_settings_page.py`` and
    ``test_ui_service_resources.py`` use for this same module, under a **unique** module name so
    the three loads never share a Blueprint object.
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
    module_name = "app.routes._services_test_template_scope"
    route_path = REPO_ROOT / "src" / "ui" / "app" / "routes" / "services.py"
    spec = importlib.util.spec_from_file_location(module_name, route_path)
    module = importlib.util.module_from_spec(spec)
    stubs = {
        "app.dependencies": dependencies,
        "qrcode": qrcode,
        "qrcode.main": qrcode_main,
        module_name: module,
    }
    with patch.dict(sys.modules, stubs):
        spec.loader.exec_module(module)
    return module


_services_module = _import_services_module()
postable_template_scope = _services_module.postable_template_scope


# --------------------------------------------------------------------------------------
# Fixtures come from the real shipped manifests, reshaped into the payload
# `API_CLIENT.get_templates()` actually returns -- the two are NOT the same document, and a
# fixture built from the raw manifest tests a shape production never produces:
#   * the manifest's `configs` is a list of paths; the payload's is {path: data};
#   * `modsec-crs/api.conf` is stored through CUSTOM_CONFIGS_TYPES_ENUM (model.py:18-28), which
#     has no hyphenated member, so db_methods/templates.py:100 hands the page `modsec_crs/...`;
#   * `plugin_id` is set from the owning plugin (db_methods/plugins_update.py:670), so the
#     shipped templates belong to the `templates` core plugin -- not to the `ui` fallback;
#   * `dom_id` is injected by the route (services.py:inject_template_dom_ids), not by the API.
# In the previous slice two IS_DRAFT bugs and a USE_UI bug survived review purely because the
# fixture did not declare the setting that breaks.
# --------------------------------------------------------------------------------------


def _template_payload(template_id: str, *, plugin_id: str = "templates") -> dict:
    raw = json.loads((MANIFESTS / f"{template_id}.json").read_text())

    def _payload_config_key(path: str) -> str:
        conf_type, _, name = path.partition("/")
        return f"{conf_type.replace('-', '_')}/{name}"

    configs = {}
    for path in raw.get("configs") or []:
        conf_type, _, name = path.partition("/")
        configs[_payload_config_key(path)] = (MANIFESTS / template_id / "configs" / conf_type / name).read_text()

    steps = []
    for step in raw["steps"]:
        entry = {"title": step["title"], "subtitle": step.get("subtitle", "")}
        if step.get("settings"):
            entry["settings"] = list(step["settings"])
        if step.get("configs"):
            entry["configs"] = [_payload_config_key(path) for path in step["configs"]]
        steps.append(entry)

    # No `dom_id` on purpose: the API payload carries none and the ROUTE injects it
    # (services.py:inject_template_dom_ids). Pre-supplying it here would make the GET test unable
    # to tell whether the route ran that helper at all.
    return {
        "plugin_id": plugin_id,
        "name": raw["name"],
        "method": "manual",
        "settings": dict(raw.get("settings") or {}),
        "configs": configs,
        "steps": steps,
    }


def _rendered_payload(template_id: str, **kwargs) -> dict:
    """What the page receives: the API payload after the route's `dom_id` injection. Uses the real
    helper rather than hardcoding the result, so the render fixtures and the route agree by
    construction."""
    return _services_module.inject_template_dom_ids({template_id: _template_payload(template_id, **kwargs)})[template_id]


LOW = _rendered_payload("low")
API_TPL = _rendered_payload("api")


def _step_named(template_data: dict) -> set:
    return {setting for step in template_data["steps"] for setting in step.get("settings", [])}


LOW_STEP_NAMED = _step_named(LOW)
BLACKLISTED = get_blacklisted_settings()


def _all_plugin_settings() -> dict:
    """`get_plugins_settings()` (app/models/config.py:81) = every plugin's settings merged, with
    settings.json last. Rebuilt here from the same files rather than hand-stubbed."""
    settings = {}
    for manifest in sorted((REPO_ROOT / "src" / "common" / "core").glob("*/plugin.json")):
        settings.update(json.loads(manifest.read_text()).get("settings") or {})
    settings.update(json.loads((REPO_ROOT / "src" / "common" / "settings.json").read_text()))
    return settings


PLUGINS_SETTINGS = _all_plugin_settings()

# base.html sets this at module scope; the stubbed dashboard.html below does not extend it and
# the partial's card header reads it unconditionally.
PLUGIN_TYPES = {
    "core": {"icon": "", "title-class": " border-dark"},
    "external": {"icon": "", "title-class": " border-secondary", "text-class": " text-secondary fw-bold"},
    "ui": {"icon": "", "title-class": " border-secondary", "text-class": " text-secondary"},
    "pro": {"title-class": " border-primary", "text-class": " text-primary fw-bold shine"},
}
PLUGINS = {"templates": {"id": "templates", "type": "core", "name": "Templates"}}

CONTROL_KEYS = ("SERVER_NAME", "OLD_SERVER_NAME", "IS_DRAFT", "USE_TEMPLATE", "USE_UI")


def _db(**pairs):
    """db_config shorthand: KEY=(value, method[, global_[, template]])."""
    out = {}
    for key, args in pairs.items():
        value, method = args[0], args[1]
        entry = {"value": value, "method": method, "global": args[2] if len(args) > 2 else False}
        if len(args) > 3:
            entry["template"] = args[3]
        out[key] = entry
    return out


# ======================================================================================
# postable_template_scope -- one test per rule of the contract in its own docstring
# (app/routes/services.py:498-531). Each must fail if that one rule regresses.
# ======================================================================================


def test_postable_template_scope_is_readonly_short_circuits_to_empty():
    """Rule 1: `{% if is_readonly %}{% set disabled = true %}` disables every field the stepper
    renders (models/template_steps_body.html:131-134), so the form posts nothing and nothing may
    be claimed -- otherwise every ui-method row the template names is deleted on save. `low`
    yields 85 keys with the same arguments and is_readonly=False (see the next test), so this
    cannot pass vacuously."""
    assert postable_template_scope(LOW, {}, blacklisted=BLACKLISTED, is_readonly=True) == set()


def test_postable_template_scope_non_editable_template_is_empty():
    """Rule 2: a service locked to another template renders the "template in use" notice
    *instead of* the stepper (models/template_steps_body.html:272-283) -- zero fields, zero
    posted keys."""
    assert postable_template_scope(LOW, {}, blacklisted=BLACKLISTED, template_editable=False) == set()


def test_postable_template_scope_claims_the_step_named_keys_when_editable():
    """The non-vacuity premise of the two tests above, and rule 3: candidates are the union of
    the steps' `settings` lists, nothing else."""
    scope = postable_template_scope(LOW, {}, blacklisted=BLACKLISTED)
    assert scope == LOW_STEP_NAMED - BLACKLISTED
    assert "SERVER_NAME" in scope


def test_postable_template_scope_excludes_blacklisted_keys():
    """Rule 4: a blacklisted key is rendered by nobody at all, so it can never post whatever its
    method. SERVER_NAME is used as the probe because it is the one control key a shipped
    manifest's first step really does name -- no shipped template names a permanently
    blacklisted setting, so the rule is otherwise unobservable on real data."""
    scope = postable_template_scope(LOW, {}, blacklisted=BLACKLISTED | {"SERVER_NAME"})
    assert "SERVER_NAME" not in scope
    assert "SECURITY_MODE" in scope


def test_postable_template_scope_excludes_a_disabled_scheduler_managed_key():
    """Rule 7: mirrors models/template_steps_body.html:123 -- a scheduler-managed setting whose
    stored entry has global=False renders disabled, so the page cannot post it."""
    db_config = _db(SECURITY_MODE=("block", "scheduler", False))
    assert "SECURITY_MODE" not in postable_template_scope(LOW, db_config, blacklisted=BLACKLISTED)


def test_postable_template_scope_includes_a_global_override_despite_a_non_editable_method():
    """Rule 7, the other half of the same expression: `global` is the `or` that keeps a
    scheduler-managed row editable on a service page. Dropping it silently makes every
    global-overridden setting unwritable from this page."""
    db_config = _db(USE_REVERSE_PROXY=("yes", "scheduler", True))
    assert "USE_REVERSE_PROXY" in postable_template_scope(LOW, db_config, blacklisted=BLACKLISTED)


def test_postable_template_scope_includes_a_step_named_key_with_no_stored_row():
    """Rule 8: a key that was never written has no method to be disabled by and cannot be
    deleted anyway -- "default" is editable under allow_default, same conservative-when-in-doubt
    contract as postable_scope."""
    scope = postable_template_scope(LOW, {}, blacklisted=BLACKLISTED)
    assert "ALLOWED_METHODS" in scope
    assert "ALLOWED_METHODS" not in _db()


def test_postable_template_scope_includes_a_step_named_key_absent_from_the_settings_map():
    """Rule 3's real-world evidence: `api.json` names USE_CLIENT_CACHE in its last step while the
    template declares no default for it, so it is absent from `template_data["settings"]` (it is
    the `clientcache` plugin's setting, not one of the master settings.json entries). Deriving
    candidates from the settings map -- the obvious alternative -- would drop a key the form does
    post, and the save would then delete its row."""
    assert "USE_CLIENT_CACHE" not in API_TPL["settings"]
    assert "USE_CLIENT_CACHE" in _step_named(API_TPL)
    assert "USE_CLIENT_CACHE" in postable_template_scope(API_TPL, {}, blacklisted=BLACKLISTED)


def test_postable_template_scope_ignores_a_settings_key_no_step_names():
    """Rule 3's other direction. **This fixture is synthetic and has to be**: in all five shipped
    manifests `set(settings) - set(step-named)` is empty, so the case cannot be built from real
    data. One key is added to a copy of the real `low` payload's settings map and to nothing
    else; everything around it stays real."""
    assert not set(LOW["settings"]) - LOW_STEP_NAMED, "a shipped manifest grew an unstepped setting -- this fixture can stop being synthetic"
    synthetic = LOW | {"settings": LOW["settings"] | {"X_FRAME_OPTIONS": "SAMEORIGIN"}}
    scope = postable_template_scope(synthetic, _db(X_FRAME_OPTIONS=("SAMEORIGIN", "ui")), blacklisted=BLACKLISTED)
    assert "X_FRAME_OPTIONS" not in scope


def test_postable_template_scope_excludes_a_stored_suffixed_row_no_step_names():
    """Rule 9, first half -- and the plan originally specified the opposite, which T4's review
    reproduced as a live deletion of five rows per save. The stepper is a flat
    `{% for setting in step["settings"] %}` with **no** multiples loop
    (models/template_steps_body.html:115), so a stored REVERSE_PROXY_HOST_1 is never rendered
    and never posted even though a step names the base. Claiming it would delete it."""
    db_config = _db(REVERSE_PROXY_HOST=("http://a", "ui"), REVERSE_PROXY_HOST_1=("http://b", "ui"))
    scope = postable_template_scope(LOW, db_config, blacklisted=BLACKLISTED)
    assert "REVERSE_PROXY_HOST" in scope
    assert "REVERSE_PROXY_HOST_1" not in scope


def test_postable_template_scope_includes_a_suffixed_key_a_step_names_literally():
    """Rule 9, the exception: `db_methods/templates.py:82` builds a step's setting list with the
    suffix already attached (`f"{setting_id}_{suffix}"`), so a template CAN name
    REVERSE_PROXY_URL_2 directly -- and then the stepper does render it and the form does post
    it. **Synthetic**: no shipped manifest declares a suffix today, so the suffixed name is
    grafted onto a copy of `low`'s real second step."""
    steps = [step | {"settings": step["settings"] + ["REVERSE_PROXY_URL_2"]} if step is LOW["steps"][1] else step for step in LOW["steps"]]
    synthetic = LOW | {"steps": steps}
    scope = postable_template_scope(synthetic, _db(REVERSE_PROXY_URL_2=("/app", "ui")), blacklisted=BLACKLISTED)
    assert "REVERSE_PROXY_URL_2" in scope
    # ...and it is judged on its OWN stored row, not the base's.
    disabled = postable_template_scope(synthetic, _db(REVERSE_PROXY_URL_2=("/app", "scheduler", False)), blacklisted=BLACKLISTED)
    assert "REVERSE_PROXY_URL_2" not in disabled


def test_postable_template_scope_never_claims_custom_conf_keys():
    """`update_service` deletes CUSTOM_CONF_* from `variables` (services.py:600) before
    `restore_unowned_settings` runs, and they have no db_config rows -- so a scope built from a
    step's `configs` list rather than its `settings` list would claim keys that can never be
    posted. `api` step 4 is the one that carries configs.

    Note on what this does and does not catch: a scope built from a step's `configs` list would
    yield `modsec/api.conf`-shaped keys, which do not start with `CUSTOM_CONF` -- that mutant dies
    in `test_postable_template_scope_claims_the_step_named_keys_when_editable`, not here. What
    this pins is the stronger, format-independent property: nothing outside the step-named key set
    gets in, whatever a future derivation does to the names."""
    scope = postable_template_scope(API_TPL, {}, blacklisted=BLACKLISTED)
    assert API_TPL["steps"][3]["configs"], "the api fixture lost its configs -- this test is now vacuous"
    assert not [key for key in scope if key.startswith("CUSTOM_CONF")]
    assert scope == _step_named(API_TPL) - BLACKLISTED


# ======================================================================================
# The scope set is only half of it: save_scope.py's `_in_scope` base-matches independently of
# what the scope set contains, so a suffixed row can be out of the returned set and still be
# deleted by the save. These drive the real `update_service` and assert on the payload that
# reaches `BW_CONFIG.edit_service`.
# ======================================================================================


class _FakeData(dict):
    def load_from_file(self):
        pass


def _run_template_save(monkeypatch, *, db_config, posted, scope, mode="template", api=None, configs=None):
    """Drive the real `update_service` and return the settings payload handed to `edit_service`.

    `api` is accepted so a caller that needs to assert on another API call (bulk_save_configs)
    keeps the reference; `configs` is what `get_configs` returns, i.e. the service's already
    stored custom configs.
    """
    module = _services_module
    api = api if api is not None else Mock()
    api.get_service.return_value = db_config
    api.get_configs.return_value = configs or []
    api.get_templates.return_value = {}
    bw_config = Mock()
    # The real check_variables validates and returns the payload; identity keeps this test about
    # the restore/re-injection layer rather than about validation.
    bw_config.check_variables.side_effect = lambda variables, *args, **kwargs: variables
    bw_config.edit_service.return_value = ("Configuration saved", None)
    monkeypatch.setattr(module, "API_CLIENT", api)
    monkeypatch.setattr(module, "BW_CONFIG", bw_config)
    monkeypatch.setattr(module, "DATA", _FakeData(TO_FLASH=[]))
    monkeypatch.setattr(module, "wait_applying", lambda: None)

    module.update_service("app.example.com", dict(posted), False, mode, "", {}, scope=scope)

    assert bw_config.edit_service.called, "update_service returned early -- nothing reached the save, so this test proves nothing"
    payload = bw_config.edit_service.call_args[0][1]

    # The restore layer's guard, asserted here rather than per test so every case below carries
    # it. X_FRAME_OPTIONS is stored, ui-method, and named by no shipped template's steps -- so
    # the stepper never renders it, the form never posts it, and NOTHING restores it except
    # `restore_unowned_settings`' scope branch (the method branch skips it precisely because
    # "ui" is editable). Drop the restore call, pass `scope=None`, or claim every stored key as
    # in-scope, and this row is absent from the payload -- which is config_save.py:592 deleting
    # it. Without this, no end-to-end save in this file observes that layer at all.
    assert "X_FRAME_OPTIONS" not in LOW_STEP_NAMED, "fixture premise: no step of `low` renders it, so the form cannot post it"
    assert db_config.get("X_FRAME_OPTIONS", {}).get("method") == "ui", "fixture premise: stored, and ui-method so the method-based restore skips it"
    assert payload.get("X_FRAME_OPTIONS") == "DENY", "an out-of-scope stored setting was dropped -> its row dies"
    return payload


_STORED = _db(
    SERVER_NAME=("app.example.com", "ui"),
    USE_TEMPLATE=("low", "ui"),
    MAX_CLIENT_SIZE=("10m", "ui"),
    REVERSE_PROXY_HOST=("http://a", "ui"),
    REVERSE_PROXY_HOST_1=("http://b", "ui"),
    REVERSE_PROXY_URL_1=("/legacy", "ui"),
    # Out of scope and stored -- the probe `_run_template_save` uses for the restore layer. No
    # shipped manifest step-names it (the helper asserts that against `low` on every call). Keep
    # it ui-method: a non-editable method would be carried by the method-based restore instead
    # and the guard would go vacuous.
    X_FRAME_OPTIONS=("DENY", "ui"),
)

# What the stepper's form really sends: every step-named key it rendered, and NO suffixed row.
_POSTED = {
    "SERVER_NAME": "app.example.com",
    "USE_TEMPLATE": "low",
    "USE_UI": "no",
    "MAX_CLIENT_SIZE": "20m",
    "REVERSE_PROXY_HOST": "http://a",
}


def test_suffixed_multiple_rows_survive_a_template_save(monkeypatch):
    """The measured pre-fix loss was five rows per save. Asserting only that the suffixed key is
    absent from the scope SET would pass while the row still died: `_in_scope`
    (app/models/save_scope.py:39-40) matches REVERSE_PROXY_HOST_1 against the base
    REVERSE_PROXY_HOST that IS in scope, so it is treated as owned, is not restored, and is
    deleted. `update_service`'s `mode == "template"` re-injection is what actually saves it."""
    scope = postable_template_scope(LOW, _STORED, blacklisted=BLACKLISTED)
    payload = _run_template_save(monkeypatch, db_config=_STORED, posted=_POSTED, scope=scope)

    assert payload["REVERSE_PROXY_HOST_1"] == "http://b"
    assert payload["REVERSE_PROXY_URL_1"] == "/legacy"
    # ...without freezing the base, which the user really did edit on this page.
    assert payload["MAX_CLIENT_SIZE"] == "20m"


def test_clearing_a_rendered_step_named_setting_still_goes_through(monkeypatch):
    """The re-injection must stay narrow: it restores only `_<digits>` keys, never a base.
    Restoring bases too would look safer and would make every "clear this field" a no-op.

    On its own this case is stopped by either clause of the guard, so it does not pin either one;
    the next two tests do, one clause each."""
    scope = postable_template_scope(LOW, _STORED, blacklisted=BLACKLISTED)
    payload = _run_template_save(monkeypatch, db_config=_STORED, posted=_POSTED | {"REVERSE_PROXY_HOST": ""}, scope=scope)

    assert payload["REVERSE_PROXY_HOST"] == ""


def test_an_edit_to_a_step_named_suffixed_key_is_not_reverted(monkeypatch):
    """Pins the guard's `setting in variables` clause. When a step names a suffixed key literally
    (`db_methods/templates.py:82` builds those) the stepper DOES render it and the form DOES post
    it -- so the re-injection, which exists to protect unrendered suffixed rows, must not walk over
    the value the user just typed. Without this clause the edit is silently reverted to the stored
    value: the save reports success and the change is gone.

    **Synthetic fixture** for the same reason as
    `test_postable_template_scope_includes_a_suffixed_key_a_step_names_literally`: no shipped
    manifest declares a suffix today, so the suffixed name is grafted onto a copy of `low`'s real
    second step."""
    steps = [step | {"settings": step["settings"] + ["REVERSE_PROXY_URL_2"]} if step is LOW["steps"][1] else step for step in LOW["steps"]]
    synthetic = LOW | {"steps": steps}
    db_config = _STORED | _db(REVERSE_PROXY_URL_2=("/old", "ui"))
    scope = postable_template_scope(synthetic, db_config, blacklisted=BLACKLISTED)
    assert "REVERSE_PROXY_URL_2" in scope, "premise: the stepper renders and posts this key"

    payload = _run_template_save(monkeypatch, db_config=db_config, posted=_POSTED | {"REVERSE_PROXY_URL_2": "/new"}, scope=scope)

    assert payload["REVERSE_PROXY_URL_2"] == "/new"


def test_blacklisted_globals_never_ride_into_a_template_save(monkeypatch):
    """Pins the guard's `_base_setting_name(setting) == setting` clause. `db_config` comes from
    `get_service(..., full=True)`, so it carries the merged global settings -- including
    DATABASE_URI and BUNKERWEB_INSTANCES. `restore_unowned_settings` can never let those through
    (they are in `restore_skip`, which is `get_blacklisted_settings() | {...}`), but the
    re-injection runs BEFORE it and writes straight into `variables`, so it is not covered by that
    guarantee. Dropping the base clause makes every template save post the database URI as a
    per-service setting."""
    db_config = _STORED | _db(DATABASE_URI=("sqlite:////data/db.sqlite3", "scheduler"), BUNKERWEB_INSTANCES=("bunkerweb", "scheduler"))
    scope = postable_template_scope(LOW, db_config, blacklisted=BLACKLISTED)
    payload = _run_template_save(monkeypatch, db_config=db_config, posted=_POSTED, scope=scope)

    assert "DATABASE_URI" not in payload
    assert "BUNKERWEB_INSTANCES" not in payload


def test_suffixed_template_default_is_carried_when_the_template_is_unchanged(monkeypatch):
    """The control case for the switch test below: the guard must be conditional on the switch,
    not unconditional.

    Honest note on its strength, and this one really is an equivalence: the row is carried by TWO
    independent layers -- the re-injection and, because method="default" is non-editable under
    allow_default=False, `restore_unowned_settings`' own method-based restore. No mutation of
    either layer alone can turn it red. The discriminating assertion for the re-injection itself is
    `test_suffixed_multiple_rows_survive_a_template_save`, whose rows are ui-method and therefore
    have only one layer holding them up."""
    db_config = _STORED | _db(REVERSE_PROXY_URL_1=("/legacy", "default", False, "low"))
    scope = postable_template_scope(LOW, db_config, blacklisted=BLACKLISTED)
    payload = _run_template_save(monkeypatch, db_config=db_config, posted=_POSTED, scope=scope)

    assert payload["REVERSE_PROXY_URL_1"] == "/legacy"


def test_suffixed_template_default_is_dropped_when_the_save_switches_template(monkeypatch):
    """The re-injection runs BEFORE `restore_unowned_settings`, so it bypasses that function's
    own template guard (save_scope.py:83-84) unless the guard is re-applied locally. Without it,
    an outgoing template's default rides across a USE_TEMPLATE switch and
    db_methods/config_save.py:1067-1071 materialises it as a real ui-method row -- permanently
    detaching the service from the template it came from. Reachable from the service page too:
    services.py:910 reads `mode` from an unvalidated query parameter."""
    db_config = _STORED | _db(REVERSE_PROXY_URL_1=("/legacy", "default", False, "low"))
    scope = postable_template_scope(LOW, db_config, blacklisted=BLACKLISTED)
    payload = _run_template_save(monkeypatch, db_config=db_config, posted=_POSTED | {"USE_TEMPLATE": "high"}, scope=scope)

    assert "REVERSE_PROXY_URL_1" not in payload
    # A suffixed row that is NOT an outgoing template default is still carried -- the guard is
    # scoped to method="default" WITH a template, not to every suffixed row.
    assert payload["REVERSE_PROXY_HOST_1"] == "http://b"


# ======================================================================================
# The custom-config branch (services.py:597-643). This slice put it on the new page's save
# path (`if mode == "easy"` -> `if mode in ("easy", "template")`) and rewrote the None-guard at
# :632, and until these two tests nothing in the repo drove `update_service` with a
# CUSTOM_CONF_* key at all -- coverage reported the whole `if conf_match:` body missing, so
# every mutant inside it survived the suite.
# ======================================================================================

_CUSTOM_CONF_KEY = "CUSTOM_CONF_MODSEC_CRS_api"  # what the ace editor's data-name really is
_CUSTOM_CONF_BODY = "SecRuleEngine On\n"


def test_a_posted_custom_config_leaves_the_settings_payload_and_is_saved_as_a_config(monkeypatch):
    """Two properties in one save, because they are two halves of the same handoff.

    1. No CUSTOM_CONF_* key may survive into the settings payload: `save_config` would either
       reject it or write it as a setting row, and either way the config itself is lost.
    2. It must arrive at the config save, as `{type, name, data}` derived from the posted key.

    The settings are posted UNCHANGED on purpose. `configs_changed` is then the only thing
    standing between this save and services.py:740's "nothing was changed" early return, so a
    save path that forgets to set it silently discards a real config edit -- and this test goes
    red on `edit_service` never being called rather than on a wrong value.

    `get_configs` returns [] (the default, and the live case whenever the config belongs to a
    template the service does not use), so `db_custom_config["data"]` is None here: the
    pre-slice `db_custom_config["data"].strip()` raises AttributeError inside the
    CONFIG_TASKS_EXECUTOR future and discards the whole save, settings included."""
    api = Mock()
    db_config = _STORED | _db(USE_UI=("no", "ui"))
    scope = postable_template_scope(LOW, db_config, blacklisted=BLACKLISTED)
    unchanged = _POSTED | {"MAX_CLIENT_SIZE": "10m"}
    payload = _run_template_save(monkeypatch, db_config=db_config, posted=unchanged | {_CUSTOM_CONF_KEY: _CUSTOM_CONF_BODY}, scope=scope, api=api)

    assert not [key for key in payload if key.startswith("CUSTOM_CONF")]
    saved = api.bulk_save_configs.call_args[0][0]
    assert [(config["type"], config["name"], config["data"]) for config in saved] == [("modsec_crs", "api", "SecRuleEngine On")]
    assert saved[0]["service_id"] == "app.example.com"


def test_editing_a_stored_custom_config_replaces_it_instead_of_adding_a_second_row(monkeypatch):
    """The other half of the same branch: the lookup key it builds
    (`f"{conf_match['type'].lower()}_{conf_match['name']}"`) is what matches the posted config to
    the one already stored. Lose the `.lower()` and the key becomes MODSEC_CRS_api, the lookup
    misses, and the edit is written under a SECOND key -- so the save ships both the new body and
    the stale one, which is why this asserts the row COUNT and not just the body."""
    api = Mock()
    stored = [{"service": "app.example.com", "type": "modsec_crs", "name": "api", "data": "# old", "method": "ui", "template": None}]
    scope = postable_template_scope(LOW, _STORED, blacklisted=BLACKLISTED)
    _run_template_save(monkeypatch, db_config=_STORED, posted=_POSTED | {_CUSTOM_CONF_KEY: _CUSTOM_CONF_BODY}, scope=scope, api=api, configs=stored)

    saved = api.bulk_save_configs.call_args[0][0]
    assert [(config["type"], config["name"], config["data"]) for config in saved] == [("modsec_crs", "api", "SecRuleEngine On")]


# ======================================================================================
# Route wiring (plan D2.1). `postable_scope`'s logic was unit-tested in the previous slice
# while its wiring was verified by inspection only, and that gap shipped a Critical. This
# POSTs through the real route and asserts what is actually handed to `submit`.
# ======================================================================================


@pytest.fixture
def route_app():
    app = Flask(__name__)
    app.secret_key = "test"
    app.register_blueprint(_services_module.services)
    app.add_url_rule("/loading", "loading", lambda: "")
    return _services_module, app


def _post_template_page(module, app, monkeypatch, *, db_config, form=None, permissions=("read", "write"), template="low"):
    api = Mock()
    api.readonly = False
    # Raw API payloads, with no `dom_id`: the POST path returns before inject_template_dom_ids,
    # so this is the shape `resolve_template` really hands `postable_template_scope`.
    api.get_templates.return_value = {"low": _template_payload("low"), "api": _template_payload("api")}
    api.get_service.return_value = db_config
    executor = Mock()
    monkeypatch.setattr(module, "API_CLIENT", api)
    monkeypatch.setattr(module, "CONFIG_TASKS_EXECUTOR", executor)
    monkeypatch.setattr(module, "DATA", _FakeData(TO_FLASH=[]))
    monkeypatch.setattr(module, "current_user", SimpleNamespace(list_permissions=list(permissions)))

    data = {"csrf_token": "x"} | (form or {})
    with app.test_request_context(f"/services/app.example.com/templates/{template}", method="POST", data=data):
        # The route's own return value is the post-save redirect, and it is the only place the
        # rename branch is observable. Hung off the Mock rather than returned so every existing
        # caller keeps unpacking a plain `executor`.
        executor.response = module.services_template_page.__wrapped__("app.example.com", template)
    return executor


def _redirect_next(response):
    """The `next` the loading page will bounce to once the save finishes."""
    return parse_qs(urlsplit(response.headers["Location"]).query).get("next")


def test_route_hands_update_service_the_template_mode_and_the_derived_scope(route_app, monkeypatch):
    module, app = route_app
    db_config = _STORED | _db(SECURITY_MODE=("block", "scheduler", False))
    executor = _post_template_page(module, app, monkeypatch, db_config=db_config, form={"SERVER_NAME": "app.example.com", "USE_TEMPLATE": "low"})

    args, kwargs = executor.submit.call_args
    # submit(update_service, service, variables, is_draft, mode, clone, file_setting_names, scope=...)
    assert args[0] is module.update_service
    assert args[1] == "app.example.com"
    assert args[4] == "template"
    # Absolute properties, not `== postable_template_scope(...)`: computing the oracle by calling
    # the function under test moves both sides together, so it can only detect a scope that is not
    # derived from THIS template -- never a wrong argument handed to it.
    assert "SERVER_NAME" in kwargs["scope"]
    assert "SECURITY_MODE" not in kwargs["scope"]  # the per-row method rule reached it
    assert "REVERSE_PROXY_HOST_1" not in kwargs["scope"]  # ...and so did rule 9
    assert kwargs["scope"] <= LOW_STEP_NAMED  # derived from `low`, not from `api` or a plugin


def test_route_passes_the_blacklist_to_the_scope_call(route_app, monkeypatch):
    """`blacklisted=get_blacklisted_settings()` is unobservable on a shipped manifest -- no
    template names a permanently blacklisted key -- so the wiring needs a template that does.
    **Synthetic**, and deliberately so: without it the route could pass `blacklisted=set()` and
    every assertion in this file would still be green, while a template save would then claim
    IS_DRAFT and publish the service."""
    module, app = route_app
    steps = [step | {"settings": step["settings"] + ["IS_DRAFT"]} if step is LOW["steps"][0] else step for step in LOW["steps"]]
    synthetic = LOW | {"steps": steps}
    monkeypatch.setattr(module, "resolve_template", lambda template, templates_data: synthetic if template == "low" else None)
    executor = _post_template_page(module, app, monkeypatch, db_config=_STORED)

    assert "IS_DRAFT" not in executor.submit.call_args.kwargs["scope"]
    assert "SERVER_NAME" in executor.submit.call_args.kwargs["scope"]


def test_route_yields_an_empty_scope_for_a_user_without_write_permission(route_app, monkeypatch):
    """`is_readonly` is recomputed on POST from the same formula the GET used (main.py:1283), and
    it must reach the scope call: a form that somehow submitted while read-only posts nothing, so
    a non-empty scope would delete every ui-method row the template names."""
    module, app = route_app
    executor = _post_template_page(module, app, monkeypatch, db_config=_STORED, permissions=("read",))

    assert executor.submit.call_args.kwargs["scope"] == set()


def test_route_yields_an_empty_scope_when_the_service_is_locked_to_another_template(route_app, monkeypatch):
    """`template_editable` must reach the scope call too -- the page renders the notice, not the
    stepper, so nothing posts."""
    module, app = route_app
    db_config = _STORED | _db(USE_TEMPLATE=("high", "scheduler"))
    executor = _post_template_page(module, app, monkeypatch, db_config=db_config)

    assert executor.submit.call_args.kwargs["scope"] == set()


def test_route_keeps_a_service_with_no_template_editable(route_app, monkeypatch):
    """`template_editable` is `is_editable_method(m) or not selected_template or template ==
    selected_template`, and the middle clause carries the COMMON case, not an edge one: a service
    that uses no template gets `USE_TEMPLATE = {"value": "", "method": "default"}` from
    `full=True`, and `is_editable_method("default")` is False (app/utils.py:234-236). Drop that
    clause and every default service gets an empty scope -- the page renders its fields and the
    save silently owns nothing."""
    module, app = route_app
    db_config = _STORED | _db(USE_TEMPLATE=("", "default"))
    executor = _post_template_page(module, app, monkeypatch, db_config=db_config)

    assert "SERVER_NAME" in executor.submit.call_args.kwargs["scope"]


def test_route_rejects_an_unknown_template_id(route_app, monkeypatch):
    """`resolve_template` is a membership check, never a regex, and the raw segment is never
    interpolated into a flash (flash.html renders with |safe)."""
    module, app = route_app
    monkeypatch.setattr(module, "handle_error", lambda *args, **kwargs: "REJECTED")
    executor = _post_template_page(module, app, monkeypatch, db_config=_STORED, template="../../etc/passwd")

    executor.submit.assert_not_called()


def test_a_rename_sends_the_user_to_the_service_list(route_app, monkeypatch):
    """A rename makes this page's own URL dead -- the path segment still names the pre-rename
    service, so the GET behind the loading page would flash "Service not found" right next to the
    save's success message. The redirect is computed from the RAW posted SERVER_NAME, so it is
    invisible to every other test in this file: they all discard the route's response."""
    module, app = route_app
    executor = _post_template_page(module, app, monkeypatch, db_config=_STORED, form={"SERVER_NAME": "renamed.example.com", "USE_TEMPLATE": "low"})

    assert _redirect_next(executor.response) == ["/services"]


def test_a_save_without_a_rename_comes_back_to_this_page(route_app, monkeypatch):
    """The control half, and it is not optional: an UNCONDITIONAL
    `url_for("services.services_page")` satisfies the rename test above while throwing the user
    off the page on every ordinary save."""
    module, app = route_app
    executor = _post_template_page(module, app, monkeypatch, db_config=_STORED, form={"SERVER_NAME": "app.example.com", "USE_TEMPLATE": "low"})

    assert _redirect_next(executor.response) == ["/services/app.example.com/templates/low"]


def test_get_hands_the_page_the_context_it_cannot_derive_itself(route_app, monkeypatch):
    """The GET path had no coverage at all, and five of its lines fail silently rather than loudly.

    `inject_template_dom_ids` is the sharpest: its own docstring says "a route that skips this
    renders a stepper whose navigation silently no-ops", and it had zero test references anywhere
    in the repo. `selected_template` decides what Reset means (wrong value => Reset loads the
    template's defaults over the user's saved ones), `is_draft` round-trips the draft state, and
    `configs` is what puts the service's STORED custom config in the editor instead of the
    template's default."""
    module, app = route_app
    api = Mock()
    api.readonly = False
    api.get_templates.return_value = {"low": _template_payload("low"), "api": _template_payload("api")}
    api.get_service.return_value = _STORED | _db(IS_DRAFT=("yes", "ui"), USE_TEMPLATE=("high", "ui"))
    api.get_configs.return_value = [{"service": "app.example.com", "type": "modsec", "name": "anomaly_score", "data": "# stored"}]
    monkeypatch.setattr(module, "API_CLIENT", api)
    monkeypatch.setattr(module, "DATA", _FakeData(TO_FLASH=[]))
    monkeypatch.setattr(module, "current_user", SimpleNamespace(list_permissions=["read", "write"]))
    captured = {}
    monkeypatch.setattr(module, "render_template", lambda name, **context: captured.update(context, _name=name) or "")

    with app.test_request_context("/services/app.example.com/templates/low"):
        module.services_template_page.__wrapped__("app.example.com", "low")

    assert captured["_name"] == "template_settings_page.html"
    assert list(captured["templates"]) == ["low"]
    assert captured["templates"]["low"]["dom_id"] == "low"  # inject_template_dom_ids ran
    assert captured["service_id"] == "app.example.com"
    assert captured["is_draft"] == "yes"
    assert captured["selected_template"] == "high"
    assert captured["template_method"] == "ui"
    assert captured["clone"] is None
    assert captured["configs"]["app.example.com_modsec_anomaly_score"]["data"] == b"# stored"
    assert captured["config"] is api.get_service.return_value


# ======================================================================================
# template_settings_page.html -- rendered off a standalone Jinja env, same harness as
# test_plugin_settings_page.py. The page `{% extends "dashboard.html" %}`, so the loader stubs
# dashboard.html down to its `content` and `scripts` blocks; without the `scripts` placeholder
# the page's own override is silently dropped and every script assertion below goes vacuous.
# ======================================================================================


@pytest.fixture
def render_template_page():
    env = Environment(
        loader=ChoiceLoader(
            [
                DictLoader({"dashboard.html": "{% block content %}{% endblock %}{% block scripts %}{% endblock %}"}),
                FileSystemLoader(TEMPLATES),
            ]
        ),
        autoescape=True,
    )

    def _url_for(endpoint, **kwargs):
        if endpoint == "static" and "filename" in kwargs:
            return f"/static/{kwargs['filename']}"
        return f"/{endpoint}"

    env.globals.update(
        csrf_token=lambda: "test-csrf-token",
        url_for=_url_for,
        get_blacklisted_settings=get_blacklisted_settings,
        get_filtered_settings=get_filtered_settings,
        get_multiples=get_multiples,
        is_editable_method=is_editable_method,
        get_plugins_settings=lambda: PLUGINS_SETTINGS,
        resource_kind_for_setting=lambda *_: None,
    )

    def _render(
        template="low",
        template_data=None,
        service_id="app.example.com",
        selected_template="low",
        template_method="ui",
        is_draft="no",
        use_ui="no",
        is_readonly=False,
        user_readonly=False,
        configs=None,
        extra_config=None,
        plugins=None,
    ):
        if template_data is None:
            template_data = LOW if template == "low" else API_TPL
        config = {
            "SERVER_NAME": {"value": service_id, "method": "ui"},
            "IS_DRAFT": {"value": is_draft, "method": "ui"},
            "USE_TEMPLATE": {"value": selected_template, "method": template_method},
            "USE_UI": {"value": use_ui, "method": "ui"},
        }
        config.update(extra_config or {})
        return env.get_template("template_settings_page.html").render(
            config=config,
            templates={template: template_data},
            configs=configs or {},
            service_id=service_id,
            clone=None,
            is_draft=is_draft,
            service_method="ui",
            template_method=template_method,
            selected_template=selected_template,
            is_readonly=is_readonly,
            user_readonly=user_readonly,
            plugins=PLUGINS if plugins is None else plugins,
            plugin_types=PLUGIN_TYPES,
            pro_diamond_url="/static/img/pro.svg",
            theme="light",
        )

    return _render


_CONTROL_TAG_RX = re.compile(r"<(?:input|select|textarea)\b[^>]*>", re.I)
_NAME_RX = re.compile(r'\bname="([^"]*)"')
_DISABLED_RX = re.compile(r"\sdisabled(?=[\s>=])")
_ACE_TAG_RX = re.compile(r"<div[^>]*\bace-editor\b[^>]*>")


def _named_enabled_controls(html):
    """Every form control that would actually post: has a `name`, has no `disabled`."""
    found = []
    for tag in _CONTROL_TAG_RX.finditer(html):
        raw = tag.group(0)
        name = _NAME_RX.search(raw)
        if name and not _DISABLED_RX.search(raw):
            found.append(name.group(1))
    return found


@pytest.mark.parametrize("key", CONTROL_KEYS)
def test_page_posts_every_restore_skip_control_key(key, render_template_page):
    """`restore_unowned_settings` never restores restore_skip keys, so whatever this form omits
    is destroyed: omitting IS_DRAFT publishes a draft service, omitting USE_UI deletes the row,
    and omitting USE_TEMPLATE makes config_save materialise the whole template as real rows,
    permanently detaching the service from it."""
    html = render_template_page()
    assert f'name="{key}"' in html


def test_control_key_values_round_trip(render_template_page):
    html = render_template_page(is_draft="yes", use_ui="yes", selected_template="low")
    assert 'name="IS_DRAFT" value="yes"' in html
    assert 'name="USE_UI" value="yes"' in html
    assert 'name="USE_TEMPLATE" value="low"' in html
    assert 'name="OLD_SERVER_NAME" value="app.example.com"' in html


def test_control_block_renders_after_the_stepper(render_template_page):
    """`request.form.to_dict()` keeps the FIRST value for a repeated name, so an enabled field a
    step renders (low's step 1 names SERVER_NAME) must win while a disabled or unrendered one
    falls through to the hidden fallback. Position is the whole mechanism.

    `html.index(x) < html.rindex(x)` is TAUTOLOGICAL whenever the needle occurs twice -- it is
    true for every such string and proves only that it occurs twice. Assert real positions, at
    BOTH ends: "the last one is hidden" alone would also hold if both of them were."""
    html = render_template_page()
    assert html.count('name="SERVER_NAME"') == 2
    first, last = html.index('name="SERVER_NAME"'), html.rindex('name="SERVER_NAME"')
    assert html[:last].rstrip().endswith('<input type="hidden"')
    first_tag_end = html.index(">", first)
    assert "plugin-setting" in html[first:first_tag_end]
    assert html.rindex('id="navs-steps-low-11"') < html.rindex('name="USE_UI"')


def test_current_endpoint_is_reasserted_to_the_service_id(render_template_page):
    """`current_endpoint` is `request.path.split("/")[-1]` (main.py:1184), i.e. the TEMPLATE id
    on this route, and the shared body uses it as a custom-config key prefix
    (models/template_steps_body.html:235). Asserted behaviourally with a decoy keyed by the
    template id: a grep for the `{% set %}` proves nothing about which branch the include took."""
    html = render_template_page(
        configs={
            "app.example.com_modsec_anomaly_score": {"method": "ui", "data": b"# stored on the service"},
            "low_modsec_anomaly_score": {"method": "ui", "data": b"# DECOY keyed by the template id"},
        }
    )
    assert "# stored on the service" in html
    assert "DECOY" not in html


def test_stored_config_bytes_reach_the_mirror_textarea_verbatim(render_template_page):
    """The `-value` mirror is rendered with `|safe` (models/template_steps_body.html:248) while
    `-default` is escaped, and that asymmetry is deliberate rather than accidental: the editor and
    settings-widgets.js's submit handler both read `textarea.value`, so escaping here would be
    inert for correctness -- but removing `|safe` is still not free, and this test says why in both
    directions.

    Cost, recorded on purpose rather than discovered later: stored bytes are interpolated raw into
    the page, so a config containing `</textarea><script>` closes the element. Inherited verbatim
    from models/plugins_settings_easy.html:321 (confirmed against HEAD), reachable only by someone
    who can already write custom configs, and defanged by main.py's `'strict-dynamic'` CSP, which
    makes a modern browser ignore the sibling `'unsafe-inline'`. Not a blocker and not this
    slice's to change -- but now a decision on record with a test that fails if it moves."""
    html = render_template_page(configs={"app.example.com_modsec_anomaly_score": {"method": "ui", "data": b'SecRule ARGS "@rx <script>" "id:1"'}})
    assert 'SecRule ARGS "@rx <script>" "id:1"' in html


def test_page_renders_one_pane_per_step_and_one_nav_item_per_step(render_template_page):
    html = render_template_page()
    assert len(LOW["steps"]) == 11
    assert html.count('class="ps-1 pe-1 tab-pane fade') == 11
    assert html.count('class="list-group-item step-navigation-item') == 11
    assert html.count('data-template-id="low"') == 12  # the outer pane + one per step pane


def test_step_nav_items_carry_the_attributes_the_submit_gate_counts(render_template_page):
    """The markup half of the capture-phase gate's contract, and it can rot on its own:
    `template-settings-page.js:525-527` sizes its walk with
    `.step-navigation-item[data-template="<id>"]`, so an empty or missing `data-template` makes
    `totalSteps` 0 and the gate walks NOTHING while still looking installed. `data-step` is what
    `getStepContainer` then resolves each iteration against."""
    html = render_template_page()
    nav_items = re.findall(r'<li class="list-group-item step-navigation-item[^>]*>', html)
    assert len(nav_items) == 11
    assert all('data-template="low"' in item for item in nav_items)
    assert [re.search(r'data-step="(\d+)"', item).group(1) for item in nav_items] == [str(n) for n in range(1, 12)]
    step_panes = re.findall(r'<div id="navs-steps-low-\d+"[^>]*>', html)
    assert [re.search(r'data-step="(\d+)"', pane).group(1) for pane in step_panes] == [str(n) for n in range(1, 12)]
    assert all('data-template-dom-id="low"' in pane for pane in step_panes)


def test_no_button_inside_the_form_can_submit_by_accident(render_template_page):
    """A `<button>` with no `type` inside a form defaults to `type="submit"` -- and the two modal
    confirm buttons this page relocated (`models/plugins_settings_easy.html:132-135`, `:169-172`)
    carry no `type` in the source they were copied from. Two independent guards: the modals render
    OUTSIDE `</form>`, and both confirms carry an explicit `type="button"`. The page's own comment
    calls this "the difference between 'Reset template configuration' opening a dialog and it
    silently saving the service"."""
    html = render_template_page()
    form_start, form_end = html.index("<form "), html.index("</form>")
    form = html[form_start:form_end]
    assert [tag for tag in re.findall(r"<button\b[^>]*>", form) if "type=" not in tag] == []
    assert 'id="modal-reset-template-config"' not in form
    assert 'id="modal-fetch-global-config"' not in form
    for button_id in ("confirm-reset-template-config", "confirm-fetch-global-config"):
        tag = re.search(rf'<button id="{button_id}"[^>]*>', html)
        assert tag and 'type="button"' in tag.group(0), button_id


def test_outer_pane_carries_the_ids_the_stepper_scopes_itself_through(render_template_page):
    """`getTemplateContainer` selects `.tab-pane[data-template-id="..."]` and everything --
    prev/next, the active step pane, Reset's step reset -- is scoped through it. If the OUTER
    pane loses the attribute the only matches are the step panes, which are inside it, so every
    `templateContainer.find(...)` returns empty and the stepper is silently dead.

    Asserted on the outer pane's own tag: the step panes carry the same two attributes, so a bare
    `'data-template-id="low"' in html` passes with the outer pane stripped bare."""
    html = render_template_page()
    tag = re.search(r'<div id="navs-templates-low"[^>]*>', html)
    assert tag, "outer template pane missing"
    assert 'data-template-id="low"' in tag.group(0)
    assert 'data-template-dom-id="low"' in tag.group(0)
    assert "tab-pane fade show active" in tag.group(0)


def test_every_ace_editor_has_its_mirror_textareas(render_template_page):
    """The editor's content is read back through `data-source` (settings-widgets.js's submit
    normalisation reads the mirror, never the `ace` global), and compared against `-default` to
    decide whether the config differs from the template's. A missing pair means the config is
    silently dropped from the POST."""
    html = render_template_page(template="api")
    editors = _ACE_TAG_RX.findall(html)
    assert len(editors) == 2  # api step 4 ships modsec/api.conf and modsec-crs/api.conf
    for tag in editors:
        editor_id = re.search(r'id="([^"]+)"', tag).group(1)
        assert re.search(r'data-name="CUSTOM_CONF_[^"]+"', tag), tag
        assert f'data-source="#{editor_id}-value"' in tag
        assert f'<textarea id="{editor_id}-default"' in html
        assert f'<textarea id="{editor_id}-value"' in html
    assert 'data-name="CUSTOM_CONF_MODSEC_CRS_api"' in html


def test_every_step_setting_carries_its_template_default_mirror(render_template_page):
    """The settings-side counterpart of the ace `-default`/`-value` pair above, and it was the
    one thing 62 rendering tests did not pin: deleting the three-line hidden input at
    models/template_steps_body.html:206-208 leaves the whole suite green.

    `resolveTemplateValue` (template-settings-page.js:568) reads `#<field-id>-template` and the
    plain `input, select` reset loop at :575 has no `undefined` guard (unlike the multiselect and
    multivalue loops), so with the input gone Reset BLANKS every text/number/size field instead
    of restoring the template's defaults.

    Probed on MAX_CLIENT_SIZE, and the choice of setting is the whole test: `{{
    template_data['settings'].get(setting, setting_default) }}` and `{{ setting_default }}` are
    the same string for any setting whose template value equals its plugin default, so a probe
    like SECURITY_MODE (`block` in low.json AND in settings.json) cannot tell the two apart and
    the mutant survives -- measured. MAX_CLIENT_SIZE is `100m` in low.json and `10m` in
    src/common/core/misc/plugin.json, so all three candidate sources are distinguishable, and 19
    of low's 86 step-named settings are in that position: on every one of them a fallback to the
    plugin default makes Reset restore the wrong value.

    Asserted with a decoy stored value too: the input must carry the TEMPLATE's default, never the
    service's current one, or Reset silently becomes a no-op."""
    html = render_template_page(extra_config={"MAX_CLIENT_SIZE": {"value": "50m", "method": "ui"}})
    template_default = LOW["settings"]["MAX_CLIENT_SIZE"]
    plugin_default = PLUGINS_SETTINGS["MAX_CLIENT_SIZE"]["default"]
    assert template_default == "100m" and plugin_default == "10m", "fixture premise: the template overrides the plugin default"
    assert "50m" not in (template_default, plugin_default), "fixture premise: the stored decoy differs from both"
    tag = re.search(r'<input id="low-setting-templates-max-client-size-template"[^>]*>', html)
    assert tag, "the per-setting -template mirror is gone -- Reset blanks the field instead of restoring the default"
    assert 'type="hidden"' in tag.group(0)
    assert f'value="{template_default}"' in tag.group(0)
    assert f'value="{plugin_default}"' not in tag.group(0), "the mirror carries the PLUGIN default -- Reset restores the wrong value"
    assert 'value="50m"' not in tag.group(0), "the mirror carries the STORED value -- Reset is a no-op"
    # One per rendered step field, not just this one.
    assert len(re.findall(r'<input id="low-setting-templates-[^"]+-template"', html)) == sum(len(step["settings"]) for step in LOW["steps"])


def test_template_in_use_notice_replaces_the_stepper_but_not_the_control_block(render_template_page):
    """Dropping the control block behind an `{% if template_editable %}` would look correct and
    would delete USE_UI on every save of a locked service."""
    html = render_template_page(selected_template="high", template_method="scheduler")
    assert 'data-i18n="status.template_in_use"' in html
    assert 'class="ps-1 pe-1 tab-pane fade' not in html
    assert set(_named_enabled_controls(html)) == {"csrf_token", *CONTROL_KEYS}
    assert 'name="USE_TEMPLATE" value="high"' in html


def test_form_carries_the_native_submit_marker(render_template_page):
    """T4's hard invariant. models/checkbox_setting.html is a bare `type="checkbox"` with a
    `name` and NO `value` and no hidden companion: unchecked, it posts nothing. The
    normalisation that turns that into "no" is bound to `form[data-plugin-settings-form]`
    (settings-widgets.js:1626). Without the marker, turning any of low's 19 switches off DELETES
    its row instead of setting it to "no"."""
    html = render_template_page()
    assert "data-plugin-settings-form" in html
    switches = [tag for tag in _CONTROL_TAG_RX.findall(html) if 'type="checkbox"' in tag and "plugin-setting" in tag and _NAME_RX.search(tag)]
    assert len(switches) == 19
    assert not any('value="' in tag for tag in switches), "a checkbox with a value would post without the normaliser -- retune this test, not the page"


def test_form_is_novalidate(render_template_page):
    """models/input_setting.html emits `pattern=` unconditionally and overrides.css:1637 hides
    non-active step panes with `display: none !important`. A browser refuses to submit a form
    containing an invalid NON-FOCUSABLE control and never dispatches `submit` at all -- so an
    invalid value left on step 7 makes Save do nothing, with no message and no flash, and
    settings-widgets.js's normalisation never runs either. js/pages/template-settings-page.js's
    capture-phase gate is what replaces the browser's check."""
    html = render_template_page()
    assert "novalidate" in html


def test_form_action_is_relative(render_template_page):
    """A hardcoded absolute action posts the __Host- session cookie and a valid CSRF token to
    whatever serves / when the UI is mounted behind REVERSE_PROXY_URL."""
    html = render_template_page()
    assert 'action=""' in html
    assert 'action="/services' not in html


def test_page_loads_ace_then_the_widgets_module_then_its_own_script(render_template_page):
    """Order is a hard dependency: settings-widgets.js publishes `window.BWSettingsWidgets`,
    which template-settings-page.js destructures and hard-fails without (deferred scripts run in
    document order). And per D0.1 no page may load the monolith alongside them -- every handler
    in both files is `$(document).on(...)` delegated, so one ADD click would clone twice."""
    html = render_template_page()
    positions = [html.index(f"/static/{src}") for src in ("libs/ace/src-min/ace.js", "js/components/settings-widgets.js", "js/pages/template-settings-page.js")]
    assert positions == sorted(positions)
    assert "js/plugins-settings.js" not in html
    assert "js/pages/plugin-settings-page.js" not in html


def test_used_template_input_is_present_and_nameless(render_template_page):
    """`resetTemplateConfig` branches on it -- restore the saved values on the service's active
    template, load the defaults on any other one -- and it must reflect the SERVICE's template,
    not the page's. A `name` here (service_settings.html:13-16 has one, and copying that file is
    the obvious next move) would post a junk `used_template` key into update_service."""
    html = render_template_page(selected_template="high", template_method="ui")
    marker = html.index('id="used-template"')
    start, end = html.rindex("<input", 0, marker), html.index(">", marker) + 1
    tag = html[start:end]
    assert 'value="high"' in tag
    assert "name=" not in tag


def test_readonly_emits_no_enabled_control_that_can_post(render_template_page):
    """ "Every control is disabled" and "no enabled control carrying a name" are different claims
    and only the second is the property that matters -- models/multiselect_setting.html:122-151
    renders its search box and per-option checkboxes with neither `disabled` nor `name`
    unconditionally, so the first is simply false on a real read-only render."""
    readonly = set(_named_enabled_controls(render_template_page(is_readonly=True)))
    assert readonly == {"csrf_token", *CONTROL_KEYS}
    # Non-vacuity: the same page is full of postable controls when it is not read-only.
    assert len(_named_enabled_controls(render_template_page())) > 80


def test_readonly_marks_every_ace_editor_readonly(render_template_page):
    html = render_template_page(template="api", is_readonly=True)
    editors = _ACE_TAG_RX.findall(html)
    assert editors
    assert all('data-method="readonly"' in tag for tag in editors)


def test_page_renders_when_the_owning_plugin_is_missing(render_template_page):
    """`plugins` is empty whenever the API call behind it failed; the partial falls back to a
    `ui` pseudo-plugin for the header badge (models/template_steps_body.html:32-34) rather than
    raising -- while `plugin_dom_id` still comes from `template_data["plugin_id"]`, so no id the
    stepper JS keys off changes."""
    html = render_template_page(plugins={})
    assert 'class="ps-1 pe-1 tab-pane fade' in html
    assert "low-setting-templates-" in html


def test_settings_ids_use_the_owning_plugin_id(render_template_page):
    """Shipped templates belong to the `templates` core plugin
    (db_methods/plugins_update.py:670), so production ids are `low-setting-templates-...`, not
    the `ui` fallback a `plugin_id: None` fixture would exercise."""
    html = render_template_page()
    assert 'id="low-setting-templates-security-mode"' in html
    assert 'id="low-config-templates-modsec-anomaly_score"' in html


# ======================================================================================
# D0.1's "no page loads both" invariant, as a rendered/parsed assertion rather than a raw grep:
# plugin_settings_page.html carries a Jinja comment naming the monolith on purpose, and Jinja
# strips `{# #}` before render, so a source grep false-positives on exactly the file this
# invariant is about.
# ======================================================================================


_JINJA_COMMENT_RX = re.compile(r"\{#.*?#\}", re.S)


def test_no_template_loads_both_the_monolith_and_the_widgets_module():
    both = []
    for path in sorted(TEMPLATES.rglob("*.html")):
        rendered = _JINJA_COMMENT_RX.sub("", path.read_text(encoding="utf-8"))
        if "js/plugins-settings.js" in rendered and "js/components/settings-widgets.js" in rendered:
            both.append(path.name)
    assert both == []
    # Non-vacuity: both scripts really are loaded somewhere, just never together.
    sources = [_JINJA_COMMENT_RX.sub("", path.read_text(encoding="utf-8")) for path in TEMPLATES.rglob("*.html")]
    assert any("js/plugins-settings.js" in src for src in sources)
    assert any("js/components/settings-widgets.js" in src for src in sources)


def test_the_deleted_page_script_is_referenced_by_nobody():
    assert not (STATIC / "js" / "pages" / "plugin-settings-page.js").exists()
    referrers = [path.name for path in TEMPLATES.rglob("*.html") if "plugin-settings-page.js" in _JINJA_COMMENT_RX.sub("", path.read_text(encoding="utf-8"))]
    assert referrers == []


# ======================================================================================
# JS -- source assertions plus `node --check`. No framework exists in this repo (Prettier only,
# no Jest), so these pin the invariants that rot silently rather than the behaviour.
# ======================================================================================

_LINE_COMMENT_RX = re.compile(r"^\s*(//|\*|/\*)")


def _code_only(path: Path) -> str:
    """Both new files document, in comments, the very patterns they are forbidden to contain --
    that is the point of the comments. Strip whole-line comments before asserting absence."""
    return "\n".join(line for line in path.read_text(encoding="utf-8").splitlines() if not _LINE_COMMENT_RX.match(line))


def _submit_gate(code: str) -> str:
    """The submit listener's own source, from `document.addEventListener(` to its closing
    `);` -- so an assertion about the gate cannot be satisfied by a match elsewhere in a
    1900-line file."""
    start = code.index("document.addEventListener(")
    end = code.index("\n  );", start)
    return code[start:end]


requires_node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")


@requires_node
@pytest.mark.parametrize("script", [WIDGETS_JS, PAGE_JS], ids=lambda p: p.name)
def test_js_parses(script):
    assert subprocess.run(["node", "--check", str(script)], capture_output=True).returncode == 0


def test_widgets_module_carries_no_page_state_and_no_ace():
    """`ace.require(...)` sits at the top level of the monolith's single ready closure
    (plugins-settings.js:2521), so on a page that does not load ace it throws and every handler
    registered after it never binds. This module must stay ace-free and page-agnostic: no pane
    mode, no plugin-nav ids, and no `.save-settings` hijack (the pages that load it submit
    natively). Four pure-negative assertions, so they get an anchor first: a `_code_only` that
    silently returned nothing would satisfy every one of them."""
    code = _code_only(WIDGETS_JS)
    assert "window.BWSettingsWidgets" in code and len(code.splitlines()) > 1000
    assert "ace.require" not in code
    assert "let currentMode" not in code and "#selected-mode" not in code
    assert "navs-plugins-" not in code
    assert "save-settings" not in code


def test_widgets_module_exports_the_helpers_the_page_script_destructures():
    code = _code_only(WIDGETS_JS)
    assert "window.BWSettingsWidgets" in code
    page = _code_only(PAGE_JS)
    assert "const W = window.BWSettingsWidgets;" in page
    assert "if (!W)" in page


def test_page_script_syncs_the_ace_mirror_textarea():
    """settings-widgets.js's submit normalisation reads the `data-source` mirror, never the ace
    editor. Lose this pair and the mirror keeps its server-rendered value, `value ===
    defaultValue`, and EVERY custom-config edit is dropped from the POST with no error."""
    code = _code_only(PAGE_JS)
    assert code.count("$source.val(editor.getValue())") == 2  # the initial sync, then the `change` handler


def test_page_script_drops_four_path_segments_for_the_fetch_global_url():
    """The route is /services/<svc>/templates/<tpl>, four segments deep; the monolith drops two
    because it runs on /services/<svc>. A copy-paste back to -2 is a silent 404 on a button that
    otherwise looks fine."""
    code = _code_only(PAGE_JS)
    assert ".slice(0, -4)" in code
    assert ".slice(0, -2)" not in code


def test_page_script_dedupes_the_dom_id_scan():
    """The scan matches `[data-template-id][data-template-dom-id]`, and N step panes all carry
    the same pair. Without the guard, registerDomId's collision loop hands the 2nd..Nth
    `<dom_id>-2`, `-3` ... and overwrites the map with an id that matches no element -- so the
    stepper's own container lookup silently returns nothing."""
    code = _code_only(PAGE_JS)
    assert "if (!templateId || templateDomIdMap[templateId]) return;" in code


def test_page_script_gates_submit_in_the_capture_phase_on_document():
    """This is the invariant that rots silently. settings-widgets.js binds its normalisation
    directly on the form, from a ready callback that runs first, so a target-phase listener here
    would run SECOND: it would normalise a submit we then cancel, leave the appended hidden
    inputs behind, and the next attempt would append them again -- and `to_dict()` keeps the
    FIRST value, so a re-edited ace config would save its stale copy. A later edit to
    `form.addEventListener` still looks correct and still blocks; only the capture flag and the
    `document` target make the ordering unconditional. `stopPropagation` is required alongside
    `preventDefault`: cancelling the default action does not stop the widget listener running."""
    code = _code_only(PAGE_JS)
    gate = _submit_gate(code)
    assert gate.splitlines()[-1] == "    true,", gate.splitlines()[-3:]
    assert "event.preventDefault();" in gate
    assert "event.stopPropagation();" in gate
    assert re.findall(r'(\w+)\.addEventListener\(\s*"submit"', code) == ["document"]
    assert '.on("submit"' not in code


def test_page_script_gate_walks_every_step_not_the_visible_one():
    """The whole reason the gate exists is a pane hidden by `display: none !important`. A filter
    on `.active` or on visibility would restore exactly the bug it replaces."""
    gate = _submit_gate(_code_only(PAGE_JS))
    assert "for (let step = 1; step <= totalSteps; step++)" in gate
    assert ".active" not in gate and ":visible" not in gate


def test_page_script_validation_skips_disabled_fields():
    """A disabled field is out of scope by construction (the template disables exactly
    `not editable and not global`, which is the complement of what postable_template_scope
    admits), so validating it can only ever block a save the user cannot fix -- a permanently
    dead Save on a stored value that no longer matches a tightened regex, or on an external
    plugin shipping a Python-only regex that throws in `new RegExp`."""
    code = _code_only(PAGE_JS)
    assert "if (this.disabled) return;" in code


# ======================================================================================
# Regression: easy mode still works after T1 moved the stepper body into
# models/template_steps_body.html. Nothing in the repo rendered plugins_settings_easy.html
# before this test.
# ======================================================================================


@pytest.fixture
def render_easy_pane():
    env = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=True)
    env.globals.update(
        url_for=lambda endpoint, **kwargs: f"/{endpoint}",
        get_blacklisted_settings=get_blacklisted_settings,
        get_filtered_settings=get_filtered_settings,
        get_multiples=get_multiples,
        is_editable_method=is_editable_method,
        get_plugins_settings=lambda: PLUGINS_SETTINGS,
        resource_kind_for_setting=lambda *_: None,
    )

    def _render(templates):
        return env.get_template("models/plugins_settings_easy.html").render(
            templates=templates,
            config={"SERVER_NAME": {"value": "app.example.com", "method": "ui"}},
            configs={},
            clone=None,
            current_endpoint="app.example.com",
            service_method="ui",
            is_draft="no",
            is_readonly=False,
            user_readonly=False,
            selected_template="low",
            template_method="ui",
            plugins=PLUGINS,
            plugin_types=PLUGIN_TYPES,
            pro_diamond_url="/static/img/pro.svg",
        )

    return _render


def test_easy_mode_still_activates_step_one_of_every_template_pane(render_easy_pane):
    """The trap T1's extraction could have sprung: the body carries BOTH the templates loop's
    index (which decides which template pane is active) and the step loops' indices (which
    decide the active step INSIDE each pane). Swapping an inner one for `is_active` breaks easy
    mode invisibly.

    Counting `class="tab-pane fade show active"` cannot catch it -- the step panes emit
    `class="ps-1 pe-1 tab-pane fade show active"`, a different string, so the count passes either
    way. The load-bearing assertion is that the SECOND template's step 1 is still active."""
    html = render_easy_pane({"low": LOW, "api": API_TPL})

    for dom_id, step_count in (("low", 11), ("api", 4)):
        first = re.search(rf'<div id="navs-steps-{dom_id}-1"\s+class="([^"]*)"', html)
        assert first, f"{dom_id} step 1 pane missing"
        assert "show active" in first.group(1), f"{dom_id} step 1 is not the active step"
        assert html.count(f'<div id="navs-steps-{dom_id}-') == step_count
        # ...and only step 1 is active within that template.
        actives = re.findall(rf'<div id="navs-steps-{dom_id}-(\d+)"\s+class="[^"]*show active', html)
        assert actives == ["1"]

    # Exactly one TEMPLATE pane is active, and it is the first one -- the outer loop's index
    # still drives the outer pane, which is the other half of the same trap.
    assert html.count('class="tab-pane fade show active"') == 1
    template_panes = re.findall(r'<div id="navs-templates-([a-z]+)"\s+class="(tab-pane[^"]*)"', html)
    assert template_panes == [("low", "tab-pane fade show active"), ("api", "tab-pane fade")]
