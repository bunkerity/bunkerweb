import os
from contextlib import suppress
from datetime import datetime

from worker.app import app, get_worker_db
from worker.executor import JobExecutor

SENSITIVE_ENV_KEYS = {"CELERY_BROKER_URL", "JOBS_HMAC_SECRET"}

# Core jobs that take a distributed lease and therefore need a broker of their own.
#
# Stripping CELERY_BROKER_URL left push-configs' lease inert in exactly the topology that needs
# it. A split-container worker has no Redis on localhost, so the job's `redis://localhost:6379/0`
# fallback could not connect, the acquisition raised, and the except branch runs the push anyway
# ("proceeding without coordination") -- on every single dispatch. The lease therefore worked
# only in all-in-one, where a single worker means there is nothing to coordinate with.
#
# Re-injected by name so the strip still holds for every other job, including every third-party
# plugin job. These are core jobs shipped in this tree, and they already receive DATABASE_URI --
# a strictly more sensitive credential -- so the marginal exposure is nil.
LEASE_JOBS = frozenset(("push-configs",))

# Config keys returned by Database.get_config() that must NOT overwrite the
# worker's own runtime env when overlaying settings for a job. Mirrors
# scheduler/main.py:_strip_bootstrap_env so the loaded config can't clobber the
# worker's DATABASE_URI / PATH / PYTHONPATH.
_BOOTSTRAP_ENV_KEYS = ("DATABASE_URI", "DATABASE_URI_READONLY", "PYTHONPATH", "PATH")


def _get_apis():
    from API import API  # type: ignore
    from ApiCaller import ApiCaller  # type: ignore

    token = os.getenv("API_TOKEN") or None

    # Primary source: registered instances in the DB (filters out hosts marked
    # "down"). Falls back to BUNKERWEB_INSTANCES env for the standalone /
    # diagnostic mode documented in src/worker/CLAUDE.md.
    db = get_worker_db()
    if db is not None:
        try:
            db_instances = [inst for inst in db.get_instances() if inst.get("status") != "down"]
        except Exception:
            db_instances = []
        if db_instances:
            return ApiCaller([API.from_instance(inst, token=token) for inst in db_instances])

    env_hostnames = [hostname.strip() for hostname in os.getenv("BUNKERWEB_INSTANCES", "").split() if hostname.strip()]
    if not env_hostnames:
        return None
    return ApiCaller([API(f"http://{hostname}:5000", host=hostname, token=token) for hostname in env_hostnames])


def _load_job_config_env(db, logger) -> dict:
    """Return the resolved BunkerWeb config as a flat env dict for the job.

    Jobs read their settings via ``os.getenv(...)``. Since jobs now run in the
    worker process (not the scheduler), the worker must materialize the full
    config — global plus per-service multisite keys (e.g. ``www.example.com_USE_BLACKLIST``),
    including defaults — from the shared DB, exactly like the scheduler used to
    overlay into ``os.environ`` before running jobs in-process. Without this,
    every job sees compiled defaults instead of the user configuration.

    ``global_only=False`` is required so per-service multisite keys are emitted.
    Bootstrap keys are dropped so the config can't overwrite the worker's own
    ``DATABASE_URI`` / ``PATH`` / ``PYTHONPATH``.
    """
    if db is None:
        # Not cosmetic: without the DB the job runs against compiled defaults, so USE_BLACKLIST,
        # AUTO_LETS_ENCRYPT and every per-service setting silently do not apply. Say so, because
        # the job itself will look like it succeeded.
        logger.warning("Worker database is not initialized; running the job with default settings, NOT the stored configuration")
        return {}
    try:
        config = db.get_config(global_only=False, methods=False, with_drafts=False)
    except Exception as exc:
        logger.warning(f"Could not load config from database for job env: {exc}")
        return {}
    # Expand @resource-group tokens (e.g. WHITELIST_IP=@office) into flat values so jobs
    # reading settings via os.getenv() never see an unresolved token. The DB keeps the
    # @name; only the materialized job env is expanded.
    from resource_group_resolver import expand_config_groups  # type: ignore

    config = expand_config_groups(config, db, logger)
    for key in _BOOTSTRAP_ENV_KEYS:
        config.pop(key, None)
    return {key: "" if value is None else str(value) for key, value in config.items()}


