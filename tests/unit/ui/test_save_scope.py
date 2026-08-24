"""What survives a save that only owns part of a service's configuration.

`Database.save_config` deletes the row for any key the payload omits
(`db_methods/config_save.py:592`). These tests pin down which keys
`restore_unowned_settings` puts back, and — just as importantly — which it
deliberately does not, because a key it wrongly restores is a user's clear that
silently did not happen.
"""

import importlib.util
import json
import sys
from functools import partial
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from flask import Flask

from app.models.config import Config  # type: ignore  (src/ui on path via the ui conftest)
from app.models.save_scope import control_keys, restore_unowned_settings, templates_unchanged
from app.utils import get_blacklisted_settings, is_readonly_request

RESTORE_SKIP = {"SERVER_NAME", "OLD_SERVER_NAME", "USE_TEMPLATE", "USE_UI", "IS_DRAFT"}

REPO_ROOT = Path(__file__).resolve().parents[3]
CORE_PLUGINS = REPO_ROOT / "src" / "common" / "core"
SERVICES_ROUTE = REPO_ROOT / "src" / "ui" / "app" / "routes" / "services.py"


def _import_services_module(source: Path = SERVICES_ROUTE) -> ModuleType:
    """Load ``app/routes/services.py`` against stubs -- the pattern test_plugin_settings_page.py
    documents: ``app.dependencies`` builds real singletons at module scope (``Config()`` reads the
    image-only ``/usr/share/bunkerweb/settings.json``) and ``app.routes.utils`` pulls
    ``qrcode.main``, so a bare import fails at collection time.

    ``source`` is a parameter for the same reason test_global_settings_propagation.py's loader has
    one: a mutation run points it at a modified copy under the scratchpad, never at the repo file.
    """
    dependencies = ModuleType("app.dependencies")
    dependencies.API_CLIENT = Mock()
    dependencies.BW_CONFIG = Mock()
    dependencies.CONFIG_TASKS_EXECUTOR = Mock()
    dependencies.DATA = Mock()
    # The real one is the image-only /usr/share/bunkerweb/core. Point it at the repo so
    # `core_plugin_order()` reads the SHIPPED order.json rather than exercising its fallback --
    # a Mock() here would make it return {} and every ordering assertion vacuous.
    dependencies.CORE_PLUGINS_PATH = CORE_PLUGINS
    qrcode = ModuleType("qrcode")
    qrcode_main = ModuleType("qrcode.main")
    qrcode_main.QRCode = Mock()
    qrcode.main = qrcode_main
    module_name = "app.routes._services_save_contract"
    spec = importlib.util.spec_from_file_location(module_name, source)
    module = importlib.util.module_from_spec(spec)
    stubs = {"app.dependencies": dependencies, "qrcode": qrcode, "qrcode.main": qrcode_main, module_name: module}
    with patch.dict(sys.modules, stubs):
        spec.loader.exec_module(module)
    return module


_services = _import_services_module()
postable_shelf_scope = _services.postable_shelf_scope
resolve_save_mode = _services.resolve_save_mode
shelf_plugin_scope = _services.shelf_plugin_scope


def _real_plugins():
    """Every shipped core plugin, in the shape ``BW_CONFIG.get_plugins()`` returns.

    Real manifests on purpose. Both IS_DRAFT bugs and the USE_UI bug in this chantier survived a
    round of green tests precisely because a hand-typed fixture plugin did not declare the setting
    that breaks -- ``country``'s multiselect activation keys and ``redirect``'s ``multiple`` one
    are exactly that shape, and neither is inventable by accident.
    """
    plugins = {}
    for manifest_path in sorted(CORE_PLUGINS.glob("*/plugin.json")):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        plugins[manifest.get("id") or manifest_path.parent.name] = manifest | {"type": "core"}
    return plugins


REAL_PLUGINS = _real_plugins()
# Read off the same manifests rather than transcribed, so a manifest edit shows up here as a test
# result instead of as silent drift. Mirrors iter_plugin_activations' extraction.
REAL_ACTIVATION_MAP = {
    plugin_id: data["extensions"]["activation"]
    for plugin_id, data in REAL_PLUGINS.items()
    if isinstance(data.get("extensions"), dict) and data["extensions"].get("activation") is not None
}


def _shelf_scope(db_config=None, **kwargs):
    kwargs.setdefault("global_page", False)
    kwargs.setdefault("is_pro_version", False)
    kwargs.setdefault("blacklisted", get_blacklisted_settings(kwargs["global_page"]))
    kwargs.setdefault("activation_map", REAL_ACTIVATION_MAP)
    return postable_shelf_scope(REAL_PLUGINS, db_config or {}, **kwargs)


def _entry(value, method="ui", template=""):
    return {"value": value, "method": method, "template": template}


def _db(**pairs):
    """db_config shorthand: KEY=(value, method) or KEY=(value, method, template)."""
    return {key: _entry(*args) for key, args in pairs.items()}


# ---------------------------------------------------------------- scope=None
# With no scope declared the function must behave exactly as the loop it
# replaces, or this slice is not invisible.


def test_scope_none_restores_non_editable_methods():
    db_config = _db(X_FRAME_OPTIONS=("SAMEORIGIN", "scheduler"))
    result = restore_unowned_settings({}, db_config, restore_skip=RESTORE_SKIP)
    assert result == {"X_FRAME_OPTIONS": "SAMEORIGIN"}


def test_scope_none_does_not_restore_ui_owned_keys():
    """A ui-method key absent from the payload is a real clear and must delete."""
    db_config = _db(USE_ANTIBOT=("captcha", "ui"))
    result = restore_unowned_settings({}, db_config, restore_skip=RESTORE_SKIP)
    assert result == {}


def test_scope_none_restores_template_defaults_when_template_unchanged():
    db_config = _db(SSL_PROTOCOLS=("TLSv1.2 TLSv1.3", "default", "low"))
    result = restore_unowned_settings({}, db_config, restore_skip=RESTORE_SKIP, template_unchanged=True)
    assert result == {"SSL_PROTOCOLS": "TLSv1.2 TLSv1.3"}


def test_template_unchanged_defaults_to_true():
    """`template_unchanged` defaults to True: a 3-arg call is the documented "adopt this
    before you can compute a scope" path, and it must mean "template did not change"."""
    db_config = _db(SSL_PROTOCOLS=("TLSv1.2 TLSv1.3", "default", "low"))
    result = restore_unowned_settings({}, db_config, restore_skip=RESTORE_SKIP)
    assert result == {"SSL_PROTOCOLS": "TLSv1.2 TLSv1.3"}


def test_scope_none_drops_outgoing_template_defaults_when_template_changed():
    """Switching template must not freeze the old template's values into the service."""
    db_config = _db(SSL_PROTOCOLS=("TLSv1.2 TLSv1.3", "default", "low"))
    result = restore_unowned_settings({}, db_config, restore_skip=RESTORE_SKIP, template_unchanged=False)
    assert result == {}


