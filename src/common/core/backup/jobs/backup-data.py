#!/usr/bin/env python3

from datetime import datetime, timedelta
from json import loads
from os import getenv, sep
from os.path import join
from pathlib import Path
from sys import exit as sys_exit, path as sys_path
from traceback import format_exc

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("db",), ("core", "backup"))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from Database import Database  # type: ignore
from logger import getLogger  # type: ignore
from jobs import Job  # type: ignore
from backup import backup_database, hanoi_rotation, update_cache_file, acquire_db_lock, is_sqlite_wal, DB_LOCK_FILE

LOGGER = getLogger("BACKUP")
status = 0
lock_acquired = False  # Track whether this process holds the DB lock

try:
    backup_dir = Path(getenv("BACKUP_DIRECTORY", "/var/lib/bunkerweb/backups"))
    backup_dir.mkdir(parents=True, exist_ok=True)

    force_backup = getenv("FORCE_BACKUP", "no") == "yes"
    current_time = datetime.now().astimezone()
    LOGGER.debug(f"Backup directory: {backup_dir}, force_backup={force_backup}, current_time={current_time.isoformat()}")

    if not force_backup:
        # Check if backup is activated
        if getenv("USE_BACKUP", "yes") == "no":
            LOGGER.info("Backup feature is disabled, skipping backup ...")
            sys_exit(0)

        JOB = Job(LOGGER, __file__)

        last_backup = loads(JOB.get_cache("backup.json") or "{}")
        last_backup_date = last_backup.get("date", None)
        if last_backup_date:
            last_backup_date = datetime.fromisoformat(last_backup_date).astimezone()
        LOGGER.debug(f"Last backup date: {last_backup_date.isoformat() if last_backup_date else 'none'}")

        backup_period = getenv("BACKUP_SCHEDULE", "daily")
        PERIOD_STAMPS = {
            "hanoi":   timedelta(hours=1).total_seconds(),
            "daily":   timedelta(days=1).total_seconds(),
            "weekly":  timedelta(weeks=1).total_seconds(),
            "monthly": timedelta(weeks=4).total_seconds(),
        }

        period_seconds = PERIOD_STAMPS.get(backup_period, PERIOD_STAMPS["daily"])
        already_done = last_backup_date and last_backup_date.timestamp() + period_seconds > current_time.timestamp()
        backup_rotation = int(getenv("BACKUP_ROTATION", "7"))
        LOGGER.debug(f"Schedule: {backup_period}, period: {period_seconds}s, already_done={already_done}, rotation={backup_rotation}")

        sorted_files = []
        if already_done:

            # Get all backup files in the directory
            backup_files = backup_dir.glob("backup-*.zip")

            # Sort the backup files by name
            sorted_files = sorted(backup_files)
            LOGGER.debug(f"Existing backup files ({len(sorted_files)}): {[f.name for f in sorted_files]}")

        if already_done:
            if backup_period == "hanoi" or len(sorted_files) <= backup_rotation:
                LOGGER.info(f"Backup already done within the last {backup_period} period, skipping backup ...")
                sys_exit(0)

    if not force_backup:
        db = JOB.db
    else:
        db = Database(LOGGER, sqlalchemy_string=getenv("DATABASE_URI"))

    backed_up = False
    if force_backup or not already_done:
        if not force_backup:
            db_metadata = db.get_metadata()

            if isinstance(db_metadata, str) or db_metadata["scheduler_first_start"]:
                LOGGER.info("First start of the scheduler, skipping backup ...")
                sys_exit(0)

        if is_sqlite_wal(db):
            LOGGER.info("SQLite WAL mode detected — SQLite readers/writers won't block, but the BunkerWeb lock is still acquired to prevent concurrent backup/restore operations.")

        # Acquire the lock only when a backup will actually run.
        # Placing it here (rather than at script start) means that
        # rotation-only runs and already_done early exits never touch
        # the lock file. The post_dump_hook releases the lock after the
        # SQL dump but before compression, keeping the hold time minimal.
        LOGGER.debug("Acquiring database lock ...")
        acquire_db_lock()
        lock_acquired = True
        LOGGER.debug("Database lock acquired.")
        LOGGER.debug("Starting database dump ...")
        db, _ = backup_database(current_time, db, backup_dir, post_dump_hook=lambda: DB_LOCK_FILE.unlink(missing_ok=True))
        backed_up = True
        LOGGER.debug("Database dump and compression complete.")

        if not force_backup:
            # Get all backup files in the directory
            backup_files = backup_dir.glob("backup-*.zip")

            # Sort the backup files by name
            sorted_files = sorted(backup_files)
            LOGGER.debug(f"Backup files after dump ({len(sorted_files)}): {[f.name for f in sorted_files]}")

    if not force_backup:
        if backup_period == "hanoi":
            backup_directory = Path(getenv("BACKUP_DIRECTORY", "/var/lib/bunkerweb/backups"))
            all_files = sorted(backup_directory.glob("backup-*.zip"))
            to_delete = hanoi_rotation(all_files, current_time)
            LOGGER.debug(f"Hanoi rotation: {len(all_files)} files total, {len(to_delete)} to delete, {len(all_files) - len(to_delete)} to keep.")
            for file in to_delete:
                LOGGER.warning(f"Removing old backup file: {file.name} (Towers of Hanoi rotation).")
                file.unlink()
        elif len(sorted_files) > backup_rotation:
            # Calculate the number of files to remove
            num_files_to_remove = len(sorted_files) - backup_rotation
            LOGGER.debug(f"Rotation: removing {num_files_to_remove} file(s) to stay within limit of {backup_rotation}.")

            # Remove the oldest backup files
            for file in sorted_files[:num_files_to_remove]:
                LOGGER.warning(f"Removing old backup file: {file}, as the rotation limit has been reached ...")
                file.unlink()

        if backed_up:
            update_cache_file(db, backup_dir)
except SystemExit as e:
    status = e.code
except BaseException as e:
    status = 2
    LOGGER.debug(format_exc())
    LOGGER.error(f"Exception while running backup-data.py :\n{e}")

finally:
    # Only release the lock if this process acquired it (WAL mode skips the lock entirely).
    if lock_acquired:
        DB_LOCK_FILE.unlink(missing_ok=True)

sys_exit(status)
