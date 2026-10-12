const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

test("jobs page columnDefs sort renderers order boolean and status columns correctly", async () => {
  let capturedConfig = null;
  const mockJquery = function () {
    return {
      ready: function (fn) {
        fn();
      },
      val: () => "0",
      trim: () => "",
      find: () => mockJquery(),
      text: () => "",
      data: () => "",
      each: () => {},
      clone: () => mockJquery(),
      removeClass: () => {},
      html: () => {},
      on: () => {},
    };
  };
  mockJquery.fn = { dataTable: { ext: { buttons: {} } } };

  const win = { i18nextReady: false };
  const context = vm.createContext({
    console,
    window: win,
    document: {},
    $: mockJquery,
    DataTable: { render: { select: () => {} } },
    initializeDataTable: (config) => {
      capturedConfig = config;
    },
    bootstrap: { Modal: class {} },
    i18next: { t: (k, fallback) => fallback || k },
    setTimeout: (fn) => {
      win.i18nextReady = true;
      fn();
    },
  });

  const source = fs.readFileSync(
    path.join(__dirname, "../../src/ui/app/static/js/pages/jobs.js"),
    "utf8",
  );
  vm.runInContext(source, context);

  await new Promise((resolve) => setImmediate(resolve));

  assert.ok(capturedConfig, "jobs_config was passed to initializeDataTable");
  const columnDefs = capturedConfig.dataTableOptions.columnDefs;

  // Target 5: Reload column
  const reloadDef = columnDefs.find((c) => c.targets === 5);
  assert.ok(
    reloadDef && reloadDef.render,
    "Reload column has a render function",
  );
  assert.equal(
    reloadDef.render('<i class="bx bx-sm bx-check text-success"></i>', "sort"),
    1,
  );
  assert.equal(
    reloadDef.render('<i class="bx bx-sm bx-x text-danger"></i>', "sort"),
    0,
  );
  assert.equal(
    reloadDef.render(
      '<i class="bx bx-sm bx-check text-success"></i>',
      "display",
    ),
    '<i class="bx bx-sm bx-check text-success"></i>',
  );

  // Target 6: Async column
  const asyncDef = columnDefs.find((c) => c.targets === 6);
  assert.ok(asyncDef && asyncDef.render, "Async column has a render function");
  assert.equal(
    asyncDef.render('<i class="bx bx-sm bx-check text-success"></i>', "sort"),
    1,
  );
  assert.equal(
    asyncDef.render('<i class="bx bx-sm bx-x text-danger"></i>', "sort"),
    0,
  );
  assert.equal(
    asyncDef.render(
      '<i class="bx bx-sm bx-check text-success"></i>',
      "display",
    ),
    '<i class="bx bx-sm bx-check text-success"></i>',
  );

  // Target 7: Last Run column
  const lastRunDef = columnDefs.find((c) => c.targets === 7);
  assert.ok(
    lastRunDef && lastRunDef.render,
    "Last run column has a render function",
  );
  assert.equal(
    lastRunDef.render('<i class="bx bx-sm bx-check text-success"></i>', "sort"),
    2,
  );
  assert.equal(
    lastRunDef.render('<i class="bx bx-sm bx-x text-danger"></i>', "sort"),
    1,
  );
  assert.equal(
    lastRunDef.render(
      '<span data-i18n="status.no_history">No history available.</span>',
      "sort",
    ),
    0,
  );
  assert.equal(
    lastRunDef.render(
      '<i class="bx bx-sm bx-check text-success"></i>',
      "display",
    ),
    '<i class="bx bx-sm bx-check text-success"></i>',
  );
});