def test_bare_default_is_restored_even_when_template_changed():
    """The template guard only skips defaults that came FROM a template.

    A bare default (no template attached) must still be restored during a
    template switch -- ``entry.get("template")`` is the conjunct that scopes
    the guard to outgoing-template values, not to every "default" method.
    """
    db_config = _db(X_FRAME_OPTIONS=("SAMEORIGIN", "default"))
    result = restore_unowned_settings({}, db_config, restore_skip=RESTORE_SKIP, template_unchanged=False)
    assert result == {"X_FRAME_OPTIONS": "SAMEORIGIN"}


def test_non_default_method_with_template_is_restored_on_template_switch():
    """The template guard also requires ``setting_method == "default"``, not just a
    template value being present.

    Not reachable from today's producers -- every site in db_methods/config_read.py that
    sets a template also hardcodes method "default" -- so this pins a defensive contract
    rather than a live bug: a scheduler-owned row that merely records a template must
    still be restored, never skipped as if it were an outgoing template default.
    """
    db_config = _db(X=("1", "scheduler", "low"))
    result = restore_unowned_settings({}, db_config, restore_skip=RESTORE_SKIP, template_unchanged=False)
    assert result == {"X": "1"}


def test_restore_skip_defaults_to_empty_set():
    """``restore_skip`` defaults to None in the signature; omitting it must still work via
    the `or set()` normalisation rather than raising on `setting in None`."""
    result = restore_unowned_settings({}, _db(X=("1", "scheduler")))
    assert result == {"X": "1"}


def test_restore_skip_keys_are_never_restored():
    db_config = _db(USE_TEMPLATE=("low", "scheduler"), SERVER_NAME=("app.example.com", "scheduler"))
    result = restore_unowned_settings({}, db_config, restore_skip=RESTORE_SKIP)
    assert result == {}


def test_posted_keys_are_never_overwritten():
    db_config = _db(USE_ANTIBOT=("captcha", "scheduler"))
    result = restore_unowned_settings({"USE_ANTIBOT": "no"}, db_config, restore_skip=RESTORE_SKIP)
    assert result == {"USE_ANTIBOT": "no"}


def test_payload_is_not_mutated():
    payload = {"USE_ANTIBOT": "no"}
    db_config = _db(X_FRAME_OPTIONS=("SAMEORIGIN", "scheduler"))
    restore_unowned_settings(payload, db_config, restore_skip=RESTORE_SKIP)
    assert payload == {"USE_ANTIBOT": "no"}


# --------------------------------------------------------------- scope given
# The new behaviour: a form owning part of the config cannot delete the rest.


def test_out_of_scope_ui_owned_key_is_preserved():
    """The whole point: an antibot page must not delete limit's ui-owned rows."""
    db_config = _db(USE_ANTIBOT=("captcha", "ui"), LIMIT_REQ_RATE=("10r/s", "ui"))
    result = restore_unowned_settings({"USE_ANTIBOT": "no"}, db_config, scope={"USE_ANTIBOT", "ANTIBOT_URI"}, restore_skip=RESTORE_SKIP)
    assert result == {"USE_ANTIBOT": "no", "LIMIT_REQ_RATE": "10r/s"}


def test_in_scope_key_omitted_from_payload_still_clears():
    """Clearing a ui-owned setting from its own page must still go through."""
    db_config = _db(ANTIBOT_URI=("/challenge", "ui"))
    result = restore_unowned_settings({}, db_config, scope={"USE_ANTIBOT", "ANTIBOT_URI"}, restore_skip=RESTORE_SKIP)
    assert result == {}


def test_in_scope_non_editable_key_is_restored():
    """Inside the declared scope, the method-based protection still applies."""
    db_config = _db(X_FRAME_OPTIONS=("SAMEORIGIN", "scheduler"))
    result = restore_unowned_settings({}, db_config, scope={"X_FRAME_OPTIONS"}, restore_skip=RESTORE_SKIP)
    assert result == {"X_FRAME_OPTIONS": "SAMEORIGIN"}


def test_out_of_scope_key_is_preserved_regardless_of_method():
    db_config = _db(A=("1", "ui"), B=("2", "api"), C=("3", "scheduler"), D=("4", "default"))
    result = restore_unowned_settings({}, db_config, scope=set(), restore_skip=RESTORE_SKIP)
    assert result == {"A": "1", "B": "2", "C": "3", "D": "4"}


def test_restore_skip_wins_over_scope_preservation():
    """restore_skip must win even for an out-of-scope, non-editable-method key."""
    db_config = _db(SERVER_NAME=("app.example.com", "scheduler"))
    result = restore_unowned_settings({}, db_config, scope=set(), restore_skip=RESTORE_SKIP)
    assert result == {}


def test_outgoing_template_default_not_carried_forward_even_when_out_of_scope():
    """The template guard is hoisted above the scope branch on purpose.

    Changing USE_TEMPLATE happens on the service page, whose scope excludes every
    plugin setting -- so without the hoist the preserve branch would materialise
    the outgoing template's values as real service rows.
    """
    db_config = _db(SSL_PROTOCOLS=("TLSv1.2 TLSv1.3", "default", "low"))
    result = restore_unowned_settings({}, db_config, scope=set(), restore_skip=RESTORE_SKIP, template_unchanged=False)
    assert result == {}


def test_empty_scope_and_empty_db_config_is_a_no_op():
    assert restore_unowned_settings({}, {}, scope=set(), restore_skip=RESTORE_SKIP) == {}


def test_suffixed_multiple_key_matches_a_base_name_scope():
    """A scope derived from plugin.json carries base names; suffixed `multiple`
    settings must still be recognised as in-scope so a real clear goes through."""
    db_config = _db(REVERSE_PROXY_URL_2=("/app", "ui"))
    result = restore_unowned_settings({}, db_config, scope={"REVERSE_PROXY_URL"}, restore_skip=RESTORE_SKIP)
    assert result == {}


def test_similar_key_is_not_swallowed_by_base_matching():
    """Base-matching must strip a genuine `_<digits>` suffix only, not match by prefix."""
    db_config = _db(LIMIT_REQ_RATE=("10r/s", "ui"))
    result = restore_unowned_settings({}, db_config, scope={"LIMIT_REQ"}, restore_skip=RESTORE_SKIP)
    assert result == {"LIMIT_REQ_RATE": "10r/s"}


def test_suffixed_scope_key_matches_the_stored_suffixed_key():
    """`_in_scope`'s exact-match branch: a scope built from posted field names carries the
    suffixed key itself, not its base -- that's how a multi-value page posts its own fields."""
    db_config = _db(REVERSE_PROXY_URL_2=("/app", "ui"))
    result = restore_unowned_settings({}, db_config, scope={"REVERSE_PROXY_URL_2"}, restore_skip=RESTORE_SKIP)
    assert result == {}


def test_base_matching_requires_a_terminal_numeric_suffix():
    """The `$` anchor in the suffix regex: without it, a mid-string `_<digits>` segment
    would rsplit into a false base match instead of correctly leaving the key out of scope."""
    db_config = _db(FOO_2_BAR=("1", "ui"))
    result = restore_unowned_settings({}, db_config, scope={"FOO_2"}, restore_skip=RESTORE_SKIP)
    assert result == {"FOO_2_BAR": "1"}


