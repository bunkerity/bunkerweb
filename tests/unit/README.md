# BunkerWeb unit tests (1.6.x)

Fast, isolated pytest coverage for Python components. These tests complement the Docker,
Linux and orchestration integration suites by checking method-level behaviour without
starting a BunkerWeb stack. The framework and most test files are ported from the `1.7`
branch and pruned to what holds on 1.6 source (see "dev (1.6.x) differences").

## Setup

Python 3.14, matching the images. Use a dedicated virtualenv, never the repo's `.venv`:

```bash
uv venv -p python3.14 .venv-unit
uv pip install -p .venv-unit/bin/python --require-hashes -r tests/unit/requirements.txt
```

Pins follow the versions BunkerWeb ships (`src/**/requirements.in`). After changing
`requirements.in`, relock with
`uv pip compile -q -p python3.14 --generate-hashes tests/unit/requirements.in -o tests/unit/requirements.txt`.

Run from a git checkout that has the release tags (a full clone, or `fetch-depth: 0` in CI):
`db/test_upgrade_schema_parity.py` reads old schemas with `git show vX.Y.Z:src/common/db/model.py`.
From a source tarball or a shallow clone it fails (measured: 6 failed, 54 errors, everything else green).

## Running

Pytest settings live in root `pyproject.toml`; `testpaths = ["tests/unit"]` makes a bare
`pytest` from the repository root collect this suite. Explicit paths select a component.

Default SQLite suite, including dev's standalone scripts (`legacy/`):

```bash
timeout -k 30 1500 .venv-unit/bin/python -m pytest tests/unit
```

Skip the slower DB integration-style tests:

```bash
timeout -k 30 1500 .venv-unit/bin/python -m pytest tests/unit -m 'not slow'
```

