"""Q8 F-4..F-7: English literals that survived in a translated UI.

Source-level pins: each block below was English in French and German on the live stack
(QA-Q7-LIVE2). The catalogs carry the keys; these fail if a literal comes back.
"""

from json import loads
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
UI = REPO / "src" / "ui" / "app"
TEMPLATES = UI / "templates"
PAGES = UI / "static" / "js" / "pages"
EN = loads((UI / "static" / "locales" / "en.json").read_text(encoding="utf-8"))


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _key(dotted: str):
    node = EN
    for part in dotted.split("."):
        node = node[part]
    return node


def test_the_retired_plugins_page_script_is_gone():
    assert not (PAGES / "plugins.js").exists()


def test_the_live_plugin_upload_input_is_cleared_so_the_same_file_can_be_retried():
    handler = _read(PAGES / "plugins-grid.js").split('fileInput.on("change"', 1)[1].split("dragArea.on", 1)[0]
    assert 'this.value = ""' in handler
    assert "Array.from(this.files)" in handler  # the clear must not empty the list being iterated


def test_bulk_actions_menu_labels_are_translated():
    for name in ("services.js", "configs.js"):
        source = _read(PAGES / name)
        assert "Convert to<span" not in source, name
        assert 't(\n            "button.convert_to_online"' in source or 'data-i18n="button.convert_to_online"' in source, name
        assert 'data-i18n="button.convert_to_draft"' in source, name
        assert "</span>Export'" not in source, name
    assert "convert-to" in _read(PAGES / "services.js")  # the type no longer comes from the English label
    assert _key("button.convert_to_online") and _key("button.convert_to_draft")


def test_aria_labels_and_placeholders_go_through_the_catalog():
    forbidden = {
        "navbar.html": ('aria-label="Open user menu"',),
        "language-selector.html": ('placeholder="Search..."', 'aria-label="Search..."'),
        "groups.html": ('aria_label="Show details for', 'aria_label="Clone @'),
        "certificates.html": ('aria_label="Show details for',),
        "plugins.html": ('aria-label="Toggle {{ pname }}"',),
        "dashboard.html": ('aria-label="Toggle navigation"',),
    }
    for name, literals in forbidden.items():
        source = _read(TEMPLATES / name)
        for literal in literals:
            assert literal not in source, f"{name}: {literal}"
    for key in ("aria.label.open_user_menu", "aria.label.show_details", "aria.label.clone_item", "aria.label.toggle_item"):
        assert _key(key)


def test_notification_type_badges_are_translated():
    source = _read(TEMPLATES / "sidebar-notifications.html")
    assert "{{ category|capitalize }}\n                            {% else %}\n                                Info" not in source
    assert '_("status.success")' in source and '_("flash." ~ category)' in source


def test_data_table_language_covers_row_checkbox_and_pane_search_title():
    source = _read(UI / "static" / "js" / "dataTableInit.js")
    assert 'translate("datatable.select_row"' in source
    assert 'translate("searchpane.search_title"' in source
    assert _key("datatable.select_row") and _key("searchpane.search_title")


def test_instances_hostname_help_has_no_english_tail():
    source = _read(TEMPLATES / "instances.html")
    assert "are allowed in protocol/port" not in source


def test_duplicate_service_refusal_is_translated_at_the_route():
    source = _read(UI / "routes" / "services.py")
    assert 'translated("services.flash.service_already_exists", service=clash)' in source
    assert _key("services.flash.service_already_exists") == "Service {{service}} already exists."


def test_url_for_does_not_try_the_page_form_of_a_qualified_endpoint():
    source = _read(UI.parent / "main.py")
    assert 'not endpoint.endswith("_page") and "." not in endpoint' in source


def test_services_conversion_modal_is_translated():
    source = _read(PAGES / "services.js")
    body = source.split("const setupConversionModal", 1)[1].split("const setupDeletionModal", 1)[0]
    assert "modal.body.confirm_${" in body and '"services" : "service"' in body and "_conversion_${conversionType}" in body
    assert "button.convert_to_" in body
    assert ".text(`Convert to" not in body
    assert "{{state}}" not in body  # a translated word is never interpolated into the sentence
    for key in ("service", "services"):
        for state in ("online", "draft"):
            sentence = _key(f"modal.body.confirm_{key}_conversion_{state}")
            assert "{{" not in sentence and state in sentence, sentence
