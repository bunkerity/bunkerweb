"""Execute the shared table and Logs regressions in Node, without a dev stack."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from app.utils import COLUMNS_PREFERENCES_DEFAULTS

ROOT = Path(__file__).resolve().parents[3]
JS = ROOT / "src/ui/app/static/js"


def run_js(script):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is needed to execute the UI regression")
    result = subprocess.run([node, "-e", "const assert = require('node:assert/strict');\n" + script], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize(
    "saved, expected",
    [
        ("{broken", {"2": False, "3": True}),
        ('{"3": false, "99": true}', {"2": True, "3": False}),
        ('{"2": false, "3": true}', {"2": False, "3": True}),
        ('{"2": "false", "3": 0}', {"2": True, "3": True}),
        ("null", {"2": False, "3": True}),
    ],
)
def test_saved_column_preferences(saved, expected):
    source = (JS / "dataTableInit.js").read_text()
    block = source.split("    const defaultColsVisibility =", 1)[1].split("    // Without the second argument", 1)[0]
    run_js(
        """
const $columnsPreferenceDefaults = {val: () => '{"2":true,"3":true}'};
const $columnsPreference = {val: () => '{"2":false,"99":true}'};
let originalColumnsPreferences;
const tableName = 'reports';
const localStorage = {getItem: () => SAVED};
""".replace("SAVED", json.dumps(saved))
        + "const defaultColsVisibility ="
        + block
        + "assert.deepEqual(originalColumnsPreferences, {'2': false, '3': true});\n"
        + f"assert.deepEqual(columnVisibility, {json.dumps(expected)});"
    )


def test_column_visibility_ignores_non_preference_columns():
    source = (JS / "dataTableInit.js").read_text()
    block = source.split("    // Column visibility event", 1)[1].split("    // Override the default colvisRestore", 1)[0]
    run_js(
        """
let handler;
const dataTable = {on: (event, fn) => {handler = fn;}, column: () => ({visible: () => false})};
const defaultColsVisibility = {'2': true};
const columnVisibility = {'2': false};
const columnVisibilityCondition = undefined;
const localStorage = {setItem() {}, removeItem() {}};
const originalColumnsPreferences = {'2': true};
const tableName = 'reports';
const dbReadOnly = false;
let saves = 0;
const saveColumnsPreferences = () => saves++;
"""
        + block
        + """
handler(null, null, 0, true);
assert.deepEqual(columnVisibility, {'2': false});
assert.equal(saves, 0);
handler(null, null, 2, true);
assert.deepEqual(columnVisibility, {'2': true});
assert.equal(saves, 1);
"""
    )


def test_reports_date_default_matches_column_layout():
    source = (JS / "pages/reports.js").read_text()
    columns = source.split("      columns: [\n", 1)[1].split("columnDefs:", 1)[0]
    assert columns.index('data: "date"') < columns.index('data: "id"')
    assert COLUMNS_PREFERENCES_DEFAULTS["reports"]["2"] is True


def test_sort_button_names_use_header_text_and_keep_order_instructions():
    source = (JS / "dataTableInit.js").read_text()
    block = source.split("  applyTranslations();", 1)[1].split("  // Rows are rebuilt", 1)[0]
    run_js(
        r"""
const markup = '<span>Date</span>';
const columns = [{ariaTitle: markup}, {ariaTitle: 'Plain'}];
let title = '  Date \n  locale  ';
let label = markup + ': Activate to sort';
const header = {find: (selector) => selector === '.dt-column-title'
  ? {text: () => title}
  : {length: 1, attr: (name, value) => value === undefined ? label : (label = value)}};
const $ = (value) => value;
const dataTable = {settings: () => [{aoColumns: columns}], column: () => ({header: () => header})};
"""
        + block
        + """
assert.equal(columns[0].ariaTitle, 'Date locale');
assert.equal(label, 'Date locale: Activate to sort');
assert.equal(columns[1].ariaTitle, 'Plain');
title = 'Datum';
syncHeaderAriaTitles();
assert.equal(columns[0].ariaTitle, 'Datum');
assert.equal(label, 'Datum: Activate to sort');
"""
    )
    language_handler = source.split('i18next.on("languageChanged"', 1)[1].split("// Column visibility event", 1)[0]
    assert "syncHeaderAriaTitles();" in language_handler


def test_logs_search_box_tracks_toolbar_overlap_and_resets_when_hidden():
    source = (JS / "pages/logs.js").read_text()
    block = source.split("// ============================ Toolbar wiring", 1)[0].rsplit("    editor.focus();\n  }", 1)[1]
    run_js(
        """
let afterExec, observer;
const events = {};
let queued;
let top = 50;
let bottom = 120;
let box = null;
const editor = {
  get searchBox() {return box ? {element: box} : null;},
  renderer: {scroller: {getBoundingClientRect: () => ({top, height: 300})}},
  commands: {on: (event, fn) => {assert.equal(event, 'afterExec'); afterExec = fn;}},
};
const document = {querySelector: (selector) => {
  assert.equal(selector, '.sticky-card');
  return {getBoundingClientRect: () => ({bottom})};
}};
const window = {addEventListener: (event, fn) => events[event] = fn};
const requestAnimationFrame = (fn) => {queued = fn; return 1;};
const MutationObserver = class {
  constructor(fn) {observer = fn;}
  observe() {}
};
const flush = () => {const fn = queued; queued = null; if (fn) fn();};
"""
        + block
        + """
assert.equal(typeof afterExec, 'function', 'find must register search-box placement');
afterExec();
box = {style: {display: '', transform: ''}, offsetHeight: 40};
afterExec(); flush();
assert.equal(box.style.transform, 'translateY(70px)');
top = -500; events.scroll(); flush();
assert.equal(box.style.transform, 'translateY(260px)', 'must stay inside scroller');
top = 200; events.resize(); flush();
assert.equal(box.style.transform, '');
top = 50; events.scroll(); flush();
box.style.display = 'none'; observer();
assert.equal(box.style.transform, '');
box.style.display = ''; observer(); flush();
assert.equal(box.style.transform, 'translateY(70px)');
"""
    )
    template = (ROOT / "src/ui/app/templates/logs.html").read_text()
    assert 'classes="p-1 mb-4 sticky-card"' in template
