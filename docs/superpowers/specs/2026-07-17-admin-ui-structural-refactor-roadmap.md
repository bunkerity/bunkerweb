## Purpose

Index/overview doc for the admin Web UI (`src/ui/app/`) **structural** design-kit refactor. Decomposes the work into sub-projects, records sequencing and locked scope decisions, and points to where each sub-project's own spec will live once brainstormed. Read this first before picking up any piece of this effort.

## Context / how we got here

The original session goal (set 2026-07-17) was "the front end design has to be exactly like the one in the Claude Design project (full refactor)," referencing the **BunkerWeb Design System** Claude Design project (`claude.ai/design`, projectId `4e1650b2-e5c5-445a-acc3-a57435060530`), whose `ui_kits/admin/` click-through prototype is the source of truth for the admin-UI visual language.

Mid-session, 3 `AskUserQuestion` answers narrowed that to a **component/token/copy-fidelity** scope (not a structural rebuild):

- "Finish current approach" — continue the in-flight Jinja component-partial-library retrofit (`src/ui/app/templates/components/`), not a pixel-perfect override.
- Profile's mocked-only "API tokens"/"Notifications" tabs — stay excluded (no backing route/DB).
- Auth pages (`login.html`/`totp.html`/`register.html`) — leave as-is, don't redesign to the kit's full-screen wizard treatment.

That narrower scope shipped as a design-fidelity polish pass: 9 template files touched (`home`, `bans`, `services`, `configs`, `support`, `instances`, `reports`, `plugins` — title/copy/icon/color fixes only), reviewed by Criticos (verdict: NEEDS WORK → follow-up applied → clean). See git history / working-tree diff on those files for the concrete changes; not re-described here.

A stop-hook then flagged that this polish pass does not satisfy the literal original goal ("exactly like design, full refactor"). Asked again with that tension made explicit, the user chose: **go full structural refactor** — rebuild page layouts to literally match the design-kit mockups (card-grids, dashboards, etc.), not just tokens/copy/chrome.

**This doc's own scope decisions (locked 2026-07-17):**
- Start with the **Reports** sub-project.
- Profile's API-tokens/Notifications tabs: **stay excluded**, parked as their own future sub-project, not reopened in this pass.
- Auth pages (login/totp/register): **stay as-is**, parked as their own future sub-project, not reopened in this pass.
- Both parked items can be picked up later as their own brainstorm → spec → plan cycles; nothing here forecloses that.

This supersedes the scope note in the persistent-memory entry `1-7-ui-redesign-chantier` (assistant memory, not repo-tracked), which described the *original*, narrower "CSS design-token layer, stack/IA/flows/build all unchanged" plan. That memory should be updated to point here.

## What NOT to redo

The component-partial-library retrofit (Phases 1-3 of the earlier plan) and the design-fidelity polish pass above are **foundation, not obsolete work**:

- The 29 shared Jinja macros under `src/ui/app/templates/components/` (card, modal, tile, badge, table-toolbar, etc.) stay in use — structural rebuilds should still compose from them for chrome/cards/modals/buttons, not hand-roll new markup.
- DataTables-backed data plumbing (`static/js/pages/*.js`, positional `columnDefs`, DB-backed pagination/filtering/search/export) is real, working, production functionality the design kit's simplified fake-data mockups don't have an equivalent for. Where a design-kit mockup imagines a fundamentally different page type (card-grid instead of table, multi-tab dashboard instead of flat log), that IS the structural refactor — but it means **building new UI on top of the existing data/JS layer**, or extending that layer, not deleting working functionality to match a static prototype's simplified fake data.
- Don't re-run the token/copy/icon fixes already shipped — check `git diff`/`git log` on the touched files first if unsure what's already done.

## Sub-projects (decomposition + proposed build order)

Each row is its own future brainstorm → spec (`docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`) → plan → implementation cycle. Order is a proposal, not a hard dependency chain except where noted.

