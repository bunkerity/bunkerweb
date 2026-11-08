"""Saving the global settings with USE_PROXY_PROTOCOL turned on asks for confirmation first (#3596).

PROXY protocol makes NGINX refuse every connection without a PROXY header, the web UI included,
so the real save handler must stop on the confirmation modal and only submit once it is confirmed.
"""

import pytest
from _u2_helpers import node_runs_es_modules, run_dom

pytestmark = pytest.mark.skipif(not node_runs_es_modules(), reason="node 22.7 or newer is required")

DRIVER = r"""
// Modal double: showing it records the call, then clicks confirm or just closes, like the user would.
const modals = [];
const once = {};
Jq.prototype.one = function (event, fn) { this.els.forEach((e) => { (once[e.attrs.id] ||= {})[event] = fn; }); return this; };
Jq.prototype.off = function () { return this; };
Jq.prototype.trigger = function () { return this; };
Jq.prototype.has = function () { return wrap(new Jq()); };
// hasChangedGlobalSettings() reads the posted fields as { name, value } pairs
Jq.prototype.toArray = function () { return this.els.map((e) => ({ name: e.attrs.name, value: e.value })); };
Jq.prototype.modal = function (action) {
  const id = this.els[0].attrs.id;
  if (action !== "show") return this;
  modals.push(id);
  const confirmId = { "modal-confirm-proxy-protocol": "confirm-enable-proxy-protocol", "modal-apply-all-services": "confirm-apply-all-services" }[id];
  const confirm = typeof scenario.confirm === "object" ? scenario.confirm[id] : scenario.confirm;
  if (confirm && once[confirmId]?.click) once[confirmId].click();
  once[id]["hidden.bs.modal"]();
  return this;
};
const oldIs = Jq.prototype.is;
Jq.prototype.is = function (sel) { return sel === ":checked" ? Boolean(this.els[0]?.props.checked) : oldIs.call(this, sel); };

for (const id of ["modal-confirm-proxy-protocol", "confirm-enable-proxy-protocol", "modal-apply-all-services", "confirm-apply-all-services"]) {
  if (id.startsWith("modal-") && !scenario.modal && id === "modal-confirm-proxy-protocol") continue;
  registry[`#${id}`] = [el({ attrs: { id } })];
}
const modalFinds = (id, confirmId) => { if (registry[`#${id}`]) registry[`#${id}`][0].finds[`#${confirmId}`] = registry[`#${confirmId}`]; };
modalFinds("modal-confirm-proxy-protocol", "confirm-enable-proxy-protocol");
modalFinds("modal-apply-all-services", "confirm-apply-all-services");

registry["#selected-mode"] = [el({ value: scenario.mode })];
registry["#csrf_token"] = [el({ value: "csrf-proof" })];
registry["#override-non-global-settings"] = [el({ value: scenario.override ? "yes" : "no" })];
registry["#raw-known-keys"] = [el({ value: JSON.stringify({ keys: ["USE_PROXY_PROTOCOL", "USE_GZIP"], multiple: [], multiline: [] }) })];

if (scenario.mode === "raw") {
  registry["#raw-config"] = [el({ value: scenario.raw })];
  registry["#raw-entire-config"] = [el({ value: scenario.saved_raw })];
} else {
  const box = el({ name: "USE_PROXY_PROTOCOL", attrs: { type: "checkbox", name: "USE_PROXY_PROTOCOL", "data-original": scenario.saved, "data-method": "ui" }, props: { checked: scenario.value === "yes" } });
  registry["#navs-modes-advanced .plugin-setting[data-original]"] = [box];
  registry["div[id^='navs-plugins-']"] = [el({ attrs: { id: "navs-plugins-realip" }, finds: { "input, select": [box], ".plugin-setting": [] } })];
}
globalThis.window.location.pathname = "/en/global-settings";

await import(pathToFileURL(process.argv[2] + "/plugins-settings.js").href);
const save = handlers.find((h) => h.selector === ".save-settings" && h.event === "click");
if (!save) throw new Error("missing save handler");
await save.fn.call(el({}));
console.log(JSON.stringify({ modals, submitted: !!globalThis.submitted,
  fields: globalThis.submitted?.children.map((e) => [e.attrs.name, e.value]) || [] }));
process.exit(0);
"""


def save(tmp_path, **scenario):
    scenario = {"mode": "advanced", "modal": True, "confirm": False, "override": False, **scenario}
    return run_dom(tmp_path, DRIVER, scenario)


def test_enabling_proxy_protocol_waits_for_confirmation_and_cancel_keeps_it_unsaved(tmp_path):
    out = save(tmp_path, saved="no", value="yes", confirm=False)
    assert out["modals"] == ["modal-confirm-proxy-protocol"]
    assert out["submitted"] is False


def test_confirming_saves_proxy_protocol_on(tmp_path):
    out = save(tmp_path, saved="no", value="yes", confirm=True)
    assert out["modals"] == ["modal-confirm-proxy-protocol"]
    assert out["submitted"] is True
    assert dict(out["fields"])["USE_PROXY_PROTOCOL"] == "yes"


@pytest.mark.parametrize(("saved", "value"), [("yes", "yes"), ("yes", "no"), ("no", "no")])
def test_no_confirmation_unless_proxy_protocol_is_being_turned_on(tmp_path, saved, value):
    out = save(tmp_path, saved=saved, value=value)
    assert out["modals"] == []
    assert out["submitted"] is True


PROXY_MODAL, OVERRIDE_MODAL = "modal-confirm-proxy-protocol", "modal-apply-all-services"


def test_cancelling_the_apply_to_all_services_prompt_after_confirming_proxy_protocol_saves_nothing(tmp_path):
    out = save(tmp_path, saved="no", value="yes", override=True, confirm={PROXY_MODAL: True, OVERRIDE_MODAL: False})
    assert out["modals"] == [PROXY_MODAL, OVERRIDE_MODAL]
    assert out["submitted"] is False


def test_confirming_both_prompts_saves(tmp_path):
    out = save(tmp_path, saved="no", value="yes", override=True, confirm={PROXY_MODAL: True, OVERRIDE_MODAL: True})
    assert out["modals"] == [PROXY_MODAL, OVERRIDE_MODAL]
    assert out["submitted"] is True
    assert dict(out["fields"])["USE_PROXY_PROTOCOL"] == "yes"


def test_cancelling_proxy_protocol_never_reaches_the_apply_to_all_services_prompt(tmp_path):
    out = save(tmp_path, saved="no", value="yes", override=True, confirm={PROXY_MODAL: False, OVERRIDE_MODAL: True})
    assert out["modals"] == [PROXY_MODAL]
    assert out["submitted"] is False


def test_pages_without_the_modal_save_as_before(tmp_path):
    out = save(tmp_path, saved="no", value="yes", modal=False)
    assert out["modals"] == []
    assert out["submitted"] is True


def test_raw_mode_asks_before_turning_proxy_protocol_on(tmp_path):
    out = save(tmp_path, mode="raw", saved_raw="USE_GZIP=yes", raw="USE_GZIP=yes\nUSE_PROXY_PROTOCOL=yes")
    assert out["modals"] == ["modal-confirm-proxy-protocol"]
    assert out["submitted"] is False


def test_raw_mode_keeps_an_already_enabled_proxy_protocol_without_asking(tmp_path):
    out = save(tmp_path, mode="raw", saved_raw="USE_PROXY_PROTOCOL=yes", raw="USE_PROXY_PROTOCOL=yes")
    assert out["modals"] == []
    assert out["submitted"] is True
