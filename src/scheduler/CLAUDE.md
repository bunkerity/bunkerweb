# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

See also the [root CLAUDE.md](../../CLAUDE.md) for project-wide architecture, build commands, and conventions.

## What This Component Does

The Scheduler is BunkerWeb's central orchestrator — the "brain" of the system. It:

1. Saves configuration to the database on startup
2. Schedules plugin jobs (download blocklists, renew certificates, etc.) and dispatches them to Celery workers via the API on `once` / `minute` / `hour` / `day` / `week` cadences — execution happens in `src/worker/`, not in the scheduler
3. Generates NGINX configs via the Configurator/Templator pipeline
4. Distributes configs, plugins, caches, and custom configs to BunkerWeb instances via their API
5. Monitors instance health and re-sends config to instances that come back online
6. Handles failover: backs up known-good configs and restores them when a reload fails
7. Polls the database for changes (plugins, configs, instances) and triggers reload cycles

## File Overview

| File                           | Purpose                                                                                                                                                                                                                                                                                                                                      |
| ------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `main.py` (~1050 lines)        | Entry point. Contains the main event loop, signal handlers, config generation orchestration, healthcheck logic, failover backup/restore, and change detection polling                                                                                                                                                                        |
| `JobScheduler.py` (~260 lines) | Thin `JobScheduler` class — standalone (does **not** inherit from `ApiCaller`; accepts an `api_client` by injection). Discovers jobs from `plugin.json` files, validates them, manages the `schedule` library, and **dispatches** jobs (and reload requests) to the API, which routes them to Celery workers. Does not execute jobs locally. |
| `entrypoint.sh`                | Docker entrypoint. Runs Alembic database migrations, detects integration mode, then launches `main.py`                                                                                                                                                                                                                                       |
| `Dockerfile`                   | Multi-stage build: installs Python deps (including certbot + `maxminddb`, pulled transitively via the shared `gen`/`db` requirements — not from `scheduler/requirements.in`), copies shared code, sets up data directories with correct permissions                                                                                          |
| `requirements.in`              | Direct deps — `schedule`, `cryptography`, `pydantic`, `python-magic`, `requests` (certbot, the DNS plugins, and `maxminddb` are **not** here — they live in `src/worker/requirements.in` since job execution moved to Celery; the scheduler image still pulls them transitively via `src/common/{gen,db}/requirements.txt` at build)         |

## Architecture Details

### Main Loop Flow

```
Startup → save_config → wait for DB init → restore caches → check custom configs/plugins
    → generate NGINX config → send to instances → reload → dispatch once-jobs to workers
    → enter polling loop:
        sleep(1) → run_pending (dispatch due scheduled jobs to workers) → check DB metadata for changes
        → if changes detected: set NEED_RELOAD, break inner loop
        → regenerate affected artifacts → send to instances → reload → failover if needed
```

### Key Global State in main.py

- `SCHEDULER` (JobScheduler): the singleton orchestrator — holds the injected API client, the base environment snapshot, and the discovered job set (no longer holds a DB connection or an API instance list itself)
- `APPLYING_CHANGES` / `BACKING_UP_FAILOVER` (Events): coordination flags preventing concurrent operations
- `SCHEDULER_LOCK` (Lock): defined in `main.py` and passed into `JobScheduler`; used to serialize single-job dispatch (`JobScheduler.run_single`) and guard scheduler-side mutable state that `main.py` still owns
- `SCHEDULER_TASKS_EXECUTOR` (ThreadPoolExecutor, 4 workers): runs config sending, plugin checks, and healthchecks in parallel
- Flags: `FIRST_START`, `CONFIG_NEED_GENERATION`, `RUN_JOBS_ONCE`, `NEED_RELOAD`, `PLUGINS_NEED_GENERATION`, etc.

### JobScheduler Internals

- **Job discovery**: globs `plugin.json` files from core plugins, external plugins, and pro plugins (`JobScheduler.__get_jobs`), then validates each job's `name`, `file`, `every`, `reload`, and `async` fields against pre-compiled regexes and the allowed `every` set (`__validate_jobs`).
- **Dispatch model**: `JobScheduler` does **not** import or execute job modules. It builds a dispatch payload (`_build_dispatch_item`) and sends it via `api_client.dispatch_jobs(...)`. Execution happens in Celery workers — see `src/worker/tasks.py:execute_job` and `src/worker/executor.py:JobExecutor.run`.
- **Schedule management**: `setup()` uses Python's `schedule` library to register periodic jobs; the scheduled callback is `_dispatch_scheduled_job` (dispatch, not execute). `run_pending()` triggers dispatch for due jobs; `run_once()` dispatches all `once` jobs (optionally filtered by plugin); `run_single(name)` dispatches one job by name under the injected lock.
- **Environment management**: the `env` setter resets `os.environ` from a snapshot taken at `__init__` and overlays the provided dict. Used by `reload()` when the scheduler detects config or plugin changes.
- **`reload(env, changed_plugins=..., ignore_plugins=...)`**: resets environment, re-discovers jobs (`update_jobs`), clears the `schedule` state, dispatches once-jobs, and re-schedules periodic jobs.
- **Reload requests**: `request_reload(test=True)` calls `api_client.reload_instances(...)`. Worker-driven reloads (triggered when a job exits with `sys.exit(1)`) happen inside `src/worker/tasks.py` and are debounced there — the scheduler is not in that path.
- **Return-code semantics live in the worker**, not here. For reference: `src/worker/tasks.py` treats `ret == 0` as success (no reload), `ret == 1` as success + debounced reload request, and anything else as failure. Celery enforces task time limits (`task_soft_time_limit=900s`, `task_time_limit=1800s`) — see `src/worker/app.py`.
- **Queue routing also lives in the worker**: jobs whose `name` is in `HEAVY_JOBS` (`src/worker/app.py` — e.g. `certbot-*`, `backup-data`, `download-*`, `bunkernet-*`, `coreruleset-nightly`) are routed to the `heavy` queue; everything else to `default`.

