# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

See also the [root CLAUDE.md](../../CLAUDE.md) for project-wide architecture, build commands, and conventions.

## What This Is

The Worker is BunkerWeb's Celery-based distributed job executor. It replaces the in-process job execution that previously lived inside `JobScheduler`: the Scheduler now only **dispatches** jobs via the API, while every plugin job (blocklist downloads, certbot, backups, anti-bot data refreshes, etc.) actually runs in a worker process consuming Celery queues backed by a Redis/Valkey broker.

The worker runs independently of the Scheduler, shares the BunkerWeb database for state, and broadcasts cache + reload requests to the BunkerWeb instances listed in `BUNKERWEB_INSTANCES` whenever a job asks for a reload.

## File Overview

| File                                   | Purpose                                                                                                                                                                                                                                                                                                      |
| -------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `app.py`                               | Celery app construction. Defines the broker URL, queues (`default`, `heavy`), task time limits, prefork tuning, `HEAVY_JOBS` routing set, `route_job` callable wired into `task_routes`, and the `worker_process_init` / `worker_process_shutdown` hooks that create/close a per-process `Database` instance |
| `tasks.py`                             | The single Celery task `worker.execute_job`. Snapshots `os.environ`, strips `SENSITIVE_ENV_KEYS`, overlays `job_data["env"]`, runs the job via `JobExecutor`, persists every run via `db.add_job_run`, and triggers a debounced cache+reload broadcast when the job returns `1`                              |
| `executor.py`                          | `JobExecutor` class. Sandboxed dynamic loader: resolves the job file, refuses anything outside `ALLOWED_ROOTS`, imports it under a hashed module name, restores `sys.path` afterwards                                                                                                                        |
| `entrypoint.sh`                        | Docker entrypoint. Writes the `INTEGRATION` file, waits up to 30×2s for the database to be reachable, then `exec`s `celery -A worker.app worker` with the prefork pool and `default,heavy` queues                                                                                                            |
| `Dockerfile`                           | Multi-stage alpine build. Final image runs as UID/GID `102` (`worker:worker`); workdir is `/usr/share/bunkerweb/worker`                                                                                                                                                                                      |
| `healthcheck-worker.sh`                | Container healthcheck: `celery inspect ping --destination worker@<hostname>` and greps for `pong`                                                                                                                                                                                                            |
| `requirements.in` / `requirements.txt` | Direct deps: `celery==5.6.3`, `redis[hiredis]==7.4.0` (Kombu is pulled in transitively by Celery)                                                                                                                                                                                                            |
| `__init__.py`                          | Package marker — makes `worker.app` / `worker.tasks` importable                                                                                                                                                                                                                                              |

## Architecture

### Queues and Routing

Two queues are declared in `app.py`:

- `default` — fast jobs (most plugin maintenance tasks)
- `heavy` — long-running or resource-intensive jobs

`route_job` inspects `job_data["name"]` and returns `{"queue": "heavy"}` when the name is in the `HEAVY_JOBS` set, otherwise `{"queue": "default"}`. The current `HEAVY_JOBS` set in `app.py` contains:

```
backup-data, bunkernet-data, bunkernet-register,
certbot-auth, certbot-cleanup, certbot-deploy, certbot-new, certbot-renew,
coreruleset-nightly,
download-crs-plugins, download-plugins, download-pro-plugins,
push-configs
```

This set is duplicated in `src/api/app/routers/jobs.py` (the dispatch side passes an explicit `queue=` to `send_task`, so the API copy is what actually routes); keep the two in sync.

The routing is wired in via `app.conf.task_routes = {"worker.execute_job": route_job}`. The `default` queue is also the Celery `task_default_queue`. Both queues are consumed by the same worker process pool via `-Q default,heavy` in `entrypoint.sh` (override with `WORKER_QUEUES`).

### Celery Configuration Knobs

All set in `app.py`:

| Setting                                            | Value                 | Notes                                                               |
| -------------------------------------------------- | --------------------- | ------------------------------------------------------------------- |
| `task_time_limit`                                  | `1800` (30 min, hard) | Worker is killed if exceeded                                        |
| `task_soft_time_limit`                             | `900` (15 min, soft)  | Raises `SoftTimeLimitExceeded`                                      |
| `worker_max_tasks_per_child`                       | `1`                   | Recycle the prefork child after every job                           |
| `worker_max_memory_per_child`                      | `300000` KB (~300 MB) | Recycle if RSS exceeds this                                         |
| `worker_prefetch_multiplier`                       | `1`                   | Pull one task at a time per worker child                            |
| `task_acks_late`                                   | `False`               | Ack happens _before_ execution — see Pitfalls                       |
| `task_reject_on_worker_lost`                       | `False`               | Worker loss does not requeue                                        |
| `task_track_started`                               | `True`                | `STARTED` state visible to monitoring                               |
| `broker_pool_limit`                                | `4`                   | Connection pool size                                                |
| `broker_transport_options.visibility_timeout`      | `7200`                | Long enough to outlive the hard 1800s task limit                    |
| `broker_transport_options.max_connections`         | `8`                   | Cap on broker connections per worker                                |
| `broker_connection_retry_on_startup`               | `True`                | Retry broker connect on cold start                                  |
| `worker_hijack_root_logger`                        | `False`               | Preserve BunkerWeb logger configuration                             |
| `worker_send_task_events` + `task_send_sent_event` | `True`                | Stream task events (consumable by external monitors)                |
| `result_backend`                                   | `None`                | No result store — task return values are not retrievable via Celery |
| `worker_soft_shutdown_timeout`                     | `900.0`               | Graceful shutdown grace period                                      |

