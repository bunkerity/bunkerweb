"""Mouse, focus and reorder regressions from the final UI-port review."""

import json
from pathlib import Path
from shutil import which
from subprocess import run

import pytest

JS = Path(__file__).resolve().parents[3] / "src/ui/app/static/js"


def _node(script, *args):
    binary = which("node")
    if not binary:
        pytest.skip("node is not installed")
    result = run([binary, "-e", script, *map(str, args)], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr


def test_setting_select_dropdown_escapes_clipping_ancestors():
    source = (JS / "components/settings-widgets.js").read_text(encoding="utf-8")
    select_boxes = source.split("const initSelectBoxes =", 1)[1].split("const initPasswordCopy =", 1)[0]
    assert "new bootstrap.Dropdown(trigger," in select_boxes
    assert 'popperConfig: { strategy: "fixed" }' in select_boxes
    # Keep the successful native control, rather than replacing/renaming it for the widget.
    assert "wrapper.append(trigger, list, select)" in select_boxes
    assert 'select.dispatchEvent(new Event("change", { bubbles: true }))' in select_boxes
    assert "trigger.disabled = select.disabled" in select_boxes
    assert "if (!button || select.disabled) return" in select_boxes


@pytest.mark.parametrize("selection", [(3, 3, "none"), (1, 2, "backward")])
def test_offender_search_retains_focus_and_selection_after_rerender(selection):
    _node(
        r"""
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync(process.argv[1], 'utf8');
const section = source.slice(source.indexOf('  function renderTable()'), source.indexOf('  function render(data)'));
const selection = JSON.parse(process.argv[2]);
const document = {activeElement: null};
let search;
function makeSearch() {
  return {type: 'search', value: '203', selectionStart: 0, selectionEnd: 0, selectionDirection: 'none',
    focus() { document.activeElement = this; },
    setSelectionRange(start, end, direction) {
      this.selectionStart = start; this.selectionEnd = end; this.selectionDirection = direction;
    },
  };
}
search = makeSearch();
search.setSelectionRange(...selection);
search.focus();
const host = {
  empty() { if (document.activeElement === search) document.activeElement = {}; search = null; return this; },
  append() { return this; },
  find() { return {0: search, trigger() { search.focus(); return this; }}; },
};
const sandbox = {document, $: () => host, offenders: [{}], visibleOffenders: () => [],
  labels: () => ({}), emptyStateNode: () => ({}), toolbar() { search = makeSearch(); return {}; },
};
vm.createContext(sandbox);
vm.runInContext(section, sandbox);
sandbox.renderTable();
assert.equal(document.activeElement, search, 'rerender dropped search focus');
assert.equal(search.value, '203');
assert.deepEqual([search.selectionStart, search.selectionEnd, search.selectionDirection], selection);
// A refresh while focus is elsewhere must not steal it back into this toolbar.
const outside = {type: 'search'};
document.activeElement = outside;
sandbox.renderTable();
assert.notEqual(document.activeElement, search, 'unrelated search lost focus to offenders');
""",
        JS / "pages/reports-offenders.js",
        json.dumps(selection),
    )


@pytest.mark.parametrize("readonly", [False, True])
@pytest.mark.parametrize("count", [1, 3])
def test_workflow_reorder_recovers_after_filter_clear_and_reset(readonly, count):
    _node(
        r"""
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync(process.argv[1], 'utf8');
const section = source.slice(source.indexOf('  function resetFilters()'), source.indexOf('  function render(focusSelector)'));
const readonly = process.argv[2] === 'true';
const count = Number(process.argv[3]);
const rules = Array.from({length: count}, (_, i) => ({id: 'r' + i}));
const controls = rules.flatMap((rule, index) => ['up', 'down', 'position'].map(direction => ({
  dataset: direction === 'position' ? {wfPos: rule.id} : {wfMove: direction + ':' + rule.id},
  disabled: readonly || (direction === 'up' && index === 0) || (direction === 'down' && index === count - 1),
  setAttribute(name) { if (name === 'disabled') this.disabled = true; },
  removeAttribute(name) { if (name === 'disabled') this.disabled = false; },
})));
const state = {rules, readonly, filter: {q: '', state: '', action: ''}, view: 'list', open: new Set()};
const noop = () => {};
const sandbox = {
  STATE: state,
  filtering: () => !!(state.filter.q || state.filter.state || state.filter.action),
  ruleMatches: () => true,
  translate: () => '',
  ladderEl: {classList: {toggle: noop}, querySelector: () => null,
    querySelectorAll(selector) {
      if (selector.includes('data-wf-move')) return controls;
      return rules.map((rule, index) => ({dataset: {wfItem: rule.id, wfIndex: index}, classList: {toggle: noop}}));
    },
  },
  document: {getElementById: () => null, querySelectorAll: () => []},
};
vm.createContext(sandbox);
vm.runInContext(section, sandbox);
function checkRestored() {
  controls.forEach((control, i) => {
    const index = Math.floor(i / 3), kind = i % 3;
    const expected = readonly || (kind === 0 && index === 0) || (kind === 1 && index === count - 1);
    assert.equal(control.disabled, expected, 'wrong restored reorder state at ' + i);
  });
}
sandbox.applyDisplay();
checkRestored();
for (const field of ['q', 'state', 'action']) {
  state.filter[field] = 'filter';
  sandbox.applyDisplay();
  assert.ok(controls.every(control => control.disabled), 'filter must pause every reorder control');
  state.filter[field] = '';
  sandbox.applyDisplay();
  checkRestored();
  state.filter[field] = 'filter';
  sandbox.applyDisplay();
  sandbox.resetFilters();
  sandbox.applyDisplay();
  checkRestored();
}
""",
        JS / "pages/workflow_editor.js",
        str(readonly).lower(),
        count,
    )
