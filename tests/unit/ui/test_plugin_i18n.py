"""The plugin i18n extension point (wave 20, lane PX-I18N).

A plugin drops `ui/blueprints/static/locales/<lang>.json` (12 of the 13 PRO plugins — the ones with
a Flask blueprint) or `ui/static/locales/<lang>.json` (`alerting`, which has none) next to its
`plugin.json` — both are layouts PRO already ships for the now-deleted
`window.BunkerWebExtraI18nPath` hook — and its keys are merged into `window.BW_I18N` and resolved by
`_()`, with no `plugin.json` declaration and no build step. See
`.cache/wave20-2026-09-21/report-PX-I18N.md` for the design.
"""

import ast
import os
import sys
from json import dumps, loads
from pathlib import Path
from types import SimpleNamespace

import pytest
from jinja2 import ChoiceLoader, DictLoader, Environment, FileSystemLoader

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "src" / "ui"))

import plugin_extensions  # type: ignore  # noqa: E402

import app.i18n as i18n_module  # noqa: E402
from app.i18n import browser_catalog, init_i18n, plugin_catalog_fingerprint  # noqa: E402


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dumps(data), encoding="utf-8")


def _plugin_locales(plugin_root: Path, plugin_id: str) -> Path:
    """The blueprint layout — 12 of the 13 PRO plugins."""
    return plugin_root / plugin_id / "ui" / "blueprints" / "static" / "locales"


def _plugin_locales_no_blueprint(plugin_root: Path, plugin_id: str) -> Path:
    """The `alerting` layout — no blueprint, catalog straight under `ui/static/`."""
    return plugin_root / plugin_id / "ui" / "static" / "locales"


def _merged_messages(catalog_script: str) -> dict:
    body = catalog_script.split("window.BW_I18N=", 1)[1].rsplit(";window.BW_LANG=", 1)[0]
    return loads(body)


@pytest.fixture(autouse=True)
def _reset_warned_collisions():
    """`_WARNED_COLLISIONS` is a process-lifetime dedup memo by design (see its own docstring), so
    two tests that happen to produce the same (plugin_id, offending-keys) or (plugin_id, path)
    marker would otherwise see only the FIRST test's warning — a real cross-test leak, not
    something a distinctly-named fixture per test should have to work around."""
    i18n_module._WARNED_COLLISIONS.clear()
    yield


@pytest.fixture
def core_static(tmp_path):
    """A minimal core catalog: the real 18 files aren't needed to test the merge."""
    static_dir = tmp_path / "core_static"
    _write_json(static_dir / "locales" / "en.json", {"button": {"save": "Save"}})
    _write_json(static_dir / "locales" / "fr.json", {"button": {"save": "Enregistrer"}})
    return static_dir


@pytest.fixture
def plugin_root(tmp_path, monkeypatch):
    """An external-plugin root the scanner reads instead of `/etc/bunkerweb/plugins` — and empties
    out the other two roots, so a bare checkout's absence of `/usr/share/bunkerweb/core` can't be
    mistaken for "no plugins found" passing for the wrong reason."""
    root = tmp_path / "external_plugins"
    root.mkdir()
    monkeypatch.setattr(plugin_extensions, "EXTERNAL_PLUGINS_PATH", str(root))
    monkeypatch.setattr(plugin_extensions, "CORE_PLUGINS_PATH", str(tmp_path / "no_core_plugins"))
    monkeypatch.setattr(plugin_extensions, "PRO_PLUGINS_PATH", str(tmp_path / "no_pro_plugins"))
    return root


# --------------------------------------------------------------------------------------
# (a) the browser catalog: a plugin's key for the active language, falling back to its `en`
# --------------------------------------------------------------------------------------
def test_plugin_catalog_merges_into_bw_i18n_for_the_active_language(core_static, plugin_root):
    _write_json(_plugin_locales(plugin_root, "myplugin") / "en.json", {"myplugin": {"title": "My Plugin"}})
    _write_json(_plugin_locales(plugin_root, "myplugin") / "fr.json", {"myplugin": {"title": "Mon Plugin"}})

    messages = _merged_messages(browser_catalog(str(core_static), "fr"))

    assert messages["myplugin"]["title"] == "Mon Plugin"
    assert messages["button"]["save"] == "Enregistrer"  # core untouched


