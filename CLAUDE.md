# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

BunkerWeb is an open-source Web Application Firewall (WAF) built on NGINX with a modular plugin architecture. It provides "security by default" for web services through multiple integration modes (Docker, Kubernetes, Swarm, Linux) and is fully configurable via environment variables.

## Start Here

- **[AGENTS.md](AGENTS.md)** is the primary, short-form instruction file for AI agents — read it first for the repo map, critical architecture facts, and pitfalls.
- This CLAUDE.md is the long-form architecture reference. Per-directory guidance lives in each directory's `AGENTS.md`, indexed from AGENTS.md.
- [BUILD.md](BUILD.md) covers reproducible artifact builds; [CONTRIBUTING.md](CONTRIBUTING.md) covers the contribution process.

**On enumerations:** this file deliberately does not list routers, blueprints, DB mixins, or plugins. Those sets grow with every feature and any list here would be wrong within weeks. It documents where things live, how they are named, and what the filesystem cannot tell you. Run `ls` for the current set.

## Architecture

### Core Components

- **BunkerWeb Core** (`src/bw/`, `src/common/core/`): NGINX-based reverse proxy with security modules in Lua (request-time) and Python (jobs). The Lua runtime lives in `src/bw/lua/bunkerweb/`.
- **Scheduler** (`src/scheduler/`): central orchestrator ("brain"). `main.py` runs the main loop; `JobScheduler.py` schedules plugin jobs with Python's `schedule` library and **dispatches execution to Celery workers** (`src/worker/`) rather than running them in-process. Still owns config generation and reload orchestration for BunkerWeb instances.
- **Worker** (`src/worker/`): Celery-based distributed job executor. `app.py` configures the Celery app with a Redis/Valkey broker and two queues, `default` and `heavy`; the heavy-job set and the routing function live in `src/common/utils/job_queues.py` (`HEAVY_JOBS`, `queue_for`) and are re-exported from `app.py`. `tasks.py` defines the `execute_job` task; `executor.py` dynamically loads plugin jobs from `src/common/core/*/jobs/`. Workers run independently of the Scheduler and write results to the shared DB. `CELERY_BROKER_URL` defaults to `redis://127.0.0.1:6379/0` — a literal IPv4, deliberately, because `localhost` resolution is ambiguous on dual-stack hosts.
- **Autoconf** (`src/autoconf/`): listens for Docker/Swarm/Kubernetes events and dynamically reconfigures BunkerWeb. One controller per integration in `controllers/`, all inheriting `Controller.py`.
- **API** (`src/api/`): FastAPI service. Entry point `src/api/app/main.py`; `app/routers/core.py` is the router hub, not the app. One router file per resource under `app/routers/`, each mounted at its own prefix. Auth is a per-endpoint dependency, not middleware.
- **Web UI** (`src/ui/`): Flask app using Blueprints. Entry point `src/ui/main.py`; one blueprint file per page under `src/ui/app/routes/`. `dependencies.py` is the dependency-injection point; `api_client.py` is the only data path — the UI does not touch the database. Server-rendered Jinja2 plus vanilla JS, no bundler.
- **Database** (`src/common/db/`): SQLAlchemy 2.0 ORM. `model.py` defines every table; `Database.py` is a thin coordinator (connection pooling, sessions) that composes high-level query mixins from `db_methods/`. Supports SQLite (WAL), MariaDB, MySQL, PostgreSQL. See [src/common/db/AGENTS.md](src/common/db/AGENTS.md).
- **Linux packaging** (`src/linux/`): native deb/rpm packaging, systemd units, `postinst`/`prerm`. The `bwcli` entry point itself ships from `src/common/helpers/bwcli`, with per-plugin subcommands under `src/common/core/*/bwcli/`.
- **Vendored deps** (`src/deps/`): third-party Lua modules, Python packages and NGINX modules bundled into the images and packages.

### Configuration Flow

1. Settings are defined as environment variables (e.g. `USE_ANTIBOT=captcha`, `AUTO_LETS_ENCRYPT=yes`).
2. Scheduler reads settings from the environment or the database.
3. **Configurator** (`src/common/gen/Configurator.py`) validates settings against `plugin.json` schemas with pre-compiled regex caches.
4. **Templator** (`src/common/gen/Templator.py`) renders NGINX configs from Jinja2 templates (`src/common/confs/`) using a ProcessPoolExecutor.
5. BunkerWeb instances reload with the new configuration.
6. In multisite mode, settings are prefixed with the server name: `www.example.com_USE_ANTIBOT=captcha`.
7. Repeated setting families use numeric suffixes: `REVERSE_PROXY_URL_1=/api`, `REVERSE_PROXY_HOST_1=http://backend1`.

### Plugin System

