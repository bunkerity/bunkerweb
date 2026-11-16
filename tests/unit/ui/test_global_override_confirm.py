"""Port of dev 9b75d80c4: say which global settings "Apply to all services" pushes, and confirm it.

The toggle on /global-settings makes a save copy the globals changed in THAT save onto every service
(routes/global_settings.py `changed_variables`). Before this port a tooltip was the only hint, and
nothing listed the services about to be overwritten. Three things are pinned here:

* the compose pane's wording and the confirmation modal it renders (services listed, outside the
  form, absent when there is no service to overwrite or on a service page);
* the catalog keys, in all 19 catalogs and in the generated gettext files;
* the behaviour of the confirm in JS, run in Node: the modal opens only with the toggle on and a
  changed setting, cancel keeps the form, confirm re-submits once.
"""

import json
import shutil
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_compose_page_assembly import render_pane  # noqa: E402,F401  (pytest fixture, used by name)
from test_compose_page_assembly import _form  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
LOCALES = ROOT / "src" / "ui" / "app" / "static" / "locales"
TRANSLATIONS = ROOT / "src" / "ui" / "translations"
RAW_JS = ROOT / "src" / "ui" / "app" / "static" / "js" / "pages" / "settings-raw.js"

SERVICES = "app.example.com other.example.com"
KEYS = {
    "button.apply_all_services",
    "tooltip.apply_all_services",
    "modal.title.apply_all_services",
    "modal.body.apply_all_services",
    "modal.body.apply_all_services_count",
}


def _global_config(server_name=SERVICES):
    config = {"USE_UI": {"value": "no", "method": "default", "global": True}}
    if server_name is not None:
        config["SERVER_NAME"] = {"value": server_name, "method": "scheduler", "global": True}
    return config


class _Modal(HTMLParser):
    """The modal element's subtree: its list items and whether anything in it posts."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.found = False
        self.items = []
        self.named = []
        self.buttons = []
        self._li = False

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if attributes.get("id") == "modal-apply-all-services":
            self.found = True
            self.depth = 1
            return
        if not self.depth:
            return
        if tag not in ("input", "br", "meta", "link", "img", "hr"):
            self.depth += 1
        if attributes.get("name"):
            self.named.append(attributes["name"])
        if tag == "button":
            self.buttons.append(attributes)
        if tag == "li":
            self._li = True
            self.items.append("")

    def handle_endtag(self, tag):
        if self.depth:
            self.depth -= 1
        if tag == "li":
            self._li = False

    def handle_data(self, data):
        if self._li:
            self.items[-1] += data


def _modal(html):
    parser = _Modal()
    parser.feed(html)
    return parser


# ----------------------------------------------------------------------------------- wording


def test_the_toggle_says_only_changed_settings_are_applied(render_pane):  # noqa: F811
    html = render_pane(_global_config(), global_page=True)
    assert "Overrides only the global settings" not in html
    assert "Override services" not in html, "the old toggle label is still rendered"
    assert "Apply to all services" in html
    assert "Applies only the global settings changed in this save to all services" in html


# ------------------------------------------------------------------------------------ modal


def test_the_modal_lists_every_service_outside_the_form(render_pane):  # noqa: F811
    html = render_pane(_global_config(), global_page=True)
    modal = _modal(html)
    assert modal.found, "no confirmation modal on the global page"
    assert modal.items == ["app.example.com", "other.example.com"]
    assert "All known services (2)" in html
    assert "Unchanged settings are kept" in html
    assert modal.named == [], "the modal must post nothing"
    assert [button.get("type") for button in modal.buttons[1:]] == ["button", "button"], "the footer buttons must never submit"
    assert 'id="confirm-apply-all-services"' in html
    parser = _form(html)
    assert [name for _, attrs in parser.outside for name in [attrs.get("name")] if name] == []
    assert len([button for button in parser.buttons if button.get("type") == "submit"]) == 1


def test_a_service_name_is_escaped_in_the_modal(render_pane):  # noqa: F811
    html = render_pane(_global_config("<script>alert(1)</script>.example.com"), global_page=True)
    assert "<script>alert(1)" not in html
    assert _modal(html).items == ["<script>alert(1)</script>.example.com"]


@pytest.mark.parametrize("server_name", ["", "   "])
def test_no_services_means_no_modal(render_pane, server_name):  # noqa: F811
    assert not _modal(render_pane(_global_config(server_name), global_page=True)).found


def test_the_service_page_renders_no_modal(render_pane):  # noqa: F811
    assert not _modal(render_pane(_global_config(), global_page=False, service_id="app.example.com")).found


# ---------------------------------------------------------------------------------- catalogs


def _leaf(data, dotted):
    for part in dotted.split("."):
        data = data[part]
    return data


@pytest.mark.parametrize("locale_file", sorted(LOCALES.glob("*.json")), ids=lambda path: path.stem)
def test_every_locale_carries_the_keys(locale_file):
    data = json.loads(locale_file.read_text(encoding="utf-8"))
    for key in KEYS:
        assert isinstance(_leaf(data, key), str) and _leaf(data, key), f"{locale_file.name} misses {key}"
    assert "{{count}}" in _leaf(data, "modal.body.apply_all_services_count"), f"{locale_file.name} lost the count placeholder"


def test_the_gettext_catalogs_know_the_keys():
    for po in sorted(TRANSLATIONS.glob("*/LC_MESSAGES/messages.po")):
        text = po.read_text(encoding="utf-8")
        for key in KEYS:
            assert f'msgid "{key}"' in text, f"{po.parent.parent.name} misses {key}: run misc/dev/i18n/json_to_po.py"


# ------------------------------------------------------------------------------------ JS in Node


def _block(name):
    source = RAW_JS.read_text(encoding="utf-8")
    begin, end = f"// BEGIN {name}\n", f"  // END {name}\n"
    assert begin in source and end in source, f"settings-raw.js has no `{name}` block"
    return source.split(begin, 1)[1].split(end, 1)[0]


def _node(script):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is needed to execute the UI regression")
    result = subprocess.run([node, "-e", "const assert = require('node:assert/strict');\n" + script], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_a_setting_counts_as_changed_only_when_its_value_moved():
    _node(_block("override-confirm") + """