def test_plugin_catalog_fingerprint_changes_when_catalogs_change(plugin_root):
    catalog = _plugin_locales(plugin_root, "myplugin") / "en.json"
    assert plugin_catalog_fingerprint() == "0"

    _write_json(catalog, {"myplugin": {"title": "My Plugin"}})
    first = plugin_catalog_fingerprint()
    assert len(first) == 12
    assert plugin_catalog_fingerprint() == first

    old_stat = catalog.stat()
    _write_json(catalog, {"myplugin": {"title": "New Value"}})
    assert catalog.stat().st_size == old_stat.st_size
    os.utime(catalog, ns=(old_stat.st_mtime_ns + 1_000_000, old_stat.st_mtime_ns + 1_000_000))
    second = plugin_catalog_fingerprint()
    assert second != first

    _write_json(_plugin_locales(plugin_root, "other") / "en.json", {"other": {"title": "Other"}})
    third = plugin_catalog_fingerprint()
    assert third != second
    (plugin_root / "other").rename(plugin_root / "removed")
    assert plugin_catalog_fingerprint() != third


def _inject_variables():
    tree = ast.parse((REPO / "src" / "ui" / "main.py").read_text(encoding="utf-8"))
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "inject_variables")
    function.decorator_list = []
    namespace = {
        "app": SimpleNamespace(config={"CONTEXT_PROCESSOR_HOOKS": [], "SCRIPTS_HOOKS": [], "STYLES_HOOKS": []}),
        "g": SimpleNamespace(_env={}),
        "plugin_catalog_fingerprint": lambda: "abcdef123456",
    }
    exec(compile(ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[])), str(REPO / "src/ui/main.py"), "exec"), namespace)
    return namespace["inject_variables"], namespace["g"]


def test_context_processor_versions_normal_and_login_catalogs():
    inject, g = _inject_variables()
    g._env = {"bw_version": "1.7.0"}
    assert inject()["i18n_catalog_version"] == "1.7.0.abcdef123456"

    g._env = {}
    assert inject()["i18n_catalog_version"] == ".abcdef123456"


def test_plugin_catalog_fingerprint_is_memoized_per_app_context(plugin_root):
    from flask import Flask

    catalog = _plugin_locales(plugin_root, "myplugin") / "en.json"
    _write_json(catalog, {"myplugin": {"title": "My Plugin"}})
    app = Flask("plugin_i18n_fingerprint_test")
    with app.app_context():
        first = plugin_catalog_fingerprint()
        catalog.write_text('{"myplugin":{"title":"New Value"}}', encoding="utf-8")
        assert plugin_catalog_fingerprint() == first


def test_base_template_uses_the_plugin_catalog_fingerprint():
    templates = REPO / "src" / "ui" / "app" / "templates"
    env = Environment(loader=ChoiceLoader([DictLoader({"child.html": '{% extends "base.html" %}'}), FileSystemLoader(templates)]))
    env.globals["url_for"] = lambda endpoint, **kwargs: f"/{endpoint}"
    html = env.get_template("child.html").render(
        theme="light",
        theme_mode="light",
        current_endpoint="test",
        script_nonce="nonce",
        style_nonce="nonce",
        bw_version="1.7.0",
        i18n_catalog_version="1.7.0.abcdef123456",
        ui_locale_code="en",
        starting=True,
        extra_scripts=[],
        extra_styles=[],
        custom_js=[],
        custom_css=[],
        supported_languages={},
        language="en",
        is_readonly=False,
        user_readonly=False,
        user_admin=False,
        db_readonly=False,
    )
    assert "?v=1.7.0.abcdef123456" in html


def test_a_plugin_without_the_active_language_falls_back_to_its_own_en(core_static, plugin_root):
    _write_json(_plugin_locales(plugin_root, "myplugin") / "en.json", {"myplugin": {"title": "My Plugin"}})

    messages = _merged_messages(browser_catalog(str(core_static), "fr"))

    assert messages["myplugin"]["title"] == "My Plugin"