def test_multi_digit_suffix_matches_a_base_name_scope():
    """The `+` in `_\\d+$`: multi-value suffixes routinely pass 9 -- `reverseproxy` alone
    declares 19 `multiple` settings -- so a single-digit pattern would leave every entry
    from _10 upwards permanently unclearable."""
    db_config = _db(REVERSE_PROXY_URL_10=("/app", "ui"))
    result = restore_unowned_settings({}, db_config, scope={"REVERSE_PROXY_URL"}, restore_skip=RESTORE_SKIP)
    assert result == {}


def test_trailing_digit_without_a_separator_is_not_a_suffix():
    """The leading `_` in `_\\d+$`: real setting ids end in a bare digit (LIMIT_CONN_MAX_HTTP2,
    ANTIBOT_RECAPTCHA_JA3, USE_IPV6). Those are whole names, not indexed entries, and must not
    be stripped down to a base that happens to be in scope."""
    db_config = _db(LIMIT_CONN_MAX_HTTP2=("100", "ui"))
    result = restore_unowned_settings({}, db_config, scope={"LIMIT_CONN_MAX"}, restore_skip=RESTORE_SKIP)
    assert result == {"LIMIT_CONN_MAX_HTTP2": "100"}


# ------------------------------------------------------------- parity oracle
# A verbatim copy of the loop this function replaces (services.py:447-455 as of
# f903102b2). Same pattern as test_plugin_activation.py's LEGACY_SPECIFICS: the
# old implementation is kept as the thing the new one must agree with.


def _legacy_restore(payload, db_config, restore_skip, template_unchanged):
    from app.utils import is_editable_method

    variables = dict(payload)
    for setting, value in db_config.items():
        if setting in variables or setting in restore_skip:
            continue
        setting_method = value.get("method")
        if not is_editable_method(setting_method, allow_default=False):
            if setting_method == "default" and value.get("template") and not template_unchanged:
                continue
            variables[setting] = value["value"]
    return variables


PARITY_CASES = [
    pytest.param({}, _db(A=("1", "ui")), True, id="ui-method-cleared"),
    pytest.param({}, _db(A=("1", "api")), True, id="api-method-cleared"),
    pytest.param({}, _db(A=("1", "scheduler")), True, id="scheduler-method-restored"),
    pytest.param({}, _db(A=("1", "default")), True, id="bare-default-restored"),
    pytest.param({}, _db(A=("1", "default", "low")), True, id="template-default-kept"),
    pytest.param({}, _db(A=("1", "default", "low")), False, id="template-default-dropped"),
    pytest.param({"A": "2"}, _db(A=("1", "api")), True, id="posted-wins"),
    pytest.param({}, _db(USE_TEMPLATE=("low", "api")), True, id="restore-skip-honoured"),
    pytest.param({}, _db(A=("1", "ui"), B=("2", "api"), C=("3", "default", "high")), False, id="mixed"),
]


@pytest.mark.parametrize("payload, db_config, template_unchanged", PARITY_CASES)
def test_scope_none_matches_the_loop_it_replaces(payload, db_config, template_unchanged):
    assert restore_unowned_settings(payload, db_config, scope=None, restore_skip=RESTORE_SKIP, template_unchanged=template_unchanged) == _legacy_restore(
        payload, db_config, RESTORE_SKIP, template_unchanged
    )


def test_draft_and_identity_keys_are_never_restored():
    """restore_skip keys are the caller's responsibility, whatever the scope.

    IS_DRAFT is the sharp edge: `services.py` does `variables.pop("IS_DRAFT", "no")`, so a
    surface that omits it publishes a draft service. This test pins that the restore loop
    will NOT quietly cover for that -- the page must post these keys itself.
    """
    db_config = _db(IS_DRAFT=("yes", "ui"), SERVER_NAME=("app.example.com", "ui"), USE_TEMPLATE=("low", "ui"))
    result = restore_unowned_settings({}, db_config, scope=set(), restore_skip=RESTORE_SKIP)
    assert result == {}


# ------------------------------------------------------- preserve_suffixed (debt 2)
# Folded in from update_service's local re-injection loop, which ran BEFORE this function and
# therefore had to re-implement its template guard by hand. The guard now exists once.


def test_preserve_suffixed_keeps_an_in_scope_multi_value_row():
    """The whole reason the flag exists: the stepper renders one input per step-named key and no
    multiples cloner, so a stored REVERSE_PROXY_HOST_1 is never posted -- while `_in_scope`
    base-matches it into the scope declared for REVERSE_PROXY_HOST and would delete it."""
    db_config = _db(REVERSE_PROXY_HOST_1=("http://app:8080", "ui"))
    result = restore_unowned_settings({}, db_config, scope={"REVERSE_PROXY_HOST"}, restore_skip=RESTORE_SKIP, preserve_suffixed=True)
    assert result == {"REVERSE_PROXY_HOST_1": "http://app:8080"}


def test_preserve_suffixed_defaults_off_so_an_in_scope_suffix_still_clears():
    """Tying the flag to the surface is the point: the per-plugin page DOES render the cloner, so
    defaulting it on would make clearing a multi-value entry impossible everywhere."""
    db_config = _db(REVERSE_PROXY_HOST_1=("http://app:8080", "ui"))
    assert restore_unowned_settings({}, db_config, scope={"REVERSE_PROXY_HOST"}, restore_skip=RESTORE_SKIP) == {}


def test_preserve_suffixed_does_not_touch_base_names():
    """Narrow by design -- only `_<digits>` keys. A legitimate clear of a step-named setting must
    still go through, or the stepper could never turn anything off."""
    db_config = _db(REVERSE_PROXY_HOST=("http://app:8080", "ui"))
    assert restore_unowned_settings({}, db_config, scope={"REVERSE_PROXY_HOST"}, restore_skip=RESTORE_SKIP, preserve_suffixed=True) == {}


def test_the_template_guard_still_wins_over_preserve_suffixed():
    """Ordering, and it is the whole reason the fold is worth doing: carrying an outgoing
    template's default across a USE_TEMPLATE switch makes config_save materialise it as a real
    ui-method row, permanently detaching it from the template it came from. Placing the new
    branch above the guard would silently defeat it -- which is exactly the coupling the local
    loop in services.py had to re-implement by hand."""
    db_config = _db(REVERSE_PROXY_HOST_1=("http://old-template:80", "default", "low"))
    result = restore_unowned_settings({}, db_config, scope={"REVERSE_PROXY_HOST"}, restore_skip=RESTORE_SKIP, template_unchanged=False, preserve_suffixed=True)
    assert result == {}


def test_a_suffixed_default_from_a_template_survives_when_the_template_is_unchanged():
    """The control half of the guard: only a template SWITCH drops it."""
    db_config = _db(REVERSE_PROXY_HOST_1=("http://app:80", "default", "low"))
    result = restore_unowned_settings({}, db_config, scope={"REVERSE_PROXY_HOST"}, restore_skip=RESTORE_SKIP, preserve_suffixed=True)
    assert result == {"REVERSE_PROXY_HOST_1": "http://app:80"}


def test_restore_skip_still_wins_over_preserve_suffixed():
    """`restore_skip` is now consulted where the local loop never consulted it. Unreachable with
    the shipped manifests (see the next test), so this pins the defensive contract rather than a
    live behaviour: a form-managed key stays the form's responsibility."""
    db_config = _db(SERVER_NAME_1=("app.example.com", "ui"))
    assert restore_unowned_settings({}, db_config, scope=set(), restore_skip={"SERVER_NAME_1"}, preserve_suffixed=True) == {}


