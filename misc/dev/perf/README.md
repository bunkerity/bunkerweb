# UI performance: measuring before optimising

Lots A (measurement), B (the common path) and C (the critical pages) of the web-UI performance work. Everything here exists to answer one question with numbers
instead of impressions: **what does a page render cost, and where does the time go?**

Two things make that answerable at any moment, in any environment, with no tooling to install:

- **`Server-Timing`** on every UI response — `api;dur=<ms>;desc="<n> calls", app;dur=<ms>,
  total;dur=<ms>`, plus `cache;desc="<n> hits"` when the per-request memo answered something.
  Readable in the browser's network panel. The split between `api` and `app` is the useful part:
  it says which of the two services to go and look at.
- **`X-Request-ID`** on the response, sent along with every API call the render made and echoed
  by the API. One page render, one id, both logs.

Neither is sampled or behind a flag. A number you have to switch on is a number nobody has when
it matters.

## Taking a measurement

`measure.py` logs into a running UI and reports p50/p95, the call count and the HTML size for a
handful of pages.

```bash
python3 misc/dev/perf/measure.py --base http://127.0.0.1:7000 --label "20 services"
```

`seed.py` creates draft services through the API so the same pages can be measured at 1, 20, 100
and 500 services:

```bash
python3 misc/dev/perf/seed.py --api http://127.0.0.1:8888 --count 100
```

