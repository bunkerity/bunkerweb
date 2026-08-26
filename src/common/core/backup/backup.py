#!/usr/bin/env python3

from datetime import datetime, timedelta
import re
from json import dumps, loads
from os import O_DIRECTORY, O_NOFOLLOW, O_RDONLY, close as os_close, fchown, fstat, geteuid, getenv, open as os_open, replace, stat as os_stat
from os.path import join, sep
from pathlib import Path
from subprocess import PIPE, run
from shutil import which
from sys import exit as sys_exit, path as sys_path
from time import sleep
from typing import Literal
from zipfile import ZIP_DEFLATED, ZipFile

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from sqlalchemy.engine.url import make_url

from common_utils import bytes_hash, safe_zip_extractall  # type: ignore
from Database import Database  # type: ignore
from logger import getLogger  # type: ignore
from model import Base  # type: ignore

LOGGER = getLogger("BACKUP")

BACKUP_DIR = Path(getenv("BACKUP_DIRECTORY", "/var/lib/bunkerweb/backups"))
STAMP_RE = re.compile(r"(\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2})")
STAMP_FORMAT = "%Y-%m-%d_%H-%M-%S"
DB_LOCK_FILE = Path(sep, "var", "lib", "bunkerweb", "db.lock")


def ensure_backup_dir(directory: Path = BACKUP_DIR) -> Path:
    """Create the backup directory and keep it owned by the user the product runs as.

    `bwcli plugin backup save` runs as root on a package install, the worker that rotates runs
    as nginx, and whoever creates this directory first owns it. A root-created one is readable
    but not writable by the worker, and unlinking a file needs write+execute on the DIRECTORY --
    so rotation died on `PermissionError: [Errno 13] ... backup-*.zip`, the backup count grew
    past BACKUP_ROTATION forever, and the only record of why sat in the worker journal.

    The reference owner is the product's state directory (`DB_LOCK_FILE.parent`,
    /var/lib/bunkerweb, which `src/linux/scripts/postinstall.sh` chowns to nginx), NOT the
    backup directory's own parent: a custom BACKUP_DIRECTORY under a root-owned parent would
    otherwise be aligned to root, which is the very bug this function exists to prevent.

    Everything after the mkdir is fd-bound, and that is a security requirement rather than a
    style choice. This runs as ROOT and nginx owns the parent, so nginx -- the uid the API, the
    UI, the worker and the Lua runtime all run as -- can replace `backups` with a symlink.
    `Path.mkdir(exist_ok=True)` does not raise on a symlink-to-directory, and `Path.stat()` and
    `os.chown()` both follow it, so a path-based chown here hands a compromised nginx the
    ownership of any directory it can name -- `/etc`, and from there `/etc/ld.so.preload`. An
    `is_symlink()` pre-check does not close it either; the swap can happen between the check and
    the chown. `O_NOFOLLOW` refuses a symlinked final component outright and `fchown` acts on
    the object the descriptor already holds, so there is no window and no second lookup.
    `lchown` is NOT the fix: it would chown the link and leave rotation broken.

    A refused or impossible chown is a warning, not a failure -- the caller needs the directory,
    and a backup that cannot rotate still beats no backup. The archives themselves may stay
    root-owned; nothing needs to open them for writing.
    """
    directory.mkdir(parents=True, exist_ok=True)
    if geteuid() != 0:
        return directory
    reference = DB_LOCK_FILE.parent
    try:
        owner = os_stat(reference)
        fd = os_open(directory, O_RDONLY | O_NOFOLLOW | O_DIRECTORY)
        try:
            current = fstat(fd)
            if (current.st_uid, current.st_gid) != (owner.st_uid, owner.st_gid):
                fchown(fd, owner.st_uid, owner.st_gid)
        finally:
            os_close(fd)
    except OSError as e:
        LOGGER.warning(f"Could not align the ownership of {directory} with {reference}: {e}")
    return directory


def mysql_client_command(operation: Literal["dump", "restore"]) -> tuple[str, bool]:
    """Pick the client binary and report whether it is the MariaDB one.

    MySQL 9 dropped the `mysql`/`mysqldump` symlinks some images used to ship, and the MariaDB
    and MySQL clients disagree on TLS flags, so the caller needs to know which family it got.
    """
    mariadb_command = "mariadb-dump" if operation == "dump" else "mariadb"
    if which(mariadb_command):
        return mariadb_command, True
    return ("mysqldump" if operation == "dump" else "mysql"), False