def test_a_plugin_with_no_blueprint_still_gets_its_catalog_merged(core_static, plugin_root):
    """`alerting` ships `ui/static/locales/`, not `ui/blueprints/static/locales/` — both layouts
    have to work, since both are real PRO plugins today (Criticos wave-20 round 1, REQUIRED 1)."""
    _write_json(_plugin_locales_no_blueprint(plugin_root, "alerting") / "en.json", {"alerting": {"title": "Alerting"}})

    messages = _merged_messages(browser_catalog(str(core_static), "en"))

    assert messages["alerting"]["title"] == "Alerting"


# --------------------------------------------------------------------------------------
# (b) a plugin key colliding with a core key never overrides it, and it warns — at the LEAF,
# not the whole top-level namespace: 2 of the 13 real PRO catalogs (`user_manager`,
# `easy_resolve`) nest strings under a top-level name core also uses (`button`, `flash`, ...)
# for unrelated keys, and a top-level-only rule silently dropped 179 real strings on those two
# plugins alone (Criticos wave-20 round 2, NEW REQUIRED A) — one exact leaf collides, a sibling
# new leaf under the same namespace must still merge.
# --------------------------------------------------------------------------------------
def test_a_plugin_leaf_colliding_with_a_core_leaf_never_overrides_it(core_static, plugin_root, caplog):
    """SEC-W20 F-04 narrowed the merge to `plugin_id.*` only, so `myplugin` claiming `button.save`
    is now a namespace violation (refused wholesale), not a leaf collision — the outcome (core's
    `button.save` survives) is unchanged, only the warning's shape is."""
    _write_json(_plugin_locales(plugin_root, "myplugin") / "en.json", {"button": {"save": "Plugin save"}})

    with caplog.at_level("WARNING", logger="UI"):
        messages = _merged_messages(browser_catalog(str(core_static), "en"))

    assert messages["button"]["save"] == "Save"
    assert any("myplugin" in record.getMessage() and "button" in record.getMessage() for record in caplog.records)


def test_a_plugin_leaf_colliding_within_its_own_namespace_never_overrides_it(core_static, tmp_path, monkeypatch):
    """The leaf-collision guard still applies INSIDE a plugin's own namespace: two roots shipping a
    same-named plugin (accepted residual of F-04, Criticos round 1 R5 — `bw_plugins.id` is a
    primary key so this cannot happen through either supported install path, but the merge itself
    is still first-root-wins) cannot have the later root overwrite the earlier one's leaf. Two real
    roots are required here — a single-root single-catalog write would pass even if the whole
    collision branch were deleted."""
    core_root, external_root = tmp_path / "core_plugins", tmp_path / "external_plugins"
    core_root.mkdir()
    external_root.mkdir()
    monkeypatch.setattr(plugin_extensions, "CORE_PLUGINS_PATH", str(core_root))
    monkeypatch.setattr(plugin_extensions, "EXTERNAL_PLUGINS_PATH", str(external_root))
    monkeypatch.setattr(plugin_extensions, "PRO_PLUGINS_PATH", str(tmp_path / "no_pro_plugins"))

    _write_json(_plugin_locales(core_root, "myplugin") / "en.json", {"myplugin": {"title": "First"}})
    _write_json(_plugin_locales(external_root, "myplugin") / "en.json", {"myplugin": {"title": "Second"}})

    messages = _merged_messages(browser_catalog(str(core_static), "en"))
    assert messages["myplugin"]["title"] == "First"


def test_a_plugin_leaf_outside_its_own_namespace_is_refused_even_when_new(core_static, plugin_root):
    """SEC-W20 F-04: before the fix, a NEW leaf under a namespace core (or another plugin) already
    owns silently merged in — `button.new_action` landed even though `button` isn't `myplugin`'s
    own top-level id. The narrow rule refuses it, full stop: the docs' broader "new leaves under
    an existing namespace merge normally" promise no longer holds (see docs/plugins.md "Plugin
    translations")."""
    _write_json(_plugin_locales(plugin_root, "myplugin") / "en.json", {"button": {"new_action": "Do it"}})

    messages = _merged_messages(browser_catalog(str(core_static), "en"))

    assert "new_action" not in messages["button"]
    assert messages["button"]["save"] == "Save"  # untouched


