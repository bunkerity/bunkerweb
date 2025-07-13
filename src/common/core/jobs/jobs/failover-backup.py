#!/usr/bin/env python3

from os import sep
from os.path import join
from sys import exit as sys_exit, path as sys_path

# Add BunkerWeb dependency paths to Python path for module imports
for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) 
                  for paths in (("deps", "python"), ("utils",), ("api",), 
                               ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from bw_logger import setup_logger

# Initialize bw_logger module
logger = setup_logger(
    title="jobs-failover-backup",
    log_file_path="/var/log/bunkerweb/jobs.log"
)

logger.debug("Debug mode enabled for jobs-failover-backup")

from jobs import Job  # type: ignore

status = 0

try:
    logger.debug("Starting failover backup process")
    
    # Restoring the backup failover configuration
    logger.debug("Creating Job instance for failover backup")
    JOB = Job(logger, __file__)
    logger.debug("Job instance created successfully")
    
    logger.debug("Failover backup process completed successfully")
    
except BaseException as e:
    status = 2
    logger.exception("Exception while running failover-backup.py")

logger.debug(f"Exiting with status: {status}")
sys_exit(status)
