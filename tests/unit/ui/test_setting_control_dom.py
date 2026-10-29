"""SettingControl builders must attach browser-safe patterns to their actual fields."""

import pytest
from _u2_helpers import node_runs_es_modules, run_dom

pytestmark = pytest.mark.skipif(not node_runs_es_modules(), reason="node 22.7 or newer is required")

DRIVER = r"""
const controls = await import(pathToFileURL(process.argv[2] + '/modules/setting_controls.js').href);
const control = controls.createSettingControl({ entry: { type: scenario.type, regex: scenario.regex }, value: scenario.value });
const read = () => [...control.root.querySelectorAll('input'), ...control.root.querySelectorAll('textarea')]
  .filter((node) => node.type !== 'file').map((node) => ({ pattern: node.getAttribute('pattern'), value: node.value }));
const initial = read();
if (scenario.type === 'multivalue') {
  control.root.children[1].listeners.click();
}
const added = read();
controls.updateSettingControl(control, { entry: { type: scenario.type, regex: '(?i)unsupported' }, value: scenario.value });
console.log(JSON.stringify({ initial, added, updated: read(), value: controls.getSettingControlValue(control) }));
"""


@pytest.mark.parametrize("kind", ["text", "number", "password", "multivalue", "file"])
def test_each_builder_attaches_pattern_and_drops_unsupported_pattern_on_update(tmp_path, kind):
    out = run_dom(tmp_path, DRIVER, {"type": kind, "regex": "^[a-z-]+$", "value": "ab-c"})
    assert out["initial"] == [{"pattern": r"^[a-z\-]+$", "value": "ab-c"}]
    if kind == "multivalue":
        assert out["added"] == [*out["initial"], {"pattern": r"^[a-z\-]+$", "value": ""}]
    assert out["updated"] == [{"pattern": None, "value": "ab-c"}]
    assert out["value"] == "ab-c"
