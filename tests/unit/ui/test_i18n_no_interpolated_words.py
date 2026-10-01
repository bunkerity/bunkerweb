"""Q7-H1: no word is interpolated into a translated sentence.

A noun, verb or state word spliced into another sentence breaks gender, case, plural and word order in
every language that is not English. One whole-sentence key per variant; only names, counts, identifiers,
lists of identifiers and server messages may be interpolated.
"""

import ast
import re
from json import loads
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
APP = REPO / "src" / "ui" / "app"
CATALOG_PATH = APP / "static" / "locales" / "en.json"
ROUTES = APP / "routes"

# Never allowed, whatever the key: each one carried a word (or a plural suffix, or a sentence fragment).
FORBIDDEN = {"entity", "verb", "state", "noun", "separatorNote", "how", "convert_to", "suffix", "plural"}

# Allowed only where the value is a name, an identifier, a formatted value or a server message. Each entry
# says why; a new entry is a review decision, not a way to silence this test.
ALLOWED = {
    ("crowdsec.reason.sentence", "action"): "label: detail line, both halves stand alone",
    ("crowdsec.reason.sentence_scenario", "action"): "label: detail line, both halves stand alone",
    ("workflows.reason.sentence", "action"): "rule action id out of the operator's own config",
    ("crowdsec.reason.sentence", "source"): "label of the decision source",
    ("crowdsec.reason.sentence_scenario", "source"): "label of the decision source",
    ("crowdsec.remove.selection", "source"): "name of the CrowdSec connection",
    ("crowdsec.remove.selection", "scope"): "CrowdSec API data value",
    ("crowdsec.remove.selection", "type"): "CrowdSec API data value",
    ("crowdsec.remove.selection", "origin"): "CrowdSec API data value",
    ("crowdsec.remove.success", "status"): "propagation status value returned by the API",
    ("crowdsec.remove.success", "mode"): "propagation mode value returned by the API",
    ("tooltip.readonly_user_action_disabled", "action"): "caption of the disabled button, quoted",
    ("workflows.say.jumped", "where"): "rule label: message line",
    ("workflows.test.detail_status", "status"): "HTTP status code",
    ("service.resources.conflict.inline", "family"): "setting family id of the inline claim",
    ("request_path.source", "phase"): "nginx phase id",
    ("request_path.unordered", "phase"): "nginx phase id",
    ("tooltip.toggle_level", "level"): "log level id",
    ("raw_drafts.missing_metadata", "field"): "metadata field id",
    ("validation.pattern", "field"): "setting label",
    ("validation.required", "field"): "setting label",
    ("setup.flash.couldn_t_edit_new_service", "operation"): "server message",
    ("setup.flash.couldn_t_create_new_service", "operation"): "server message",
    ("status.deferred_tooltip", "reason"): "server message",
    ("templates.import.refused", "reason"): "parser message",
    ("compose.provenance.managed", "method"): "method id",
    ("legend.locked_settings_annotation", "method"): "method id",
    ("raw_drafts.locked_by_method", "method"): "method id",
    ("status.template_in_use", "method"): "method id",
    ("template.editor.readonly_method", "method"): "method id",
    ("tooltip.disabled_by_method", "method"): "method id",
    ("tooltip.enroll_disabled_by_method", "method"): "method id",
    ("plugins.flash.plugin_upload_error", "value2"): "server message",
    ("plugins.flash.file_plugin_json_missing_one_more", "value2"): "folder name",
    ("web_cache.flash.web_cache_purged_instance_failed_unreachable", "value2"): "count",
    ("web_cache.flash.web_cache_purged_instance_failed_unreachable", "value3"): "count",
}
RESTRICTED = {
    "action",
    "where",
    "type",
    "kind",
    "family",
    "mode",
    "status",
    "scope",
    "level",
    "phase",
    "reason",
    "method",
    "field",
    "source",
    "operation",
    "origin",
    "value2",
    "value3",
}

PLACEHOLDER = re.compile(r"\{\{\s*(\w+)\s*\}\}|\{(\w+)\}|%\((\w+)\)s")
PLURAL_SUFFIX = re.compile(r"\w\{\{\s*value\s*\}\}")


def _leaves(node, path=""):
    for name, value in node.items():
        if isinstance(value, dict):
            yield from _leaves(value, f"{path}{name}.")
        else:
            yield path + name, str(value)


def catalog_violations(catalog):
    """``(key, problem)`` for every en.json sentence that interpolates a word."""
    found = []
    for key, value in _leaves(catalog):
        names = {a or b or c for a, b, c in PLACEHOLDER.findall(value)}
        found += [(key, f"forbidden placeholder {name}") for name in sorted(names & FORBIDDEN)]
        found += [(key, f"restricted placeholder {name} is not allowlisted") for name in sorted(names & RESTRICTED) if (key, name) not in ALLOWED]
        if PLURAL_SUFFIX.search(value):
            found.append((key, "plural suffix interpolated"))
    return found


