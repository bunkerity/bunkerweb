#!/usr/bin/env python3

from datetime import datetime
from os import sep
from os.path import join
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
    title="backup",
    log_file_path="/var/log/bunkerweb/backup.log"
)

logger.debug("Debug mode enabled for backup")

from backup import BACKUP_DIR

try:
    logger.debug(f"Scanning backup directory: {BACKUP_DIR}")
    
    # Check if backup directory exists
    if not BACKUP_DIR.exists():
        logger.debug(f"Backup directory does not exist: {BACKUP_DIR}")
        logger.info(f"No backup found in {BACKUP_DIR}")
        sys_exit(0)
    
    logger.debug(f"Backup directory exists and is accessible")
    backups = sorted(BACKUP_DIR.glob("*.zip"), reverse=True)
    logger.debug(f"Found {len(backups)} backup files")
    
    message = ""
    if backups:
        logger.debug("Processing backup files for display")
        message = f"Found {len(backups)} backup{'s' if len(backups) > 1 else ''} in {BACKUP_DIR} :"
        # Show a table with the backups details
        message += "\n+------------+--------------------------+"
        message += "\n|  Database  |           Date           |"
        message += "\n+------------+--------------------------+"
        for backup in backups:
            database = backup.name.split("-")[1]
            date = datetime.strptime("-".join(backup.stem.split("-")[2:]), "%Y-%m-%d_%H-%M-%S").astimezone()
            message += f"\n| {database:<10} | {date.strftime('%Y/%m/%d %H:%M:%S %Z'):<24} |"
            logger.debug(f"Processed backup: {backup.name} - {database} - {date}")
        message += "\n+------------+--------------------------+"
        logger.debug("Backup table formatting completed")
    else:
        message = f"No backup found in {BACKUP_DIR}"
        logger.debug("No backup files found to display")
    logger.info(message)
    logger.debug("Backup list command completed successfully")
except SystemExit as se:
    logger.debug(f"SystemExit with code: {se.code}")
    sys_exit(se.code)
except BaseException as e:
    logger.exception("Exception while executing backup list command")
    sys_exit(1)
