# QOL Config — Group B: unit suffixes + list normalization

Status: approved (2026-06-25). Part of the 1.7 "Confort de configuration (QOL)" chantier. Follows A1 (boolean `check` normalization, shipped commit `7493219a3`).

## Goal

Two QOL mechanisms around settings, applied at the validation/ingestion boundary (same pillar as A1 — normalize before the gate, store canonical, leave the ~239 downstream consumers untouched):

- **B2** — first-class `size` / `duration` setting types backed by a shared parser that owns acceptance + canonical output, replacing the per-plugin unit regexes. Accepts the **full** nginx grammar (including compound durations the current regex rejects) plus human variants.
- **B1** — list normalization for `multivalue` / `multiselect`: trim items, drop empties, canonical separator.

## Background (verified in code)

- Validation is **whole-string regex** for every type (`Configurator.__check_var`, `config_read.is_valid_setting`, `ui/models/config.check_variables`). Multivalue regexes bake in the separator + repetition; there is no per-item split at validation. `separator` (default `" "`) is consumer-side metadata.
- No existing unit parser in the codebase.
- 26 unit-suffix settings, all `text`/`multivalue`, values fed **straight into nginx config** via Jinja → canonical output must be nginx-valid.
- The current duration regex `^\d+(ms?|[shdwMy])?$` allows only **one** unit group, so nginx-valid compound times (`1h30m`, `1d12h`, `1y6M`) are **rejected today**. The parser is a capability upgrade, not just tolerance.
- `SETTINGS_TYPES_ENUM` (model.py:15) is a real DB `Enum` → new types need a migration across sqlite/mariadb/mysql/postgresql. **Migrations are auto-generated** (extend the model, run the generator per engine — do not hand-author version files).
- ModSecurity `SecRequestBodyLimit`/`SecRequestBodyNoFilesLimit` **do** accept `k/m/g` suffixes (per plugin help + README) and empty→derived from `MAX_CLIENT_SIZE` → they are genuinely `size`.

## B2 — unit parser

New module `src/common/utils/unit_parser.py`. Pure functions, no I/O. Exposes per-kind `validate(value) -> bool` and `canonicalize(value) -> str` (or a single `normalize(kind, value) -> Optional[str]` returning None on invalid).

### duration (nginx `ngx_parse_time`)
- Units: `ms s m h d w M y`. **Compound** allowed: `1h30m`, `1d12h`, `1y6M`. Bare int = seconds. `0` valid.
- **Unit order (enforced):** nginx requires compound units in **strictly decreasing magnitude with no repeats** — `1h30m` valid, but `30m1h`, `1h1h`, `1h1d` are rejected by nginx and so the parser rejects them too. Without this, an order-invalid value would pass both parser and regex and break the nginx reload.
- Empty string is **rejected** (the prior unit regexes required digits; an empty *default* bypasses value validation, so rejecting empty user input preserves behaviour).
- Human aliases → canonical nginx unit: `sec|secs|second|seconds`→`s`, `min|mins|minute|minutes`→`m`, `hr|hrs|hour|hours`→`h`, `day|days`→`d`, `week|weeks`→`w`, `month|months`→`M`, `year|years`→`y`. (`ms`, `s`, `h`, `d`, `w`, `y` pass through.)
- **`m`/`M` rule (critical):** single-letter units are **case-sensitive** — `m`=minutes, `M`=months, `ms`=milliseconds. Word aliases are case-insensitive (`MONTH`→`M`, `Minutes`→`m`). NEVER blanket-lowercase the value (would corrupt `M`→`m`).
- Whitespace stripped (`30 s`→`30s`, `1h 30m`→`1h30m`).
- Canonical: keep the user's numeric grouping (`90m` stays `90m`, not recomputed to `1h30m`); only normalize units + strip space. Idempotent.

### size (nginx `ngx_parse_size`)
- Units: `k m g`, **case-insensitive**. Bare int = bytes. `0` valid. Empty string valid. **No compound, no fraction** (reject `1.5g`, `64m32k`).
- Aliases: `kb|kib`→`k`, `mb|mib`→`m`, `gb|gib`→`g`.
- Canonical: lowercase suffix, strip space (`64 M`→`64m`, `1KB`→`1k`). Idempotent.

### Conversions (set `type`, drop unit regex)
- **`duration` (13):** `WORKER_SHUTDOWN_TIMEOUT`, `CLIENT_BODY_TIMEOUT`, `CLIENT_HEADER_TIMEOUT`, `KEEPALIVE_TIMEOUT`, `SEND_TIMEOUT`, `GRPC_CONNECT_TIMEOUT`, `GRPC_READ_TIMEOUT`, `GRPC_SEND_TIMEOUT`, `GRPC_NEXT_UPSTREAM_TIMEOUT`, `REVERSE_PROXY_CONNECT_TIMEOUT`, `REVERSE_PROXY_READ_TIMEOUT`, `REVERSE_PROXY_SEND_TIMEOUT`, `OPEN_FILE_CACHE_VALID`.
- **`size` (11):** `WORKERLOCK_MEMORY_SIZE`, `INTERNALSTORE_MEMORY_SIZE`, `DATASTORE_MEMORY_SIZE`, `CACHESTORE_MEMORY_SIZE`, `CACHESTORE_IPC_MEMORY_SIZE`, `CACHESTORE_MISS_MEMORY_SIZE`, `CACHESTORE_LOCKS_MEMORY_SIZE`, `METRICS_MEMORY_SIZE`, `MAX_CLIENT_SIZE`, `MODSECURITY_REQ_BODY_NO_FILES_LIMIT`, `MODSECURITY_SEC_REQUEST_BODY_LIMIT`.

