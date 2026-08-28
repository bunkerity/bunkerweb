# AGENTS.md

Agent guide for the BunkerWeb Celery job executor in `src/worker/`. This is the canonical guide for this directory; `CLAUDE.md` here is a pointer to it.

## Read First

- Root: [../../AGENTS.md](../../AGENTS.md) (short) and [../../CLAUDE.md](../../CLAUDE.md) (architecture)
- Scheduler guide: [../scheduler/AGENTS.md](../scheduler/AGENTS.md) — the dispatch side
- Shared code: [../common/AGENTS.md](../common/AGENTS.md)

## What This Is

The Worker executes plugin jobs. It replaces the in-process execution that used to live in `JobScheduler`: the Scheduler dispatches through the API, and every plugin job (blocklist downloads, certbot, backups, anti-bot refreshes) runs in a worker process consuming Celery queues on a Redis/Valkey broker. It runs independently of the Scheduler, shares the database for state, and broadcasts cache + reload requests to the instances when a job asks for a reload.

## Critical Rules

- The Worker executes; the Scheduler/API dispatches. Keep that separation.
- A Redis or Valkey broker is required. `CELERY_BROKER_URL` defaults to `redis://127.0.0.1:6379/0` — a literal IPv4 on purpose, because `localhost` is ambiguous on dual-stack hosts.
- Queue routing has **one** source of truth: `HEAVY_JOBS` and `queue_for()` in `src/common/utils/job_queues.py`, imported by both `app.py` and `src/api/app/routers/jobs.py`. Do not reintroduce a local copy.
- Job loading stays sandboxed under the core, external and pro plugin roots.
- Return codes are a protocol: `0` success, `1` success plus debounced reload, anything else failure.
- The per-job environment must keep stripping the sensitive keys.

## Files

- `app.py` — Celery app: broker URL, the `default`/`heavy` queues, time limits, prefork tuning, `task_routes` wired to the shared `queue_for`, and the `worker_process_init` / `worker_process_shutdown` lifecycle hooks.
- `tasks.py` — the single task `worker.execute_job`: snapshots `os.environ`, strips `SENSITIVE_ENV_KEYS`, overlays `job_data["env"]`, runs the job through `JobExecutor`, persists every run via `db.add_job_run`, and triggers the debounced cache+reload broadcast when the job returns `1`.
- `executor.py` — `JobExecutor`: sandboxed dynamic loader. Resolves the job file, refuses anything outside `ALLOWED_ROOTS`, imports it under a hashed module name, restores `sys.path` afterwards.
- `entrypoint.sh` — writes the `INTEGRATION` file, waits for the database, then `exec`s `celery -A worker.app worker` with the prefork pool on `default,heavy`.
- `Dockerfile` — multi-stage **Debian-slim**, not Alpine: the certbot-dns-multi Go/CGO bridge cannot load on musl. Runs as UID/GID `101`, the same ids as the scheduler, API and UI images, so a SQLite stack can share one `/data` volume.
- `healthcheck-worker.sh` — `celery inspect ping --destination worker@<hostname>`, grepped for `pong`.

## Architecture

### Queues

Two queues: `default` for fast maintenance jobs, `heavy` for long or resource-intensive ones (certbot, backups, plugin/blocklist downloads, `push-configs`). `route_job` asks the shared `queue_for(job_data["name"])`. Both are consumed by the same pool via `-Q default,heavy` (override with `WORKER_QUEUES`).

### Celery knobs that carry a reason

Everything is set in `app.py`; these are the ones you must not change casually:

| Setting                                       | Value   | Why                                                                                 |
| --------------------------------------------- | ------- | ----------------------------------------------------------------------------------- |
| `task_acks_late`                              | `True`  | Ack after execution, so a killed job is redelivered instead of lost                 |
| `task_reject_on_worker_lost`                  | `True`  | A signal-killed prefork child requeues instead of being acked                       |
| `broker_transport_options.visibility_timeout` | `7200`  | Must cover a full task **plus** its reserved queue wait, not just `task_time_limit` |
| `worker_max_tasks_per_child`                  | `1`     | Recycles the child after every job — leaks are safe, cold start is paid every time  |
| `result_backend`                              | `None`  | Task return values are not retrievable; durable evidence goes to the DB or the log  |
| `worker_hijack_root_logger`                   | `False` | Preserves the BunkerWeb logger configuration                                        |
| `worker_redirect_stdouts`                     | `False` | Load-bearing — see Runtime Gotchas                                                  |

Hard and soft time limits are `task_time_limit` / `task_soft_time_limit`; concurrency, memory ceiling and prefetch are tuned alongside them.

### Return codes

`execute_job` maps what `JobExecutor.run` returns (or a `SystemExit` code):

- `0` — success, no reload
- `1` — success, request a debounced reload of every instance
- anything else, including unhandled exceptions — failure

**`JobExecutor.run` itself only ever returns `0` or `2`** (path outside `ALLOWED_ROOTS`, missing file, or any exception during load/execution). The `1` path is reachable **only** when the job script raises `SystemExit(1)` — i.e. calls `sys.exit(1)`. That is the convention every job in `src/common/core/*/jobs/` follows. A plain `return 1` from the job module does nothing: module return values are discarded and reported as `0`.

