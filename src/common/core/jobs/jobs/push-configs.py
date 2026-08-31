#!/usr/bin/env python3
# push-configs: Render NGINX configs from the DB and ship them (plus cache,
# custom_configs, plugins, pro_plugins) to every registered BunkerWeb instance,
# then trigger a reload. Owned by the Celery worker; dispatched by the
# scheduler whenever the DB metadata flags signal a change. Replaces the
# in-process generate_*/send_file_to_bunkerweb path that lived in the
# scheduler before the worker refactor.

from contextlib import nullcontext, suppress
from datetime import datetime
from io import BytesIO
from os import getenv, sep
from os.path import join
from pathlib import Path
from shutil import copytree, rmtree
from stat import S_IRGRP, S_IRUSR, S_IWUSR, S_IXGRP, S_IXUSR
from subprocess import DEVNULL, STDOUT, run as subprocess_run
from sys import exit as sys_exit, path as sys_path
from tarfile import open as tar_open
from tempfile import TemporaryDirectory
from traceback import format_exc
from uuid import uuid4

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("api",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

import redis  # type: ignore

from API import API  # type: ignore
from ApiCaller import ApiCaller  # type: ignore
from Database import Database  # type: ignore
from logger import setup_logger  # type: ignore
from jobs import _write_atomic  # type: ignore

try:
    from letsencrypt_consistency import le_cache_write_lock  # type: ignore
except Exception:
    le_cache_write_lock = None  # type: ignore

LOGGER = setup_logger("JOBS.PUSH-CONFIGS")

BUNKERWEB_PATH = Path(sep, "usr", "share", "bunkerweb")
CONFIG_PATH = Path(sep, "etc", "nginx")
CACHE_PATH = Path(sep, "var", "cache", "bunkerweb")
CUSTOM_CONFIGS_PATH = Path(sep, "etc", "bunkerweb", "configs")
EXTERNAL_PLUGINS_PATH = Path(sep, "etc", "bunkerweb", "plugins")
PRO_PLUGINS_PATH = Path(sep, "etc", "bunkerweb", "pro", "plugins")
FAILOVER_PATH = Path(sep, "var", "tmp", "bunkerweb", "failover")

CUSTOM_CONFIGS_DIRS = (
    "http",
    "stream",
    "server-http",
    "server-stream",
    "default-server-http",
    "default-server-stream",
    "modsec",
    "modsec-crs",
    "crs-plugins-before",
    "crs-plugins-after",
)

# This lease lives on the Celery broker, and its correctness depends on the broker running
# `maxmemory-policy noeviction`. It is a TTL'd key, so any `volatile-*` policy is free to evict
# it while a push is still in flight — two workers would then push configs to the fleet at once.
# That is why the broker is a dedicated instance everywhere (shipped compose stacks, k8s
# manifests, and `ensure_job_broker` in misc/install-bunkerweb.sh) and never shares a server
# with the WAF datastore, which evicts on purpose. Do not "optimize" the policy back.
LOCK_KEY = "bw:push_configs_inflight"
LOCK_TTL = 1800  # matches Celery task_time_limit
FAILOVER_KEEP = 3
INSTANCE_PUSH_TIMEOUT = (5, 60)
RELOAD_TIMEOUT = (5, 30)

RETIRED_CACHE_ROWS = {
    ("api-server-cert", "api-server-cert.key"),
    ("api-server-cert", "api-server-cert.pem"),
    ("default-server-cert", "default-server-cert.key"),
    ("default-server-cert", "default-server-cert.pem"),
    # The GeoIP databases moved from this plugin to the `geoip` core plugin
    ("mmdb-country", "country.mmdb"),
    ("mmdb-asn", "asn.mmdb"),
}
RETIRED_CACHE_PATHS = {
    ("jobs", "api-server-cert.key"),
    ("jobs", "api-server-cert.pem"),
    ("misc", "api-server-cert.key"),
    ("misc", "api-server-cert.pem"),
    ("misc", "default-server-cert.key"),
    ("misc", "default-server-cert.pem"),
    # Superseded by /var/cache/bunkerweb/geoip/*.mmdb
    ("jobs", "country.mmdb"),
    ("jobs", "asn.mmdb"),
}


def _redis_client():
    broker_url = getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
    return redis.Redis.from_url(broker_url, socket_timeout=5)


def acquire_lease(client, lock_owner: str, reclaimable: bool) -> bool:
    """Take the push-configs lease, reclaiming one this same dispatch left behind.

    The lease is released in a `finally`, which a SIGKILL never reaches, so a worker killed
    mid-push leaves it held for up to LOCK_TTL. Job delivery is at-least-once, so the next run
    is very often the redelivery of the dispatch that was killed -- and with the old
    timestamp-valued lease it could not tell its own orphan from a genuinely concurrent run. It
    exited 0, was recorded as a SUCCESS, and every instance carried on serving the previous
    configuration until something else happened to dispatch a push.

    `lock_owner` is the Celery task id, which is stable across a redelivery, so an owner match
    means "this is my own orphan" and nothing else. `reclaimable` is False when there is no task
    id to match on (bwcli, an older worker): then a failed acquisition is always someone else's,
    which is the safe reading.
    """
    if client.set(LOCK_KEY, lock_owner, nx=True, ex=LOCK_TTL):
        return True

    if not reclaimable:
        return False

    holder = client.get(LOCK_KEY)
    if holder is None or holder.decode("utf-8", "replace") != lock_owner:
        return False

    LOGGER.warning("Reclaiming the lease left behind by an interrupted delivery of this same run")
    client.set(LOCK_KEY, lock_owner, ex=LOCK_TTL)
    return True


def acknowledge_changes(db: Database, metadata_snapshot, reason: str) -> None:
    """Tell the database this run applied the changes it read, and only those.

    The scheduler used to clear the change flags in the same iteration that DISPATCHED this job.
    Dispatch is fire-and-forget -- there is no result backend -- so a push that never completed
    left the flags already clear and nothing re-dispatched it: instances kept serving the
    previous configuration indefinitely.

    Acknowledging here, from the run that actually pushed, closes that. `metadata_snapshot` is
    taken before this job reads anything, and the clear is a compare-and-set against each
    change's `last_*_change` watermark, so a change that landed WHILE this run worked has a
    newer watermark, is not acknowledged, and gets picked up on the next poll.

    `plugins_config` belongs in that list: a settings change sets each affected plugin's
    `config_changed`, and this push is what applies it. Leaving it out stranded the flag —
    nothing else clears it — and autoconf's readiness gate blocks on it, so every
    configuration change cost autoconf the full 240s it waits before giving up.
    """
    error = db.clear_applied_changes(metadata_snapshot, ("custom_configs", "external_plugins", "pro_plugins", "instances", "plugins_config"))
    if error:
        # Not fatal: leaving a flag set costs a redundant push next poll, which is the safe
        # direction. Clearing it wrongly would cost a lost configuration.
        LOGGER.error(f"Could not acknowledge the applied changes ({reason}): {error}")
    else:
        LOGGER.info(f"Acknowledged the configuration changes applied by this run ({reason})")


def may_acknowledge_without_pushing(registered_instances) -> bool:
    """Whether a run that pushed to nobody may still clear the change flags.

    Only when nothing is registered at all, and that case is load-bearing rather than a
    convenience: autoconf refuses to register anything while a change flag is set
    (`autoconf/Config.py:have_to_wait`, which `wait_applying` spins on for 240s inside
    `expect_errors`, so it does it silently). Nothing but a push clears those flags, and a push
    needs an instance. Acknowledge here and the bootstrap proceeds; hold the flags and the two
    sides wait on each other until autoconf times out -- verified on an Autoconf stack, where the
    stack came up with zero instances and stayed that way, and no configuration was ever pushed.
    Registering an instance raises `instances_changed` (db_methods/instances.py:86), so a real
    push follows as soon as there is somewhere to push to.

    When instances ARE registered but every one of them is currently down, the change is still
    pending, not inapplicable. Acknowledging there clears the flags with nothing else to re-raise
    them, so the fleet keeps serving its previous configuration until an unrelated change happens
    along -- which is exactly what a container restart produced: the database held
    `USE_MODSECURITY=no` while the instance went on enforcing `yes`.
    """
    return not registered_instances


def _materialize_custom_configs(db: Database) -> None:
    LOGGER.info("Materializing custom configs from DB ...")
    CUSTOM_CONFIGS_PATH.mkdir(parents=True, exist_ok=True)
    for sub in CUSTOM_CONFIGS_DIRS:
        CUSTOM_CONFIGS_PATH.joinpath(sub).mkdir(parents=True, exist_ok=True)

    for sub_dir in CUSTOM_CONFIGS_PATH.iterdir():
        if sub_dir.is_dir():
            for entry in sub_dir.glob("*"):
                if entry.is_dir():
                    rmtree(entry, ignore_errors=True)
                else:
                    with suppress(OSError):
                        entry.unlink()

    configs = db.get_custom_configs()
    if not configs:
        return

    desired_perms = S_IRUSR | S_IWUSR | S_IRGRP  # 0o640
    for cc in configs:
        if cc.get("is_draft") or not cc.get("data"):
            continue
        try:
            tmp_path = CUSTOM_CONFIGS_PATH.joinpath(
                cc["type"].replace("_", "-"),
                cc["service_id"] or "",
                f"{Path(cc['name']).stem}.conf",
            )
            tmp_path.parent.mkdir(parents=True, exist_ok=True)
            _write_atomic(tmp_path, cc["data"])
            if tmp_path.stat().st_mode & 0o777 != desired_perms:
                tmp_path.chmod(desired_perms)
        except BaseException as e:
            LOGGER.error(f"Failed to materialize custom config {cc.get('name')!r}: {e}")


def _materialize_plugins(db: Database, target: Path, *, pro: bool) -> None:
    label = "pro" if pro else "external"
    LOGGER.info(f"Materializing {label} plugins from DB ...")
    target.mkdir(parents=True, exist_ok=True)

    plugins = db.get_plugins(_type="pro" if pro else "external", with_data=True, only_enabled=True)
    keep_ids = {p["id"] for p in plugins}

    for entry in target.iterdir():
        if entry.name in keep_ids:
            continue
        if entry.is_dir():
            rmtree(entry, ignore_errors=True)
        else:
            with suppress(OSError):
                entry.unlink()

    if not plugins:
        return

    desired_exec = S_IRUSR | S_IWUSR | S_IXUSR | S_IRGRP | S_IXGRP  # 0o750
    for plugin in plugins:
        data = plugin.get("data")
        if not data:
            continue
        try:
            with tar_open(fileobj=BytesIO(data), mode="r:gz") as tar:
                try:
                    tar.extractall(target, filter="fully_trusted")
                except TypeError:
                    tar.extractall(target)

            plugin_dir = target.joinpath(plugin["id"])
            for subdir, pattern in (("jobs", "*"), ("bwcli", "*"), ("ui", "*.py")):
                sub = plugin_dir.joinpath(subdir)
                if not sub.is_dir():
                    continue
                for executable in sub.rglob(pattern):
                    if executable.is_file() and executable.stat().st_mode & 0o777 != desired_exec:
                        executable.chmod(desired_exec)
        except BaseException as e:
            LOGGER.error(f"Failed to extract {label} plugin {plugin.get('id')!r}: {e}")


def _purge_retired_caches(db: Database) -> None:
    """Drop the cache rows and files left behind by PREVIOUS versions.

    The two failure modes are deliberately NOT treated the same.

    A ROW that will not delete is a non-event, so it only warns. `_materialize_caches` skips every
    RETIRED_CACHE_ROWS entry, so a surviving row never reaches disk and never reaches an instance.
    This used to raise, and it cost the fleet its configuration once: a single transient
    `(1146, "Table 'db.bw_jobs_cache' doesn't exist")` on a freshly forked Celery child came out of
    here, and since this runs before any instance is contacted, every instance carried on serving
    the previous configuration -- to protect a row whose only cost is disk. Note this does NOT make
    the push survive a structurally missing `bw_jobs_cache`: `_materialize_caches` reads that same
    table a few lines below and that read is load-bearing.

    A FILE that will not delete stays fatal, and that is the point of the asymmetry. The retired
    entries include `api-server-cert.key` and `default-server-cert.key`, and whatever is still
    under CACHE_PATH after this point gets copied into the failover snapshot (`_snapshot_failover`)
    and pushed to every instance (`_push_all`). Aborting beats redistributing retired private keys,
    so no exception is caught below.
    """
    errors = []
    for job_name, file_name in RETIRED_CACHE_ROWS:
        error = db.delete_job_cache(file_name, job_name=job_name)
        if error:
            errors.append(f"{job_name}/{file_name}: {error}")

    cache_roots = [CACHE_PATH]
    if FAILOVER_PATH.is_dir():
        cache_roots.extend(snapshot.joinpath("cache") for snapshot in FAILOVER_PATH.iterdir() if snapshot.is_dir())
    for cache_root in cache_roots:
        for plugin_id, file_name in RETIRED_CACHE_PATHS:
            cache_root.joinpath(plugin_id, file_name).unlink(missing_ok=True)

    if errors:
        LOGGER.warning(f"Could not purge some retired cache rows from the database: {'; '.join(errors)}")


def _materialize_caches(db: Database) -> None:
    LOGGER.info("Materializing job caches from DB ...")
    CACHE_PATH.mkdir(parents=True, exist_ok=True)

    cache_files = db.get_jobs_cache_files()
    desired_perms = S_IRUSR | S_IWUSR | S_IRGRP  # 0o640

    for cache in cache_files:
        plugin_id = cache.get("plugin_id")
        file_name = cache.get("file_name") or ""
        if not plugin_id or not file_name:
            continue
        if (cache.get("job_name"), file_name) in RETIRED_CACHE_ROWS or (plugin_id, file_name) in RETIRED_CACHE_PATHS:
            continue
        cache_dir = CACHE_PATH.joinpath(plugin_id, cache.get("service_id") or "")
        cache_path = cache_dir.joinpath(file_name)
        try:
            cache_dir.mkdir(parents=True, exist_ok=True)
            if file_name.endswith(".tgz"):
                extract_path = cache_dir
                if file_name.startswith("folder:"):
                    extract_path = Path(file_name.split("folder:", 1)[1].rsplit(".tgz", 1)[0])
                is_letsencrypt = plugin_id == "letsencrypt"
                # Open once to inspect membership before any destructive rmtree.
                with tar_open(fileobj=BytesIO(cache["data"]), mode="r:gz") as tar:
                    members = tar.getmembers()
                    if is_letsencrypt and not any(
                        m.name.replace("\\", "/").endswith("fullchain.pem") and "/live/" in ("/" + m.name.replace("\\", "/")) for m in members
                    ):
                        # Empty/skeleton LE row: never wipe a possibly-good on-disk tree
                        # (certbot may be mid-issuance or already delivered a real cert).
                        LOGGER.warning("Skipping rebuild of Let's Encrypt cache tree: DB row contains no live/*/fullchain.pem (empty/skeleton row)")
                        continue
                    # Serialize the LE-tree rebuild against certbot-new's direct /cache push.
                    lock_cm = le_cache_write_lock() if (is_letsencrypt and le_cache_write_lock is not None) else nullcontext()
                    with lock_cm:
                        rmtree(extract_path, ignore_errors=True)
                        extract_path.mkdir(parents=True, exist_ok=True)
                        try:
                            tar.extractall(extract_path, members=members, filter="fully_trusted")
                        except TypeError:
                            tar.extractall(extract_path, members=members)
                continue
            _write_atomic(cache_path, cache["data"])
            if cache_path.stat().st_mode & 0o777 != desired_perms:
                cache_path.chmod(desired_perms)
        except BaseException as e:
            LOGGER.error(f"Failed to materialize cache {file_name!r}: {e}")


def _render_nginx_configs() -> bool:
    cmd_env = {
        "PATH": getenv("PATH", ""),
        "PYTHONPATH": getenv("PYTHONPATH", ""),
        "CUSTOM_LOG_LEVEL": getenv("CUSTOM_LOG_LEVEL", ""),
        "LOG_LEVEL": getenv("LOG_LEVEL", ""),
        "DATABASE_URI": getenv("DATABASE_URI", ""),
    }
    # The logging variables have to travel with it, same reason as `build_cmd_env` in the
    # scheduler: without them gen/main.py falls back to LOG_TYPES=stderr, so on Linux every
    # rendering error lands in journald while the log file only keeps the one-line summary.
    for key in ("TZ", "LOG_TYPES", "LOG_FILE_PATH", "LOG_SYSLOG_ADDRESS", "LOG_SYSLOG_TAG", "DATABASE_LOG_LEVEL"):
        value = getenv(key)
        if value:
            cmd_env[key] = value

    LOGGER.info("Rendering NGINX configs via gen/main.py ...")
    proc = subprocess_run(
        [
            BUNKERWEB_PATH.joinpath("gen", "main.py").as_posix(),
            "--settings",
            BUNKERWEB_PATH.joinpath("settings.json").as_posix(),
            "--templates",
            BUNKERWEB_PATH.joinpath("confs").as_posix(),
            "--output",
            CONFIG_PATH.as_posix(),
        ],
        stdin=DEVNULL,
        stderr=STDOUT,
        check=False,
        env=cmd_env,
    )
    if proc.returncode != 0:
        LOGGER.error("gen/main.py failed; configs not rendered")
        return False
    return True


def _build_api_caller(instances, *, hostnames=None) -> ApiCaller:
    token = getenv("API_TOKEN") or None
    apis = []
    for inst in instances:
        if hostnames is not None and inst.get("hostname") not in hostnames:
            continue
        # Per-instance credential wins; fall back to the global API token when unset.
        apis.append(API.from_instance(inst, token=inst.get("credential") or token))
    return ApiCaller(apis)


def _push_one_kind(api_caller: ApiCaller, src: Path, endpoint: str) -> bool:
    if not src.exists():
        LOGGER.warning(f"Skipping push of {src} → {endpoint}: source does not exist")
        return True
    LOGGER.info(f"Pushing {src} → {endpoint} ({len(api_caller.apis)} instance(s)) ...")
    return bool(api_caller.send_files(src.as_posix(), endpoint, timeout=INSTANCE_PUSH_TIMEOUT))


def _config_with_api_token(data: bytes, token: str) -> bytes:
    if "\n" in token or "\r" in token:
        raise ValueError("instance API credential contains a newline")
    lines = data.splitlines(keepends=True)
    for index, line in enumerate(lines):
        if line.startswith(b"API_TOKEN="):
            ending = b"\r\n" if line.endswith(b"\r\n") else b"\n" if line.endswith(b"\n") else b""
            lines[index] = f"API_TOKEN={token}".encode() + (ending or b"\n")
            return b"".join(lines)
    if data and not data.endswith((b"\n", b"\r")):
        data += b"\n"
    return data + f"API_TOKEN={token}\n".encode()


def _push_configs(instances, src: Path = CONFIG_PATH) -> bool:
    if not src.exists():
        LOGGER.warning(f"Skipping push of {src} → /confs: source does not exist")
        return True

    ok = True
    for instance in instances:
        hostname = instance.get("hostname", "unknown")
        try:
            with TemporaryDirectory(prefix="bw-push-configs-") as tmp:
                rendered = Path(tmp, "nginx")
                copytree(src, rendered, symlinks=True)
                variables = rendered.joinpath("variables.env")
                _write_atomic(variables, _config_with_api_token(variables.read_bytes(), instance.get("credential") or getenv("API_TOKEN", "")))
                ok = _push_one_kind(_build_api_caller([instance]), rendered, "/confs") and ok
        except (OSError, ValueError) as exc:
            LOGGER.error(f"Failed to prepare instance-specific configuration for {hostname}: {exc}")
            ok = False
    return ok


def _push_all(api_caller: ApiCaller, instances) -> bool:
    ok = _push_configs(instances)
    for src, endpoint in (
        (CACHE_PATH, "/cache"),
        (CUSTOM_CONFIGS_PATH, "/custom_configs"),
        (EXTERNAL_PLUGINS_PATH, "/plugins"),
        (PRO_PLUGINS_PATH, "/pro_plugins"),
    ):
        ok = _push_one_kind(api_caller, src, endpoint) and ok
    return ok


def _trigger_reload(api_caller: ApiCaller) -> bool:
    test = "no" if getenv("DISABLE_CONFIGURATION_TESTING", "no").lower() == "yes" else "yes"
    LOGGER.info(f"Reloading {len(api_caller.apis)} instance(s) (test={test}) ...")
    sent, _ = api_caller.send_to_apis("POST", f"/reload?test={test}", timeout=RELOAD_TIMEOUT)
    return bool(sent)


def _snapshot_failover() -> Path | None:
    if not CONFIG_PATH.is_dir():
        return None
    FAILOVER_PATH.mkdir(parents=True, exist_ok=True)
    snapshot = FAILOVER_PATH.joinpath(datetime.now().astimezone().strftime("%Y%m%dT%H%M%S"))
    try:
        snapshot.mkdir(parents=True, exist_ok=True)
        copytree(CONFIG_PATH, snapshot.joinpath("nginx"), dirs_exist_ok=True, symlinks=True)
        if CACHE_PATH.is_dir():
            copytree(CACHE_PATH, snapshot.joinpath("cache"), dirs_exist_ok=True, symlinks=True)
    except BaseException as e:
        LOGGER.warning(f"Failover snapshot failed: {e}")
        return None

    snapshots = sorted([p for p in FAILOVER_PATH.iterdir() if p.is_dir()])
    for old in snapshots[:-FAILOVER_KEEP]:
        rmtree(old, ignore_errors=True)
    return snapshot


def _restore_from_snapshot(snapshot: Path, api_caller: ApiCaller, instances) -> bool:
    LOGGER.warning(f"Reload failed; restoring failover snapshot {snapshot.name}")
    nginx_snap = snapshot.joinpath("nginx")
    cache_snap = snapshot.joinpath("cache")
    ok = True
    if nginx_snap.is_dir():
        ok = _push_configs(instances, nginx_snap) and ok
    if cache_snap.is_dir():
        ok = bool(api_caller.send_files(cache_snap.as_posix(), "/cache", timeout=INSTANCE_PUSH_TIMEOUT)) and ok
    if not ok:
        LOGGER.error("Failed to ship failover snapshot to instances")
        return False
    return _trigger_reload(api_caller)


def _mark_failover(db: Database, instances) -> None:
    for inst in instances:
        hostname = inst.get("hostname")
        if not hostname:
            continue
        err = db.update_instance(hostname, "failover")
        if err:
            LOGGER.error(f"Failed to mark instance {hostname} as failover: {err}")


# ── Main ────────────────────────────────────────────────────────────────────

status = 0
lock_acquired = False
client = None

try:
    target_hostnames_env = getenv("PUSH_CONFIGS_TARGETS", "").strip()
    target_hostnames = {h for h in target_hostnames_env.split() if h} or None

    # The worker exports the Celery task id, which is stable across a redelivery of the same
    # dispatch -- that is what makes the lease reclaimable below. Outside the worker (bwcli, an
    # older worker) there is no such id, so fall back to a value that is unique per process and
    # can therefore never match an existing holder: no id means no reclaiming, which is the
    # safe direction.
    run_id = getenv("BW_JOB_RUN_ID", "").strip()
    lock_owner = run_id or f"anonymous-{uuid4()}"

    try:
        client = _redis_client()
        lock_acquired = acquire_lease(client, lock_owner, bool(run_id))
    except BaseException as e:
        LOGGER.warning(f"Could not acquire Redis lock ({e}); proceeding without coordination")
        client = None
        lock_acquired = True

    if not lock_acquired:
        LOGGER.info("Another push-configs run is in flight; skipping")
        sys_exit(0)

    db = Database(LOGGER)

    # Snapshot the change flags BEFORE reading anything we are about to apply. Everything below
    # -- the materialize calls, and gen/main.py inside _render_nginx_configs, which opens its own
    # connection later still -- reads the database strictly after this point, so any change that
    # lands from here on carries a newer watermark than the snapshot and will not be acknowledged
    # by this run. Snapshotting after the reads would swallow it.
    metadata_snapshot = db.get_metadata()

    _purge_retired_caches(db)

    registered_instances = db.get_instances(with_credential=True)
    instances = [inst for inst in registered_instances if inst.get("status") != "down"]
    if not instances:
        # "Nothing registered" and "everything registered is down" look the same here and are
        # opposites -- see may_acknowledge_without_pushing().
        if not may_acknowledge_without_pushing(registered_instances):
            # A restart is the ordinary way to land here: the instances exist but the scheduler
            # has them marked down, so this run has nowhere to push *yet*. Leave the flags set
            # and let a later run apply them -- the scheduler re-dispatches when an instance
            # comes back up (healthcheck_job) and again on the APPLY_RETRY_INTERVAL re-arm.
            LOGGER.warning(f"All {len(registered_instances)} registered BunkerWeb instance(s) are down; leaving the changes pending for a later run")
            sys_exit(0)

        LOGGER.warning("No BunkerWeb instances registered; nothing to push")
        acknowledge_changes(db, metadata_snapshot, "no instances registered")
        sys_exit(0)

    if target_hostnames:
        instances = [inst for inst in instances if inst.get("hostname") in target_hostnames]
        if not instances:
            LOGGER.warning(f"No live targets matched {sorted(target_hostnames)}; nothing to push")
            sys_exit(0)

    snapshot = _snapshot_failover()

    _materialize_custom_configs(db)
    _materialize_plugins(db, EXTERNAL_PLUGINS_PATH, pro=False)
    _materialize_plugins(db, PRO_PLUGINS_PATH, pro=True)
    _materialize_caches(db)

    if not _render_nginx_configs():
        LOGGER.error("Aborting push: NGINX config rendering failed")
        sys_exit(2)

    api_caller = _build_api_caller(instances)

    push_ok = _push_all(api_caller, instances)
    if not push_ok:
        LOGGER.error("One or more artifact pushes failed (see per-instance logs above)")

    reload_ok = _trigger_reload(api_caller)
    if reload_ok:
        LOGGER.info("Push and reload completed successfully")
        # Only here. Gating on the exit code instead would acknowledge four paths that reach
        # exit 0 having pushed nothing (the lease skip, no live instances, no target match, and
        # a failed push whose reload still succeeded), and `Jobs_runs.success` is likewise true
        # for all of them -- neither is a statement that instances took the new configuration.
        if push_ok:
            acknowledge_changes(db, metadata_snapshot, "pushed and reloaded")
        else:
            LOGGER.warning("Not acknowledging the changes: at least one artifact push failed, so a re-push is still owed")
    else:
        LOGGER.error("Reload failed on at least one instance")
        if snapshot is not None and _restore_from_snapshot(snapshot, api_caller, instances):
            LOGGER.warning("Successfully restored previous configuration after reload failure")
        else:
            LOGGER.error("Failover restore failed; marking instances as failover")
            _mark_failover(db, instances)
            status = 2

    # Always return 0 unless we hit a catastrophic failure: the legacy
    # ret==1 / _request_reload_debounced path in worker.tasks would otherwise
    # double-fire a cache push + reload that we already performed here.
    if status == 0:
        sys_exit(0)
    sys_exit(status)
except SystemExit:
    raise
except BaseException as e:
    LOGGER.error(f"push-configs crashed: {e}\n{format_exc()}")
    sys_exit(2)
finally:
    if lock_acquired and client is not None:
        with suppress(BaseException):
            client.delete(LOCK_KEY)
