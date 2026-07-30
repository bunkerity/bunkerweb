"""extensions.activation discovery."""

import json
from pathlib import Path

from plugin_extensions import iter_plugin_activations


def _plugin(tmp_path: Path, plugin_id: str, manifest: dict, *, owns=()) -> None:
    """Write a manifest. ``owns`` names the settings the plugin declares, since an activation key
    is only read when the declaring plugin owns it (see the ownership test below)."""
    directory = tmp_path / plugin_id
    directory.mkdir(parents=True, exist_ok=True)
    if owns:
        manifest = {"settings": {name: {"context": "multisite", "type": "check", "default": "yes"} for name in owns}} | manifest
    (directory / "plugin.json").write_text(json.dumps(manifest), encoding="utf-8")


def test_reads_a_setting_map(tmp_path):
    _plugin(
        tmp_path,
        "limit",
        {"id": "limit", "extensions": {"activation": {"USE_LIMIT_REQ": "no", "USE_LIMIT_CONN": "no"}}},
        owns=("USE_LIMIT_REQ", "USE_LIMIT_CONN"),
    )
    result = iter_plugin_activations(paths=[(tmp_path, "core")])
    assert result == {"limit": {"USE_LIMIT_REQ": "no", "USE_LIMIT_CONN": "no"}}


def test_reads_the_always_marker(tmp_path):
    """`always` carries no keys, so it is not subject to the ownership filter."""
    _plugin(tmp_path, "errors", {"id": "errors", "extensions": {"activation": "always"}})
    assert iter_plugin_activations(paths=[(tmp_path, "core")]) == {"errors": "always"}


def test_ignores_plugins_without_the_key(tmp_path):
    _plugin(tmp_path, "plain", {"id": "plain"})
    _plugin(tmp_path, "other", {"id": "other", "extensions": {"certificate_source": {"label": "x"}}})
    assert iter_plugin_activations(paths=[(tmp_path, "core")]) == {}


def test_ignores_malformed_declarations(tmp_path):
    _plugin(tmp_path, "bad_type", {"id": "bad_type", "extensions": {"activation": ["USE_X"]}}, owns=("USE_X",))
    _plugin(tmp_path, "bad_marker", {"id": "bad_marker", "extensions": {"activation": "sometimes"}})
    _plugin(tmp_path, "bad_values", {"id": "bad_values", "extensions": {"activation": {"USE_X": 1}}}, owns=("USE_X",))
    assert iter_plugin_activations(paths=[(tmp_path, "core")]) == {}


def test_survives_unreadable_manifest(tmp_path):
    (tmp_path / "broken").mkdir()
    (tmp_path / "broken" / "plugin.json").write_text("{not json", encoding="utf-8")
    _plugin(tmp_path, "good", {"id": "good", "extensions": {"activation": {"USE_GOOD": "no"}}}, owns=("USE_GOOD",))
    assert iter_plugin_activations(paths=[(tmp_path, "core")]) == {"good": {"USE_GOOD": "no"}}


def test_falls_back_to_directory_name_when_id_absent(tmp_path):
    _plugin(tmp_path, "noid", {"extensions": {"activation": {"USE_NOID": "no"}}}, owns=("USE_NOID",))
    assert iter_plugin_activations(paths=[(tmp_path, "core")]) == {"noid": {"USE_NOID": "no"}}


def test_a_plugin_may_only_declare_its_own_settings(tmp_path):
    """The manifest alone decides what an activation toggle writes, and this loop is deliberately
    NOT behind `is_trusted` (declarative data, no plugin code loaded), so an external plugin.json
    reaches both the activation writer (ui/app/routes/plugins.py) and the compose shelf's declared
    save scope (ui/app/routes/services.py:shelf_plugin_scope) -- where a key that is in scope and
    not posted has its row DELETED (db_methods/config_save.py:592).

    Blast-radius limit, not a privilege boundary: installing a hostile plugin already buys code
    execution. What it does buy is that a malformed or copy-pasted manifest cannot reach another
    plugin's settings."""
    _plugin(tmp_path, "hostile", {"id": "hostile", "extensions": {"activation": {"SERVER_NAME": ""}}}, owns=("USE_HOSTILE",))
    assert iter_plugin_activations(paths=[(tmp_path, "core")]) == {}


