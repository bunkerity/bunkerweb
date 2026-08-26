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
from backup import backup_database, update_cache_file, acquire_db_lock, ensure_backup_dir, rotate_backups, sorted_backups, DB_LOCK_FILE

LOGGER = getLogger("BACKUP")
status = 0

try:
    # Prevent concurrent DB access with other backup plugins
    acquire_db_lock()
    backup_dir = ensure_backup_dir(Path(getenv("BACKUP_DIRECTORY", "/var/lib/bunkerweb/backups")))

    # A run killed mid-archive leaves the partial file `backup_database` was building. It is
    # inert -- no `backup-*.zip` glob matches it -- but nothing else ever removes it, so sweep
    # it here rather than letting half-written database dumps accumulate on disk forever.
    for stale in backup_dir.glob("backup-*.zip.tmp"):
        LOGGER.warning(f"Removing leftover partial backup {stale.name} from an interrupted run ...")
        stale.unlink(missing_ok=True)

    force_backup = getenv("FORCE_BACKUP", "no") == "yes"
    current_time = datetime.now().astimezone()

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

        backup_period = getenv("BACKUP_SCHEDULE", "daily")
        PERIOD_STAMPS = {
            "daily": timedelta(days=1).total_seconds(),
            "weekly": timedelta(weeks=1).total_seconds(),
            "monthly": timedelta(weeks=4).total_seconds(),
        }

        already_done = last_backup_date and last_backup_date.timestamp() + PERIOD_STAMPS[backup_period] > current_time.timestamp()
        backup_rotation = int(getenv("BACKUP_ROTATION", "7"))
        backup_strategy = getenv("BACKUP_ROTATION_STRATEGY", "hanoi")

        sorted_files = []
        if already_done:
            # Oldest first: the engine name precedes the timestamp, so plain name order is
            # per-engine order (see backup.sorted_backups).
            sorted_files = sorted_backups(backup_dir)

        if len(sorted_files) <= backup_rotation and already_done:
            LOGGER.info(f"Backup already done within the last {backup_period} period, skipping backup ...")
            sys_exit(0)

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

        db, _ = backup_database(current_time, db, backup_dir)
        backed_up = True

        if not force_backup:
            sorted_files = sorted_backups(backup_dir)

    if not force_backup:
        # Both strategies drop the same number of files (len - rotation); `hanoi` only chooses
        # differently among them, so it can never delete more than `fifo` would.
        rotate_backups(sorted_files, backup_rotation, backup_strategy, timedelta(seconds=PERIOD_STAMPS[backup_period]))

        if backed_up:
            update_cache_file(db, backup_dir)
except SystemExit as e:
    status = e.code
except BaseException as e:
    status = 2
    LOGGER.debug(format_exc())
    LOGGER.error(f"Exception while running backup-data.py :\n{e}")

finally:
    # Always release DB lock
    DB_LOCK_FILE.unlink(missing_ok=True)

sys_exit(status)
