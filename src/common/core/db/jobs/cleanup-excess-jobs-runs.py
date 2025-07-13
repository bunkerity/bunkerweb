#!/usr/bin/env python3

from os import getenv, sep
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
    title="cleanup-excess-jobs-runs",
    log_file_path="/var/log/bunkerweb/cleanup-excess-jobs-runs.log"
)

logger.debug("Debug mode enabled for cleanup-excess-jobs-runs")

from Database import Database  # type: ignore

status = 0

try:
    logger.debug("Starting database cleanup for excess job runs")
    
    # Get configuration values
    database_uri = getenv("DATABASE_URI")
    max_jobs_runs = int(getenv("DATABASE_MAX_JOBS_RUNS", "10000"))
    logger.debug(f"Database URI set: {database_uri is not None}")
    logger.debug(f"Max job runs configured: {max_jobs_runs}")
    
    # Initialize database connection
    logger.debug("Creating database connection")
    DB = Database(logger, sqlalchemy_string=database_uri)
    
    # Perform cleanup operation
    logger.debug(f"Starting cleanup of excess job runs (keeping max {max_jobs_runs})")
    ret = DB.cleanup_jobs_runs_excess(max_jobs_runs)
    logger.debug(f"Cleanup operation result: {ret}")
    
    if not ret.startswith("Removed"):
        logger.error(ret)
        sys_exit(1)
    logger.info(ret)
    logger.debug("Database cleanup completed successfully")
    
except SystemExit as e:
    status = e.code
    logger.debug(f"SystemExit with code: {status}")
except BaseException as e:
    status = 2
    logger.exception("Exception while running cleanup-excess-jobs-runs.py")

logger.debug(f"Exiting with status: {status}")
sys_exit(status)
