"""Service names and instance hostnames must reach the bulk-action modals as text, never as markup (L03-F2).

``SERVER_NAME`` accepts ``<``, ``>``, ``=`` and ``!`` (the setting regex only rejects whitespace, ``+``, ``/``, ``:`` and
uppercase), so a service can be named ``a<img src=x onerror=...>b``. ``services.js`` (bulk convert/delete list and the export
badges) ``instances.js`` (bulk delete list) and ``bans.js`` (the service shown beside a ban in the unban and
update-duration lists) built their list items with a template literal, so ``.attr("data-service-id")``
(which returns the decoded name) was parsed as HTML.

This runs the real functions, cut out of the page scripts by name, with the vendored jQuery over a ``domino`` document, and
reads the modal DOM back. Skipped when node or the repo's ``node_modules/domino`` is absent.
"""

import json
from pathlib import Path
from shutil import which
from subprocess import run

import pytest

ROOT = Path(__file__).resolve().parents[3]
PAGES = ROOT / "src/ui/app/static/js/pages"
JQUERY = ROOT / "src/ui/app/static/libs/jquery/jquery.min.js"
DOMINO = ROOT / "node_modules/domino"

pytestmark = pytest.mark.skipif(which("node") is None or not DOMINO.is_dir(), reason="node and node_modules/domino are required")

# `a<img ...>b` (event handler) and the script + HTML comment tail the verifier used against the export sink
PAYLOADS = [
    "a<img src=x onerror=window.pwned=1>b",
    "a<script>window.vfprobe=1;<!--x",
]

DRIVER = r"""
const fs = require("fs");
const [pagePath, jqueryPath, dominoPath, name, kind, payload] = process.argv.slice(2);
const domino = require(dominoPath);
const win = domino.createWindow("<!doctype html><html><body></body></html>");
const mod = { exports: {} };
new Function("module", "exports", "window", "document", fs.readFileSync(jqueryPath, "utf8"))(mod, mod.exports, win, win.document);
const $ = mod.exports.fn ? mod.exports : mod.exports(win);

// cut the function out of the page script: from `  const <name> = ` to the first `\n  };\n`
const source = fs.readFileSync(pagePath, "utf8");
const start = source.indexOf(`\n  const ${name} = `);
if (start < 0) throw new Error(`${name} not found`);
const end = source.indexOf("\n  };\n", start);
const body = source.slice(start, end + 5);

const shown = [];
const bootstrap = { Modal: function (el) { this.show = () => shown.push(el); } };
const t = (key, fallback) => fallback || key;
const servicesWithConfigs = new Set([payload]);
const ban = { ip: "1.2.3.4", ban_scope: "service", service: payload, time_remaining: "1h" };
const appendDataTableParamsInputs = () => {};
const setupCrowdsecUnban = () => {};
const isLease = () => false;

let root;
let call;
if (kind === "services-modal") {
  win.document.body.innerHTML = '<div id="m"></div>';
  root = "#m";
  call = `${body}\n setupModal([payload], $("#m"));`;
} else if (kind === "services-export") {
  win.document.body.innerHTML =
    '<div id="modal-export-services"></div><div id="selected-services-export"></div><input id="services-export-include-configs" type="checkbox">';
  root = "#selected-services-export";
  call = `${body}\n openExportModal([payload]);`;
} else if (kind === "bans-unban") {
  win.document.body.innerHTML =
    '<div id="selected-ips-unban"></div><div id="modal-unban-ips"><form></form><div class="alert"></div></div><input id="selected-ips-input-unban">';
  root = "#selected-ips-unban";
  call = `${body}\n setupUnbanModal([ban]);`;
} else if (kind === "bans-duration") {
  win.document.body.innerHTML =
    '<div id="selected-ips-update-duration"></div><div id="modal-update-duration"><div class="alert"></div></div><input id="selected-ips-input-update-duration"><input id="custom-end-date">';
  win.document.getElementById("custom-end-date")._flatpickr = {};
  root = "#selected-ips-update-duration";
  call = `${body}\n setupUpdateDurationModal([ban]);`;
} else {
  win.document.body.innerHTML =
    '<div id="modal-delete-instances"><div class="alert"></div></div><div id="selected-instances"></div><input id="selected-instances-input">';
  root = "#selected-instances";
  call = `${body}\n setupDeletionModal([payload]);`;
}

let error = null;
try {
  new Function(
    "$", "bootstrap", "t", "servicesWithConfigs", "payload", "window", "document",
    "ban", "appendDataTableParamsInputs", "setupCrowdsecUnban", "isLease", call,
  )($, bootstrap, t, servicesWithConfigs, payload, win, win.document, ban, appendDataTableParamsInputs, setupCrowdsecUnban, isLease);
} catch (e) {
  error = String(e && e.message || e);
}
const $root = $(root);
process.stdout.write(JSON.stringify({
  error,
  injected: $root.find("img, script").length,
  text: $root.text(),
  shown: shown.length,
}));
"""


def run_driver(tmp_path, page, name, kind, payload):
    driver = tmp_path / "driver.cjs"
    driver.write_text(DRIVER, encoding="utf-8")
    done = run(
        ["node", str(driver), str(PAGES / page), str(JQUERY), str(DOMINO), name, kind, payload],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


CASES = [
    ("services.js", "setupModal", "services-modal"),
    ("services.js", "openExportModal", "services-export"),
    ("instances.js", "setupDeletionModal", "instances-modal"),
    ("bans.js", "setupUnbanModal", "bans-unban"),
    ("bans.js", "setupUpdateDurationModal", "bans-duration"),
]


@pytest.mark.parametrize("payload", PAYLOADS)
@pytest.mark.parametrize(("page", "name", "kind"), CASES, ids=[c[2] for c in CASES])
def test_name_is_inserted_as_text(tmp_path, page, name, kind, payload):
    out = run_driver(tmp_path, page, name, kind, payload)
    assert out["error"] is None
    assert out["injected"] == 0, "the name was parsed as markup"
    assert payload in out["text"], "the name must be shown verbatim as text"
