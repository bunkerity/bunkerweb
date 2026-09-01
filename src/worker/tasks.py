import json
import os
from contextlib import suppress
from datetime import datetime
from typing import Optional
from uuid import uuid4

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


def _api_token(db, logger=None) -> Optional[str]:
    """The token the instances expect, from the worker env or, failing that, the stored config.

    API_TOKEN is a BunkerWeb setting, so a split deployment normally sets it on the instances and
    the API, not on the worker container. Reading only `os.environ` therefore built every caller
    tokenless and the instances answered 444 "missing API token" -- silently, because the caller
    logs that failure inside the worker child, whose output does not reach the container log.
    Jobs never hit this: `_load_job_config_env` overlays the stored config before they run, which
    is exactly why push-configs pushed fine while every other job's cache was refused.
    """
    token = os.getenv("API_TOKEN") or None
    if token or db is None:
        return token
    try:
        return db.get_config(global_only=True, methods=False, with_drafts=False).get("API_TOKEN") or None
    except Exception as exc:
        if logger is not None:
            logger.warning(f"Could not read API_TOKEN from the database: {exc}")
        return None


def _get_apis(logger=None):
    from API import API  # type: ignore
    from ApiCaller import ApiCaller  # type: ignore

    # Primary source: registered instances in the DB (filters out hosts marked
    # "down"). Falls back to BUNKERWEB_INSTANCES env for the standalone /
    # diagnostic mode documented in src/worker/CLAUDE.md.
    db = get_worker_db()
    token = _api_token(db, logger)
    if db is not None:
        try:
            db_instances = [inst for inst in db.get_instances(with_credential=True) if inst.get("status") != "down"]
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


# Acknowledgements a job deferred until its material actually reached the instances. A job that
# writes files and exits 1 cannot clear its own change flag honestly: the push and the reload happen
# here, afterwards, so clearing inside the job records a delivery that may still fail, and nothing
# re-dispatches it. Each entry is a JSON `{"keys": [...], "snapshot": {...}}` claimed alongside
# RELOAD_DIRTY_KEY and applied only once the push and the reload have both succeeded.
#
# Imported rather than duplicated: if the two sides ever named different keys nothing would error --
# the job would write one key, the worker drain another, and the change flag would stay pinned while
# the set grew. /usr/share/bunkerweb/utils is on PYTHONPATH in all three worker targets.
from job_queues import queue_for  # type: ignore # noqa: E402
from jobs import (  # type: ignore # noqa: E402
    JOB_REQUEUE_COUNT_ENV,
    MAX_JOB_REQUEUES,
    RELOAD_ACK_PENDING_KEY as ACK_PENDING_KEY,
    drain_pending_acks,
    drain_requeue_request,
)

RELOAD_LOCK_KEY = "bw:reload_pending"
RELOAD_DIRTY_KEY = "bw:reload_dirty"
# Keep aligned with common/core/jobs/jobs/push-configs.py.
RELOAD_TIMEOUT = (5, 30)
# Long enough to cover a push plus a reload with configuration testing on a slow instance. The
# holder deletes the key when it is done, so this only matters when a worker dies mid-reload.
RELOAD_LOCK_TTL = 60
# A job that finishes while the holder is pushing gets picked up by the next round. Bounded so a
# steady stream of jobs cannot pin one worker child in here forever -- whatever is left dirty is
# carried by the next job's reload.
MAX_RELOAD_ROUNDS = 5
# Releasing the lock and checking the dirty flag has to be one step. Do it in two and a job that
# raises the flag in between finds the holder already gone and the lock already free, having
# failed its own acquisition a moment earlier -- its files then wait for whatever reloads next.
RELEASE_IF_CLEAN = """
if redis.call('exists', KEYS[2]) == 1 then return 0 end
redis.call('del', KEYS[1])
return 1
"""


def _publish_deferred_acks(broker_url: str, logger) -> None:
    """Queue what the job that just ran deferred, from the side that holds the broker credentials.

    The job cannot do this itself -- CELERY_BROKER_URL is stripped from its environment -- so it
    leaves the payload in the jobs module and this ships it. Queue it before requesting the reload:
    the holder claims the set at the top of each round, so publishing afterwards would miss the very
    push this job asked for and leave the change waiting for the next one.

    A publish that fails drops the entry and leaves the change flag raised, which the scheduler
    already handles by re-dispatching the job.
    """
    pending = drain_pending_acks()
    if not pending:
        return

    try:
        _broker_client(broker_url).sadd(ACK_PENDING_KEY, *pending)
    except BaseException as exc:
        logger.error(f"Could not queue the deferred acknowledgements, leaving those changes pending: {exc}")


