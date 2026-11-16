"""Offender country cells use the static URL rendered by Flask."""

import shutil
import subprocess
from pathlib import Path

import pytest

JS = Path(__file__).resolve().parents[3] / "src/ui/app/static/js"


@pytest.mark.parametrize("base", ["/img/flags", "/console/img/flags"])
def test_offender_flags_follow_the_rendered_static_base(base):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is needed to exercise country cells")
    script = r"""
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const sandbox = {window: {}, document: {}, bootstrap: {Tooltip: function () {}}};
let render;
const images = [];
function element(selector) {
  const item = {
    0: {}, val(value) { return arguments.length ? this : selector === '#base_flags_url' ? process.argv[3] : 'False'; },
    addClass() { return this; }, text() { return this; }, append() { return this; },
    empty() { return this; }, find() { return {0: null}; }, on() { return this; }, prop() { return this; },
    ready(fn) { fn(); return this; },
    attr(attrs) { if (selector === '<img>') images.push(attrs.src); return this; },
  };
  return item;
}
sandbox.$ = element;
sandbox.window.BWReportsDashboard = {onRangeChange(fn) { render = fn; }};
vm.runInNewContext(fs.readFileSync(process.argv[1], 'utf8'), sandbox);
vm.runInNewContext(fs.readFileSync(process.argv[2], 'utf8'), sandbox);
render({status: 'success', offenders: [
  {ip: '203.0.113.1', country: 'FR', blocks: 2},
  {ip: '203.0.113.2', country: 'unknown', blocks: 1},
]});
assert.deepEqual(images, [process.argv[3] + '/fr.svg', process.argv[3] + '/zz.svg']);
"""
    result = subprocess.run(
        [node, "-e", script, str(JS / "components/country-flag.js"), str(JS / "pages/reports-offenders.js"), base],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