def job_shadow_name(task, args, kwargs, options) -> str:
    if args and isinstance(args[0], dict):
        job_data = args[0]
        return f"job.{job_data.get('plugin_id', '?')}.{job_data.get('name', '?')}"
    return "job.unknown"


# How many times one dispatched job may be delivered before we give up on it. Celery's own
# loop protection (acknowledge a task whose child died by signal) is switched off in app.py so
# an OOM-killed job is actually retried, so this is the bound that replaces it: a job that
# reliably kills its worker would otherwise be requeued forever, taking the worker down with it
# on every lap and starving every other job in the lane.
MAX_DELIVERY_ATTEMPTS = int(os.getenv("WORKER_MAX_DELIVERY_ATTEMPTS", "3") or 3)


def _broker_client(broker_url: str):
    """Redis client for the broker, with timeouts. NEVER call `Redis.from_url` bare here.

    Both callers run on the job's critical path, and the conditions that make a worker die --
    a netsplit, a fenced node, a dropped security group -- are exactly the ones that black-hole
    the broker rather than refusing the connection. redis-py defaults to `socket_timeout=None`,
    so a bare client blocks forever: the job would hang until `task_time_limit` (1800s) fires,
    and a time-limit kill ACKs the message (`acks_on_failure_or_timeout` defaults True), losing
    the job silently -- reintroducing the exact bug at-least-once delivery exists to fix.
    """
    import redis

    return redis.Redis.from_url(broker_url, socket_timeout=2, socket_connect_timeout=2)


def _delivery_attempt(task_id: str, broker_url: str, logger) -> int:
    """Return which delivery of ``task_id`` this is, 1-based. 0 means "could not tell".

    The counter lives in the broker rather than in the process because the whole point is to
    survive the process dying. The key is the task id, which the API sets to the run id and
    Celery preserves across a redelivery, so a *rescheduled* run of the same job gets a fresh
    id and a fresh count -- this bounds retries of one dispatch, never the job itself.

    Fails OPEN: if the broker cannot be reached the job runs. A counter that cannot be read is
    a reason to lose visibility, not a reason to refuse work.
    """
    if not task_id:
        return 0
    try:
        client = _broker_client(broker_url)
        key = f"bw:job_attempt:{task_id}"
        attempt = int(client.incr(key))  # type: ignore[arg-type]  # sync client returns int, not an awaitable
        if attempt == 1:
            # Long enough to outlive any redelivery of this dispatch, short enough that the
            # keys do not accumulate. Every dispatch mints a new task id, so this only ever
            # garbage-collects.
            client.expire(key, 86400)
        return attempt
    except Exception as exc:
        logger.warning(f"Could not read the delivery counter, running the job unbounded: {exc}")
        return 0


def _request_reload_debounced(apis, broker_url: str, logger) -> None:
    client = _broker_client(broker_url)
    if not client.set("bw:reload_pending", "1", nx=True, ex=10):
        logger.info("Reload already pending, skipping duplicate request")
        return

    cache_sent = apis.send_files("/var/cache/bunkerweb", "/cache")
    if not cache_sent:
        raise RuntimeError("Failed to send /var/cache/bunkerweb to BunkerWeb instances")

    test = "no" if os.getenv("DISABLE_CONFIGURATION_TESTING", "no").lower() == "yes" else "yes"
    reload_sent = apis.send_to_apis("POST", f"/reload?test={test}")[0]
    if not reload_sent:
        raise RuntimeError("Failed to request BunkerWeb reload")


