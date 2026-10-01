"""Per-plugin parity for the metadata translations a core plugin ships (CAT-C6, M13).

A core plugin translates its `plugin.json` / `templates/*.json` text in
`src/common/core/<id>/locales/<lang>.json`, not in the 19 core catalogs, so
`test_i18n_catalogs.py` never sees these files. The English source is the manifest itself;
`misc/dev/i18n/plugin_meta_keys.py` derives the expected key set from it. For each metadata
subtree a plugin ships (`meta`, `settings`, `templates`), every one of the 18 non-English files
must carry exactly that subtree's keys, with the same value checks the core catalogs get. Page
strings outside those subtrees stay free-form, as for any plugin.
"""

import sys
from json import dumps, loads
from pathlib import Path
from re import findall

import pytest

REPO = Path(__file__).resolve().parents[3]
CORE_PLUGINS = REPO / "src" / "common" / "core"
CORE_LOCALES = REPO / "src" / "ui" / "app" / "static" / "locales"

sys.path.insert(0, str(REPO / "src" / "ui"))
sys.path.insert(0, str(REPO / "misc" / "dev" / "i18n"))

from app.i18n import PLUGIN_METADATA_SUBTREES  # noqa: E402
from app.lang_config import SUPPORTED_LANGUAGES  # noqa: E402

from plugin_meta_keys import general_keys, plugin_meta_keys  # noqa: E402

CODES = sorted(entry["code"] for entry in SUPPORTED_LANGUAGES)
TRANSLATED_CODES = [code for code in CODES if code != "en"]


def _flatten(node, prefix=""):
    for key, value in node.items():
        path = f"{prefix}{key}"
        if isinstance(value, dict):
            yield from _flatten(value, f"{path}.")
        else:
            yield path, value


def _value_errors(where: str, source: str, value) -> list:
    if not isinstance(value, str) or not value.strip():
        return [f"{where}: empty or not a string"]
    errors = []
    for label, pattern in (("placeholders", r"\{\{\s*\w+\s*\}\}|%\(\w+\)s"), ("embedded HTML", r"</?[^>]+>")):
        if sorted(findall(pattern, value)) != sorted(findall(pattern, source)):
            errors.append(f"{where}: {label} differ from the English source")
    if (value[:1].isspace() and not source[:1].isspace()) or (value[-1:].isspace() and not source[-1:].isspace()):
        errors.append(f"{where}: invented edge whitespace")
    return errors


def catalog_errors(plugin_dir: Path) -> list:
    """Every parity or value problem in the metadata catalogs `plugin_dir/locales/` ships."""
    locales = plugin_dir / "locales"
    if not locales.is_dir():
        return []
    plugin_id = plugin_dir.name
    expected = plugin_meta_keys(plugin_dir)
    files = {path.stem: loads(path.read_text(encoding="utf-8")) for path in sorted(locales.glob("*.json"))}
    errors = [f"{plugin_id}/{code}.json: not a supported language" for code in files if code not in CODES]

    own = {code: catalog.get(plugin_id) if isinstance(catalog.get(plugin_id), dict) else {} for code, catalog in files.items()}
    shipped = {subtree for catalog in own.values() for subtree in PLUGIN_METADATA_SUBTREES if subtree in catalog}
    wanted = {key: source for key, source in expected.items() if key.split(".")[1] in shipped}

    for code in CODES:
        if code not in files:
            if code != "en" and shipped:
                errors.append(f"{plugin_id}/{code}.json: missing (ships {', '.join(sorted(shipped))})")
            continue
        found = {f"{plugin_id}.{key}": value for key, value in _flatten(own[code]) if key.split(".")[0] in PLUGIN_METADATA_SUBTREES}
        # en.json is optional for these subtrees (the manifest is the English source): it may
        # override a subset, never add a key the manifest does not have.
        missing = [] if code == "en" else sorted(set(wanted) - set(found))
        errors += [f"{plugin_id}/{code}.json: missing {key}" for key in missing]
        errors += [f"{plugin_id}/{code}.json: stale {key}" for key in sorted(set(found) - set(wanted))]
        for key in sorted(set(found) & set(wanted)):
            errors += _value_errors(f"{plugin_id}/{code}.json {key}", wanted[key], found[key])
    return errors


# --------------------------------------------------------------------------------------
# The real tree
# --------------------------------------------------------------------------------------
@pytest.mark.parametrize("plugin_dir", sorted(path.parent for path in CORE_PLUGINS.glob("*/plugin.json")), ids=lambda path: path.name)
def test_core_plugin_metadata_catalogs_are_at_parity(plugin_dir):
    assert catalog_errors(plugin_dir) == []


def _actions_i18n_widget_keys(plugin_dir: Path) -> set:
    """Every `widgets.<key>.title`/`.subtitle` path a plugin's `ui/actions.py` declares via a
    `title_i18n`/`subtitle_i18n` literal. Grepped from the source text, not imported: `actions.py`
    is arbitrary plugin code, not a manifest, and the key path is a JSON string literal either way."""
    actions = plugin_dir / "ui" / "actions.py"
    if not actions.is_file():
        return set()
    return set(findall(r'"(?:title|subtitle)_i18n":\s*"(widgets\.[\w.]+)"', actions.read_text(encoding="utf-8")))