def test_no_restore_skip_name_is_a_multiple_setting():
    """Why the `restore_skip` difference above is unreachable in practice, checked against what
    actually ships rather than asserted in a comment. A `multiple` setting is the only way a
    stored `<name>_<digits>` row exists, so if no skipped name is `multiple`, the fold cannot
    change behaviour. This is a property of the manifests, NOT of the code -- nothing enforces
    it, which is why it is a test."""
    declared = json.loads((REPO_ROOT / "src" / "common" / "settings.json").read_text(encoding="utf-8"))
    for data in REAL_PLUGINS.values():
        declared.update(data.get("settings") or {})

    skipped = get_blacklisted_settings() | set(control_keys()) | get_blacklisted_settings(True) | set(control_keys(True))
    multiples = sorted(name for name in skipped if (declared.get(name) or {}).get("multiple"))
    assert multiples == [], f"a skipped key is multi-valued, so the preserve_suffixed fold DOES change behaviour: {multiples}"


def _legacy_suffixed_reinjection(payload, db_config, template_unchanged):
    """Verbatim copy of routes/services.py:660-672 as of e78f065b7, the loop the fold replaces."""
    from regex import search

    variables = dict(payload)
    switching_template = not template_unchanged
    for setting, value in db_config.items():
        base = setting.rsplit("_", 1)[0] if search(r"_\d+$", setting) else setting
        if setting in variables or base == setting:
            continue
        if switching_template and value.get("method") == "default" and value.get("template"):
            continue
        variables[setting] = value["value"]
    return variables


SUFFIXED_PARITY_CASES = [
    pytest.param(_db(A_1=("1", "ui")), True, id="ui-suffix-kept"),
    pytest.param(_db(A_1=("1", "scheduler")), True, id="scheduler-suffix-kept"),
    pytest.param(_db(A_1=("1", "default", "low")), True, id="template-suffix-kept"),
    pytest.param(_db(A_1=("1", "default", "low")), False, id="template-suffix-dropped-on-switch"),
    pytest.param(_db(A_1=("1", "default")), False, id="bare-default-suffix-kept-on-switch"),
    pytest.param(_db(A=("1", "ui"), A_1=("2", "ui"), A_10=("3", "ui")), True, id="base-untouched-multi-digit"),
]


@pytest.mark.parametrize("db_config, template_unchanged", SUFFIXED_PARITY_CASES)
def test_the_fold_matches_the_loop_it_replaces(db_config, template_unchanged):
    """Equivalent-refactor is exactly the claim that hides a regression, so it is checked against
    the old code rather than asserted. Scope {A} on purpose: it base-matches every suffix, which
    is the condition under which the two implementations could disagree."""
    folded = restore_unowned_settings({}, db_config, scope={"A"}, restore_skip=RESTORE_SKIP, template_unchanged=template_unchanged, preserve_suffixed=True)
    legacy = _legacy_suffixed_reinjection({}, db_config, template_unchanged)
    # The legacy loop ran *before* the restore, so its output is the payload the restore then saw.
    expected = restore_unowned_settings(legacy, db_config, scope={"A"}, restore_skip=RESTORE_SKIP, template_unchanged=template_unchanged)
    assert folded == expected


# ------------------------------------------------------------------ control keys
# `restore_skip` keys are NEVER restored, so each one is destroyed by omission. The two pages
# need different lists and a shared partial emitting one would be wrong on both.


def test_the_service_page_posts_the_five_keys_that_destroy_themselves_by_omission():
    assert control_keys() == ("SERVER_NAME", "OLD_SERVER_NAME", "IS_DRAFT", "USE_TEMPLATE", "USE_UI")


def test_the_global_page_gets_a_different_list():
    """Not a shared list. `get_blacklisted_settings(True)` adds SERVER_NAME/USE_TEMPLATE and has
    NO USE_UI and NO OLD_SERVER_NAME, and the global page has no draft state -- so emitting the
    service list here would post SERVER_NAME, which at global scope IS the service list."""
    assert control_keys(True) != control_keys()
    assert "SERVER_NAME" not in control_keys(True)


def test_the_service_restore_skip_is_unchanged_by_being_derived():
    """`get_blacklisted_settings() | control_keys()` must still be the historical names, or
    deriving it moved the goalposts instead of removing a duplicate.

    SERVICE_MODE is the one deliberate addition (2026-08-24, PRO quota chantier). It decides
    whether a service is billable, so it must not be a knob on the generic per-plugin form --
    same reason IS_DRAFT is here. It is NOT yet in `control_keys()`, which means an ordinary
    service save drops a SERVICE_MODE row that env or the API had set. That hazard is known,
    accepted and pinned in `tests/unit/ui/test_quota_count.py`: it is money-inert while the
    exemption is gated off (a dropped row reverts the service to standard, i.e. billable, i.e.
    fail closed). **Lot C must add SERVICE_MODE to `_SERVICE_CONTROL_KEYS` and render its hidden
    input in the same change that opens the gate.**
    """
    assert get_blacklisted_settings() | set(control_keys()) == {
        "IS_LOADING",
        "AUTOCONF_MODE",
        "SWARM_MODE",
        "KUBERNETES_MODE",
        "IS_DRAFT",
        "SERVICE_MODE",
        "BUNKERWEB_INSTANCES",
        "DATABASE_URI",
        "DATABASE_URI_READONLY",
        "SERVER_NAME",
        "OLD_SERVER_NAME",
        "USE_TEMPLATE",
        "USE_UI",
    }


def test_the_global_restore_skip_is_unchanged_by_being_derived():
    assert get_blacklisted_settings(True) | set(control_keys(True)) == get_blacklisted_settings(True)


def test_the_route_really_skips_the_control_keys_it_declares():
    """The list being right says nothing about `update_service` using it. With the control keys
    missing from `restore_skip`, every one of them starts being restored from storage instead of
    posted -- which silently masks the omission the shelf must not make, and hands `edit_service`
    a stale SERVER_NAME on a rename. Out of scope on purpose: that is the branch that restores
    regardless of method, so it is the one the skip set has to beat."""
    stored = {
        "SERVER_NAME": {"value": "app.example.com", "method": "scheduler", "global": False},
        "USE_TEMPLATE": {"value": "low", "method": "scheduler", "global": False},
        "USE_UI": {"value": "yes", "method": "scheduler", "global": False},
        "USE_ANTIBOT": {"value": "captcha", "method": "ui", "global": False},
    }
    payload = _run_update_service(
        posted={"SERVER_NAME": "app.example.com", "USE_ANTIBOT": "no"},
        db_config=stored,
        scope={"USE_ANTIBOT"},
    )
    assert "USE_TEMPLATE" not in payload, "a control key must be posted by the page, never restored behind its back"
    assert "USE_UI" not in payload
    assert payload["USE_ANTIBOT"] == "no", "...while an ordinary out-of-scope row is still protected"