# --------------------------------------------------------------------------------------
# (b2) SEC-W20 F-04: an overlay may only contribute leaves under its OWN top-level id — a plugin
# whose directory is `aaa_evil` cannot claim `user_manager.*`, regardless of load order relative
# to the real `user_manager` plugin (the original bug: whichever plugin merged first won the leaf,
# and the WARNING named the victim that lost, not the shadower).
# --------------------------------------------------------------------------------------
def test_a_plugin_cannot_claim_keys_outside_its_own_plugin_id(core_static, plugin_root, caplog):
    _write_json(_plugin_locales(plugin_root, "aaa_evil") / "en.json", {"user_manager": {"page": {"title": "<img src=x onerror=alert(1)>"}}})
    _write_json(_plugin_locales(plugin_root, "user_manager") / "en.json", {"user_manager": {"page": {"title": "User manager"}}})

    with caplog.at_level("WARNING", logger="UI"):
        messages = _merged_messages(browser_catalog(str(core_static), "en"))

    assert messages["user_manager"]["page"]["title"] == "User manager"
    assert any("aaa_evil" in record.getMessage() and "user_manager" in record.getMessage() for record in caplog.records)


def test_namespace_violations_are_warned_once_per_plugin_not_once_per_leaf(core_static, plugin_root, caplog):
    _write_json(
        _plugin_locales(plugin_root, "aaa_evil") / "en.json",
        {"user_manager": {"page": {"title": "pwned"}}, "footer": {"copyright": "pwned"}},
    )

    with caplog.at_level("WARNING", logger="UI"):
        messages = _merged_messages(browser_catalog(str(core_static), "en"))

    assert "user_manager" not in messages
    assert "footer" not in messages
    warnings = [record for record in caplog.records if "aaa_evil" in record.getMessage()]
    assert len(warnings) == 1
    assert "user_manager" in warnings[0].getMessage() and "footer" in warnings[0].getMessage()


def test_a_dotted_plugin_id_never_merges_and_warns_once(core_static, plugin_root, caplog):
    """Criticos round 2 C1: `PLUGIN_NAME_RX` (src/ui/app/utils.py) allows a dot in a plugin id, but
    both `_dotted_lookup` here and the browser's `t()` split a key on `.` — a catalog nested under
    `{"my.plugin": {...}}` (the only form the namespace guard accepts) is a namespace no dotted
    lookup key can ever reach. Refuse it outright rather than merge in a catalog whose every string
    silently renders as its own raw key."""
    _write_json(_plugin_locales(plugin_root, "my.plugin") / "en.json", {"my.plugin": {"title": "Unreachable"}})

    with caplog.at_level("WARNING", logger="UI"):
        messages = _merged_messages(browser_catalog(str(core_static), "en"))

    assert "my.plugin" not in messages
    assert any("my.plugin" in record.getMessage() and "unreachable" in record.getMessage().lower() for record in caplog.records)


def test_namespace_violation_warning_is_deduplicated_across_requests(core_static, plugin_root, caplog):
    """Criticos round 1 R2: `_merged_catalog` isn't cached, only the plugin disk scan is (see
    `_plugin_catalogs_for_request`), so every `_()` miss re-runs `_merge_plugin_catalog` from
    scratch — without a dedup memo (same mechanism as `_WARNED_COLLISIONS` already applies to a
    leaf collision), a single page with N misses against one violating plugin logs N lines, and
    a real PRO install (`user_manager`/`easy_resolve`, both violating by construction under the
    new rule) would log on every request forever."""
    _write_json(_plugin_locales(plugin_root, "zzz_evil") / "en.json", {"totally_unique_namespace_marker": {"x": "1"}})

    with caplog.at_level("WARNING", logger="UI"):
        browser_catalog(str(core_static), "en")
        browser_catalog(str(core_static), "en")
        browser_catalog(str(core_static), "en")

    warnings = [record for record in caplog.records if "zzz_evil" in record.getMessage()]
    assert len(warnings) == 1