def _requeue_if_asked(job_data: dict, logger) -> None:
    """Dispatch this job again later, because it told us its precondition is not met yet.

    A NEW task id, not a Celery retry. `_delivery_attempt` counts deliveries per task id to bound
    a job that keeps killing its worker, and `retry()` preserves the id -- a deferral chain would
    then be abandoned with "it keeps killing its worker", which is a diagnosis it never earned.
    Minting an id is also what the counter's own contract already says a rescheduled run does.

    The countdown is served by the broker, so nothing is held in this process and no prefork child
    is occupied while it waits.
    """
    request = drain_requeue_request()
    if not request:
        return

    count = int(job_data.get("requeue_count") or 0) + 1
    name = job_data.get("name", "unknown")
    if count > MAX_JOB_REQUEUES:
        # The job is told its budget (JOB_REQUEUE_COUNT_ENV) and is expected to stop asking, so
        # reaching this means a job -- possibly third-party -- ignored it. Refuse loudly rather
        # than re-dispatch forever.
        logger.error(f"Job {name} asked to be deferred more than {MAX_JOB_REQUEUES} times; refusing to re-dispatch it again")
        return

    payload = dict(job_data)
    payload["requeue_count"] = count
    payload["run_id"] = str(uuid4())
    try:
        execute_job.apply_async(args=[payload], task_id=payload["run_id"], queue=queue_for(name), countdown=request["delay"])
    except BaseException as exc:
        # Nothing is lost that was not already lost: the job did no work, and the scheduler
        # re-dispatches `once` jobs on the next change or restart.
        logger.error(f"Could not re-dispatch {name} after it deferred: {exc}")
        return

    logger.warning(
        f"Job {name} deferred ({request['reason']}); re-dispatched as {payload['run_id']} in {request['delay']}s (deferral {count}/{MAX_JOB_REQUEUES})"
    )


def _apply_deferred_acks(client, claimed, logger) -> None:
    """Clear the change flags whose material the push that just succeeded carried.

    An entry that cannot be applied stays in the set: the flag it belongs to remains raised, the
    scheduler re-dispatches the job, and the next successful reload tries again. Dropping it here
    would reproduce the bug this exists to close.
    """
    if not claimed:
        return

    db = get_worker_db()
    if db is None:
        logger.error("No database handle in the worker; leaving the delivered changes to acknowledge later")
        return

    for raw in claimed:
        try:
            entry = json.loads(raw)
            snapshot = dict(entry.get("snapshot") or {})
            # get_metadata() hands back datetimes; JSON gave them back as strings.
            for key, value in tuple(snapshot.items()):
                if key.startswith("last_") and isinstance(value, str):
                    snapshot[key] = datetime.fromisoformat(value)

            error = db.clear_applied_changes(snapshot, tuple(entry.get("keys") or ()))
            if error:
                logger.error(f"Could not acknowledge delivered changes {entry.get('keys')}: {error}")
                continue
        except BaseException as e:
            logger.error(f"Could not apply a deferred acknowledgement: {e}")
            continue

        client.srem(ACK_PENDING_KEY, raw)
        logger.info(f"Acknowledged {entry.get('keys')} now that the push reached the instances")


