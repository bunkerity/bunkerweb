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
pip install -r src/worker/requirements.in
docker compose -f misc/dev/docker-compose.ui.api.yml up -d
docker compose -f misc/dev/docker-compose.ui.api.yml up -d --force-recreate bw-worker
pre-commit run --all-files
```

## Pitfalls

- Dev compose does not volume-mount Worker source; rebuild and recreate `bw-worker` for code changes.
- `task_acks_late=False` means a crash mid-job will not requeue the task.
- `worker_max_tasks_per_child=1` makes every job pay child init cost.
- No Celery result backend is configured; durable evidence must go through DB job runs or logs.
