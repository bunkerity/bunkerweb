#!/usr/bin/env python3
# push-configs: Render NGINX configs from the DB and ship them (plus cache,
# custom_configs, plugins, pro_plugins) to every registered BunkerWeb instance,
# then trigger a reload. Owned by the Celery worker; dispatched by the
# scheduler whenever the DB metadata flags signal a change. Replaces the
# in-process generate_*/send_file_to_bunkerweb path that lived in the
# scheduler before the worker refactor.

from contextlib import suppress
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
from traceback import format_exc

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("api",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

import redis  # type: ignore

from API import API  # type: ignore
from ApiCaller import ApiCaller  # type: ignore
from Database import Database  # type: ignore
from logger import setup_logger  # type: ignore
from jobs import _write_atomic  # type: ignore

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

LOCK_KEY = "bw:push_configs_inflight"
LOCK_TTL = 1800  # matches Celery task_time_limit
FAILOVER_KEEP = 3
INSTANCE_PUSH_TIMEOUT = (5, 60)
RELOAD_TIMEOUT = (5, 30)


def _redis_client():
    broker_url = getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
    return redis.Redis.from_url(broker_url, socket_timeout=5)


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

    plugins = db.get_plugins(_type="pro" if pro else "external", with_data=True)
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


def _materialize_caches(db: Database) -> None:
    LOGGER.info("Materializing job caches from DB ...")
    CACHE_PATH.mkdir(parents=True, exist_ok=True)

    cache_files = db.get_jobs_cache_files()
    desired_perms = S_IRUSR | S_IWUSR | S_IRGRP  # 0o640

    expected = set()
    for cache in cache_files:
        plugin_id = cache.get("plugin_id")
        file_name = cache.get("file_name") or ""
        if not plugin_id or not file_name:
            continue
        cache_dir = CACHE_PATH.joinpath(plugin_id, cache.get("service_id") or "")
        cache_path = cache_dir.joinpath(file_name)
        expected.add(cache_path)
        try:
            cache_dir.mkdir(parents=True, exist_ok=True)
            if file_name.endswith(".tgz"):
                extract_path = cache_dir
                if file_name.startswith("folder:"):
                    extract_path = Path(file_name.split("folder:", 1)[1].rsplit(".tgz", 1)[0])
                rmtree(extract_path, ignore_errors=True)
                extract_path.mkdir(parents=True, exist_ok=True)
                with tar_open(fileobj=BytesIO(cache["data"]), mode="r:gz") as tar:
                    try:
                        tar.extractall(extract_path, filter="fully_trusted")
                    except TypeError:
                        tar.extractall(extract_path)
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
    tz = getenv("TZ")
    if tz:
        cmd_env["TZ"] = tz

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
        apis.append(API.from_instance(inst, token=token))
    return ApiCaller(apis)


def _push_one_kind(api_caller: ApiCaller, src: Path, endpoint: str) -> bool:
    if not src.exists():
        LOGGER.warning(f"Skipping push of {src} → {endpoint}: source does not exist")
        return True
    LOGGER.info(f"Pushing {src} → {endpoint} ({len(api_caller.apis)} instance(s)) ...")
    return bool(api_caller.send_files(src.as_posix(), endpoint, timeout=INSTANCE_PUSH_TIMEOUT))


def _push_all(api_caller: ApiCaller) -> bool:
    ok = True
    for src, endpoint in (
        (CONFIG_PATH, "/confs"),
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


def _restore_from_snapshot(snapshot: Path, api_caller: ApiCaller) -> bool:
    LOGGER.warning(f"Reload failed; restoring failover snapshot {snapshot.name}")
    nginx_snap = snapshot.joinpath("nginx")
    cache_snap = snapshot.joinpath("cache")
    ok = True
    if nginx_snap.is_dir():
        ok = bool(api_caller.send_files(nginx_snap.as_posix(), "/confs", timeout=INSTANCE_PUSH_TIMEOUT)) and ok
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

    try:
        client = _redis_client()
        lock_acquired = bool(client.set(LOCK_KEY, str(int(datetime.now().timestamp())), nx=True, ex=LOCK_TTL))
    except BaseException as e:
        LOGGER.warning(f"Could not acquire Redis lock ({e}); proceeding without coordination")
        client = None
        lock_acquired = True

    if not lock_acquired:
        LOGGER.info("Another push-configs run is in flight; skipping")
        sys_exit(0)

    db = Database(LOGGER)

    instances = [inst for inst in db.get_instances() if inst.get("status") != "down"]
    if not instances:
        LOGGER.warning("No live BunkerWeb instances registered; nothing to push")
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

    push_ok = _push_all(api_caller)
    if not push_ok:
        LOGGER.error("One or more artifact pushes failed (see per-instance logs above)")

    reload_ok = _trigger_reload(api_caller)
    if reload_ok:
        LOGGER.info("Push and reload completed successfully")
    else:
        LOGGER.error("Reload failed on at least one instance")
        if snapshot is not None and _restore_from_snapshot(snapshot, api_caller):
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
