# BunkerWeb unit tests

Fast, isolated unit tests for the Python layers. They complement the integration/e2e
tests (the deprecated `tests/` here, and the new e2e suite in `bunkerweb-tests`): unit
tests run in milliseconds and pin exact per-method behavior rather than observable HTTP
behavior.

**Milestone 1** covers the **database layer** (`src/common/db/`), validated against
SQLite, PostgreSQL and MariaDB.

## Setup (one-time)

BunkerWeb's runtime dependencies are not installed on the host (they are baked into the
container images), so use a dedicated virtualenv:

```bash
python3 -m venv .venv-unit
.venv-unit/bin/pip install -r tests/unit/requirements.txt
```

## Running

Fast loop — SQLite only (the default):

```bash
.venv-unit/bin/pytest
```

Pure-logic helpers only (no DB at all, instant):

```bash
.venv-unit/bin/pytest tests/unit/db/test_helpers_pure.py
```

Full multi-engine matrix (SQLite + PostgreSQL + MariaDB):

```bash
docker compose -f misc/dev/docker-compose.test-db.yml up -d --wait
export BW_TEST_PG_URI=postgresql://bw:bw@127.0.0.1:5433/bw_test
export BW_TEST_MARIA_URI=mariadb://bw:bw@127.0.0.1:3307/bw_test
.venv-unit/bin/pytest --db-engines=sqlite,postgresql,mariadb
# tear the throwaway databases down when finished:
docker compose -f misc/dev/docker-compose.test-db.yml down
```

Engine selection also reads `BW_TEST_DB_ENGINES` (the `--db-engines` option wins).
Engines that are unconfigured or unreachable are **skipped**, not failed.

## Layout

| Path | Purpose |
| --- | --- |
| `conftest.py` | `sys.path` injection, `--db-engines` option, the `db` fixture |
| `_paths.py` | the `src` directories injected onto `sys.path` |
| `fixtures/engines.py` | per-engine URI build / reachability probe / schema reset |
| `fixtures/seed.py` | composable, FK-valid seed builders |
| `db/` | DB-layer tests — one module per mixin domain |
| `api/` | `APIDatabase` users/permissions + `schemas.py` Pydantic validators |
| `ui/` | `UIDatabase` tests + `app/utils` bcrypt helpers (via the `app` package; needs Flask/bcrypt) |
| `common/` | pure-logic helpers (`common_utils`) — no DB, run once |
| `gen/` | `Configurator` validation, `has_permissions`, `Templator` SSL curve ranking |
| `scheduler/` | `JobScheduler` job validation + dispatch payloads |
| `worker/` | `executor` job-path sandbox guard |

## Conventions

- Tests using the `db` fixture run **once per selected engine** (ids `[sqlite]`,
  `[postgresql]`, `[mariadb]`).
- Isolation is **schema-level** (the DB methods commit internally, so transaction
  rollback can't isolate): SQLite gets a fresh temp file per test; PostgreSQL/MariaDB
  get `drop_all` + `create_all` per test.
- Seeds are FK-valid — PostgreSQL/MariaDB enforce foreign keys while SQLite does not, so
  the matrix catches integrity bugs SQLite would hide — and use fixed datetimes for
  determinism.
- DB mutators return `""` on success or an error string; assert the return value, then
  read the state back.

## Coverage status

**Done — full DB layer:** pure helpers, metadata, instances, services, jobs,
custom_configs, `bulk_add_in_fk_order`, `config_read` (multisite), plugins, templates,
API permissions (`APIDatabase`), UI RBAC / users / column preferences (`UIDatabase`) —
all in a single `pytest` run.

**Done — pure-logic (no DB, run once):** `common_utils` (hashing, version compare, plugin
tar determinism, tar/zip extraction safety), `api/app/schemas.py` Pydantic validators,
`gen/Configurator.py` (settings/plugin validation + variable filtering), `gen/utils.has_permissions`,
`gen/Templator.py` SSL ECDH-curve ranking, `scheduler/JobScheduler` job validation + dispatch,
`worker/executor` path-sandbox guard, `ui/app/utils` bcrypt password helpers.

Coverage on the unit-targeted modules runs 60–93% (services 93, api-users 88, api-permissions 87,
ui-preferences 91, ui-rbac 82, config_read/metadata/plugins ~75, Configurator/custom_configs/jobs ~60–66).
The deliberately-deferred high-risk files sit at 4–8% (see below) — by design, not a gap.

`src/api` and `src/ui` both expose a top-level `app` package. The API user/permission
mixins use only absolute imports, so the API fixture **recomposes** `APIDatabase` from
`src/api/app/models` without importing `app`. The UI mixins need `app.models...`, so the UI
fixture imports the real `UIDatabase` with `src/ui` on the path. Because only the UI imports
`app`, it resolves uniquely to `src/ui/app` — db, api and ui coexist in one process.

**Remaining / deferred (by design):**
- `api/app/rate_limit.py` — not unit-isolatable: relative `app.*` imports pull `app.config`
  (pydantic-settings) and `app.utils` (→ `APIDatabase`), plus fastapi/slowapi/biscuit/yaml.
  Importing it boots most of the app, so its parsing helpers belong to integration/e2e, not
  isolated unit tests. (The equivalent bcrypt helpers are covered via `ui/app/utils`.)
- `config_save`, `init_tables`, `plugins_update` — highest-risk; covered today by the
  behavioral snapshot harness in `misc/refactor/` (`snapshot.sh` + `db_snapshot.py`) and
  earmarked for a pytest integration tier later.
