# AGENTS.md

This is the primary instruction file for AI coding agents in this repository.

## Fast Start

- Read [CLAUDE.md](CLAUDE.md) for architecture and component boundaries.
- Read [BUILD.md](BUILD.md) for reproducible artifact builds.
- Read [README.md](README.md) and [docs/quickstart-guide.md](docs/quickstart-guide.md) for integration context.
- Run `pre-commit run --all-files` before finishing code changes.

## Repository Map

- `src/bw/`: NGINX runtime + Lua request pipeline.
- `src/common/`: shared generators, DB models, plugin metadata, utility modules.
- `src/scheduler/`: orchestrator loop and config application logic.
- `src/worker/`: Celery workers that execute plugin jobs (Scheduler dispatches here).
- `src/api/`: FastAPI control plane.
- `src/ui/`: Flask web UI.
- `src/autoconf/`: Docker/Swarm/Kubernetes event-driven config sync.
- `src/linux/` and `src/all-in-one/`: packaging and distribution targets.
- `examples/`: integration scenarios and end-to-end test fixtures.
- `tests/`: integration test harness (`tests/main.py`).

## Critical Architecture Facts

- Scheduler does not execute all jobs in-process anymore; it dispatches execution to Celery workers in `src/worker/` (Redis or Valkey broker required).
- UI should not bypass the API for data access; UI reads/writes flow through API client layers.
- `src/api/app/routers/core.py` is router assembly, not the FastAPI app entry point (`src/api/app/main.py`).
- Config pipeline is settings -> Configurator -> Templator -> rendered NGINX files; avoid bypassing validation.
- Multisite settings are server-name prefixed; repeated setting families use numeric suffixes.

## Build, Lint, Test

- Lint/format (all): `pre-commit run --all-files`
- API deps: `pip install -r src/api/requirements.txt`
- UI deps: `pip install -r src/ui/requirements.txt`
- Scheduler deps: `pip install -r src/scheduler/requirements.txt`
- Worker deps: `pip install -r src/worker/requirements.txt`
- Dev stack (recommended): `docker compose -f misc/dev/docker-compose.ui.api.yml up -d`
- Integration tests: `python3 tests/main.py docker` (or `autoconf`, `swarm`, `kubernetes`, `linux`)

For packaging commands and distro-specific build details, use [BUILD.md](BUILD.md) instead of duplicating steps here.

## Working Conventions

- Prefer minimal, targeted changes; preserve existing APIs and behavior unless task requires a change.
- Follow project styles configured in `pyproject.toml`, `.pre-commit-config.yaml`, `.luacheckrc`, and `stylua.toml`.
- Add or update docs when behavior, configuration keys, or operational flows change.
- Treat generated/vendor content under `src/deps/` as external unless the task explicitly targets it.

## Practical Pitfalls

- Many components expect container filesystem paths under `/usr/share/bunkerweb/` and `/var/tmp/bunkerweb/`; local ad-hoc runs can fail without that layout.
- Dynamic imports and plugin discovery rely on metadata (`plugin.json`) and naming conventions; validate metadata changes carefully.
- Scheduler/autoconf behavior depends on DB metadata flags; verify end-to-end reload signaling when changing config flows.
- Integration tests are environment-heavy and may require domain/env setup (`TEST_DOMAIN*`).

## Where To Go Next

- Contribution process: [CONTRIBUTING.md](CONTRIBUTING.md)
- Security policy: [SECURITY.md](SECURITY.md)
- Plugin reference: [docs/plugins.md](docs/plugins.md)
- Architecture details by component:
  - [src/api/CLAUDE.md](src/api/CLAUDE.md)
  - [src/ui/CLAUDE.md](src/ui/CLAUDE.md)
  - [src/scheduler/CLAUDE.md](src/scheduler/CLAUDE.md)
  - [src/autoconf/CLAUDE.md](src/autoconf/CLAUDE.md)
  - [src/bw/CLAUDE.md](src/bw/CLAUDE.md)
  - [src/worker/CLAUDE.md](src/worker/CLAUDE.md)
  - [src/common/CLAUDE.md](src/common/CLAUDE.md)
  - [src/linux/CLAUDE.md](src/linux/CLAUDE.md)
  - [src/all-in-one/CLAUDE.md](src/all-in-one/CLAUDE.md)
  - [examples/mcp-stack/CLAUDE.md](examples/mcp-stack/CLAUDE.md)