# --------------------------------------------- omitting the name pair loses the save
# Nothing tested this, and it is the sharpest edge in the control-key list: it does not flash, it
# does not fail the save loudly -- it raises inside CONFIG_TASKS_EXECUTOR, so DATA["RELOADING"]
# is never cleared and the loading page spins forever.


def _config_stub():
    """Enough of `Config` for `edit_service` to reach the line that crashes."""
    return SimpleNamespace(get_services=lambda **kwargs: [], get_config=lambda **kwargs: {}, gen_conf=lambda *args, **kwargs: "ok")


def test_edit_service_raises_indexerror_when_the_server_name_is_empty():
    """models/config.py:375 -- `changed_service=server_name_splitted[0]` on `"".split() == []`."""
    with pytest.raises(IndexError):
        Config.edit_service(_config_stub(), "", {"SERVER_NAME": ""})


def test_a_payload_omitting_both_name_keys_reaches_that_crash():
    """The chain the control keys exist to break: SERVER_NAME is in `restore_skip` so it is never
    restored; update_service then falls back to `old_server_name`, which is "" when
    OLD_SERVER_NAME is absent too (services.py:586, :750-755)."""
    assert "SERVER_NAME" in control_keys() and "OLD_SERVER_NAME" in control_keys()
    with pytest.raises(IndexError):
        _run_update_service(posted={"USE_ANTIBOT": "no"}, edit_service=partial(Config.edit_service, _config_stub()))


def test_the_same_payload_is_fine_once_the_shelf_posts_server_name():
    """The control half. Without it the test above passes against a route that crashes on EVERY
    save, which would say nothing about the control keys at all."""
    payload = _run_update_service(
        posted={"SERVER_NAME": "app.example.com", "OLD_SERVER_NAME": "app.example.com", "USE_ANTIBOT": "no"},
        edit_service=partial(Config.edit_service, _config_stub()),
    )
    assert payload["SERVER_NAME"] == "app.example.com"


class _FakeData(dict):
    def load_from_file(self):
        return None


_SERVICE_STORED = {
    "SERVER_NAME": {"value": "app.example.com", "method": "ui", "global": False},
    "USE_ANTIBOT": {"value": "captcha", "method": "ui", "global": False},
    "USE_LIMIT_REQ": {"value": "no", "method": "ui", "global": False},
    "USE_LIMIT_CONN": {"value": "no", "method": "ui", "global": False},
    "REDIRECT_TO_1": {"value": "https://elsewhere.example.com", "method": "ui", "global": False},
    "X_FRAME_OPTIONS": {"value": "DENY", "method": "ui", "global": False},
}


def _run_update_service(*, posted, db_config=None, scope=None, mode="compose", edit_service=None, module=None):
    """Drive the real `update_service` and return the payload handed to `edit_service`."""
    module = module or _services
    api = Mock()
    api.get_service.return_value = _SERVICE_STORED if db_config is None else db_config
    api.get_configs.return_value = []
    api.get_templates.return_value = {}
    bw_config = Mock()
    bw_config.check_variables.side_effect = lambda variables, *args, **kwargs: variables
    if edit_service is None:
        bw_config.edit_service.return_value = ("Configuration saved", None)
    else:
        bw_config.edit_service.side_effect = edit_service
    with patch.object(module, "API_CLIENT", api), patch.object(module, "BW_CONFIG", bw_config), patch.object(
        module, "DATA", _FakeData(TO_FLASH=[])
    ), patch.object(module, "wait_applying", lambda: None):
        module.update_service("app.example.com", dict(posted), False, mode, "", {}, scope=scope)
    assert bw_config.edit_service.called, "update_service returned early -- nothing reached the save, so this test proves nothing"
    return bw_config.edit_service.call_args[0][1]


# ------------------------------------------------------------------ mode resolution
# `mode` is a client-controlled query argument synced by history.pushState, not a route segment.


@pytest.mark.parametrize("requested", ["easy", "advanced", "raw", "compose"])
def test_a_rendered_pane_saves_as_itself(requested):
    assert resolve_save_mode(requested, "easy") == requested


@pytest.mark.parametrize("requested", ["", "wat", None, "RAW", "raw ", "template"])
def test_anything_the_page_does_not_render_falls_back_to_that_page_default(requested):
    """The fallback is the page's own GET default, so an unrecognised mode saves the way the pane
    the user is actually looking at posts. Pairing a rendered pane with another pane's save
    contract is measured in deleted rows (db_methods/config_save.py:592) -- `template` is in this
    list because it is not a pane of either page: routes/services.py's template page passes its
    mode literally and never routes through here."""
    assert resolve_save_mode(requested, "easy") == "easy"
    assert resolve_save_mode(requested, "advanced") == "advanced"


# ------------------------------------------------------------------- the shelf scope
# Derived from what the shelf RENDERS AS AN ENABLED, POSTABLE CONTROL -- never from the
# activation map. Scope must be a subset of Posted: over-claiming deletes, under-claiming only
# preserves.


def test_a_multi_key_plugin_puts_every_declared_key_in_scope():
    """limit declares three `check` keys, every one defaulting to "yes". "ON writes the first key"
    is only safe if the siblings are OUT of scope -- and OFF needs them IN, so the row must post
    all of them and own all of them. Returning only the first would leave the others in scope,
    unposted, deleted, and falling back to their "yes" default: the connection limiter turns itself
    ON from an operator turning the plugin off.

    Asserted against the map DERIVED FROM THE SHIPPED MANIFEST rather than a literal, so adding a
    fourth activation key to `limit` extends the scope instead of failing here -- but the
    three-way `>=` still pins that none of the three may silently leave."""
    declared = REAL_ACTIVATION_MAP["limit"]
    assert set(declared) >= {"USE_LIMIT_REQ", "USE_LIMIT_CONN", "USE_LIMIT_REQ_GLOBAL"}, "fixture premise"
    assert set(declared.values()) == {"no"}, "fixture premise: every inactive value is 'no'"
    keys = shelf_plugin_scope(
        "limit", REAL_PLUGINS["limit"], _SERVICE_STORED, global_page=False, is_pro_version=False, blacklisted=set(), activation_map=REAL_ACTIVATION_MAP
    )
    assert keys == set(declared)


def test_a_multiselect_activation_key_is_never_in_scope():
    """country's BLACKLIST_COUNTRY/WHITELIST_COUNTRY are `type: multiselect`, so the row gets a
    count and a chevron and posts nothing at all. In scope would delete BOTH rows."""
    assert REAL_PLUGINS["country"]["settings"]["BLACKLIST_COUNTRY"]["type"] == "multiselect", "fixture premise"
    scope = _shelf_scope(_SERVICE_STORED)
    assert "BLACKLIST_COUNTRY" not in scope and "WHITELIST_COUNTRY" not in scope


def test_a_multiple_activation_key_is_never_in_scope_and_its_suffixes_survive():
    """REDIRECT_TO is `"multiple": "redirect"` AND redirect's declared activation key. `_in_scope`
    base-matches, so claiming it drags every stored REDIRECT_TO_<n> into scope for a control that
    posts none of them. End-to-end, not just as a set membership."""
    assert REAL_PLUGINS["redirect"]["settings"]["REDIRECT_TO"]["multiple"], "fixture premise"
    scope = _shelf_scope(_SERVICE_STORED)
    assert "REDIRECT_TO" not in scope

    payload = _run_update_service(posted={"SERVER_NAME": "app.example.com", "USE_ANTIBOT": "no"}, scope=scope)
    assert payload["REDIRECT_TO_1"] == "https://elsewhere.example.com"