Every run is persisted with `db.add_job_run(name, success, start, end)`.

### Reload broadcast

On `ret == 1`, `_request_reload_debounced` takes a Redis SETNX lock (`bw:reload_pending`, TTL `RELOAD_LOCK_TTL`), then `send_files("/var/cache/bunkerweb", "/cache")` to every instance and `POST /reload?test=<yes|no>` (`no` only when `DISABLE_CONFIGURATION_TESTING=yes`). A job that loses the lock sets `bw:reload_dirty` and returns; the holder re-reads that flag after each reload and goes round again, up to `MAX_RELOAD_ROUNDS`, then deletes the lock. **The push is inside the loop** because `send_files` tars the tree as it stands — a job that wrote its cache after the holder's tar needs another push, not just another reload.

`_get_apis` resolves targets in two tiers: the database first (`db.get_instances()`, dropping hosts marked `down`), then `BUNKERWEB_INSTANCES` as a fallback. If both are empty it returns `None` and the reload is silently skipped — deliberate, so a worker can run standalone for diagnostics.

### Environment isolation

Around each job: snapshot `os.environ`, copy it, pop `SENSITIVE_ENV_KEYS` (`CELERY_BROKER_URL`, `JOBS_HMAC_SECRET`), clear and repopulate `os.environ`, overlay `job_data["env"]`, run, and restore the snapshot in `finally`. This keeps broker credentials and the HMAC secret out of any subprocess a job spawns. `LEASE_JOBS` re-injects the broker URL for the named jobs that genuinely need it.

### Database lifecycle

`worker_process_init` runs once per prefork child: defaults the DB pool settings, and if `DATABASE_URI` is set imports the shared `Database` and assigns the module-global `_worker_db`. Without it, jobs still run and persistence is skipped with a warning. `worker_process_shutdown` closes it; `tasks.execute_job` fetches it through `get_worker_db()`.

### Sandboxed loading

`JobExecutor.run` only loads modules resolving under `ALLOWED_ROOTS` (`/usr/share/bunkerweb/core`, `/etc/bunkerweb/plugins`, `/etc/bunkerweb/pro/plugins`), checked with `Path.relative_to`. Anything outside, missing or unloadable returns `2`. The module is loaded as `bw_job_<name>_<md5[:8]>` so two plugins can share a job filename; the job folder and its parent are prepended to `sys.path` for the duration and removed in `finally`.

## Build and Run

```bash
docker build -f src/worker/Dockerfile -t bunkerweb-worker:dev .   # context must be the repo root
pip install --require-hashes -r src/worker/requirements.txt        # local IDE support

docker compose -f misc/dev/docker-compose.ui.api.yml up -d
docker compose -f misc/dev/docker-compose.ui.api.yml up -d --force-recreate bw-worker
```

The dev compose does **not** volume-mount the worker source — rebuild and recreate to pick up code changes. A compose stack without `bw-jobs-broker` and `bw-worker` cannot run jobs at all. In the all-in-one image supervisord launches the worker, gated by `SERVICE_WORKER=yes`.

certbot and certbot-dns-multi are direct dependencies here because the worker runs the Let's Encrypt jobs; that is also why the image is Debian-slim.

## Runtime Gotchas

- **Delivery is at-least-once, so every job may be re-run from the start.** `task_acks_late` + `task_reject_on_worker_lost` mean a job whose worker dies mid-run is redelivered rather than lost. The two flags cover different halves: `acks_late` alone catches the whole container dying; only `reject_on_worker_lost` catches a single prefork child killed by a signal, which Celery otherwise acks deliberately to stop a segfaulting task looping forever.
  - Because that removes Celery's loop protection, `tasks.py` supplies its own: `_delivery_attempt()` counts deliveries per task id in the broker and, past `WORKER_MAX_DELIVERY_ATTEMPTS` (default 3), drops the job and records a **failed** run. It fails **open** — an unreachable broker runs the job rather than blocking it. **Do not enable one flag without the other, and do not remove the counter.**
  - Never build a Redis client here without timeouts. `redis-py` defaults to `socket_timeout=None`, and a black-holed broker would hang a job until `task_time_limit`, whose kill **acks** the message — re-creating the silent loss this exists to prevent. Use `_broker_client()`.
  - **Recovery latency differs by failure mode.** A killed _child_ requeues immediately; a killed _container_ is only redelivered when the visibility timeout expires, measured from **delivery**, not from the crash. Restarting the worker does not accelerate it.
