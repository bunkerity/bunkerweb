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
    JOB_DEFERRAL_PREFIX,
    JOB_REQUEUE_COUNT_ENV,
    MAX_JOB_REQUEUES,
    RELOAD_ACK_PENDING_KEY as ACK_PENDING_KEY,
    drain_deferral_reason,
    drain_pending_acks,
    drain_requeue_request,
)

RELOAD_LOCK_KEY = "bw:reload_pending"
RELOAD_DIRTY_KEY = "bw:reload_dirty"
# A push that is owed but was not delivered: no instance was reachable when a job asked for one, or
# the push itself failed. Distinct from RELOAD_DIRTY_KEY, which only says "more files landed while
# this reload was running" and is therefore only ever read by the holder of the reload lock -- with
# nobody holding it, a dirty flag just expires and the material is dropped. This one carries across
# jobs and across worker children (a child dies after every task), so it lives in the broker with no
# expiry and is cleared only once a push and a reload have both succeeded -- and then only if it is
# still the same debt. The value is a token minted by whoever raised it, never a bare flag: the
# settle is SETTLE_OWED_IF_UNCHANGED below, so a debt another job raised while this push was
# building its tar survives a push that cannot have carried it.
#
# Broker-global while /var/cache/bunkerweb is per-container, exactly like the pending-ack set: with
# more than one worker replica and no shared cache volume, the replica that settles the debt pushes
# its OWN tree and clears the marker anyway. See "Known limit" in src/worker/AGENTS.md -- the same
# shared-cache requirement covers both.
RELOAD_OWED_KEY = "bw:reload_owed"
# How many carry attempts that debt has already cost, so a push that keeps failing cannot reload the
# whole fleet on every job forever. `apis` stays truthy while a push fails -- a failed send_files
# marks nobody down -- and `send_files` gzip-tars the WHOLE cache tree per attempt, so retrying at
# full rate against one stuck instance (send_to_apis is all-or-nothing) pins the storm on the entire
# fleet. Same shape, same numbers and same "this needs an operator" escalation as the scheduler's
# LOADING_FAST_RETRIES / *_SLOW_RETRY_EVERY pair (scheduler/main.py:569-583, :639-646). The debt is
# kept in the broker until a push settles it -- dropping it would be the silent loss this whole
# change exists to close -- only retried slowly.
#
# One narrowing to know about: `_mark_reload_owed` resets this counter, so the slow window is only
# guaranteed while the fleet stays reachable. A deployment that flaps -- some jobs finding no
# instance at all, others finding one whose push then fails -- resets the count on every no-instance
# job and can stay in the fast window indefinitely, never reaching the "this needs an operator"
# escalation. That trade is deliberate: the common case by far is a cold boot, where inheriting a
# stale count would delay the FIRST delivery by ~14 job runs.
RELOAD_OWED_ATTEMPTS_KEY = "bw:reload_owed_attempts"
RELOAD_OWED_FAST_RETRIES = 3
RELOAD_OWED_SLOW_RETRY_EVERY = 20
# Keep aligned with common/core/jobs/jobs/push-configs.py.
RELOAD_TIMEOUT = (5, 30)
# Long enough to cover a push plus a reload with configuration testing on a slow instance. The
# holder deletes the key when it is done, so this only matters when a worker dies mid-reload.
# DEV-2b3 (port of dev 462c1e851): the push read budget is no longer flat -- `folder_push_timeout`
# grants up to 120 s on a large fleet, so 60 s could expire while the holder was still uploading.
# A second child would then take the lock and push concurrently, which is exactly the contention
# this lock exists to prevent. 300 covers connect + 120 s push + connect + 30 s reload with room to
# spare. It does NOT cover the worst case once dev `7a6bf2c70`/`32a2985ab` (rows 20/22) land and the
# 503 retry becomes reachable (3 attempts x 125 s); closing that wants the holder to renew the key
# each round rather than a larger constant -- see report-DEV-2b3.md, PO question 4.
RELOAD_LOCK_TTL = 300
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
# Settling the debt is a compare-and-delete for the same reason releasing the lock is a
# compare-and-set. A job that found no instance while this push was building its tar wrote a debt
# this tar cannot possibly carry; a blind `del` erases it, RELEASE_IF_CLEAN then sees a clean run,
# and that job's material is dropped in silence -- the exact defect the marker exists to close, in a
# narrower window.
SETTLE_OWED_IF_UNCHANGED = """
if redis.call('get', KEYS[1]) ~= ARGV[1] then return 0 end
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


def _mark_reload_owed(broker_url: str, logger) -> None:
    """Remember that the cache tree still has to be pushed, for the next run that can push it.

    The value is a fresh token, not a flag, so that whoever settles the debt can tell it apart from
    one raised afterwards (SETTLE_OWED_IF_UNCHANGED). Overwriting an existing token is deliberate:
    the debt stands either way, and a token an in-flight push has already claimed must stop matching
    -- that push cannot have carried what this job just wrote.

    The attempt budget goes with it. It counts consecutive failures to *settle* a debt, and this
    branch never attempted one, so a fresh debt must not inherit an older one's backoff and start
    life in the slow window (~14 job runs of delay on a cold boot).
    """
    try:
        client = _broker_client(broker_url)
        client.set(RELOAD_OWED_KEY, uuid4().hex)
        client.delete(RELOAD_OWED_ATTEMPTS_KEY)
    except BaseException as exc:
        # The warning above already told the operator; losing the marker only costs the recovery,
        # and the job's own change flags (if it raised any) are still pending for the scheduler.
        logger.error(f"Could not record that a cache push is still owed: {exc}")


def _reload_is_owed(broker_url: str, logger) -> bool:
    """Whether an earlier run's push never landed, so this run should carry it.

    Counts the consultation before answering, so a debt that keeps failing to settle backs off
    instead of reloading the fleet on every job: the first RELOAD_OWED_FAST_RETRIES carries cover the
    ordinary cases (an instance that came up a moment ago, a transient refusal), and after that one
    carry every RELOAD_OWED_SLOW_RETRY_EVERY consultations keeps a genuinely broken push -- a bad
    custom config, one wedged instance in an otherwise healthy fleet -- from re-tarring and
    re-shipping the whole cache tree twice a minute forever.

    What it counts is *consultations*, not settlement attempts: a carry that then loses the reload
    lock returns from `_request_reload_debounced` without pushing anything and has still spent a unit
    of budget. On a busy fleet that costs latency on the recovery, never the debt itself -- the
    marker stands until a push settles it.

    Fails CLOSED on a broker error: a push we cannot prove is owed is not worth reloading the whole
    fleet for, and the next run asks again.
    """
    try:
        client = _broker_client(broker_url)
        if not client.exists(RELOAD_OWED_KEY):
            return False
        attempts = int(client.incr(RELOAD_OWED_ATTEMPTS_KEY))  # type: ignore[arg-type]
    except BaseException as exc:
        logger.warning(f"Could not tell whether a cache push is owed: {exc}")
        return False

    if attempts <= RELOAD_OWED_FAST_RETRIES:
        return True
    if attempts % RELOAD_OWED_SLOW_RETRY_EVERY == 0:
        logger.error(
            f"A cache push has been owed for {attempts} job runs with an instance reachable the whole time. "
            "The push or the reload is failing without marking any instance down -- a broken custom config or one "
            "wedged instance would do this -- so retrying on every job would re-ship the whole cache tree each time; "
            "carrying it once now, but this needs an operator."
        )
        return True
    return False


def _push_service_count(logger=None) -> int:
    """How many services the cache archive covers.

    DEV-2b3: the environment is the FALLBACK, not the source. A split-container worker has no
    SERVER_NAME of its own (`misc/dev/docker-compose.ui.api.yml` sets it on `bw-scheduler` only),
    and an all-in-one whose services come from the UI or autoconf exports it empty, so counting
    from the env alone left exactly the deployments this timeout is for on the flat floor. Same
    shape as `core/pro/jobs/download-pro-plugins.py`: database first, env second.
    """
    with suppress(BaseException):
        services = get_worker_db().get_services(with_drafts=True)
        if services:
            return len(services)
    if logger is not None:
        logger.debug("Sizing the cache push from SERVER_NAME: no service could be read from the database")
    return len(os.getenv("SERVER_NAME", "").split())


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
    from ApiCaller import folder_push_timeout  # type: ignore  # DEV-2b3 (deps are on sys.path by now, like every other import here)

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
            # Claimed with them, and for the same reason: this push carries what was owed when the
            # tar was built, and nothing raised after it.
            claimed_owed = client.get(RELOAD_OWED_KEY)

            # DEV-2b3 (port of dev 462c1e851): the archive is the whole cache tree, so its size
            # tracks the number of services -- a fleet with a hundred of them regularly needs more
            # than the flat 30s read budget this used to take, and the push failed on the timeout
            # with every file already built. The floor stays at that same 30s, so a small install
            # behaves exactly as before. `send_files` derives the body-write budget from the read
            # one; it reaches the socket only once `API.request` accepts it (dev 7a6bf2c70).
            if not apis.send_files("/var/cache/bunkerweb", "/cache", timeout=folder_push_timeout(30, _push_service_count(logger))):
                raise RuntimeError("Failed to send /var/cache/bunkerweb to BunkerWeb instances")

            if not apis.send_to_apis("POST", f"/reload?test={test}", timeout=RELOAD_TIMEOUT)[0]:
                raise RuntimeError("Failed to request BunkerWeb reload")

            # The material is on the instances and they have reloaded: now, and only now, is a
            # change that shipped with it genuinely applied.
            _apply_deferred_acks(client, claimed_acks, logger)
            # Whatever was owed when this round started left with this push: it ships the whole
            # tree, so one successful round settles every job whose own push was skipped or failed
            # earlier. Compare-and-delete, never a blind one -- a debt raised after the tar was
            # built belongs to material this push did not carry. The attempt budget is reset either
            # way: it counts consecutive failures to settle, not lifetime ones, and a debt that
            # outlived this round is a new debt entitled to its own fast window.
            if claimed_owed is not None:
                client.eval(SETTLE_OWED_IF_UNCHANGED, 1, RELOAD_OWED_KEY, claimed_owed)
            client.delete(RELOAD_OWED_ATTEMPTS_KEY)

            released = bool(client.eval(RELEASE_IF_CLEAN, 2, RELOAD_LOCK_KEY, RELOAD_DIRTY_KEY))
            if released:
                return
            logger.info("Another job finished during the reload, pushing and reloading again")
            client.expire(RELOAD_LOCK_KEY, RELOAD_LOCK_TTL)

        logger.warning(f"Still dirty after {MAX_RELOAD_ROUNDS} reload rounds, leaving it to the next job")
    finally:
        # The bound was hit, or the push raised. Either way the flag stays up, and the next job to
        # finish takes the lock and carries whatever is still waiting -- but "the next job" only
        # used to mean a job that exits 1, so a failed push waited for the next *change* instead of
        # the next run. The owed flag makes any later run carry it.
        if not released:
            # Owed BEFORE the lock goes, not after: release first and another worker can take the
            # lock, push, clear the debt, and then have this frame raise it again behind it -- one
            # fleet reload nobody owed. A new token, so the next push settles this debt and not an
            # older one it never carried.
            try:
                client.set(RELOAD_OWED_KEY, uuid4().hex)
            except BaseException as exc:
                # Every other broker write here says so when it fails; this one was the last silent
                # path left in a change whose whole subject is silent paths.
                logger.error(f"Could not record that a cache push is still owed after a failed reload: {exc}")
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
    # What the job deferred instead of doing, if anything -- drained in `finally` below, folded
    # into `error` (prefixed) only once we know the run is otherwise a success.
    deferral_reason: Optional[str] = None

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
        # First, before anything below that could itself raise (e.g. `_requeue_if_asked`'s
        # unguarded `int(job_data.get("requeue_count") or 0)`): a reason left by a job that then
        # crashed must not attach itself to a later, unrelated run in this same worker child, and
        # that guarantee only holds unconditionally if nothing between here and the drain can skip
        # it.
        deferral_reason = drain_deferral_reason()
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

    # Resolved here rather than before the run: a job takes seconds to minutes, and an instance
    # that registers while it runs can carry this very push. Asking beforehand answered for a
    # fleet that no longer exists -- on a cold boot, one that did not exist yet. Guarded because it
    # now runs after the work: a raise here used to cost a dispatch that had done nothing, and would
    # now cost the run row and re-run a job that already ran.
    resolution_failed = False
    try:
        apis = _get_apis(logger)
    except BaseException as exc:
        logger.error(f"[{run_id}] Could not resolve the BunkerWeb instances to reload: {exc}")
        apis = None
        resolution_failed = True

    if ret == 1 and not apis:
        # The job wrote its output and asked for it to be shipped, and there is nobody to ship it
        # to. Left silent (which it was), the cache stays on the worker, the instances keep serving
        # the previous configuration, and the run records as a plain success -- the operator has
        # nothing to grep for. Say it, record it as a deferral, and remember the push is owed so the
        # next run that does have an instance carries it.
        #
        # "Nobody to ship it to" and "the resolution itself broke" are different operator problems,
        # so they do not get the same words. Note how narrow the second one is: a database that
        # *refuses* never reaches it -- `_get_apis` swallows that inside its own try, falls through
        # to BUNKERWEB_INSTANCES and returns None, so a refusing DB is still reported as an empty
        # fleet (deliberate: from here the two are indistinguishable, and the operator's next step
        # is the same). `resolution_failed` means `_get_apis` itself raised: a failed
        # `from API import API`, a malformed instance row `API.from_instance()` chokes on, an
        # `ApiCaller()` that will not construct.
        said, recorded = (
            ("the BunkerWeb instances could not be resolved", "could not resolve any reachable instance")
            if resolution_failed
            else ("no BunkerWeb instance is reachable yet", "no reachable instance yet")
        )
        logger.warning(f"[{run_id}] Job {plugin}/{name} requested a reload but {said}; deferring its cache push to the next job that completes with one")
        _mark_reload_owed(broker_url, logger)
        deferral_reason = "; ".join(filter(None, (deferral_reason, f"{recorded} -- reload deferred")))

    # The executor returns a bare 2 for a job it could not even load or import; the reason it
    # logged is the only description of that failure there is.
    if not success and error is None:
        error = executor.last_error
    elif success and deferral_reason:
        # Not a failure: the flags are still raised on purpose, waiting for a precondition (e.g.
        # push-configs: every instance down). Prefixed so the UI can tell this apart from a plain
        # success (error is None) and from a real failure (success is False).
        error = f"{JOB_DEFERRAL_PREFIX}{deferral_reason}"

    if db:
        try:
            err = db.add_job_run(name, success, start, end, error=error)
            if err:
                logger.error(f"[{run_id}] Failed to record job run: {err}")
        except Exception as exc:
            logger.error(f"[{run_id}] Failed to record job run: {exc}")
    else:
        logger.warning(f"[{run_id}] Worker database is not initialized, skipping job run persistence")

    # `or _reload_is_owed(...)`: the push ships the whole /var/cache/bunkerweb tree, so any run
    # with a reachable instance can settle what an earlier one could not deliver -- it does not have
    # to be a run that changed something itself.
    if apis and (ret == 1 or _reload_is_owed(broker_url, logger)):
        try:
            logger.info(
                f"[{run_id}] Job {plugin}/{name} requested reload" if ret == 1 else f"[{run_id}] Carrying a cache push an earlier job could not deliver"
            )
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
