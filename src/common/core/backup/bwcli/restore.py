#!/usr/bin/env python3

from argparse import ArgumentParser
from datetime import datetime
from os.path import join, sep
from pathlib import Path
from sys import exit as sys_exit, path as sys_path

deps_path = join(sep, "usr", "share", "bunkerweb", "core", "backup")
if deps_path not in sys_path:
    sys_path.append(deps_path)

from backup import acquire_db_lock, backup_database, BACKUP_DIR, DB_LOCK_FILE, LOGGER, restore_database

status = 0

try:
    acquire_db_lock()

    # Global parser
    parser = ArgumentParser(description="BunkerWeb's backup plugin restore command line interface")

    backups = sorted(BACKUP_DIR.glob("*.zip"), reverse=True)
    backup_file = backups[0] if backups else None

    # Optional backup file argument
    parser.add_argument("backup_file", nargs="?", const="default_value", default=backup_file, type=str, help="backup file to restore (default : latest backup)")

    # Parse args
    args = parser.parse_args()

    backup_file = Path(args.backup_file) if args.backup_file else None
    if not backup_file:
        if backup_file == BACKUP_DIR and not BACKUP_DIR.is_dir():
            LOGGER.error(f"Backup directory {BACKUP_DIR} does not exist, aborting restore")
            sys_exit(1)

        if not backups:
            LOGGER.error(f"No backup found in {BACKUP_DIR}, aborting restore")
            sys_exit(1)

    if not backup_file:
        LOGGER.error("No backup file to restore, aborting restore")
        sys_exit(1)

    if not backup_file.is_file():
        LOGGER.error(f"Backup file {backup_file} does not exist, aborting restore")
        sys_exit(1)

    LOGGER.info("Backing up the current database before restoring the backup ...")
    current_time = datetime.now().astimezone()
    tmp_backup_dir = Path(sep, "tmp", "bunkerweb", "backups")
    tmp_backup_dir.mkdir(parents=True, exist_ok=True)
    db, _ = backup_database(current_time, backup_dir=tmp_backup_dir)

    LOGGER.info(f"Restoring backup {backup_file} ...")
    restore_database(backup_file, db)
except SystemExit as se:
    status = se.code
except BaseException as e:
    LOGGER.error(f"Error while executing backup restore command: {e}")
    status = 1
finally:
    DB_LOCK_FILE.unlink(missing_ok=True)

sys_exit(status)