Each core module in `src/common/core/*/` may contain:

- `plugin.json`: metadata and settings schema (id, name, version, stream, settings with context/type/regex/default, `jobs` with schedule/reload/async flags, and optional `extensions`).
- `jobs/`: Python scripts run periodically by the Worker.
- Lua code for request-time processing, and `confs/` for NGINX templates.
- `ui/`: an optional Flask blueprint contributing a plugin page.
- `api/router.py`: an optional FastAPI router. Plugins declaring `extensions.api` are auto-discovered by `src/api/app/routers/plugin_loader.py` and mounted at `/<plugin_id>` with the auth guard and rate limiter injected at mount time — a plugin author cannot forget authentication, and cannot shadow an existing core prefix.
- `bwcli/`: optional CLI subcommands.

Load order is defined in `src/common/core/order.json`. External and PRO plugins follow the same structure. Details: [src/common/core/AGENTS.md](src/common/core/AGENTS.md).

**Job exit codes are a protocol**: `1` = something changed, which ships the job cache to the instances and requests a debounced reload; `0` = success, nothing changed; anything else = failure. Returning `0` after writing files means the output never reaches the instances.

### Lua Request Processing Pipeline

The Lua runtime (`src/bw/lua/bunkerweb/`) runs plugin hooks at NGINX phases: init, access, header_filter, body_filter, log. Core modules there cover plugin loading and per-request context, the datastore/cachestore/clusterstore storage tiers (shared dict and Redis), the internal API surface, ban synchronization, rate limiting, and the MaxMind-format GeoIP reader used by the `geoip` core plugin. `src/bw/lua/middleclass.lua` is a third-party OOP library, excluded from linting. See [src/bw/AGENTS.md](src/bw/AGENTS.md).

### Cross-Cutting Subsystems

These span the DB, API and UI at once; each is owned by a mixin in `db_methods/`, an API surface, and a UI blueprint of the same name.

- **Attachable resources** — reusable redirects and upstream pools attached to services, plus resource groups. `reverseproxy`, `grpc` and `redirect` all render a `location` into the same server block, so a path is claimed across all three families at once: the mutation-time guard is `db_methods/locations.py`, the render-time mirror is `src/common/utils/location_claims.py`. Both compare _rendered_ locations (`^/api` and `~ ^/api` are one location), and normalizing only one mirror produces a false refusal.
- **Certificates** — centralized certificate storage and lifecycle, distinct from the `letsencrypt`/`customcert`/`selfsigned` core plugins that feed it.
- **Workflows** — the security-workflow engine: a core plugin shipping both a Lua evaluator and its own API router via the plugin extension mechanism.
- **Metrics and reports** — request metrics persisted to the database (HTTP and stream traffic are distinguished by a protocol discriminator), feeding the UI reports and threat-map pages.
- **i18n** — the UI is server-translated through Flask-Babel (`src/ui/app/i18n.py`, `src/ui/app/lang_config.py`, `src/ui/babel.cfg`), with the JSON catalogs in `src/ui/app/static/locales/` as the authoring format. `en.json` is the source of truth; see that directory's README before adding keys.

### Shared Utilities (`src/common/utils/`)

- `common_utils.py`: Docker secrets handling, hashing, version info, integration detection
- `logger.py`: logging with syslog support
- `jobs.py`: job helpers (atomic writes, file hashing, tar operations)
- `ApiCaller.py`: HTTP client for inter-component API calls
- `job_queues.py`: Celery queue routing for jobs
- `location_claims.py`: render-time half of the location-namespace guard

## Development Commands

### Setup

```bash
pip install --require-hashes -r src/scheduler/requirements.txt
pip install --require-hashes -r src/ui/requirements.txt
pip install --require-hashes -r src/api/requirements.txt
pre-commit install
```

### Build

```bash
# All-in-one image
docker build -f src/all-in-one/Dockerfile -t bunkerweb:dev .

# Or a single component (scheduler, ui, api, worker, autoconf, ...)
docker build -f src/<component>/Dockerfile -t bunkerweb-<component>:dev .
```

### Linting & Formatting

```bash
pre-commit run --all-files        # everything, in the pinned versions
```

Individual tools, all configured in `.pre-commit-config.yaml` (line length 160 for Python, set in `pyproject.toml`): `black`, `flake8`, `refurb`, `codespell` for Python; `stylua` and `luacheck` for Lua (globals and ignores in `.luacheckrc`); `djlint` for the Jinja templates under `src/ui/app/templates` and `src/common/core/*/ui/*/templates`; `prettier` for JS/CSS/HTML/JSON/YAML/Markdown; `shellcheck` for shell.

Run the hooks rather than the bare tools — a local binary older than the pinned revision reformats files the hook would leave alone.

### Run Development Instance

