# AGENTS.md

Primary instruction file for AI coding agents in this repository.

## Fast Start

- Read [CLAUDE.md](CLAUDE.md) for architecture and component boundaries.
- Read [BUILD.md](BUILD.md) for reproducible artifact builds.
- Read [README.md](README.md) and [docs/quickstart-guide.md](docs/quickstart-guide.md) for integration context.
- Open the guide of the directory you are about to touch (list at the bottom) — it holds the traps.
- Run `pre-commit run --all-files` before finishing code changes.

## Repository Map

- `src/bw/`: NGINX runtime + Lua request pipeline.
- `src/common/`: shared library — DB layer, config generation, core plugins, utilities.
- `src/scheduler/`: orchestrator loop, config application, job scheduling.
- `src/worker/`: Celery workers that execute plugin jobs (Scheduler dispatches here).
- `src/api/`: FastAPI control plane.
- `src/ui/`: Flask web UI.
- `src/autoconf/`: Docker/Swarm/Kubernetes event-driven config sync.
- `src/linux/` and `src/all-in-one/`: packaging and distribution targets.
- `src/deps/`: vendored third-party code — treat as external unless the task targets it.
- `examples/`: user-facing deployment recipes, also used as e2e fixtures. Their test descriptors live in `tests/examples/<name>.json`, not in the example folder.
- `tests/`: the YAML-spec integration framework (`tests/scripts/test.sh`) and the pytest unit suite (`tests/unit/`).
- `docs/`: user-facing documentation, partly generated from plugin metadata.

## Critical Architecture Facts

- Scheduler does not execute jobs in-process; it dispatches to Celery workers in `src/worker/` (Redis or Valkey broker required).
- UI does not reach the database; UI reads and writes flow through the API client layer.
- `src/api/app/routers/core.py` assembles routers; the FastAPI app is created in `src/api/app/main.py`.
- Config pipeline is settings -> Configurator -> Templator -> rendered NGINX files. Do not bypass validation.
- Multisite settings are server-name prefixed; repeated setting families use numeric suffixes.
- A job's exit code is a protocol, not a status: `1` means "something changed" and triggers cache delivery plus a debounced reload, `0` means success with no change, anything else is a failure.
- `reverseproxy`, `grpc` and `redirect` share one per-service location namespace, guarded in `src/common/db/db_methods/locations.py` with a render-time mirror in `src/common/utils/location_claims.py`. Both mirrors must agree.

## Build, Lint, Test

- Lint/format (all): `pre-commit run --all-files`
- Component deps: `pip install --require-hashes -r src/<component>/requirements.txt`
- Dev stack (recommended): `docker compose -f misc/dev/docker-compose.ui.api.yml up -d`
- Integration tests: `./tests/scripts/test.sh <integration> <type> <release> <category>`, e.g. `./tests/scripts/test.sh docker core dev headers`
- Unit tests: `.venv-unit/bin/pytest`
- Both suites, their setup and their traps: [tests/AGENTS.md](tests/AGENTS.md). `tests/main.py` is the **legacy** harness, not the entry point.

For packaging commands and distro-specific build details, use [BUILD.md](BUILD.md) instead of duplicating steps here.

## Working Conventions

- Prefer minimal, targeted changes; preserve existing APIs and behavior unless the task requires a change.
- Follow project styles configured in `pyproject.toml`, `.pre-commit-config.yaml`, `.luacheckrc`, and `stylua.toml`.
- Add or update docs when behavior, configuration keys, or operational flows change.
- Never hand-author or regenerate an Alembic migration without an explicit request — see [src/common/db/AGENTS.md](src/common/db/AGENTS.md).
- A setting added without touching its plugin `README.md` is invisible in the published docs — see [docs/AGENTS.md](docs/AGENTS.md).

## Practical Pitfalls

- Many components expect container filesystem paths under `/usr/share/bunkerweb/` and `/var/tmp/bunkerweb/`; local ad-hoc runs fail without that layout.
- Dynamic imports and plugin discovery rely on `plugin.json` metadata and naming conventions; validate metadata changes carefully.
- Scheduler/autoconf behavior depends on DB metadata flags; verify end-to-end reload signaling when changing config flows.
- Fresh installs build their schema from the model and always look healthy; only an upgrade from a previous version runs migrations. Test the upgrade path, not just a clean boot.
- Integration tests are environment-heavy and may require domain/env setup (`TEST_DOMAIN*`).

## Where To Go Next

- Contribution process: [CONTRIBUTING.md](CONTRIBUTING.md)
- Security policy: [SECURITY.md](SECURITY.md)
- Plugin reference (user-facing): [docs/plugins.md](docs/plugins.md)
- Component guides (each directory's `CLAUDE.md` is a pointer to its `AGENTS.md`):
  - [src/api/AGENTS.md](src/api/AGENTS.md)
  - [src/ui/AGENTS.md](src/ui/AGENTS.md)
  - [src/scheduler/AGENTS.md](src/scheduler/AGENTS.md)
  - [src/worker/AGENTS.md](src/worker/AGENTS.md)
  - [src/autoconf/AGENTS.md](src/autoconf/AGENTS.md)
  - [src/bw/AGENTS.md](src/bw/AGENTS.md)
  - [src/common/AGENTS.md](src/common/AGENTS.md)
    - [src/common/db/AGENTS.md](src/common/db/AGENTS.md)
    - [src/common/core/AGENTS.md](src/common/core/AGENTS.md)
  - [src/linux/AGENTS.md](src/linux/AGENTS.md)
  - [src/all-in-one/AGENTS.md](src/all-in-one/AGENTS.md)
  - [tests/AGENTS.md](tests/AGENTS.md)
  - [docs/AGENTS.md](docs/AGENTS.md)
  - [examples/mcp-stack/AGENTS.md](examples/mcp-stack/AGENTS.md)
