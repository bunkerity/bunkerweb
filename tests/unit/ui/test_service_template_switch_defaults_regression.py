"""Switching the template of an existing service must load the new template's defaults into the form.

On an existing service the template pane kept showing the values of the saved configuration after the user picked another
template, so saving stored the old template's values as explicit overrides on top of the new one. The page script now resets
the pane of the template that was left and then the pane of the template that was picked, taking the default of every field
the user had not customized and keeping the ones they had. This runs the real ``plugins-settings.js`` under node, with a small
stand-in for jQuery over an in-memory form, fires the ``shown.bs.tab`` handler of the template menu and reads the fields back.
Refs: #3241.
"""

import json
from pathlib import Path
from shutil import which
from subprocess import run

import pytest

SCRIPT = Path(__file__).resolve().parents[3] / "src/ui/app/static/js/plugins-settings.js"

HARNESS = r"""
import { pathToFileURL } from "node:url";

const scenario = JSON.parse(process.argv[3]);
const handlers = [];
const registry = {};

const el = (props) => ({ tag: "input", attrs: {}, classes: new Set(), props: {}, data: {}, value: "", finds: {}, ...props });
const field = (id, type, value, original, dflt) =>
  el({ id, attrs: { type }, value, props: type === "checkbox" ? { checked: value === "yes" } : {}, data: { original, default: dflt } });
const templateDefault = (id, value) => { registry[`#${id}-template`] = [el({ value })]; };

class Jq {
  constructor(els = [], selector = "") {
    this.els = els;
    this.selector = selector;
    this.length = els.length;
    els.forEach((e, i) => { this[i] = e; });
  }
  each(fn) { this.els.forEach((e, i) => fn.call(e, i, e)); return this; }
  find(sel) { return new Jq(this.els.flatMap((e) => e.finds[sel] || []), sel); }
  val(v) { if (v === undefined) return this.els[0] && this.els[0].value; this.els.forEach((e) => { e.value = v; }); return this; }
  prop(k, v) { if (v === undefined) return this.els[0] && this.els[0].props[k]; this.els.forEach((e) => { e.props[k] = v; }); return this; }
  attr(k, v) { if (v === undefined) return this.els[0] && this.els[0].attrs[k]; this.els.forEach((e) => { e.attrs[k] = v; }); return this; }
  data(k, v) { if (v === undefined) return this.els[0] && this.els[0].data[k]; this.els.forEach((e) => { e.data[k] = v; }); return this; }
  hasClass(c) { return Boolean(this.els[0] && this.els[0].classes.has(c)); }
  is(sel) { return sel === "select" && Boolean(this.els[0]) && this.els[0].tag === "select"; }
  addClass(c) { this.els.forEach((e) => e.classes.add(c)); return this; }
  removeClass(c) { this.els.forEach((e) => e.classes.delete(c)); return this; }
  on(event, ...rest) { handlers.push({ selector: this.selector, event, fn: rest[rest.length - 1] }); return this; }
  ready(fn) { fn(); return this; }
}
// every jQuery method the page uses that the form model does not need answers with an empty selection
const wrap = (jq) => new Proxy(jq, { get: (t, k) => (k in t || typeof k === "symbol" ? t[k] : () => wrap(new Jq())) });

const documentJq = new Jq([], "document");
const document = { title: "" };
const $ = new Proxy(
  (arg) => {
    if (typeof arg === "string") return wrap(new Jq(registry[arg] || [], arg));
    if (arg === document) return wrap(documentJq);
    if (typeof arg === "function") return arg();
    return wrap(new Jq(arg && typeof arg === "object" ? [arg] : []));
  },
  { get: (t, k) => (k in t ? t[k] : () => undefined) },
);

// browser libraries the page only touches outside the template switch
const inert = () => new Proxy(function () {}, { get: (t, k) => (typeof k === "symbol" ? undefined : inert()), apply: () => inert() });

const menu = '#templates-dropdown-menu button[data-template-id]';
const button = (id) => el({ data: { "template-id": id, "template-dom-id": id, "bs-target": `#navs-templates-${id}` } });
const buttons = { low: button("low"), web: button("web") };
registry[menu] = Object.values(buttons);
registry["#used-template"] = [el({ value: scenario.used })];
registry["#selected-template"] = [el({ value: scenario.used })];
registry["#selected-mode"] = [el({ value: "easy" })];

// the pane of the template that is left: nothing was customized there, the saved value is the field's original
const lowField = field("LOW_FIELD", "text", "edited-by-user", "saved-low", "saved-low");
registry['.tab-pane[data-template-id="low"]'] = [el({ finds: { "input, select": [lowField] } })];

// the pane of the template that is picked
const plain = field("REVERSE_PROXY_HOST", "text", "saved-host", "saved-host", "saved-host");
const box = field("USE_GZIP", "checkbox", "yes", "yes", "yes");
const custom = field("CLIENT_MAX_BODY_SIZE", "text", "50m", "50m", "10m");
const options = [el({ value: "TLSv1.2", props: { selected: true } }), el({ value: "TLSv1.3", props: { selected: false } })];
const select = el({ id: "SSL_PROTOCOLS", tag: "select", value: "TLSv1.2", finds: { option: options } });
registry['.tab-pane[data-template-id="web"]'] = [el({ finds: { "input, select": [plain, box, custom, select] } })];
templateDefault("REVERSE_PROXY_HOST", "web-template-host");
templateDefault("USE_GZIP", "no");
templateDefault("CLIENT_MAX_BODY_SIZE", "1m");
templateDefault("SSL_PROTOCOLS", "TLSv1.3");
templateDefault("LOW_FIELD", "low-template-value");

Object.assign(globalThis, {
  $, jQuery: $, document,
  window: { location: { pathname: scenario.pathname, href: `http://localhost${scenario.pathname}`, hash: "" } },
  history: { pushState() {} },
  localStorage: { getItem: () => null, setItem() {} },
  requestAnimationFrame: (fn) => fn(),
  debounce: (fn) => fn,
  ace: inert(),
  bootstrap: inert(),
});

await import(pathToFileURL(process.argv[2]).href);

const handler = handlers.find((h) => h.selector === '#templates-dropdown-menu button[data-bs-toggle="tab"]' && h.event === "shown.bs.tab");
if (!handler) throw new Error("no shown.bs.tab handler on the template menu");
handler.fn({ target: buttons.web });

process.stdout.write(JSON.stringify({
  low: lowField.value,
  host: plain.value,
  gzip: box.props.checked,
  size: custom.value,
  selected: Object.fromEntries(options.map((o) => [o.value, o.props.selected])),
  currentTemplate: registry["#selected-template"][0].value,
}));
process.exit(0);
"""


