"""A DataTables export must ship cell *text*, not cell markup.

`dataTableInit.js` wraps the `csvHtml5` / `excelHtml5` / `copyHtml5` buttons to install its own
`format.body/header/footer`, so that a value like `=cmd()` is escaped before it reaches a
spreadsheet. Replacing Buttons' formatters outright removed the step they existed for: their
defaults are what call `stripData`, and `stripData` is what turns a `<td>` full of badges, links
and icons into text. Every CSV / XLSX / clipboard payload carried raw `innerHTML` instead.

The second half is subtler and is why composing needs care. `stripData` reads its flags from its
second argument and skips a step whenever that object is *present* with the flag falsy — in the
vendored bundle, literally `n && !n.stripHtml || (t = stripHtml(t))`. So handing it
`config.exportOptions` (which normally carries `columns`, not `stripHtml`) silently disables
stripping again while *looking* composed. The defaults have to be restated.

Both failure modes are asserted below through the real file, with a spy in place of the library:
the point under test is the composition, not DataTables' own stripping.
"""

from json import loads
from pathlib import Path
from shutil import which
from subprocess import run

import pytest

DATATABLE_INIT = Path(__file__).resolve().parents[3] / "src/ui/app/static/js/dataTableInit.js"

# Loads the real file with a $ stub, fires the patched button action, and reports what the
# formatter did: whether it reached stripData at all, and with which flags.
HARNESS = r"""
const fs = require("fs");
const vm = require("vm");

const calls = [];
function stripData(value, config) {
  calls.push({ value: String(value), config: config });
  // Stand-in for the library: strip tags only when the flags say so, mirroring
  // `n && !n.stripHtml || (t = stripHtml(t))`.
  let out = String(value);
  if (!(config && !config.stripHtml)) out = out.replace(/<[^>]*>/g, "");
  return out;
}

function $(...args) { return args[0]; }
$.extend = Object.assign;
$.fn = { dataTable: { ext: { buttons: {} }, Buttons: { stripData: stripData } } };

const buttons = $.fn.dataTable.ext.buttons;
let seenConfig = null;
for (const name of ["csvHtml5", "excelHtml5", "copyHtml5"]) {
  buttons[name] = { action: function (e, dt, button, config) { seenConfig = config; } };
}

const sandbox = { $, window: {}, document: { addEventListener() {} }, console };
sandbox.globalThis = sandbox;
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync(process.argv[2], "utf8"), sandbox);

// A page that supplies its own exportOptions is the case that used to disable stripping.
const config = { exportOptions: { columns: ":visible" } };
buttons.csvHtml5.action.call(null, null, null, null, config);

const body = seenConfig.exportOptions.format.body;
process.stdout.write(
  JSON.stringify({
    patched: typeof body === "function",
    markup: body('<a href="/x"><i class="bx"></i>&nbsp;app1.example.com</a>'),
    formula: body("=cmd()"),
    plain: body("blacklist"),
    calls: calls,
  }),
);
"""


@pytest.fixture(scope="module")
def node():
    binary = which("node")
    if not binary:
        pytest.skip("node is not installed")
    return binary


@pytest.fixture(scope="module")
def exported(node, tmp_path_factory):
    harness = tmp_path_factory.mktemp("export") / "harness.js"
    harness.write_text(HARNESS, encoding="utf-8")
    result = run([node, str(harness), str(DATATABLE_INIT)], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    return loads(result.stdout)


def test_the_export_formatter_strips_markup_before_it_escapes(exported):
    assert exported["patched"], "the export buttons were not patched at all"
    # The defect: this used to come back with the whole anchor, icon and &nbsp; intact.
    assert exported["markup"] == "&nbsp;app1.example.com"
    assert "<" not in exported["markup"]


def test_the_formatter_reaches_stripdata_with_stripping_switched_on(exported):
    # Composing with the library rather than replacing it is the fix; calling it with flags that
    # disable stripping would pass the test above only by accident of the spy.
    assert exported["calls"], "stripData was never called - the formatter replaced it instead"
    config = exported["calls"][0]["config"]
    assert config["stripHtml"] is True
    assert config["stripNewlines"] is True
    assert config["decodeEntities"] is True
    assert config["trim"] is True
    # The page's own exportOptions still travel through, so nothing it set is lost.
    assert config["columns"] == ":visible"


def test_formula_injection_is_still_escaped(exported):
    # bwCsvSafe stays the single place this happens: `escapeExcelFormula` is deliberately left out
    # of the strip config, so stripData does not also prefix and the value is not escaped twice.
    assert exported["formula"] == "'=cmd()"
    assert exported["plain"] == "blacklist"
