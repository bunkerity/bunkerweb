# AGENTS.md

Agent guide for the BunkerWeb database layer in `src/common/db/`. This is the canonical guide for this directory; `CLAUDE.md` here is a pointer to it.

## Read First

- Shared layer: [../AGENTS.md](../AGENTS.md)
- Root: [../../../AGENTS.md](../../../AGENTS.md) (short) and [../../../CLAUDE.md](../../../CLAUDE.md) (architecture)

## Structure

- `model.py` — every SQLAlchemy 2.0 table, plus the `JSONText` TypeDecorator. This file is the schema's source of truth; read it rather than any list of tables.
- `Database.py` — the coordinator. It owns the engine, the connection pool and the session, and composes the domain mixins; it holds almost no queries of its own. The mixin list is in the `class Database(...)` declaration — read that for the current set, one mixin per file in `db_methods/`.
- `db_methods/` — one module per domain. Two files there are **not** mixins: `common.py` (shared infrastructure, including the retry decorator) and `locations.py` (the cross-plugin location-claim guard).
- `alembic/` — `env.py`, `alembic.ini`, and one version directory per engine: `sqlite_versions/`, `mariadb_versions/`, `mysql_versions/`, `postgresql_versions/`.

Four engines are supported: SQLite (WAL mode), MariaDB, MySQL and PostgreSQL, all pooled with `QueuePool`.

## Critical Rules

- **Never hand-author, generate, or "just regenerate" an Alembic revision without an explicit request.** See the migration section below.
- Every schema change must land in **all four** engine version directories.
- A new query belongs in the domain mixin, not in `Database.py`. Do not let the coordinator grow query logic back.
- Database mutators return `""` on success or an error string, unless their own contract says otherwise. Assert the return value before reading state back.

## Patterns

- **Transient-error resilience**: `@retry_on_transient_db_errors` (in `db_methods/common.py`) wraps most methods; attempts and delay come from `DATABASE_REQUEST_RETRY_ATTEMPTS` and `DATABASE_REQUEST_RETRY_DELAY`. A read-only fallback mode exists for degraded reads.
- **Validation happens here too**, not only in the Configurator: `is_valid_setting(setting, value)` checks against pre-compiled regex caches at runtime.
- **Multisite prefixing**: settings with `context=multisite` are stored and queried with the server-name prefix (`www.example.com_SETTING_ID`); global settings have none. The lookup falls back service-specific → global.
- **Suffix settings**: a setting declaring `"multiple": "group-name"` in `plugin.json` accepts `SETTING_1`, `SETTING_2`, …, with the regex applied per value.
- **File-backed settings**: when a value is a file, the filename is stored separately from the value so updates stay atomic.
- **Custom configs** are stored as `LargeBinary` with checksum tracking and an `is_draft` flag for multi-step UI flows. The type enum lives in `model.py` and includes `default_server_http` but **no** `default_server_stream`.

## The Location-Claim Guard (`db_methods/locations.py`)

`reverseproxy`, `grpc` and `redirect` all render a `location` into the same server block, and NGINX refuses two blocks with the same URI. A path is therefore claimed across all three families at once — by an inline setting or by an attached resource alike — so every vertical that mounts something on a path checks here, not only against its own kind.

**Both mirrors compare `rendered_location()` output, not the stored value.** An anchored path renders as a regex location, so `^/api` and `~ ^/api` are one location and must be one claim. The render-time mirror is `src/common/utils/location_claims.py`; **normalizing only one mirror produces a false refusal** — the guard rejecting an attachment NGINX would accept. `tests/unit/db/test_redirects.py` pins both directions.

## Sessions

**`_db_session` is not reentrant.** It yields the shared scoped session and its `finally` calls `session.remove()`, so a nested `with self._db_session()` closes the session the outer block holds: everything it loaded becomes detached and anything pending is discarded. Never call another session-opening method from inside a session — resolve the value first and pass it in, or pass `session=` where the callee accepts one.

## Migrations

**Rule: no revision is written, generated or sketched without an explicit request.**

When one is requested:

- `misc/migration/create.sh` is the **only** supported generator. It boots the scheduler at the original tag, applies every existing migration in bulk, then generates the new one.
- `env.py` parses the `-m "Upgrade to version <X>"` message to auto-inject the `bw_metadata.version` bump and the `last_pro_check` reset. A hand-run `alembic revision` silently loses both.
- `env.py` carries suppression lists (`_IGNORED_ALTER_COLUMNS`, `_IGNORED_INDEXES`, `_IGNORED_CONSTRAINTS`) that can eat operations you need. Diff what was generated against the drift you expected.
- `src/scheduler/entrypoint.sh` maps version → revision by globbing `*_upgrade_to_version_<normalized>.py` and taking the leading field, so **exactly one file per version string may exist** in each engine directory.
- `env.py`'s own `version_locations` derivation is dead on the stamp/upgrade path — `command.stamp` builds its `ScriptDirectory` from the config before `env.py` runs. Production works only because the entrypoint `sed`s `alembic.ini` on disk first. Anything running alembic in-process must set `version_locations` itself.

### Why migration bugs hide

`create_all(checkfirst=True)` silently creates a missing **table** on every scheduler boot but never adds a **column** to an existing one. A fresh install therefore builds its schema from the model and always looks healthy, while an upgrade from a previous version runs the revision chain and breaks. **Only the upgrade path exercises migrations — test that, not a clean boot.**

The same shape defeats naive tests: a test that calls `Base.metadata.create_all(engine)` first has every current column present before alembic runs, so a missing `add_column` is undetectable by construction. A migration test must start from a **real old** schema.

Two per-engine reflection blind spots to know about: SQLAlchemy reflects a MariaDB `ENUM` back as a bare `ENUM` with the labels dropped (read `information_schema.column_type` instead), and it excludes `sqlite_autoindex_*`, so index drift originating from a UNIQUE constraint is invisible on SQLite (check the unique constraints instead).

## Testing

Unit tests live in `tests/unit/db/` and run once per selected engine. SQLite gets a fresh temporary file per test; PostgreSQL and MariaDB reset a shared schema because the database methods commit internally. See [../../../tests/AGENTS.md](../../../tests/AGENTS.md) and `tests/unit/README.md` for the matrix setup.