def switch_template(tmp_path, *, pathname="/en/services/app", used="low"):
    harness = tmp_path / "harness.mjs"
    harness.write_text(HARNESS, encoding="utf-8")
    done = run(["node", str(harness), str(SCRIPT), json.dumps({"pathname": pathname, "used": used})], capture_output=True, text=True, timeout=60, check=False)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


def node_runs_es_modules() -> bool:
    """The page script is an ES module in a ``.js`` file, which node only loads without a flag from 22.7 on."""
    if which("node") is None:
        return False
    version = run(["node", "--version"], capture_output=True, text=True, timeout=30, check=False).stdout.strip().lstrip("v").split(".")
    return tuple(int(part) for part in version[:2]) >= (22, 7)


pytestmark = pytest.mark.skipif(not node_runs_es_modules(), reason="node 22.7 or newer is required to run the page script")


@pytest.fixture
def switched(tmp_path):
    return switch_template(tmp_path)


def test_the_picked_template_becomes_the_current_one(switched):
    assert switched["currentTemplate"] == "web"


def test_fields_left_at_their_default_take_the_new_templates_default(switched):
    assert switched["host"] == "web-template-host"
    assert switched["gzip"] is False
    assert switched["selected"] == {"TLSv1.2": False, "TLSv1.3": True}


def test_a_field_the_user_customized_keeps_its_value(switched):
    assert switched["size"] == "50m"


def test_the_pane_of_the_template_that_was_left_goes_back_to_its_saved_values(switched):
    assert switched["low"] == "saved-low"
