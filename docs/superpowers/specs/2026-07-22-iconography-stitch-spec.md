# BunkerWeb Custom Iconography — Google Stitch Prompt Spec

**Date:** 2026-07-22 · **Branch:** `1.7` · **Status:** Ready to run (paste-into-Stitch)
**Scope:** 42 core-plugin icons + 10 architecture-resource icons = **52 marks**

This document is fully self-sufficient. Paste the prompt cells into Google Stitch as-is
(no API needed). Every prompt cell already embeds the compact style stem, so each row is
paste-ready on its own — you do not need to re-type the global style block per icon.

Grounded in the BunkerWeb Design System:
`.claude/BunkerWeb Design System/README.md`,
`.claude/BunkerWeb Design System/ICONOGRAPHY.md`,
`.claude/BunkerWeb Design System/colors_and_type.css`.

---

## 0. Governance — where custom icons are sanctioned (READ FIRST)

There is a **deliberate tension** with the current brand rules that must be resolved before adoption:

> `ICONOGRAPHY.md` currently states **"Boxicons 2.1 is the only icon set"** and **"No Font Awesome,
> no Lucide, no Heroicons"** for the product UI. This custom set does **not** replace Boxicons — it
> **extends** the brand system into surfaces where a generic glyph font is too weak: identity marks
> for plugins and architecture components.

**Sanctioned for custom icons** (per-subject illustrative marks):

| Surface | Why custom |
| --- | --- |
| Plugin marketplace **cards** (`plugins.html`) | Each plugin deserves a recognizable identity, not a shared `bx-shield` |
| **Templates** page per-template tiles (`templates.html`) | Same identity value, reuses plugin marks |
| **Docs** pages & architecture **diagrams** | Component/plugin recognition at a glance |
| **Marketing** visuals, slide decks, brand collateral | Richer than a monochrome glyph font |

**Boxicons stay** (do **not** replace with custom art):

| Surface | Why Boxicons |
| --- | --- |
| Inline **UI glyphs** — buttons, nav, badges, form affordances, table actions | Consistency, i18n `aria-label` pattern, size classes, zero asset weight |
| Any icon-only **control** | Boxicons carry the established a11y contract (`aria-hidden`, `data-i18n-aria-label`) |
| Status glyphs (check / warning / error), spinners, chevrons | Already canonical in the admin UI |

**Amendment required on adoption:** `ICONOGRAPHY.md` must gain a section
*"Custom illustrative marks (plugins & architecture)"* that (a) carves out the surfaces above,
(b) states Boxicons remain the only **inline UI glyph** set, and (c) points to this spec + the
`assets/plugins/` mirror as the source of truth. Do not ship the icons without that amendment,
or the two documents contradict each other.

---

## 1. Global style block (reusable base prompt)

Paste this once into Stitch when starting a batch, or rely on the per-row stem (each row embeds it).

