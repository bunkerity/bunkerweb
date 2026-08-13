# AGENTS.md

Local agent guide for the BunkerWeb Celery job executor in `src/worker/`.

## Read First

- Root guide: [../../AGENTS.md](../../AGENTS.md)
- Long-form Worker notes: [CLAUDE.md](CLAUDE.md)
- Scheduler guide: [../scheduler/AGENTS.md](../scheduler/AGENTS.md)
- Common guide: [../common/AGENTS.md](../common/AGENTS.md)

## Critical Rules

- Worker executes plugin jobs dispatched by the Scheduler/API path; keep this separation intact.
- Redis or Valkey broker is required. Default broker URL is `redis://localhost:6379/0`.
- Keep `HEAVY_JOBS` routing aligned with the API dispatch copy in `src/api/app/routers/jobs.py`.
- Job loading must stay sandboxed under core, external, or pro plugin roots.
- Return code semantics matter: `0` success, `1` success plus debounced reload, anything else failure.
- Per-job environment handling must continue stripping sensitive env keys.

## Commands

```bash
docker build -f src/worker/Dockerfile -t bunkerweb-worker:dev .
pip install --require-hashes -r src/worker/requirements.txt
docker compose -f misc/dev/docker-compose.ui.api.yml up -d
docker compose -f misc/dev/docker-compose.ui.api.yml up -d --force-recreate bw-worker
pre-commit run --all-files
```

## Pitfalls

- Dev compose does not volume-mount Worker source; rebuild and recreate `bw-worker` for code changes.
- `task_acks_late=True` + `task_reject_on_worker_lost=True`: delivery is **at-least-once**, so a job killed mid-run is re-run from the start. `tasks.py` bounds redeliveries per dispatch (`WORKER_MAX_DELIVERY_ATTEMPTS`, default 3) because those flags switch off Celery's own loop protection.
- `worker_max_tasks_per_child=1` makes every job pay child init cost.
- No Celery result backend is configured; durable evidence must go through DB job runs or logs.
