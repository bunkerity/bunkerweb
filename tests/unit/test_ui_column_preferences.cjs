// Regression harness for the DataTables column preferences (BW-446).
// Run: node tests/unit/test_ui_column_preferences.cjs
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const root = path.join(__dirname, "../..");
const source = fs.readFileSync(
  path.join(root, "src/ui/app/static/js/dataTableInit.js"),
  "utf8",
);

// COLUMNS_PREFERENCES_DEFAULTS is the allowlist set_columns_preferences enforces.
function loadServerDefaults() {
  const py = fs.readFileSync(path.join(root, "src/ui/app/utils.py"), "utf8");
  const block = py.match(/^COLUMNS_PREFERENCES_DEFAULTS = (\{[\s\S]*?\n\})/m);
  assert.ok(block, "COLUMNS_PREFERENCES_DEFAULTS not found in utils.py");
  return JSON.parse(
    block[1]
      .replace(/\bTrue\b/g, "true")
      .replace(/\bFalse\b/g, "false")
      .replace(/,(\s*[}\]])/g, "$1"),
  );
}

// Runs initializeDataTable() against fakes and returns what it applied and posted.
function run({
  tableName = "reports",
  defaults,
  db,
  local,
  condition = (column) => column > 2 && column < 11,
  dbReadOnly = false,
}) {
  const applied = [];
  const posts = [];
  const store = new Map();
  if (local !== undefined) store.set(`bw-${tableName}-columns`, local);
  const handlers = {};
  const inputs = {
    "#is-read-only": "False",
    "#db-read-only": dbReadOnly ? "True" : "False",
    "#csrf_token": "token",
    "#home-path": "/home",
    "#columns_preferences_defaults": JSON.stringify(defaults),
    "#columns_preferences": db,
  };

  const chain = (selector) => {
    const node = new Proxy(function () {}, {
      get(_, prop) {
        if (prop === "length") return selector in inputs ? 1 : 0;
        if (prop === "val") return () => inputs[selector];
        return () => node;
      },
      apply: () => node,
    });
    return node;
  };
  const $ = (selector) => chain(selector);
  $.fn = { dataTable: { ext: { buttons: {} } } };
  const windowHandlers = {};
  const windowNode = {
    on: (name, fn) => {
      windowHandlers[name] = fn;
      return windowNode;
    },
  };
  const jq = (selector) => (selector === context.window ? windowNode : $(selector));
  jq.fn = $.fn;

  class FakeDataTable {
    constructor() {
      const chainable = { adjust: () => ({ responsive: { recalc() {} }, draw() {} }) };
      this.columns = Object.assign(() => chainable, chainable);
      this.searchPanes = { container: () => null };
      this.ajax = { params: () => ({}) };
    }
    settings() {
      return [{ aoColumns: [], oFeatures: {}, oLanguage: {} }];
    }
    buttons() {
      return { container: () => null };
    }
    column(key) {
      return {
        visible: (value) => {
          if (value === undefined) return true;
          applied.push([String(key), value]);
        },
      };
    }
    on(name, fn) {
      handlers[name] = fn;
    }
  }

  const context = vm.createContext({
    console: { ...console, error() {} },
    window: {},
    document: {},
    JSON,
    Object,
    Array,
    Set,
    String,
    parseInt,
    DataTable: FakeDataTable,
    FormData: class {
      constructor() {
        this.fields = {};
      }
      append(key, value) {
        this.fields[key] = value;
      }
    },
    fetch: (url, options) => {
      posts.push({ url, fields: options.body.fields });
      return Promise.resolve({ ok: true });
    },
    localStorage: {
      getItem: (key) => (store.has(key) ? store.get(key) : null),
      setItem: (key, value) => store.set(key, String(value)),
      removeItem: (key) => store.delete(key),
    },
    debounce: (fn) => fn,
    applyTranslations() {},
  });
  context.$ = jq;
  vm.runInContext(source, context);

  context.initializeDataTable({
    tableSelector: `#${tableName}`,
    tableName,
    columnVisibilityCondition: condition,
    dataTableOptions: {},
  });

  return {
    applied,
    posts,
    store,
    toggle: (column, state) =>
      handlers["column-visibility.dt"]({}, {}, column, state),
    postedMapping: () =>
      posts.length ? JSON.parse(posts[posts.length - 1].fields.columns_preferences) : null,
  };
}

const defaults = { 3: true, 6: false };
const appliedMap = (result) => Object.fromEntries(result.applied);

test("stale_db_key_is_dropped", () => {
  const r = run({ defaults, db: JSON.stringify({ 3: false, 999: false }) });
  assert.deepEqual(appliedMap(r), { 3: false, 6: false });
  r.toggle(3, false);
  assert.deepEqual(r.postedMapping(), { 3: false, 6: false });
});

test("stale_local_storage_key_is_dropped", () => {
  const r = run({
    defaults,
    db: JSON.stringify({ 3: true, 6: false }),
    local: JSON.stringify({ 3: false, 999: false }),
  });
  assert.deepEqual(appliedMap(r), { 3: false, 6: false });
  r.toggle(3, false);
  assert.deepEqual(r.postedMapping(), { 3: false, 6: false });
  assert.deepEqual(
    JSON.parse(r.store.get("bw-reports-columns")),
    { 3: false, 6: false },
  );
});

test("valid_false_choices_survive", () => {
  const r = run({
    defaults: { 3: true, 4: true, 6: false },
    db: JSON.stringify({ 3: false, 4: true, 6: true }),
  });
  assert.deepEqual(appliedMap(r), { 3: false, 4: true, 6: true });
});

test("new_default_key_gets_default", () => {
  const r = run({ defaults, db: JSON.stringify({ 3: true }) });
  assert.deepEqual(appliedMap(r), { 3: true, 6: false });
  r.toggle(3, false);
  assert.deepEqual(r.postedMapping(), { 3: false, 6: false });
});

test("reports_date_toggle_is_saved", () => {
  const server = loadServerDefaults();
  assert.ok("2" in server.reports, 'Reports defaults must carry "2" (Date)');
  const r = run({
    defaults: server.reports,
    db: JSON.stringify(server.reports),
    condition: (column) => column > 1 && column < 15,
  });
  r.toggle(2, false);
  const posted = r.postedMapping();
  assert.ok(posted, "toggling Date must post");
  assert.equal(posted["2"], false);
  for (const key of Object.keys(posted)) {
    assert.ok(key in server.reports, `server would answer 400 for key ${key}`);
  }
});

test("unknown_column_toggle_is_ignored", () => {
  const r = run({ defaults, db: JSON.stringify(defaults) });
  r.toggle(9, false);
  assert.equal(r.postedMapping(), null);
  assert.equal(r.store.has("bw-reports-columns"), false);
});

test("malformed_local_storage_is_treated_as_absent", () => {
  const r = run({
    defaults,
    db: JSON.stringify({ 3: false, 6: true }),
    local: "{not json",
  });
  assert.deepEqual(appliedMap(r), { 3: false, 6: true });
});

test("null_values_are_treated_as_absent", () => {
  let r = run({ defaults, db: JSON.stringify({ 3: false }), local: "null" });
  assert.deepEqual(appliedMap(r), { 3: false, 6: false });
  r = run({ defaults, db: "null" });
  assert.deepEqual(appliedMap(r), { 3: true, 6: false });
});

test("read_only_database_never_posts", () => {
  const r = run({ defaults, db: JSON.stringify(defaults), dbReadOnly: true });
  r.toggle(3, false);
  assert.equal(r.posts.length, 0);
});
