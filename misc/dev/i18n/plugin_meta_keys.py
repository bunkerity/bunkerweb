#!/usr/bin/env python3
"""The translation keys of a plugin's metadata, with their English source text.

    python3 misc/dev/i18n/plugin_meta_keys.py src/common/core/antibot     # skeleton of antibot's catalog
    python3 misc/dev/i18n/plugin_meta_keys.py --general                   # general.settings.* of settings.json

A plugin translates its `plugin.json` / `templates/*.json` text by shipping `locales/<lang>.json`
at its root (see docs/plugins.md, "Plugin translations"). The English source is the manifest
itself, so there is no `en.json` to keep in sync: this script derives the key set from the
manifest, and prints it as a nested JSON skeleton holding the English text, ready to translate.
`tests/unit/ui/test_core_plugin_catalogs.py` uses the same functions to hold every core plugin's
catalogs to exactly this key set.

Keys, under the plugin's directory name (the id its catalog is merged under):

    <id>.meta.name / .description                    plugin.json name, description
    <id>.settings.<SETTING>.label / .help            each setting's label and help
    <id>.templates.<tpl>.name                        templates/<tpl>.json name
    <id>.templates.<tpl>.steps.<n>.title / .subtitle its steps, numbered from 0

An empty source string has nothing to translate and gets no key.
"""

from argparse import ArgumentParser
from json import dumps, loads
from pathlib import Path
from typing import Dict

REPO = Path(__file__).resolve().parents[3]
SETTINGS_JSON = REPO / "src" / "common" / "settings.json"


def _settings_keys(namespace: str, settings: dict) -> Dict[str, str]:
    keys = {}
    for setting_id, setting in settings.items():
        for field in ("label", "help"):
            keys[f"{namespace}.settings.{setting_id}.{field}"] = setting.get(field, "")
    return keys


def plugin_meta_keys(plugin_dir: Path) -> Dict[str, str]:
    """`{dotted key: English source}` for the plugin at `plugin_dir`."""
    plugin_id = plugin_dir.name
    manifest = loads((plugin_dir / "plugin.json").read_text(encoding="utf-8"))
    keys = {f"{plugin_id}.meta.name": manifest.get("name", ""), f"{plugin_id}.meta.description": manifest.get("description", "")}
    keys.update(_settings_keys(plugin_id, manifest.get("settings", {})))
    for template_file in sorted((plugin_dir / "templates").glob("*.json")):
        template = loads(template_file.read_text(encoding="utf-8"))
        prefix = f"{plugin_id}.templates.{template_file.stem}"
        keys[f"{prefix}.name"] = template.get("name", "")
        for index, step in enumerate(template.get("steps", [])):
            for field in ("title", "subtitle"):
                keys[f"{prefix}.steps.{index}.{field}"] = step.get(field, "")
    return {key: value for key, value in keys.items() if isinstance(value, str) and value}


def general_keys(settings_json: Path = SETTINGS_JSON) -> Dict[str, str]:
    """`general.settings.*` for `src/common/settings.json`, which has no plugin directory: these
    keys live in the core catalogs."""
    keys = _settings_keys("general", loads(settings_json.read_text(encoding="utf-8")))
    return {key: value for key, value in keys.items() if isinstance(value, str) and value}


def nest(flat: Dict[str, str]) -> dict:
    tree: dict = {}
    for key, value in flat.items():
        *parents, leaf = key.split(".")
        node = tree
        for part in parents:
            node = node.setdefault(part, {})
        node[leaf] = value
    return tree


def main() -> None:
    parser = ArgumentParser(description="The translation keys of a plugin's metadata, with their English source text.")
    parser.add_argument("plugin_dirs", nargs="*", type=Path, help="plugin directories holding a plugin.json")
    parser.add_argument("--general", action="store_true", help="the general.settings.* keys of src/common/settings.json")
    args = parser.parse_args()
    if not args.plugin_dirs and not args.general:
        parser.error("give at least one plugin directory, or --general")

    flat: Dict[str, str] = general_keys() if args.general else {}
    for plugin_dir in args.plugin_dirs:
        flat.update(plugin_meta_keys(plugin_dir))
    print(dumps(nest(flat), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
