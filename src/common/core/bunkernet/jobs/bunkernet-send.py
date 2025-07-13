#!/usr/bin/env python3

from datetime import datetime, timedelta
from itertools import chain
from json import dumps, loads
from os import getenv, sep
from os.path import join
from pathlib import Path
from sys import exit as sys_exit, path as sys_path
from time import sleep

# Add BunkerWeb dependency paths to Python path for module imports
for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) 
                  for paths in (("deps", "python"), ("utils",), ("api",), 
                               ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from bw_logger import setup_logger

# Initialize bw_logger module
logger = setup_logger(
    title="bunkernet-send",
    log_file_path="/var/log/bunkerweb/bunkernet.log"
)

logger.debug("Debug mode enabled for bunkernet")

from bunkernet import send_reports
from heapq import merge

from API import API  # type: ignore
from ApiCaller import ApiCaller  # type: ignore
from jobs import Job  # type: ignore

exit_status = 0

BATCH_SIZE = 100

try:
    logger.debug("Starting bunkernet send process")
    
    # Check if at least a server has BunkerNet activated
    bunkernet_activated = False
    logger.debug("Checking bunkernet activation status")
    
    # Multisite case
    if getenv("MULTISITE", "no") == "yes":
        logger.debug("Processing multisite configuration")
        servers = getenv("SERVER_NAME", "www.example.com").split(" ")
        logger.debug(f"Checking {len(servers)} servers for bunkernet activation")
        
        for first_server in servers:
            if getenv(f"{first_server}_USE_BUNKERNET", "yes") == "yes":
                bunkernet_activated = True
                logger.debug(f"Bunkernet activated for server: {first_server}")
                break
    # Singlesite case
    elif getenv("USE_BUNKERNET", "yes") == "yes":
        logger.debug("Bunkernet activated for singlesite")
        bunkernet_activated = True

    if not bunkernet_activated:
        logger.info("BunkerNet is not activated, skipping download...")
        sys_exit(0)

    # Create directory if it doesn't exist
    bunkernet_path = Path(sep, "var", "cache", "bunkerweb", "bunkernet")
    bunkernet_path.mkdir(parents=True, exist_ok=True)
    logger.debug(f"Bunkernet cache directory: {bunkernet_path}")

    logger.debug("Creating Job instance")
    JOB = Job(logger, __file__)

    db_metadata = JOB.db.get_metadata()
    logger.debug(f"Database metadata: {type(db_metadata)}")

    if isinstance(db_metadata, str) or db_metadata["scheduler_first_start"]:
        logger.info("First start of the scheduler, skipping send...")
        sys_exit(0)

    # Get ID from cache
    bunkernet_id = None
    logger.debug("Retrieving bunkernet ID from cache")
    bunkernet_id = JOB.get_cache("instance.id")
    if bunkernet_id:
        bunkernet_path.joinpath("instance.id").write_bytes(bunkernet_id)
        logger.info("Successfully retrieved BunkerNet ID from db cache")
        logger.debug(f"Bunkernet ID length: {len(bunkernet_id)} bytes")
    else:
        logger.info("No BunkerNet ID found in db cache")

    # Check if ID is present
    id_file = bunkernet_path.joinpath("instance.id")
    if not id_file.is_file():
        logger.warning("Not sending BunkerNet data because instance is not registered")
        sys_exit(2)

    logger.debug("Creating API instances for database instances")
    # Create API instances for each database instance
    instances = JOB.db.get_instances()
    logger.debug(f"Found {len(instances)} database instances")
    
    apis = [API(f"http://{instance['hostname']}:{instance['port']}", instance["server_name"]) for instance in instances]
    logger.debug(f"Created {len(apis)} API instances")

    apiCaller = ApiCaller(apis)

    # Get reports from all instances
    logger.debug("Requesting reports from all instances")
    resp, instances_data = apiCaller.send_to_apis("GET", "/bunkernet/reports", response=True)
    logger.debug(f"API call response: {resp}, instances data keys: {list(instances_data.keys()) if instances_data else 'none'}")

    instance_reports = []
    if resp:
        # Extract and sort requests using chain to flatten the nested lists
        successful_instances = [data for data in instances_data.values() if data.get("status", "ko") == "success"]
        logger.debug(f"Found {len(successful_instances)} successful instance responses")
        
        instance_reports = list(chain.from_iterable((data.get("msg", []) for data in successful_instances)))
        logger.debug(f"Extracted {len(instance_reports)} reports from instances")

    logger.debug("Loading cached reports")
    cached_data = loads(JOB.get_cache("reports.json") or "{}")

    if not cached_data:
        cached_data = {"created": datetime.now().astimezone().isoformat(), "reports": []}
        logger.debug("Created new cached data structure")
    else:
        logger.debug(f"Loaded cached data with {len(cached_data.get('reports', []))} existing reports")

    # Merge reports and sort by the oldest first using heapq merge
    logger.debug("Merging and sorting reports")
    reports = list(merge(cached_data.get("reports", []), instance_reports, key=lambda x: datetime.fromisoformat(x["date"])))
    logger.debug(f"Total reports after merge: {len(reports)}")

    # Check if forced send is needed due to time
    cache_created = datetime.fromisoformat(cached_data["created"])
    force_send = cache_created + timedelta(hours=24) < datetime.now().astimezone()
    logger.debug(f"Cache created: {cache_created}, force_send: {force_send}")

    if force_send:
        logger.info("Forcing send of cached reports as they are older than 24 hours")

    # Process reports in batches of 100
    remaining = len(reports)
    batch_count = 0
    logger.debug(f"Starting batch processing with {remaining} total reports")
    
    while force_send or remaining >= BATCH_SIZE:
        force_send = False
        batch_count += 1

        batch, reports = reports[:BATCH_SIZE], reports[BATCH_SIZE:]
        logger.debug(f"Processing batch {batch_count}: {len(batch)} reports")

        logger.info(f"Sending {len(batch)} / {remaining} reports to BunkerNet API ...")
        ok, status, data = send_reports(batch)
        logger.debug(f"Send result: ok={ok}, status={status}")

        if not ok or status in (429, 403):
            reports = batch + reports  # Add batch back to reports
            remaining = len(reports)
            logger.debug(f"Re-added batch to reports, total now: {remaining}")

            if not ok:
                logger.error(f"Error while sending data to BunkerNet API: {data}")
            elif status == 429:
                logger.warning("BunkerNet API rate limit reached, will retry later")
            else:  # status == 403
                logger.warning("BunkerNet instance banned, will retry later")
            break

        remaining = len(reports)
        logger.debug(f"Batch sent successfully, remaining reports: {remaining}")

        if remaining >= BATCH_SIZE:
            logger.info("Sleeping 2 seconds before next batch...")
            sleep(2)

    if reports:
        logger.info(f"Caching {remaining} reports...")
        cached_data["reports"] = reports

        # Cache the remaining reports
        logger.debug("Caching remaining reports to file")
        cached, err = JOB.cache_file("reports.json", dumps(cached_data, indent=2).encode())
        if not cached:
            logger.error(f"Failed to cache reports.json :\n{err}")
            exit_status = 2
        else:
            logger.debug("Successfully cached remaining reports")
    else:
        logger.debug("No reports remaining, deleting cache file")
        deleted, err = JOB.del_cache("reports.json")
        if not deleted:
            logger.warning(f"Couldn't delete reports.json from cache : {err}")
        else:
            logger.debug("Successfully deleted empty reports cache")
            
    logger.debug(f"Bunkernet send process completed with {batch_count} batches processed")
    
except SystemExit as e:
    exit_status = e.code
    logger.debug(f"SystemExit with code: {exit_status}")
except BaseException as e:
    exit_status = 2
    logger.exception("Exception while running bunkernet-send.py")

logger.debug(f"Exiting with status: {exit_status}")
sys_exit(exit_status)