def test_a_plugin_catalog_whose_own_key_is_not_an_object_is_ignored(core_static, plugin_root, caplog):
    """Criticos round 1 R1: a plugin catalog is untrusted input (shipped by any installed plugin) —
    before this guard, `{"myplugin": "not an object"}` reached `_merge_plugin_leaf`'s `.items()`
    call on a str and raised `AttributeError`, crashing every page render and the public
    `/locales/<lang>.js` on a malformed file, not just an actively malicious one."""
    _write_json(_plugin_locales(plugin_root, "myplugin") / "en.json", {"myplugin": "not an object"})

    with caplog.at_level("WARNING", logger="UI"):
        messages = _merged_messages(browser_catalog(str(core_static), "en"))

    assert "myplugin" not in messages
    assert messages["button"]["save"] == "Save"
    assert any("myplugin" in record.getMessage() for record in caplog.records)


def test_a_plugin_cannot_clobber_a_non_namespace_core_value_at_its_own_id(tmp_path, plugin_root, caplog):
    """Criticos round 1 R1: if a core catalog ever defines a plugin's own top-level id as a plain
    string rather than a namespace object (none do today — this pins the invariant instead of
    relying on it), a plugin of that id must not silently replace it."""
    static_dir = tmp_path / "core_static"
    _write_json(static_dir / "locales" / "en.json", {"myplugin": "a core string, not a namespace"})
    _write_json(_plugin_locales(plugin_root, "myplugin") / "en.json", {"myplugin": {"title": "Plugin title"}})

    with caplog.at_level("WARNING", logger="UI"):
        messages = _merged_messages(browser_catalog(str(static_dir), "en"))

    assert messages["myplugin"] == "a core string, not a namespace"
    assert any("myplugin" in record.getMessage() for record in caplog.records)


# --------------------------------------------------------------------------------------
# (e) SEC-W20 F-08: U+2028/U+2029 are valid JSON but terminate a statement in a parse-time
# <script> on engines predating ES2019 — a catalog value carrying either must not reach the
# served JS unescaped.
# --------------------------------------------------------------------------------------
def test_browser_catalog_escapes_line_and_paragraph_separators(core_static, plugin_root):
    _write_json(_plugin_locales(plugin_root, "myplugin") / "en.json", {"myplugin": {"title": f"a{chr(0x2028)}b{chr(0x2029)}c"}})

    catalog_script = browser_catalog(str(core_static), "en")

    assert " " not in catalog_script
    assert " " not in catalog_script
    assert "\\u2028" in catalog_script
    assert "\\u2029" in catalog_script


# --------------------------------------------------------------------------------------
# (c) server-side `_()` resolves a plugin key in a plugin template
# --------------------------------------------------------------------------------------
@pytest.fixture
def app():
    from flask import Flask

    # `static_folder="app/static"` matches `src/ui/main.py:616`'s real app: the core-key guard in
    # `gettext_or_plugin` reads `app.static_folder`, and that only lands on the real
    # `app/static/locales/*.json` catalogs (not Flask's `static/` default) with this set.
    application = Flask("bw_ui_plugin_i18n_test", root_path=str(REPO / "src" / "ui"), static_folder="app/static")
    application.config["SECRET_KEY"] = "test"
    init_i18n(application)
    return application


def test_gettext_resolves_a_plugin_key_in_a_plugin_template(app, plugin_root):
    from flask import render_template_string
    from flask_babel import force_locale

    _write_json(_plugin_locales(plugin_root, "myplugin") / "fr.json", {"myplugin": {"title": "Mon Plugin"}})

    with app.test_request_context("/"):
        with force_locale("fr"):
            rendered = render_template_string("{{ _('myplugin.title') }}")

    assert rendered == "Mon Plugin"


def test_gettext_still_translates_a_core_key_unchanged(app, plugin_root):
    """The plugin fallback only ever fires on a miss — a real core key must render exactly as
    it did before this extension point existed."""
    from flask import render_template_string
    from flask_babel import force_locale

    with app.test_request_context("/"):
        with force_locale("fr"):
            rendered = render_template_string("{{ _('button.create_service') }}")

    assert rendered not in ("button.create_service", "")


