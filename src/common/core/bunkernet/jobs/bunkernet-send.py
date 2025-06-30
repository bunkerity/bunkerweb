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

for deps_path in [
    join(sep, "usr", "share", "bunkerweb", *paths) 
    for paths in (
        ("deps", "python"), 
        ("utils",), 
        ("api",), 
        ("db",)
    )
]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from bunkernet import send_reports
from heapq import merge

from API import API  # type: ignore
from ApiCaller import ApiCaller  # type: ignore
from logger import setup_logger  # type: ignore
from jobs import Job  # type: ignore

LOGGER = setup_logger("BUNKERNET.send")
exit_status = 0

BATCH_SIZE = 100


def debug_log(logger, message):
    # Log debug messages only when LOG_LEVEL environment variable is set to
    # "debug"
    if getenv("LOG_LEVEL") == "debug":
        logger.debug(f"[DEBUG] {message}")


def check_bunkernet_activation():
    # Check if BunkerNet is activated for at least one server.
    # Returns: True if BunkerNet is activated, False otherwise
    debug_log(LOGGER, "Checking BunkerNet activation status")
    
    bunkernet_activated = False
    
    # Multisite case
    if getenv("MULTISITE", "no") == "yes":
        server_names = getenv("SERVER_NAME", "www.example.com").split(" ")
        debug_log(LOGGER, f"Multisite mode - checking servers: {server_names}")
        
        for first_server in server_names:
            use_bunkernet = getenv(f"{first_server}_USE_BUNKERNET", "yes")
            debug_log(LOGGER, 
                f"Server {first_server}: USE_BUNKERNET={use_bunkernet}")
            
            if use_bunkernet == "yes":
                bunkernet_activated = True
                break
    # Singlesite case
    elif getenv("USE_BUNKERNET", "yes") == "yes":
        bunkernet_activated = True
        debug_log(LOGGER, "Singlesite mode - BunkerNet activated")

    debug_log(LOGGER, f"BunkerNet activation result: {bunkernet_activated}")
    
    return bunkernet_activated


def get_cached_reports(job):
    # Get cached reports from database.
    # Args: job (Job instance for database operations)
    # Returns: dict with cached reports data and creation timestamp
    debug_log(LOGGER, "Getting cached reports from database")
    
    cached_data = loads(job.get_cache("reports.json") or "{}")

    if not cached_data:
        cached_data = {
            "created": datetime.now().astimezone().isoformat(), 
            "reports": []
        }
        debug_log(LOGGER, "No cached data found, creating new cache structure")
    else:
        debug_log(LOGGER, f"Found cached data created: {cached_data.get('created')}")
        debug_log(LOGGER, f"Cached reports count: {len(cached_data.get('reports', []))}")
    
    return cached_data


def get_instance_reports(api_caller):
    # Get reports from all BunkerWeb instances.
    # Args: api_caller (ApiCaller instance for making API requests)
    # Returns: list of reports from all instances
    debug_log(LOGGER, "Getting reports from all instances")
    
    resp, instances_data = api_caller.send_to_apis(
        "GET", 
        "/bunkernet/reports", 
        response=True
    )

    instance_reports = []
    if resp:
        # Extract and sort requests using chain to flatten nested lists
        instance_reports = list(chain.from_iterable((
            data.get("msg", []) 
            for data in instances_data.values() 
            if data.get("status", "ko") == "success"
        )))
        
        debug_log(LOGGER, f"Retrieved {len(instance_reports)} instance reports")
    else:
        debug_log(LOGGER, "Failed to get reports from instances")
    
    return instance_reports


def merge_and_sort_reports(cached_data, instance_reports):
    # Merge cached and instance reports, sorted by date.
    # Args: cached_data (dict with cached reports), 
    # instance_reports (list of reports from instances)
    # Returns: list of merged and sorted reports
    cached_count = len(cached_data.get("reports", []))
    instance_count = len(instance_reports)
    debug_log(LOGGER, 
        f"Merging {cached_count} cached + {instance_count} instance reports")
    
    # Merge reports and sort by oldest first using heapq merge
    reports = list(merge(
        cached_data.get("reports", []), 
        instance_reports, 
        key=lambda x: datetime.fromisoformat(x["date"])
    ))
    
    debug_log(LOGGER, f"Total merged reports: {len(reports)}")
    
    return reports


