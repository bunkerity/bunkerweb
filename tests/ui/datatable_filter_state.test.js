const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const source = fs.readFileSync(
  path.join(__dirname, "../../src/ui/app/static/js/dataTableInit.js"),
  "utf8",
);
const context = vm.createContext({ console, window: {} });
vm.runInContext(source, context);

test("serializes nested SearchPanes state as request parameters", () => {
  const entries = context.collectDataTableSearchPaneEntries({
    searchPanes: { country: ["FR", "DE"], status: [403] },
  });

  assert.deepEqual(JSON.parse(JSON.stringify(entries)), [
    ["searchPanes[country][0]", "FR"],
    ["searchPanes[country][1]", "DE"],
    ["searchPanes[status][0]", "403"],
  ]);
});

test("combines search, ordering, and panes without duplicating entries", () => {
  const params = {
    search: { value: "blocked" },
    columns: [{ data: "date" }, { data: "ip" }],
    order: [{ column: 1, dir: "asc" }],
    searchPanes: { country: ["FR"] },
    "searchPanes[country][0]": "FR",
  };
  const state = context.getDataTableStateParams({
    ajax: { params: () => params },
  });

  assert.deepEqual(JSON.parse(JSON.stringify(state)), {
    search: "blocked",
    order_column: "ip",
    order_dir: "asc",
    "searchPanes[country][0]": "FR",
  });
});
