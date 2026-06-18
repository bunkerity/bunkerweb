# AGENTS.md

Local agent guide for the BunkerWeb all-in-one Docker image in `src/all-in-one/`.

## Read First

- Root guide: [../../AGENTS.md](../../AGENTS.md)
- Long-form AIO notes: [CLAUDE.md](CLAUDE.md)
- Build reference: [../../BUILD.md](../../BUILD.md)

## Critical Rules

- AIO packages BunkerWeb, Scheduler, Worker, UI, API, Autoconf, Redis, CrowdSec, and log streaming under supervisord.
- Service toggles are applied by `entrypoint.sh` before supervisord starts.
- `SERVICE_WORKER` defaults to enabled only when `SERVICE_SCHEDULER=yes`; keep Scheduler/Worker/API coupling intact.
- Persistent data is rooted in `/data` and exposed through symlinks to standard runtime paths.
- CrowdSec, Redis, and logstream behavior is AIO-specific; avoid leaking assumptions into standalone components.
- Dependency version bumps are made in `deps/*.json` and consumed by the Dockerfile via `jq`.

## Commands

```bash
docker build -f src/all-in-one/Dockerfile -t bunkerweb:dev .
docker build -f src/all-in-one/Dockerfile --build-arg SKIP_MINIFY=yes -t bunkerweb:dev .
docker compose -f misc/dev/docker-compose.all-in-one.yml up -d
pre-commit run --all-files
```

## Pitfalls

- Build context must be the repo root.
- `procps` is required for process handoff and healthcheck helpers.
- AIO worker hostname is hardcoded in `supervisor.d/worker.ini`.
- `MULTISITE` defaults to `yes` in AIO, unlike standalone BunkerWeb.
