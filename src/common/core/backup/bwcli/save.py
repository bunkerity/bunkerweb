#!/usr/bin/env python3

from argparse import ArgumentParser
from datetime import datetime
from os import sep
from os.path import join
from pathlib import Path
from sys import exit as sys_exit, path as sys_path

# Add BunkerWeb dependency paths to Python path for module imports
for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) 
                  for paths in (("deps", "python"), ("utils",), ("api",), 
                               ("db",), ("core", "backup"))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from bw_logger import setup_logger

# Initialize bw_logger module
logger = setup_logger(
    title="backup-save",
    log_file_path="/var/log/bunkerweb/backup.log"
)

logger.debug("Debug mode enabled for backup")

from backup import acquire_db_lock, backup_database, BACKUP_DIR, DB_LOCK_FILE, update_cache_file

status = 0

try:
    logger.debug("Acquiring database lock")
    acquire_db_lock()

    # Global parser
    parser = ArgumentParser(description="BunkerWeb's backup plugin save command line interface")

    # Optional directory argument
    parser.add_argument(
        "-d",
        "--directory",
        default=BACKUP_DIR,
        type=str,
        help="directory where to save the backup, default is the one defined in the setting BACKUP_DIRECTORY",
    )

    # Parse args
    args = parser.parse_args()
    logger.debug(f"Command line arguments parsed: {args}")

    directory = Path(args.directory)

    logger.debug(f"Backup directory: {directory}")

    if not directory.is_dir():
        if directory == BACKUP_DIR:
            logger.error(f"Backup directory {directory} does not exist")
            sys_exit(1)

        logger.info(f"Creating directory {directory} as it does not exist")
        directory.mkdir(parents=True, exist_ok=True)

    logger.debug("Starting backup database operation")
    db = backup_database(datetime.now().astimezone(), backup_dir=directory)

    if directory == BACKUP_DIR:
        logger.debug("Updating cache file for default backup directory")
        update_cache_file(db, directory)
        
except SystemExit as se:
    status = se.code
    logger.debug(f"SystemExit with code: {status}")
except BaseException as e:
    logger.exception("Exception while executing backup save command")
    status = 1
finally:
    logger.debug("Releasing database lock")
    DB_LOCK_FILE.unlink(missing_ok=True)

logger.debug(f"Exiting with status: {status}")
sys_exit(status)