> **Design a flat, 2-D geometric app icon for a security product called BunkerWeb.** Single solid
> mark, **deep navy `#0b354a`**, on a **transparent** background. Build on a **24 px grid** mindset
> with **2 px-equivalent strokes** or clean solid shapes. Use **squared / right-angle corners** that
> echo a brick-and-battlement motif (the brand's signature). **One accent color is allowed**:
> **signature green `#2eac68`** — used **only** for pro / security-*positive* concepts (allow, verified,
> encrypted, pro tier); **amber `#ffab00`** — used **sparingly**, only for warning / watched concepts.
> Motif language is **geometric and abstract**: bricks, diamonds, square tiles, nodes, gauges.
> **Flat only.** No gradients, no 3-D, no bevels, no drop shadows, no inner glow, no text/letters,
> no numerals inside the mark. Silhouette must read at **20 px**.

**Negative-prompt guidance (append to any prompt that drifts):**

> Negative: no photorealism, no skeuomorphism, no realistic textures, no gradients or gradient meshes,
> no 3-D / isometric / extruded look, no drop shadows or glows, no thin-line "hipster" hairline style,
> no hand-drawn / sketchy strokes, no emoji, no embedded text or numbers, no rainbow palettes,
> no background fill or card behind the mark, no rounded blobby corners.

**Compact style stem** (this exact string is prepended in every prompt cell below):

> *Flat 2-D geometric icon, single deep-navy #0b354a mark on transparent, 24px grid, 2px-equivalent
> strokes/solid shapes, squared brick-motif corners, flat only — no gradients, 3-D, shadows, text or
> photorealism —*

**Shield budget:** at most 6 shield-based concepts across the whole set. This spec uses **2**
(`modsecurity`, `crowdsec`). Everything else uses a concept specific to what the plugin actually does.

---

## 2. Core plugin icons (42)

Every directory under `src/common/core/*/plugin.json` is covered. `id` and `name` are verbatim from
each `plugin.json`; the metaphor is grounded in the plugin's `description`.

### 2.1 Security (detection & active protection)

| id | name | metaphor / concept | Stitch prompt (paste this cell) |
| --- | --- | --- | --- |
| `antibot` | Antibot | Robot head behind a challenge checkbox/gate — bot must pass a challenge | *Flat 2-D geometric icon, single deep-navy #0b354a mark on transparent, 24px grid, 2px-equivalent strokes/solid shapes, squared brick-motif corners, flat only — no gradients, 3-D, shadows, text or photorealism —* a blocky robot head silhouette positioned behind a square challenge/CAPTCHA checkbox tile with a checkmark, robot partly gated by the tile. |
| `badbehavior` | Bad behavior | Stacked HTTP error-status tickets crossing a threshold line, then a ban ring | *Flat 2-D geometric icon, single deep-navy #0b354a mark on transparent, 24px grid, 2px-equivalent strokes/solid shapes, squared brick-motif corners, flat only — no gradients, 3-D, shadows, text or photorealism —* three rising rectangular status tickets breaking a horizontal threshold line, stamped by a circular ban/no-entry ring. |
| `modsecurity` | ModSecurity | **Shield built from rule-bricks** — WAF + OWASP Core Rule Set | *Flat 2-D geometric icon, single deep-navy #0b354a mark on transparent, 24px grid, 2px-equivalent strokes/solid shapes, squared brick-motif corners, flat only — no gradients, 3-D, shadows, text or photorealism —* a broad shield whose interior is filled with a neat brick-wall grid, one brick highlighted as an active rule. |
| `crowdsec` | CrowdSec | **Collective-defense shield** — linked community nodes sharing a signal | *Flat 2-D geometric icon, single deep-navy #0b354a mark on transparent, 24px grid, 2px-equivalent strokes/solid shapes, squared brick-motif corners, flat only — no gradients, 3-D, shadows, text or photorealism —* a compact shield formed by three connected node-dots (a small community mesh) with a central alert beacon at the top. |
| `reversescan` | Reverse scan | Radar sweep over a row of client ports — detect proxy/open ports | *Flat 2-D geometric icon, single deep-navy #0b354a mark on transparent, 24px grid, 2px-equivalent strokes/solid shapes, squared brick-motif corners, flat only — no gradients, 3-D, shadows, text or photorealism —* a radar sweep arc passing over a row of small square port slots, one slot flagged. |
| `bunkernet` | BunkerNet | Linked bunker nodes exchanging a shared threat-data packet | *Flat 2-D geometric icon, single deep-navy #0b354a mark on transparent, 24px grid, 2px-equivalent strokes/solid shapes, squared brick-motif corners, flat only — no gradients, 3-D, shadows, text or photorealism —* three small brick-bunker glyphs connected by lines, a diamond data-packet travelling on the central link. |
| `dnsbl` | DNSBL | DNS lookup cross-referenced against a blocklist row (denied) | *Flat 2-D geometric icon, single deep-navy #0b354a mark on transparent, 24px grid, 2px-equivalent strokes/solid shapes, squared brick-motif corners, flat only — no gradients, 3-D, shadows, text or photorealism —* a DNS query tag/envelope with an arrow pointing to a small list sheet whose top row is struck out with an X. |

### 2.2 Access control

| id | name | metaphor / concept | Stitch prompt (paste this cell) |
| --- | --- | --- | --- |
| `authbasic` | Auth basic | Browser HTTP-auth dialog with a key — login before access | *Flat 2-D geometric icon, single deep-navy #0b354a mark on transparent, 24px grid, 2px-equivalent strokes/solid shapes, squared brick-motif corners, flat only — no gradients, 3-D, shadows, text or photorealism —* a small square credentials dialog box with two input bars and a key glyph, a browser title-bar dot row on top. |
| `blacklist` | Blacklist | List sheet with a struck-through row — deny | *Flat 2-D geometric icon, single deep-navy #0b354a mark on transparent, 24px grid, 2px-equivalent strokes/solid shapes, squared brick-motif corners, flat only — no gradients, 3-D, shadows, text or photorealism —* a document/list sheet of horizontal rows, one row struck through and marked with an X. |
| `whitelist` | Whitelist | List sheet with a **green** checked row — allow (security-positive) | *Flat 2-D geometric icon, single deep-navy #0b354a mark on transparent, 24px grid, 2px-equivalent strokes/solid shapes, squared brick-motif corners, flat only — no gradients, 3-D, shadows, text or photorealism —* a document/list sheet of rows with one row marked by a signature-green #2eac68 checkmark accent. |
| `greylist` | Greylist | Half-tone list, checked but watched — allow with an **amber** watch dot | *Flat 2-D geometric icon, single deep-navy #0b354a mark on transparent, 24px grid, 2px-equivalent strokes/solid shapes, squared brick-motif corners, flat only — no gradients, 3-D, shadows, text or photorealism —* a list sheet with a checked row and a small amber #ffab00 eye/watch dot in the corner. |
| `country` | Country | Globe with one region blocked by a no-entry arc | *Flat 2-D geometric icon, single deep-navy #0b354a mark on transparent, 24px grid, 2px-equivalent strokes/solid shapes, squared brick-motif corners, flat only — no gradients, 3-D, shadows, text or photorealism —* a geometric globe with latitude/longitude lines, one wedge covered by a no-entry / blocked arc. |
| `limit` | Limit | Throttle valve / gauge metering request dots against a max line | *Flat 2-D geometric icon, single deep-navy #0b354a mark on transparent, 24px grid, 2px-equivalent strokes/solid shapes, squared brick-motif corners, flat only — no gradients, 3-D, shadows, text or photorealism —* a funnel/valve narrowing a stream of small square request dots, a gauge needle pinned at a max mark. |
| `cors` | CORS | Cross-origin arrow bridging two labeled origin squares over a dashed boundary | *Flat 2-D geometric icon, single deep-navy #0b354a mark on transparent, 24px grid, 2px-equivalent strokes/solid shapes, squared brick-motif corners, flat only — no gradients, 3-D, shadows, text or photorealism —* two separate square origins linked by an arrow crossing a dashed vertical origin boundary. |

### 2.3 TLS / certificates

| id | name | metaphor / concept | Stitch prompt (paste this cell) |
| --- | --- | --- | --- |
| `letsencrypt` | Let's Encrypt | Padlock with circular renewal arrows and a small **green** sprout — auto-renew | *Flat 2-D geometric icon, single deep-navy #0b354a mark on transparent, 24px grid, 2px-equivalent strokes/solid shapes, squared brick-motif corners, flat only — no gradients, 3-D, shadows, text or photorealism —* a closed padlock encircled by two curved renewal arrows, a signature-green #2eac68 leaf sprout accent at the shackle. |
| `customcert` | Custom SSL certificate | Certificate sheet with a ribbon seal and a hand-picked pin | *Flat 2-D geometric icon, single deep-navy #0b354a mark on transparent, 24px grid, 2px-equivalent strokes/solid shapes, squared brick-motif corners, flat only — no gradients, 3-D, shadows, text or photorealism —* a certificate document with a circular ribbon seal in the corner and a small pin/upload marker indicating a user-supplied cert. |
| `selfsigned` | Self-signed certificate | Certificate whose signature stamp loops back onto itself | *Flat 2-D geometric icon, single deep-navy #0b354a mark on transparent, 24px grid, 2px-equivalent strokes/solid shapes, squared brick-motif corners, flat only — no gradients, 3-D, shadows, text or photorealism —* a certificate document with a circular seal and a curved arrow looping from the seal back onto the same document (self-referential signing). |
| `ssl` | SSL | Padlock clasping an interlocking-bracket TLS handshake | *Flat 2-D geometric icon, single deep-navy #0b354a mark on transparent, 24px grid, 2px-equivalent strokes/solid shapes, squared brick-motif corners, flat only — no gradients, 3-D, shadows, text or photorealism —* a closed padlock sitting above two interlocking square brackets that clasp (a handshake). |
| `mtls` | Mutual TLS | Two certificate badges exchanging keys — bidirectional trust | *Flat 2-D geometric icon, single deep-navy #0b354a mark on transparent, 24px grid, 2px-equivalent strokes/solid shapes, squared brick-motif corners, flat only — no gradients, 3-D, shadows, text or photorealism —* two small certificate badges facing each other with a two-way arrow and a key on each side (mutual authentication). |

### 2.4 Performance

| id | name | metaphor / concept | Stitch prompt (paste this cell) |
| --- | --- | --- | --- |
| `brotli` | Brotli | Inward arrows tightly compressing a stack into a small dense block | *Flat 2-D geometric icon, single deep-navy #0b354a mark on transparent, 24px grid, 2px-equivalent strokes/solid shapes, squared brick-motif corners, flat only — no gradients, 3-D, shadows, text or photorealism —* four inward-pointing arrows squeezing a stack of bars into a small dense square block (tight compression). |
| `gzip` | Gzip | Inward arrows compressing a block sealed with a zipper | *Flat 2-D geometric icon, single deep-navy #0b354a mark on transparent, 24px grid, 2px-equivalent strokes/solid shapes, squared brick-motif corners, flat only — no gradients, 3-D, shadows, text or photorealism —* a rectangular data block with a vertical zipper down the middle and two inward compression arrows. |
| `clientcache` | Client cache | Browser window holding a layered cache stack with a small clock (TTL) | *Flat 2-D geometric icon, single deep-navy #0b354a mark on transparent, 24px grid, 2px-equivalent strokes/solid shapes, squared brick-motif corners, flat only — no gradients, 3-D, shadows, text or photorealism —* a browser frame containing a small layered/stacked cache shape with a tiny clock badge in the corner. |

### 2.5 Observability

| id | name | metaphor / concept | Stitch prompt (paste this cell) |
| --- | --- | --- | --- |
| `metrics` | Metrics | Framed panel with a climbing bar+line chart and a pulse node | *Flat 2-D geometric icon, single deep-navy #0b354a mark on transparent, 24px grid, 2px-equivalent strokes/solid shapes, squared brick-motif corners, flat only — no gradients, 3-D, shadows, text or photorealism —* a rectangular panel containing rising bars overlaid with a line chart and a single data node dot. |

### 2.6 Integration (proxy / data / runtime)

| id | name | metaphor / concept | Stitch prompt (paste this cell) |
| --- | --- | --- | --- |
| `reverseproxy` | Reverse proxy | Central node routing one inbound arrow to several backend squares | *Flat 2-D geometric icon, single deep-navy #0b354a mark on transparent, 24px grid, 2px-equivalent strokes/solid shapes, squared brick-motif corners, flat only — no gradients, 3-D, shadows, text or photorealism —* one inbound arrow entering a central routing node that fans out to three stacked backend squares. |
| `grpc` | gRPC | Two nodes with paired bidirectional streaming chevrons | *Flat 2-D geometric icon, single deep-navy #0b354a mark on transparent, 24px grid, 2px-equivalent strokes/solid shapes, squared brick-motif corners, flat only — no gradients, 3-D, shadows, text or photorealism —* two square nodes connected by two parallel arrows in opposite directions, each carrying a small chevron packet (streaming). |
| `php` | PHP | Abstract elephant-head silhouette feeding a page through a process gear | *Flat 2-D geometric icon, single deep-navy #0b354a mark on transparent, 24px grid, 2px-equivalent strokes/solid shapes, squared brick-motif corners, flat only — no gradients, 3-D, shadows, text or photorealism —* a simplified geometric elephant-head silhouette (PHP mascot, abstracted) beside a small gear and a document page. |
| `realip` | Real IP | Proxy envelope peeled back to reveal the true client IP tag | *Flat 2-D geometric icon, single deep-navy #0b354a mark on transparent, 24px grid, 2px-equivalent strokes/solid shapes, squared brick-motif corners, flat only — no gradients, 3-D, shadows, text or photorealism —* a layered envelope with the outer layer peeled back to reveal an inner IP address tag/label. |
| `redirect` | Redirect | Arrow bending from a source URL square to a target square (3xx) | *Flat 2-D geometric icon, single deep-navy #0b354a mark on transparent, 24px grid, 2px-equivalent strokes/solid shapes, squared brick-motif corners, flat only — no gradients, 3-D, shadows, text or photorealism —* a right-angle bending arrow leaving a source square and pointing into a separate target square. |
| `redis` | Redis | Stacked in-memory datastore cylinder with a lightning bolt (fast) | *Flat 2-D geometric icon, single deep-navy #0b354a mark on transparent, 24px grid, 2px-equivalent strokes/solid shapes, squared brick-motif corners, flat only — no gradients, 3-D, shadows, text or photorealism —* a layered database cylinder with a lightning bolt overlaid (in-memory speed), cluster hint via a small linked node. |
| `db` | Database | Database cylinder with a connector plug — easy integration | *Flat 2-D geometric icon, single deep-navy #0b354a mark on transparent, 24px grid, 2px-equivalent strokes/solid shapes, squared brick-motif corners, flat only — no gradients, 3-D, shadows, text or photorealism —* a stacked database cylinder with a small plug/connector attaching to its side. |
| `sessions` | Sessions | Session token/ticket stub with a clock (lifecycle) | *Flat 2-D geometric icon, single deep-navy #0b354a mark on transparent, 24px grid, 2px-equivalent strokes/solid shapes, squared brick-motif corners, flat only — no gradients, 3-D, shadows, text or photorealism —* a perforated ticket/token stub with a small clock badge indicating session lifetime. |

### 2.7 Misc / content / internal

| id | name | metaphor / concept | Stitch prompt (paste this cell) |
| --- | --- | --- | --- |
| `headers` | Headers | Stacked HTTP header lines with one highlighted key:value pair | *Flat 2-D geometric icon, single deep-navy #0b354a mark on transparent, 24px grid, 2px-equivalent strokes/solid shapes, squared brick-motif corners, flat only — no gradients, 3-D, shadows, text or photorealism —* a document header band above stacked horizontal lines, one line split into a highlighted key/value block. |
| `inject` | HTML injection | Angle-bracket slot dropping a snippet block into a page frame | *Flat 2-D geometric icon, single deep-navy #0b354a mark on transparent, 24px grid, 2px-equivalent strokes/solid shapes, squared brick-motif corners, flat only — no gradients, 3-D, shadows, text or photorealism —* a page frame with a small code-snippet block dropping into an angle-bracket `</>` slot near the top/bottom edge. |
| `robotstxt` | Robots.txt | Text file with a tiny robot glyph and allow/deny path rows | *Flat 2-D geometric icon, single deep-navy #0b354a mark on transparent, 24px grid, 2px-equivalent strokes/solid shapes, squared brick-motif corners, flat only — no gradients, 3-D, shadows, text or photorealism —* a plain text-file document with a tiny blocky robot head in the header and two path rows (one allow tick, one deny bar). |
| `securitytxt` | Security.txt | Text file with a lock and a contact/@ mark — disclosure policy | *Flat 2-D geometric icon, single deep-navy #0b354a mark on transparent, 24px grid, 2px-equivalent strokes/solid shapes, squared brick-motif corners, flat only — no gradients, 3-D, shadows, text or photorealism —* a plain text-file document with a small padlock in the header and an @ / contact mark on a body line. |
| `errors` | Errors | Browser page showing an **amber** "!" tile with a restyle brush marker | *Flat 2-D geometric icon, single deep-navy #0b354a mark on transparent, 24px grid, 2px-equivalent strokes/solid shapes, squared brick-motif corners, flat only — no gradients, 3-D, shadows, text or photorealism —* a browser page frame containing a square tile with a small amber #ffab00 exclamation and a brush/swap marker (custom error page). |
| `misc` | Miscellaneous | Overlapping gear and a small slider row — settings grab-bag | *Flat 2-D geometric icon, single deep-navy #0b354a mark on transparent, 24px grid, 2px-equivalent strokes/solid shapes, squared brick-motif corners, flat only — no gradients, 3-D, shadows, text or photorealism —* a gear overlapping a short row of two horizontal sliders (assorted settings). |
| `backup` | Backup | Database cylinder archiving into a box with a schedule clock | *Flat 2-D geometric icon, single deep-navy #0b354a mark on transparent, 24px grid, 2px-equivalent strokes/solid shapes, squared brick-motif corners, flat only — no gradients, 3-D, shadows, text or photorealism —* a database cylinder with an arrow flowing into an archive box, a small clock badge for scheduled backups. |
| `jobs` | Jobs | Clock-gear with recurring arrows and a task tick — internal scheduler | *Flat 2-D geometric icon, single deep-navy #0b354a mark on transparent, 24px grid, 2px-equivalent strokes/solid shapes, squared brick-motif corners, flat only — no gradients, 3-D, shadows, text or photorealism —* a gear with clock hands encircled by two cyclical arrows, a small checklist tick beside it (recurring jobs). |
| `templates` | Templates | Stacked blueprint sheets with a duplicate/copy corner | *Flat 2-D geometric icon, single deep-navy #0b354a mark on transparent, 24px grid, 2px-equivalent strokes/solid shapes, squared brick-motif corners, flat only — no gradients, 3-D, shadows, text or photorealism —* two overlapping blueprint/config sheets with a folded copy corner (reusable template). |
| `ui` | UI | Dashboard window framing the BunkerWeb brick-battlement glyph | *Flat 2-D geometric icon, single deep-navy #0b354a mark on transparent, 24px grid, 2px-equivalent strokes/solid shapes, squared brick-motif corners, flat only — no gradients, 3-D, shadows, text or photorealism —* a browser/dashboard window frame with a sidebar strip, containing a small brick-battlement mark (the BunkerWeb symbol) centered. |
| `pro` | Pro | Faceted **green** diamond with a crown notch — Pro tier (brand `diamond.svg` lineage) | *Flat 2-D geometric icon, single deep-navy #0b354a mark on transparent, 24px grid, 2px-equivalent strokes/solid shapes, squared brick-motif corners, flat only — no gradients, 3-D, shadows, text or photorealism —* a faceted diamond glyph with a small crown notch on top, filled signature-green #2eac68 (pro accent). |

---

## 3. Architecture resource icons (10)

**Family motif:** every architecture component is a **hexagonal machine plate** (same hex outline,
same visual weight) with a single **distinguishing central element**. This makes the runtime
components read as one family in diagrams while staying individually identifiable.

| resource | role | central distinguishing element | Stitch prompt (paste this cell) |
| --- | --- | --- | --- |
| `instance` | BunkerWeb instance (NGINX node) | Brick-battlement wall | *Flat 2-D geometric icon, single deep-navy #0b354a mark on transparent, 24px grid, 2px-equivalent strokes/solid shapes, squared brick-motif corners, flat only — no gradients, 3-D, shadows, text or photorealism —* a hexagonal machine plate with a small brick-battlement wall at its center (the BunkerWeb node). |
| `scheduler` | Scheduler ("the brain" / orchestrator) | Connected-node brain / circuit hub | *Flat 2-D geometric icon, single deep-navy #0b354a mark on transparent, 24px grid, 2px-equivalent strokes/solid shapes, squared brick-motif corners, flat only — no gradients, 3-D, shadows, text or photorealism —* a hexagonal machine plate with a central hub of connected nodes forming a compact brain/circuit (orchestration). |
| `worker` | Worker (Celery executor) | Gear pulling a task from a queue | *Flat 2-D geometric icon, single deep-navy #0b354a mark on transparent, 24px grid, 2px-equivalent strokes/solid shapes, squared brick-motif corners, flat only — no gradients, 3-D, shadows, text or photorealism —* a hexagonal machine plate with a central gear pulling a task chevron off a short queue of stacked tiles. |
| `api` | API service (FastAPI) | Curly-brace endpoint / plug | *Flat 2-D geometric icon, single deep-navy #0b354a mark on transparent, 24px grid, 2px-equivalent strokes/solid shapes, squared brick-motif corners, flat only — no gradients, 3-D, shadows, text or photorealism —* a hexagonal machine plate with a central `{ }` brace pair and a small endpoint plug (API). |
| `ui` | Web UI (Flask admin) | Dashboard window | *Flat 2-D geometric icon, single deep-navy #0b354a mark on transparent, 24px grid, 2px-equivalent strokes/solid shapes, squared brick-motif corners, flat only — no gradients, 3-D, shadows, text or photorealism —* a hexagonal machine plate with a central mini dashboard window (sidebar strip + content tiles). |
| `autoconf` | Autoconf watcher | Eye/radar watching container squares | *Flat 2-D geometric icon, single deep-navy #0b354a mark on transparent, 24px grid, 2px-equivalent strokes/solid shapes, squared brick-motif corners, flat only — no gradients, 3-D, shadows, text or photorealism —* a hexagonal machine plate with a central eye/radar arc watching two small container squares (event watcher). |
| `database` | Database | Data cylinder | *Flat 2-D geometric icon, single deep-navy #0b354a mark on transparent, 24px grid, 2px-equivalent strokes/solid shapes, squared brick-motif corners, flat only — no gradients, 3-D, shadows, text or photorealism —* a hexagonal machine plate with a central stacked database cylinder. |
| `broker` | Redis/Valkey broker | Message relay with a bolt + envelopes | *Flat 2-D geometric icon, single deep-navy #0b354a mark on transparent, 24px grid, 2px-equivalent strokes/solid shapes, squared brick-motif corners, flat only — no gradients, 3-D, shadows, text or photorealism —* a hexagonal machine plate with a central relay routing two small envelopes, a lightning bolt overlay (fast in-memory broker). |
| `syslog` | Syslog aggregator | Log lines funneling into one stream | *Flat 2-D geometric icon, single deep-navy #0b354a mark on transparent, 24px grid, 2px-equivalent strokes/solid shapes, squared brick-motif corners, flat only — no gradients, 3-D, shadows, text or photorealism —* a hexagonal machine plate with several stacked log lines funneling down into a single output stream (aggregation). |
| `bwcli` | bwcli command-line | Terminal prompt `>_` | *Flat 2-D geometric icon, single deep-navy #0b354a mark on transparent, 24px grid, 2px-equivalent strokes/solid shapes, squared brick-motif corners, flat only — no gradients, 3-D, shadows, text or photorealism —* a hexagonal machine plate with a central terminal prompt chevron and cursor bar (`>_`). |

---

## 4. Export & naming conventions

| Item | Rule |
| --- | --- |
| **Format** | **SVG** preferred (clean geometry, scales, small). Fallback: **512×512 PNG, transparent**. |
| **Plugin filename** | `plugin-<id>.svg` — e.g. `plugin-antibot.svg`, `plugin-letsencrypt.svg`. `<id>` = verbatim `plugin.json` `id`. |
| **Resource filename** | `resource-<name>.svg` — e.g. `resource-scheduler.svg`, `resource-broker.svg`. |
| **Mono variant** | Single deep-navy `#0b354a` fill/stroke. Default. Suffix: none. |
| **Duotone variant** | Navy + one accent (`#2eac68` green or `#ffab00` amber) where the concept sanctions it. Suffix: `-duo` → `plugin-whitelist-duo.svg`. |
| **Light-bg variant** | Navy mark (default file, no suffix). For `#f5f5f9` / `#ffffff` backgrounds. |
| **Dark-bg variant** | White mark, suffix `-white` → `plugin-antibot-white.svg`, `resource-scheduler-white.svg`. **Mirrors the existing `icon.svg` / `icon-white.svg` pairing** in `src/ui/app/static/img/`. |
| **viewBox** | `0 0 24 24` (matches the 24 px grid and Boxicons' sizing so it drops into existing size slots). |
| **No embedded raster / no `<text>`** | SVGs must be pure path geometry — no fonts, no base64 images. |
| **Optimize** | Run through SVGO before commit (strip metadata, editor cruft). |

---

## 5. Repo integration plan (PLAN ONLY — no code changes now)

### 5.1 Target paths

| Location | Purpose |
| --- | --- |
| `src/ui/app/static/img/plugins/` | Live assets the UI serves. `plugin-<id>.svg` (+ `-white`, `-duo`). |
| `.claude/BunkerWeb Design System/assets/plugins/` | Design-system **mirror** (source of truth for the brand kit). Keep in sync. |
| `src/ui/app/static/img/resources/` | Architecture-resource marks (docs/diagrams reuse). |

### 5.2 How the UI would consume them (marketplace card)

Current card icon logic (`src/ui/app/templates/plugins.html`):

- **Line 69:** `{% set icon = 'bx-shield' if ptype == 'core' else ('bx-diamond' if ptype == 'pro' else ('bx-cloud-upload' if ptype == 'ui' else 'bx-plug')) %}`
- **Line 80:** `<i class="bx {{ icon }} bx-sm text-primary" aria-hidden="true"></i>`

**Planned change (do NOT apply yet):** before the boxicon fallback, look up a custom SVG by plugin id.
Pseudocode for the card head:

```jinja
{# resolve once, near line 69 #}
{% set custom_icon = 'img/plugins/plugin-' ~ plugin ~ '.svg' %}
{% set has_custom = custom_icon in resolved_static_files %}   {# see fallback rule below #}
...
{% if has_custom %}
  <img src="{{ url_for('static', filename=custom_icon) }}" class="plugin-mark" width="18" height="18" alt="" aria-hidden="true">
{% else %}
  <i class="bx {{ icon }} bx-sm text-primary" aria-hidden="true"></i>   {# unchanged existing boxicon #}
{% endif %}
```

**Fallback rule (mandatory):** missing `plugin-<id>.svg` → render the **current boxicon** exactly as today.
The custom set can therefore land incrementally (one plugin at a time) with zero regressions.

Two ways to implement the existence check when built:

1. **Static manifest** (preferred, no per-request FS hit): a small generated `plugins/index.json` (or a
   Jinja global set at startup) listing which ids have a custom SVG. Card checks membership.
2. **`os.path.exists`** in the route/context processor that builds `plugins` — simplest, acceptable given
   the plugin grid renders once per page load.

Dark mode: pick `-white` when `data-bs-theme="dark"` (same pattern the UI already uses for
`logo-menu.png` ↔ `logo-menu-white.png`).

### 5.3 Templates page reuse

`src/ui/app/templates/templates.html` (line 66) already keyword-maps a template id/name → a boxicon
for the template card. Same fallback pattern applies: if a template maps to a plugin concept and a
`plugin-<id>.svg` exists, prefer it; otherwise keep the boxicon keyword map. No new asset pipeline —
templates reuse the plugin marks.

### 5.4 Docs & diagrams

`resource-<name>.svg` marks are used directly in architecture diagrams (the hex-plate family) and docs
pages. No UI wiring required — they are static includes.

---

## 6. QA checklist (review every Stitch output against this)

- [ ] **Grid consistency** — mark sits on a 24 px grid; optical weight matches siblings in the same group.
- [ ] **Stroke weight** — 2 px-equivalent throughout; no stray hairlines, no chunky-vs-thin mix within one mark.
- [ ] **Color compliance** — navy `#0b354a` only, **except** sanctioned green `#2eac68` (pro / allow / encrypted) or amber `#ffab00` (warning / watched). No stray hues, no Bootstrap semantic colors bleeding in, **green never used as a generic success tint**.
- [ ] **Flat rule** — zero gradients, 3-D, bevels, shadows, glows. (SKILL.md gradient ban.)
- [ ] **No text/numerals** — no letters or digits baked into the mark.
- [ ] **Silhouette readable at 20 px** — shrink to 20 px; the core concept must still be identifiable.
- [ ] **Transparent background** — no card, no fill plate behind the mark (except the intentional hex plate on resource icons).
- [ ] **Dark-variant contrast** — white `-white` version is legible on `#0c283a` / `#133044`; no navy detail that vanishes.
- [ ] **Family coherence** — resource icons share the identical hex-plate outline; only the center differs.
- [ ] **Shield budget** — ≤6 shields across the set (spec ships 2: `modsecurity`, `crowdsec`).
- [ ] **Distinctiveness** — no two plugins in the same group share a silhouette; concept matches the plugin's real function.
- [ ] **File hygiene** — SVG is pure geometry (no `<text>`, no raster), `viewBox="0 0 24 24"`, SVGO-optimized, correct `plugin-<id>` / `resource-<name>` name.

---

## Appendix — coverage ledger

- **Core plugins covered:** 42 / 42 — every directory under `src/common/core/*/plugin.json` was read
  (id + name + description verbatim). None unreadable.
- **Architecture resources:** 10 (instance, scheduler, worker, api, ui, autoconf, database, broker, syslog, bwcli).
- **Total marks:** 52.
- **plugin.json files that could not be read:** none.

---

## Curated icon set (shipped) — 2026-07-22

**Status update: the Stitch generation route (sections 1–4 above) was abandoned.** Rather than
generate 52 marks from the prompt cells, the set was **curated and brand-tuned from
[@tabler/icons](https://github.com/tabler/tabler-icons) v3.45.0** (MIT, © Paweł Kuna): recolored to
navy `#0b354a` with sanctioned green `#2eac68` / amber `#ffab00` accents, a few composing two
glyphs. The metaphors, naming conventions (§4), governance carve-out (§0) and QA checklist (§6)
remain the reference — only the origin of the geometry changed (Tabler, not Stitch).

**Delivered:**

- **Assets:** `src/ui/app/static/img/plugins/` — `plugin-<id>.svg` + `-white` (42×2) and
  `resource-<name>.svg` + `-white` (10×2), plus `LICENSE-tabler.md`. Per-icon mapping rationale in
  the curation notes (`scratchpad/icon-curate/mapping.md`).
- **Wiring:** marketplace cards (`plugins.html` + `routes/plugins.py`) render `plugin-<id>.svg`
  with a light/dark CSS swap; unknown ids fall back to the boxicon (server-side known-ids set).
- **Governance:** `ICONOGRAPHY.md` amended with the *"Custom illustrative marks"* carve-out
  (Boxicons stays the only inline-UI glyph set; custom set sanctioned for identity marks / diagrams
  / docs; provenance + license recorded).
- **Deferred:** Templates-page tiles (§5.3) and docs/diagram reuse of `resource-*` marks (§5.4)
  reuse the same assets when those surfaces are next touched — no new pipeline needed.

### Plugin icon field

Beyond the curated static set, each plugin can ship **its own** icon, resolved through a fixed
chain and persisted in `Plugins.icon` (`String(256)`, nullable):

1. **Shipped file wins (auto-detected).** An allowlisted root-level icon in the plugin —
   `icon.svg` / `icon.png` / `logo.svg` / `logo.png` (priority order,
   `common_utils.PLUGIN_ICON_FILES`) — is recorded as the marker **`@file/<name>`**. External/ui/pro
   plugins ship it inside their archive blob (`detect_plugin_icon`); core plugins ship it in their own
   directory (`src/common/core/<id>/icon.svg`, no data blob) and it is auto-detected from that dir
   (`detect_local_plugin_icon`) — **no `plugin.json` `icon` field required**. The field is an *optional
   override*, honored only when it names an allowlisted file that actually exists (never promoted to a
   marker that would 404). `resolve_plugin_icon(data, icon, dir_path=…)` computes this at DB sync
   (init + `update_external_plugins`) — deterministic per dir/blob contents, so a reboot never
   overwrites a detected marker.
2. **plugin.json `icon` string.** A bare `*.svg` naming a UI static asset, or a boxicon class
   (e.g. `bx-shield`), is stored verbatim.
3. **NULL** → the UI's type-based boxicon fallback.

**Serving endpoint.** `GET /plugins/{id}/icon` (API) serves only `@file/<name>` markers: for a
**core** plugin it reads the file off disk from `CORE_PLUGINS_ROOT/<id>/<name>`
(`read_local_plugin_icon`); otherwise it extracts `<name>` from the stored archive blob
(`read_plugin_icon`). Anything non-servable (bare `*.svg`, boxicon class, NULL, unknown plugin)
→ 404; a file over 512KB → 413; an invalid id → 422. **Every** icon response carries three
security headers — `Content-Security-Policy: default-src 'none'; sandbox` (neutralizes any script
in an SVG opened by direct navigation — CSP on the response never affects the page that `<img>`-embeds
it, so `img-src` discipline alone is insufficient), `Content-Disposition: inline; filename="<name>"`
(quoted), and `X-Content-Type-Options: nosniff` — with the correct image Content-Type. The fixed
4-name root-only allowlist means there is no path-traversal surface.

**UI consumption.** Browsers cannot authenticate to the API, so the UI proxies the bytes:
`GET /plugins/<id>/icon` (Flask, `@login_required`) fetches via `api_client.get_plugin_icon()` and
re-serves with the same three headers plus `Cache-Control: private, max-age=3600`. The marketplace
card (`plugins.html`) resolves **field-first** off `plugin_data.icon`: the curated brand pair still
wins (id-keyed, dark-mode swap); then `@file/*` → the UI proxy URL; a bare `*.svg` that exists in
`static/img/plugins/` → that asset; a `bx*` string → the icon font; else the type boxicon.