1. **Reports** — _STARTING NOW_. Flat DataTable of blocked-request log rows → tabbed KPI/analytics dashboard (Overview / Attack patterns / Top offenders / Compliance tabs), stat tiles, charts, time-range picker, "Generate PDF" export. Design-kit source: `ui_kits/admin/pages/tables.js` (`reports` section). Self-contained (own route `src/ui/app/routes/reports.py` if present + `static/js/pages/reports.js` + `templates/reports.html`), doesn't block on auth/profile decisions — good first pick.
2. **Logs** — single-file paginated ACE-editor viewer → multi-instance/multi-service live-tailing dashboard (filter pills, level select, "Tailing · N sources" badge, terminal-style stream). Design-kit source: `ui_kits/admin/pages/operate.js` (`logs` section). Needs a new streaming/aggregation data path across instances — bigger backend lift than Reports.
3. **Plugins** — DataTable → marketplace card-grid (tier chips CORE/PRO/Community, per-plugin Enable/Disable switch, Configure cog, Install/Uninstall). Design-kit source: `ui_kits/admin/pages/configure.js` (`plugins` section, lines ~376-543 as of last read). **Blocked on a product decision**: BunkerWeb's data model has no "enable/disable a whole plugin" concept today (plugins are always active once installed; only their settings toggle features) — this needs resolving before layout work starts, not worked around silently.
4. **Templates** — DataTable → 3-col card gallery (per-template icon/color, plugin/config/feature tag badges, "Use template"/"Edit" buttons). Design-kit source: `configure.js` (`templates` section). Likely the easiest structural swap of the remaining pages — more read/browse-oriented, less write-path complexity than Plugins.
5. **Home** — add: onboarding checklist card (install/register-service/MFA/PRO-activation steps), "Top reasons for blocks" table, Upstreams/Certificates KPI tiles, trend-delta secondary mini-tiles (bans active, jobs queued, req/sec with arrows), interactive range-picker (1h/24h/7d/custom). Needs new backend context data that doesn't exist yet (install/MFA/PRO-activation state, historical-comparison values, block-reason breakdown, upstreams feature isn't built per roadmap). Design-kit source: `ui_kits/admin/pages/home.js`.
6. **Bans** — add KPI tile row (Active bans / Expiring ≤1h / Countries / By CRS%) + "Bans by reason" bar-chart card + a "Non-persisted, expire on restart unless USE_REDIS" alert. Needs client-side aggregation of the already-fetched async ban dataset (`POST /bans/fetch`) or a new API aggregation endpoint — the tile/chart values aren't available at Jinja render time today. Design-kit source: `tables.js` (`bans` section).
7. **Services** — action-button visual language (colored Bootstrap outline btn-group → neutral icon-btn-with-colored-hover) + badge-dot status indicators (vs current icon+text pills). This is a **shared-component-level** change (touches `components/badge.html` and the row-action pattern used by many already-retrofitted list pages) — needs a cross-page pass once decided, not a services-only edit.
8. **Configs** — DataTable → the design kit's console-sidebar+editor OR simplified 5-column table concept. Real re-architecture; the design kit's own mockup is arguably a worse UX than the current rich table (loses Method/Service/Status/Template/Checksum columns) — flag this as a product conversation before committing to literal fidelity here, don't just copy it.
9. **Profile** _(parked exclusion lives here)_ — SSO/SAML PRO-upsell card, session KPI tiles (session lifetime, last sign-in — only "active sessions" exists today), Danger zone card (transfer ownership/delete account), multi-method MFA (hardware key, SMS fallback), Session policy card, and — only if explicitly unparked later — the API-tokens/Notifications tabs.
10. **Auth pages** _(parked)_ — login/totp/register full-screen wizard treatment (design kit has dedicated `setup.js`/`totp.js` full-screen chrome), only if explicitly unparked later.

**Not a sub-project, ongoing hygiene**: `web-cache.html`'s Bootstrap `.progress`/badge hit/miss display vs. the design kit's dedicated `wc-stack` segmented-bar + legend-grid pattern — lower priority, optional, can be folded into any nearby pass.

## Status tracking

| # | Sub-project | Status | Spec doc |
|---|---|---|---|
| 1 | Reports | Implemented | Spec: `docs/superpowers/specs/2026-07-17-reports-dashboard-design.md`; Plan: `docs/superpowers/plans/2026-07-17-reports-dashboard.md` |
| 2 | Logs | Implemented — v1 is a UI-host multi-file live-tail over syslog-aggregated instance logs (instance-side tailing rejected: access/error/modsec logs are stdout-only symlinks with no safe read surface); `/logs?file=X` ACE viewer unchanged | Plan: `~/.claude/plans/use-the-claude-design-mcp-rosy-rainbow.md` (Wave 2 combined plan, Phase 3) |
| 3 | Plugins | Implemented — product decision resolved: a real DB-backed `Plugins.enabled` flag (not a `USE_*` mapping) drives FS materialization for external/UI/PRO plugins; core plugins stay bound to their `USE_*` master switch or a locked "Core / always on" chip and cannot be disabled via the API | Plan: `~/.claude/plans/use-the-claude-design-mcp-rosy-rainbow.md` (Wave 2 combined plan, Phase 4) |
| 4 | Templates | Implemented | Plan: `~/.claude/plans/use-the-claude-design-mcp-rosy-rainbow.md` (Wave 2 combined plan, Phase 1A) |
| 5 | Home | Implemented — Upstreams/Certificates/req-sec tiles dropped (no backend, no fake data); range picker rewindows only the new trend chart/mini-tiles, existing 7-day Redis-aggregate widgets stay labelled "last 7 days" | Plan: `~/.claude/plans/use-the-claude-design-mcp-rosy-rainbow.md` (Wave 2 combined plan, Phase 2) |
| 6 | Bans | Implemented — tile #4 is "Permanent bans" (CRS % isn't a stored field) | Plan: `~/.claude/plans/use-the-claude-design-mcp-rosy-rainbow.md` (Wave 2 combined plan, Phase 1B) |
| 7 | Services | Implemented — shared `.icon-btn`/`.row-actions` + status-dot pass across Services, Instances, Configs, Cache and Jobs | Plan: `~/.claude/plans/use-the-claude-design-mcp-rosy-rainbow.md` (Wave 2 combined plan, Phase 1C) |
| 8 | Configs | Implemented — table kept (owner decision, richer than the kit's mockup); chrome/badge polish only, no "Lint all" (no backing endpoint) | Plan: `~/.claude/plans/use-the-claude-design-mcp-rosy-rainbow.md` (Wave 2 combined plan, Phase 1D) |
| 9 | Profile | Parked | — |
| 10 | Auth pages | Parked | — |

Update this table as each sub-project's spec is written and implemented.