def test_one_foreign_key_drops_the_whole_declaration(tmp_path):
    """All-or-nothing, NOT a filter that keeps the good keys. Keeping them would leave the plugin
    map-declared with a silently truncated declaration -- wrong activation set, wrong
    `is_plugin_active`, wrong shelf scope, and no signal anywhere that it happened. Dropping hands
    the plugin to the tier-3 naming heuristic, which can only resolve its own USE_<ID>."""
    _plugin(tmp_path, "greedy", {"id": "greedy", "extensions": {"activation": {"SERVER_NAME": "", "USE_GREEDY": "no"}}}, owns=("USE_GREEDY",))
    assert iter_plugin_activations(paths=[(tmp_path, "core")]) == {}


def test_a_manifest_with_no_settings_block_declares_nothing(tmp_path):
    """A key with no declaration has no type, no legal values and no schema for the writer to
    validate against -- the same reason `shelf_plugin_scope` drops undeclared keys."""
    _plugin(tmp_path, "empty", {"id": "empty", "extensions": {"activation": {"USE_EMPTY": "no"}}})
    assert iter_plugin_activations(paths=[(tmp_path, "core")]) == {}


CORE = Path(__file__).resolve().parents[3] / "src" / "common" / "core"

# Ported verbatim from the PLUGINS_SPECIFICS table this slice deletes, so the manifests are
# provably a faithful move rather than a rewrite.
EXPECTED_MAPS = {
    "country": {"BLACKLIST_COUNTRY": "", "WHITELIST_COUNTRY": ""},
    "customcert": {"USE_CUSTOM_SSL": "no"},
    "inject": {"INJECT_BODY": "", "INJECT_HEAD": ""},
    "letsencrypt": {"AUTO_LETS_ENCRYPT": "no"},
    "limit": {"USE_LIMIT_REQ": "no", "USE_LIMIT_CONN": "no"},
    "php": {"REMOTE_PHP": "", "LOCAL_PHP": ""},
    "redirect": {"REDIRECT_TO": ""},
    "selfsigned": {"GENERATE_SELF_SIGNED_SSL": "no"},
    "antibot": {"USE_ANTIBOT": "no"},
}

EXPECTED_ALWAYS = {"errors", "headers", "misc", "pro", "sessions", "ssl"}

# Keys added DELIBERATELY after the port, kept separate so EXPECTED_MAPS stays a faithful record of
# what PLUGINS_SPECIFICS held and every later addition has to be written down here to pass.
#
# USE_LIMIT_REQ_GLOBAL activates limit.lua (`:99`, `:107`, `:150`) exactly as the other two do. It
# was missing from the ported table, so a conformant OFF left the global rate limiter running and a
# service using only it read as inactive.
DELIBERATE_ADDITIONS = {"limit": {"USE_LIMIT_REQ_GLOBAL": "no"}}


def test_core_manifests_declare_the_ported_maps():
    found = iter_plugin_activations(paths=[(CORE, "core")])
    for plugin_id, expected in EXPECTED_MAPS.items():
        assert found.get(plugin_id) == expected | DELIBERATE_ADDITIONS.get(plugin_id, {}), plugin_id


def test_core_manifests_declare_always_on_plugins():
    found = iter_plugin_activations(paths=[(CORE, "core")])
    for plugin_id in EXPECTED_ALWAYS:
        assert found.get(plugin_id) == "always", plugin_id


def test_declared_settings_exist_in_their_own_plugin():
    """A declared setting must belong to the plugin declaring it, or the map is a typo."""
    found = iter_plugin_activations(paths=[(CORE, "core")])
    for plugin_id, declaration in found.items():
        if declaration == "always":
            continue
        manifest = json.loads((CORE / plugin_id / "plugin.json").read_text(encoding="utf-8"))
        own = set(manifest.get("settings", {}))
        assert set(declaration) <= own, f"{plugin_id} declares settings it does not own: {set(declaration) - own}"