def mysql_connection_args(query_args, mariadb_client: bool) -> list[str]:
    """Translate the DATABASE_URI query string into client flags.

    `query_args` values arrive as a tuple when the same key appears more than once in the URI,
    so take the last one rather than formatting the tuple into the command line.
    """
    args = []
    ssl = query_args.get("ssl")
    if isinstance(ssl, tuple):
        ssl = ssl[-1]
    ssl = str(ssl).lower() if ssl is not None else None

    if ssl == "true":
        args.append("--ssl")
    elif ssl == "false":
        args.append("--skip-ssl")
    elif mariadb_client:
        # MariaDB clients verify opportunistic TLS by default. MySQL's generated
        # certificate is self-signed, so keep encryption but skip verification
        # unless DATABASE_URI explicitly requests SSL.
        args.append("--skip-ssl-verify-server-cert")

    charset = query_args.get("charset")
    if isinstance(charset, tuple):
        charset = charset[-1]
    if charset:
        args.extend(["--default-character-set", str(charset)])
    return args


def acquire_db_lock():
    """Acquire the database lock to prevent concurrent access to the database."""
    current_time = datetime.now().astimezone()
    while DB_LOCK_FILE.is_file() and DB_LOCK_FILE.stat().st_ctime + 30 > current_time.timestamp():
        LOGGER.warning("Database is locked, waiting for it to be unlocked (timeout: 30s) ...")
        sleep(1)
    DB_LOCK_FILE.unlink(missing_ok=True)
    DB_LOCK_FILE.touch()


def sorted_backups(backup_dir: Path = BACKUP_DIR) -> list:
    """Backup archives, oldest first.

    Sorting by name looks like sorting by date because the timestamp is in the name, but the
    engine comes first: `backup-sqlite-2026-01-01_00-00-00.zip` sorts after every
    `backup-mariadb-*` whatever the dates are. A directory that saw more than one engine --
    a SQLite install migrated to MariaDB, or the backup test suite -- therefore had
    `bwcli plugin backup restore` pick the newest SQLite dump instead of the newest backup,
    and rotation delete the newest MariaDB one as if it were the oldest file.
    """

    def _key(path: Path):
        stamp = STAMP_RE.search(path.name)
        # A name without a timestamp is not ours; mtime keeps it in a sane place instead of
        # sorting every one of them together at one end.
        return stamp.group(1) if stamp else datetime.fromtimestamp(path.stat().st_mtime).strftime(STAMP_FORMAT)

    return sorted(backup_dir.glob("backup-*.zip"), key=_key)


def backup_time(backup: Path) -> datetime:
    """When a backup was taken.

    Same source of truth as `sorted_backups` -- the timestamp in the name, `mtime` for a name
    that has none -- read as a date instead of as a sort key. The stamp is written without an
    offset (`backup_database` formats a local time), so it is read back as local time, exactly
    like `bwcli plugin backup list` does.

    A stamp that MATCHES the pattern but is not a real date (`2026-02-30_00-00-00`) counts as a
    name with no timestamp, not as an error. Rotation is the only caller, and letting `strptime`
    raise here took the whole job down -- on the default FIFO path too -- which skipped
    `update_cache_file`, froze the manifest date, and left `already_done` false forever: a full
    dump on every run and rotation never running again, from one malformed file name.
    """
    stamp = STAMP_RE.search(backup.name)
    if stamp:
        try:
            return datetime.strptime(stamp.group(1), STAMP_FORMAT).astimezone()
        except ValueError:
            LOGGER.warning(f"Backup {backup.name} carries an impossible date, falling back to its modification time")
    return datetime.fromtimestamp(backup.stat().st_mtime).astimezone()


