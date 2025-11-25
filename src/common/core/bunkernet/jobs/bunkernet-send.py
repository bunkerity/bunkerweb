#!/usr/bin/env python3

from datetime import datetime, timedelta
from itertools import chain
from json import dumps, loads
from os import getenv, sep
from os.path import join
from pathlib import Path
from sys import exit as sys_exit, path as sys_path
from time import sleep
from traceback import format_exc

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("api",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from bunkernet import send_reports
from heapq import merge

from API import API  # type: ignore
from ApiCaller import ApiCaller  # type: ignore
from logger import getLogger  # type: ignore
from jobs import Job  # type: ignore

LOGGER = getLogger("BUNKERNET.SEND")
exit_status = 0

BATCH_SIZE = 100

try:
    # Check if at least a server has BunkerNet activated
    bunkernet_activated = False
    # Multisite case
    if getenv("MULTISITE", "no") == "yes":
        for first_server in getenv("SERVER_NAME", "www.example.com").split(" "):
            if getenv(f"{first_server}_USE_BUNKERNET", "yes") == "yes":
                bunkernet_activated = True
                break
    # Singlesite case
    elif getenv("USE_BUNKERNET", "yes") == "yes":
        bunkernet_activated = True

    if not bunkernet_activated:
        LOGGER.info("BunkerNet is not activated, skipping download...")
        sys_exit(0)

    # Create directory if it doesn't exist
    bunkernet_path = Path(sep, "var", "cache", "bunkerweb", "bunkernet")
    bunkernet_path.mkdir(parents=True, exist_ok=True)

    JOB = Job(LOGGER, __file__)

    db_metadata = JOB.db.get_metadata()

    if isinstance(db_metadata, str) or db_metadata["scheduler_first_start"]:
        LOGGER.info("First start of the scheduler, skipping send...")
        sys_exit(0)

    # Get ID from cache
    bunkernet_id = None
    bunkernet_id = JOB.get_cache("instance.id")
    if bunkernet_id:
        bunkernet_path.joinpath("instance.id").write_bytes(bunkernet_id)
        LOGGER.info("Successfully retrieved BunkerNet ID from db cache")
    else:
        LOGGER.info("No BunkerNet ID found in db cache")

    # Check if ID is present
    if not bunkernet_path.joinpath("instance.id").is_file():
        LOGGER.warning("Not sending BunkerNet data because instance is not registered")
        sys_exit(2)

    # Create API instances for each database instance (HTTPS-aware)
    apis = [API.from_instance(instance) for instance in JOB.db.get_instances()]

    apiCaller = ApiCaller(apis)

    # Get reports from all instances
    resp, instances_data = apiCaller.send_to_apis("GET", "/bunkernet/reports", response=True)

    instance_reports = []
    if resp:
        # Extract and sort requests using chain to flatten the nested lists
        instance_reports = list(chain.from_iterable((data.get("msg", []) for data in instances_data.values() if data.get("status", "ko") == "success")))

    cached_data = loads(JOB.get_cache("reports.json") or "{}")

    if not cached_data:
        cached_data = {"created": datetime.now().astimezone().isoformat(), "reports": []}

    # Merge reports and sort by the oldest first using heapq merge
    reports = list(merge(cached_data.get("reports", []), instance_reports, key=lambda x: datetime.fromisoformat(x["date"])))

    # Check if forced send is needed due to time
    force_send = datetime.fromisoformat(cached_data["created"]) + timedelta(hours=24) < datetime.now().astimezone()

    if force_send:
        LOGGER.info("Forcing send of cached reports as they are older than 24 hours")

    # Process reports in batches of 100
    remaining = len(reports)
    while force_send or remaining >= BATCH_SIZE:
        force_send = False

        batch, reports = reports[:BATCH_SIZE], reports[BATCH_SIZE:]

        LOGGER.info(f"Sending {len(batch)} / {remaining} reports to BunkerNet API ...")
        ok, status, data = send_reports(batch)

        if not ok or status in (429, 403):
            reports = batch + reports  # Add batch back to reports
            remaining = len(reports)

            if not ok:
                LOGGER.error(f"Error while sending data to BunkerNet API: {data}")
            elif status == 429:
                LOGGER.warning("BunkerNet API rate limit reached, will retry later")
            else:  # status == 403
                LOGGER.warning("BunkerNet instance banned, will retry later")
            break

        remaining = len(reports)

        if remaining >= BATCH_SIZE:
            LOGGER.info("Sleeping 2 seconds before next batch...")
            sleep(2)

    if reports:
        LOGGER.info(f"Caching {remaining} reports...")
        cached_data["reports"] = reports

        # Cache the remaining reports
        cached, err = JOB.cache_file("reports.json", dumps(cached_data, indent=2).encode())
        if not cached:
            LOGGER.error(f"Failed to cache reports.json :\n{err}")
            status = 2
    else:
        deleted, err = JOB.del_cache("reports.json")
        if not deleted:
            LOGGER.warning(f"Couldn't delete reports.json from cache : {err}")
except SystemExit as e:
    exit_status = e.code
except BaseException as e:
    exit_status = 2
    LOGGER.debug(format_exc())
    LOGGER.error(f"Exception while running bunkernet-send.py :\n{e}")

sys_exit(exit_status)
