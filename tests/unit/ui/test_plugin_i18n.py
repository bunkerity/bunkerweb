"""The plugin i18n extension point (wave 20, lane PX-I18N).

A plugin drops `ui/blueprints/static/locales/<lang>.json` (12 of the 13 PRO plugins — the ones with
a Flask blueprint) or `ui/static/locales/<lang>.json` (`alerting`, which has none) next to its
`plugin.json` — both are layouts PRO already ships for the now-deleted
`window.BunkerWebExtraI18nPath` hook — and its keys are merged into `window.BW_I18N` and resolved by
`_()`, with no `plugin.json` declaration and no build step. See
`.cache/wave20-2026-09-21/report-PX-I18N.md` for the design.
"""

import sys
from json import dumps, loads
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "src" / "ui"))

import plugin_extensions  # type: ignore  # noqa: E402

import app.i18n as i18n_module  # noqa: E402
from app.i18n import browser_catalog, init_i18n  # noqa: E402


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
    _write_json(_plugin_locales(plugin_root, "myplugin") / "en.json", {"button": {"save": "Plugin save"}})

    with caplog.at_level("WARNING", logger="UI"):
        messages = _merged_messages(browser_catalog(str(core_static), "en"))

    assert messages["button"]["save"] == "Save"
    assert any("myplugin" in record.getMessage() and "button.save" in record.getMessage() for record in caplog.records)


def test_a_new_plugin_leaf_under_a_shared_core_namespace_still_merges(core_static, plugin_root):
    """The bug this test pins: a plugin adding `button.new_action` (core only has `button.save`)
    must merge in, not get dropped because `button` itself already exists in core."""
    _write_json(_plugin_locales(plugin_root, "myplugin") / "en.json", {"button": {"new_action": "Do it"}})

    messages = _merged_messages(browser_catalog(str(core_static), "en"))

    assert messages["button"]["new_action"] == "Do it"
    assert messages["button"]["save"] == "Save"  # untouched


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


def test_gettext_resolves_a_new_leaf_under_a_shared_core_namespace(app, plugin_root):
    """`button.totally_new_thing` is not a real core message id, so the `.mo` misses it — and a
    real PRO plugin (`user_manager`, `easy_resolve`) nests 179 of its own strings exactly this way,
    under a top-level name core also owns for unrelated keys. Refusing the whole `button.*`
    namespace here was the round-2 regression (Criticos wave-20 round 2, NEW REQUIRED A); only an
    exact leaf collision (`button.create_service`, covered above) may refuse."""
    from flask import render_template_string
    from flask_babel import force_locale

    _write_json(_plugin_locales(plugin_root, "myplugin") / "en.json", {"button": {"totally_new_thing": "Plugin text"}})

    with app.test_request_context("/"):
        with force_locale("en"):
            rendered = render_template_string("{{ _('button.totally_new_thing') }}")

    assert rendered == "Plugin text"


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