def source_violations(text):
    """Lines of a routes module that pass a plural suffix or an English word into ``translated()``."""
    found = []
    for node in ast.walk(ast.parse(text)):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "translated"):
            continue
        for keyword in node.keywords:
            value = keyword.value
            literal = isinstance(value, ast.Constant) and isinstance(value.value, str) and value.value.strip()
            ternary = isinstance(value, ast.IfExp) and any(
                isinstance(side, ast.Constant) and isinstance(side.value, str) for side in (value.body, value.orelse)
            )
            cased = isinstance(value, ast.Call) and isinstance(value.func, ast.Attribute) and value.func.attr in {"title", "capitalize", "lower", "upper"}
            if literal or ternary or cased:
                found.append(f"{node.lineno}: {keyword.arg}={ast.unparse(value)[:60]}")
    return found


CATALOG = loads(CATALOG_PATH.read_text(encoding="utf-8"))


def _key(dotted):
    node = CATALOG
    for part in dotted.split("."):
        node = node[part]
    return node


def test_no_catalog_sentence_interpolates_a_word():
    assert catalog_violations(CATALOG) == []


def test_every_allowlist_entry_is_still_used():
    used = {(key, name) for key, value in _leaves(CATALOG) for name in {a or b or c for a, b, c in PLACEHOLDER.findall(value)}}
    assert sorted(set(ALLOWED) - used) == []


@pytest.mark.parametrize("path", sorted(ROUTES.glob("*.py")), ids=lambda path: path.name)
def test_no_route_passes_a_word_or_plural_suffix_to_translated(path):
    assert source_violations(path.read_text(encoding="utf-8")) == []


def _bulk_entities():
    script = (APP / "static" / "js" / "dataTableInit.js").read_text(encoding="utf-8")
    block = re.search(r"const allowedNames = \[(.*?)\];", script, re.S)
    assert block, "allowedNames list not found in dataTableInit.js"
    return sorted(set(re.findall(r'"(\w+)"', block.group(1))) | {"items"})


@pytest.mark.parametrize("entity", _bulk_entities())
def test_every_bulk_select_entity_has_whole_sentences(entity):
    node = _key(f"datatable.bulk_select.{entity}")

    assert set(node) == {"page_one", "page_other", "all_filtered", "all_done"}
    assert all("{{count}}" in value for value in node.values())
    assert not any("{{entity}}" in value for value in node.values())


def test_the_bulk_select_banner_no_longer_passes_the_entity():
    script = (APP / "static" / "js" / "dataTableInit.js").read_text(encoding="utf-8")

    assert "entity: entityName" not in script
    assert "datatable.bulk_select_page" not in script and "datatable.bulk_select_all_done" not in script


@pytest.mark.parametrize(
    "key",
    [
        "datatable.bulk_select_page",
        "datatable.bulk_select_all_filtered",
        "datatable.bulk_select_all_done",
        "plugins.flash.couldn_t",
        "plugins.flash.couldn_t_2",
        "plugins.flash.refused",
        "plugins.flash.did_not_complete",
        "instances.flash.instance_does_not_have_method",
        "instances.flash.missing_instances_parameter_instances",
        "instances.flash.instance_successfully",
        "instances.flash.instance_deleted_successfully",
        "instances.flash.could_not_found",
        "configs.flash.converted_configs",
        "configs.flash.for_service_suffix",
        "cache.flash.for_service_suffix",
        "services.flash.converted_services",
        "services.flash.service_now_declared",
        "services.flash.could_not_fetch_attached_service",
        "template.editor.multivalue_helper_separator_note",
        "workflows.say.actionChanged",
        "workflows.say.via",
        "service.resources.family_singular",
        "redirects.flash.message",
    ],
)
def test_a_catalog_key_nothing_reads_is_removed(key):
    with pytest.raises(KeyError):
        _key(key)


@pytest.mark.parametrize("action", ["install", "update"])
def test_the_catalogue_plugin_flashes_have_one_sentence_per_action(action):
    flash = CATALOG["plugins"]["flash"]

    for key in (f"refused_{action}", f"{action}_did_not_complete", f"couldn_t_{action}_catalogue", f"couldn_t_{action}_catalogue_2"):
        assert key in flash and action in flash[key].lower()
        assert "{{action}}" not in flash[key] and "{{value}}" not in flash[key]


def test_the_instance_flashes_have_one_sentence_per_action():
    flash = CATALOG["instances"]["flash"]

    for action in ("ping", "reload", "stop", "delete"):
        assert flash[f"missing_instances_parameter_instances_{action}"].endswith(f"/instances/{action}.")
    for action in ("reload", "stop"):
        assert f"a {action} method" in flash[f"instance_does_not_have_{action}_method"]