def test_gettext_never_resolves_a_plugin_leaf_that_shadows_a_real_core_key(app, plugin_root):
    """The browser-side leaf-collision test above has no server-side mirror: a plugin claiming
    the exact id of a real core key (not merely its namespace) must never win server-side either,
    even though `_()` never reaches the merged catalog for this key (the `.mo` already resolves
    it — see `test_gettext_still_translates_a_core_key_unchanged`)."""
    from flask import render_template_string
    from flask_babel import force_locale

    _write_json(_plugin_locales(plugin_root, "myplugin") / "fr.json", {"button": {"create_service": "Plugin text"}})

    with app.test_request_context("/"):
        with force_locale("fr"):
            rendered = render_template_string("{{ _('button.create_service') }}")

    assert rendered != "Plugin text"


def test_gettext_never_resolves_a_new_leaf_outside_the_plugins_own_namespace(app, plugin_root):
    """SEC-W20 F-04 narrowed the merge to `plugin_id.*` only: `button.totally_new_thing` from
    `myplugin` is now refused (namespace violation) even though it is a brand new leaf and `.mo`
    misses it — this reverses the round-2 regression fix from wave 20 (Criticos wave-20 round 2,
    NEW REQUIRED A), a deliberate security-over-convenience trade documented in docs/plugins.md
    "Plugin translations". A miss still echoes the key itself, same as any other untranslated
    lookup (see `translated()`)."""
    from flask import render_template_string
    from flask_babel import force_locale

    _write_json(_plugin_locales(plugin_root, "myplugin") / "en.json", {"button": {"totally_new_thing": "Plugin text"}})

    with app.test_request_context("/"):
        with force_locale("en"):
            rendered = render_template_string("{{ _('button.totally_new_thing') }}")

    assert rendered == "button.totally_new_thing"


def test_plugin_catalogs_are_read_once_per_request_but_not_across_requests(app, plugin_root, monkeypatch):
    """Every `_()` miss in a plugin template used to re-scan every plugin root from scratch
    (Criticos wave-20 round 1, REQUIRED 2: ~2ms x N keys per request). One request with two misses
    must cost one scan; the next request must scan again, so an install/upgrade/reload is still
    visible immediately rather than for the life of the worker process."""
    from flask import render_template_string
    from flask_babel import force_locale

    _write_json(_plugin_locales(plugin_root, "myplugin") / "en.json", {"myplugin": {"a": "A", "b": "B"}})

    calls = {"n": 0}
    real_iter = i18n_module.iter_plugin_catalogs

    def counting_iter(lang, roots=None):
        calls["n"] += 1
        return real_iter(lang, roots)

    monkeypatch.setattr(i18n_module, "iter_plugin_catalogs", counting_iter)

    with app.test_request_context("/"):
        with force_locale("en"):
            rendered = render_template_string("{{ _('myplugin.a') }}{{ _('myplugin.b') }}")
    assert rendered == "AB"
    assert calls["n"] == 1  # two misses, one scan

    with app.test_request_context("/"):
        with force_locale("en"):
            render_template_string("{{ _('myplugin.a') }}")
    assert calls["n"] == 2  # a new request scans again


# --------------------------------------------------------------------------------------
# (d) invalid JSON warns and the plugin still loads — every other plugin unaffected
# --------------------------------------------------------------------------------------
def test_invalid_plugin_catalog_warns_and_does_not_break_the_others(core_static, plugin_root, caplog):
    broken = _plugin_locales(plugin_root, "broken_plugin") / "en.json"
    broken.parent.mkdir(parents=True, exist_ok=True)
    broken.write_text("{not valid json", encoding="utf-8")
    _write_json(_plugin_locales(plugin_root, "myplugin") / "en.json", {"myplugin": {"title": "My Plugin"}})

    with caplog.at_level("WARNING", logger="UI"):
        messages = _merged_messages(browser_catalog(str(core_static), "en"))

    assert messages["myplugin"]["title"] == "My Plugin"
    assert "broken_plugin" not in messages
    assert any("broken_plugin" in record.getMessage() for record in caplog.records)
