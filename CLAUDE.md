# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

BunkerWeb is an open-source Web Application Firewall (WAF) built on NGINX with a modular plugin architecture. It provides "security by default" for web services through multiple integration modes (Docker, Kubernetes, Swarm, Linux) and is fully configurable via environment variables.

## Architecture

### Core Components

- **BunkerWeb Core** (`src/bw/`, `src/common/core/`): NGINX-based reverse proxy with security modules in Lua (request-time) and Python (jobs). Entry point: `src/bw/lua/bunkerweb.lua`.
- **Scheduler** (`src/scheduler/`): Central orchestrator ("brain"). `main.py` runs the main loop; `JobScheduler.py` manages job execution with thread pools. Uses Python's `schedule` library.
- **Autoconf** (`src/autoconf/`): Listens for Docker/Swarm/Kubernetes events and dynamically reconfigures BunkerWeb.
- **API** (`src/api/`): FastAPI service with router-based architecture (`src/api/app/routers/` — auth, instances, services, configs, plugins, jobs). IP whitelist and rate limiting support.
- **Web UI** (`src/ui/`): Flask app using Blueprints for routing (`src/ui/app/routes/` — configs, plugins, jobs, logs, instances, profile, etc.). Uses Flask-Login for auth and Jinja2 templates. `dependencies.py` is the central dependency injection point providing DB, DATA, BW_CONFIG, BW_INSTANCES_UTILS.
- **Database** (`src/common/db/`): SQLAlchemy ORM with `model.py` defining all tables (Plugins, Settings, Services, Jobs, Custom_configs, Users, etc.). `Database.py` wraps high-level query methods. Supports SQLite (WAL mode), MariaDB, MySQL, PostgreSQL with QueuePool for connection pooling.

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

External plugins follow the same structure.

### Lua Request Processing Pipeline

The Lua runtime (`src/bw/lua/`) processes requests through plugin hooks at NGINX phases: access, header_filter, body_filter, log. Key files:

- `plugin.lua`: Plugin loader and execution across phases
- `ctx.lua`: Per-request context management
- `datastore.lua`: Shared data persistence (shared dict backed)
- `cachestore.lua`: Request-level caching
- `clusterstore.lua`: Cluster-aware storage (Redis)

### Core Plugins (src/common/core/)

42 plugins organized by function:

- **Auth**: antibot (CAPTCHA), authbasic, mtls, crowdsec
- **Threat Detection**: modsecurity (OWASP WAF), badbehavior, dnsbl, reversescan
- **Access Control**: whitelist, blacklist, greylist, country, limit (rate limiting)
- **SSL/TLS**: ssl, letsencrypt, customcert, selfsigned
- **Proxy & Routing**: reverseproxy, realip, redirect, grpc, php
- **Performance**: gzip, brotli, clientcache, redis
- **Headers & Content**: headers, cors, inject, robotstxt, securitytxt
- **Management**: sessions, metrics, backup, templates, bunkernet, ui, db, jobs

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
```

### Linting & Formatting

```bash
# Run all pre-commit hooks
pre-commit run --all-files

# Individual tools
black .                          # Python formatting (160 char lines)
flake8 .                         # Python linting (ignores E266,E402,E501,E722,W503)
stylua .                         # Lua formatting
luacheck src/                    # Lua linting (--std min)
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

Dev compose files in `misc/dev/`:

- `docker-compose.ui.api.yml` — Full stack (UI + API + core + MariaDB) — **recommended**
- `docker-compose.ui.yml` — UI only (no API)
- `docker-compose.all-in-one.yml` — Single container with all components
- `docker-compose.autoconf.yml` — Docker autoconf mode
- `docker-compose.wizard.yml` — Setup wizard

Dev credentials: UI `admin`/`P@ssw0rd`, API `admin`/`P@ssw0rd`, DB `bunkerweb`/`secret`.

The dev compose mounts `src/ui/app/` and `src/api/app/` as read-only volumes, so UI and API code changes apply without rebuilding (restart the container to pick up changes).

### Database Migrations

```bash
# Alembic migrations in src/common/db/alembic/
# Separate version directories per DB type: mariadb_versions, mysql_versions, postgresql_versions, sqlite_versions
# Migration scripts also in src/common/db/alembic/
```

## Key Files

- `src/common/settings.json`: Master list of all core settings with validation rules
- `src/common/db/model.py`: SQLAlchemy ORM models for all tables
- `src/common/db/Database.py`: High-level database wrapper
- `src/common/gen/Configurator.py`: Settings validation engine
- `src/common/gen/Templator.py`: NGINX config renderer
- `src/scheduler/main.py`: Scheduler entry point
- `src/scheduler/JobScheduler.py`: Job execution orchestrator
- `src/ui/main.py`: Web UI entry point
- `src/ui/app/dependencies.py`: UI dependency injection (DB, DATA, BW_CONFIG)
- `src/api/app/core.py`: API entry point (imports all routers)
- `src/bw/lua/bunkerweb.lua`: Main Lua runtime initialization
- `pyproject.toml`: Black config (160 char lines)
- `.pre-commit-config.yaml`: All linting/formatting rules

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

```bash
python3 tests/main.py docker              # Docker integration tests
python3 tests/main.py autoconf            # Autoconf tests
python3 tests/main.py swarm               # Swarm tests
python3 tests/main.py kubernetes           # Kubernetes tests
python3 tests/main.py linux debian         # Linux tests (with distro)
```

- Tests scan `examples/*/tests.json` for test scenarios (type: string/status, url, expected results)
- Real Docker environments with actual HTTP requests — tests verify observable behavior, not internals

## Key Conventions

- Python: snake_case (modules/functions), PascalCase (classes), Black formatting at 160 chars
- Lua: lowercase module names, descriptive function names, StyLua formatting
- Shell: POSIX-compatible unless `#!/bin/bash` shebang, pass ShellCheck
- Commit messages: Conventional Commits (`feat:`, `fix:`, `docs:`) or `<component> - ...` format
- UI translations in `src/ui/app/static/locales/`

## External Resources

- Documentation: <https://docs.bunkerweb.io>
- Official Plugins: <https://github.com/bunkerity/bunkerweb-plugins>
- Web UI Demo: <https://demo-ui.bunkerweb.io>
