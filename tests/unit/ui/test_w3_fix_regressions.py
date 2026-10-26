"""Regressions found by the W3 live UI walk: buttons and loading-page i18n."""

import re
import shutil
import subprocess
from pathlib import Path

import pytest

JS = Path(__file__).resolve().parents[3] / "src/ui/app/static/js"


def test_button_preparation_preserves_unknown_strings_and_registered_buttons():
    node = shutil.which("node")
    if not node:
        pytest.skip("node is needed to exercise the shared button adapter")
    source = (JS / "dataTableInit.js").read_text(encoding="utf-8")
    prepare = source[source.index("function bwPrepareTableButtons(") : source.index("let bwCloseColumnPopover;")]
    script = """
const assert = require('node:assert/strict');
const $ = {fn: {dataTable: {ext: {buttons: {
  copy: {}, colvis: {}, colvisRestore: {}, collection: {},
}}}}};
const t = (key, fallback) => fallback;
const options = {
  layout: {topStart: {buttons: [
    '<hr>', 'copy', 'colvis', 'colvisRestore',
    {extend: 'collection', buttons: ['unknown-html', 'copy', 'colvisRestore']},
  ]}},
};
"""
    script += prepare
    script += """
bwPrepareTableButtons(options, t);
const buttons = options.layout.topStart.buttons;
assert.equal(buttons[0], '<hr>', 'unknown strings must retain the DataTables HTML fallback');
assert.deepEqual(buttons[1], {extend: 'copy'});
assert.equal(buttons[2].extend, undefined);
assert.ok(buttons[2].className.includes('bw-columns-button'));
assert.equal(typeof buttons[2].action, 'function');
assert.equal(buttons.length, 4, 'colvisRestore must still be filtered');
assert.deepEqual(buttons[3].buttons, ['unknown-html', {extend: 'copy'}]);
"""
    result = subprocess.run([node, "-e", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_bans_actions_use_a_real_collection_divider():
    source = (JS / "pages/bans.js").read_text(encoding="utf-8")
    actions = source.split('{ extend: "unban_ips"', 1)[1].split('"button.set_1h"', 1)[0]
    assert '"separator"' not in actions
    assert re.search(r'\{\s*extend:\s*"spacer",\s*style:\s*"dropdown-divider"\s*\}', actions)


def test_utils_language_event_listeners_are_guarded_when_i18next_is_missing():
    source = (JS / "utils.js").read_text(encoding="utf-8")
    guarded = list(re.finditer(r'(?m)^(?P<indent>[ \t]*)if \(typeof i18next !== "undefined"\) \{\n[\s\S]*?^(?P=indent)\}', source))
    listeners = list(re.finditer(r"\bi18next\.on\(", source))
    assert listeners, "the banner's language-change listener must remain registered"
    for listener in listeners:
        assert any(block.start() < listener.start() < block.end() for block in guarded), "i18next can be absent on /loading"


@pytest.mark.parametrize("event", ["column-visibility.dt", "buttons-action.dt"])
def test_column_defaults_compare_effective_visibility_not_sparse_preferences(event):
    source = (JS / "dataTableInit.js").read_text(encoding="utf-8")
    handler = source.split(f'"{event}"', 1)[1]
    comparison = handler.split("const isDefault =", 1)[1].split(";", 1)[0]
    assert "Object.entries(defaultColsVisibility).every(" in comparison
    assert "dataTable.column(key).visible() === value" in comparison
    assert "JSON.stringify" not in comparison