### Return-Code Semantics

`execute_job` maps the value returned by `JobExecutor.run` (or a `SystemExit` code) as follows:

- `0` — success, **no reload**
- `1` — success, **request a debounced reload** of all BunkerWeb instances
- anything else (including unhandled exceptions) — failure

Important contract detail: `JobExecutor.run` itself only ever returns `0` (success) or `2` (failure — path outside `ALLOWED_ROOTS`, file missing, or any exception during module load/execution). It never returns `1`. The `ret == 1` code path is reachable **only** when the job script raises `SystemExit(1)` — i.e. calls `sys.exit(1)`. That is the convention every job in `src/common/core/*/jobs/` follows: `sys.exit(0)` for "success, no reload" and `sys.exit(1)` for "success, please reload". A plain `return 1` from the job module does nothing — `JobExecutor.run` discards module return values and reports `0`.

Every run is persisted via `db.add_job_run(name, success, start, end)`. The Celery task return dict (`{return_code, success, needs_reload, plugin, name, run_id, duration_seconds}`) is informational — `result_backend=None` means callers cannot read it back from Celery.

When `ret == 1`, `_request_reload_debounced` is called. It uses `redis.Redis.from_url(broker_url).set("bw:reload_pending", "1", nx=True, ex=10)` — a 10-second Redis SETNX lock. If another worker already holds it, the call logs `"Reload already pending, skipping duplicate request"` and returns. Otherwise it `send_files("/var/cache/bunkerweb", "/cache")` to every instance and `POST /reload?test=<yes|no>`. The `test` value is `"no"` only when `DISABLE_CONFIGURATION_TESTING=yes`, otherwise `"yes"`.

### Environment Isolation

`execute_job` does the following around the job invocation:

1. Snapshot `os.environ` (`saved_env`)
2. Copy it into `safe_env` and pop `SENSITIVE_ENV_KEYS = {"CELERY_BROKER_URL", "JOBS_HMAC_SECRET"}`
3. Clear `os.environ`, repopulate from `safe_env`, then overlay `job_data["env"]` (if a dict)
4. Run the job
5. In `finally`, restore `saved_env`

This keeps broker credentials and the HMAC secret out of any subprocess the job might spawn, and prevents per-job env leakage across runs (although `worker_max_tasks_per_child=1` would discard the process anyway).

### Database Lifecycle

`worker_process_init` runs once per prefork child:

- Sets `DATABASE_POOL_SIZE` and `DATABASE_POOL_MAX_OVERFLOW` to `5` if unset
- If `DATABASE_URI` is set, imports `Database` + `setup_logger` from the shared code and assigns the instance to module-global `_worker_db`
- Otherwise leaves `_worker_db = None` (jobs run, persistence is skipped with a warning)

`worker_process_shutdown` closes `_worker_db`. `tasks.execute_job` fetches it via `get_worker_db()`.

### Sandboxed Module Loading (`executor.py`)

`JobExecutor.run` only loads modules whose resolved path lives under one of:

```
/usr/share/bunkerweb/core
/etc/bunkerweb/plugins
/etc/bunkerweb/pro/plugins
```

`_is_allowed_job_path` uses `Path.relative_to` against each `ALLOWED_ROOTS` entry. Anything outside, missing, or unloadable returns `2` (failure). The module is loaded under `bw_job_<name>_<md5[:8]>` to avoid name collisions when two plugins share a job filename. Both the job folder and its parent are prepended to `sys.path` for the duration of execution, then removed in `finally`.

### Reload Broadcast Target

`_get_apis` reads `BUNKERWEB_INSTANCES` and splits on whitespace. Each non-empty token becomes:

```python
API(f"http://{hostname}:5000", host=hostname)
```

If the env var is empty, `_get_apis` returns `None` and the reload step is silently skipped — by design, so a worker can run standalone for diagnostics.

## Build and Run

```bash
# From the repo root (build context must be the repo root)
docker build -f src/worker/Dockerfile -t bunkerweb-worker:dev .

# Install Python deps locally for IDE support
pip install -r src/worker/requirements.in
```

