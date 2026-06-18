# AGENTS.md

Local agent guide for the BunkerWeb Scheduler in `src/scheduler/`.

## Read First

- Root guide: [../../AGENTS.md](../../AGENTS.md)
- Long-form Scheduler notes: [CLAUDE.md](CLAUDE.md)
- Worker guide: [../worker/AGENTS.md](../worker/AGENTS.md)
- Common guide: [../common/AGENTS.md](../common/AGENTS.md)

## Critical Rules

- Scheduler orchestrates and dispatches jobs; Celery workers execute plugin jobs.
- `JobScheduler` must not import or execute job modules locally.
- Config generation flows through `gen/save_config.py` and `gen/main.py`; do not bypass validation or templating.
- Change detection is driven by DB metadata flags and reload orchestration in `main.py`.
- Worker-driven reloads are handled in `src/worker/tasks.py`, not Scheduler code.
- Shared filesystem paths under `/usr/share/bunkerweb/` and `/var/tmp/bunkerweb/` are runtime assumptions.

## Commands

```bash
docker compose -f misc/dev/docker-compose.ui.api.yml up -d
pre-commit run --all-files
python3 tests/main.py docker
```

## Pitfalls

- Compose files without `bw-jobs-broker` and `bw-worker` cannot exercise the Celery job path.
- `JobScheduler.env` mutates `os.environ` globally.
- Job execution errors surface in Worker logs and DB job runs, not as Scheduler-side stack traces.
- Local runs usually fail without the full container filesystem layout.
