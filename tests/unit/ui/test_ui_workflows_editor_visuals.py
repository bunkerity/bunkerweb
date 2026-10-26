"""Part 3 of the workflows port: the overview attachment dialog and the editor card markup.

Source-level pins. The rendered behaviour is proven in a browser against the real templates
(.claude/ui-port/proofs/W2-WORKFLOWS/part3-check.cjs); these keep the contracts that would
otherwise only break there.
"""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3] / "src" / "ui" / "app"
OVERVIEW = (ROOT / "templates" / "workflows.html").read_text(encoding="utf-8")
OVERVIEW_JS = (ROOT / "static" / "js" / "pages" / "workflows.js").read_text(encoding="utf-8")
EDITOR_JS = (ROOT / "static" / "js" / "pages" / "workflow_editor.js").read_text(encoding="utf-8")
CATALOG = json.loads((ROOT / "static" / "locales" / "en.json").read_text(encoding="utf-8"))


def _key(path):
    node = CATALOG
    for part in path.split("."):
        node = node[part]
    return node


def test_the_overview_filters_by_attachment_state_and_keeps_the_exact_service_filter():
    assert 'id="workflows-attachment-filter"' in OVERVIEW
    assert 'id="workflows-service-filter"' in OVERVIEW
    assert 'value="attached"' in OVERVIEW and 'value="none"' in OVERVIEW
    assert "data-truncated" in OVERVIEW and "workflows.truncated" in OVERVIEW


def test_service_names_and_detach_live_in_a_dialog_not_in_the_cell():
    row = OVERVIEW[OVERVIEW.index("{% for flow in workflows %}") : OVERVIEW.index("{% else %}", OVERVIEW.index("{% for flow in workflows %}"))]
    assert "workflow-services" in row
    assert "/detach" not in row, "the inline detach form moved into the dialog"
    dialog = OVERVIEW[OVERVIEW.index('id="workflow-services-modal"') :]
    dialog = dialog[: dialog.index("{% endcall %}")]
    assert 'action="{{ workflows_url }}/detach"' in dialog
    for field in ("csrf_token", "workflow_id", "service_id"):
        assert f'name="{field}"' in dialog
    assert "workflow-detach" in OVERVIEW_JS and ".submit()" in OVERVIEW_JS


def test_the_export_keeps_service_names_when_the_cell_shows_a_count():
    assert 'orthogonal: "export"' in OVERVIEW_JS and 'type !== "export"' in OVERVIEW_JS


def test_the_editor_card_has_one_tool_group_and_no_repeated_footer():
    assert "bw-flow-foot" not in EDITOR_JS
    assert "consequenceBadge(rule)" in EDITOR_JS
    # grip, up, down, separator, More and expand all sit in the one group the head renders
    head = EDITOR_JS[EDITOR_JS.index("function ruleNode") :]
    assert head.count('class="bw-flow-tools"') == 1


def test_the_summary_highlight_comes_from_rule_data_not_from_the_english_text():
    body = EDITOR_JS[EDITOR_JS.index("function summaryHtml") : EDITOR_JS.index("function paintSummary")]
    assert "STATE.summaries" not in body, "summaryHtml builds from the rule, never from the server prose"
    assert not re.search(r"\.(split|replace|match|indexOf)\(", body)


def test_every_new_translation_key_the_editor_asks_for_is_in_the_catalog():
    wanted = set(re.findall(r'translate\(\s*"(workflows\.(?:sum|conseq|menu|act_settings|aria\.ruleTools)[A-Za-z_.]*)"', EDITOR_JS))
    wanted |= {"workflows.sum.leaf.ip", "workflows.sum.leaf.country", "workflows.sum.leaf.asn", "workflows.sum.leaf.method"}
    assert len(wanted) >= 15
    for key in sorted(wanted):
        assert isinstance(_key(key), str), key
    for key in (
        "workflows.port.attachment",
        "workflows.port.services_count",
        "workflows.port.services_open",
        "workflows.port.services_title",
        "workflows.port.services_none",
    ):
        assert isinstance(_key(key), str), key