Coverage floors are enforced separately from test success. See [Component coverage gate](#component-coverage-gate).

Full database matrix. Run it **serially**: only one run may use the shared PostgreSQL or
MariaDB database at a time, and concurrent schema resets deadlock. `down` always runs, so a
hung run cannot leave locks behind for the next one:

```bash
free -m # require >= 4 GiB available and <= 90% swap used
docker compose -p bwunit -f tests/unit/docker-compose.test-db.yml up -d --wait
timeout -k 30 2400 env BW_TEST_PG_URI=postgresql://bw:bw@127.0.0.1:5433/bw_test \
  BW_TEST_MARIA_URI=mariadb://bw:bw@127.0.0.1:3307/bw_test \
  BW_TEST_MYSQL_URI=mysql://bw:bw@127.0.0.1:3308/bw_test \
  .venv-unit/bin/python -m pytest tests/unit --db-engines=sqlite,postgresql,mariadb,mysql \
  -p randomly --randomly-seed=12345 -rs; rc=$?
docker compose -p bwunit -f tests/unit/docker-compose.test-db.yml down -v; echo "pytest rc=$rc"
```

`--db-engines` overrides `BW_TEST_DB_ENGINES`. Unconfigured or unreachable optional engines
are skipped: a skip mentioning `not configured` or `not reachable` means the matrix did not
run. A session leak only hangs when the leaking test runs before another test resets the same
table, so try a few `--randomly-seed` values. Exit 124 is a hang: `faulthandler_timeout`
(120 s) prints the stuck stack in the log.

## dev (1.6.x) differences

- **`legacy/`**: dev already had standalone scripts at the root of `tests/unit/`
  (`test_*.py` unittest or plain scripts, `test_*.lua`, `test_*.sh`, `test_*.cjs`). Each owns
  its `sys.path` and its own `app` package, so they cannot share pytest's interpreter: the
  root conftest ignores root `test_*.py`, and `legacy/test_legacy_scripts.py` runs each one in
  a subprocess (`lua`, `node` and `redis-server` cases skip when the binary is missing).
- **`KNOWN_FAILING`** in that wrapper lists scripts that are red on committed dev (stale
  against current source, or needing OpenResty modules), as strict xfails: a script that
  starts passing turns the run red, so remove its entry then.
- **`jobs/conftest.py`**: the fixture HTTP servers swallow per-request errors. 1.7's version
  can abort the interpreter at shutdown (`_enter_buffered_busy`) when a daemon thread is still
  printing a traceback.
- **Not ported**: tests of 1.7-only code (`db_methods`, `plugin_extensions`, `default_server`,
  worker, Celery broker), files importing `src/scheduler/main.py` (they `_exit` the run), and
  test functions pinning 1.7-only behaviour. Ported files had only those functions removed;
  no surviving assertion was changed.
- **`api_app` lane**: see "The `api_app` lane".

## The `api_app` lane

Separate invocation, separate pins, opt-in. It imports the API's `app` package, which cannot
share an interpreter with the UI's. Without the env var the directory is ignored even when
named explicitly:

```bash
uv pip install -p .venv-unit/bin/python --require-hashes -r tests/unit/api_app/requirements.txt
timeout -k 30 300 env BW_API_APP_LANE=1 .venv-unit/bin/python -m pytest tests/unit/api_app
```

## Layout

| Path | Purpose |
| --- | --- |
| `conftest.py` | Source-path setup, engine selection, environment isolation, base DB fixture |
| `fixtures/engines.py` | Engine URI handling, reachability checks, schema reset |
| `fixtures/seed.py` | FK-valid deterministic seed builders |
| `legacy/` | Subprocess wrapper for dev's standalone root scripts |
| `common/` | Shared utilities, parsers and Lua helpers |
| `db/` | `Database` persistence behaviour |
| `api/` | API database methods (`APIDatabase` loaded by file path, keeping `app` free for the UI) |
| `ui/` | UI database methods, templates, static assets and helpers |
| `gen/` | Configurator, Templator and rendered NGINX config |
| `jobs/`, `letsencrypt/`, `linux/`, `cli/` ... | Per-component logic |

## Conventions

- Tests consuming `db`, `api_db` or `ui_db` run once per selected engine.
- SQLite uses a fresh temporary file per test. PostgreSQL and MariaDB reset the shared test
  schema because database methods commit internally.
- Seeds remain foreign-key valid across every engine and use fixed timestamps where needed.
- Database mutators return `""` on success or an error string unless their documented return
  contract says otherwise; assert the result before reading state back.
- Expensive DB integration-style tests use `@pytest.mark.slow`.

## Component coverage gate

Run the SQLite/UI and API-app suites in separate interpreters, then combine their line data.
Coverage.py 7.17's subprocess patch includes Python scripts launched by the legacy wrapper;
no manual startup hook is needed. Lua execution is outside this Python gate.

```bash
mkdir -p .cache/unit-coverage
COVERAGE_FILE=.cache/unit-coverage/sqlite timeout -k 30 1500 .venv-unit/bin/python -m pytest tests/unit --cov --cov-report=
uv pip install -p .venv-unit/bin/python --require-hashes -r tests/unit/api_app/requirements.txt
COVERAGE_FILE=.cache/unit-coverage/api BW_API_APP_LANE=1 timeout -k 30 300 .venv-unit/bin/python -m pytest tests/unit/api_app --cov --cov-report=
COVERAGE_FILE=.cache/unit-coverage/combined .venv-unit/bin/python -m coverage combine --keep .cache/unit-coverage/sqlite .cache/unit-coverage/api
.venv-unit/bin/python tests/unit/coverage_gate.py .cache/unit-coverage/combined --json .cache/unit-coverage/gate.json
```

The gate also accepts several input data files directly; it unions their executed lines
without changing the inputs. Every first-party Python file is counted even when tests never
import it. Statement counts come from Coverage.py's parser, so unimported scheduler code and
core-plugin UI actions contribute uncovered statements.

Floors live in `FLOORS` at the top of `coverage_gate.py`:

| Floor | Components |
| --- | --- |
| 70% | `src/common/gen`, `src/common/db`, `src/common/utils` + `src/common/cli`, `src/api` |
| 50% | `src/ui`, `src/autoconf`, `src/scheduler`, core-plugin jobs and UI |

The shared `src/common/api` helper belongs to utils/CLI. Backup's shared `backup.py` and
`bwcli/` helpers belong to core jobs. Vendored `src/deps/` and ModSecurity CRS files,
Alembic migrations and `gunicorn.conf.py` files are excluded. Other first-party paths must
have a component assignment; an unmapped file is an error.

The table prints executable statements, covered statements, percentage, floor and the minimum
additional covered statements required (`gap`). Exit 0 means all floors pass; exit 1 means at
least one component is below its floor; exit 2 means invalid input or configuration. JSON has
`passed` and `components`, with the same numbers. Empty components have no coverage obligation.

The separate CI `coverage` job enforces these floors on push/PR. Existing SQLite and engine
matrix jobs retain their test-success checks. Current coverage is below these approved floors;
that failure is intentional until coverage work raises each component above its threshold.

## Lua module checklist

Every first-party Lua module, relative to `src/bw/lua/` and `src/common/core/` (vendored `antibot/captcha.lua`, `crowdsec/lib/` and `middleclass.lua` excluded), with the test that executes it: "module" runs the shipped file under plain `lua` with OpenResty stubbed, "fragment" slices a function out of the source and runs only that, "standalone" is a root `test_*.lua` run by `legacy/test_legacy_scripts.py`. `none` means no passing test executes the file (the xfailed `test_lua_crowdsec_promotion.lua`, `test_lua_crowdsec_rewritten.lua` and `test_letsencrypt_passthrough.lua` do not count), (L1) marks the request-path lane's files and (L3) the plugin lane's.

| Module | Test file (`tests/unit/`) | How it runs |
| --- | --- | --- |
| `bunkerweb/acme.lua` | `common/test_bw_acme_lua.py` | pytest, module |
| `bunkerweb/api.lua` | `test_lua_api_leases.lua`; `common/test_api_audit_preflight_lua.py` | standalone; pytest fragment |
| `bunkerweb/banlease.lua` | `test_lua_banlease.lua`, `test_lua_banlease_write.lua` | standalone |
| `bunkerweb/cachestore.lua` | `common/test_bw_cachestore_lua.py` | pytest, module |
| `bunkerweb/clusterstore.lua` | `common/test_duration_readers_lua.py` | pytest, module |
| `bunkerweb/ctx.lua` | `common/test_bw_ctx_lua.py` | pytest, module |
| `bunkerweb/datastore.lua` | `common/test_datastore_worker_lru_exptime.py` | pytest, module |
| `bunkerweb/duration.lua` | `common/test_duration_parser.py`, `common/test_duration_regex_parity.py` | pytest, module |
| `bunkerweb/helpers.lua` | `test_lua_init_store_order.lua` | standalone |
| `bunkerweb/logger.lua` | `common/test_bw_logger_lua.py` | pytest, module |
| `bunkerweb/mmdb.lua` | `common/test_bw_mmdb_lua.py` | pytest, module |
| `bunkerweb/plugin.lua` | `common/test_bw_plugin_lua.py` | pytest, module |
| `bunkerweb/pushswap.lua` | `test_lua_pushswap_sentinel.lua` | standalone |
| `bunkerweb/rediskeys.lua` | `common/test_redis_cluster_nodes_default_port.py`, `test_lua_rediskeys.lua` | pytest, module; standalone |
| `bunkerweb/utils.lua` | `test_lua_is_banned_leases.lua`; `common/test_header_rules_lua.py` | standalone; pytest fragment |
| `antibot/antibot.lua` | `test_lua_rdns_skip_empty.lua` | standalone |
| `authbasic/authbasic.lua` | `common/test_authbasic_behaviour_lua.py` (L1) | pytest, module |
| `badbehavior/badbehavior.lua` | `common/test_duration_readers_lua.py` | pytest, module |
| `blacklist/blacklist.lua` | `common/test_blacklist_behaviour_lua.py` | pytest, module |
| `bunkernet/bunkernet.lua` | `common/test_bunkernet_challenge_not_reported.py` | pytest fragment |
| `cors/cors.lua` | `common/test_duration_readers_lua.py`, `test_lua_cors_credentials.lua` | pytest, module; standalone |
| `country/country.lua` | `common/test_country_behaviour_lua.py` (L3) | pytest, module |
| `crowdsec/cache_partition.lua` | `common/test_crowdsec_cache_partition_lua.py` | pytest, module |
| `crowdsec/control.lua` | `common/test_crowdsec_control_already_absent_lua.py` | pytest, module |
| `crowdsec/crowdsec.lua` | `common/test_crowdsec_behaviour_lua.py` (L3) | pytest, module |
| `crowdsec/enforcement_state.lua` | `common/test_crowdsec_enforcement_state_lua.py` | pytest, module |
| `customcert/customcert.lua` | `common/test_customcert_empty_server_name_lua.py` | pytest, module (`init`) |
| `dnsbl/dnsbl.lua` | `common/test_dnsbl_behaviour_lua.py` | pytest, module |
| `errors/errors.lua` | `common/test_errors_behaviour_lua.py` (L3) | pytest, module |
| `greylist/greylist.lua` | `common/test_greylist_behaviour_lua.py` | pytest, module |
| `headers/headers.lua` | `common/test_headers_behaviour_lua.py` (L1) | pytest, module |
| `letsencrypt/letsencrypt.lua` | `common/test_init_empty_server_name_guards_lua.py` | pytest, module (`init`) |
| `limit/limit.lua` | `common/test_limit_behaviour_lua.py` (L1) | pytest, module |
| `metrics/metrics.lua` | `test_lua_metrics_seed.lua`, `test_lua_metrics_search_panes.lua` | standalone |
| `misc/misc.lua` | `common/test_misc_behaviour_lua.py` (L1) | pytest, module |
| `mtls/mtls.lua` | `common/test_mtls_behaviour_lua.py` (L1) | pytest, module |
| `redis/redis.lua` | `common/test_redis_behaviour_lua.py` | pytest, module |
| `reversescan/reversescan.lua` | `common/test_duration_readers_lua.py` | pytest, module |
| `robotstxt/robotstxt.lua` | `common/test_robotstxt_behaviour_lua.py` (L3) | pytest, module |
| `securitytxt/securitytxt.lua` | `common/test_securitytxt_behaviour_lua.py` (L1) | pytest, module |
| `selfsigned/selfsigned.lua` | `common/test_init_empty_server_name_guards_lua.py` | pytest, module (`init`) |
| `sessions/sessions.lua` | `common/test_duration_readers_lua.py` | pytest, module |
| `ssl/ssl.lua` | `common/test_ssl_behaviour_lua.py` (L3) | pytest, module |
| `ui/ui.lua` | `common/test_ui_behaviour_lua.py` (L1) | pytest, module |
| `whitelist/whitelist.lua` | `common/test_header_rules_plugins_lua.py` | pytest, module (header criterion) |