### Special cases (compound-structured — keep type and **original single-unit** regex)
`OPEN_FILE_CACHE` (`text`) and `PROXY_CACHE_VALID` (`multivalue`) embed a duration inside a larger structure and are gated by regex only (no parser). A regex cannot enforce nginx's strictly-decreasing unit-order rule, so admitting compound inner time would let an order-invalid value (e.g. `inactive=30m1h`) reach nginx and break the reload. Their inner duration is therefore **kept single-unit** (original `\d+(ms?|[shdwMy])`, matching their common usage `inactive=20s`, `200=24h`). Full compound time is delivered only for the 13 scalar `duration` settings, which the order-enforcing parser gates. `PROXY_CACHE_VALID` still gets B1 item-trimming.

## B1 — list normalization

For `multivalue`/`multiselect`, on the storage path: `split(separator) → strip each item → drop empty items → join(canonical separator)`. Separator = declared `separator` (default `" "`). Idempotent. Matches what consumers already compute (regexes already tolerate ` *` around items, consumers strip per-item) → no acceptance change, only clean canonical storage (` 10.0.0.1  10.0.0.2 `→`10.0.0.1 10.0.0.2`).

## Wiring (boundary seams — same as A1)

`Configurator.__check_var`, `config_read.is_valid_setting`, `config_save` (×3 storage fns), `ui/app/models/config.check_variables`, `autoconf/Config.__get_full_env`, `db_methods/templates._prepare_template_entities`. New types added to `Configurator.__valid_setting_types` and `SETTINGS_TYPES_ENUM`. Validation branches: when `type in (size, duration)` → use parser; B1 normalize when `type in (multivalue, multiselect)`.

## Ripples
- DB: `SETTINGS_TYPES_ENUM += "size", "duration"` → auto-generated migration ×4 engines.
- `regex` handling — **Decision (implemented): keep `regex`** on `size`/`duration` settings, set to the exact canonical grammar (`size`: `^\d+([kKmMgG])?$`; `duration`: `^(\d+(ms|s|m|h|d|w|M|y))+$|^\d+$`; two empty-allowing variants for `GRPC_NEXT_UPSTREAM_TIMEOUT` and `MODSECURITY_SEC_REQUEST_BODY_LIMIT`). The **parser is the authoritative server-side gate + canonicalizer** at each seam; the canonical value it emits always satisfies the regex (242-case consistency check). Keeping `regex` avoids any change to `__mandatory_setting_keys`, the DB `nullable=False`, or the UI template (which renders `pattern="{{ regex }}"`), and preserves client-side validation. This deviates from the earlier "relax mandatory regex" sketch — the keep-regex path is lower-risk and was chosen deliberately.
- UI render: `plugins_settings.html` else-branch renders a text input (`input_setting.html`) for unknown types → size/duration degrade gracefully. JS client-side validation keys off `regex`; with no regex these rely on the server parser. Verify no JS break; optionally surface a `data-unit` hint.
- Consumers: nginx receives canonical nginx-valid strings → ~239 downstream consumers untouched. No data migration (canonicalization idempotent on existing values; all current defaults already canonical).

## Testing (TDD, multi-engine)
- `tests/unit/common/test_unit_parser.py` — table: compound durations, `m`/`M` case rule, all aliases, fraction reject, bare int, `0`, empty passthrough, idempotence (canonicalize twice == once), size k/m/g + kb/mb/gb.
- Configurator: size/duration accept+canonicalize, invalid reject, compound accepted (regression on old single-group rejection).
- `config_read`/`config_save`: canonical stored across global/multisite/service paths.
- B1: multivalue/multiselect trim+dedup-empties+canonical separator; idempotent; free-text multivalue (space sep) consistent.
- Duration unit-order: order-invalid compounds (`30m1h`, `1h1h`, `1h1d`) rejected; valid decreasing-order compounds accepted.
- 2 compound settings: `OPEN_FILE_CACHE` / `PROXY_CACHE_VALID` keep their original single-unit regex (defaults still validate); B1 trimming still applies to `PROXY_CACHE_VALID`.
- Migration: enum round-trip (a setting persisted as `size`/`duration` reads back).
- Run on sqlite + PostgreSQL + MariaDB.

## Out of scope
A2 (universal trim), A3 (select case-insensitivity), Group C (actionable validation). Inner-value parser normalization for the 2 compound settings (regex-only fix here).