const originals = new Map([["A", "1"], ["B", "2"], ["USE_X", "no"]]);
const same = new Map([["csrf_token", "t"], ["A", "1"], ["B", "2"], ["USE_X", "no"], ["OVERRIDE_NON_GLOBAL_SERVICES", "yes"]]);
assert.equal(hasChangedGlobalSetting(same, originals), false, "an untouched save changes nothing");
assert.equal(hasChangedGlobalSetting(new Map([["A", "1"], ["B", "3"]]), originals), true);
assert.equal(hasChangedGlobalSetting(new Map([["NEW", "x"]]), originals), true, "a new key is a change");
assert.equal(hasChangedGlobalSetting(new Map([["OVERRIDE_NON_GLOBAL_SERVICES", "yes"], ["csrf_token", "t"]]), new Map()), false);
assert.equal(hasChangedGlobalSetting(new Map([["IS_DRAFT", "yes"], ["B", "2"]]), originals, {isSetting: (key) => key !== "IS_DRAFT"}), false, "a control key is not a setting");
assert.equal(hasChangedGlobalSetting(new Map([["B", "9"]]), originals, {drafted: new Set(["B"])}), false, "a drafted value is never applied");
assert.equal(hasChangedGlobalSetting(new Map([["B", "2"]]), originals, {savedDrafts: new Set(["B"])}), true, "a draft leaving the draft state is applied");
assert.equal(hasChangedGlobalSetting(new Map([["B", "2"]]), originals, {savedDrafts: new Set(["B"]), drafted: new Set(["B"])}), false, "a draft that stays a draft is not");
""")


# A form, a bootstrap modal and the save button, as small as the handler needs them.
_HARNESS = """
const on = (target, type, fn, options) => { (target.listeners[type] ||= []).push({fn, options}); };
const element = (id) => ({id, listeners: {}, addEventListener(type, fn, options) { on(this, type, fn, options); },
  removeEventListener(type, fn) { this.listeners[type] = (this.listeners[type] || []).filter((entry) => entry.fn !== fn); },
  focus() { this.focused = true; }});