def period_index(taken: datetime, period: timedelta) -> int:
    """Which backup period a timestamp falls in -- the Hanoi session counter, derived not stored."""
    return int(taken.timestamp() // period.total_seconds())


def newest_per_period(dated_backups: list, period: timedelta) -> dict:
    """The last backup of each period, by period index.

    Two backups in one period -- a manual `bwcli plugin backup save` beside the scheduled one --
    are a single restore point as far as rotation is concerned, and the freshest of them is it.
    """
    by_period = {}
    for taken, backup in sorted(dated_backups, key=lambda dated: dated[0]):
        by_period[period_index(taken, period)] = backup
    return by_period


def hanoi_keep(dated_backups: list, rotation: int, period: timedelta) -> set:
    """The backups the Tower of Hanoi ladder protects -- never more than `rotation` of them.

    Classic Hanoi rotation is the medium reused every `2^k` sessions. The session counter is
    derived from the timestamp (`floor(taken / period)`) instead of stored, so nothing has to
    survive a restore for the ladder to keep working. Level `k` cuts the timeline into fixed
    blocks of `2^k` periods and keeps the OLDEST backup of each of its two most recent non-empty
    blocks; level 0's blocks are single periods, so it keeps the last two. The newest backup is
    pinned on top of that, which is what covers `rotation = 1`, where there are no levels at all.

    Three decisions carry this design, and each of them is the difference between an exponential
    ladder and something that only looks like one:

    * The blocks are anchored on an ABSOLUTE grid, not on windows measured back from `now`. Block
      membership is then a property of the file itself, so a backup that falls out of the ladder
      can never be wanted again and deleting it is safe forever. Windows measured from `now`
      cannot promise that -- whichever backup such a window protects, the ones that would have
      refilled it are the ones being deleted, so the deep tiers empty out and stay empty. Only
      walking a long sequence shows it (`tests/unit/backup/test_hanoi_rotation.py`).
    * A level takes a backup from each of its two most recent non-empty BLOCKS, not the backups
      whose index divides `2^k` exactly. Divisibility works only while backups are perfectly
      regular; after a scheduler outage, or in a directory of manual backups, nothing lands on a
      grid point at all and a ladder built on divisibility protects none of it.
    * It takes the OLDEST backup of the block, not the newest. The oldest of the previous block
      is at least `2^k` periods back, so level `k` is guaranteed to reach that far and the levels
      spread out exponentially. The newest of that block can be one single period back, and then
      the levels pile up on each other: measured over 2100 periods, `rotation = 12` collapses from
      a depth of 1049 periods to 26, and `rotation = 24` keeps one point at 2074 and NOTHING
      between 26 and it.

    Each level costs at most one file more than the level below it -- its newer keeper is the
    oldest backup of the current block, which is also the oldest backup of a block the level
    below already keeps -- so `2 + (levels - 1)` bounds the whole ladder. That is why `levels` is
    `rotation - 1`: it is exactly what the operator's file budget pays for.
    """
    by_period = newest_per_period(dated_backups, period)
    if not by_period:
        return set()

    indices = sorted(by_period)
    kept = {by_period[indices[-1]]}
    for level in range(max(0, rotation - 1)):
        block_size = 1 << level
        oldest_of_block = {}
        for index in indices:
            oldest_of_block.setdefault(index // block_size, index)
        kept.update(by_period[oldest_of_block[block]] for block in sorted(oldest_of_block)[-2:])
    return kept


def hanoi_rank(index: int, indices: list, levels: int) -> tuple:
    """How close a period came to the ladder: `(level, blocks behind the newest)`, its best.

    A block 0 or 1 behind the newest is a block the ladder keeps, so a victim's best rank is 2 or
    more -- and which level it came closest on is the one thing that tells an operator whether a
    file was one backup away from being kept or nowhere near it.
    """
    best = (0, len(indices))
    for level in range(max(1, levels)):
        block_size = 1 << level
        blocks = sorted({other // block_size for other in indices}, reverse=True)
        rank = blocks.index(index // block_size)
        if rank < best[1]:
            best = (level, rank)
    return best


def rotation_victims(dated_backups: list, rotation: int, strategy: str = "hanoi", period: timedelta = timedelta(days=1)) -> list:
    """The backups rotation gives up, each with the reason to log.

    Pure: it reads `(taken_at, path)` pairs and nothing else -- not the current time, so a run
    delayed by hours makes exactly the same decision as one on schedule, and not the filesystem.
    Resolving a backup's date is the caller's job and `backup_time` is where a `stat()` can
    happen, for the archives whose name carries no usable timestamp.

    Both strategies give up exactly `count - rotation` files, so `hanoi` can never delete MORE
    than the FIFO rotation that shipped before it would have for the same inputs -- they differ
    only in WHICH files they pick. FIFO gives up the oldest ones. Hanoi gives up whatever its
    ladder does not need, oldest first.

    `hanoi` is the default, here and in `plugin.json`: the two defaults are deliberately the same
    value so that a caller who omits `strategy` gets the policy the product actually ships. Any
    other value -- including a typo the setting's `select` regex would have rejected -- is FIFO,
    which is the conservative half of a choice that deletes the same number of files either way.
    """
    ordered = sorted(dated_backups, key=lambda dated: dated[0])
    excess = len(ordered) - rotation
    if excess <= 0:
        return []

    if strategy != "hanoi":
        return [(backup, f"oldest of {len(ordered)} backups, over the rotation limit of {rotation}") for _, backup in ordered[:excess]]

    kept = hanoi_keep(ordered, rotation, period)
    by_period = newest_per_period(ordered, period)

    # The ladder asks for fewer files than the operator allows until the deep levels fill up --
    # reaching level k takes 2^k periods. The rest of the quota is not spent explicitly: taking
    # only `excess` victims, oldest first, leaves exactly the most recent unladdered backups
    # standing, which is the granularity near the present #3271 asks for.
    indices = sorted(by_period)
    victims = []
    for taken, backup in ordered:
        if backup in kept:
            continue
        index = period_index(taken, period)
        # A backup that is not the last of its period costs nothing to give up -- a newer copy of
        # the same period is still there -- so those go before anything that is a period's last.
        last_of_period = backup is by_period[index]
        if not last_of_period:
            reason = f"period {index} already has a newer backup"
        else:
            level, rank = hanoi_rank(index, indices, rotation - 1)
            reason = f"period {index} is off the Hanoi ladder: closest at level {level} (blocks of {1 << level} period(s)), {rank} blocks behind the newest, and only the last 2 are kept"
        victims.append((last_of_period, taken, backup, reason))
    victims.sort(key=lambda victim: victim[:2])
    return [(backup, reason) for _, _, backup, reason in victims[:excess]]


def rotate_backups(backups: list, rotation: int, strategy: str = "hanoi", period: timedelta = timedelta(days=1)) -> list:
    """Delete the backups the rotation policy gives up. Returns what was deleted."""
    victims = rotation_victims([(backup_time(backup), backup) for backup in backups], rotation, strategy, period)
    LOGGER.info(
        f"Backup rotation ({strategy}): {len(backups)} backup(s) present, limit {rotation}, removing {len(victims)}, keeping {len(backups) - len(victims)}"
    )
    for backup, reason in victims:
        LOGGER.warning(f"Removing old backup file: {backup}, {reason} ...")
        backup.unlink()
    return [backup for backup, _ in victims]


def update_cache_file(db: Database, backup_dir: Path) -> str:
    """Update the cache file in the database."""
    backup_data = loads(db.get_job_cache_file("backup-data", "backup.json") or "{}")
    backup_data["files"] = sorted([file.name for file in backup_dir.glob("backup-*.zip")])
    backup_data["date"] = datetime.now().astimezone().isoformat()
    content = dumps(backup_data, indent=2).encode()
    checksum = bytes_hash(content)
    err = db.upsert_job_cache(None, "backup.json", content, job_name="backup-data", checksum=checksum)
    if err:
        LOGGER.error(f"Failed to update the backup.json cache file: {err}")
        return err

    LOGGER.info("Backup cache file updated successfully")
    return ""


def write_backup_archive(backup_file: Path, member_name: str, payload: bytes) -> None:
    """Publish a backup archive atomically: build under `.zip.tmp`, then rename.

    Writing straight to the final name published a HALF-WRITTEN archive under a name every
    other part of the feature treats as a finished backup. A killed run therefore produced a
    truncated file that `update_cache_file` listed (:46), `bwcli restore` offered, and -- worst
    -- that counted toward BACKUP_ROTATION, so rotation deleted a GOOD backup to make room for
    a corrupt one (jobs/backup-data.py:93-105). At-least-once delivery makes that failure more
    frequent, but it was never dependent on it.

    `os.replace` is atomic within a directory, so the final name only ever appears complete;
    `backup-*.zip` does not match the temporary name, so an interrupted run is inert until the
    job sweeps it. The chmod deliberately happens BEFORE the rename: the payload is a full
    database dump, and chmod-after would publish it world-readable for the length of a syscall.
    """
    tmp_file = backup_file.with_suffix(".zip.tmp")
    with ZipFile(tmp_file, "w", compression=ZIP_DEFLATED) as zipf:
        zipf.writestr(member_name, payload)

    tmp_file.chmod(0o600)
    replace(tmp_file, backup_file)


def backup_database(current_time: datetime, db: Database = None, backup_dir: Path = BACKUP_DIR):
    """Backup the database."""
    db = db or Database(LOGGER)

    database_url = make_url(db.database_uri)
    database: Literal["sqlite", "mariadb", "mysql", "postgresql", "oracle"] = database_url.drivername.split("+")[0]
    backup_file = backup_dir.joinpath(f"backup-{database}-{current_time.strftime('%Y-%m-%d_%H-%M-%S')}.zip")
    LOGGER.debug(f"Backup file path: {backup_file}")
    stderr = "Table 'db.test_"
    current_time = datetime.now().astimezone()

    # Get table names from the SQLAlchemy model
    model_tables = list(Base.metadata.tables.keys())
    LOGGER.info(f"Backing up {len(model_tables)} tables defined in the model")

    while "Table 'db.test_" in stderr and (datetime.now().astimezone() - current_time).total_seconds() < 10:
        if database == "sqlite":
            db_path = Path(database_url.database)

            LOGGER.info("Creating a backup for the SQLite database ...")

            # Full SQLite database dump
            proc = run(
                ["sqlite3", db_path.as_posix()],
                input=".dump\n".encode(),
                stdout=PIPE,
                stderr=PIPE,
                env={"PATH": getenv("PATH", ""), "PYTHONPATH": getenv("PYTHONPATH", "")},
            )
        else:
            url = make_url(db.database_uri)
            db_user = url.username or ""
            db_password = url.password or ""
            db_host = url.host or ""
            db_port = str(url.port) if url.port else ""
            db_database_name = url.database or ""
            db_query_args = url.query if hasattr(url, "query") else {}

            if database in ("mariadb", "mysql"):
                LOGGER.info("Creating a backup for the MariaDB/MySQL database ...")

                dump_bin, mariadb_client = mysql_client_command("dump")
                cmd = [
                    dump_bin,
                    "-h",
                    db_host,
                    "-u",
                    db_user,
                    db_database_name,
                ]
                if db_port:
                    cmd.extend(["-P", db_port])

                # Add options to handle large data and improve compatibility
                cmd.extend(
                    [
                        "--single-transaction",  # Consistent backup for InnoDB
                        "--routines",  # Include stored procedures and functions
                        "--triggers",  # Include triggers
                        "--events",  # Include events
                        "--no-tablespaces",  # Avoid requiring the global PROCESS privilege
                        "--max_allowed_packet=2147483648",  # 2GB max packet size
                        "--quick",  # Retrieve rows one at a time
                        "--lock-tables=false",  # Don't lock tables
                        "--skip-add-locks",  # Don't add LOCK TABLES statements
                        "--default-character-set=utf8mb4",  # Use utf8mb4 charset
                        "--add-drop-table",  # Ensure DROP TABLE before CREATE
                    ]
                )

                # Avoid --set-gtid-purged for broad compatibility (MariaDB variant doesn't support it)

                cmd.extend(mysql_connection_args(db_query_args, mariadb_client))

                proc = run(
                    cmd,
                    stdout=PIPE,
                    stderr=PIPE,
                    env={"MYSQL_PWD": db_password, "PATH": getenv("PATH", ""), "PYTHONPATH": getenv("PYTHONPATH", "")},
                )
            elif database == "postgresql":
                LOGGER.info("Creating a backup for the PostgreSQL database ...")

                cmd = [
                    "pg_dump",
                    "-h",
                    db_host,
                    "-U",
                    db_user,
                    db_database_name,
                    "-w",
                    "--no-password",
                ]
                if db_port:
                    cmd.extend(["-p", db_port])

                # Add options to handle large data and improve compatibility
                cmd.extend(
                    [
                        "--clean",  # Include DROP statements for existing objects
                        "--if-exists",  # Avoid errors if objects do not exist
                        "--no-owner",  # Skip ownership commands
                        "--no-privileges",  # Skip privilege commands
                        "--format=plain",  # Plain text format
                        "--verbose",  # Verbose output for debugging
                    ]
                )

                # Apply additional arguments from query parameters
                pg_env = {"PGPASSWORD": db_password}
                for key, value in db_query_args.items():
                    if key == "sslmode":
                        pg_env["PGSSLMODE"] = value
                    elif key == "sslrootcert":
                        pg_env["PGSSLROOTCERT"] = value
                proc = run(
                    cmd,
                    stdout=PIPE,
                    stderr=PIPE,
                    env={"PATH": getenv("PATH", ""), "PYTHONPATH": getenv("PYTHONPATH", "")} | pg_env,
                )
            elif database == "oracle":
                LOGGER.warning("Creating a database backup for Oracle is not supported")
                return db

        stderr = proc.stderr.decode() if hasattr(proc, "stderr") and proc.stderr else ""
        if "Table 'db.test_" not in stderr and proc.returncode != 0:
            LOGGER.error(f"Failed to dump the database: {stderr}")
            sys_exit(1)

    if (datetime.now().astimezone() - current_time).total_seconds() >= 10:
        LOGGER.error("Failed to dump the database: Timeout reached")
        sys_exit(1)

    write_backup_archive(backup_file, backup_file.with_suffix(".sql").name, proc.stdout)

    LOGGER.info(f"💾 Backup {backup_file.name} created successfully in {backup_dir}")
    return db, backup_file


def restore_database(backup_file: Path, db: Database = None) -> Database:
    """Restore the database from a backup."""
    db = db or Database(LOGGER)
    database_url = make_url(db.database_uri)
    database: Literal["sqlite", "mariadb", "mysql", "postgresql", "oracle"] = database_url.drivername.split("+")[0]

    # Each dump speaks its own engine's dialect, and the restore clears the database first, so
    # feeding it the wrong one empties the database and then dies partway through the import
    # ("PRAGMA foreign_keys=OFF" is a syntax error to mysql). Backups of several engines share
    # one directory as soon as an install is migrated, so refuse before anything is destroyed.
    archived = backup_file.name.split("-")
    if len(archived) > 2 and archived[0] == "backup" and archived[1] != database:
        LOGGER.error(f"Backup {backup_file.name} was taken from a {archived[1]} database, but this instance runs {database}, aborting restore")
        sys_exit(1)

    Base.metadata.drop_all(db.sql_engine)

    if database == "sqlite":
        db_path = Path(database_url.database)

        # Clear the database. This used to be `.read /dev/null`, which reads an empty file and
        # clears nothing, so the only clearing was the drop_all above -- and that knows only the
        # tables declared in `model.py`, not the ones a plugin extension creates
        # (`bw_bunkernet_stats` and its indexes). `sqlite3 .dump` writes plain CREATE TABLE with
        # no DROP, unlike the MySQL (--add-drop-table) and PostgreSQL (--clean) dumps, so every
        # leftover object failed the restore with "table already exists" followed by UNIQUE
        # constraint errors on every row. Dropping the schema wholesale is what the other two
        # engines get from their dump.
        # Objects are dropped one by one rather than through `DELETE FROM sqlite_master`: the
        # sqlite3 shell runs with SQLITE_DBCONFIG_DEFENSIVE on, which refuses to modify the
        # schema table even after `PRAGMA writable_schema = 1`. Indexes and triggers go with
        # their table, and foreign keys are off in the shell, so the order does not matter.
        sqlite_env = {"PATH": getenv("PATH", ""), "PYTHONPATH": getenv("PYTHONPATH", "")}
        proc = run(
            [
                "sqlite3",
                db_path.as_posix(),
                "SELECT 'DROP ' || type || ' IF EXISTS \"' || name || '\";' FROM sqlite_master "
                "WHERE type IN ('table', 'view') AND name NOT LIKE 'sqlite_%';",
            ],
            stdout=PIPE,
            stderr=PIPE,
            env=sqlite_env,
        )
        if proc.returncode != 0:
            LOGGER.error(f"Failed to list the database objects before restoring it: {proc.stderr.decode(errors='replace')}")
            sys_exit(1)

        drops = proc.stdout.decode(errors="replace").strip()
        if drops:
            proc = run(
                ["sqlite3", db_path.as_posix()],
                input=f"{drops}\nVACUUM;\n".encode(),
                stdout=PIPE,
                stderr=PIPE,
                env=sqlite_env,
            )
            if proc.returncode != 0:
                LOGGER.error(f"Failed to clear the database before restoring it: {proc.stderr.decode(errors='replace')}")
                sys_exit(1)

        LOGGER.info("Restoring the SQLite database ...")

        tmp_file = Path(sep, "var", "tmp", "bunkerweb", backup_file.with_suffix(".sql").name)
        with ZipFile(backup_file, "r") as zipf:
            safe_zip_extractall(zipf, tmp_file.parent)

        proc = run(
            ["sqlite3", db_path.as_posix(), f".read {tmp_file.as_posix()}"],
            stdout=PIPE,
            stderr=PIPE,
            env={"PATH": getenv("PATH", ""), "PYTHONPATH": getenv("PYTHONPATH", "")},
        )
        tmp_file.unlink(missing_ok=True)
    else:
        url = make_url(db.database_uri)
        db_user = url.username or ""
        db_password = url.password or ""
        db_host = url.host or ""
        db_port = str(url.port) if url.port else ""
        db_database_name = url.database or ""
        db_query_args = url.query if hasattr(url, "query") else {}

        if database in ("mariadb", "mysql"):
            LOGGER.info("Restoring the MariaDB/MySQL database ...")

            restore_bin, mariadb_client = mysql_client_command("restore")
            cmd = [restore_bin, "-h", db_host, "-u", db_user, db_database_name]
            if db_port:
                cmd.extend(["-P", db_port])

            cmd.extend(mysql_connection_args(db_query_args, mariadb_client))

            with ZipFile(backup_file, "r") as zipf:
                proc = run(
                    cmd,
                    stdout=PIPE,
                    stderr=PIPE,
                    env={"PATH": getenv("PATH", ""), "PYTHONPATH": getenv("PYTHONPATH", ""), "MYSQL_PWD": db_password},
                    input=zipf.read(backup_file.with_suffix(".sql").name),
                )
        elif database == "postgresql":
            LOGGER.info("Restoring the PostgreSQL database ...")

            cmd = [
                "psql",
                "-h",
                db_host,
                "-U",
                db_user,
                db_database_name,
                "-v",
                "ON_ERROR_STOP=1",  # Stop immediately on error
                "--single-transaction",  # All-or-nothing restore
                "--no-psqlrc",  # Do not read user startup files
                "-X",  # Do not read ~/.psqlrc or ~/.pgpass implicitly
            ]
            if db_port:
                cmd.extend(["-p", db_port])

            # Apply additional arguments from query parameters
            pg_env = {"PGPASSWORD": db_password}
            for key, value in db_query_args.items():
                if key == "sslmode":
                    pg_env["PGSSLMODE"] = value
                elif key == "sslrootcert":
                    pg_env["PGSSLROOTCERT"] = value

            with ZipFile(backup_file, "r") as zipf:
                sql_name = backup_file.with_suffix(".sql").name
                sql_data = zipf.read(sql_name)

                # Sanitize dump for cross-version compatibility:
                # - Remove SET directives unknown to older servers (e.g., transaction_timeout)
                sql_text = sql_data.decode("utf-8", errors="ignore")
                set_blacklist = re.compile(r"^\s*SET\s+(transaction_timeout|idle_session_timeout)\s*=.*;\s*$", re.IGNORECASE)
                sanitized_lines = [line for line in sql_text.splitlines(True) if not set_blacklist.match(line)]
                sanitized_sql = "".join(sanitized_lines).encode()

                # Stabilize restore by setting safe defaults before feeding dump
                # Avoid superuser-only settings to preserve compatibility
                preamble = (
                    "SET client_min_messages = WARNING;\n"
                    "SET statement_timeout = 0;\n"
                    "SET lock_timeout = '5s';\n"
                    "SET idle_in_transaction_session_timeout = '5min';\n"
                    "SET client_encoding = 'UTF8';\n"
                    "SET standard_conforming_strings = on;\n"
                    "SET search_path = public, pg_catalog;\n"
                ).encode()
                input_bytes = preamble + sanitized_sql

                proc = run(
                    cmd,
                    stdout=PIPE,
                    stderr=PIPE,
                    input=input_bytes,
                    env={"PATH": getenv("PATH", ""), "PYTHONPATH": getenv("PYTHONPATH", "")} | pg_env,
                )
        elif database == "oracle":
            LOGGER.warning("Restoring a database backup for Oracle is not supported")
            return db

    if proc.returncode != 0:
        LOGGER.error(f"Failed to restore the database: {proc.stderr.decode()}")
        sys_exit(1)

    err = db.checked_changes(plugins_changes="all", value=True)
    if err:
        LOGGER.error(f"Error while applying changes to the database: {err}, you may need to reload the application")

    LOGGER.info(f"💾 Database restored successfully from {backup_file}")
    return db