def test_no_key_in_the_shelf_scope_is_a_multi_value_setting():
    """The property that lets the compose save run with preserve_suffixed=False. Checked over
    every shipped manifest rather than over the two plugins that happen to break it today."""
    scope = _shelf_scope(_SERVICE_STORED) | _shelf_scope(_SERVICE_STORED, global_page=True)
    declared = {}
    for data in REAL_PLUGINS.values():
        declared.update(data.get("settings") or {})
    assert [key for key in sorted(scope) if (declared.get(key) or {}).get("multiple")] == []


def test_an_always_on_plugin_owns_nothing():
    """`extensions.activation: "always"` renders the words "Always on", no switch, no post."""
    assert REAL_ACTIVATION_MAP["ssl"] == "always", "fixture premise"
    assert (
        shelf_plugin_scope("ssl", REAL_PLUGINS["ssl"], {}, global_page=False, is_pro_version=False, blacklisted=set(), activation_map=REAL_ACTIVATION_MAP)
        == set()
    )


def test_the_synthesized_general_plugin_owns_nothing():
    """`general` has no plugin.json and is always on, so SERVER_NAME and friends can never enter
    the shelf's scope through it."""
    general = {"id": "general", "name": "General", "type": "core", "stream": "yes", "settings": {"USE_GENERAL": {"context": "multisite", "type": "check"}}}
    assert shelf_plugin_scope("general", general, {}, global_page=False, is_pro_version=False, blacklisted=set(), activation_map={}) == set()


def test_a_plugin_with_no_multisite_setting_owns_nothing_on_a_service_page():
    """`backup`'s only activation key is `global` context, so the settings-driven loop renders no
    row for it on a service page -- and models/config.py:61 would drop the key from a service
    payload anyway. It IS in scope at global scope."""
    assert REAL_PLUGINS["backup"]["settings"]["USE_BACKUP"]["context"] == "global", "fixture premise"
    assert "USE_BACKUP" not in _shelf_scope(_SERVICE_STORED)
    assert "USE_BACKUP" in _shelf_scope({}, global_page=True)


def test_a_resource_only_plugin_owns_nothing():
    """`workflows` declares no activation manifest and no USE_<ID>/USE_<NAME> setting, so tier 3
    finds nothing to render a control from."""
    assert "workflows" not in REAL_ACTIVATION_MAP, "fixture premise"
    assert (
        shelf_plugin_scope(
            "workflows", REAL_PLUGINS["workflows"], {}, global_page=False, is_pro_version=False, blacklisted=set(), activation_map=REAL_ACTIVATION_MAP
        )
        == set()
    )


def test_the_tier_three_naming_convention_still_produces_a_switch():
    """Tier 3 is load-bearing -- 30 core plugins and every third-party plugin rely on it. Losing
    it silently gives those rows no switch at all."""
    scope = _shelf_scope(_SERVICE_STORED)
    assert "badbehavior" not in REAL_ACTIVATION_MAP, "fixture premise: badbehavior declares no manifest"
    assert "USE_BAD_BEHAVIOR" in scope, "USE_<NAME> -- the plugin id is `badbehavior`, the setting is not USE_BADBEHAVIOR"
    assert "USE_MTLS" in scope, "USE_<ID>"
    assert "USE_UI" in scope, "ui's tier-3 key is a control key AND a shelf switch at once"


def test_an_http_only_plugin_is_out_of_scope_on_a_stream_service():
    """Disabling the control for a stream-incompatible plugin is a SAVE change, not a display
    change: a disabled input posts nothing. `plugin_data['stream']` has three values and only the
    literal "no" is excluded."""
    assert REAL_PLUGINS["antibot"]["stream"] == "no" and REAL_PLUGINS["limit"]["stream"] == "partial", "fixture premise"
    stream_config = _SERVICE_STORED | {"SERVER_TYPE": {"value": "stream", "method": "ui", "global": False}}
    scope = _shelf_scope(stream_config)
    assert "USE_ANTIBOT" not in scope
    assert "USE_LIMIT_REQ" in scope, "`partial` is not `no` -- excluding it would drop a working control"
    assert "USE_ANTIBOT" in _shelf_scope(_SERVICE_STORED), "the control half: an http service keeps it"


def test_a_pro_plugin_without_a_licence_is_out_of_scope():
    """Every field renders disabled, so the form posts nothing for it."""
    pro = {"id": "waf_extra", "name": "WAF Extra", "type": "pro", "stream": "yes", "settings": {"USE_WAF_EXTRA": {"context": "multisite", "type": "check"}}}
    common = dict(global_page=False, blacklisted=set(), activation_map={})
    assert shelf_plugin_scope("waf_extra", pro, {}, is_pro_version=False, **common) == set()
    assert shelf_plugin_scope("waf_extra", pro, {}, is_pro_version=True, **common) == {"USE_WAF_EXTRA"}


def test_a_non_ui_editable_stored_method_is_out_of_scope():
    """The same disabled formula plugin_settings_body.html:20 uses. A scheduler-owned row renders
    a disabled control, which posts nothing."""
    plugin = {"id": "p", "name": "P", "type": "core", "stream": "yes", "settings": {"USE_P": {"context": "multisite", "type": "check"}}}
    common = dict(global_page=False, is_pro_version=False, blacklisted=set(), activation_map={})
    assert shelf_plugin_scope("p", plugin, {"USE_P": {"value": "yes", "method": "scheduler"}}, **common) == set()
    assert shelf_plugin_scope("p", plugin, {"USE_P": {"value": "yes", "method": "ui"}}, **common) == {"USE_P"}


def test_a_service_may_override_a_non_editable_global():
    """On a service page `entry["global"]` flips the verdict: an inherited scheduler-owned global
    is still overridable locally, so its control renders enabled and DOES post."""
    plugin = {"id": "p", "name": "P", "type": "core", "stream": "yes", "settings": {"USE_P": {"context": "multisite", "type": "check"}}}
    entry = {"USE_P": {"value": "yes", "method": "scheduler", "global": True}}
    common = dict(is_pro_version=False, blacklisted=set(), activation_map={})
    assert shelf_plugin_scope("p", plugin, entry, global_page=False, **common) == {"USE_P"}
    assert shelf_plugin_scope("p", plugin, entry, global_page=True, **common) == set(), "at global scope there is nothing to override"


def test_a_blacklisted_activation_key_is_out_of_scope():
    plugin = {"id": "p", "name": "P", "type": "core", "stream": "yes", "settings": {"USE_P": {"context": "multisite", "type": "check"}}}
    common = dict(global_page=False, is_pro_version=False, activation_map={})
    assert shelf_plugin_scope("p", plugin, {}, blacklisted={"USE_P"}, **common) == set()
    assert shelf_plugin_scope("p", plugin, {}, blacklisted=set(), **common) == {"USE_P"}