Both take credentials from `--username` / `--password` (default `admin` / `P@ssw0rd`, the dev
stack's).

## What the baseline says (2026-08-18)

Measured on the dev images with the UI and API each on one worker, MariaDB, no BunkerWeb
instance attached — so these are *shapes*, not absolute numbers to hold anyone to. Twelve runs
per page after a warm-up, median and 95th percentile in milliseconds.

| Page | calls | p50 @0 svc | @20 | @100 | @500 | HTML @20 | @100 | @500 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `/home` | 14–15 | 138 | 154 | 162 | 173 | 150 KB | 155 KB | 182 KB |
| `/services` | 9 | 179 | 150 | 185 | **483** | 291 KB | 834 KB | **3.5 MB** |
| `/instances` | 7 | 110 | 114 | 117 | 121 | 144 KB | 144 KB | 144 KB |
| `/reports` | 6 | 124 | 116 | 117 | 117 | 149 KB | 149 KB | 149 KB |
| `/global-settings` | 7 | — | 241 | 248 | 253 | 379 KB | 379 KB | 379 KB |

Three findings worth acting on, in that order:

1. **Every page pays a fixed 5–6 call toll before it renders anything of its own**: `/metadata`,
   `/users/{name}`, `/users/{name}/permissions`, `/plugins`, `/global_settings`, and the page's
   column preferences. That is Lot B's target — one bootstrap contract, or a short-lived
   per-request cache.
2. **Duplicates inside a single render.** `/home` asks for `/metadata` twice, `/global_settings`
   twice and `/instances` twice; `/instances` asks for `/metadata` twice. Each duplicate is a
   route repeating what the shared context already fetched.
3. **`/services` is the only page that scales with the estate, and it scales linearly** — 291 KB
   of HTML at 20 services, 834 KB at 100, **3.5 MB at 500**, with p50 going 150 → 185 → 483 ms
   and the API half of it going 71 → 111 → 364 ms. The table renders every row server-side;
   only two of the thirteen tables in the UI are `serverSide`. That is Lot C, and it is the
   single largest number in this table.

   Every other page is flat in the service count, which is the useful half of the finding: the
   fixed toll in (1) is what makes them all cost 110–250 ms whatever the install looks like.

`p95` is noisy on a laptop running the stack, the browser and the test runner at once: single
samples of 700–900 ms show up on pages whose p50 is 120 ms. Treat p95 here as "there is jitter",
not as a budget. Budgets belong on a quiet machine, and the regression guard that runs in CI
counts **calls**, not milliseconds — see `tests/unit/ui/test_home_call_budget.py`.

## What Lot B changed (2026-08-18)

Two findings from the baseline, both fixed, both measured on the same stack and the same
scenarios.

### 1. Duplicates inside a render — a per-request memo

`BaseApiClient` memoises idempotent GETs for the span of one request. The cache is opened by
`perf.start()` in `before_request`, closed by `perf.finish()` in `teardown_request`, and lives in
a `ContextVar` so threaded workers never share one. Any non-GET the request makes empties it, so
a page that saves and then reads back sees what it wrote.

Deliberately **not** a cross-request cache: this one cannot go stale, because nothing outside
the request can change while it is open. That is what makes it need no invalidation protocol, no
TTL and no agreement between UI workers.

`/home` went from 14–15 calls to **12 calls + 2 memo hits**; no page issues a duplicate any more.

Entries are copied in and out. Callers treat a response as theirs and edit it in place, and one
of them did: `Config.get_plugins()` built its id-keyed dict with `plugin.pop("id")`, so once the
shared context had listed the plugins, `/global-settings/plugins/<p>` and
`/services/<s>/plugins/<p>` resolved theirs from a memo entry with no `id` left in it and
answered **500 `KeyError: 'id'`**. Both the mutation and the sharing are fixed — the copy is what
stops the next such caller from being a bug. It costs 2.9 ms on the largest response in the
product and nothing measurable on the 2 KB metadata that is actually fetched twice.

### 2. The fixed toll — a slim plugin payload

Every page fetched `/plugins?type=all` once to draw the sidebar's plugin list. That response is
**212 KB and 27 ms**, of which the declared settings schema is 95%. `with_settings=false` returns
the identities only — **11 KB and 5.5 ms** — and the shared context asks for the slim shape unless
the page actually renders settings (`SETTINGS_HUNGRY_PATH_PREFIXES` in `src/ui/app/utils.py`:
`/global-config`, `/global-settings`, `/services`, `/plugins`).

The parameter defaults to *on* API-side, so the scheduler, the CLI and every settings page are
untouched. `tests/unit/ui/test_plugins_payload.py` fails if a template starts reading the schema
from a page that is not on the list — the failure mode otherwise is silent (an empty shelf), and
it caught two readers this list was originally missing.

### Before / after, same stack, same scenarios

p50 in milliseconds; "calls" is the render's own count from `Server-Timing`.

| Page | calls before → after | @0 svc | @20 | @100 | @500 |
| --- | --- | --- | --- | --- | --- |
| `/home` | 14–15 → **12** (+2 memo hits) | 138 → **121** | 154 → **125** | 162 → **125** | 173 → **132** |
| `/instances` | 7 → 7 | 110 → **90** | 114 → **88** | 117 → **90** | 121 → **94** |
| `/reports` | 6 → 6 | 124 → **87** | 116 → **87** | 117 → **89** | 117 → **86** |
| `/services` | 9 → 9 | 179 → 126 | 150 → 154 | 185 → 192 | 483 → 490 |
| `/global-settings` | 7 → 7 | — | 241 → 243 | 248 → 258 | 253 → 258 |

Read it as **−25% on every page that is not a settings page**, and flat on the two that are —
which is the intended shape: `/services` and `/global-settings` render the schema, so they still
pay for it. Their numbers are Lot C's problem, not Lot B's.

The millisecond figures carry the same laptop jitter as the baseline. The deterministic halves of
the result are the call count (14–15 → 12) and the payload (212 KB → 11 KB), and those are what
the unit tests pin.

## What Lot C changed (2026-08-18)

`/services` was the only page that scaled with the estate. Both halves of its cost turned out to
be something other than what the baseline suggested.

### 1. The API half was not the service list — it was `/configs`

At 500 services the page's three calls measured `/services` **14 ms**, `/templates` **14 ms**, and
`/configs?with_drafts=true&with_data=false` **379 ms — returning an empty payload**.

`get_custom_configs()` merges each service's template-provided configs, and it found the template
by matching *any* setting key starting with `<service>_` and treating its value as a template id.
Every service carries an `IS_DRAFT`, so on 500 services that was half a million prefix tests and
**500 queries for a template named `"no"`**. `get_custom_config()` (singular) forty lines below
already did the right thing: read `<service>_USE_TEMPLATE`. The merge now does the same, and reads
each distinct template once instead of once per service.

**287 ms → 22 ms** at the DB layer; the endpoint goes 379 ms → 22 ms.

This was also a **correctness** bug, which is how the regression test catches it: a template whose
id happened to equal another setting's value was applied to services that never declared it. The
test creates a template called `no` and asserts nobody inherits it.

### 2. The HTML half was the actions column, not the rows

3.31 MB of `<tbody>` for 501 rows — **6.9 KB per row, 73% of it the six action buttons**, whose
markup is identical for every service apart from the id and two flags. They are now built by the
column renderer in `static/js/pages/services.js`, so they exist for the ten rows on screen and
nowhere else. The cell carries a `|`-packed payload of the four per-row facts.

**3.47 MB → 1.09 MB (−69%)**, 6925 → 1939 bytes per row.

Two things this had to get right, both verified in a browser rather than by unit test:

- The payload lives in the cell **content**, not in `data-` attributes. DataTables' Responsive
  plugin builds the collapsed child row from the column's *rendered data*, not from the DOM — a
  first attempt that patched the DOM in `drawCallback` left the expanded row showing an "Actions"
  heading and no buttons.
- `render` returns markup for `display` only. Left in the search index, the payload made a search
  for `yes` match all 500 deletable services against a column that shows no text at all.

The generated markup keeps its `data-i18n` attributes rather than resolving strings once, so
switching language still retranslates the buttons without a redraw (verified: EN → FR).

### Still open for Lot C

- 11 of 13 tables still render every row server-side. Only `/services` was measurably affected by
  it, and it is now 1.09 MB at 500 services; the rest are flat in the estate size.
- `limit=500` is the client default and pages that show a count pull 500 rows to get it
  (`test_home_call_budget.py` records the certificate card doing exactly that).
- The four remaining bootstrap calls — `/metadata`, `/users/{n}`, `/users/{n}/permissions`,
  `/global_settings?methods=true` — are 4–7 ms each. A bootstrap contract would collapse them
  into one, and that is now worth ~15 ms, not the ~50 ms it looked like before the plugin payload
  shrank.

### A caveat on the wall-clock numbers

The Lot C measurements were taken while another session was saturating the same laptop (load
average 7.6), and page p50s swung by 3× between consecutive runs. The numbers quoted above are
therefore the ones that do not depend on machine load: direct DB timings, single-endpoint curl
medians, and byte counts. `/services` p50 was measured at **490 ms → 211 ms** at 500 services
before the machine got busy, which is consistent with a 357 ms API saving, but treat the p50 as
indicative and the component measurements as the result.
