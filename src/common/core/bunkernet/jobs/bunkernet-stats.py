#!/usr/bin/env python3

from json import loads
from os import getenv, sep
from os.path import join
from sys import exit as sys_exit, path as sys_path
from traceback import format_exc

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("api",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from API import API  # type: ignore
from ApiCaller import ApiCaller  # type: ignore
from logger import getLogger  # type: ignore
from jobs import Job  # type: ignore

LOGGER = getLogger("BUNKERNET.STATS")
exit_status = 0


def _count_lines(data) -> int:
    if not data:
        return 0
    try:
        return len([line for line in data.decode("utf-8", "replace").splitlines() if line.strip()])
    except Exception:
        return 0


def _count_reports(data) -> int:
    if not data:
        return 0
    try:
        payload = loads(data.decode("utf-8", "replace"))
        reports = payload.get("reports", []) if isinstance(payload, dict) else payload
        return len(reports) if isinstance(reports, list) else 0
    except Exception:
        return 0


try:
    if getenv("USE_BUNKERNET_STATS", "yes") != "yes":
        LOGGER.info("USE_BUNKERNET_STATS is disabled, skipping BunkerNet stats persistence...")
        sys_exit(0)

    JOB = Job(LOGGER, __file__)

    db_metadata = JOB.db.get_metadata()
    if isinstance(db_metadata, str) or db_metadata["scheduler_first_start"]:
        LOGGER.info("First start of the scheduler, skipping BunkerNet stats persistence...")
        sys_exit(0)

    # Deployment-level contribution/health metrics, read from the existing BunkerNet job
    # caches (DB-backed; no instance round-trip needed).
    rows = []
    rows.append({"metric": "blocklist_size", "value": _count_lines(JOB.db.get_job_cache_file("bunkernet-data", "ip.list"))})
    rows.append({"metric": "reports_pending", "value": _count_reports(JOB.db.get_job_cache_file("bunkernet-send", "reports.json"))})
    instance_id = JOB.db.get_job_cache_file("bunkernet-register", "instance.id")
    rows.append({"metric": "registered", "value": 1 if instance_id and instance_id.strip() else 0})

    # Best-effort per-instance connectivity (never fails the job).
    try:
        instances = JOB.db.get_instances()
        if instances:
            caller = ApiCaller([API.from_instance(instance) for instance in instances])
            _, responses = caller.send_to_apis("POST", "/bunkernet/ping", response=True)
            if isinstance(responses, dict):
                for hostname, resp in responses.items():
                    connected = isinstance(resp, dict) and resp.get("status") == "success"
                    rows.append({"metric": "connected", "value": 1 if connected else 0, "instance_hostname": hostname})
    except Exception:
        LOGGER.debug(format_exc())

    err = JOB.db.ext("bunkernet").upsert_stats(rows)
    if err:
        LOGGER.error(f"Failed to persist BunkerNet stats: {err}")
        exit_status = 2
    else:
        LOGGER.info(f"Persisted {len(rows)} BunkerNet stat metric(s).")
except SystemExit as e:
    exit_status = e.code
except BaseException as e:
    exit_status = 2
    LOGGER.debug(format_exc())
    LOGGER.error(f"Exception while running bunkernet-stats.py :\n{e}")

sys_exit(exit_status)