- **Not every job is safe to re-run.** The jobs were audited against "killed at an arbitrary instruction, then re-run from the start"; most are safe by construction (atomic writes via `Job._write_atomic`, DB upserts, expiry checks that short-circuit a second run). Known-unsafe remainder: `certbot-new` persists the issued certificate only at the very end and a re-run re-extracts the pre-issuance blob, so certbot re-orders the same SAN set and spends a Let's Encrypt duplicate slot; `certbot-renew`, `bunkernet-send`, `bunkernet-register` and `anonymous-report` can duplicate an external effect rather than corrupt state. **Read this before adding a job**: the safe ones are safe because they write atomically and commit their marker **last**, not by accident.
- **The debounce guards the reload, never the cache push.** It used to `return` before `send_files`, so every job finishing within the window had its output dropped — at boot a dozen jobs land inside a few seconds, and a freshly downloaded blocklist or certificate never reached the instances while the run was recorded a success. The loser now sets `bw:reload_dirty` and the holder pushes and reloads again. **Do not "simplify" the loser back into an early return**, and do not move the push out of the loop.
- **The deferred-acknowledgement set is broker-global; `/var/cache/bunkerweb` is per-container.** A job that writes material and exits `1` leaves its acknowledgement in `bw:reload_pending_acks` (via `jobs.defer_change_acknowledgement`, published by `_publish_deferred_acks` — the job cannot reach the broker itself). The reload holder claims that set and clears the flags after **its own** push. With one worker that is exact; with replicas, worker B can acknowledge material that only exists on worker A's disk — the flag goes down, the instances never got the files, and nothing re-dispatches. Give the workers a shared cache volume, or make the ack carry the writing worker's identity, before scaling past one.
- **Change flags are cleared by the run that pushed, not by the dispatch.** `acknowledge_changes` is a compare-and-set against each change's watermark, so a push that is abandoned or delayed leaves the flags set and gets re-dispatched.
- **`push-configs` holds a lease keyed by its own dispatch id** (the worker exports the Celery task id as `BW_JOB_RUN_ID`), so a redelivery reclaims the lease its own kill orphaned instead of reading it as "another run is in flight", exiting 0 and being recorded a **success** while instances keep serving the old config.
- **`BUNKERWEB_INSTANCES=""` silently disables the reload path.** Intentional (standalone diagnostics), easy to misread as a bug: if jobs return `1` and nothing happens, check that first.
- **Job code edits require restarting `bw-worker`, not `bw-scheduler`.** Dynamic job module loading lives here now; the Scheduler caches nothing.
- **`worker_redirect_stdouts=False` is load-bearing, not cosmetic.** Celery's default hands every child a `LoggingProxy` for `sys.stdout`/`sys.stderr` that drops writes coming from a logging handler. `logger.py` binds its `StreamHandler` to `sys.stderr`, so with the redirect on, **every line a job or `tasks.py` logs inside the child is discarded** — the container log keeps Celery's own task lines and subprocess output, which reads like a healthy worker while job failures are invisible. Pinned by `tests/unit/worker/test_delivery_guarantees.py`.
- **Job names are globally unique across plugins**, and heavy-queue routing is by name only — an external plugin reusing a heavy job's name inherits the `heavy` queue.
- **The healthcheck pings `worker@<HOSTNAME>`.** Overriding `WORKER_HOSTNAME` to something that does not match `worker@$(hostname)` reports unhealthy on a perfectly good worker.

## Environment

| Variable                                            | Default                    | Purpose                                                                                                    |
| --------------------------------------------------- | -------------------------- | ---------------------------------------------------------------------------------------------------------- |
| `CELERY_BROKER_URL`                                 | `redis://127.0.0.1:6379/0` | Broker URL, and the reload debounce lock. Sensitive: stripped from the per-job env except for `LEASE_JOBS` |
| `BUNKERWEB_INSTANCES`                               | (empty)                    | Space-separated hostnames, each becoming `http://<host>:5000`. Empty → no reload broadcast                 |
| `JOBS_HMAC_SECRET`                                  | (empty)                    | Sensitive — stripped from the per-job env                                                                  |
| `WORKER_CONCURRENCY`                                | `2`                        | `celery worker --concurrency`                                                                              |
| `WORKER_MAX_MEMORY_KB`                              | `300000`                   | `--max-memory-per-child` (KB)                                                                              |
| `WORKER_QUEUES`                                     | `default,heavy`            | `-Q` argument                                                                                              |
| `WORKER_HOSTNAME`                                   | `worker@%h`                | `--hostname` argument                                                                                      |
| `WORKER_MAX_DELIVERY_ATTEMPTS`                      | `3`                        | Redelivery ceiling before the job is dropped and recorded failed                                           |
| `DATABASE_URI`                                      | (empty)                    | Without it, job-run persistence is skipped                                                                 |
| `DATABASE_POOL_SIZE` / `DATABASE_POOL_MAX_OVERFLOW` | `5`                        | Defaulted at child init if unset                                                                           |
| `DISABLE_CONFIGURATION_TESTING`                     | `no`                       | `yes` makes the reload broadcast use `?test=no`                                                            |
| `LOG_LEVEL`                                         | `info`                     | Passed to `celery worker --loglevel`                                                                       |
| `LOG_SYSLOG_TAG`                                    | `bw-worker`                | Exported by `entrypoint.sh`                                                                                |
| `SWARM_MODE` / `KUBERNETES_MODE` / `AUTOCONF_MODE`  | `no`                       | Selects the value written to `/usr/share/bunkerweb/INTEGRATION`                                            |
