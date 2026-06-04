# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

BunkerWeb is an open-source Web Application Firewall (WAF) built on NGINX with a modular plugin architecture. It provides "security by default" for web services through multiple integration modes (Docker, Kubernetes, Swarm, Linux) and is fully configurable via environment variables.

## Start Here

- **[AGENTS.md](AGENTS.md)** is the primary, short-form instruction file for AI agents — read it first for the repo map, critical architecture facts, and pitfalls.
- This CLAUDE.md is the long-form architecture/reference. Component-level guidance lives in per-directory CLAUDE.md files linked from AGENTS.md.
- [BUILD.md](BUILD.md) covers reproducible artifact builds; [CONTRIBUTING.md](CONTRIBUTING.md) covers the contribution process.

## Architecture

### Core Components

- **BunkerWeb Core** (`src/bw/`, `src/common/core/`): NGINX-based reverse proxy with security modules in Lua (request-time) and Python (jobs). Lua modules live in `src/bw/lua/bunkerweb/` (plugin.lua, ctx.lua, datastore.lua, etc.).
- **Scheduler** (`src/scheduler/`): Central orchestrator ("brain"). `main.py` runs the main loop; `JobScheduler.py` schedules jobs using Python's `schedule` library and **dispatches execution to Celery workers** (see `src/worker/`) rather than running them in-process. Still owns config reload orchestration for BunkerWeb instances.
- **Worker** (`src/worker/`): Celery-based distributed job executor. `app.py` configures the Celery app with a Redis broker and two queues — `default` (fast jobs) and `heavy` (certbot, blocklist downloads, backups, etc.; see the `HEAVY_JOBS` set in `app.py`). `tasks.py` defines the `execute_job` Celery task; `executor.py` dynamically loads and runs plugin jobs from `src/common/core/*/jobs/`. Workers run independently of the Scheduler and write results to the shared DB. Redis is required: `CELERY_BROKER_URL` defaults to `redis://localhost:6379/0`.
- **Autoconf** (`src/autoconf/`): Listens for Docker/Swarm/Kubernetes events and dynamically reconfigures BunkerWeb. Controllers in `controllers/`: DockerController, SwarmController, IngressController, GatewayController (all inherit from `Controller.py`).
- **API** (`src/api/`): FastAPI service. Entry point: `src/api/app/main.py`. Routers in `src/api/app/routers/` (`auth`, `bans`, `cache`, `configs`, `global_settings`, `instances`, `jobs`, `metadata`, `plugins`, `services`, `system`, `templates`, `users`). `core.py` is the router hub that assembles all routers — it is NOT the FastAPI app entry point.
- **Web UI** (`src/ui/`): Flask app using Blueprints. Entry point: `src/ui/main.py`. Routes in `src/ui/app/routes/` (~20 blueprints including configs, plugins, jobs, logs, instances, services, bans, cache, global_settings, templates, reports, etc.). Uses Flask-Login for auth and Jinja2 templates. `dependencies.py` is the central dependency injection point providing API_CLIENT, DATA, BW_CONFIG, BW_INSTANCES_UTILS, CORE_PLUGINS_PATH, EXTERNAL_PLUGINS_PATH, PRO_PLUGINS_PATH. The UI no longer accesses the database directly — all data flows through the API via `api_client.py`. Frontend assets are static files in `src/ui/app/static/` (no separate build system).
- **Database** (`src/common/db/`): SQLAlchemy ORM with `model.py` defining all tables (Plugins, Settings, Services, Jobs, Custom_configs, Users, etc.). `Database.py` wraps high-level query methods. Supports SQLite (WAL mode), MariaDB, MySQL, PostgreSQL with QueuePool for connection pooling.
- **Linux packaging** (`src/linux/`): Native deb/rpm packaging — systemd units, `postinst`/`prerm` scripts, `bwcli` installation. Used by the Linux integration mode.
- **Vendored deps** (`src/deps/`): Third-party dependencies (Lua modules, Python packages, NGINX modules) bundled into the Docker images and Linux packages.

### Configuration Flow

1. Settings defined as environment variables (e.g., `USE_ANTIBOT=captcha`, `AUTO_LETS_ENCRYPT=yes`)
2. Scheduler reads settings from environment or database
3. **Configurator** (`src/common/gen/Configurator.py`) validates settings against `plugin.json` schemas with pre-compiled regex caches
4. **Templator** (`src/common/gen/Templator.py`) renders NGINX configs from Jinja2 templates (`src/common/confs/`) using ProcessPoolExecutor for parallel rendering
5. BunkerWeb instances reload with new configuration
6. In multisite mode, prefix settings with server name: `www.example.com_USE_ANTIBOT=captcha`
7. Multiple settings use numeric suffixes: `REVERSE_PROXY_URL_1=/api`, `REVERSE_PROXY_HOST_1=http://backend1`

