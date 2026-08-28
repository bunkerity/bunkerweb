# AGENTS.md

Agent guide for the BunkerWeb Scheduler in `src/scheduler/`. This is the canonical guide for this directory; `CLAUDE.md` here is a pointer to it.

## Read First

- Root: [../../AGENTS.md](../../AGENTS.md) (short) and [../../CLAUDE.md](../../CLAUDE.md) (architecture)
- Worker guide: [../worker/AGENTS.md](../worker/AGENTS.md) — where jobs actually run
- Shared code: [../common/AGENTS.md](../common/AGENTS.md)

## What This Component Does

The Scheduler is the central orchestrator — the "brain":

1. Saves configuration to the database on startup.
2. Schedules plugin jobs on `once` / `minute` / `hour` / `day` / `week` cadences and **dispatches** them through the API to Celery workers — execution happens in `src/worker/`.
3. Generates NGINX configs through the Configurator/Templator pipeline.
4. Distributes configs, plugins, caches and custom configs to the instances via their API.
5. Monitors instance health and re-pushes to instances that come back.
6. Handles failover: backs up known-good configs and restores them when a reload fails.
7. Polls the database for changes and triggers reload cycles.

## Critical Rules

- Scheduler orchestrates and dispatches; workers execute. `JobScheduler` must never import or run a job module.
- Config generation flows through `gen/save_config.py` and `gen/main.py` — invoked as subprocesses with a restricted environment. Do not bypass validation or templating.
- Change detection is driven by DB metadata flags in `main.py`.
- Worker-driven reloads live in `src/worker/tasks.py`, not here.
- Runtime assumes the container filesystem layout under `/usr/share/bunkerweb/` and `/var/tmp/bunkerweb/`.

## Files

- `main.py` — entry point: main event loop, signal handlers, config-generation orchestration, healthchecks, failover backup/restore, change-detection polling.
- `JobScheduler.py` — thin `JobScheduler` class. Standalone (it does **not** inherit `ApiCaller`; an `api_client` is injected). Discovers jobs from `plugin.json`, validates them, drives the `schedule` library and dispatches.
- `api_client.py` — the injected client.
- `entrypoint.sh` — runs Alembic migrations, detects the integration mode, launches `main.py`.
- `Dockerfile` — multi-stage; certbot and `maxminddb` arrive transitively through the shared `gen`/`db` requirements, not from `requirements.in`.

## Architecture

### Main loop

```
Startup -> save_config -> wait for DB init -> restore caches -> check custom configs/plugins
        -> generate NGINX config -> send to instances -> reload -> dispatch once-jobs
        -> polling loop:
             sleep(1) -> run_pending (dispatch due jobs) -> check DB metadata
             -> on change: set NEED_RELOAD, regenerate, send, reload, failover if needed
```

### Global state in `main.py`

- `SCHEDULER` (`JobScheduler`): holds the injected API client, the base environment snapshot and the discovered job set — no DB connection, no instance list.
- `APPLYING_CHANGES` / `BACKING_UP_FAILOVER` (Events): prevent concurrent operations.
- `SCHEDULER_LOCK` (Lock): defined here, passed into `JobScheduler`; serializes `run_single` dispatch and guards the mutable state `main.py` still owns.
- `SCHEDULER_TASKS_EXECUTOR` (ThreadPoolExecutor): parallel config sends, plugin checks, healthchecks.
- Flags: `FIRST_START`, `CONFIG_NEED_GENERATION`, `RUN_JOBS_ONCE`, `NEED_RELOAD`, `PLUGINS_NEED_GENERATION`, …

### JobScheduler internals

- **Discovery**: globs `plugin.json` from core, external and pro plugins (`__get_jobs`), then validates `name`, `file`, `every`, `reload` and `async` against pre-compiled regexes and the allowed `every` set (`__validate_jobs`).
- **Dispatch**: builds a payload (`_build_dispatch_item`) and calls `api_client.dispatch_jobs(...)`. Execution is `src/worker/tasks.py::execute_job` + `src/worker/executor.py::JobExecutor.run`.
- **Schedule management**: `setup()` registers periodic jobs with the `schedule` library; the callback is `_dispatch_scheduled_job`. `run_pending()` dispatches due jobs, `run_once()` dispatches all `once` jobs, `run_single(name)` dispatches one under the injected lock.
- **Environment**: the `env` setter resets `os.environ` from the snapshot taken at `__init__` and overlays the given dict — global, across all threads.
- **`reload(env, changed_plugins=…, ignore_plugins=…)`**: resets the environment, re-discovers jobs, clears `schedule` state, dispatches once-jobs, re-schedules periodic ones.
- **Reload requests**: `request_reload(test=True)` calls `api_client.reload_instances(...)`. The reload a job triggers by calling `sys.exit(1)` is debounced inside the worker; the scheduler is not in that path.
- **Return codes and queue routing live in the worker.** For reference: `0` = success without reload, `1` = success plus debounced reload, anything else = failure; heavy jobs are routed by `HEAVY_JOBS`/`queue_for` in `src/common/utils/job_queues.py`, and Celery enforces `task_soft_time_limit`/`task_time_limit`.

### Signals

