"""Configs bulk selection follows tab/scope filtering, not hidden inventory rows."""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from app.utils import COLUMNS_PREFERENCES_DEFAULTS

SCRIPT = Path(__file__).resolve().parents[3] / "src/ui/app/static/js/pages/configs.js"


@pytest.mark.parametrize(
    "filters, expected",
    [({"type": "HTTP"}, [0, 1]), ({"scope": "global"}, [0, 2]), ({"scope": "service"}, [1, 3]), ({"type": "STREAM", "scope": "global"}, [2])],
)
def test_filter_changes_deselect_hidden_rows_but_keep_visible_selection(filters, expected):
    """Execute the real filter setter and predicate with a minimal DataTables boundary."""
    node = shutil.which("node")
    if not node:
        pytest.skip("node is needed to exercise the configs filter callbacks")
    source = SCRIPT.read_text(encoding="utf-8")
    callbacks = source[source.index("const setFilters =") : source.index('$(".config-type-tab").on("click"')]
    script = """
const assert = require('node:assert/strict');
const configs = [
  {type: 'http', service: 'global'},
  {type: 'http', service: 'app.example.com'},
  {type: 'stream', service: 'global'},
  {type: 'stream', service: 'app.example.com'},
];
let currentType = '', currentScope = 'all';
const normalizeType = (type) => type.replaceAll('-', '_').toUpperCase();
const rowConfig = (node) => configs[node.index];
const $ = () => ({each() {}, val() {}});
$.fn = {dataTable: {ext: {search: []}}};
const selected = new Set([0, 1, 2, 3]);
let visible;
const dt = {
  row: (index) => ({node: () => ({index})}),
  draw() {
    visible = configs.map((_, i) => i).filter((i) =>
      $.fn.dataTable.ext.search.every((filter) => filter({nTable: {id: 'configs'}}, [], i)));
  },
  rows({search}) {
    assert.equal(search, 'removed');
    assert.ok(visible, 'draw must apply the new filter before deselecting');
    return {deselect() {
      for (const i of selected) if (!visible.includes(i)) selected.delete(i);
    }};
  },
};
"""
    script += callbacks
    script += f"\nsetFilters({json.dumps(filters)});\nassert.deepEqual([...selected], {json.dumps(expected)});"
    script += "\nsetFilters({type: '', scope: 'all'});\n"
    script += f"assert.deepEqual([...selected], {json.dumps(expected)}, 'showing rows again must not reselect them');"
    result = subprocess.run([node, "-e", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_all_tab_and_scope_controls_use_the_filter_setter():
    source = SCRIPT.read_text(encoding="utf-8")
    for selector, event, argument in (
        (".config-type-tab", "click", "{ type: this.dataset.type }"),
        ("#configs-type-select", "change", "{ type: this.value }"),
        (".config-scope-tab", "click", "{ scope: this.dataset.scope }"),
    ):
        handler = source.split(f'$("{selector}").on("{event}", function () {{', 1)[1].split("\n  });", 1)[0]
        assert f"setFilters({argument})" in handler


def test_reset_columns_uses_compact_defaults_without_overwriting_saved_choices():
    assert COLUMNS_PREFERENCES_DEFAULTS["configs"] == {str(index): index == 3 for index in range(3, 9)}
    assert "bw-configs-console-initialized" not in SCRIPT.read_text(encoding="utf-8")


def test_fresh_configs_hidden_columns_match_compact_reset_defaults():
    source = SCRIPT.read_text(encoding="utf-8").split("columnDefs: [", 1)[1].split("layout:", 1)[0]
    hidden = set()
    for targets in re.findall(r"\{\s*visible:\s*false,\s*targets:\s*(\[[\d,\s]+\]|\d+)\s*\}", source):
        indexes = json.loads(targets)
        hidden.update(indexes if isinstance(indexes, list) else [indexes])
    assert hidden == {int(index) for index, visible in COLUMNS_PREFERENCES_DEFAULTS["configs"].items() if not visible}