def _request_reload_debounced(apis, broker_url: str, logger) -> None:
    """Push the cache tree to every instance and reload them, one reload at a time.

    `send_files` ships the whole /var/cache/bunkerweb tree, so one push carries every job's
    output -- but only the output that existed when the tar was built. The debounce therefore
    guards the reload alone: a job that loses the lock flags the run dirty, and the holder goes
    round again, so the last writer's files always leave with a push. Skipping the push for the
    losers instead (which is what this did) silently dropped the output of every job that landed
    inside the window -- a downloaded blocklist or a fresh certificate that never reached the
    instances, with the job recorded as a success.
    """
    client = _broker_client(broker_url)
    test = "no" if os.getenv("DISABLE_CONFIGURATION_TESTING", "no").lower() == "yes" else "yes"

    # Announce the files BEFORE bidding for the lock. The holder cannot release while this flag
    # stands, so whoever ends up holding it either claims the flag and pushes after we set it, or
    # cannot release and goes round again. Flagging after a failed acquisition instead leaves the
    # window where the holder checked, found nothing, and released.
    client.set(RELOAD_DIRTY_KEY, "1", ex=RELOAD_LOCK_TTL)

    if not client.set(RELOAD_LOCK_KEY, "1", nx=True, ex=RELOAD_LOCK_TTL):
        logger.info("Reload already running, flagged the run as dirty for the holder to pick up")
        return

    released = False
    try:
        for _ in range(MAX_RELOAD_ROUNDS):
            # Claim every flag raised so far: those jobs wrote their files before flagging, so
            # this push carries them. Anything raised from here on earns another round.
            client.delete(RELOAD_DIRTY_KEY)
            claimed_acks = client.smembers(ACK_PENDING_KEY)

            if not apis.send_files("/var/cache/bunkerweb", "/cache"):
                raise RuntimeError("Failed to send /var/cache/bunkerweb to BunkerWeb instances")

            if not apis.send_to_apis("POST", f"/reload?test={test}", timeout=RELOAD_TIMEOUT)[0]:
                raise RuntimeError("Failed to request BunkerWeb reload")

            # The material is on the instances and they have reloaded: now, and only now, is a
            # change that shipped with it genuinely applied.
            _apply_deferred_acks(client, claimed_acks, logger)

            released = bool(client.eval(RELEASE_IF_CLEAN, 2, RELOAD_LOCK_KEY, RELOAD_DIRTY_KEY))
            if released:
                return
            logger.info("Another job finished during the reload, pushing and reloading again")
            client.expire(RELOAD_LOCK_KEY, RELOAD_LOCK_TTL)

        logger.warning(f"Still dirty after {MAX_RELOAD_ROUNDS} reload rounds, leaving it to the next job")
    finally:
        # The bound was hit, or the push raised. Either way the flag stays up, and the next job to
        # finish takes the lock and carries whatever is still waiting.
        if not released:
            client.delete(RELOAD_LOCK_KEY)


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
    broker_url = os.getenv("CELERY_BROKER_URL", "redis://127.0.0.1:6379/0")
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
                db.add_job_run(
                    name,
                    False,
                    start,
                    datetime.now().astimezone(),
                    error=f"Abandoned after {attempt} deliveries (limit {MAX_DELIVERY_ATTEMPTS}) -- the job keeps killing its worker",
                )
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
    apis = _get_apis(logger)

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
    # Why this run failed, in the operator's words rather than an exit code. Only this frame sees
    # all three sources (a non-zero SystemExit, an exception, the executor's own refusals), so it
    # is where the message is assembled for Jobs_runs.error.
    error: Optional[str] = None

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
        # Which deferral of this dispatch the job is on, so a job that gates itself on a
        # precondition can tell "not ready yet" from "not ready after N tries" and stop waiting.
        os.environ[JOB_REQUEUE_COUNT_ENV] = str(int(job_data.get("requeue_count") or 0))

        job_env = job_data.get("env")
        if isinstance(job_env, dict):
            os.environ.update(job_env)

        ret = executor.run(job_data)
        success = ret in (0, 1)
    except SystemExit as exc:
        ret = exc.code if isinstance(exc.code, int) else 1
        success = ret in (0, 1)
        if not success:
            error = f"Job exited with code {ret}"
            logger.error(f"[{run_id}] Job {plugin}/{name} exited with code {ret}")
    except Exception as exc:
        error = f"Job crashed: {exc}"
        logger.error(f"[{run_id}] Job {plugin}/{name} crashed: {exc}")
    finally:
        os.environ.clear()
        os.environ.update(saved_env)
        # After the restore: the job ran without CELERY_BROKER_URL in its environment, and this
        # needs it back.
        _publish_deferred_acks(broker_url, logger)
        # Same reason as above -- re-dispatching needs the broker URL the job did not have. Drained
        # unconditionally so a request cannot leak into whatever runs next in this worker child.
        _requeue_if_asked(job_data, logger)

    end = datetime.now().astimezone()
    duration = (end - start).total_seconds()

    # The executor returns a bare 2 for a job it could not even load or import; the reason it
    # logged is the only description of that failure there is.
    if not success and error is None:
        error = executor.last_error

    if db:
        try:
            err = db.add_job_run(name, success, start, end, error=error)
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