### Plugin System

Each core module in `src/common/core/*/` contains:

- `plugin.json`: Metadata with settings schema (id, name, version, stream, settings with context/type/regex/default, jobs array with schedule/reload/async flags)
- `jobs/` folder: Python scripts for periodic tasks (e.g., downloading blocklists). Jobs specify `every` (once/minute/hour/day/week) and `reload` flag.
- Lua code for request-time processing
- `confs/` folder: NGINX configuration templates

Plugin load order defined in `src/common/core/order.json`. External plugins follow the same structure.

### Lua Request Processing Pipeline

The Lua runtime (`src/bw/lua/bunkerweb/`) processes requests through plugin hooks at NGINX phases: access, header_filter, body_filter, log. Key modules:

- `plugin.lua`: Plugin loader and execution across phases
- `ctx.lua`: Per-request context management
- `datastore.lua`: Shared data persistence (shared dict backed)
- `cachestore.lua`: Request-level caching
- `clusterstore.lua`: Cluster-aware storage (Redis)
- `helpers.lua`, `utils.lua`: Shared utilities
- `api.lua`: Internal API handling
- `mmdb.lua`: MaxMind GeoIP database reader

`src/bw/lua/middleclass.lua` provides OOP support (third-party library, excluded from linting).

### Shared Utilities (src/common/utils/)

- `common_utils.py`: Docker secrets handling, hashing, version info, integration detection
- `logger.py`: Logging with syslog support
- `jobs.py`: Job helpers (atomic writes, file hashing, tar operations)
- `ApiCaller.py`: HTTP client for inter-component API calls

## Development Commands

### Setup

```bash
pip install -r src/scheduler/requirements.txt
pip install -r src/ui/requirements.txt
pip install -r src/api/requirements.txt
pre-commit install
```

### Build

```bash
# Build Docker image (all-in-one)
docker build -f src/all-in-one/Dockerfile -t bunkerweb:dev .

# Build specific component
docker build -f src/scheduler/Dockerfile -t bunkerweb-scheduler:dev .
docker build -f src/ui/Dockerfile -t bunkerweb-ui:dev .
docker build -f src/api/Dockerfile -t bunkerweb-api:dev .
docker build -f src/worker/Dockerfile -t bunkerweb-worker:dev .
docker build -f src/autoconf/Dockerfile -t bunkerweb-autoconf:dev .
```

### Linting & Formatting

```bash
# Run all pre-commit hooks
pre-commit run --all-files

# Individual tools
black .                          # Python formatting (160 char lines, config in pyproject.toml)
flake8 --max-line-length=160 --ignore=E266,E402,E501,E722,W503 .  # Python linting (config in .pre-commit-config.yaml, no .flake8 file)
stylua .                         # Lua formatting (no .stylua.toml, uses defaults)
luacheck src/                    # Lua linting (--std min, config in .luacheckrc: globals ngx/delay/unpack, ignores 411)
shellcheck scripts/*.sh          # Shell script linting
prettier --write "**/*.{js,ts,css,html,json,yaml,md}"  # Frontend formatting
codespell                        # Spell checking
refurb                           # Python refactoring suggestions (excludes tests/)
```

### Run Development Instance

```bash
# Full stack with UI + API (recommended)
docker compose -f misc/dev/docker-compose.ui.api.yml up -d
```

Key dev compose files in `misc/dev/` (18 total):

- `docker-compose.ui.api.yml` — Full stack (UI + API + core + MariaDB) — **recommended**
- `docker-compose.ui.yml` — UI + API + core + MariaDB (UI requires bw-api)
- `docker-compose.all-in-one.yml` — Single container with all components
- `docker-compose.autoconf.yml` — Docker autoconf mode
- `docker-compose.autoconf.ui.api.yml` — Autoconf with UI + API
- `docker-compose.wizard.yml` — Setup wizard
- Various `.misc.` variants include additional services (syslog-ng, etc.)

Dev credentials: UI `admin`/`P@ssw0rd`, API `admin`/`P@ssw0rd`, DB `bunkerweb`/`secret`.