- `SIGTERM`/`SIGINT`: waits up to 30s for `APPLYING_CHANGES` to clear, then shuts down cleanly.
- `SIGHUP`: runs `save_config.py` to persist the current env vars to the database (used by the Linux integration).

### Healthchecks

- Every `HEALTHCHECK_INTERVAL` seconds (default 30), `GET /instances/{hostname}/health` forwards the instance's own state: `ok`, `loading`, `reloading`, `needs_config`. A failure there means unreachable — the instance answers 200 in every state.
- **`loading` and `needs_config` both earn a re-push and are not the same thing.** `loading` means there is no configuration, so the plugins listed below are inactive: a real exposure. `needs_config` is a restart that kept its configuration, is enforcing all of it, and merely wants a fresh one — set by the entrypoint as `/var/tmp/bunkerweb_needs_config`, cleared by `POST /confs`. Do not merge their log messages: telling an operator that access controls are inactive when they are enforcing sends them chasing a bypass that does not exist.
- `push-configs` is dispatched when an instance transitions `down`/`failover` → `up`, **or** when a reachable instance reports `loading` — the case a short container restart needs.
- **`IS_LOADING=yes` is a security state, not telemetry.** Nine core plugins gate `is_needed()` on it — `mtls`, `authbasic`, `blacklist`, `limit`, greylist, whitelist, dnsbl, bunkernet, robotstxt — so an instance holding it serves traffic with no client certificates, no basic auth, no blacklist and no rate limit while answering healthchecks as `up`; timer-driven work stops too. ModSecurity/CRS, antibot, country and the bans path do **not** read the flag and keep enforcing, so this is a partial bypass, not a disabled WAF.
- The loading re-push is retried but **bounded**: `LOADING_FAST_RETRIES` in a row, then one every `LOADING_SLOW_RETRY_EVERY`. Retrying matters because `run_single` can report success without queueing anything (a read-only database does exactly that); bounding it matters because the instance is marked `up` before this branch, making each attempt a full `push-configs` — render, upload, fleet-wide reload — and `api.lua`'s `/health` fails toward `loading`, so a datastore hiccup alone lands here. `LOADING_INSTANCES` maps hostname → consecutive loading healthchecks and drives both cadence and log level.
- Instance status in the DB is `up`, `down` or `failover`. There is no in-memory `SCHEDULER.apis` list any more.

### Failover

After a successful reload, config/custom_configs/cache are copied to `/var/tmp/bunkerweb/failover/` and cached to the DB. On reload failure the last known-good set is restored and reloaded. Failover state is recorded in DB metadata.

### Change detection

The inner loop reads `db.get_metadata()` every 1s (3s when read-only) and reacts to `pro_plugins_changed` / `external_plugins_changed` (regenerate plugins, re-run jobs, regenerate config), `custom_configs_changed` (regenerate custom config files), `plugins_config_changed` (regenerate NGINX config, re-run changed plugin jobs) and `instances_changed` (refresh instances, regenerate everything). Changes are timestamped to avoid reprocessing in read-only mode.

## Commands

```bash
docker compose -f misc/dev/docker-compose.ui.api.yml up -d
pre-commit run --all-files
./tests/scripts/test.sh docker core dev <category>   # see tests/AGENTS.md
```

That compose provisions the whole job path: `bw-scheduler`, `bw-api`, `bw-db`, `bw-jobs-broker` (Valkey, the Celery broker) and `bw-worker`. A compose file without the broker and worker **cannot run jobs at all**.

Unit tests for job validation and dispatch-payload building live in `tests/unit/scheduler/`.

## Runtime Gotchas

- `os.environ` is mutated globally by the `JobScheduler.env` setter — it affects every thread.
- Job execution errors surface in **worker** logs and in the DB job runs, not as scheduler stack traces. Scheduler-side failures are limited to discovery, validation and dispatch.
- The polling loop catches every `BaseException` with a 5-error threshold before calling `stop(1)`.
- **A once-batch has no execution order.** `run_once()` dispatches every `once` job at once and the workers run them in parallel, so a job that reads what another writes can no longer rely on plugin order. Two live consequences:
  - **A job must not read a database flag the scheduler clears around the dispatch.** `backup-data` skips itself when `scheduler_first_start` is set and `main.py` clears that flag right after dispatching — fire-and-forget, so the worker normally reads it already cleared, backs up a pristine database, stamps the plugin's "already done for this period" cache and suppresses the first real backup for a day. The job is kept out of the first batch (`skipped_plugins`); its own guard stays for the other dispatch paths.
  - **Certificate providers race `deploy-certificates`.** `self-signed`/`custom-cert`/`letsencrypt` decide the attachments, `deploy-certificates` materializes them; dispatched together the deploy usually wins and ships material the provider is about to detach. It self-corrects — the provider raises `certificates_changed`, the loop re-dispatches the deploy alone (`CERTIFICATES_NEED_DEPLOYMENT`) — so anything asserting on TLS right after a provider setting changes must wait for that flag to clear, not merely for the jobs to fall quiet.
- Local runs without the full container filesystem layout usually fail.

## Shared Code

Imported via `sys.path` manipulation, not pip: `common_utils`, `logger`, `jobs`, `ApiCaller` from `src/common/utils/`; `Database` from `src/common/db/`; `API` from `src/common/api/`; `Configurator` and `Templator` from `src/common/gen/` (as subprocesses).
