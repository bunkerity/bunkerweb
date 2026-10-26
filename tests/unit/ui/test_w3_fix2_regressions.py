"""Regressions from the second live workflows pass (W3V-8 through W3V-11)."""

import json
from pathlib import Path
from shutil import which
from subprocess import run

import pytest

APP = Path(__file__).resolve().parents[3] / "src/ui/app"
JS = APP / "static/js"


def _node(script, *args):
    binary = which("node")
    if not binary:
        pytest.skip("node is not installed")
    result = run([binary, "-e", script, *map(str, args)], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("button", ["csvHtml5", "excelHtml5", "copyHtml5"])
def test_export_wrappers_forward_the_completion_callback(button):
    _node(
        r"""
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const receiver = {};
let completed = 0;
const cb = () => { completed++; };
const event = {}, dt = {}, button = {};
const config = { exportOptions: { columns: ':visible' } };
const buttons = {};
buttons[process.argv[2]] = { action(e, api, node, options, done) {
  assert.equal(typeof done, 'function', 'Buttons completion callback was dropped');
  assert.equal(done, cb);
  assert.equal(this, receiver);
  assert.equal(e, event);
  assert.equal(api, dt);
  assert.equal(node, button);
  assert.equal(options, config);
  assert.equal(options.exportOptions.format.body('=cmd()'), "'=cmd()");
  done();
  return 'exported';
} };
function $() {}
$.extend = Object.assign;
$.fn = { dataTable: { ext: { buttons }, Buttons: { stripData: value => value } } };
vm.runInNewContext(fs.readFileSync(process.argv[1], 'utf8'), {
  $, window: {}, document: { addEventListener() {} },
});
for (let i = 0; i < 2; i++) {
  assert.equal(buttons[process.argv[2]].action.call(receiver, event, dt, button, config, cb), 'exported');
}
assert.equal(completed, 2);
""",
        JS / "dataTableInit.js",
        button,
    )


# Run the real overview and its delegated handlers with only the DOM/library boundary stubbed.
OVERVIEW_HARNESS = r"""
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const listeners = {};
const modalEvents = {};
const flow = { id: 'flow-1', name: 'Example', services: [] };
const row = { dataset: { workflowId: flow.id } };
let focused = null;
const opener = { isConnected: true, closest: () => row, focus: () => { focused = opener; } };
const replacement = { focus: () => { focused = replacement; } };
const noop = () => {};
const elements = {
  'workflows-data': { value: JSON.stringify([flow]) },
  'workflows': {},
  'workflow-services-list': { classList: { toggle: noop } },
  'workflow-services-detach': { dataset: {} },
  'workflow-services-id': {},
  'workflow-services-modal': {
    addEventListener: (name, fn) => { modalEvents[name] = fn; },
  },
};
const document = {
  getElementById: id => elements[id] || null,
  querySelector: selector => selector.includes('data-workflow-id="flow-1"') ? replacement : null,
  addEventListener(name, fn) { (listeners[name] ||= []).push(fn); },
  createElement() {
    return {
      set innerHTML(value) { this.value = value; },
      get children() {
        return [...this.value.matchAll(/<(a|div)\b[^>]*>(.*?)<\/\1>/gs)]
          .map(match => ({ innerHTML: match[2] }));
      },
    };
  },
};
let options;
const table = { on: noop, search: () => ({ draw: noop }) };
const $ = { fn: { dataTable: { ext: { search: [] } } } };
vm.runInNewContext(fs.readFileSync(process.argv[1], 'utf8'), {
  document, $, CSS: { escape: value => value },
  window: { bootstrap: { Modal: { getOrCreateInstance: () => ({ show: noop }) } } },
  DataTable: { render: { select: noop } },
  initializeDataTable(config) { options = config.dataTableOptions; return table; },
});
listeners.DOMContentLoaded[0]();
"""


@pytest.mark.parametrize("replaced", [False, True], ids=["original-opener", "redrawn-row"])
def test_services_dialog_returns_focus_to_its_workflow(replaced):
    _node(
        OVERVIEW_HARNESS + r"""
const event = { target: { closest: selector => selector === '.workflow-services' ? opener : null } };
listeners.click.forEach(fn => fn(event));
assert.equal(typeof modalEvents['hidden.bs.modal'], 'function', 'Services dialog never restores focus');
opener.isConnected = process.argv[2] !== 'true';
modalEvents['hidden.bs.modal']();
assert.equal(focused, opener.isConnected ? opener : replacement);
""",
        JS / "pages/workflows.js",
        str(replaced).lower(),
    )


@pytest.mark.parametrize("column,parts", [(2, ["name & title", "description"]), (3, ["6 total", "5 active"])])
def test_workflow_export_joins_cell_parts_with_one_space(column, parts):
    _node(
        OVERVIEW_HARNESS + r"""
const column = Number(process.argv[2]);
const parts = JSON.parse(process.argv[3]);
const def = options.columnDefs.find(def => [].concat(def.targets).includes(column));
assert.ok(def && typeof def.render === 'function', 'Name/Rules have no export renderer');
const html = parts.map(value => '<div>' + value.replace(/&/g, '&amp;') + '</div>').join('\n                                             ');
// The shared formatter strips markup/decodes entities after the orthogonal render.
assert.equal(def.render(html, 'export').replace(/&amp;/g, '&'), parts.join(' '));
assert.equal(def.render(html, 'display'), html);
assert.equal(def.render('<a>name</a>', 'export'), 'name');
""",
        JS / "pages/workflows.js",
        column,
        json.dumps(parts),
    )


@pytest.mark.parametrize("close", ["apply", "cancel", "cancel-edited"])
def test_inspector_close_returns_focus_after_render_without_changing_draft_semantics(close):
    _node(
        r"""
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync(process.argv[1], 'utf8');
// Execute the real inspector section, including any focus helper, without booting the editor.
const section = source.slice(source.indexOf('var inspectSnapshot = null;'), source.indexOf('  function removeNode('));
let focused = null;
let renders = 0;
let touches = 0;
const sandbox = {
  STATE: { inspect: null, rules: [{ id: 'rule-1', name: 'before' }] },
  CSS: { escape: value => value },
  ladderEl: { querySelector(selector) {
    if (selector === '.wf-drawer') return { querySelector: () => ({ focus() {} }) };
    if (selector === '[data-wf-inspect="rule-1"]') {
      const generation = renders;
      return { focus(options) { focused = { generation, options }; } };
    }
    return null;
  } },
  render() { renders++; }, paint() {},
  touch() { touches++; renders++; },
  say() {}, translate: () => '', ruleLabel: rule => rule.name,
};
sandbox.ruleById = id => sandbox.STATE.rules.find(rule => rule.id === id);
vm.createContext(sandbox);
vm.runInContext(section, sandbox);
sandbox.inspect('rule-1');
const close = process.argv[2];
if (close === 'apply' || close === 'cancel-edited') sandbox.STATE.rules[0].name = 'changed';
if (close === 'apply') sandbox.inspect(null);
else sandbox.cancelInspect();
assert.ok(focused, 'Closing the inspector dropped focus');
assert.equal(focused.generation, renders, 'Focused stale control from before the ladder render');
assert.equal(focused.options.preventScroll, true);
assert.equal(sandbox.STATE.inspect, null);
assert.equal(sandbox.STATE.rules[0].name, close === 'apply' ? 'changed' : 'before');
assert.equal(touches, close === 'cancel-edited' ? 1 : 0);
""",
        JS / "pages/workflow_editor.js",
        close,
    )


def test_german_challenge_summary_keeps_provider_in_natural_german():
    catalog = json.loads((APP / "static/locales/de.json").read_text(encoding="utf-8"))
    assert catalog["workflows"]["sum"]["challenge"] == "eine {{provider}}-Prüfung anzeigen"


@pytest.mark.parametrize("kind", ["copy", "csv", "excel", "copyHtml5", "csvHtml5", "excelHtml5"])
def test_export_collections_close_by_default_without_overriding_page_choices(kind):
    _node(
        r"""
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const kind = process.argv[2];
const $ = { fn: { dataTable: { ext: { buttons: { [kind]: {} } } } } };
const sandbox = { $, window: {}, document: { addEventListener() {} } };
vm.runInNewContext(fs.readFileSync(process.argv[1], 'utf8'), sandbox);
const choices = [
  { extend: 'collection', buttons: [kind] },
  { extend: 'collection', buttons: [{ extend: kind }] },
  { extend: 'collection', autoClose: false, buttons: [kind] },
  { extend: 'collection', autoClose: true, buttons: [kind] },
  { extend: 'collection', buttons: [{ extend: 'delete' }] },
];
const options = { layout: { topStart: { buttons: choices } } };
sandbox.bwPrepareTableButtons(options, (key, fallback) => fallback);
const buttons = options.layout.topStart.buttons;
assert.equal(buttons[0].autoClose, true, 'Export string collection must auto-close');
assert.equal(buttons[1].autoClose, true, 'Export object collection must auto-close');
assert.equal(buttons[2].autoClose, false, 'Explicit persistent collection must stay persistent');
assert.equal(buttons[3].autoClose, true);
assert.equal('autoClose' in buttons[4], false, 'Non-export collection must stay unchanged');
""",
        JS / "dataTableInit.js",
        kind,
    )