### Signal Handling

- `SIGTERM`/`SIGINT`: waits up to 30s for `APPLYING_CHANGES` to clear, then cleanly shuts down
- `SIGHUP`: triggers `save_config.py` to persist current env vars to the database (used by Linux integration)

### Healthcheck System

- Runs every `HEALTHCHECK_INTERVAL` seconds (default 30)
- Checks each instance via `GET /health`
- If an instance is "loading", sends full config (custom configs, plugins, pro plugins, NGINX confs, cache) and reloads it
- Updates instance status in DB (`up`, `down`, `failover`). The scheduler no longer maintains an in-memory `SCHEDULER.apis` list — it talks to instances via the injected API client

### Failover Mechanism

- After a successful reload, copies config/custom_configs/cache to `/var/tmp/bunkerweb/failover/` and caches it to DB
- On reload failure, restores from failover path and attempts reload with last-known-good config
- Failover state recorded in DB metadata

### Config Generation Pipeline

The scheduler doesn't generate configs directly — it shells out to:

- `gen/save_config.py`: validates and persists settings to DB
- `gen/main.py`: renders NGINX config files from Jinja2 templates

Both are invoked as subprocesses with a restricted environment (PATH, PYTHONPATH, LOG*LEVEL, DATABASE_URI, TZ, CUSTOM_CONF*\* vars only).

### Change Detection

The inner polling loop checks `db.get_metadata()` every 1s (3s if read-only) for these flags:

- `pro_plugins_changed` / `external_plugins_changed`: regenerate plugins, re-run jobs, regenerate config
- `custom_configs_changed`: regenerate custom configs files from DB
- `plugins_config_changed`: regenerate NGINX config, re-run changed plugin jobs
- `instances_changed`: refresh API list, regenerate everything

Changes are tracked with timestamps to avoid reprocessing in read-only mode.

## Development Notes

### Running Locally

The scheduler requires the full BunkerWeb filesystem layout (`/usr/share/bunkerweb/`, `/var/cache/bunkerweb/`, etc.) and running BunkerWeb instances. Use the Docker dev compose:

```bash
docker compose -f misc/dev/docker-compose.ui.api.yml up -d
```

This compose file provisions the full job-execution path: `bw-scheduler`, `bw-api`, `bw-db`, `bw-jobs-broker` (Valkey — the Celery broker), and `bw-worker` (Celery worker consuming `default` and `heavy` queues). Compose files in `misc/dev/` that do **not** include the broker and worker cannot run jobs that rely on the Celery path — see the root [CLAUDE.md](../../CLAUDE.md) for the full compose matrix.

### Dependencies on Shared Code

The scheduler imports from several shared packages via `sys.path` manipulation (not pip installs):

- `src/common/utils/` → `common_utils`, `logger`, `jobs`, `ApiCaller`
- `src/common/db/` → `Database`
- `src/common/api/` → `API`
- `src/common/gen/` → `Configurator`, `Templator` (invoked as subprocesses)

### Testing Considerations

- Unit tests for `JobScheduler` (job validation + dispatch-payload building) live in `tests/unit/scheduler/` (pytest); broader behavior is integration-tested via `tests/main.py`
- The scheduler is tightly coupled to the database and filesystem — changes should be tested with the full Docker stack
- Job modules are imported and executed in the worker (`src/worker/executor.py`); errors surface there and are recorded against the job run in the DB by `src/worker/tasks.py:execute_job`. Scheduler-side failures are limited to discovery, validation, and dispatch

### Common Pitfalls

- `os.environ` is mutated globally by `JobScheduler.env` setter — this affects all threads
- Dynamic job module loading (and any reload-on-replace behavior) now lives in `src/worker/executor.py`; the scheduler keeps no module cache and no job-execution thread pool
- The polling loop catches all `BaseException` with a 5-error threshold before calling `stop(1)`
