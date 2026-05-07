#!/usr/bin/env python3

from argparse import ArgumentParser
from datetime import datetime
from os.path import join, sep
from pathlib import Path
from sys import exit as sys_exit, path as sys_path

deps_path = join(sep, "usr", "share", "bunkerweb", "core", "backup")
if deps_path not in sys_path:
    sys_path.append(deps_path)

from backup import acquire_db_lock, backup_database, BACKUP_DIR, DB_LOCK_FILE, is_sqlite_wal, LOGGER, update_cache_file
from Database import Database  # type: ignore  # path added by backup module import

status = 0
lock_acquired = False

try:
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

    directory = Path(args.directory)

    LOGGER.debug(f"Backup directory: {directory}")

    if not directory.is_dir():
        if directory == BACKUP_DIR:
            LOGGER.error(f"Backup directory {directory} does not exist")
            sys_exit(1)

        LOGGER.info(f"Creating directory {directory} as it does not exist")
        directory.mkdir(parents=True, exist_ok=True)

    db = Database(LOGGER)

    if is_sqlite_wal(db):
        LOGGER.info("SQLite WAL mode detected — SQLite readers/writers won't block, but the BunkerWeb lock is still acquired to prevent concurrent backup/restore operations.")

    acquire_db_lock()
    lock_acquired = True
    db, _ = backup_database(datetime.now().astimezone(), db=db, backup_dir=directory, post_dump_hook=lambda: DB_LOCK_FILE.unlink(missing_ok=True))

    if directory == BACKUP_DIR:
        update_cache_file(db, directory)
except SystemExit as se:
    status = se.code
except BaseException as e:
    LOGGER.error(f"Error while executing backup save command: {e}")
    status = 1
finally:
    if lock_acquired:
        DB_LOCK_FILE.unlink(missing_ok=True)

sys_exit(status)