def test_a_readonly_page_owns_nothing_at_all():
    """A read-only page disables every control but still renders a valid csrf_token, so the POST
    is accepted and posts nothing. In scope would mean DELETE -- at global scope that wipes a
    plugin's whole configuration, one plugin per POST."""
    assert _shelf_scope(_SERVICE_STORED) != set(), "fixture premise"
    assert _shelf_scope(_SERVICE_STORED, is_readonly=True) == set()
    assert _shelf_scope({}, global_page=True, is_readonly=True) == set()


def test_the_default_activation_map_is_the_real_one():
    """The `activation_map=None` path, which is what production takes. Without this every test
    above could pass against a function that ignores its default and reads nothing."""
    scope = postable_shelf_scope(REAL_PLUGINS, _SERVICE_STORED, global_page=False, is_pro_version=False, blacklisted=get_blacklisted_settings())
    assert {"USE_LIMIT_REQ", "USE_LIMIT_CONN"} <= scope
    assert "REDIRECT_TO" not in scope and "BLACKLIST_COUNTRY" not in scope


# ---------------------------------------------------- the shared is_readonly helper
# Both POST handlers recomputed this independently; S3.4 would have added a third and fourth
# copy. The helper is in app/utils.py, not in a route module, because it must stay importable in
# a bare checkout (importing app.dependencies executes the eager Config() singleton).


def _with_permissions(*permissions):
    return patch("app.utils.current_user", SimpleNamespace(list_permissions=list(permissions)))


def test_is_readonly_request_needs_both_terms():
    """Dropping either term silently re-enables a scope the page could not post."""
    with _with_permissions("read", "write"):
        assert is_readonly_request(False) is False
        assert is_readonly_request(True) is True, "the API's own readonly state must still count"
    with _with_permissions("read"):
        assert is_readonly_request(False) is True, "a user without write must still count"


def test_is_readonly_request_treats_a_missing_permission_list_as_readonly():
    """`list_permissions` is set to an empty set when the permission load fails mid-request, and
    the anonymous user has no such attribute at all -- both must read as read-only."""
    with patch("app.utils.current_user", SimpleNamespace()):
        assert is_readonly_request(False) is True


# ------------------------------------------------------------------- route wiring
# The scope SET is only half of the contract: nothing here drove the real route before, so
# `scope=scope` could become `scope=None` at the submit and every test above stayed green while
# the save deleted every row the shelf did not post.


@pytest.fixture
def service_route_app():
    app = Flask(__name__)
    app.secret_key = "test"
    app.register_blueprint(_services.services)
    app.add_url_rule("/loading", "loading", lambda: "")
    return app


def _post_service_page(app, monkeypatch, *, service="app.example.com", query="", form=None, permissions=("read", "write"), module=None):
    module = module or _services
    api = Mock()
    api.readonly = False
    api.get_service.return_value = _SERVICE_STORED
    api.get_metadata.return_value = {"is_pro": False}
    bw_config = Mock()
    bw_config.get_config.return_value = {"SERVER_NAME": "app.example.com"}
    bw_config.get_plugins.return_value = REAL_PLUGINS
    executor = Mock()
    monkeypatch.setattr(module, "API_CLIENT", api)
    monkeypatch.setattr(module, "BW_CONFIG", bw_config)
    monkeypatch.setattr(module, "CONFIG_TASKS_EXECUTOR", executor)
    monkeypatch.setattr(module, "DATA", _FakeData(TO_FLASH=[]))
    data = {"csrf_token": "x"} | (form or {})
    with app.test_request_context(f"/services/{service}{query}", method="POST", data=data), _with_permissions(*permissions):
        module.services_service_page.__wrapped__(service)
    assert executor.submit.called, "the route returned before submitting -- this test proves nothing"
    return executor.submit.call_args, api


def test_the_compose_shelf_declares_a_scope(service_route_app, monkeypatch):
    call, _ = _post_service_page(service_route_app, monkeypatch, query="?mode=compose", form={"SERVER_NAME": "app.example.com"})
    assert call.args[4] == "compose"
    assert call.kwargs["scope"] is not None
    assert {"USE_LIMIT_REQ", "USE_LIMIT_CONN"} <= call.kwargs["scope"]


def test_a_bare_post_still_saves_as_easy_with_no_scope(service_route_app, monkeypatch):
    """The easy pane's own save strips `?mode=` (static/js/plugins-settings.js:577-580), so a bare
    POST IS an easy-pane POST -- and easy is still this page's default pane
    (services.py:1130, service_settings.html:37-39). Handing it a declared scope would give the
    stepper authority to delete every activation key no step of the template names; see the
    end-to-end test below. Revisit at T7/T8, when compose replaces easy as the default."""
    call, _ = _post_service_page(service_route_app, monkeypatch, form={"SERVER_NAME": "app.example.com"})
    assert call.args[4] == "easy"
    assert call.kwargs["scope"] is None


def test_an_easy_pane_payload_does_not_delete_what_the_stepper_never_posts(service_route_app, monkeypatch):
    """The regression in full, route gate included: take the mode and scope the route ACTUALLY
    submits for a bare POST, drive the real `update_service` with an easy-pane-shaped payload
    (USE_TEMPLATE plus step-named keys only), and require the stored ui-method rows the stepper
    cannot post to reach `edit_service` anyway.

    Against a route that resolves a bare POST to compose this fails on USE_BROTLI: the shelf scope
    holds it, the stepper never posts it, and in-scope-and-unposted means the row is deleted."""
    stored = _SERVICE_STORED | {
        "USE_BROTLI": {"value": "yes", "method": "ui", "global": False},
        "USE_TEMPLATE": {"value": "low", "method": "ui", "global": False},
    }
    call, _ = _post_service_page(service_route_app, monkeypatch, form={"SERVER_NAME": "app.example.com"})
    payload = _run_update_service(
        posted={"SERVER_NAME": "app.example.com", "OLD_SERVER_NAME": "app.example.com", "USE_TEMPLATE": "low", "USE_REVERSE_PROXY": "no"},
        db_config=stored,
        mode=call.args[4],
        scope=call.kwargs["scope"],
    )
    assert payload["USE_BROTLI"] == "yes"
    assert payload["USE_ANTIBOT"] == "captcha"


def test_raw_still_claims_the_whole_config(service_route_app, monkeypatch):
    """Raw posts every key, so it is the one surface for which `scope=None` is correct."""
    call, _ = _post_service_page(service_route_app, monkeypatch, query="?mode=raw", form={"SERVER_NAME": "app.example.com"})
    assert call.args[4] == "raw"
    assert call.kwargs["scope"] is None


def test_a_readonly_user_gets_an_empty_scope_from_the_route(service_route_app, monkeypatch):
    """The route WIRING for is_readonly. `postable_scope`'s own version of this gap already
    produced one Critical: the predicate being unit-tested says nothing about the route using it."""
    call, _ = _post_service_page(service_route_app, monkeypatch, query="?mode=compose", permissions=("read",), form={"SERVER_NAME": "app.example.com"})
    assert call.kwargs["scope"] == set()


