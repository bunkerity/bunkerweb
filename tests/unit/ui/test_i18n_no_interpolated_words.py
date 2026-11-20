"""Translation source checks shared with dev."""

import ast
from json import loads
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
APP = REPO / "src" / "ui" / "app"
CATALOG_PATH = APP / "static" / "locales" / "en.json"
ROUTES = APP / "routes"
CATALOG = loads(CATALOG_PATH.read_text(encoding="utf-8"))


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


def _key(dotted):
    node = CATALOG
    for part in dotted.split("."):
        node = node[part]
    return node


@pytest.mark.parametrize("path", sorted(ROUTES.glob("*.py")), ids=lambda path: path.name)
def test_no_route_passes_a_word_or_plural_suffix_to_translated(path):
    assert source_violations(path.read_text(encoding="utf-8")) == []


@pytest.mark.parametrize(
    "key",
    [
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
        "workflows.say.jumped",
    ],
)
def test_a_catalog_key_nothing_reads_is_removed(key):
    with pytest.raises(KeyError):
        _key(key)


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


@pytest.mark.parametrize(
    "path",
    sorted(
        path
        for path in ROUTES.glob("*.py")
        if path.name not in {"bans.py", "configs.py", "global_settings.py", "instances.py", "jobs.py", "plugins.py", "pro.py", "services.py", "totp.py"}
    ),
    ids=lambda path: path.name,
)
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
