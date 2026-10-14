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
    ("crowdsec.reason.sentence_other", "action"): "quoted raw remediation name this build does not know",
    ("crowdsec.reason.sentence_other_scenario", "action"): "quoted raw remediation name this build does not know",
    ("workflows.reason.sentence_other", "action"): "quoted raw rule action id this build does not know",
    **{
        (f"crowdsec.reason.sentence_{action}{suffix}", "source"): "label of the decision source"
        for action in ("ban", "captcha", "challenge", "other")
        for suffix in ("", "_scenario")
    },
    ("crowdsec.remove.selection", "source"): "name of the CrowdSec connection",
    ("crowdsec.remove.selection", "scope"): "quoted CrowdSec API data value",
    ("crowdsec.remove.selection", "type"): "quoted CrowdSec API data value",
    ("crowdsec.remove.selection", "origin"): "quoted CrowdSec API data value",
    ("crowdsec.remove.success_other_one", "mode"): "quoted propagation mode this build does not know",
    ("crowdsec.remove.success_other_other", "mode"): "quoted propagation mode this build does not know",
    ("tooltip.readonly_user_action_disabled", "action"): "caption of the disabled button, quoted",
    ("workflows.test.detail_status", "status"): "HTTP status code",
    ("service.resources.conflict.inline", "family"): "quoted setting family label (four families, too many for one key each)",
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
        "crowdsec.reason.action",
        "crowdsec.reason.sentence",
        "crowdsec.reason.sentence_scenario",
        "workflows.reason.sentence",
        "crowdsec.remove.success",
        "workflows.say.jumped",
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


# --- D5: whole-sentence detail lines and loading messages -------------------------------------------------------------------------------


def _js(name):
    return (APP / "static" / "js" / name).read_text(encoding="utf-8")


def _default_of(source, key):
    """The English default literal of a `t("<key>", "<default>"`, `translate(...)` or `t("<key>", { defaultValue: "<default>" })` call site."""
    literal = r'"((?:[^"\\]|\\.)*)"'
    match = re.search(r"\b(?:t|translate)\(\s*\"" + re.escape(key) + r"\",\s*" + literal, source) or re.search(
        r"\b(?:t|translate)\(\s*\"" + re.escape(key) + r"\",\s*\{[^}]*?defaultValue:\s*" + literal, source, re.S
    )
    assert match, f"no t({key!r}, ...) call site with a literal default"
    return match.group(1)


NEW_SENTENCE_KEYS = {
    "components/security-reason.js": [
        *(f"crowdsec.reason.sentence_{a}{s}" for a in ("ban", "captcha", "challenge", "other") for s in ("", "_scenario")),
        *(f"workflows.reason.sentence_{a}" for a in ("block", "redirect", "challenge", "other")),
    ],
    "pages/crowdsec.js": ["crowdsec.remove.selection", *(f"crowdsec.remove.success_{m}_{n}" for m in ("stream", "live", "other") for n in ("one", "other"))],
    "pages/workflow_editor.js": [f"workflows.say.jumped_{w}" for w in ("whole", "rule", "ruleNamed")],
    "pages/service-resources.js": ["service.resources.conflict.inline"],
    "pages/home.js": [
        *(f"dashboard.chart.tooltip.{word}_{form}" for word in ("requests", "blocked") for form in ("one", "other")),
        "dashboard.chart.tooltip.top_share",
    ],
}


@pytest.mark.parametrize("script, key", [(script, key) for script, keys in NEW_SENTENCE_KEYS.items() for key in keys])
def test_a_detail_line_is_a_whole_sentence_whose_js_default_is_the_catalog_text(script, key):
    assert _default_of(_js(script), key) == _key(key)


def test_the_catalog_text_of_the_detail_lines_quotes_its_data():
    assert _key("crowdsec.reason.sentence_ban_scenario") == "{{source}}: request blocked (scenario: “{{scenario}}”)"
    assert _key("workflows.reason.sentence_redirect") == "Security workflow “{{workflow}}”: request redirected"
    assert "“{{value}}”" in _key("crowdsec.remove.selection")
    assert "“{{family}}”" in _key("service.resources.conflict.inline")
    for form in ("one", "other"):
        for mode in ("stream", "live"):
            text = _key(f"crowdsec.remove.success_{mode}_{form}")
            assert f"{mode} mode" in text and "{{status}}" not in text and "{{mode}}" not in text