```bash
docker compose -f misc/dev/docker-compose.ui.api.yml up -d   # full stack, recommended
```

`misc/dev/` holds one compose file per scenario (UI, API, autoconf, wizard, all-in-one, per-database, `.misc.` variants adding syslog-ng and friends). Dev credentials: UI `admin`/`P@ssw0rd`, API `admin`/`P@ssw0rd`, DB `bunkerweb`/`secret`.

`docker-compose.ui.api.yml` mounts `src/ui/app/` and `src/api/app/` read-only, so UI and API code changes apply without rebuilding.

Since the Celery job executor landed, a normal dev stack brings up a Redis/Valkey broker (`bw-jobs-broker`), a `bw-worker` and a `bw-api` alongside the scheduler; all-in-one variants bundle these inside the single container. The exceptions are the override fragments and helpers that need none of it — `docker-compose.db-mount.yml`, `docker-compose.test-db.yml`, and `docker-compose.bwcli.yml` (a one-shot `bwcli` runner, `--profile tools`).

### Database Migrations

Alembic migrations live in `src/common/db/alembic/` with one version directory per engine. **Never hand-author or generate a revision without an explicit request** — the only supported generator is `misc/migration/create.sh`. Read [src/common/db/AGENTS.md](src/common/db/AGENTS.md) before touching anything here.

## Key Files

- `src/common/settings.json`: master list of global settings with validation rules
- `src/common/core/order.json`: plugin load order
- `src/common/db/model.py`: SQLAlchemy ORM models
- `src/common/db/Database.py`: DB coordinator composing the `db_methods/` mixins
- `src/common/gen/Configurator.py`: settings validation engine
- `src/common/gen/Templator.py`: NGINX config renderer
- `src/scheduler/main.py`: scheduler entry point
- `src/scheduler/JobScheduler.py`: job scheduling, dispatch to Celery
- `src/worker/app.py`: Celery app config and queue wiring
- `src/worker/tasks.py`: `execute_job` — job execution, cache delivery, reload debounce
- `src/ui/main.py`: Web UI entry point
- `src/ui/app/dependencies.py`: UI dependency injection
- `src/ui/app/api_client.py`: UI API client — all UI data access goes through it
- `src/api/app/main.py`: API entry point
- `src/api/app/routers/core.py`: router hub
- `src/api/app/routers/plugin_loader.py`: plugin-shipped API router discovery
- `pyproject.toml`, `.pre-commit-config.yaml`, `.luacheckrc`, `stylua.toml`: style configuration
- `AGENTS.md`: short-form entry point for agents — keep in sync with this file
- `.github/copilot-instructions.md`: dispatcher pointing GitHub Copilot at AGENTS.md; keep its links valid when files move

## Important Patterns

### Settings Context

- `global`: applied to all servers (e.g. `WORKER_PROCESSES`, `LOG_LEVEL`)
- `multisite`: can be server-specific (prefix with the server name)

### Security Modes

- `detect`: log threats without blocking
- `block`: actively block threats (default)

### Integration Modes

Set one of `AUTOCONF_MODE`, `SWARM_MODE`, `KUBERNETES_MODE` to `yes`.

### Testing

Two tiers, both documented in [tests/AGENTS.md](tests/AGENTS.md): integration tests that spin up real Docker/Linux environments and hit BunkerWeb with actual HTTP requests, and a pytest unit suite under `tests/unit/` covering the Python layers across SQLite/PostgreSQL/MariaDB.

```bash
# Integration: <integration> <type> <release> <category>
./tests/scripts/test.sh docker core dev headers

# Unit
.venv-unit/bin/pytest
.venv-unit/bin/pytest --db-engines=sqlite,postgresql,mariadb
```

The legacy harness (`tests/main.py`, the `*Test.py` classes, `tests/examples/`) was deleted once the Swarm arm and Linux example mode closed its last two gaps. `staging-tests.yml`, its only caller, no longer runs anything.

A fresh install builds its schema from the model and always looks healthy; only an upgrade runs migrations. Exercise the upgrade path explicitly.

## Key Conventions

- Python: snake_case modules/functions, PascalCase classes, Black at 160 columns
- Lua: lowercase module names, descriptive function names, StyLua formatting
- Shell: POSIX-compatible unless a `#!/bin/bash` shebang says otherwise; must pass ShellCheck
- Commit messages: Conventional Commits (`feat:`, `fix:`, `docs:`) with an optional scope, e.g. `fix(ui):`
- User-visible UI strings go through the i18n catalogs, not into templates

## External Resources

- Documentation: <https://docs.bunkerweb.io>
- Official Plugins: <https://github.com/bunkerity/bunkerweb-plugins>
- Web UI Demo: <https://demo-ui.bunkerweb.io>
