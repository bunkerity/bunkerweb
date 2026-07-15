# BunkerWeb unit tests

Fast, isolated pytest coverage for Python components. These tests complement the Docker,
Linux, and orchestration integration suites by checking method-level behaviour without
starting a BunkerWeb stack.

## Setup

Runtime dependencies are normally installed in container images. Use a dedicated virtualenv
for local unit tests:

```bash
python3 -m venv .venv-unit
.venv-unit/bin/pip install -r tests/unit/requirements.txt
```

## Running

Default SQLite suite:

```bash
.venv-unit/bin/pytest
```

Pure normalization helpers only:

```bash
.venv-unit/bin/pytest tests/unit/common/test_common_utils.py tests/unit/common/test_unit_parser.py
```

Direct 1.7 changed-line coverage gate:

```bash
.venv-unit/bin/pytest tests/unit \
  --cov=src/common --cov=src/api --cov=src/ui \
  --cov=src/autoconf --cov=src/scheduler --cov=src/worker \
  --cov-branch --cov-report=json:coverage.json --cov-report=
.venv-unit/bin/python tests/unit/check_changed_coverage.py coverage.json --fail-under 80
```

Full database matrix:

```bash
docker compose -f misc/dev/docker-compose.test-db.yml up -d --wait
export BW_TEST_PG_URI=postgresql://bw:bw@127.0.0.1:5433/bw_test
export BW_TEST_MARIA_URI=mariadb://bw:bw@127.0.0.1:3307/bw_test
.venv-unit/bin/pytest --db-engines=sqlite,postgresql,mariadb
docker compose -f misc/dev/docker-compose.test-db.yml down
```

`--db-engines` overrides `BW_TEST_DB_ENGINES`. Unconfigured or unreachable optional engines
are skipped.

## Layout

| Path | Purpose |
| --- | --- |
| `conftest.py` | Source-path setup, engine selection, environment isolation, base DB fixture |
| `fixtures/engines.py` | Engine URI handling, reachability checks, schema reset |
| `fixtures/seed.py` | FK-valid deterministic seed builders |
| `common/` | Shared utility, parser, plugin-extension, and resource-group logic |
| `db/` | Database mixin and persistence behaviour |
| `api/` | API schemas, permissions, routing, and plugin loading |
| `ui/` | UI database methods, configuration validation, helpers, and routes |
| `gen/` | Configurator, Templator, and permission helpers |
| `autoconf/`, `scheduler/`, `worker/` | Orchestration component logic |
| `letsencrypt/`, `linux/` | Provider translation and installer behaviour |

## Conventions

- Tests consuming `db`, `api_db`, or `ui_db` run once per selected engine.
- SQLite uses a fresh temporary file per test. PostgreSQL and MariaDB reset the shared test
  schema because database methods commit internally.
- Seeds remain foreign-key valid across every engine and use fixed timestamps where needed.
- Database mutators return `""` on success or an error string unless their documented return
  contract says otherwise; assert the result before reading state back.
- Expensive DB integration-style tests use `@pytest.mark.slow`; exclude them with
  `pytest -m 'not slow'` when a shorter feedback loop is enough.

Only one matrix run may use a shared PostgreSQL or MariaDB database at a time. Concurrent
schema resets can deadlock; use separate databases for parallel runs.