def _loading_message_problems(text):
    """Every `url_for("loading", ..., message=...)` whose message is English typed into the route."""
    found = []
    for node in ast.walk(ast.parse(text)):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "url_for"):
            continue
        if not (node.args and isinstance(node.args[0], ast.Constant) and node.args[0].value == "loading"):
            continue
        for keyword in node.keywords:
            if keyword.arg != "message":
                continue
            value = keyword.value
            if _is_typed_english(value):
                found.append(f"{node.lineno}: message={ast.unparse(value)[:60]}")
    return found


def _is_typed_english(value):
    """A message that is a literal, an f-string, a concatenation, or a fallback with no `translated()` in front of it."""
    if isinstance(value, ast.IfExp):
        return _is_typed_english(value.body) or _is_typed_english(value.orelse)
    if isinstance(value, ast.BoolOp):
        return not _calls_translated(value.values[0])
    return isinstance(value, (ast.Constant, ast.JoinedStr, ast.BinOp))


def _calls_translated(node):
    if isinstance(node, ast.IfExp):
        return _calls_translated(node.body) and _calls_translated(node.orelse)
    return isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "translated"


@pytest.mark.parametrize("path", sorted(ROUTES.glob("*.py")), ids=lambda path: path.name)
def test_no_route_hands_the_loading_page_a_literal_english_message(path):
    assert _loading_message_problems(path.read_text(encoding="utf-8")) == []


def test_the_loading_guard_flags_a_literal_an_fstring_and_an_untranslated_fallback():
    flagged = _loading_message_problems(
        'url_for("loading", message="Saving")\n'
        'url_for("loading", message=f"Saving {x}")\n'
        'url_for("loading", message=f"Saving {x}" or "y")\n'
        'url_for("loading", message=translated("loading.a") or "Saving")\n'
        'url_for("loading", message=translated("loading.a") if a else translated("loading.b"))\n'
        'url_for("loading", message=(translated("loading.a") or "x") if a else "Saving")\n'
    )

    assert len(flagged) == 4


def _constant_arms(node):
    """The string constants a key expression can evaluate to: a literal, or the arms of (nested) ternaries."""
    if isinstance(node, ast.IfExp):
        return _constant_arms(node.body) + _constant_arms(node.orelse)
    return [node] if isinstance(node, ast.Constant) else []


def _loading_keys_used():
    """``{key: set of kwarg names}`` for every `translated("loading....")` call of the routes (ternary arms included)."""
    used = {}
    for path in ROUTES.glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "translated" and node.args):
                continue
            for name in _constant_arms(node.args[0]):
                if isinstance(name, ast.Constant) and isinstance(name.value, str) and name.value.startswith("loading."):
                    used.setdefault(name.value, set()).update(k.arg for k in node.keywords)
    return used


def test_every_loading_key_a_route_names_exists_with_the_placeholders_it_passes():
    used = _loading_keys_used()

    assert used, "no route translates a loading message"
    for key, passed in sorted(used.items()):
        placeholders = {a or b or c for a, b, c in PLACEHOLDER.findall(_key(key))}
        assert placeholders == passed, f"{key}: catalog placeholders {sorted(placeholders)} != kwargs {sorted(passed)}"


def _loading_key_literals():
    """Every `"loading.…"` string constant of the routes, wherever it sits (a module-level key table counts)."""
    return {
        node.value
        for path in ROUTES.glob("*.py")
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value.startswith("loading.")
    }


def test_every_loading_catalog_key_is_read_by_a_route():
    named = _loading_key_literals()
    unused = sorted(f"loading.{key}" for key, _ in _leaves(CATALOG["loading"]) if f"loading.{key}" not in named and key != "default")

    assert unused == []


def test_the_loading_page_default_message_is_translated():
    main = (REPO / "src" / "ui" / "main.py").read_text(encoding="utf-8")

    assert 'request.values.get("message", "Loading...")' not in main
    assert 'translated("loading.default")' in main
    assert CATALOG["loading"]["default"] == "Loading..."
