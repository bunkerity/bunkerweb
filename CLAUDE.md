# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

BunkerWeb is an open-source Web Application Firewall (WAF) built on NGINX with a modular plugin architecture. It provides "security by default" for web services through multiple integration modes (Docker, Kubernetes, Swarm, Linux) and is fully configurable via environment variables.

## Architecture

### Core Components

- **BunkerWeb Core** (`src/bw/`, `src/common/core/`): NGINX-based reverse proxy with security modules written in Lua and Python. Each security feature is a plugin with its own `plugin.json` configuration.
- **Scheduler** (`src/scheduler/`): Central orchestrator that manages configuration, executes jobs, generates NGINX configs, and acts as intermediary between components. This is the "brain" of BunkerWeb.
- **Autoconf** (`src/autoconf/`): Listens for Docker/Swarm/Kubernetes events and dynamically reconfigures BunkerWeb without container restarts.
- **API** (`src/api/`): FastAPI service for programmatic control of BunkerWeb instances.
- **Web UI** (`src/ui/`): Flask-based admin interface for managing instances, viewing blocked attacks, configuring settings, and monitoring jobs.
- **Database** (`src/common/db/`): Backend store (SQLite/MariaDB/MySQL/PostgreSQL) for configuration, metadata, cached files, and job execution state.

### Configuration Flow

1. Settings are defined as environment variables (e.g., `USE_ANTIBOT=captcha`, `AUTO_LETS_ENCRYPT=yes`)
2. Scheduler reads settings from environment or database
3. Configurator/Templator (`src/common/gen/`) generates NGINX configuration files from templates (`src/common/confs/`)
4. BunkerWeb instances reload with new configuration
5. In multisite mode, prefix settings with server name: `www.example.com_USE_ANTIBOT=captcha`
6. Multiple settings use numeric suffixes: `REVERSE_PROXY_URL_1=/api`, `REVERSE_PROXY_HOST_1=http://backend1`

### Plugin System

Each core module in `src/common/core/*/` is a plugin with:

- `plugin.json`: Metadata, settings schema, validation regex
- Python jobs for periodic tasks (e.g., downloading blocklists)
- Lua code for request-time processing
- NGINX configuration templates

External plugins follow the same structure and can be installed via the Web UI or CLI.

## Development Commands

### Setup

```bash
# Install Python dependencies for a component
pip install -r src/scheduler/requirements.txt
pip install -r src/ui/requirements.txt
pip install -r src/api/requirements.txt

# Install pre-commit hooks
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
flake8 .                         # Python linting
stylua .                         # Lua formatting
luacheck src/                    # Lua linting
shellcheck scripts/*.sh          # Shell script linting
prettier --write "**/*.{js,ts,css,html,json,yaml,md}"  # Frontend formatting
```

### Documentation

```bash
# Serve docs locally with live reload
mkdocs serve --watch

# Build static docs
mkdocs build
```

### Run Development Instance

```bash
# Iso-prod environment with all components
docker compose -f misc/dev/docker-compose.ui.api.yml up -d

# There are other compose files for different setups in misc/dev/
```

## Code Organization

### Directory Structure

```
src/
├── all-in-one/      # Single container with all components
├── api/             # FastAPI service
├── autoconf/        # Docker/Swarm/K8s event listener
├── bw/              # BunkerWeb core (NGINX + Lua runtime)
├── common/          # Shared code
│   ├── api/         # API client library
│   ├── cli/         # Command-line interface (bwcli)
│   ├── confs/       # NGINX configuration templates
│   ├── core/        # Core security plugins (each is a module)
│   ├── db/          # Database abstraction + Alembic migrations
│   ├── gen/         # Configuration generator (Configurator, Templator)
│   ├── helpers/     # Healthcheck scripts
│   └── utils/       # Shared utilities
├── deps/            # Third-party dependencies (NGINX modules, Lua libs)
├── linux/           # Linux package build scripts (deb/rpm)
├── scheduler/       # Job scheduler and orchestrator
└── ui/              # Web UI (Flask app)

docs/                # MkDocs documentation
examples/            # Integration examples with tests.json
tests/               # Integration test suites
misc/                # Utilities and scripts
```

### Key Files

- `src/common/settings.json`: Master list of all core settings with validation rules
- `src/scheduler/main.py`: Scheduler entry point, handles config generation and job execution
- `src/ui/main.py`: Web UI entry point
- `src/bw/lua/bunkerweb.lua`: Main Lua runtime initialization
- `pyproject.toml`: Project metadata (Black config: 160 char lines)
- `.pre-commit-config.yaml`: All linting/formatting rules

## Important Patterns

### Settings Context

- `global`: Applied to all servers (e.g., `WORKER_PROCESSES`, `LOG_LEVEL`)
- `multisite`: Can be server-specific (prefix with `SERVER_NAME_`)

### Security Modes

- `detect`: Log threats without blocking (for testing/debugging false positives)
- `block`: Actively block threats (default)

### Integration Modes

Set one of these to `yes`:

- `AUTOCONF_MODE`: Docker autoconf (labels on containers)
- `SWARM_MODE`: Docker Swarm (labels on services)
- `KUBERNETES_MODE`: Kubernetes (Ingress resources)

### Database Migrations

Use Alembic for schema changes:

```bash
# Located in src/common/db/alembic/
# Separate version directories for: mariadb, mysql, postgresql, sqlite
```

## Testing Philosophy

- Integration tests use real Docker environments with actual HTTP requests
- Each example has a `tests.json` defining test scenarios (HTTP status codes, response content, timing)
- Tests verify observable behavior, not internals
- For regressions, add a test case to the relevant example's `tests.json`

## Configuration Best Practices

- Never commit secrets (use `env/` templates for examples)
- Settings are validated against regex in `plugin.json`
- Custom NGINX configs go in designated directories or via Web UI
- ModSecurity custom rules follow the same pattern
- Multi-language UI translations in `src/ui/app/static/locales/`

## Key Conventions

- Python: snake_case (modules/functions), PascalCase (classes), Black formatting at 160 chars
- Lua: lowercase module names, descriptive function names, StyLua formatting
- Shell: POSIX-compatible unless `#!/bin/bash` shebang, pass ShellCheck
- Commit messages: Use Conventional Commits (`feat:`, `fix:`, `docs:`) or `<component> - ...` format

## External Resources

- Documentation: https://docs.bunkerweb.io
- Official Plugins: https://github.com/bunkerity/bunkerweb-plugins
- Web UI Demo: https://demo-ui.bunkerweb.io
- Discord: https://discord.com/invite/fTf46FmtyD
