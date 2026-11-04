"""Extend the existing page-script DOM double for controls and submitted forms."""

import json
from pathlib import Path
from subprocess import run

from test_service_template_switch_defaults_regression import HARNESS, node_runs_es_modules

ROOT = Path(__file__).resolve().parents[3]
JS = ROOT / "src/ui/app/static/js"
JQUERY_DOM = HARNESS.split("// browser libraries", 1)[0]

DOM = r"""
const makeNode = (tag) => {
  const n = el({ tag, children: [], dataset: {}, listeners: {}, className: "" });
  n.setAttribute = (k, v) => { n.attrs[k] = String(v); };
  n.getAttribute = (k) => n.attrs[k] ?? null;
  n.removeAttribute = (k) => { delete n.attrs[k]; };
  n.append = (...nodes) => { nodes.forEach((child) => { child.parent = n; n.children.push(child); }); };
  n.addEventListener = (event, fn) => { n.listeners[event] = fn; };
  n.focus = () => {};
  n.scrollIntoView = () => {};
  n.classList = {
    add: (...cs) => cs.forEach((c) => n.classes.add(c)),
    remove: (...cs) => cs.forEach((c) => n.classes.delete(c)),
    contains: (c) => n.classes.has(c),
  };
  n.querySelectorAll = (selector) => n.children.flatMap((child) => {
    const match = selector.startsWith(".") ? child.className.split(" ").includes(selector.slice(1)) : child.tag === selector;
    return [...(match ? [child] : []), ...child.querySelectorAll(selector)];
  });
  n.querySelector = (selector) => n.querySelectorAll(selector)[0] || null;
  let html = "", text = "";
  Object.defineProperty(n, "innerHTML", {
    get: () => html,
    set: (value) => { html = String(value); text = ""; n.children = []; },
  });
  Object.defineProperty(n, "textContent", {
    get: () => text,
    set: (value) => { text = String(value); html = ""; n.children = []; },
  });
  return n;
};

document.createElement = makeNode;
document.getElementById = (id) => registry[`#${id}`]?.[0] || null;
document.querySelectorAll = () => [];
document.querySelector = () => null;
Jq.prototype.append = function(child) {
  this.els.forEach((e) => { e.children ||= []; e.children.push(...(child instanceof Jq ? child.els : [child])); });
  return this;
};
Jq.prototype.appendTo = function() { return this; };
Jq.prototype.children = function() { return wrap(new Jq(this.els.flatMap((e) => e.children || []))); };
Jq.prototype.submit = function() { globalThis.submitted = this.els[0]; return this; };
const oldFind = Jq.prototype.find;
Jq.prototype.find = function(selector) {
  const children = this.els.flatMap((e) => e.children || []);
  if (!children.length) return oldFind.call(this, selector);
  const name = selector.match(/name=['"]([^'"]+)['"]/);
  return wrap(new Jq(children.filter((e) => !name || e.attrs.name === name[1])));
};

const pageDollar = new Proxy($, {
  apply(target, that, args) {
    if (typeof args[0] === "string" && /^<(form|input|textarea)>$/.test(args[0])) {
      const tag = args[0].slice(1, -1);
      return wrap(new Jq([el({ tag, attrs: args[1] || {}, value: args[1]?.value ?? "", children: [] })]));
    }
    return Reflect.apply(target, that, args);
  },
});
const inert = () => new Proxy(function () {}, { get: (t, k) => (typeof k === "symbol" ? undefined : inert()), apply: () => inert() });
Object.assign(globalThis, {
  $: pageDollar, jQuery: pageDollar, document,
  window: { location: { pathname: "/en/services/app", href: "http://localhost/en/services/app", hash: "" } },
  history: { pushState() {} },
  localStorage: { getItem: () => null, setItem() {} },
  requestAnimationFrame: (fn) => fn(), debounce: (fn) => fn,
  ace: inert(), bootstrap: inert(), applyTranslations() {},
});
"""


def run_dom(tmp_path, body, scenario=None, script=JS):
    harness = tmp_path / "u2-dom.mjs"
    harness.write_text(JQUERY_DOM + DOM + body, encoding="utf-8")
    done = run(["node", str(harness), str(script), json.dumps(scenario or {})], capture_output=True, text=True, timeout=15, check=False)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


__all__ = ["JS", "node_runs_es_modules", "run_dom"]