const fire = (target, type) => {
  const entries = [...(target.listeners[type] || [])];
  entries.forEach((entry) => { if (entry.options && entry.options.once) target.listeners[type] = target.listeners[type].filter((other) => other !== entry); entry.fn({type}); });
};
const modalElement = element("modal-apply-all-services");
const confirmButton = element("confirm-apply-all-services");
let modalShown = 0;
const bootstrap = {Modal: {getOrCreateInstance: (el) => ({show() { modalShown++; }, hide() { fire(el, "hidden.bs.modal"); }})}};
const form = element("compose-form");
form.requestSubmit = (submitter) => { form.submitted = (form.submitted || 0) + 1; form.lastSubmitter = submitter; submitNow(submitter); };
const hasModal = {value: true};
const document = {
  getElementById: (id) => ({"compose-form": form, "modal-apply-all-services": hasModal.value ? modalElement : null, "confirm-apply-all-services": confirmButton})[id] || null,
  body: {appendChild() {}},
};
const $ = () => ({length: 1});
const override = {on: true};
const isOverrideNonGlobalEnabled = () => override.on;
const state = {values: [["csrf_token", "t"], ["USE_X", "no"], ["USE_X", "yes"], ["B", "2"]]};
class FormData { forEach(callback) { state.values.forEach(([key, value]) => callback(value, key)); } }
const makeEvent = (submitter) => { const event = {submitter, prevented: 0, stopped: 0, preventDefault() { event.prevented++; }, stopImmediatePropagation() { event.stopped++; }}; return event; };
const submitNow = (submitter) => { const event = makeEvent(submitter); (form.listeners.submit || []).forEach((entry) => entry.fn(event)); form.lastEvent = event; return event; };
const flush = () => new Promise((resolve) => setTimeout(resolve, 0));
"""


def _compose_script(body):
    return (
        _HARNESS
        + _block("override-confirm")
        + _block("compose-override-confirm")
        + "\n(async () => {\n"
        + body
        + "\n})().catch((error) => { console.error(error); process.exit(1); });\n"
    )


def test_the_confirm_needs_the_toggle_on_and_a_changed_setting():
    _node(_compose_script("""
// toggle off: the submit goes straight through
override.on = false; state.values[3] = ["B", "3"];
let event = submitNow(null);
assert.equal(event.prevented, 0, "toggle off must not hold the submit");
assert.equal(modalShown, 0, "toggle off must not open the modal");
// toggle on, but nothing changed since the page loaded
override.on = true; state.values[3] = ["B", "2"];
event = submitNow(null);
assert.equal(event.prevented, 0);
assert.equal(modalShown, 0, "an untouched save overrides nothing, so it never asks");
// toggle on and a changed setting: held, modal open
state.values[3] = ["B", "3"];
event = submitNow(null);
assert.equal(event.prevented, 1);
assert.equal(event.stopped, 1, "compose-shelf.js must not clear its unsaved-edit guard for a held submit");
assert.equal(modalShown, 1);
// first value wins: a switch flipped off posts its fallback, the checked box is the first value
state.values = [["csrf_token", "t"], ["USE_X", "yes"], ["USE_X", "no"], ["B", "2"]];
modalShown = 0;
event = submitNow(null);
assert.equal(event.prevented, 1, "a flipped switch is a changed setting");
// no modal rendered (no services): never asks
hasModal.value = false;
event = submitNow(null);
assert.equal(event.prevented, 0);
"""))


def test_cancel_keeps_the_form_and_confirm_submits_once():
    _node(_compose_script("""
state.values[3] = ["B", "3"];
const save = element("save");
// cancel (Esc, close or Cancel all end in hidden.bs.modal without the confirm click)
let event = submitNow(save);
assert.equal(event.prevented, 1);
fire(modalElement, "hidden.bs.modal");
await flush();
assert.equal(form.submitted || 0, 0, "cancel must not submit");
assert.equal(save.focused, true, "focus returns to the save button");
// confirm
event = submitNow(save);
fire(confirmButton, "click");
await flush();
assert.equal(form.submitted, 1, "confirm submits exactly once");
assert.equal(form.lastSubmitter, save);
assert.equal(form.lastEvent.prevented, 0, "the confirmed submit is not held again");
// the flag is spent: the next submit asks again
event = submitNow(save);
assert.equal(event.prevented, 1);
"""))


def test_the_raw_save_asks_with_the_same_modal():
    source = RAW_JS.read_text(encoding="utf-8")
    handler = source.split('$(".save-settings").on("click"', 1)[1].split('$(".toggle-draft")', 1)[0]
    assert "hasChangedGlobalSetting(" in handler and "confirmGlobalOverride(" in handler
    assert handler.index("confirmGlobalOverride(") < handler.index('form.appendTo("body").submit()'), "the raw form must not submit before the confirm"
