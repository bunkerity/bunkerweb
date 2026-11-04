"""Rendered raw-default JSON must reach the real save handler and omit unchanged defaults.

Explicit defaults, service overrides and resets must still be submitted once.
"""

from html.parser import HTMLParser

import pytest
from _u2_helpers import node_runs_es_modules, run_dom

from test_raw_mode_skips_unchanged_defaults import POLICY_DEFAULT, _render, _setting

pytestmark = pytest.mark.skipif(not node_runs_es_modules(), reason="node 22.7 or newer is required")


class Fields(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.values = {}
        self.textarea = None
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "input" and attrs.get("id"):
            self.values[attrs["id"]] = attrs.get("value", "")
        if tag == "textarea":
            self.textarea = attrs.get("id")
            if self.textarea:
                self.values[self.textarea] = ""

    def handle_data(self, data):
        if self.textarea:
            self.values[self.textarea] += data

    def handle_endtag(self, tag):
        if tag == "textarea":
            self.textarea = None


DRIVER = r"""
for (const [id, value] of Object.entries(scenario.fields)) registry[`#${id}`] = [el({ value })];
registry['#selected-mode'] = [el({ value: 'raw' })];
registry['#raw-config'] = [el({ value: scenario.raw })];
registry['#csrf_token'] = [el({ value: 'csrf-proof' })];
await import(pathToFileURL(process.argv[2] + '/plugins-settings.js').href);
const save = handlers.find((h) => h.selector === '.save-settings' && h.event === 'click');
if (!save) throw new Error('missing save handler');
await save.fn.call(el({}));
console.log(JSON.stringify({ submitted: !!globalThis.submitted,
  fields: globalThis.submitted?.children.map((e) => [e.attrs.name, e.value]) }));
process.exit(0);
"""


@pytest.mark.parametrize("explicit_default", [False, True])
def test_rendered_default_roster_controls_actual_raw_submit(tmp_path, explicit_default):
    settings = {
        "PERMISSIONS_POLICY": _setting(POLICY_DEFAULT),
        "USE_ANTIBOT": _setting("no"),
        "USE_GZIP": _setting("no"),
        "SERVER_NAME": _setting(""),
    }
    config = {
        "PERMISSIONS_POLICY": {"value": POLICY_DEFAULT, "method": "default"},
        "USE_ANTIBOT": {"value": "no", "method": "ui"},
        "USE_GZIP": {"value": "yes", "method": "ui"},
        "SERVER_NAME": {"value": "app.example.com", "method": "ui"},
    }
    fields = Fields(_render(config, settings)).values
    raw = "SERVER_NAME=app.example.com"
    if explicit_default:
        raw += f"\nPERMISSIONS_POLICY={POLICY_DEFAULT}"
    out = run_dom(tmp_path, DRIVER, {"fields": fields, "raw": raw})
    assert out["submitted"] is True
    posted = dict(out["fields"])
    assert posted["csrf_token"] == "csrf-proof"
    assert posted["SERVER_NAME"] == "app.example.com"
    assert posted["USE_ANTIBOT"] == "no"
    assert posted["USE_GZIP"] == "no"
    assert ("PERMISSIONS_POLICY" in posted) is explicit_default
    if explicit_default:
        assert posted["PERMISSIONS_POLICY"] == POLICY_DEFAULT
    assert len(out["fields"]) == len(posted), "raw submit posted duplicate keys"
