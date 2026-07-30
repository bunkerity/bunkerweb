"""extensions.activation discovery."""

import json
from pathlib import Path

from plugin_extensions import iter_plugin_activations


def _plugin(tmp_path: Path, plugin_id: str, manifest: dict) -> None:
    directory = tmp_path / plugin_id
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "plugin.json").write_text(json.dumps(manifest), encoding="utf-8")


def test_reads_a_setting_map(tmp_path):
    _plugin(tmp_path, "limit", {"id": "limit", "extensions": {"activation": {"USE_LIMIT_REQ": "no", "USE_LIMIT_CONN": "no"}}})
    result = iter_plugin_activations(paths=[(tmp_path, "core")])
    assert result == {"limit": {"USE_LIMIT_REQ": "no", "USE_LIMIT_CONN": "no"}}


def test_reads_the_always_marker(tmp_path):
    _plugin(tmp_path, "errors", {"id": "errors", "extensions": {"activation": "always"}})
    assert iter_plugin_activations(paths=[(tmp_path, "core")]) == {"errors": "always"}


def test_ignores_plugins_without_the_key(tmp_path):
    _plugin(tmp_path, "plain", {"id": "plain"})
    _plugin(tmp_path, "other", {"id": "other", "extensions": {"certificate_source": {"label": "x"}}})
    assert iter_plugin_activations(paths=[(tmp_path, "core")]) == {}


def test_ignores_malformed_declarations(tmp_path):
    _plugin(tmp_path, "bad_type", {"id": "bad_type", "extensions": {"activation": ["USE_X"]}})
    _plugin(tmp_path, "bad_marker", {"id": "bad_marker", "extensions": {"activation": "sometimes"}})
    _plugin(tmp_path, "bad_values", {"id": "bad_values", "extensions": {"activation": {"USE_X": 1}}})
    assert iter_plugin_activations(paths=[(tmp_path, "core")]) == {}


def test_survives_unreadable_manifest(tmp_path):
    (tmp_path / "broken").mkdir()
    (tmp_path / "broken" / "plugin.json").write_text("{not json", encoding="utf-8")
    _plugin(tmp_path, "good", {"id": "good", "extensions": {"activation": {"USE_GOOD": "no"}}})
    assert iter_plugin_activations(paths=[(tmp_path, "core")]) == {"good": {"USE_GOOD": "no"}}


def test_falls_back_to_directory_name_when_id_absent(tmp_path):
    _plugin(tmp_path, "noid", {"extensions": {"activation": {"USE_NOID": "no"}}})
    assert iter_plugin_activations(paths=[(tmp_path, "core")]) == {"noid": {"USE_NOID": "no"}}


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


def test_core_manifests_declare_the_ported_maps():
    found = iter_plugin_activations(paths=[(CORE, "core")])
    for plugin_id, expected in EXPECTED_MAPS.items():
        assert found.get(plugin_id) == expected, plugin_id


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
