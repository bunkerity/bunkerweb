"""The Jobs SearchPanes for the Reload and Async columns read the cell's ``@data-order`` value, not its markup.

DataTables stores a cell that carries ``data-order`` as an object (``{display, "@data-order"}``), not as a string. The pane
callbacks called ``.includes("bx-x")`` on that object, which threw ``includes is not a function`` while the panes were built,
so the Jobs table never left its loading state. This runs the real ``jobs.js`` with a stub in place of jQuery and DataTables
and calls the pane callbacks with cells shaped the way DataTables stores them.
"""

from json import loads
from pathlib import Path
from shutil import which
from subprocess import run

import pytest

JOBS_JS = Path(__file__).resolve().parents[3] / "src/ui/app/static/js/pages/jobs.js"

HARNESS = r"""
const fs = require("fs");
const vm = require("vm");

let captured = null;
const proxy = new Proxy(function () {}, {
  get: (target, key) => (key === "val" ? () => "False" : () => proxy),
  apply: () => proxy,
});
function $(selector) {
  if (selector === sandbox.document) return { ready: (fn) => fn(), on() {} };
  return proxy;
}
$.fn = { dataTable: { isDataTable: () => false, ext: { buttons: {} } } };

const sandbox = {
  $,
  window: {},
  document: {},
  DataTable: { render: { select: () => null } },
  initializeDataTable: (config) => { captured = config; },
  setTimeout,
  console,
};
sandbox.globalThis = sandbox;
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync(process.argv[2], "utf8"), sandbox);
// the page waits for the i18next flag before it builds the table
sandbox.window.i18nextReady = true;

setTimeout(() => {
  const out = {};
  for (const def of captured.dataTableOptions.columnDefs) {
    const options = def.searchPanes && def.searchPanes.options;
    if (!options || ![5, 6].includes(def.targets)) continue;
    out[def.targets] = [];
    for (const order of ["0", "1"]) {
      const row = Array(10).fill("");
      row[def.targets] = { display: "<i class='bx bx-check'></i>", "@data-order": order };
      for (const option of options) {
        let result;
        try {
          result = option.value(row);
        } catch (error) {
          result = "threw: " + error.message;
        }
        out[def.targets].push({ order, yes: option.label.includes("bx-check"), result });
      }
    }
  }
  process.stdout.write(JSON.stringify(out));
}, 150);
"""


@pytest.mark.skipif(which("node") is None, reason="node is required to run the page script")
def test_jobs_reload_and_async_panes_filter_on_the_cell_order_value(tmp_path):
    """Each pane option matches exactly the rows whose ``@data-order`` is its own value and never throws."""
    harness = tmp_path / "harness.js"
    harness.write_text(HARNESS, encoding="utf-8")

    done = run(["node", str(harness), str(JOBS_JS)], capture_output=True, text=True, timeout=30, check=False)

    assert done.returncode == 0, done.stderr
    results = loads(done.stdout)
    assert set(results) == {"5", "6"}
    for column, entries in results.items():
        assert len(entries) == 4, f"column {column} should expose a No and a Yes option"
        for entry in entries:
            expected = (entry["order"] == "1") == entry["yes"]
            assert (
                entry["result"] is expected
            ), f"column {column}: option {'Yes' if entry['yes'] else 'No'} on data-order {entry['order']} gave {entry['result']!r}"