def should_force_send(cached_data):
    # Check if forced send is needed due to age of cached data.
    # Args: cached_data (dict with cached reports and creation time)
    # Returns: True if force send is needed, False otherwise
    force_send = (
        datetime.fromisoformat(cached_data["created"]) + timedelta(hours=24) 
        < datetime.now().astimezone()
    )
    
    cache_age = (
        datetime.now().astimezone() 
        - datetime.fromisoformat(cached_data["created"])
    )
    debug_log(LOGGER, f"Cache age: {cache_age}, force send: {force_send}")
    
    return force_send


def process_report_batches(reports):
    # Process reports in batches and send to BunkerNet API.
    # Args: reports (list of reports to process)
    # Returns: list of remaining unsent reports
    remaining = len(reports)
    force_send = should_force_send({"created": datetime.now().isoformat()})
    
    if force_send:
        LOGGER.info(
            "Forcing send of cached reports as they are older than 24 hours"
        )

    # Process reports in batches of 100
    while force_send or remaining >= BATCH_SIZE:
        force_send = False

        batch, reports = reports[:BATCH_SIZE], reports[BATCH_SIZE:]

        debug_log(LOGGER, f"Processing batch of {len(batch)} reports")

        LOGGER.info(
            f"Sending {len(batch)} / {remaining} reports to BunkerNet API ..."
        )
        ok, status, data = send_reports(batch)

        if not ok or status in (429, 403):
            reports = batch + reports  # Add batch back to reports
            remaining = len(reports)

            if not ok:
                LOGGER.error(
                    f"Error while sending data to BunkerNet API: {data}"
                )
            elif status == 429:
                LOGGER.warning(
                    "BunkerNet API rate limit reached, will retry later"
                )
            else:  # status == 403
                LOGGER.warning(
                    "BunkerNet instance banned, will retry later"
                )
            break

        remaining = len(reports)

        if remaining >= BATCH_SIZE:
            debug_log(LOGGER, "Sleeping 2 seconds before next batch...")
            LOGGER.info("Sleeping 2 seconds before next batch...")
            sleep(2)
    
    return reports


def cache_remaining_reports(job, reports, cached_data):
    # Cache any remaining unsent reports.
    # Args: job (Job instance), reports (list of unsent reports), 
    # cached_data (original cached data structure)
    # Returns: int exit status (0 for success, 2 for error)
    if reports:
        remaining_count = len(reports)
        LOGGER.info(f"Caching {remaining_count} reports...")
        
        debug_log(LOGGER, f"Caching {remaining_count} remaining reports")
        
        cached_data["reports"] = reports

        # Cache the remaining reports
        cached, err = job.cache_file(
            "reports.json", 
            dumps(cached_data, indent=2).encode()
        )
        if not cached:
            LOGGER.error(f"Failed to cache reports.json :\n{err}")
            return 2
    else:
        debug_log(LOGGER, "No reports to cache, deleting cache file")
        
        deleted, err = job.del_cache("reports.json")
        if not deleted:
            LOGGER.warning(f"Couldn't delete reports.json from cache : {err}")
    
    return 0


try:
    if not check_bunkernet_activation():
        LOGGER.info("BunkerNet is not activated, skipping download...")
        sys_exit(0)

    # Create directory if it doesn't exist
    bunkernet_path = Path(sep, "var", "cache", "bunkerweb", "bunkernet")
    bunkernet_path.mkdir(parents=True, exist_ok=True)

    debug_log(LOGGER, f"BunkerNet cache directory: {bunkernet_path}")

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
        LOGGER.warning(
            "Not sending BunkerNet data because instance is not registered"
        )
        sys_exit(2)

    # Create API instances for each database instance
    apis = [
        API(
            f"http://{instance['hostname']}:{instance['port']}", 
            instance["server_name"]
        ) 
        for instance in JOB.db.get_instances()
    ]

    debug_log(LOGGER, f"Created {len(apis)} API instances")

    apiCaller = ApiCaller(apis)

    # Get reports from all instances
    instance_reports = get_instance_reports(apiCaller)
    cached_data = get_cached_reports(JOB)
    reports = merge_and_sort_reports(cached_data, instance_reports)

    # Process reports in batches
    reports = process_report_batches(reports)
    
    # Cache any remaining reports
    cache_status = cache_remaining_reports(JOB, reports, cached_data)
    if cache_status != 0:
        exit_status = cache_status

except SystemExit as e:
    exit_status = e.code
except BaseException as e:
    exit_status = 2
    debug_log(LOGGER, format_exc())
    LOGGER.error(f"Exception while running bunkernet-send.py :\n{e}")

sys_exit(exit_status)