@app.task(
    bind=True,
    name="worker.execute_job",
    shadow_name=job_shadow_name,
    # Mirrors app.conf. The decorator wins over the app config, so leaving this at False would
    # have silently kept early-acking no matter what app.py says -- see the comment there for
    # why both halves are on.
    acks_late=True,
    track_started=True,
)
def execute_job(self, job_data: dict) -> dict:
    from logger import setup_logger  # type: ignore

    logger = setup_logger("WORKER")
    db = get_worker_db()

    name = job_data.get("name", "unknown")
    plugin = job_data.get("plugin_id", "unknown")
    run_id = job_data.get("run_id", "")
    broker_url = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
    start = datetime.now().astimezone()

    # Count this delivery before doing anything expensive. A job that OOM-kills its worker gets
    # requeued (reject_on_worker_lost), comes back here, and would loop forever otherwise; the
    # run is recorded as failed so the operator sees the job dying rather than silence.
    attempt = _delivery_attempt(self.request.id or run_id, broker_url, logger)
    if attempt > MAX_DELIVERY_ATTEMPTS:
        logger.error(
            f"[{run_id}] Job {plugin}/{name} has been delivered {attempt} times "
            f"(limit {MAX_DELIVERY_ATTEMPTS}) -- it keeps killing its worker. Giving up on this dispatch."
        )
        if db:
            with suppress(Exception):
                db.add_job_run(name, False, start, datetime.now().astimezone())
        return {
            "duration_seconds": 0.0,
            "name": name,
            "needs_reload": False,
            "plugin": plugin,
            "return_code": 2,
            "run_id": run_id,
            "success": False,
            "abandoned_after_attempts": attempt,
        }

    executor = JobExecutor(logger)
    apis = _get_apis()

    logger.info(f"[{run_id}] Starting job {plugin}/{name}" + (f" (delivery {attempt})" if attempt > 1 else ""))

    saved_env = os.environ.copy()
    safe_env = saved_env.copy()
    for key in SENSITIVE_ENV_KEYS:
        safe_env.pop(key, None)

    # The one documented exception to the strip above -- see LEASE_JOBS.
    if name in LEASE_JOBS and saved_env.get("CELERY_BROKER_URL"):
        safe_env["CELERY_BROKER_URL"] = saved_env["CELERY_BROKER_URL"]

    ret = 2
    success = False

    try:
        os.environ.clear()
        os.environ.update(safe_env)

        # Materialize the BunkerWeb settings from the shared DB so jobs that read
        # config via os.getenv() honor the user's configuration (USE_BLACKLIST,
        # AUTO_LETS_ENCRYPT, multisite per-service settings, ...) instead of
        # compiled defaults. The scheduler no longer runs jobs in-process, so it
        # can no longer provide this env — the worker must.
        os.environ.update(_load_job_config_env(db, logger))

        # Identity of THIS dispatch, stable across a redelivery (Celery keeps the task id). A
        # job that takes a distributed lease needs it: without an owner token it cannot tell a
        # lease held by another run from the one its own killed delivery left behind, and the
        # retry then skips itself. Set after the config overlay so a stored setting cannot
        # shadow it, and before the per-job env so an explicit override still wins.
        os.environ["BW_JOB_RUN_ID"] = self.request.id or run_id

        job_env = job_data.get("env")
        if isinstance(job_env, dict):
            os.environ.update(job_env)

        ret = executor.run(job_data)
        success = ret in (0, 1)
    except SystemExit as exc:
        ret = exc.code if isinstance(exc.code, int) else 1
        success = ret in (0, 1)
        if not success:
            logger.error(f"[{run_id}] Job {plugin}/{name} exited with code {ret}")
    except Exception as exc:
        logger.error(f"[{run_id}] Job {plugin}/{name} crashed: {exc}")
    finally:
        os.environ.clear()
        os.environ.update(saved_env)

    end = datetime.now().astimezone()
    duration = (end - start).total_seconds()

    if db:
        try:
            err = db.add_job_run(name, success, start, end)
            if err:
                logger.error(f"[{run_id}] Failed to record job run: {err}")
        except Exception as exc:
            logger.error(f"[{run_id}] Failed to record job run: {exc}")
    else:
        logger.warning(f"[{run_id}] Worker database is not initialized, skipping job run persistence")

    if ret == 1 and apis:
        try:
            logger.info(f"[{run_id}] Job {plugin}/{name} requested reload")
            _request_reload_debounced(apis, broker_url, logger)
        except Exception as exc:
            logger.error(f"[{run_id}] Cache/reload failed: {exc}")

    logger.info(f"[{run_id}] Job {plugin}/{name} completed with code {ret} in {duration:.1f}s")

    return {
        "duration_seconds": duration,
        "name": name,
        "needs_reload": ret == 1,
        "plugin": plugin,
        "return_code": ret,
        "run_id": run_id,
        "success": success,
    }
