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
    title="backup-restore",
    log_file_path="/var/log/bunkerweb/backup.log"
)

logger.debug("Debug mode enabled for backup")

from backup import acquire_db_lock, backup_database, BACKUP_DIR, DB_LOCK_FILE, restore_database

status = 0

try:
    logger.debug("Acquiring database lock")
    acquire_db_lock()

    # Global parser
    parser = ArgumentParser(description="BunkerWeb's backup plugin restore command line interface")

    backups = sorted(BACKUP_DIR.glob("*.zip"), reverse=True)
    backup_file = backups[0] if backups else None
    logger.debug(f"Found {len(backups)} backup files, latest: {backup_file}")

    # Optional backup file argument
    parser.add_argument("backup_file", nargs="?", const="default_value", default=backup_file, type=str, help="backup file to restore (default : latest backup)")

    # Parse args
    args = parser.parse_args()
    logger.debug(f"Command line arguments parsed: {args}")

    backup_file = Path(args.backup_file) if args.backup_file else None
    if not backup_file:
        if backup_file == BACKUP_DIR and not BACKUP_DIR.is_dir():
            logger.error(f"Backup directory {BACKUP_DIR} does not exist, aborting restore")
            sys_exit(1)

        if not backups:
            logger.error(f"No backup found in {BACKUP_DIR}, aborting restore")
            sys_exit(1)

    if not backup_file:
        logger.error("No backup file to restore, aborting restore")
        sys_exit(1)

    if not backup_file.is_file():
        logger.error(f"Backup file {backup_file} does not exist, aborting restore")
        sys_exit(1)

    logger.debug(f"Selected backup file for restore: {backup_file}")

    logger.info("Backing up the current database before restoring the backup ...")
    current_time = datetime.now().astimezone()
    tmp_backup_dir = Path(sep, "tmp", "bunkerweb", "backups")
    tmp_backup_dir.mkdir(parents=True, exist_ok=True)
    logger.debug(f"Temporary backup directory: {tmp_backup_dir}")
    
    db = backup_database(current_time, backup_dir=tmp_backup_dir)

    logger.info(f"Restoring backup {backup_file} ...")
    restore_database(backup_file, db)
    
except SystemExit as se:
    status = se.code
    logger.debug(f"SystemExit with code: {status}")
except BaseException as e:
    logger.exception("Exception while executing backup restore command")
    status = 1
finally:
    logger.debug("Releasing database lock")
    DB_LOCK_FILE.unlink(missing_ok=True)

logger.debug(f"Exiting with status: {status}")
sys_exit(status)