def test_a_new_service_declares_no_scope(service_route_app, monkeypatch):
    """`update_service` skips the restore for "new" and its db_config is the GLOBAL config, so
    there is nothing to protect and nothing to claim."""
    call, api = _post_service_page(service_route_app, monkeypatch, service="new", query="?mode=compose", form={"SERVER_NAME": "new.example.com"})
    assert call.kwargs["scope"] is None
    assert not api.get_service.called, "a new service has no stored config to derive a scope from"


def test_the_template_page_still_preserves_suffixed_rows_end_to_end():
    """The fold moved this from services.py into save_scope.py; the template page's behaviour must
    not have moved with it. Scope names the base, the stepper posts no suffix, the row survives."""
    stored = {
        "SERVER_NAME": {"value": "app.example.com", "method": "ui", "global": False},
        "REVERSE_PROXY_HOST": {"value": "http://app:80", "method": "ui", "global": False},
        "REVERSE_PROXY_HOST_1": {"value": "http://other:80", "method": "ui", "global": False},
    }
    payload = _run_update_service(
        posted={"SERVER_NAME": "app.example.com", "REVERSE_PROXY_HOST": "http://changed:80"},
        db_config=stored,
        scope={"REVERSE_PROXY_HOST"},
        mode="template",
    )
    assert payload["REVERSE_PROXY_HOST_1"] == "http://other:80"
    assert payload["REVERSE_PROXY_HOST"] == "http://changed:80", "...without freezing the key the stepper DOES post"


def test_a_compose_save_does_not_preserve_suffixed_rows_by_accident():
    """The flag is tied to the surface. Compose keeps `multiple` keys out of scope instead, so a
    suffixed row survives on the out-of-scope path -- and a compose save must NOT quietly become a
    surface on which a multi-value entry can never be cleared."""
    stored = {
        "SERVER_NAME": {"value": "app.example.com", "method": "ui", "global": False},
        "REVERSE_PROXY_HOST_1": {"value": "http://other:80", "method": "ui", "global": False},
    }
    payload = _run_update_service(
        posted={"SERVER_NAME": "app.example.com", "USE_ANTIBOT": "no"},
        db_config=stored,
        scope={"REVERSE_PROXY_HOST"},
        mode="compose",
    )
    assert "REVERSE_PROXY_HOST_1" not in payload


# ------------------------------------------------- USE_TEMPLATE as an ORDERED LIST
# `templates_unchanged` is deliberately an EXACT ORDERED comparison. Every "smarter"
# variant (set/subset, "layers were only added", per-key membership) restores an
# outgoing layer's value as a real ui-method row and permanently defeats the layer the
# user just added. These tests exist to make that regression impossible to land quietly.


@pytest.mark.parametrize(
    "old,new",
    [
        ("low", "low"),
        ("", ""),
        ("low high", "low high"),
        # whitespace only: same layer list, so NOT a change
        ("low  high", "low high"),
        (" low high ", "low high"),
    ],
)
def test_templates_unchanged_true_for_the_same_layer_list(old, new):
    assert templates_unchanged(old, new) is True


def test_only_the_literal_separator_splits_a_layer_list():
    """A tab is NOT a separator -- the storage contract (common_utils.normalize_list_value) only
    ever splits on " ", so "low\thigh" is one (bogus) template id, not two layers. Pinned
    because Jinja's bare `.split()` and a naive JS whitespace regex both disagree with that, and both
    render the picker's chips: the three halves must not disagree about what a layer is."""
    assert templates_unchanged("low\thigh", "low high") is False
    assert templates_unchanged("low\thigh", "low\thigh") is True


@pytest.mark.parametrize(
    "old,new,why",
    [
        ("low", "low high", "a layer was ADDED -- the case the feature exists for"),
        ("low high", "low", "a layer was removed"),
        ("low high", "high low", "same layers, REORDERED -- different effective values"),
        ("", "low", "first layer attached"),
        ("low", "", "last layer detached"),
        ("low high", "low medium high", "a layer was inserted in the middle"),
        ("low", "low low", "a repeat changes the stored list even though the merge is idempotent"),
    ],
)
def test_templates_unchanged_false_for_any_list_change(old, new, why):
    assert templates_unchanged(old, new) is False, why


def test_adding_a_layer_drops_the_outgoing_overlay_rather_than_freezing_it():
    """THE regression this whole comparison exists to prevent.

    A service on "low" gains a second layer. `low`'s overlay-provided SSL_PROTOCOLS must NOT be
    restored into the payload: restoring it writes a real ui-method row carrying `low`'s value,
    which then beats the layer the user just added -- forever, and silently. Dropping it costs
    nothing, because the overlay re-derives the merged value on the next read.
    """
    db_config = _db(SSL_PROTOCOLS=("TLSv1.2 TLSv1.3", "default", "low"))
    unchanged = templates_unchanged("low", "low high")
    assert unchanged is False
    result = restore_unowned_settings({}, db_config, restore_skip=RESTORE_SKIP, template_unchanged=unchanged)
    assert result == {}


def test_reordering_layers_also_drops_the_overlay():
    """Reordering changes which layer wins, so the stored defaults are just as stale as after
    an add -- a set-based comparison would call this "unchanged" and freeze them."""
    db_config = _db(SSL_PROTOCOLS=("TLSv1.2 TLSv1.3", "default", "low"))
    result = restore_unowned_settings({}, db_config, restore_skip=RESTORE_SKIP, template_unchanged=templates_unchanged("low high", "high low"))
    assert result == {}


def test_a_still_attached_layers_overlay_is_also_dropped_and_that_is_correct():
    """Pins the deliberate bluntness: `low` is STILL attached, yet its overlay key is dropped.

    That is safe and intended -- the value is re-derived from the merged overlay on the next
    read. A "keep the layers that are still attached" refinement is exactly the change that
    reintroduces the freeze, because the merged default for that key may now come from `high`.
    """
    db_config = _db(SSL_PROTOCOLS=("TLSv1.2 TLSv1.3", "default", "low"))
    result = restore_unowned_settings({}, db_config, restore_skip=RESTORE_SKIP, template_unchanged=templates_unchanged("low", "low high"))
    assert result == {}


def test_whitespace_only_edit_still_restores_the_overlay():
    """The one thing canonicalisation buys: a save that only reformats the value is not a
    template change, so nothing is needlessly dropped."""
    db_config = _db(SSL_PROTOCOLS=("TLSv1.2 TLSv1.3", "default", "low"))
    result = restore_unowned_settings({}, db_config, restore_skip=RESTORE_SKIP, template_unchanged=templates_unchanged("low  high", "low high"))
    assert result == {"SSL_PROTOCOLS": "TLSv1.2 TLSv1.3"}


def test_single_template_behaviour_is_unchanged():
    """THE ACCEPTANCE BAR: the pre-list behaviour of every one-template install."""
    db_config = _db(SSL_PROTOCOLS=("TLSv1.2 TLSv1.3", "default", "low"))
    # same template -> restored, exactly as before
    assert restore_unowned_settings({}, db_config, restore_skip=RESTORE_SKIP, template_unchanged=templates_unchanged("low", "low")) == {
        "SSL_PROTOCOLS": "TLSv1.2 TLSv1.3"
    }
    # switched template -> dropped, exactly as before
    assert restore_unowned_settings({}, db_config, restore_skip=RESTORE_SKIP, template_unchanged=templates_unchanged("low", "high")) == {}