The only dev compose that wires the worker is `misc/dev/docker-compose.ui.api.yml`. It brings up `bw-worker` (this image) alongside `bw-jobs-broker` (a Valkey instance acting as the Celery broker). The other compose files in `misc/dev/` do not yet include the worker + broker, so jobs that rely on the Celery path will not run under those stacks.

```bash
docker compose -f misc/dev/docker-compose.ui.api.yml up -d
```

**Dev iteration:** Unlike UI/API, the dev compose does **not** volume-mount the worker source — rebuild and recreate to pick up code changes:

```bash
docker build -f src/worker/Dockerfile -t bunkerweb-worker:dev .
docker compose -f misc/dev/docker-compose.ui.api.yml up -d --force-recreate bw-worker
```

In the all-in-one image the worker is launched by supervisord (`src/all-in-one/supervisor.d/worker.ini`) and gated by `SERVICE_WORKER=yes`.

## Environment Variables

| Variable                                           | Default                    | Purpose                                                                                   |
| -------------------------------------------------- | -------------------------- | ----------------------------------------------------------------------------------------- |
| `CELERY_BROKER_URL`                                | `redis://localhost:6379/0` | Redis/Valkey broker URL — also used for the reload debounce lock                          |
| `BUNKERWEB_INSTANCES`                              | (empty)                    | Space-separated hostnames; each becomes `http://<host>:5000`. Empty → no reload broadcast |
| `JOBS_HMAC_SECRET`                                 | (empty)                    | Sensitive — stripped from the per-job env before execution                                |
| `WORKER_CONCURRENCY`                               | `2`                        | `celery worker --concurrency`                                                             |
| `WORKER_MAX_MEMORY_KB`                             | `300000`                   | `--max-memory-per-child` (KB)                                                             |
| `WORKER_QUEUES`                                    | `default,heavy`            | `-Q` argument                                                                             |
| `WORKER_HOSTNAME`                                  | `worker@%h`                | `--hostname` argument                                                                     |
| `DATABASE_URI`                                     | (empty)                    | Required to enable per-process DB; without it job-run persistence is skipped              |
| `DATABASE_POOL_SIZE`                               | `5`                        | Set by `init_worker_db` if unset                                                          |
| `DATABASE_POOL_MAX_OVERFLOW`                       | `5`                        | Set by `init_worker_db` if unset                                                          |
| `DISABLE_CONFIGURATION_TESTING`                    | `no`                       | If `yes`, reload broadcast uses `?test=no`; otherwise `?test=yes`                         |
| `LOG_LEVEL`                                        | `info`                     | Passed to `celery worker --loglevel`                                                      |
| `LOG_SYSLOG_TAG`                                   | `bw-worker`                | Exported by `entrypoint.sh`                                                               |
| `SWARM_MODE` / `KUBERNETES_MODE` / `AUTOCONF_MODE` | `no`                       | Selects the value written to `/usr/share/bunkerweb/INTEGRATION`                           |

## Common Pitfalls

- **`task_acks_late=False`** means the broker acks the task _before_ execution starts. A worker crash mid-job leaves nothing to requeue. Do not flip this without first auditing every job for idempotency — many jobs (certbot, blocklist downloads, backups) are not safe to re-run blindly.
- **`worker_max_tasks_per_child=1`** recycles the prefork child after every job. This makes leaks safe but means each job pays the cold-start cost of `worker_process_init` (DB pool init, logger setup). Do not raise this for "performance" without first measuring actual leak rates.
- **Job names are globally unique across plugins** (see `src/common/CLAUDE.md`). `HEAVY_JOBS` filtering is by name only — an external plugin job that reuses a heavy job's name will inherit the `heavy` queue routing.
- **Reload debounce is 10 seconds** (`ex=10` literal in `_request_reload_debounced`). If multiple workers finish reload-flagged jobs inside the same window, only the first wins; the others log `"Reload already pending, skipping duplicate request"` and return. Tune by editing that literal in `tasks.py`.
- **`BUNKERWEB_INSTANCES=""` silently disables the reload path.** That is intentional (standalone diagnostic mode) but easy to misread as a bug — if jobs return `1` and "nothing happens", check the env var first.
- **Dynamic job module loading now lives in the worker process.** The Scheduler no longer caches or hot-reloads job modules. Edits to job code under `src/common/core/*/jobs/` require restarting `bw-worker`, not `bw-scheduler`.
- **No result backend.** `result_backend=None` means the dict returned by `execute_job` is discarded by Celery. Anything you need to inspect after the fact must go through the DB (`db.add_job_run`) or the worker log.
- **Healthcheck pings by `worker@<HOSTNAME>`.** If you override `WORKER_HOSTNAME` to something that does not match `worker@$(hostname)`, the healthcheck will report unhealthy even though the worker is fine.
