#!/usr/bin/env python3

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

LOGGER = getLogger("METRICS.SCRAPE-PERSIST-REPORTS")
exit_status = 0

try:
    # Only run when durable persistence of reports is enabled
    if getenv("METRICS_PERSIST_TO_DB", "yes") != "yes":
        LOGGER.info("METRICS_PERSIST_TO_DB is disabled, skipping reports persistence...")
        sys_exit(0)

    # Skip when metrics collection is off everywhere (USE_METRICS is multisite)
    metrics_enabled = False
    if getenv("MULTISITE", "no") == "yes":
        for server in getenv("SERVER_NAME", "").split():
            if getenv(f"{server}_USE_METRICS", getenv("USE_METRICS", "yes")) == "yes":
                metrics_enabled = True
                break
    elif getenv("USE_METRICS", "yes") == "yes":
        metrics_enabled = True

    if not metrics_enabled:
        LOGGER.info("Metrics collection is disabled, skipping reports persistence...")
        sys_exit(0)

    JOB = Job(LOGGER, __file__)

    db_metadata = JOB.db.get_metadata()
    if isinstance(db_metadata, str) or db_metadata["scheduler_first_start"]:
        LOGGER.info("First start of the scheduler, skipping reports persistence...")
        sys_exit(0)

    instances = JOB.db.get_instances()
    if not instances:
        LOGGER.info("No instances registered, nothing to scrape.")
        sys_exit(0)

    # Scrape every instance's existing Lua reports endpoint (length=-1 returns all filtered records).
    # The instance endpoint already applies the report filter (status 4xx OR detect) and dedup is on the
    # DB side by (instance_hostname, request_id), so re-scraping overlapping windows is idempotent.
    caller = ApiCaller([API.from_instance(instance) for instance in instances])
    resp, instances_data = caller.send_to_apis("GET", "/metrics/requests/query?start=0&length=-1&count_only=false", response=True)

    if not instances_data:
        LOGGER.warning("No response from instances while scraping reports.")
        sys_exit(0)

    scraped = 0
    failures = 0
    for hostname, data in instances_data.items():
        if not isinstance(data, dict) or data.get("status") != "success":
            LOGGER.warning(f"Skipping {hostname}: unsuccessful metrics response.")
            continue
        payload = data.get("msg")
        if not isinstance(payload, dict):
            LOGGER.warning(f"Skipping {hostname}: unexpected metrics payload shape.")
            continue
        records = payload.get("data") or []
        if not records:
            continue
        err = JOB.db.batch_upsert_metrics_requests(records, instance_hostname=hostname)
        if err:
            LOGGER.error(f"Failed to persist reports from {hostname}: {err}")
            failures += 1
            continue
        scraped += len(records)

    if failures:
        exit_status = 2
    LOGGER.info(f"Persisted blocked-request reports from {len(instances_data)} instance(s) ({scraped} records).")
except SystemExit as e:
    exit_status = e.code
except BaseException as e:
    exit_status = 2
    LOGGER.debug(format_exc())
    LOGGER.error(f"Exception while running scrape-persist-reports.py :\n{e}")

sys_exit(exit_status)