The dev compose mounts `src/ui/app/` and `src/api/app/` as read-only volumes, so UI and API code changes apply without rebuilding (restart the container to pick up changes).

`docker-compose.ui.api.yml` brings up a Redis (Valkey) broker (`bw-jobs-broker`) and a `bw-worker` service alongside the scheduler — required since the Celery-based job executor landed. Other compose files in `misc/dev/` do not yet include the worker/broker, so jobs requiring the Celery path will not run under those stacks.

### Database Migrations

Alembic migrations in `src/common/db/alembic/` with separate version directories per DB type: `mariadb_versions/`, `mysql_versions/`, `postgresql_versions/`, `sqlite_versions/`.

## Key Files

- `src/common/settings.json`: Master list of all core settings with validation rules (context, default, regex, type per setting)
- `src/common/core/order.json`: Plugin load order
- `src/common/db/model.py`: SQLAlchemy ORM models for all tables
- `src/common/db/Database.py`: High-level database wrapper
- `src/common/gen/Configurator.py`: Settings validation engine
- `src/common/gen/Templator.py`: NGINX config renderer
- `src/scheduler/main.py`: Scheduler entry point
- `src/scheduler/JobScheduler.py`: Job scheduling orchestrator (dispatches to Celery workers)
- `src/worker/app.py`: Celery app config, queue routing (default/heavy), DB lifecycle hooks
- `src/worker/tasks.py`: `execute_job` Celery task — job execution entry point
- `src/ui/main.py`: Web UI entry point (registers all Blueprints)
- `src/ui/app/dependencies.py`: UI dependency injection
- `src/ui/app/api_client.py`: UI API client — all UI data access goes through the API
- `src/api/app/main.py`: API entry point (FastAPI app creation)
- `src/api/app/routers/core.py`: Router hub (assembles all API routers)
- `pyproject.toml`: Black config (160 char lines)
- `.pre-commit-config.yaml`: All linting/formatting rules
- `.luacheckrc`: Luacheck globals and ignores
- `AGENTS.md`: Primary short-form entry point for AI agents — indexes component CLAUDE.md files, critical architecture facts, and pitfalls. Keep in sync with this file.
- `BUILD.md`: Reproducible artifact build instructions (Docker images, Linux packages).
- `CONTRIBUTING.md`: Contribution process and review expectations.
- `.github/copilot-instructions.md`: Mirror of this guidance for GitHub Copilot — keep in sync when editing this file

## Important Patterns

### Settings Context

- `global`: Applied to all servers (e.g., `WORKER_PROCESSES`, `LOG_LEVEL`)
- `multisite`: Can be server-specific (prefix with `SERVER_NAME_`)

### Security Modes

- `detect`: Log threats without blocking
- `block`: Actively block threats (default)

### Integration Modes

Set one of these to `yes`: `AUTOCONF_MODE`, `SWARM_MODE`, `KUBERNETES_MODE`

### Testing

Tests are **integration-focused only** — they spin up real Docker/Linux environments and hit BunkerWeb with actual HTTP requests. There is no unit-test suite under `tests/`; verify component behavior by running the relevant integration target below.

```bash
python3 tests/main.py docker              # Docker integration tests
python3 tests/main.py autoconf            # Autoconf tests
python3 tests/main.py swarm               # Swarm tests
python3 tests/main.py kubernetes           # Kubernetes tests
python3 tests/main.py linux debian         # Linux tests (with distro)
```

- Tests scan `examples/*/tests.json` for test scenarios (type: string/status, url, expected results with timeout/delay)
- Real Docker environments with actual HTTP requests — tests verify observable behavior, not internals
- Test classes: DockerTest, AutoconfTest, SwarmTest, KubernetesTest, LinuxTest

## Key Conventions

- Python: snake_case (modules/functions), PascalCase (classes), Black formatting at 160 chars
- Lua: lowercase module names, descriptive function names, StyLua formatting
- Shell: POSIX-compatible unless `#!/bin/bash` shebang, pass ShellCheck
- Commit messages: Conventional Commits (`feat:`, `fix:`, `docs:`) with optional scope in parens (e.g., `fix(ui):`, `feat(gunicorn):`)
- UI translations in `src/ui/app/static/locales/`

## External Resources

- Documentation: <https://docs.bunkerweb.io>
- Official Plugins: <https://github.com/bunkerity/bunkerweb-plugins>
- Web UI Demo: <https://demo-ui.bunkerweb.io>