@pytest.mark.parametrize("plugin_dir", sorted(path.parent for path in CORE_PLUGINS.glob("*/plugin.json")), ids=lambda path: path.name)
def test_core_plugin_widget_i18n_keys_resolve_in_every_language(plugin_dir):
    """`widgets` is free-form (not in `PLUGIN_METADATA_SUBTREES`), so `catalog_errors` never checks
    it — a `title_i18n`/`subtitle_i18n` key with no translation anywhere silently falls back to the
    raw English string with no signal. This guards it directly: every widget i18n key a plugin's
    `pre_render()` declares must resolve to a non-empty string in all 18 non-English catalogues."""
    keys = _actions_i18n_widget_keys(plugin_dir)
    if not keys:
        pytest.skip("no title_i18n/subtitle_i18n widget keys")

    plugin_id = plugin_dir.name
    locales = plugin_dir / "locales"
    errors = []
    for code in TRANSLATED_CODES:
        catalog_path = locales / f"{code}.json"
        if not catalog_path.is_file():
            errors.append(f"{plugin_id}/{code}.json: missing (widget keys: {', '.join(sorted(keys))})")
            continue
        catalog = loads(catalog_path.read_text(encoding="utf-8")).get(plugin_id) or {}
        for key in keys:
            value = catalog
            for part in key.split("."):
                value = value.get(part) if isinstance(value, dict) else None
            if not isinstance(value, str) or not value.strip():
                errors.append(f"{plugin_id}/{code}.json: missing or empty {key}")
    assert errors == []


def test_general_settings_in_the_core_catalogs_match_settings_json():
    """`general.settings.*` translate `src/common/settings.json` from the core catalogs, which
    `test_i18n_catalogs.py` already holds at parity with each other; this holds `en.json` itself to
    the manifest, once the subtree exists."""
    english = loads((CORE_LOCALES / "en.json").read_text(encoding="utf-8"))
    settings = (english.get("general") or {}).get("settings")
    if settings is None:
        pytest.skip("no general.settings.* in the core catalogs yet")
    assert {f"general.settings.{key}" for key, _ in _flatten(settings)} == set(general_keys())


# --------------------------------------------------------------------------------------
# The checker itself, on fixtures
# --------------------------------------------------------------------------------------
MANIFEST = {
    "id": "demo",
    "name": "Demo",
    "description": "Blocks {{count}} bots",
    "settings": {"USE_DEMO": {"label": "Use demo", "help": "Enable <b>demo</b>"}},
}


def _demo(tmp_path: Path, catalogs: dict) -> Path:
    plugin_dir = tmp_path / "demo"
    (plugin_dir / "locales").mkdir(parents=True)
    (plugin_dir / "plugin.json").write_text(dumps(MANIFEST), encoding="utf-8")
    for code, catalog in catalogs.items():
        (plugin_dir / "locales" / f"{code}.json").write_text(dumps(catalog), encoding="utf-8")
    return plugin_dir


def _meta(name="Démo", description="Bloque {{count}} robots"):
    return {"demo": {"meta": {"name": name, "description": description}, "page": {"free": "form"}}}


def test_a_complete_meta_subtree_in_every_language_passes(tmp_path):
    assert catalog_errors(_demo(tmp_path, {code: _meta() for code in TRANSLATED_CODES})) == []


def test_a_language_missing_a_key_or_a_file_fails(tmp_path):
    catalogs = {code: _meta() for code in TRANSLATED_CODES if code != "de"}
    catalogs["fr"] = {"demo": {"meta": {"name": "Démo"}}}

    errors = catalog_errors(_demo(tmp_path, catalogs))

    assert "demo/de.json: missing (ships meta)" in errors
    assert "demo/fr.json: missing demo.meta.description" in errors


def test_a_shipped_subtree_is_required_whole_but_an_unshipped_one_is_not(tmp_path):
    """`settings` is not shipped by any file, so it is not required; `meta` is, so both its keys are."""
    errors = catalog_errors(_demo(tmp_path, {code: _meta() for code in TRANSLATED_CODES}))

    assert not any("settings" in error for error in errors)


def test_a_stale_key_and_broken_values_fail(tmp_path):
    catalogs: dict = {code: _meta() for code in TRANSLATED_CODES}
    catalogs["fr"] = {"demo": {"meta": {"name": " Démo", "description": "Bloque des robots", "gone": "x"}}}
    catalogs["en"] = {"demo": {"meta": {"name": "Demo"}, "settings": {"OLD": {"label": "x"}}}}

    errors = catalog_errors(_demo(tmp_path, catalogs))

    assert "demo/fr.json: stale demo.meta.gone" in errors
    assert "demo/fr.json demo.meta.description: placeholders differ from the English source" in errors
    assert "demo/fr.json demo.meta.name: invented edge whitespace" in errors
    assert "demo/en.json: stale demo.settings.OLD.label" in errors


def test_embedded_html_must_survive_translation(tmp_path):
    catalogs = {code: {"demo": {"settings": {"USE_DEMO": {"label": "Démo", "help": "Active <b>démo</b>"}}}} for code in TRANSLATED_CODES}
    catalogs["it"] = {"demo": {"settings": {"USE_DEMO": {"label": "Demo", "help": "Attiva demo"}}}}

    assert catalog_errors(_demo(tmp_path, catalogs)) == ["demo/it.json demo.settings.USE_DEMO.help: embedded HTML differ from the English source"]


def test_the_generator_derives_keys_from_the_manifest_and_templates(tmp_path):
    plugin_dir = _demo(tmp_path, {})
    (plugin_dir / "templates").mkdir()
    (plugin_dir / "templates" / "low.json").write_text(dumps({"name": "Low", "steps": [{"title": "One", "subtitle": ""}]}), encoding="utf-8")

    assert plugin_meta_keys(plugin_dir) == {
        "demo.meta.name": "Demo",
        "demo.meta.description": "Blocks {{count}} bots",
        "demo.settings.USE_DEMO.label": "Use demo",
        "demo.settings.USE_DEMO.help": "Enable <b>demo</b>",
        "demo.templates.low.name": "Low",
        "demo.templates.low.steps.0.title": "One",
    }
