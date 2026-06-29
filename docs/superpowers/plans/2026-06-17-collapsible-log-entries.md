# Collapsible Multi-line Log Entries — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let operators fold the noisy continuation lines (Python tracebacks, JSON payloads, gunicorn config dumps) under their header log line in the `/logs` ACE viewer, via native ACE code-folding.

**Architecture:** Add a custom ACE **FoldMode** to the existing `ace/mode/bunkerweb_log` so every structured log line that is followed by continuation lines (lines that do NOT start a new structured entry) gets a gutter fold chevron and a `Traceback (N lines)` / `⋯ N lines` placeholder pill. A "Collapse multi-line" toggle in the filter bar folds/unfolds them all; default expanded. Folding is a pure view-layer concern on the editor session, independent of the level-filter / tail / local-time pipeline.

**Tech Stack:** Vanilla JS + jQuery + ACE editor (vendored), Bootstrap 5.3.3, Jinja2, BoxIcons. No new dependencies.

**Design inspiration (from the Stitch "Collapsible Trace" sketch):** the collapsed row keeps its severity tint (header line stays red for ERROR / amber for WARNING via the existing tokenizer), a small rounded **pill at the line end** shows `Traceback (3 lines)` for tracebacks or `⋯ N lines` otherwise, and a **gutter chevron** toggles it. No JSON re-pretty-printing (the source text is already as-written) and no per-fold severity CSS class (the header row's own tint carries severity).

## Global Constraints

- **Do NOT `git commit`.** Stage changes only; the user commits. (Project rule.)
- Extend the existing ACE mode file; do not add a JS/CSS framework. ACE only — no Prism/hljs.
- BoxIcons only (`bx bx-*`); **no hex literals in templates**; colors live in `pages/logs.css`.
- i18n: every user-facing string via `data-i18n*` (template) or `t("key", "fallback")` (JS); keys added to `static/locales/en.json` only (other locales fall back to en).
- Match the existing mode file's `ace.define` + relative-require patterns (mirror `libs/ace/src-min/mode-nginx.js`, which ships a working FoldMode under `ace/mode/folding/cstyle`).
- `node --check` + `prettier --check` (JS/HTML/CSS/JSON) must pass; `black`/`py_compile` unaffected (no Python change).
- The new fold script lives **inside** the existing `src/ui/app/static/js/pages/ace-mode-bunkerweb_log.js` (one more `ace.define` block), loaded by the existing classic-`defer` `<script>` — no new template script tag.
- Live-test caveat: the UI serves static with `Cache-Control: max-age=86400`. To see JS/CSS changes in the browser, temporarily append `?v=<token>` to the `logs.css` + `ace-mode-bunkerweb_log.js` + `logs.js` refs in `logs.html`, then revert before finishing.

## File Structure

| File | Responsibility | Change |
| --- | --- | --- |
| `src/ui/app/static/js/pages/ace-mode-bunkerweb_log.js` | Tokenizer + Mode + **new FoldMode** | Modify — add `isLogStart()` shared predicate, an `ace/mode/folding/bunkerweb_log` `ace.define` block, and wire `this.foldingRules` on the Mode |
| `src/ui/app/static/js/pages/logs.js` | Editor wiring | Modify — add `state.collapse`, wire the toggle button (`foldAll`/`unfold`), re-apply on `renderView` |
| `src/ui/app/templates/logs.html` | Filter bar | Modify — add the "Collapse multi-line" toggle button next to "Local time" |
| `src/ui/app/static/css/pages/logs.css` | Per-page styles | Modify — style `.ace_fold` as a pill (both themes) |
| `src/ui/app/static/locales/en.json` | i18n | Modify — add `button.collapse_multiline`, `tooltip.collapse_multiline`, `aria.label.collapse_multiline`, `logs.fold_lines`, `logs.fold_traceback` |
| `/tmp/test-foldmode.js` | Throwaway node test of the fold rules | Create (not committed) |

---

### Task 1: FoldMode — detect foldable multi-line groups

**Files:**
- Modify: `src/ui/app/static/js/pages/ace-mode-bunkerweb_log.js`
- Test: `/tmp/test-foldmode.js` (throwaway)

**Interfaces:**
- Produces: a module `ace/mode/folding/bunkerweb_log` exporting `FoldMode` (extends ACE `BaseFoldMode`) with `getFoldWidget(session, foldStyle, row) -> "start" | ""` and `getFoldWidgetRange(session, foldStyle, row) -> Range | undefined` (the returned `Range` carries a `.placeholder` string). Also a module-scoped `isLogStart(line) -> boolean`.
- Consumes (from existing file): the same five log-format shapes the tokenizer recognizes.

- [ ] **Step 1: Write the failing test** — `/tmp/test-foldmode.js` loads the real mode file under an `ace` stub (same technique already used in this repo's node tests), grabs the captured `ace/mode/folding/bunkerweb_log` factory, runs it with stub deps, and exercises the FoldMode against a fake session.

```js
const fs = require("fs");
const src = fs.readFileSync(
  "/home/bunkerity/dev/bunkerweb-dev/src/ui/app/static/js/pages/ace-mode-bunkerweb_log.js",
  "utf8",
);
const ace = { _m: {}, define(id, d, f) { this._m[id] = f; }, require() {} };
new Function("ace", "module", "exports", src)(ace, {}, {});

// Stub deps for the fold module factory.
const oop = { inherits: (c, s) => { c.prototype = Object.create(s.prototype); c.prototype.constructor = c; } };
function BaseFoldMode() {}
function Range(sr, sc, er, ec) { this.start = { row: sr, column: sc }; this.end = { row: er, column: ec }; }
const req = (id) => {
  if (id === "../../lib/oop") return oop;
  if (id === "./fold_mode") return { FoldMode: BaseFoldMode };
  if (id === "../../range") return { Range: Range };
  throw new Error("unexpected require " + id);
};
const exp = {};
ace._m["ace/mode/folding/bunkerweb_log"](req, exp, {});
const FoldMode = exp.FoldMode;
const fm = new FoldMode();

const mkSession = (lines) => ({ getLine: (r) => lines[r], getLength: () => lines.length });

let fail = 0;
const ok = (cond, name) => { console.log((cond ? "✓ " : "✗ ") + name); if (!cond) fail++; };

// A Python traceback block: header (ERROR) + 3 indented continuation lines.
const tb = mkSession([
  "[2026-06-17 14:33:01 +0000] [SCHEDULER] [1] [ERROR] - Boom",
  '  File "x.py", line 5, in run',
  "    raise ConnectionError",
  "ConnectionError: refused",
  "[2026-06-17 14:33:02 +0000] [SCHEDULER] [1] [INFO] - next entry",
]);
ok(fm.getFoldWidget(tb, "markbegin", 0) === "start", "header row is foldable");
ok(fm.getFoldWidget(tb, "markbegin", 1) === "", "continuation row not foldable");
ok(fm.getFoldWidget(tb, "markbegin", 4) === "", "single-line next entry not foldable");
const r = fm.getFoldWidgetRange(tb, "markbegin", 0);
ok(r && r.start.row === 0 && r.end.row === 3, "range spans header end .. last continuation");
ok(r && r.start.column === tb.getLine(0).length, "range starts at end of header line");
ok(r && /Traceback \(3 lines\)/.test(r.placeholder), "traceback placeholder labelled with count");

// A generic (non-traceback) multi-line block -> "⋯ N lines".
const json = mkSession([
  "[2026-06-17 14:33:03 +0000] [API] [9] [INFO] - Current configuration:",
  "  config: utils/gunicorn.conf.py",
  "  workers: 1",
  "[2026-06-17 14:33:04 +0000] [API] [9] [INFO] - ready",
]);
const r2 = fm.getFoldWidgetRange(json, "markbegin", 0);
ok(r2 && r2.end.row === 2 && /⋯ 2 lines/.test(r2.placeholder), "generic block -> ⋯ 2 lines");

// A lone log line (no continuation) is NOT foldable.
const lone = mkSession([
  "[2026-06-17 14:33:05 +0000] [UI] [2] [INFO] - hello",
  "[2026-06-17 14:33:06 +0000] [UI] [2] [INFO] - world",
]);
ok(fm.getFoldWidget(lone, "markbegin", 0) === "", "lone log line not foldable");
ok(fm.getFoldWidgetRange(lone, "markbegin", 0) === undefined, "lone log line range undefined");

console.log(fail ? "\nFAILURES: " + fail : "\nALL FOLD CHECKS PASSED");
process.exit(fail ? 1 : 0);
```

- [ ] **Step 2: Run it to confirm it fails**

Run: `node /tmp/test-foldmode.js`
Expected: throws `unexpected require` / `Cannot read properties of undefined` (the `ace/mode/folding/bunkerweb_log` module does not exist yet).

- [ ] **Step 3: Add the shared `isLogStart` predicate** near the top of `BunkerWebLogHighlightRules` scope, but at **module scope** so the fold module can use it. Place it just after the `ace.define("ace/mode/bunkerweb_log_highlight_rules", …)` block closes, before the Mode define. Add this standalone helper define-free constant + function at the top of the file (module scope, outside any `ace.define`):

```js
// Shared: does a line START a structured log entry? (the 5 formats the
// tokenizer recognizes). Anything else is a continuation line — a traceback,
// JSON, config dump, or blank/indented line — and folds under its header.
var BWLOG_START_RE =
  /^(?:\[[^\]]*\] \[[^\]]*\] \[\d+\] \[|[\d-]+ [\d:,]+ \[[^\]]*\] \[\d+\] \[|[\d-]+ [\d:,]+:(?:DEBUG|INFO|NOTICE|WARNING|ERROR|CRITICAL):|\d{4}\/\d\d\/\d\d \d\d:\d\d:\d\d \[|\S+ \S+ - \S+ \S+ \[[^\]]*\] ")/u;
function bwlogIsLogStart(line) {
  return typeof line === "string" && BWLOG_START_RE.test(line);
}
```

- [ ] **Step 4: Add the FoldMode `ace.define` block.** Place it immediately AFTER the `ace.define("ace/mode/bunkerweb_log", …)` block and BEFORE the trailing `(function(){ ace.require([...]) })()` IIFE.

```js
ace.define(
  "ace/mode/folding/bunkerweb_log",
  [
    "require",
    "exports",
    "module",
    "ace/lib/oop",
    "ace/mode/folding/fold_mode",
    "ace/range",
  ],
  function (require, exports, module) {
    "use strict";
    var oop = require("../../lib/oop");
    var BaseFoldMode = require("./fold_mode").FoldMode;
    var Range = require("../../range").Range;

    var FoldMode = (exports.FoldMode = function () {});
    oop.inherits(FoldMode, BaseFoldMode);

    (function () {
      // Foldable when this row starts a log entry AND the next row is a
      // continuation (does not itself start a log entry).
      this.getFoldWidget = function (session, foldStyle, row) {
        var line = session.getLine(row);
        if (!bwlogIsLogStart(line)) return "";
        var next = session.getLine(row + 1);
        if (next === undefined || bwlogIsLogStart(next)) return "";
        return "start";
      };

      // Fold from the END of the header line to the end of the last
      // continuation line, so the header stays visible with a pill at its end.
      this.getFoldWidgetRange = function (session, foldStyle, row) {
        var line = session.getLine(row);
        if (!bwlogIsLogStart(line)) return;
        var maxRow = session.getLength();
        var end = row;
        while (end + 1 < maxRow && !bwlogIsLogStart(session.getLine(end + 1))) {
          end++;
        }
        if (end === row) return; // no continuation -> not foldable
        var count = end - row;
        var firstCont = session.getLine(row + 1) || "";
        var isTrace =
          /^\s*(?:Traceback \(most recent call last\)|File ")/.test(firstCont) ||
          /Traceback \(most recent call last\)/.test(firstCont);
        var range = new Range(
          row,
          line.length,
          end,
          session.getLine(end).length,
        );
        range.placeholder = isTrace
          ? " Traceback (" + count + " lines) "
          : " ⋯ " + count + " lines ";
        return range;
      };
    }).call(FoldMode.prototype);
  },
);
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `node /tmp/test-foldmode.js`
Expected: `ALL FOLD CHECKS PASSED`.

- [ ] **Step 6: `node --check` + format**

Run: `node --check src/ui/app/static/js/pages/ace-mode-bunkerweb_log.js && npx --no-install prettier --write src/ui/app/static/js/pages/ace-mode-bunkerweb_log.js`
Expected: `JS OK`, prettier rewrites cleanly.

- [ ] **Step 7: Stage (no commit)**

Run: `git add src/ui/app/static/js/pages/ace-mode-bunkerweb_log.js`
(Do not commit — the user commits.)

---

### Task 2: Wire the FoldMode onto the Mode

**Files:**
- Modify: `src/ui/app/static/js/pages/ace-mode-bunkerweb_log.js`

**Interfaces:**
- Consumes: `ace/mode/folding/bunkerweb_log` `FoldMode` (Task 1).
- Produces: the `ace/mode/bunkerweb_log` Mode now sets `this.foldingRules`, so ACE renders gutter fold widgets on foldable rows automatically.

- [ ] **Step 1: Add the fold-mode dependency + assignment** in the existing `ace.define("ace/mode/bunkerweb_log", …)` block. Add `"ace/mode/folding/bunkerweb_log"` to its dependency array, require it, and set `this.foldingRules` in the Mode constructor.

```js
// dependency array — add the fold module id:
//   "ace/mode/bunkerweb_log_highlight_rules",
//   "ace/mode/folding/bunkerweb_log",
var BunkerWebLogFoldMode =
  require("./folding/bunkerweb_log").FoldMode;

var Mode = function () {
  TextMode.call(this);
  this.HighlightRules = BunkerWebLogHighlightRules;
  this.foldingRules = new BunkerWebLogFoldMode();
  this.$behaviour = this.$defaultBehaviour;
};
```

- [ ] **Step 2: `node --check`**

Run: `node --check src/ui/app/static/js/pages/ace-mode-bunkerweb_log.js && echo OK`
Expected: `OK`.

- [ ] **Step 3: Live smoke test (gutter chevrons appear).** Temporarily cache-bust + restart is NOT needed (static file, mounted). Cache-bust the mode + css + logs.js refs in `logs.html` with `?v=fold1`, then in the browser (logged in, `/logs?file=bw-ui.log` — it has gunicorn multi-line config dumps) run in the console / via Playwright:

```js
const ed = ace.edit(document.getElementById("raw-logs"));
// foldable rows should report a "start" fold widget
const fr = ed.session.getFoldWidget ? null : null;
// simplest check: ask the session for fold widgets across rows
let foldable = 0;
for (let r = 0; r < ed.session.getLength(); r++) {
  if (ed.session.getFoldWidget(r) === "start") foldable++;
}
console.log("foldable rows:", foldable); // expect > 0 on bw-ui.log
```

Expected: `foldable rows: > 0` and visible chevron triangles in the gutter next to the config-dump header lines.

- [ ] **Step 4: Stage (no commit)**

Run: `git add src/ui/app/static/js/pages/ace-mode-bunkerweb_log.js`

---

### Task 3: "Collapse multi-line" toggle (template + JS)

**Files:**
- Modify: `src/ui/app/templates/logs.html` (filter bar, next to `#logs-localtime`)
- Modify: `src/ui/app/static/js/pages/logs.js`
- Modify: `src/ui/app/static/locales/en.json`

**Interfaces:**
- Consumes: `editor.session.foldAll()` / `editor.session.unfold()` (ACE), and the existing `renderView(opts)` + `state` object in `logs.js`.
- Produces: a `#logs-collapse` toggle button; `state.collapse` boolean; folds re-applied after each `renderView` when on.

- [ ] **Step 1: Add the toggle button** in `logs.html`, immediately after the `#logs-localtime` button (inside the same `.ms-auto` filter-bar group):

```jinja
<button id="logs-collapse"
        type="button"
        class="btn btn-sm btn-outline-secondary"
        aria-pressed="false"
        data-bs-toggle="tooltip"
        data-bs-placement="top"
        data-i18n-title="tooltip.collapse_multiline"
        title="Collapse multi-line entries (tracebacks, payloads)"
        data-i18n-aria-label="aria.label.collapse_multiline"
        aria-label="Collapse multi-line entries">
    <i class="bx bx-collapse-vertical" aria-hidden="true"></i>
    <span class="d-none d-lg-inline">&nbsp;<span data-i18n="button.collapse_multiline">Collapse</span></span>
</button>
```

(If `bx-collapse-vertical` is absent in the vendored BoxIcons build, fall back to `bx-collapse` — verify with `grep -o '\.bx-collapse[a-z-]*:before' src/ui/app/static/fonts/boxicons.min.css`.)

- [ ] **Step 2: Add `state.collapse` + the toggle handler + re-apply hook** in `logs.js`. In the `state` object add `collapse: false`. After the `renderView` definition, make folds re-apply: at the END of `renderView`, before the `if (opts.toBottom)` line, add:

```js
if (state.collapse) editor.session.foldAll();
```

Wire the button (place near the other filter-bar wiring, e.g. after the `localTimeBtn` block):

```js
const collapseBtn = document.getElementById("logs-collapse");
if (collapseBtn)
  collapseBtn.addEventListener("click", function () {
    state.collapse = !state.collapse;
    this.classList.toggle("active", state.collapse);
    this.setAttribute("aria-pressed", String(state.collapse));
    if (state.collapse) editor.session.foldAll();
    else editor.session.unfold();
  });
```

- [ ] **Step 3: Add i18n keys** to `static/locales/en.json` — `button.collapse_multiline`, `tooltip.collapse_multiline`, `aria.label.collapse_multiline`, plus (used by Task 1's placeholder, surfaced for completeness even though ACE renders it) `logs.fold_lines` / `logs.fold_traceback`. Insert into the matching nested blocks:

```jsonc
// in "button": { ... }
"collapse_multiline": "Collapse",
// in "tooltip": { ... }
"collapse_multiline": "Collapse multi-line entries (tracebacks, payloads)",
// in "aria": { "label": { ... } }
"collapse_multiline": "Collapse multi-line entries",
// in "logs": { ... }
"fold_lines": "⋯ {{count}} lines",
"fold_traceback": "Traceback ({{count}} lines)",
```

- [ ] **Step 4: Validate + format**

Run:
```bash
node --check src/ui/app/static/js/pages/logs.js
python3 -c "import json;json.load(open('src/ui/app/static/locales/en.json'));print('en.json valid')"
npx --no-install prettier --write src/ui/app/static/js/pages/logs.js src/ui/app/templates/logs.html src/ui/app/static/locales/en.json
```
Expected: JS OK, `en.json valid`, prettier clean.

- [ ] **Step 5: Live test the toggle.** With cache-bust active, on `/logs?file=bw-ui.log`:

```js
const ed = ace.edit(document.getElementById("raw-logs"));
const before = ed.session.getAllFolds().length;        // 0
document.getElementById("logs-collapse").click();
const after = ed.session.getAllFolds().length;          // > 0
document.getElementById("logs-collapse").click();
const reset = ed.session.getAllFolds().length;          // 0
return { before, after, reset, active: false };
```
Expected: `before: 0`, `after: > 0`, `reset: 0`. Visually: clicking once collapses every config dump / traceback to a one-line pill; clicking again expands them.

- [ ] **Step 6: Stage (no commit)**

Run: `git add src/ui/app/templates/logs.html src/ui/app/static/js/pages/logs.js src/ui/app/static/locales/en.json`

---

### Task 4: Style the fold pill + verify full behaviour

**Files:**
- Modify: `src/ui/app/static/css/pages/logs.css`

**Interfaces:**
- Consumes: ACE renders the fold placeholder inside a `.ace_fold` span on the (still severity-tinted) header line.
- Produces: a small rounded pill look for `.ace_fold` in both themes, matching the Stitch sketch.

- [ ] **Step 1: Add `.ace_fold` styling** (append to `logs.css`). The header row keeps its own severity tint (red/amber) from the tokenizer; the pill is a subtle chip that reads on top of it.

```css
/* Collapsed multi-line entry: a small chip at the end of the header line
   (gutter chevron is ACE-native). The header row keeps its severity tint. */
.ace-cloud9-day .ace_fold,
.ace-cloud9-night .ace_fold {
  background: rgba(127, 127, 127, 0.18);
  border: 1px solid rgba(127, 127, 127, 0.32);
  border-radius: 0.75rem;
  padding: 0 0.45rem;
  margin-left: 0.4rem;
  color: inherit;
  box-shadow: none;
  font-size: 0.85em;
  vertical-align: baseline;
}
.ace-cloud9-day .ace_fold:hover,
.ace-cloud9-night .ace_fold:hover {
  background: rgba(127, 127, 127, 0.28);
}
```

- [ ] **Step 2: Format**

Run: `npx --no-install prettier --write src/ui/app/static/css/pages/logs.css && npx --no-install prettier --check src/ui/app/static/css/pages/logs.css`
Expected: clean.

- [ ] **Step 3: Full live verification (cache-bust active), `/logs?file=bw-ui.log`, both themes.** Confirm, via Playwright:
  1. Gutter chevrons on config-dump / traceback header rows.
  2. Click "Collapse multi-line" → config dumps collapse to a pill reading `⋯ N lines`; any traceback reads `Traceback (N lines)`; header line keeps its severity color.
  3. Click a single chevron → that one group expands/collapses independently.
  4. **Copy** (`#copy-logs`) → clipboard contains the FULL text including folded lines:

```js
// after collapsing all:
const ed = ace.edit(document.getElementById("raw-logs"));
ed.selectAll();
return ed.getSelectedText().includes("config: utils/gunicorn.conf.py"); // expect true (folded content still copied)
```

  5. **Search** (Ctrl-F) for a string inside a folded block → ACE auto-expands to the match.
  6. Toggle a level chip / change Lines selector while collapsed → after the view rebuilds, folds re-apply (because `renderView` calls `foldAll` when `state.collapse`).
  7. Dark theme: repeat 1–2, confirm the pill is legible on `#181818`.

- [ ] **Step 4: Revert the cache-bust** in `logs.html` (remove every `?v=fold1`), re-run `prettier --check` on the four front-end files, and remove `/tmp/test-foldmode.js`.

```bash
grep -c "?v=" src/ui/app/templates/logs.html   # expect 0
rm -f /tmp/test-foldmode.js
```

- [ ] **Step 5: Stage (no commit)**

Run: `git add src/ui/app/static/css/pages/logs.css src/ui/app/templates/logs.html`
(Leave the commit to the user.)

---

## Self-Review

- **Spec coverage:** FoldMode + continuation rule (Task 1) ✓; gutter chevrons via `foldingRules` (Task 2) ✓; "Collapse multi-line" toggle, default-expanded, re-applied on rebuild (Task 3) ✓; `Traceback (N lines)` / `⋯ N lines` pill + severity-tinted header carried by the existing tokenizer (Tasks 1+4) ✓; copy/search fidelity (Task 4 verification) ✓; i18n + a11y (`aria-pressed`, aria-label, BoxIcon `aria-hidden`) (Task 3) ✓; no-JSON-reprettify / no-per-fold-class (scope) ✓.
- **Placeholder scan:** none — every step has concrete code/commands.
- **Type consistency:** `bwlogIsLogStart` (defined Task 1) used in the FoldMode (Task 1) and nowhere else; `FoldMode` export name consistent across Tasks 1–2; `state.collapse` + `editor.session.foldAll()/unfold()/getAllFolds()` consistent Task 3–4; `range.placeholder` set in Task 1 and rendered by `.ace_fold` in Task 4.
- **Known risk:** if ACE's gutter-widget fold does NOT honor `range.placeholder` (uses a fixed `…`), Task 1's pill text won't show. Mitigation in Task 2/3 live tests will reveal it; fallback is to create folds programmatically with `session.addFold(placeholder, range)` in the toggle handler instead of relying on `foldAll`. Note this in the task if the live test shows a bare `…`.
